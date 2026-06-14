"""Console tests: auth, trial/entitlement, mode toggle, metering→savings→billing,
admin access control, and the machine API. Runs with Stripe disabled."""

import importlib
import time

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("CONSOLE_DB", str(tmp_path / "console.db"))
    monkeypatch.setenv("CONSOLE_SECRET", "test-secret")
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    import console.store as store
    import console.stripe_billing as sb
    import console.server as server
    importlib.reload(store)
    importlib.reload(sb)
    importlib.reload(server)
    store.init_db()
    return server, store


@pytest.fixture()
def client(env):
    server, _ = env
    return TestClient(server.app, follow_redirects=False)


def _signup(client, email="a@b.com", pw="password123", company="Acme"):
    return client.post("/signup", data={"email": email, "password": pw, "company": company})


# --- store-level ---------------------------------------------------------- #

def test_password_hash_roundtrip(env):
    _, store = env
    h, s = store.hash_password("hunter2longenough")
    assert store.verify_password("hunter2longenough", h, s)
    assert not store.verify_password("wrong", h, s)


def test_session_signing_rejects_tampering(env):
    _, store = env
    tok = store.make_session(5, "customer")
    assert store.read_session(tok)["account_id"] == 5
    assert store.read_session(tok + "x") is None
    assert store.read_session("garbage") is None


def test_create_account_sets_trial_and_deployment(env):
    _, store = env
    a = store.create_account("x@y.com", "password123", company="Y")
    assert a["role"] == "customer" and a["status"] == "active"
    deps = store.deployments_for(a["id"])
    assert len(deps) == 1 and deps[0]["deployment_id"].startswith("dep_")
    assert store.trial_status(a["id"])["active"]


def test_duplicate_email_rejected(env):
    _, store = env
    store.create_account("dup@y.com", "password123")
    with pytest.raises(store.StoreError):
        store.create_account("dup@y.com", "password123")


