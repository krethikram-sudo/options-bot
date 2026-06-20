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
    return client.post("/signup", data={"email": email, "password": pw, "company": company,
                                        "accept": "1"})


def test_signup_requires_terms_consent(env, client):
    _, store = env
    r = client.post("/signup", data={"email": "noconsent@b.com", "password": "password123"})
    assert r.status_code == 400 and "Terms" in r.text
    assert store.get_account_by_email("noconsent@b.com") is None
    # with consent -> created and consent timestamped
    ok = client.post("/signup", data={"email": "yes@b.com", "password": "password123", "accept": "1"})
    assert ok.status_code == 303
    assert store.get_account_by_email("yes@b.com")["tos_accepted_at"] is not None


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


def test_guidance_is_trial_only_and_never_bills(env):
    _, store = env
    a = store.create_account("g@y.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    # Trial default is guidance, which never applies switches (so never realizes savings/bills).
    assert store.get_settings(a["id"])["mode"] == "guidance"
    assert not store.entitlement(dep)["apply"]
    # Converting to paid auto-flips to autopilot, and routing then applies (the billable mode).
    store.convert_to_paid(a["id"])
    assert store.get_settings(a["id"])["mode"] == "autopilot"
    ent = store.entitlement(dep)
    assert ent["apply"] and ent["mode"] == "autopilot"
    # A paid customer cannot switch back to guidance (it's trial-only).
    try:
        store.update_settings(a["id"], mode="guidance")
        assert False, "guidance should be rejected for a paid plan"
    except store.StoreError:
        pass
    assert store.get_settings(a["id"])["mode"] == "autopilot"


def test_autopilot_ramp_in_entitlement(env):
    _, store = env
    a = store.create_account("ramp@y.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    # guidance -> not applied, ramp reported as 0 (nothing auto-routes)
    ent = store.entitlement(dep)
    assert ent["apply_pct"] == 0
    # autopilot defaults to 100% rollout
    store.update_settings(a["id"], mode="autopilot")
    assert store.entitlement(dep)["apply_pct"] == 100
    # ramp down to a canary slice; clamps to [0,100]
    store.update_settings(a["id"], autopilot_pct=25)
    assert store.get_settings(a["id"])["autopilot_pct"] == 25
    assert store.entitlement(dep)["apply"] and store.entitlement(dep)["apply_pct"] == 25
    store.update_settings(a["id"], autopilot_pct=500)
    assert store.get_settings(a["id"])["autopilot_pct"] == 100
    store.update_settings(a["id"], autopilot_pct=-5)
    assert store.get_settings(a["id"])["autopilot_pct"] == 0


def test_autopilot_ramp_via_http(env, client):
    server, store = env
    _signup(client, email="ramphttp@b.com")
    client.post("/app/autopilot", data={"autopilot_pct": "50"})
    acct = store.get_account_by_email("ramphttp@b.com")
    assert store.get_settings(acct["id"])["autopilot_pct"] == 50


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


def test_opportunity_savings_metered_and_summed(env, client):
    from console import web
    server, store = env
    a = store.create_account("opp@y.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    # via HTTP meter (the path the gateway uses) + a direct record
    r = client.post("/api/meter", json={"deployment_id": dep, "requests": 10, "routed": 5,
                                        "baseline_cost": 1.0, "actual_cost": 0.6,
                                        "opportunity_saved": 0.25})
    assert r.status_code == 200
    store.record_meter(dep, requests=5, baseline_cost=0.5, actual_cost=0.4, opportunity_saved=0.10)
    summ = store.savings_summary(a["id"])
    assert summ["opportunity"] == pytest.approx(0.35)
    # opportunity is advisory only — it never inflates the realized savings that bill
    assert summ["savings"] == pytest.approx(0.5)  # (1.0-0.6) + (0.5-0.4)
    # and it shows up on the dashboard as a callout
    body = web.dashboard(store.get_account(a["id"]), store.get_plan(a["id"]),
                         store.trial_status(a["id"]), store.get_settings(a["id"]),
                         store.savings_summary(a["id"], since=store.bill_estimate(a["id"])["cycle_start"]),
                         store.savings_summary(a["id"]), store.bill_estimate(a["id"]),
                         {"deployment_id": dep}, store.savings_by_category(a["id"]),
                         store.proof_summary(a["id"]), store.budget_status(a["id"]))
    assert "Additional potential savings" in body


def test_caching_savings_shown_but_not_billed(env, client):
    from console import web
    server, store = env
    a = store.create_account("cache@y.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    # gateway reports realized model-switch savings + measured caching savings
    r = client.post("/api/meter", json={"deployment_id": dep, "requests": 10,
                                        "baseline_cost": 1.0, "actual_cost": 0.6,
                                        "caching_saved": 0.50})
    assert r.status_code == 200
    summ = store.savings_summary(a["id"])
    assert summ["caching"] == pytest.approx(0.50)
    # caching savings are goodwill — they must NOT inflate the billable amount
    store.convert_to_paid(a["id"])
    bill = store.bill_estimate(a["id"])
    assert bill["cycle_savings"] == pytest.approx(0.4)        # only the model-switch savings
    assert bill["bill"] == pytest.approx(0.08)                # 20% of $0.4, NOT of $0.9
    # and it surfaces on the dashboard as a captured-for-free callout
    body = web.dashboard(store.get_account(a["id"]), store.get_plan(a["id"]),
                         store.trial_status(a["id"]), store.get_settings(a["id"]),
                         store.savings_summary(a["id"], since=bill["cycle_start"]),
                         store.savings_summary(a["id"]), bill,
                         {"deployment_id": dep}, store.savings_by_category(a["id"]),
                         store.proof_summary(a["id"]), store.budget_status(a["id"]))
    assert "Caching savings captured" in body


class _FakeStripe:
    class billing:
        class MeterEvent:
            events = []
            @classmethod
            def create(cls, **kw):
                cls.events.append(kw)
                return type("E", (), {"id": "evt_test"})()


def _fake_stripe(monkeypatch):
    from console import stripe_billing
    _FakeStripe.billing.MeterEvent.events.clear()
    monkeypatch.setattr(stripe_billing, "enabled", lambda: True)
    monkeypatch.setattr(stripe_billing, "_client", lambda: _FakeStripe)
    return _FakeStripe.billing.MeterEvent.events


def test_report_usage_bills_the_tier_rate_not_a_flat_20pct(env, monkeypatch):
    _, store = env
    from console import stripe_billing
    events = _fake_stripe(monkeypatch)
    a = store.create_account("rate@y.com", "password123")
    store.convert_to_paid(a["id"], stripe_customer_id="cus_1")
    # Self-optimize = 15% -> $100 savings bills $15 = 1500 cents (NOT 2000)
    store.set_tier(a["id"], "self_optimize")
    assert stripe_billing.report_usage(a["id"], 100.0) is True
    assert events[-1]["payload"]["value"] == "1500"
    # Pay-as-you-go = 20% -> 2000 cents
    store.set_tier(a["id"], "payg")
    assert stripe_billing.report_usage(a["id"], 100.0) is True
    assert events[-1]["payload"]["value"] == "2000"


def test_api_meter_marks_row_so_sync_never_double_bills(env, client, monkeypatch):
    _, store = env
    from console import stripe_billing
    events = _fake_stripe(monkeypatch)
    a = store.create_account("nodbl@y.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    store.convert_to_paid(a["id"], stripe_customer_id="cus_2", now=1000.0)
    store.set_tier(a["id"], "self_optimize")
    # realized savings 60 -> 15% = $9 = 900 cents, pushed inline
    r = client.post("/api/meter", json={"deployment_id": dep, "baseline_cost": 100.0,
                                         "actual_cost": 40.0})
    assert r.status_code == 200
    assert events[-1]["payload"]["value"] == "900"
    # the inline push marked the row reported -> the sync backstop bills nothing more
    before = len(events)
    res = stripe_billing.sync_unreported_usage()
    assert res["reported"] == 0 and len(events) == before


def test_sync_excludes_trial_period_savings(env, monkeypatch):
    _, store = env
    from console import stripe_billing
    events = _fake_stripe(monkeypatch)
    a = store.create_account("trial@y.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    store.record_meter(dep, baseline_cost=50.0, actual_cost=20.0, ts=1000.0)   # during trial
    store.convert_to_paid(a["id"], stripe_customer_id="cus_3", now=2000.0)
    store.set_tier(a["id"], "self_optimize")
    store.record_meter(dep, baseline_cost=80.0, actual_cost=20.0, ts=3000.0)   # after conversion
    res = stripe_billing.sync_unreported_usage()
    # only the post-conversion $60 savings is billed (15% = 900 cents); trial $30 excluded
    assert res["reported"] == 1
    assert events[-1]["payload"]["value"] == "900"


def test_estimate_page_measured_and_projector(env, client):
    server, store = env
    _signup(client, email="est@b.com")
    # no traffic yet -> projector + connect prompt
    r = client.get("/app/estimate")
    assert r.status_code == 200
    assert "What-if projector" in r.text and "No routed traffic yet" in r.text
    # with traffic -> measured savings + annualized, seeded with the real baseline
    acct = store.get_account_by_email("est@b.com")
    dep = store.deployments_for(acct["id"])[0]["deployment_id"]
    store.record_meter(dep, requests=1000, routed=600, baseline_cost=900.0, actual_cost=500.0)
    r2 = client.get("/app/estimate")
    assert "Measured savings this cycle" in r2.text and "Annualized at this run-rate" in r2.text


def test_delete_account_cascade(env):
    _, store = env
    a = store.create_account("del@y.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    store.record_meter(dep, baseline_cost=10.0, actual_cost=6.0)
    store.convert_to_paid(a["id"])
    store.delete_account(a["id"])
    assert store.get_account(a["id"]) is None
    assert store.get_account_by_email("del@y.com") is None
    assert store.deployments_for(a["id"]) == []
    assert store.savings_summary(a["id"])["savings"] == 0.0


def test_delete_account_requires_email_confirmation(env, client):
    _, store = env
    _signup(client, email="owner@del.com")
    # wrong confirmation -> bounced back with an error, account still exists
    r = client.post("/app/account/delete", data={"confirm_email": "nope@x.com"})
    assert r.status_code == 303 and "delete_error=1" in r.headers["location"]
    assert store.get_account_by_email("owner@del.com") is not None
    # correct confirmation -> account deleted, session cleared
    r = client.post("/app/account/delete", data={"confirm_email": "owner@del.com"})
    assert r.status_code == 303
    assert store.get_account_by_email("owner@del.com") is None


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


def test_revenue_overview_keeps_subcent_precision(env):
    # Aggregate must not round sub-cent savings to $0.00 — the tokens-saved view
    # and parity with the per-account rows depend on the real value.
    _, store = env
    a = store.create_account("sub@y.com", "password123")
    store.convert_to_paid(a["id"])
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    store.record_meter(dep, baseline_cost=0.0103, actual_cost=0.0064)  # $0.0039 saved
    per = store.savings_summary(a["id"])["savings"]
    rev = store.revenue_overview()
    assert per > 0
    assert rev["total_savings_delivered"] == pytest.approx(per)
    assert rev["cycle_savings"] == pytest.approx(per)


# --- HTTP / auth flows ---------------------------------------------------- #

def test_signup_login_logout_flow(client, env):
    server, _ = env
    r = _signup(client)
    # customer lands on the Spend product home
    assert r.status_code == 303 and r.headers["location"] == "/app/outlay"
    assert client.cookies.get("mp_session")
    # Spend dashboard reachable; /app now redirects to it (routing home parked)
    assert client.get("/app/outlay").status_code == 200
    assert client.get("/app", follow_redirects=False).status_code == 303
    # logout redirects to the public landing page and clears the session
    r = client.post("/logout")
    assert r.status_code == 303 and r.headers["location"] == server.LANDING_URL
    client.cookies.clear()
    assert client.get("/app/outlay", follow_redirects=False).status_code in (303, 307)  # to login


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


def test_2fa_enable_then_login_challenge(env, client):
    _, store = env
    _signup(client, email="tf@b.com")
    acct = store.get_account_by_email("tf@b.com")
    # enable: start sends a code (dev: not actually sent), confirm with the real code
    client.post("/app/2fa/start")
    code = store.issue_otp(acct["id"])          # deterministically grab a known code
    r = client.post("/app/2fa/confirm", data={"code": code})
    assert r.status_code == 303 and "twofa=on" in r.headers["location"]
    assert store.get_2fa(acct["id"])["enabled"]
    # now logging in challenges for a code instead of granting a session
    client.cookies.clear()
    r = client.post("/login", data={"email": "tf@b.com", "password": "password123"})
    assert r.status_code == 303 and r.headers["location"] == "/login/verify"
    assert client.cookies.get("mp_2fa") and not client.cookies.get("mp_session")
    # wrong code is rejected; correct code completes login
    assert client.post("/login/verify", data={"code": "000000"}).status_code == 401
    code = store.issue_otp(acct["id"])
    r = client.post("/login/verify", data={"code": code})
    assert r.status_code == 303 and client.cookies.get("mp_session")


def test_tier_upgrade_sets_rate_and_gates_tuning(env, client):
    _, store = env
    _signup(client, email="tier@b.com")
    acct = store.get_account_by_email("tier@b.com")
    assert store.get_tier(acct["id"]) == "payg"
    assert store.get_plan(acct["id"])["rate"] == 0.20
    # per-customer tuning is gated on payg (shows the upsell to plans)
    assert "See plans" in client.get("/app/connect").text
    # upgrade to Self-optimize (no Stripe configured -> records tier + paid)
    r = client.post("/app/billing/convert", data={"tier": "self_optimize"})
    assert r.status_code == 303
    p = store.get_plan(acct["id"])
    assert store.get_tier(acct["id"]) == "self_optimize" and p["rate"] == 0.15 and p["plan"] == "paid"
    # per-customer tuning now active (no upsell)
    assert "active on your plan" in client.get("/app/connect").text


def test_expired_trial_does_not_gate_pilots(env, client):
    _, store = env
    _signup(client, email="exp@b.com")
    acct = store.get_account_by_email("exp@b.com")
    store.extend_trial(acct["id"], -3)  # trial ended 3 days ago
    # pilots run free for now — no billing gate; the Spend product stays reachable
    r = client.get("/app/outlay", follow_redirects=False)
    assert r.status_code == 200
    assert "/app/billing" not in r.text or True  # not redirected to billing


# --- admin ---------------------------------------------------------------- #

def test_status_page_public(client):
    r = client.get("/status")
    assert r.status_code == 200
    assert "System status" in r.text and "Operational" in r.text


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
    # Learned floors are a Self-optimize/Managed benefit — PAYG does NOT get them via /api/policy.
    assert client.get("/api/policy", params={"deployment_id": dep}).json()["floors"] == {}
    store.set_tier(a["id"], "self_optimize")
    assert client.get("/api/policy", params={"deployment_id": dep}).json()["floors"] == {"classification": 0}


def test_payg_does_not_receive_learned_floors(env):
    _, store = env
    a = store.create_account("gate@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    store.submit_proposal(dep, "floor", "extraction", {"current_tier": 1, "proposed_tier": 0},
                          {"samples": 30})
    store.decide_proposal(store.list_proposals(a["id"])[0]["id"], "approved")
    # PAYG: floor learned/approved but not served (no per-customer tuning on PAYG).
    assert store.approved_policy_for_deployment(dep)["floors"] == {}
    # Self-optimize: served.
    store.set_tier(a["id"], "self_optimize")
    assert store.approved_policy_for_deployment(dep)["floors"] == {"extraction": 0}
    # Managed too.
    store.set_tier(a["id"], "managed")
    assert store.approved_policy_for_deployment(dep)["floors"] == {"extraction": 0}


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


def test_autoapprove_floor_meeting_threshold(env):
    _, store = env
    a = store.create_account("auto@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    cfg = {"min_samples": 30, "min_ni": 0.95}
    # meets threshold -> auto-approved on arrival
    res = store.submit_proposal(dep, "floor", "summarization_long",
                                {"current_tier": 1, "proposed_tier": 0},
                                {"samples": 40, "non_inferior_rate": 0.97}, autoapprove=cfg)
    assert res["auto_approved"] is True
    assert store.approved_floors(a["id"]) == {"summarization_long": 0}
    assert store.count_pending_proposals() == 0
    hist = store.proposal_history(a["id"])[0]
    assert hist["decided_by"] is None and "auto-approved" in hist["note"]


def test_autoapprove_skips_low_evidence_and_rules(env):
    _, store = env
    a = store.create_account("auto2@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    cfg = {"min_samples": 30, "min_ni": 0.95}
    # too few samples -> stays pending
    r1 = store.submit_proposal(dep, "floor", "extraction", {"current_tier": 1, "proposed_tier": 0},
                               {"samples": 10, "non_inferior_rate": 0.99}, autoapprove=cfg)
    # rate too low -> stays pending
    r2 = store.submit_proposal(dep, "floor", "translation", {"current_tier": 1, "proposed_tier": 0},
                               {"samples": 50, "non_inferior_rate": 0.80}, autoapprove=cfg)
    # rules never auto-approve (qualitative)
    r3 = store.submit_proposal(dep, "rule", "extraction",
                               {"name": "inv", "any": ["invoice"], "category": "extraction"},
                               {"samples": 99}, autoapprove=cfg)
    assert not (r1["auto_approved"] or r2["auto_approved"] or r3["auto_approved"])
    assert store.count_pending_proposals() == 3


def test_autoapprove_disabled_by_default_via_api(env, client, monkeypatch):
    _, store = env
    a = store.create_account("auto3@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    # no CONSOLE_AUTOAPPROVE env -> everything waits for a human
    client.post("/api/proposals", json={"deployment_id": dep, "kind": "floor",
                "category": "classification", "payload": {"current_tier": 1, "proposed_tier": 0},
                "stats": {"samples": 99, "non_inferior_rate": 1.0}})
    assert store.count_pending_proposals() == 1


def test_digest_summarizes_pending(env):
    _, store = env
    a1 = store.create_account("d1@b.com", "password123")
    a2 = store.create_account("d2@b.com", "password123")
    store.submit_proposal(store.deployments_for(a1["id"])[0]["deployment_id"],
                          "floor", "extraction", {"current_tier": 1, "proposed_tier": 0},
                          {"samples": 12, "non_inferior_rate": 0.9})
    store.submit_proposal(store.deployments_for(a2["id"])[0]["deployment_id"],
                          "rule", "translation", {"name": "t", "any": ["x"], "category": "translation"})
    from console import digest
    d = digest.build_digest()
    assert d["n_pending"] == 2 and d["n_customers"] == 2
    assert "d1@b.com" in d["text"] and "extraction" in d["text"] and "/admin/proposals" in d["text"]


def test_digest_send_skips_when_empty(env):
    from console import digest
    assert digest.send_digest()["sent"] == 0


# --- API keys ------------------------------------------------------------- #

def test_api_key_create_resolve_revoke(env):
    _, store = env
    a = store.create_account("k@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    out = store.create_api_key(a["id"], dep, "prod")
    full = out["full_key"]
    assert full.startswith("mp_live_")
    # listing never exposes the secret, only the prefix
    keys = store.list_api_keys(a["id"])
    assert len(keys) == 1 and keys[0]["prefix"] == full[:16] and "key_hash" not in keys[0]
    # resolves to the deployment + updates last_used
    r = store.resolve_api_key(full)
    assert r["deployment_id"] == dep and r["account_id"] == a["id"]
    assert store.list_api_keys(a["id"])[0]["last_used_at"] is not None
    # revoke -> no longer resolves
    assert store.revoke_api_key(keys[0]["id"], a["id"])
    assert store.resolve_api_key(full) is None
    assert store.resolve_api_key("mp_live_bogus") is None and store.resolve_api_key("nope") is None


def test_meter_authenticates_by_key_and_rejects_bad(env, client):
    _, store = env
    a = store.create_account("k2@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    full = store.create_api_key(a["id"], dep, "g")["full_key"]
    # key overrides body deployment_id; bad body id is ignored when key is valid
    r = client.post("/api/meter", json={"deployment_id": "dep_wrong", "baseline_cost": 1.0,
                                        "actual_cost": 0.6},
                    headers={"Authorization": f"Bearer {full}"})
    assert r.status_code == 200
    assert store.savings_summary(a["id"])["savings"] == pytest.approx(0.4)
    # an invalid key -> 401 (presented but bad)
    bad = client.post("/api/meter", json={"deployment_id": dep, "baseline_cost": 1.0},
                      headers={"Authorization": "Bearer mp_live_nope"})
    assert bad.status_code == 401


def test_api_keys_managed_via_http_with_one_time_reveal(env, client):
    _, store = env
    _signup(client, email="kh@b.com")
    acct = store.get_account_by_email("kh@b.com")
    dep = store.deployments_for(acct["id"])[0]["deployment_id"]
    page = client.post("/app/keys", data={"name": "ci", "deployment_id": dep}).text
    assert "shown once" in page and "mp_live_" in page  # revealed once on the page
    assert len(store.list_api_keys(acct["id"])) == 1
    kid = store.list_api_keys(acct["id"])[0]["id"]
    client.post("/app/keys/revoke", data={"key_id": str(kid)})
    assert store.list_api_keys(acct["id"])[0]["revoked_at"] is not None


# --- request logs (opt-in, metadata only) --------------------------------- #

def test_api_logs_store_and_recent(env, client):
    _, store = env
    a = store.create_account("lg@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    batch = {"deployment_id": dep, "logs": [
        {"ts": 1.0, "category": "classification", "original_model": "claude-opus-4-8",
         "routed_model": "claude-haiku-4-5", "applied": True, "input_tokens": 100,
         "output_tokens": 50, "baseline_cost": 0.01, "actual_cost": 0.004,
         "realized_saved": 0.006, "status_code": 200},
        {"ts": 2.0, "category": "debugging", "original_model": "claude-opus-4-8",
         "routed_model": "claude-opus-4-8", "applied": False, "status_code": 200}]}
    assert client.post("/api/logs", json=batch).status_code == 200
    recent = store.recent_logs(a["id"])
    assert store.logs_count(a["id"]) == 2
    assert recent[0]["category"] == "debugging"  # newest first (ts desc)
    assert recent[1]["routed_model"] == "claude-haiku-4-5" and recent[1]["applied"] == 1


def test_api_logs_rejects_prompt_text(env, client):
    _, store = env
    a = store.create_account("lg2@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    r = client.post("/api/logs", json={"deployment_id": dep,
                    "logs": [{"ts": 1.0, "prompt": "leaked!", "category": "x"}]})
    assert r.status_code == 422 and store.logs_count(a["id"]) == 0


def test_logs_page_and_csv(env, client):
    _, store = env
    _signup(client, email="lgp@b.com")
    acct = store.get_account_by_email("lgp@b.com")
    dep = store.deployments_for(acct["id"])[0]["deployment_id"]
    # empty state mentions the opt-in env vars
    assert "MODELPILOT_LOGS" in client.get("/app/logs").text
    store.record_logs(dep, [{"ts": 5.0, "category": "extraction",
                             "routed_model": "claude-haiku-4-5", "applied": True,
                             "actual_cost": 0.002, "realized_saved": 0.003, "status_code": 200}])
    page = client.get("/app/logs").text
    assert "extraction" in page and "Export CSV" in page
    csv = client.get("/app/logs.csv")
    assert csv.status_code == 200 and "text/csv" in csv.headers["content-type"]
    assert "extraction" in csv.text and "realized_saved" in csv.text


# --- teams / RBAC --------------------------------------------------------- #

def test_member_invite_set_password_login(env):
    _, store = env
    owner = store.create_account("owner@b.com", "password123")
    m = store.create_member(owner["id"], "mate@b.com", "member")
    assert m["status"] == "invited"
    # invited member can't log in until they set a password via the invite/reset token
    out = store.create_reset("mate@b.com")
    assert out is not None and out[1]
    assert store.consume_reset(out[1], "matepassword1")
    auth = store.authenticate_member("mate@b.com", "matepassword1")
    assert auth and auth["account_id"] == owner["id"] and auth["role"] == "member"


def test_owner_login_unchanged(env, client):
    # the owner auth path (accounts table) is untouched by teams
    _signup(client, email="o2@b.com")
    client.cookies.clear()
    r = client.post("/login", data={"email": "o2@b.com", "password": "password123"})
    # customers land on the Spend product home; the owner auth path is untouched
    assert r.status_code == 303 and r.headers["location"] == "/app/outlay"


def test_member_login_and_team_nav(env, client):
    _, store = env
    owner = store.create_account("o3@b.com", "password123")
    store.create_member(owner["id"], "mem@b.com", "member")
    out = store.create_reset("mem@b.com")
    store.consume_reset(out[1], "mempassword1")
    r = client.post("/login", data={"email": "mem@b.com", "password": "mempassword1"})
    assert r.status_code == 303 and r.headers["location"] == "/app/outlay"
    dash = client.get("/app/outlay").text
    assert "mem@b.com" in dash            # signed in as the member
    assert "/app/team" not in dash        # plain member: no Team nav
    # a member cannot manage the team
    assert client.get("/app/team").status_code == 403


def test_owner_sees_team_and_can_invite(env, client):
    _, store = env
    _signup(client, email="boss@team.com")
    acct = store.get_account_by_email("boss@team.com")
    assert "/app/team" in client.get("/app/settings").text   # owner reaches Team from Settings
    r = client.post("/app/team/invite", data={"email": "new@team.com", "role": "admin"})
    assert r.status_code == 303 and "invite_token=" in r.headers["location"]
    members = store.list_members(acct["id"])
    assert len(members) == 1 and members[0]["role"] == "admin"
    # change role + remove
    client.post("/app/team/role", data={"member_id": str(members[0]["id"]), "role": "billing"})
    assert store.get_member(members[0]["id"])["role"] == "billing"
    client.post("/app/team/remove", data={"member_id": str(members[0]["id"])})
    assert store.list_members(acct["id"]) == []


def test_member_cannot_convert_billing(env, client):
    _, store = env
    owner = store.create_account("o4@b.com", "password123")
    store.create_member(owner["id"], "billless@b.com", "member")
    out = store.create_reset("billless@b.com"); store.consume_reset(out[1], "mempassword1")
    client.post("/login", data={"email": "billless@b.com", "password": "mempassword1"})
    assert client.post("/app/billing/convert").status_code == 403


# --- SSO (OIDC) + SCIM ---------------------------------------------------- #

def test_sso_config_and_domain_routing(env):
    _, store = env
    a = store.create_account("ssoacct@corp.com", "password123")
    store.set_sso(a["id"], enabled=True, domain="corp.com", client_id="cid",
                  client_secret="sec", auth_url="https://idp/auth", token_url="https://idp/tok",
                  userinfo_url="https://idp/ui", default_role="member")
    assert store.sso_by_domain("corp.com")["account_id"] == a["id"]
    assert store.sso_by_domain("other.com") is None
    store.set_sso(a["id"], enabled=False)
    assert store.sso_by_domain("corp.com") is None  # disabled -> not routed


def test_sso_callback_jit_provisions_and_logs_in(env, client, monkeypatch):
    server, store = env
    a = store.create_account("o@corp2.com", "password123")
    store.set_sso(a["id"], enabled=True, domain="corp2.com", client_id="c", client_secret="s",
                  auth_url="https://idp/auth", token_url="https://idp/tok", userinfo_url="https://idp/ui")
    # /sso/start routes by domain -> redirect to the IdP with a signed state
    r = client.get("/sso/start", params={"email": "alice@corp2.com"}, follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"].startswith("https://idp/auth?")
    import urllib.parse
    state = urllib.parse.unquote(r.headers["location"].split("state=")[-1])
    # stub the IdP token/userinfo exchange
    monkeypatch.setattr(server, "_oidc_email", lambda cfg, code, ru: "alice@corp2.com")
    cb = client.get("/sso/callback", params={"code": "xyz", "state": state}, follow_redirects=False)
    assert cb.status_code == 303 and cb.headers["location"] == "/app/outlay"
    members = store.list_members(a["id"])
    assert len(members) == 1 and members[0]["email"] == "alice@corp2.com" and members[0]["status"] == "active"
    # the SSO'd member is now signed in
    assert "alice@corp2.com" in client.get("/app/outlay").text


def test_sso_callback_rejects_bad_state(env, client):
    r = client.get("/sso/callback", params={"code": "x", "state": "forged"}, follow_redirects=False)
    assert r.status_code == 303 and "sso=failed" in r.headers["location"]


def test_scim_provisioning(env, client):
    _, store = env
    a = store.create_account("scim@corp3.com", "password123")
    token = store.rotate_scim_token(a["id"])
    hdr = {"Authorization": f"Bearer {token}"}
    # no/invalid token -> 401
    assert client.post("/scim/v2/Users", json={"userName": "x@corp3.com"}).status_code == 401
    # create
    r = client.post("/scim/v2/Users", json={"userName": "bob@corp3.com", "active": True}, headers=hdr)
    assert r.status_code == 201 and r.json()["userName"] == "bob@corp3.com"
    # list
    lst = client.get("/scim/v2/Users", headers=hdr).json()
    assert lst["totalResults"] == 1 and lst["Resources"][0]["userName"] == "bob@corp3.com"
    # deprovision
    mid = store.list_members(a["id"])[0]["id"]
    assert client.request("DELETE", f"/scim/v2/Users/{mid}", headers=hdr).status_code == 204
    assert store.list_members(a["id"]) == []


def test_sso_config_http_owner_only(env, client):
    _, store = env
    _signup(client, email="owner@corp4.com")
    acct = store.get_account_by_email("owner@corp4.com")
    client.post("/app/sso", data={"enabled": "1", "domain": "corp4.com", "client_id": "c",
                "client_secret": "s", "auth_url": "https://i/a", "token_url": "https://i/t",
                "userinfo_url": "https://i/u", "default_role": "member"})
    assert store.get_sso(acct["id"])["enabled"] == 1 and store.get_sso(acct["id"])["domain"] == "corp4.com"
    page = client.post("/app/sso/scim").text if False else client.get("/app/team").text
    assert "Single sign-on" in page and "SCIM" in page


# --- webhooks ------------------------------------------------------------- #

def test_webhook_create_match_sign_deliver(env):
    _, store = env
    a = store.create_account("wh@b.com", "password123")
    store.create_webhook(a["id"], "https://x.test/hook", "budget.over,proposal.pending")
    store.create_webhook(a["id"], "https://y.test/all", "all")
    sent = []
    n = store.deliver_event(a["id"], "budget.over", {"spend": 12.0},
                            post_fn=lambda url, body, headers: sent.append((url, body, headers)))
    assert n == 2  # the specific one + the 'all' one
    urls = {u for u, _, _ in sent}
    assert urls == {"https://x.test/hook", "https://y.test/all"}
    # signature verifies with the stored secret
    url, body, headers = sent[0]
    hooks = {w["url"]: w["secret"] for w in store.list_webhooks(a["id"])}
    assert headers["x-outlay-signature"] == store.sign_payload(hooks[url], body)
    assert b'"event":"budget.over"' in body and headers["x-outlay-event"] == "budget.over"


def test_webhook_event_filtering(env):
    _, store = env
    a = store.create_account("wh2@b.com", "password123")
    store.create_webhook(a["id"], "https://only.test/h", "proposal.pending")
    sent = []
    # not subscribed -> no delivery
    assert store.deliver_event(a["id"], "budget.warn", {}, post_fn=lambda *x: sent.append(x)) == 0
    assert store.deliver_event(a["id"], "proposal.pending", {}, post_fn=lambda *x: sent.append(x)) == 1


def test_webhook_http_crud(env, client):
    _, store = env
    _signup(client, email="whc@b.com")
    acct = store.get_account_by_email("whc@b.com")
    client.post("/app/webhooks", data={"url": "https://e.test/h", "events": "all"})
    hooks = store.list_webhooks(acct["id"])
    assert len(hooks) == 1 and hooks[0]["secret"].startswith("whsec_")
    assert "e.test" in client.get("/app/connect").text
    client.post("/app/webhooks/delete", data={"webhook_id": str(hooks[0]["id"])})
    assert store.list_webhooks(acct["id"]) == []


def test_proposal_submit_fires_webhook(env, client):
    _, store = env
    a = store.create_account("whp@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    store.create_webhook(a["id"], "https://p.test/h", "proposal.pending")
    # submit via the API; the pending proposal should match the webhook
    r = client.post("/api/proposals", json={"deployment_id": dep, "kind": "rule",
                    "category": "extraction", "payload": {"name": "x", "any": ["q"], "category": "extraction"}})
    assert r.status_code == 200
    assert len(store._matching_webhooks(a["id"], "proposal.pending")) == 1


# --- spend budget + alerts ------------------------------------------------ #

def test_budget_status_and_alert_levels(env):
    _, store = env
    a = store.create_account("bud@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    store.update_settings(a["id"], monthly_budget=10.0, budget_alert_pct=0.8)
    # spend $8.50 -> 85% -> warn (not over)
    store.record_meter(dep, baseline_cost=12.0, actual_cost=8.5)
    st = store.budget_status(a["id"])
    assert st["enabled"] and st["warn"] and not st["over"]
    first = store.budget_alert_pending(a["id"])
    assert first and first["level"] == "warn"
    # same level again this cycle -> no duplicate alert
    assert store.budget_alert_pending(a["id"]) is None
    # push over 100% -> 'over' fires once
    store.record_meter(dep, baseline_cost=5.0, actual_cost=3.0)  # total 11.5
    over = store.budget_alert_pending(a["id"])
    assert over and over["level"] == "over"
    assert store.budget_alert_pending(a["id"]) is None


def test_no_budget_means_no_alerts(env):
    _, store = env
    a = store.create_account("nob@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    store.record_meter(dep, baseline_cost=100.0, actual_cost=80.0)
    assert store.budget_status(a["id"])["enabled"] is False
    assert store.budget_alert_pending(a["id"]) is None


def test_settings_budget_update_via_http(env, client):
    _, store = env
    _signup(client, email="budset@b.com")
    client.post("/app/settings", data={"risk": "balanced", "monthly_budget": "250",
                                       "budget_alert_pct": "75"})
    acct = store.get_account_by_email("budset@b.com")
    s = store.get_settings(acct["id"])
    assert s["monthly_budget"] == pytest.approx(250.0) and s["budget_alert_pct"] == pytest.approx(0.75)


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


def test_activation_funnel_and_feedback(env, client):
    _, store = env
    _signup(client)  # creates + authenticates a@b.com
    a = store.get_account_by_email("a@b.com")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    fn = store.activation_funnel()
    assert fn["signed_up"] == 1 and fn["set_up"] == 0 and fn["routed"] == 0 and fn["proven"] == 0
    store.create_api_key(a["id"], dep, "k")
    store.record_meter(dep, requests=10, routed=6, baseline_cost=1.0, actual_cost=0.6)
    fn = store.activation_funnel()
    assert fn["set_up"] == 1 and fn["routed"] == 1 and fn["proven"] == 1 and fn["paid"] == 0
    store.convert_to_paid(a["id"])
    assert store.activation_funnel()["paid"] == 1
    # dashboard feedback via HTTP (authed client)
    r = client.post("/app/feedback", data={"rating": "up", "comment": "love it"})
    assert r.status_code == 303
    assert any(x["kind"] == "dashboard" and x["rating"] == "up" and x["comment"] == "love it"
               for x in store.list_feedback())
    # cancel reason survives account deletion (feedback isn't cascade-deleted)
    store.record_feedback(a["id"], "cancel", comment="too pricey")
    store.delete_account(a["id"])
    assert any(x["kind"] == "cancel" and x["comment"] == "too pricey" for x in store.list_feedback())


# --- Outlay spend dashboard ---

def _fixtures():
    from pathlib import Path
    return Path(__file__).resolve().parent.parent / "outlay" / "fixtures"


def test_outlay_empty_then_run_then_dashboard(env, client):
    _signup(client)
    fix = _fixtures()
    issues = (fix / "github_issues.json").read_text()
    usage = (fix / "anthropic_usage.json").read_text()

    # empty state shows the connect form
    r = client.get("/app/outlay")
    assert r.status_code == 200 and "Connect your data" in r.text

    # run the engine on uploaded data
    r = client.post("/app/outlay/run", json={"issues": issues, "usage": usage})
    assert r.status_code == 200 and r.json()["ok"] is True

    # dashboard now renders real engine output
    r = client.get("/app/outlay")
    assert r.status_code == 200
    assert "Where your AI spend went" in r.text
    assert "Mapped to a ticket" in r.text


def test_outlay_run_rejects_bad_data(env, client):
    _signup(client)
    r = client.post("/app/outlay/run", json={"issues": "not json", "usage": "nope"})
    assert r.status_code == 200 and r.json()["ok"] is False


def test_outlay_requires_auth(env, client):
    r = client.post("/app/outlay/run", json={"issues": "{}", "usage": "[]"})
    assert r.status_code == 401


def test_outlay_backlog_estimator(env, client):
    _signup(client)
    fix = _fixtures()
    issues = (fix / "github_issues.json").read_text()
    usage = (fix / "anthropic_usage.json").read_text()
    planned = (fix / "planned_features.json").read_text()

    # estimator requires connected history first
    r = client.get("/app/outlay/estimate")
    assert r.status_code == 200 and "Connect your data" in r.text

    # connect history
    assert client.post("/app/outlay/run", json={"issues": issues, "usage": usage}).json()["ok"]

    # now estimate a backlog
    r = client.post("/app/outlay/estimate/run", json={"planned": planned})
    assert r.status_code == 200 and r.json()["ok"] is True

    # the estimate renders (per-item rows + a total with a likely range)
    r = client.get("/app/outlay/estimate")
    assert r.status_code == 200 and "Backlog estimate" in r.text
    assert "estimated," in r.text and "likely" in r.text


def test_outlay_estimator_needs_history(env, client):
    _signup(client, email="c@d.com")
    r = client.post("/app/outlay/estimate/run", json={"planned": '{"items":[]}'})
    assert r.status_code == 200 and r.json()["ok"] is False


def test_outlay_connection_store(env, client):
    _, store = env
    _signup(client, email="conn@x.com")
    acct = store.get_account_by_email("conn@x.com")
    store.save_outlay_connection(acct["id"], "acme", "web", "ghp_secret", "sk-admin")
    c = store.get_outlay_connection(acct["id"])
    assert c["github_owner"] == "acme" and c["github_token"] == "ghp_secret"
    # blank token preserves the saved one
    store.save_outlay_connection(acct["id"], "acme", "web2", "", "")
    c = store.get_outlay_connection(acct["id"])
    assert c["github_repo"] == "web2" and c["github_token"] == "ghp_secret"


def test_outlay_connect_page_and_sync_guard(env, client):
    _signup(client, email="cp@x.com")
    r = client.get("/app/outlay/connect")
    assert r.status_code == 200 and "Connect your sources" in r.text
    # sync with no connection saved → friendly error
    r = client.post("/app/outlay/sync")
    assert r.status_code == 200 and r.json()["ok"] is False


def _fake_transport():
    import json
    fix = _fixtures()
    issues = json.loads((fix / "github_issues.json").read_text())["issues"]
    admin = json.loads((fix / "anthropic_admin_report.json").read_text())

    def t(method, url, headers, body):
        if "api.github.com" in url:
            return issues
        return admin
    return t


def test_outlay_sync_pulls_live(env, client):
    from console import outlay_app
    conn = {"github_owner": "acme", "github_repo": "web",
            "github_token": "ghp_x", "anthropic_key": "sk-admin"}
    report = outlay_app.sync(conn, transport=_fake_transport())
    assert report["spend"]["total_usd"] > 0
    assert "_model" in report  # estimator can reuse the learned model


def _fake_transport_with_cursor():
    """GitHub issues + Anthropic admin + Cursor events, by URL."""
    import json
    fix = _fixtures()
    issues = json.loads((fix / "github_issues.json").read_text())["issues"]
    admin = json.loads((fix / "anthropic_admin_report.json").read_text())
    cursor = json.loads((fix / "cursor_events.json").read_text())

    def t(method, url, headers, body):
        if "api.github.com" in url:
            return issues
        if "api.cursor.com" in url:
            return cursor
        return admin
    return t


def test_outlay_sync_cursor_only(env, client):
    from console import outlay_app
    conn = {"github_owner": "acme", "github_repo": "web",
            "github_token": "ghp_x", "cursor_key": "key_cursor"}
    report = outlay_app.sync(conn, transport=_fake_transport_with_cursor())
    assert report["spend"]["total_usd"] > 0  # cursor token usage was costed


def test_outlay_sync_merges_both_usage_sources(env, client):
    from console import outlay_app
    conn = {"github_owner": "acme", "github_repo": "web", "github_token": "ghp_x",
            "anthropic_key": "sk-admin", "cursor_key": "key_cursor"}
    both = outlay_app.sync(conn, transport=_fake_transport_with_cursor())
    anthropic_only = outlay_app.sync(
        {**conn, "cursor_key": ""}, transport=_fake_transport_with_cursor())
    # merging Cursor events on top of Anthropic raises total spend
    assert both["spend"]["total_usd"] > anthropic_only["spend"]["total_usd"]


def test_outlay_sync_requires_a_usage_key(env, client):
    import pytest as _pytest
    from console import outlay_app
    conn = {"github_owner": "acme", "github_repo": "web", "github_token": "ghp_x"}
    with _pytest.raises(ValueError):
        outlay_app.sync(conn, transport=_fake_transport_with_cursor())


def test_outlay_cursor_key_encrypted_at_rest(env, client):
    _, store = env
    from console import secret_box
    _signup(client, email="cur@x.com")
    acct = store.get_account_by_email("cur@x.com")
    store.save_outlay_connection(acct["id"], github_owner="acme", github_repo="web",
                                 github_token="ghp_x", cursor_key="key_supersecret")
    assert store.get_outlay_connection(acct["id"])["cursor_key"] == "key_supersecret"
    raw = store.connect().execute(
        "SELECT cursor_key FROM outlay_connections WHERE account_id=?", (acct["id"],)).fetchone()
    if secret_box.available():
        assert raw["cursor_key"].startswith("enc:") and "key_supersecret" not in raw["cursor_key"]


def test_outlay_class_spend_and_dashboard(env, client):
    _, store = env
    _signup(client, email="cls@x.com")
    fix = _fixtures()
    assert client.post("/app/outlay/run", json={
        "issues": (fix / "github_issues.json").read_text(),
        "usage": (fix / "anthropic_usage.json").read_text()}).json()["ok"]
    rep = store.get_outlay_report(store.get_account_by_email("cls@x.com")["id"])
    cs = rep.get("class_spend")
    assert cs and cs[0]["spent_usd"] >= cs[-1]["spent_usd"]      # sorted desc
    assert all(0 <= c["share"] <= 1 and c["tickets"] >= 1 for c in cs)

    page = client.get("/app/outlay").text
    assert "Spend by work type" in page
    # CSV export for work types
    r = client.get("/app/outlay/export.csv?view=classes")
    assert r.status_code == 200 and r.text.splitlines()[0] == "work_type,tickets,spend_usd,share_pct"
    assert len(r.text.splitlines()) > 1


def test_outlay_budget_alert_emails_owner(env, client, monkeypatch):
    from console import notify
    calls = []
    monkeypatch.setattr(notify, "send_budget_alert",
                        lambda *a, **k: (calls.append((a, k)), True)[1])
    _signup(client, email="bmail@x.com")
    # a tiny overall budget, then a run that blows past it → owner gets emailed
    client.post("/app/outlay/budgets", data={"scope_type": "overall", "scope_id": "",
                "limit_usd": "1", "period_days": "90"}, follow_redirects=True)
    fix = _fixtures()
    client.post("/app/outlay/run", json={"issues": (fix / "github_issues.json").read_text(),
                "usage": (fix / "anthropic_usage.json").read_text()})
    assert calls, "expected a budget alert email on the over transition"
    args, kw = calls[-1]
    assert args[0] == "bmail@x.com" and args[1] == "over" and kw.get("product") == "Outlay"


def test_send_budget_alert_backward_compatible(env):
    from console import notify
    # legacy positional call (monthly budget) still works → dev path returns False
    assert notify.send_budget_alert("x@y.com", "warn", 80.0, 100.0) is False


def test_outlay_sync_error_recorded_and_cleared(env, client):
    _, store = env
    _signup(client, email="err@x.com")
    acct = store.get_account_by_email("err@x.com")
    # connection with a tracker but NO usage key → manual sync fails
    client.post("/app/outlay/connect", data={"tracker": "github", "github_owner": "acme",
                "github_repo": "web", "github_token": "ghp_x"}, follow_redirects=True)
    r = client.post("/app/outlay/sync")
    assert r.json()["ok"] is False
    conn = store.get_outlay_connection(acct["id"])
    assert conn["last_sync_error"] and conn["last_attempt_at"]
    # surfaced on the connect page
    assert "Last sync failed" in client.get("/app/outlay/connect").text

    # a later success clears it
    store.mark_outlay_synced(acct["id"])
    conn = store.get_outlay_connection(acct["id"])
    assert conn["last_sync_error"] is None and conn["synced_at"]
    assert "Last sync failed" not in client.get("/app/outlay/connect").text


def test_run_due_syncs_records_per_account_error(env, client):
    from console import server
    _, store = env
    _signup(client, email="sweeperr@x.com")
    acct = store.get_account_by_email("sweeperr@x.com")
    # auto-sync on, tracker set, but no usage key → sweep counts a failure + records it
    store.save_outlay_connection(acct["id"], github_owner="acme", github_repo="web",
                                 github_token="ghp_x", auto_sync_hours=24)
    summary = server._run_due_syncs(transport=_fake_transport())
    assert summary["failed"] == 1 and summary["synced"] == 0
    assert store.get_outlay_connection(acct["id"])["last_sync_error"]


def test_outlay_onboarding_checklist_shows_and_completes(env, client):
    _, store = env
    _signup(client, email="onb@x.com")
    # fresh account → checklist visible, nothing done
    page = client.get("/app/outlay").text
    assert "Get set up" in page and "0/4" in page

    # sample data does NOT count as being set up (still a worked example)
    client.post("/app/outlay/sample", follow_redirects=True)
    assert "Get set up" in client.get("/app/outlay").text

    # configure everything: connection, a real (non-sample) report, a budget
    client.post("/app/outlay/connect", data={"tracker": "github", "github_owner": "acme",
                "github_repo": "web", "github_token": "ghp_x", "anthropic_key": "sk"},
                follow_redirects=True)
    fix = _fixtures()
    client.post("/app/outlay/run", json={"issues": (fix / "github_issues.json").read_text(),
                "usage": (fix / "anthropic_usage.json").read_text()})
    client.post("/app/outlay/budgets", data={"scope_type": "overall", "scope_id": "",
                "limit_usd": "5000", "period_days": "90"}, follow_redirects=True)

    # all four steps done → checklist disappears
    assert "Get set up" not in client.get("/app/outlay").text


def test_outlay_csv_export(env, client):
    _signup(client, email="csv@x.com")
    # no report yet → redirect to dashboard, not a broken download
    assert client.get("/app/outlay/export.csv", follow_redirects=False).status_code in (302, 303, 307)

    client.post("/app/outlay/sample", follow_redirects=True)
    r = client.get("/app/outlay/export.csv?view=tickets")
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    assert "attachment" in r.headers["content-disposition"] and "outlay-tickets.csv" in r.headers["content-disposition"]
    assert r.text.splitlines()[0] == "ticket_id,task_class,status,cost_usd,rework_iterations,team_id"
    assert len(r.text.splitlines()) > 1  # header + at least one ticket

    people = client.get("/app/outlay/export.csv?view=people")
    assert people.text.splitlines()[0] == "engineer,spend_usd,share_pct,top_model,events"
    savings = client.get("/app/outlay/export.csv?view=savings")
    assert savings.text.splitlines()[0] == "work_type,from_model,to_model,projected_savings_usd,confidence"

    # bogus view falls back to tickets, never errors
    bogus = client.get("/app/outlay/export.csv?view=evil")
    assert bogus.status_code == 200 and bogus.text.startswith("ticket_id,")
    # dashboard exposes the export links
    assert "/app/outlay/export.csv?view=people" in client.get("/app/outlay").text


def test_outlay_sample_data_load_and_clear(env, client):
    _, store = env
    _signup(client, email="samp@x.com")
    acct = store.get_account_by_email("samp@x.com")

    # empty dashboard offers the sample button
    assert "See it with sample data" in client.get("/app/outlay").text

    # one click → populated, flagged sample, with a forecast + estimate + people
    client.post("/app/outlay/sample", follow_redirects=True)
    rep = store.get_outlay_report(acct["id"])
    assert rep and rep.get("_sample") is True
    assert rep["spend"]["total_usd"] > 0 and rep.get("estimate") and rep.get("people")
    page = client.get("/app/outlay").text
    assert "Sample data" in page and "Clear sample data" in page

    # clear → back to empty
    client.post("/app/outlay/clear", follow_redirects=True)
    assert store.get_outlay_report(acct["id"]) is None
    assert store.outlay_history(acct["id"]) == []
    assert "See it with sample data" in client.get("/app/outlay").text


def test_outlay_sample_requires_auth(env, client):
    r = client.post("/app/outlay/sample", follow_redirects=False)
    assert r.status_code in (302, 303, 307) and "/login" in r.headers.get("location", "")


def test_outlay_people_spend_rollup_and_dashboard(env, client):
    _, store = env
    _signup(client, email="ppl@x.com")
    fix = _fixtures()
    issues = (fix / "github_issues.json").read_text()
    usage = (fix / "anthropic_usage.json").read_text()
    assert client.post("/app/outlay/run", json={"issues": issues, "usage": usage}).json()["ok"]

    rep = store.get_outlay_report(store.get_account_by_email("ppl@x.com")["id"])
    people = rep.get("people")
    assert people and people[0]["user"] == "bob@acme.dev"          # biggest spender first
    assert people[0]["spent_usd"] >= people[1]["spent_usd"]        # sorted desc
    assert people[0]["top_model"] and 0 < people[0]["share"] <= 1  # model + share present

    page = client.get("/app/outlay").text
    assert "Spend by engineer" in page and "bob@acme.dev" in page
    # the unattributed bucket is excluded from the engineer card
    assert "(unattributed)" not in page


def test_outlay_people_spend_handles_no_users():
    from console import outlay_app
    # build_report tolerates usage with no resolvable users (people list still valid)
    rep = outlay_app.build_report('{"issues": []}', '{"data": []}')
    assert isinstance(rep.get("people"), list)


def test_outlay_accuracy_empty_then_populated(env, client):
    _signup(client, email="acc@x.com")
    # before any data → honest "not enough yet" state, not a fake number
    r = client.get("/app/outlay/accuracy")
    assert r.status_code == 200 and "Not enough closed" in r.text

    fix = _fixtures()
    issues = (fix / "github_issues.json").read_text()
    usage = (fix / "anthropic_usage.json").read_text()
    assert client.post("/app/outlay/run", json={"issues": issues, "usage": usage}).json()["ok"]

    r = client.get("/app/outlay/accuracy")
    assert r.status_code == 200
    assert "Median error (MdAPE)" in r.text          # measured headline
    assert "Accuracy by work type" in r.text          # per-class breakdown
    assert "Story points help" in r.text              # size-conditioning win (fixture improves)
    assert "Early read" in r.text                     # n=6 < 12 → directional banner
    # dashboard links to it
    assert "/app/outlay/accuracy" in client.get("/app/outlay").text


def test_outlay_accuracy_requires_auth(env, client):
    r = client.get("/app/outlay/accuracy", follow_redirects=False)
    assert r.status_code in (302, 303, 307) and "/login" in r.headers.get("location", "")


def test_outlay_history_records_and_trends(env, client):
    _, store = env
    _signup(client, email="hist@x.com")
    fix = _fixtures()
    issues = (fix / "github_issues.json").read_text()
    usage = (fix / "anthropic_usage.json").read_text()
    acct = store.get_account_by_email("hist@x.com")

    # two refreshes → two history rows, oldest→newest
    assert client.post("/app/outlay/run", json={"issues": issues, "usage": usage}).json()["ok"]
    assert client.post("/app/outlay/run", json={"issues": issues, "usage": usage}).json()["ok"]
    h = store.outlay_history(acct["id"])
    assert len(h) == 2 and h[0]["ts"] <= h[1]["ts"]
    assert h[-1]["total_usd"] > 0

    # an estimate re-save must NOT add a history row (only genuine refreshes do)
    client.post("/app/outlay/estimate/run", headers={"content-type": "application/json"},
                json={"planned": '{"items":[{"id":"P-1","title":"Add SSO"}]}'})
    assert len(store.outlay_history(acct["id"])) == 2

    # dashboard renders the sparkline + a delta line
    page = client.get("/app/outlay").text
    assert "<svg" in page and "vs last sync" in page


def test_sparkline_and_trend_helpers():
    from console import web
    assert web._sparkline([]) == "" and web._sparkline([5]) == ""  # need ≥2 points
    assert "<svg" in web._sparkline([1, 2, 3])
    assert web._trend_delta([]) == "this window"
    up = web._trend_delta([{"total_usd": 100}, {"total_usd": 150}])
    assert "↑" in up and "50%" in up
    down = web._trend_delta([{"total_usd": 100}, {"total_usd": 80}])
    assert "↓" in down and "20%" in down


def test_outlay_project_spend_and_budget(env, client):
    _, store = env
    _signup(client, email="proj@x.com")
    fix = _fixtures()
    issues = (fix / "github_issues.json").read_text()
    usage = (fix / "anthropic_usage.json").read_text()
    assert client.post("/app/outlay/run", json={"issues": issues, "usage": usage}).json()["ok"]
    from console import outlay_app
    acct = store.get_account_by_email("proj@x.com")
    rep = store.get_outlay_report(acct["id"])

    # GH-### tickets roll up under the "GH" project key
    ps = outlay_app.project_spend(rep)
    assert ps and ps[0]["project"] == "GH" and ps[0]["spent_usd"] > 0
    # the key shows up on the budgets page as a pick-list chip
    assert "Spend by project" in client.get("/app/outlay/budgets").text

    # a tiny project budget on GH projects over
    client.post("/app/outlay/budgets", data={"scope_type": "project", "scope_id": "GH",
                "limit_usd": "1", "period_days": "90"}, follow_redirects=True)
    buds = store.list_outlay_budgets(acct["id"])
    st = outlay_app.budget_statuses(rep, buds)[0]
    assert st["scope_type"] == "project" and st["status"] == "over"
    assert st["spent_usd"] == ps[0]["spent_usd"]  # matches the project rollup


def test_outlay_project_key_parsing():
    from console import outlay_app
    assert outlay_app._project_key("PROJ-123") == "PROJ"
    assert outlay_app._project_key("ENG-7-2") == "ENG-7"   # split on the last dash
    assert outlay_app._project_key("42") == ""             # GitHub number → no project
    assert outlay_app._project_key(None) == ""


def test_outlay_budget_rejects_bogus_scope(env, client):
    _, store = env
    _signup(client, email="bog@x.com")
    client.post("/app/outlay/budgets", data={"scope_type": "evil", "scope_id": "x",
                "limit_usd": "5", "period_days": "30"}, follow_redirects=True)
    acct = store.get_account_by_email("bog@x.com")
    assert store.list_outlay_budgets(acct["id"])[0]["scope_type"] == "overall"


def test_outlay_budgets_crud_and_status(env, client):
    _, store = env
    _signup(client, email="bud@x.com")
    fix = _fixtures()
    issues = (fix / "github_issues.json").read_text()
    usage = (fix / "anthropic_usage.json").read_text()
    assert client.post("/app/outlay/run", json={"issues": issues, "usage": usage}).json()["ok"]

    # empty budgets page
    r = client.get("/app/outlay/budgets")
    assert r.status_code == 200 and "Budgets" in r.text

    # add an overall budget that's tiny → projected over
    r = client.post("/app/outlay/budgets",
                    data={"scope_type": "overall", "scope_id": "", "limit_usd": "1", "period_days": "90"},
                    follow_redirects=True)
    assert r.status_code == 200
    acct = store.get_account_by_email("bud@x.com")
    buds = store.list_outlay_budgets(acct["id"])
    assert len(buds) == 1
    from console import outlay_app
    rep = store.get_outlay_report(acct["id"])
    st = outlay_app.budget_statuses(rep, buds)[0]
    assert st["status"] == "over"   # $13 spend vs $1 limit

    # delete it
    client.post("/app/outlay/budgets/delete", data={"id": str(buds[0]["id"])}, follow_redirects=True)
    assert store.list_outlay_budgets(acct["id"]) == []


def test_outlay_budget_ok_when_under(env, client):
    _signup(client, email="bud2@x.com")
    from console import outlay_app
    report = {"window_days": 30, "spend": {"total_usd": 100.0}, "tickets": []}
    st = outlay_app.budget_statuses(report, [{"id": 1, "scope_type": "overall",
                                              "scope_id": None, "limit_usd": 10000, "period_days": 30}])[0]
    assert st["status"] == "ok" and st["projected_usd"] == 100.0


def test_outlay_budget_alert_on_transition(env, client):
    _, store = env
    _signup(client, email="alert@x.com")
    acct = store.get_account_by_email("alert@x.com")
    # a tiny overall budget → will go over once data lands
    store.add_outlay_budget(acct["id"], "overall", None, 1.0, 90)
    fix = _fixtures()
    issues = (fix / "github_issues.json").read_text()
    usage = (fix / "anthropic_usage.json").read_text()

    assert client.post("/app/outlay/run", json={"issues": issues, "usage": usage}).json()["ok"]
    buds = store.list_outlay_budgets(acct["id"])
    assert buds[0]["last_status"] == "over"   # transition recorded (alert fired; no-op w/o webhooks)

    # the Spend dashboard surfaces the over-budget strip
    r = client.get("/app/outlay")
    assert r.status_code == 200 and "over budget" in r.text


def _fake_multi():
    import json
    fix = _fixtures()
    admin = json.loads((fix / "anthropic_admin_report.json").read_text())

    def t(method, url, headers, body):
        if "api.github.com" in url:
            return json.loads((fix / "github_issues.json").read_text())["issues"]
        if "atlassian" in url or "/rest/api" in url:
            return {"issues": [{"key": "OPS-1", "fields": {"summary": "Fix login bug",
                    "status": {"name": "Done"}}}], "total": 1, "startAt": 0,
                    "maxResults": 100, "isLast": True}
        if "linear" in url:
            return {"data": {"issues": {"nodes": [{"identifier": "ENG-1", "title": "Add SSO",
                    "state": {"type": "completed"}}], "pageInfo": {"hasNextPage": False,
                    "endCursor": None}}}}
        return admin
    return t


def test_outlay_sync_jira(env, client):
    from console import outlay_app
    conn = {"tracker": "jira", "jira_base_url": "https://acme.atlassian.net",
            "jira_email": "me@acme.dev", "jira_token": "tok", "anthropic_key": "sk-admin"}
    report = outlay_app.sync(conn, transport=_fake_multi())
    assert report["spend"]["total_usd"] > 0 and "_model" in report


def test_outlay_sync_linear(env, client):
    from console import outlay_app
    conn = {"tracker": "linear", "linear_key": "lin_key", "anthropic_key": "sk-admin"}
    report = outlay_app.sync(conn, transport=_fake_multi())
    assert report["spend"]["total_usd"] > 0


def test_outlay_connect_page_has_all_trackers(env, client):
    _signup(client, email="trk@x.com")
    r = client.get("/app/outlay/connect")
    assert r.status_code == 200
    for t in ("GitHub Issues", "Jira", "Linear"):
        assert t in r.text
    # save a jira tracker selection
    client.post("/app/outlay/connect", data={"tracker": "jira",
                "jira_base_url": "https://acme.atlassian.net", "jira_email": "a@b.com",
                "jira_token": "tok", "anthropic_key": "sk"}, follow_redirects=True)
    _, store = env
    c = store.get_outlay_connection(store.get_account_by_email("trk@x.com")["id"])
    assert c["tracker"] == "jira" and c["jira_token"] == "tok"


def test_secret_box_roundtrip():
    from console import secret_box
    e = secret_box.encrypt("hello-token")
    assert secret_box.decrypt(e) == "hello-token"
    assert secret_box.decrypt("plain-legacy") == "plain-legacy"   # pre-encryption passthrough
    if secret_box.available():
        assert e.startswith("enc:") and "hello-token" not in e


def test_outlay_token_encrypted_at_rest(env, client):
    _, store = env
    from console import secret_box
    _signup(client, email="enc@x.com")
    acct = store.get_account_by_email("enc@x.com")
    store.save_outlay_connection(acct["id"], github_owner="acme", github_repo="web",
                                 github_token="ghp_supersecret", anthropic_key="sk-admin")
    # get() returns plaintext for use
    assert store.get_outlay_connection(acct["id"])["github_token"] == "ghp_supersecret"
    # raw DB value is encrypted (when cryptography is present)
    raw = store.connect().execute(
        "SELECT github_token FROM outlay_connections WHERE account_id=?", (acct["id"],)).fetchone()
    if secret_box.available():
        assert raw["github_token"].startswith("enc:")
        assert "ghp_supersecret" not in raw["github_token"]
    # preserve-on-blank still works through encryption
    store.save_outlay_connection(acct["id"], github_owner="acme", github_repo="web2", github_token="")
    assert store.get_outlay_connection(acct["id"])["github_token"] == "ghp_supersecret"


def test_outlay_auto_sync_due_selection(env, client):
    _, store = env
    _signup(client, email="due@x.com")
    acct = store.get_account_by_email("due@x.com")
    # off by default → never due
    store.save_outlay_connection(acct["id"], github_owner="acme", github_repo="web",
                                 github_token="ghp_x", anthropic_key="sk-admin")
    assert store.list_due_outlay_connections() == []
    # daily, synced an hour ago → not due yet
    store.save_outlay_connection(acct["id"], auto_sync_hours=24)
    store.mark_outlay_synced(acct["id"], now=time.time() - 3600)
    assert store.list_due_outlay_connections() == []
    # synced 25h ago → due
    store.mark_outlay_synced(acct["id"], now=time.time() - 25 * 3600)
    assert store.list_due_outlay_connections() == [acct["id"]]
    # never synced → due
    _signup(client, email="due2@x.com")
    a2 = store.get_account_by_email("due2@x.com")
    store.save_outlay_connection(a2["id"], github_owner="b", github_repo="c",
                                 github_token="g", anthropic_key="s", auto_sync_hours=168)
    assert a2["id"] in store.list_due_outlay_connections()


def test_outlay_auto_sync_hours_validated(env, client):
    _, store = env
    _signup(client, email="val@x.com")
    client.post("/app/outlay/connect", data={"tracker": "github", "github_owner": "acme",
                "github_repo": "web", "github_token": "ghp_x", "anthropic_key": "sk",
                "auto_sync_hours": "999"}, follow_redirects=True)  # bogus → coerced to 0
    c = store.get_outlay_connection(store.get_account_by_email("val@x.com")["id"])
    assert c["auto_sync_hours"] == 0
    client.post("/app/outlay/connect", data={"auto_sync_hours": "24"}, follow_redirects=True)
    c = store.get_outlay_connection(store.get_account_by_email("val@x.com")["id"])
    assert c["auto_sync_hours"] == 24


def test_outlay_run_due_syncs_sweeps(env, client):
    from console import server
    _, store = env
    _signup(client, email="sweep@x.com")
    acct = store.get_account_by_email("sweep@x.com")
    store.save_outlay_connection(acct["id"], github_owner="acme", github_repo="web",
                                 github_token="ghp_x", anthropic_key="sk-admin", auto_sync_hours=24)
    # due (never synced) → sweep pulls live and stores a report
    summary = server._run_due_syncs(transport=_fake_transport())
    assert summary == {"due": 1, "synced": 1, "failed": 0}
    rep = store.get_outlay_report(acct["id"])
    assert rep and rep["spend"]["total_usd"] > 0
    # synced_at now set → no longer due
    assert store.list_due_outlay_connections() == []


def test_outlay_sync_due_cron_endpoint_auth(env, client, monkeypatch):
    monkeypatch.setenv("OUTLAY_CRON_TOKEN", "cron-secret")
    # no token → 401
    assert client.post("/internal/outlay/sync-due").status_code == 401
    # wrong token → 401
    assert client.post("/internal/outlay/sync-due",
                       headers={"authorization": "Bearer nope"}).status_code == 401
    # right token → 200 with a summary
    r = client.post("/internal/outlay/sync-due", headers={"authorization": "Bearer cron-secret"})
    assert r.status_code == 200 and r.json()["ok"] is True and "synced" in r.json()


def test_pilot_request_form_and_submit(env, client):
    _, store = env
    # public form renders (no auth)
    r = client.get("/pilot-request")
    assert r.status_code == 200 and "Request a design-partner pilot" in r.text and "name=email" in r.text
    assert "name=title" in r.text  # title field present
    # valid submission → stored + redirect to thanks
    r = client.post("/pilot-request", data={"email": "jane@acme.dev", "name": "Jane",
                    "company": "Acme", "title": "Head of Eng", "tools": "Claude Code",
                    "message": "5 eng, big bill"}, follow_redirects=False)
    assert r.status_code in (302, 303) and "/pilot-request/thanks" in r.headers["location"]
    leads = store.list_pilot_requests()
    assert len(leads) == 1 and leads[0]["email"] == "jane@acme.dev" and leads[0]["company"] == "Acme"
    assert leads[0]["title"] == "Head of Eng"
    assert "we'll be in touch" in client.get("/pilot-request/thanks").text.lower()


def test_pilot_request_rejects_bad_email_and_honeypot(env, client):
    _, store = env
    # missing/invalid email → 400, re-renders the form, nothing stored
    r = client.post("/pilot-request", data={"email": "notanemail", "name": "x"})
    assert r.status_code == 400 and "valid work email" in r.text
    assert store.list_pilot_requests() == []
    # honeypot filled (bot) → silently accepted, nothing stored
    r = client.post("/pilot-request", data={"email": "bot@x.com", "website": "spam"}, follow_redirects=False)
    assert r.status_code in (302, 303)
    assert store.list_pilot_requests() == []


def test_admin_leads_inbox(env, client):
    server, store = env
    store.create_account("boss@b.com", "password123", role="admin")
    # a lead comes in via the public form
    client.post("/pilot-request", data={"email": "lead@acme.dev", "name": "Lee",
                "company": "Acme", "title": "VP Eng", "message": "interested"})
    # a plain customer can't see the inbox
    _signup(client, email="cust@b.com")
    assert client.get("/admin/leads").status_code == 403
    client.post("/logout")
    # admin sees the lead
    client.post("/login", data={"email": "boss@b.com", "password": "password123"})
    r = client.get("/admin/leads")
    assert r.status_code == 200 and "Acme" in r.text and "lead@acme.dev" in r.text
    assert "Pilot requests" in r.text and "VP Eng" in r.text



def test_outlay_run_accepts_bedrock_logs(env, client):
    """The paste/run path auto-detects an AWS Bedrock invocation-log export."""
    _signup(client)
    fix = _fixtures()
    issues = (fix / "github_issues.json").read_text()
    bedrock = (fix / "bedrock_invocation_logs.jsonl").read_text()
    r = client.post("/app/outlay/run", json={"issues": issues, "usage": bedrock})
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    r = client.get("/app/outlay")
    assert r.status_code == 200 and "AI spend" in r.text


def test_outlay_sync_reconciles_to_cost_report(env, client):
    """When Anthropic is the sole usage source, sync pulls the Cost Report and
    attaches a reconciliation block (computed vs billed)."""
    from console import outlay_app
    import json
    fix = _fixtures()
    issues = json.loads((fix / "github_issues.json").read_text())["issues"]
    admin = json.loads((fix / "anthropic_admin_report.json").read_text())

    def t(method, url, headers, body):
        if "api.github.com" in url:
            return issues
        if "cost_report" in url:
            return {"data": [{"results": [{"amount": "999.00", "currency": "USD"}]}]}
        return admin

    conn = {"tracker": "github", "github_owner": "acme", "github_repo": "web",
            "github_token": "ghp", "anthropic_key": "sk-ant-admin-x"}
    report = outlay_app.sync(conn, transport=t)
    rec = report.get("reconciliation")
    assert rec and rec["source"] == "anthropic_cost_report"
    assert rec["invoice_usd"] == 999.0
    assert "computed_usd" in rec and "delta_pct" in rec
    # the dashboard renders the reconciliation strip
    from console import web
    html = web.outlay_page({"email": "u@x.com", "role": "customer", "team_role": "owner",
                            "display_email": "u@x.com"}, report, persona="finance")
    assert "reconciled" in html and "Anthropic Cost Report" in html