def test_entitlement_trial_paid_suspended(env):
    _, store = env
    a = store.create_account("e@y.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    # trial + default guidance mode -> entitled, not applied
    ent = store.entitlement(dep)
    assert ent["entitled"] and not ent["apply"] and ent["mode"] == "guidance"
    # autopilot -> applied
    store.update_settings(a["id"], mode="autopilot")
    assert store.entitlement(dep)["apply"]
    # expired trial -> not entitled
    store.extend_trial(a["id"], -1)
    assert not store.entitlement(dep)["entitled"]
    # paid -> entitled again
    store.convert_to_paid(a["id"])
    assert store.entitlement(dep)["entitled"] and store.entitlement(dep)["apply"]
    # suspended -> off
    store.set_status(a["id"], "suspended")
    assert not store.entitlement(dep)["entitled"]
    assert store.entitlement("dep_unknown")["reason"] == "unknown deployment"


def test_metering_and_billing(env):
    _, store = env
    a = store.create_account("m@y.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    store.record_meter(dep, requests=100, routed=60, baseline_cost=10.0, actual_cost=6.0,
                       category="classification")
    bill = store.bill_estimate(a["id"])
    assert bill["cycle_savings"] == pytest.approx(4.0)
    assert bill["would_bill"] == pytest.approx(0.8)   # 20% of $4
    assert bill["bill"] == 0.0                          # free during trial
    store.convert_to_paid(a["id"])
    assert store.bill_estimate(a["id"])["bill"] == pytest.approx(0.8)


def test_revenue_overview(env):
    _, store = env
    a = store.create_account("r1@y.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    store.record_meter(dep, baseline_cost=100.0, actual_cost=60.0)
    store.convert_to_paid(a["id"])
    rev = store.revenue_overview()
    assert rev["n_paid"] == 1
    assert rev["total_savings_delivered"] == pytest.approx(40.0)
    assert rev["total_revenue"] == pytest.approx(8.0)  # 20% of 40


# --- HTTP / auth flows ---------------------------------------------------- #

def test_signup_login_logout_flow(client):
    r = _signup(client)
    assert r.status_code == 303 and r.headers["location"] == "/app"
    assert client.cookies.get("mp_session")
    # dashboard reachable
    assert client.get("/app").status_code == 200
    # logout clears session
    client.post("/logout")
    client.cookies.clear()
    assert client.get("/app").status_code in (303, 307)  # redirect to login


def test_login_wrong_password(client):
    _signup(client, email="w@b.com")
    client.cookies.clear()
    r = client.post("/login", data={"email": "w@b.com", "password": "nope"})
    assert r.status_code == 401


def test_mode_toggle_persists(env, client):
    server, store = env
    _signup(client, email="mode@b.com")
    client.post("/app/mode", data={"mode": "autopilot"})
    acct = store.get_account_by_email("mode@b.com")
    assert store.get_settings(acct["id"])["mode"] == "autopilot"


def test_settings_update(env, client):
    server, store = env
    _signup(client, email="set@b.com")
    client.post("/app/settings", data={"risk": "aggressive", "min_model": "claude-sonnet-4-6"})
    acct = store.get_account_by_email("set@b.com")
    s = store.get_settings(acct["id"])
    assert s["risk"] == "aggressive" and s["min_model"] == "claude-sonnet-4-6"
    assert s["telemetry_opt_in"] == 0  # checkbox absent -> off


def test_convert_without_stripe_marks_paid(env, client):
    server, store = env
    _signup(client, email="pay@b.com")
    r = client.post("/app/billing/convert")
    assert r.status_code == 303
    acct = store.get_account_by_email("pay@b.com")
    assert store.get_plan(acct["id"])["plan"] == "paid"


# --- admin ---------------------------------------------------------------- #

def test_customer_cannot_access_admin(client):
    _signup(client, email="cust@b.com")
    assert client.get("/admin").status_code == 403


def test_admin_can_view_and_manage(env, client):
    server, store = env
    # make an admin directly, then log in via the client
    store.create_account("boss@b.com", "password123", role="admin")
    cust = store.create_account("c@b.com", "password123")
    client.post("/login", data={"email": "boss@b.com", "password": "password123"})
    assert client.get("/admin").status_code == 200
    assert client.get(f"/admin/accounts/{cust['id']}").status_code == 200
    # suspend the customer
    client.post(f"/admin/accounts/{cust['id']}/action", data={"action": "suspend"})
    assert store.get_account(cust["id"])["status"] == "suspended"
    # set rate to 30%
    client.post(f"/admin/accounts/{cust['id']}/action", data={"action": "set_rate", "rate": "30"})
    assert store.get_plan(cust["id"])["rate"] == pytest.approx(0.30)


# --- machine API ---------------------------------------------------------- #

def test_api_entitlement_and_meter(env, client):
    server, store = env
    a = store.create_account("api@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    ent = client.get("/api/entitlement", params={"deployment_id": dep}).json()
    assert ent["entitled"] is True
    r = client.post("/api/meter", json={"deployment_id": dep, "requests": 10, "routed": 5,
                                        "baseline_cost": 1.0, "actual_cost": 0.6})
    assert r.status_code == 200 and r.json()["realized_savings"] == pytest.approx(0.4)


def test_api_meter_rejects_sensitive_keys(env, client):
    server, store = env
    a = store.create_account("api2@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    r = client.post("/api/meter", json={"deployment_id": dep, "messages": [{"role": "user"}]})
    assert r.status_code == 422


def test_api_meter_unknown_deployment(client):
    r = client.post("/api/meter", json={"deployment_id": "dep_nope", "baseline_cost": 1})
    assert r.status_code == 404


# --- multiple deployments ------------------------------------------------- #

def test_multiple_deployments_roll_up_to_one_account(env):
    _, store = env
    a = store.create_account("multi@b.com", "password123")
    d1 = store.deployments_for(a["id"])[0]["deployment_id"]
    d2 = store.create_deployment(a["id"], label="staging")["deployment_id"]
    assert len(store.deployments_for(a["id"])) == 2
    store.record_meter(d1, baseline_cost=10.0, actual_cost=6.0)
    store.record_meter(d2, baseline_cost=5.0, actual_cost=4.0)
    # savings across both deployments sum to the one account
    assert store.savings_summary(a["id"])["savings"] == pytest.approx(5.0)


def test_create_and_rename_deployment_via_http(env, client):
    _, store = env
    _signup(client, email="dep@b.com")
    client.post("/app/deployments", data={"label": "prod"})
    acct = store.get_account_by_email("dep@b.com")
    deps = store.deployments_for(acct["id"])
    assert len(deps) == 2
    new = [d for d in deps if d["label"] == "prod"][0]
    client.post("/app/deployments/rename",
                data={"deployment_id": new["deployment_id"], "label": "prod-eu"})
    assert store.deployments_for(acct["id"])  # relabeled
    assert any(d["label"] == "prod-eu" for d in store.deployments_for(acct["id"]))


# --- password reset ------------------------------------------------------- #

def test_password_reset_flow(env):
    _, store = env
    store.create_account("reset@b.com", "oldpassword1")
    out = store.create_reset("reset@b.com")
    assert out is not None
    _, token = out
    assert store.consume_reset(token, "newpassword2") is True
    assert store.authenticate("reset@b.com", "newpassword2")
    assert not store.authenticate("reset@b.com", "oldpassword1")
    # single-use: token can't be reused
    assert store.consume_reset(token, "another3pw") is False


def test_reset_unknown_email_returns_none(env):
    _, store = env
    assert store.create_reset("nobody@b.com") is None


def test_expired_reset_rejected(env):
    _, store = env
    a = store.create_account("exp@b.com", "oldpassword1")
    out = store.create_reset("exp@b.com")
    _, token = out
    # simulate expiry by pushing the token's created_at into the past
    conn = store.connect()
    conn.execute("UPDATE resets SET created_at=created_at-99999 WHERE token=?", (token,))
    conn.commit(); conn.close()
    assert store.consume_reset(token, "newpassword2") is False


def test_forgot_and_reset_http(env, client):
    _, store = env
    store.create_account("httpreset@b.com", "oldpassword1")
    # forgot always returns the same "sent" page (no account enumeration)
    assert client.post("/forgot", data={"email": "httpreset@b.com"}).status_code == 200
    assert client.post("/forgot", data={"email": "nobody@b.com"}).status_code == 200
    out = store.create_reset("httpreset@b.com")
    _, token = out
    r = client.post("/reset", data={"token": token, "password": "brandnewpw9"})
    assert r.status_code == 303
    assert store.authenticate("httpreset@b.com", "brandnewpw9")


# --- aggregate proof ------------------------------------------------------ #

def test_proof_summary_and_meter(env, client):
    _, store = env
    a = store.create_account("proof@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    client.post("/api/meter", json={"deployment_id": dep, "baseline_cost": 1.0,
                                    "actual_cost": 0.7, "comparisons": 10, "non_inferior": 9})
    p = store.proof_summary(a["id"])
    assert p["comparisons"] == 10 and p["non_inferior"] == 9 and p["rate"] == pytest.approx(0.9)


# --- Tracks A/C: tuning proposals (submit -> admin review/approve -> apply) ---

def test_proposal_submit_supersede_and_approve(env):
    _, store = env
    a = store.create_account("prop@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    store.submit_proposal(dep, "floor", "summarization_long",
                          {"current_tier": 1, "proposed_tier": 0},
                          {"samples": 12, "non_inferior_rate": 0.95})
    # resubmitting supersedes the pending one (no pile-up)
    store.submit_proposal(dep, "floor", "summarization_long",
                          {"current_tier": 1, "proposed_tier": 0}, {"samples": 20})
    pend = store.list_proposals(a["id"], status="pending")
    assert len(pend) == 1 and pend[0]["stats"]["samples"] == 20
    # approve -> shows up in approved floors (taxonomy.floor_tier format)
    assert store.decide_proposal(pend[0]["id"], "approved")
    assert store.approved_floors(a["id"]) == {"summarization_long": 0}
    # deciding an already-decided proposal is a no-op
    assert store.decide_proposal(pend[0]["id"], "rejected") is False


def test_approved_rules_and_policy_for_deployment(env):
    _, store = env
    a = store.create_account("prop2@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    store.submit_proposal(dep, "rule", "extraction",
                          {"name": "invoices", "any": ["invoice"], "category": "extraction"},
                          {"samples": 30})
    pid = store.list_proposals(a["id"])[0]["id"]
    store.decide_proposal(pid, "approved")
    pol = store.approved_policy_for_deployment(dep)
    assert pol["rules"][0]["name"] == "invoices" and pol["floors"] == {}


def test_api_proposals_and_policy_http(env, client):
    _, store = env
    a = store.create_account("prop3@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    r = client.post("/api/proposals", json={
        "deployment_id": dep, "kind": "floor", "category": "classification",
        "payload": {"current_tier": 1, "proposed_tier": 0}, "stats": {"samples": 9}})
    assert r.status_code == 200
    # policy empty until approved
    assert client.get("/api/policy", params={"deployment_id": dep}).json()["floors"] == {}
    pid = store.list_proposals(a["id"])[0]["id"]
    store.decide_proposal(pid, "approved")
    assert client.get("/api/policy", params={"deployment_id": dep}).json()["floors"] == {"classification": 0}


def test_api_proposals_rejects_sensitive_keys(env, client):
    _, store = env
    a = store.create_account("prop4@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    r = client.post("/api/proposals", json={"deployment_id": dep, "kind": "rule",
                                            "category": "x", "messages": ["secret"]})
    assert r.status_code == 422


def test_admin_reviews_and_approves_proposal_via_http(env, client):
    _, store = env
    store.create_account("boss2@b.com", "password123", role="admin")
    cust = store.create_account("cust2@b.com", "password123")
    dep = store.deployments_for(cust["id"])[0]["deployment_id"]
    store.submit_proposal(dep, "floor", "extraction",
                          {"current_tier": 1, "proposed_tier": 0}, {"samples": 15})
    pid = store.list_proposals(cust["id"])[0]["id"]
    client.post("/login", data={"email": "boss2@b.com", "password": "password123"})
    # the proposal is visible on the customer detail page
    detail = client.get(f"/admin/accounts/{cust['id']}")
    assert "Proposed tuning" in detail.text and "extraction" in detail.text
    # approve it
    client.post(f"/admin/accounts/{cust['id']}/proposal",
                data={"proposal_id": str(pid), "decision": "approved"})
    assert store.approved_floors(cust["id"]) == {"extraction": 0}


def test_admin_bulk_approve_across_customers(env, client):
    _, store = env
    store.create_account("boss4@b.com", "password123", role="admin")
    c1 = store.create_account("c1@b.com", "password123")
    c2 = store.create_account("c2@b.com", "password123")
    d1 = store.deployments_for(c1["id"])[0]["deployment_id"]
    d2 = store.deployments_for(c2["id"])[0]["deployment_id"]
    store.submit_proposal(d1, "floor", "extraction", {"current_tier": 1, "proposed_tier": 0}, {"samples": 10})
    store.submit_proposal(d2, "floor", "classification", {"current_tier": 1, "proposed_tier": 0}, {"samples": 12})
    ids = [str(p["id"]) for p in store.list_proposals(status="pending")]
    assert len(ids) == 2
    client.post("/login", data={"email": "boss4@b.com", "password": "password123"})
    # the queue page lists both customers' pending proposals
    q = client.get("/admin/proposals").text
    assert "Review queue" in q and "c1@b.com" in q and "c2@b.com" in q
    # bulk-approve both (a list value encodes repeated `ids` keys)
    r = client.post("/admin/proposals/bulk",
                    data={"ids": ids, "decision": "approved", "note": "batch ok"})
    assert r.status_code == 303
    assert store.approved_floors(c1["id"]) == {"extraction": 0}
    assert store.approved_floors(c2["id"]) == {"classification": 0}
    assert store.count_pending_proposals() == 0
    # the decisions are attributed in each customer's audit trail
    assert store.proposal_history(c1["id"])[0]["note"] == "batch ok"


def test_admin_bulk_reject_only_selected(env, client):
    _, store = env
    store.create_account("boss5@b.com", "password123", role="admin")
    c1 = store.create_account("c3@b.com", "password123")
    d1 = store.deployments_for(c1["id"])[0]["deployment_id"]
    store.submit_proposal(d1, "floor", "extraction", {"current_tier": 1, "proposed_tier": 0}, {"samples": 10})
    store.submit_proposal(d1, "rule", "translation", {"name": "t", "any": ["traducir"], "category": "translation"}, {"samples": 9})
    pend = store.list_proposals(c1["id"], status="pending")
    keep = [p for p in pend if p["kind"] == "rule"][0]["id"]
    drop = [p for p in pend if p["kind"] == "floor"][0]["id"]
    client.post("/login", data={"email": "boss5@b.com", "password": "password123"})
    client.post("/admin/proposals/bulk", data={"ids": [str(drop)], "decision": "rejected"})
    # only the floor was rejected; the rule is still pending
    remaining = [p["id"] for p in store.list_proposals(c1["id"], status="pending")]
    assert remaining == [keep]


def test_proposal_audit_trail(env, client):
    _, store = env
    admin = store.create_account("boss3@b.com", "password123", role="admin")
    cust = store.create_account("cust3@b.com", "password123")
    dep = store.deployments_for(cust["id"])[0]["deployment_id"]
    store.submit_proposal(dep, "floor", "extraction", {"current_tier": 1, "proposed_tier": 0},
                          {"samples": 15})
    pid = store.list_proposals(cust["id"])[0]["id"]
    client.post("/login", data={"email": "boss3@b.com", "password": "password123"})
    client.post(f"/admin/accounts/{cust['id']}/proposal",
                data={"proposal_id": str(pid), "decision": "approved", "note": "looks safe"})
    hist = store.proposal_history(cust["id"])
    assert len(hist) == 1
    h = hist[0]
    assert h["status"] == "approved" and h["note"] == "looks safe"
    assert h["decided_by"] == admin["id"] and h["decided_by_email"] == "boss3@b.com"
    # the audit trail renders on the detail page
    assert "Tuning history" in client.get(f"/admin/accounts/{cust['id']}").text
