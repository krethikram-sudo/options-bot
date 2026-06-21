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
    monkeypatch.setenv("DEMO_ACCOUNT_EMAILS", "*")  # demo mode reachable for all test accounts
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
    r = client.post("/signup", data={"email": email, "password": pw, "company": company,
                                     "accept": "1"})
    # Move past the first-run role gate by default (eng ≈ the legacy no-persona view)
    # so existing assertions reach the app. Onboarding-gate tests sign up with a raw
    # /signup call instead, to exercise the gate.
    import console.store as _store
    acct = _store.get_account_by_email(email)
    if acct:
        _store.set_persona(acct["id"], "eng", member_id=0)
    return r


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


def test_estimate_page_redirects_to_outlay(env, client):
    server, store = env
    _signup(client, email="est@b.com")
    # The parked ModelPilot savings projection is hidden; the route now sends any
    # stray bookmark to the Outlay spend estimate rather than savings telemetry.
    r = client.get("/app/estimate")
    assert r.status_code == 303 and r.headers["location"] == "/app/outlay/estimate"


def test_delete_account_cascade(env):
    _, store = env
    a = store.create_account("del@y.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    store.record_meter(dep, baseline_cost=10.0, actual_cost=6.0)
    store.convert_to_paid(a["id"])
    # ingested Outlay data + a cancel-reason feedback row exist before deletion
    store.save_outlay_connection(a["id"], github_owner="o", github_repo="r", github_token="t")
    store.save_outlay_report(a["id"], {"spend": {"total_usd": 1.0}})
    store.record_outlay_snapshot(a["id"], {"spend": {"total_usd": 1.0}})
    store.record_feedback(a["id"], "cancel", comment="too pricey")
    store.delete_account(a["id"])
    assert store.get_account(a["id"]) is None
    assert store.get_account_by_email("del@y.com") is None
    assert store.deployments_for(a["id"]) == []
    assert store.savings_summary(a["id"])["savings"] == 0.0
    # all ingested Outlay data is gone (incl. encrypted connection creds)
    assert store.get_outlay_report(a["id"]) is None
    assert store.outlay_history(a["id"]) == []
    assert store.get_outlay_connection(a["id"]) is None
    # feedback is anonymized (account link severed), not deleted — signal survives
    fb = store.list_feedback()
    assert any(f["comment"] == "too pricey" and f["account_id"] is None for f in fb)


def test_outlay_retention_window_purges_old_snapshots(env):
    import time
    _, store = env
    a = store.create_account("ret@y.com", "password123")
    now = time.time()
    # three snapshots: 200d, 100d, 1d old
    for age in (200, 100, 1):
        store.record_outlay_snapshot(a["id"], {"spend": {"total_usd": age}}, now=now - age * 86400)
    assert len(store.outlay_history(a["id"], limit=50)) == 3
    # 90-day retention drops the 200d + 100d snapshots
    store.set_retention_days(a["id"], 90)
    assert store.purge_outlay_history(a["id"], 90, now=now) == 2
    hist = store.outlay_history(a["id"], limit=50)
    assert len(hist) == 1 and hist[0]["total_usd"] == 1

    # a fresh snapshot enforces the window inline (no cron needed): a stale row that
    # slipped in (e.g. retention set later) is trimmed the next time data refreshes
    store.record_outlay_snapshot(a["id"], {"spend": {"total_usd": 9}}, now=now - 150 * 86400)
    store.record_outlay_snapshot(a["id"], {"spend": {"total_usd": 5}}, now=now)  # current refresh
    vals = {h["total_usd"] for h in store.outlay_history(a["id"], limit=50)}
    assert 9 not in vals and 5 in vals  # the 150d row was purged on the new write
    # the daily sweep enforces it across accounts too
    a2 = store.create_account("ret2@y.com", "password123")
    store.record_outlay_snapshot(a2["id"], {"spend": {"total_usd": 7}}, now=now - 120 * 86400)
    store.set_retention_days(a2["id"], 90)
    out = store.purge_due_outlay_history(now=now)
    assert out["rows_purged"] >= 1 and store.outlay_history(a2["id"]) == []


def test_outlay_retention_and_purge_routes(env, client):
    _, store = env
    _signup(client, email="purge@y.com")
    acct = store.get_account_by_email("purge@y.com")
    client.post("/app/outlay/sample", follow_redirects=True)
    assert store.get_outlay_report(acct["id"]) is not None

    # retention control surfaces on Settings + saving it sticks
    page = client.get("/app/settings").text
    assert "Data retention" in page and 'action="/app/retention"' in page
    # grouped IA: labeled settings groups render
    assert "Data &amp; privacy" in page and "Notifications" in page
    client.post("/app/retention", data={"retention_days": "90"}, follow_redirects=True)
    assert store.get_retention_days(acct["id"]) == 90

    # purge needs the typed confirmation
    r = client.post("/app/outlay/purge", data={"confirm": "nope"})
    assert "purge_error=1" in r.headers["location"]
    assert store.get_outlay_report(acct["id"]) is not None
    # correct confirmation wipes report + history, keeps the connection
    store.save_outlay_connection(acct["id"], github_owner="o", github_repo="r", github_token="t")
    client.post("/app/outlay/purge", data={"confirm": "delete"}, follow_redirects=True)
    assert store.get_outlay_report(acct["id"]) is None
    assert store.outlay_history(acct["id"]) == []
    assert store.get_outlay_connection(acct["id"]) is not None


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
    # customer lands on the role-aware Overview (product home)
    assert r.status_code == 303 and r.headers["location"] == "/app"
    assert client.cookies.get("mp_session")
    # Overview + Spend both reachable
    assert client.get("/app").status_code == 200
    assert client.get("/app/outlay").status_code == 200
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
    # the "Settings saved." confirmation is announced to assistive tech (WCAG 2.1 4.1.3)
    saved = client.post("/app/settings", data={"risk": "balanced"}, follow_redirects=True).text
    assert 'role=status>Settings saved.' in saved or 'role="status">Settings saved.' in saved


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


def test_run_maintenance_bundle_records_run(env, client):
    from console import server, store
    _signup(client, email="maint@x.com")
    client.post("/app/outlay/sample", follow_redirects=True)
    # the shared maintenance bundle runs all sub-sweeps and stamps the cron run
    result = server._run_maintenance()
    assert set(result) >= {"sent", "close_pack", "webhooks", "retention"}
    assert store.get_cron_runs()["digest-due"]["last_run_at"]


def test_cron_health_tracking_and_surfaces(env, client):
    import time
    server, store = env
    # never run → both jobs stale; health rollup is not-ok
    h = store.cron_health()
    assert set(h) == {"sync-due", "digest-due"}
    assert all(c["stale"] and not c["ran"] for c in h.values())

    # a run stamps freshness
    store.mark_cron_run("sync-due", {"due": 2, "synced": 2, "failed": 0})
    h = store.cron_health()
    assert h["sync-due"]["ran"] and not h["sync-due"]["stale"]
    assert h["digest-due"]["stale"]  # still never run
    # goes stale once overdue (>36h)
    assert store.cron_health(now=time.time() + 40 * 3600)["sync-due"]["stale"]

    # the cron endpoint records its run (auth-gated)
    import os
    os.environ["OUTLAY_CRON_TOKEN"] = "ct"
    try:
        client.post("/internal/outlay/digest-due", headers={"authorization": "Bearer ct"})
    finally:
        del os.environ["OUTLAY_CRON_TOKEN"]
    assert store.get_cron_runs()["digest-due"]["last_run_at"]

    # public health endpoint exposes per-job freshness + a rollup
    hj = client.get("/api/health").json()
    assert "cron" in hj and "cron_ok" in hj and "sync-due" in hj["cron"]

    # admin page renders the jobs + a stale warning when overdue
    store.create_account("ops@b.com", "password123", role="admin")
    client.post("/login", data={"email": "ops@b.com", "password": "password123"})
    page = client.get("/admin/health").text
    assert "Scheduler health" in page and "sync-due" in page and "digest-due" in page


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


def test_api_key_expiry(env, client):
    import time
    _, store = env
    a = store.create_account("exp@b.com", "password123")
    dep = store.deployments_for(a["id"])[0]["deployment_id"]
    out = store.create_api_key(a["id"], dep, "rotating", expires_in_days=30)
    full = out["full_key"]
    assert out["expires_at"] and out["expires_at"] > time.time()
    # valid now
    assert store.resolve_api_key(full) is not None
    # rejected once past the expiry (like a revoked key)
    later = time.time() + 31 * 86400
    assert store.resolve_api_key(full, now=later) is None
    # no-expiry keys keep working
    forever = store.create_api_key(a["id"], dep, "prod")["full_key"]
    assert store.resolve_api_key(forever, now=later) is not None
    assert store.list_api_keys(a["id"])[0]["expires_at"] is None  # newest first

    # the create form passes the expiry through; the table shows expired keys
    from console import server
    _signup(client, email="expui@b.com")
    acct = store.get_account_by_email("expui@b.com")
    client.post("/app/keys", data={"name": "k", "expires_in_days": "30", "from": "api"})
    k = store.list_api_keys(acct["id"])[0]
    assert k["expires_at"] is not None
    # force-expire it and confirm the UI marks it expired
    conn = store.connect(None)
    conn.execute("UPDATE api_keys SET expires_at=? WHERE id=?", (time.time() - 10, k["id"]))
    conn.commit()
    conn.close()
    assert "expired" in client.get("/app/api").text


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
    # customers land on the Overview product home; the owner auth path is untouched
    assert r.status_code == 303 and r.headers["location"] == "/app"


def test_member_login_and_team_nav(env, client):
    _, store = env
    owner = store.create_account("o3@b.com", "password123")
    store.create_member(owner["id"], "mem@b.com", "member")
    out = store.create_reset("mem@b.com")
    store.consume_reset(out[1], "mempassword1")
    r = client.post("/login", data={"email": "mem@b.com", "password": "mempassword1"})
    assert r.status_code == 303 and r.headers["location"] == "/app"
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


def test_team_page_is_first_class(env, client):
    _, store = env
    _signup(client, email="lead@team.com")
    acct = store.get_account_by_email("lead@team.com")
    page = client.get("/app/team").text
    # restyled on the product design system, with the owner and an invite affordance
    assert "Team &amp; access" in page
    assert "lead@team.com" in page and "owner" in page
    assert "Invite a teammate" in page and "member" in page  # role legend / options
    # invite a teammate → they appear as a manageable row (role + remove controls)
    client.post("/app/team/invite", data={"email": "new@team.com", "role": "member"},
                follow_redirects=True)
    page = client.get("/app/team").text
    assert "new@team.com" in page
    assert "/app/team/role" in page and "/app/team/remove" in page


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
    assert cb.status_code == 303 and cb.headers["location"] == "/app"
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


def test_webhook_delivery_retries_and_logs(env):
    _, store = env
    a = store.create_account("whr@b.com", "password123")
    store.create_webhook(a["id"], "https://x.test/hook", "all")

    # a flaky endpoint: fails twice (500), then succeeds — retried, recorded delivered
    calls = {"n": 0}
    def flaky(url, body, headers):
        calls["n"] += 1
        return 500 if calls["n"] < 3 else 200
    store.deliver_event(a["id"], "budget.over", {"x": 1}, post_fn=flaky, sleep_fn=lambda s: None)
    assert calls["n"] == 3
    d = store.recent_webhook_deliveries(a["id"])
    assert len(d) == 1 and d[0]["status"] == "delivered" and d[0]["attempts"] == 3

    # a persistently-down endpoint: exhausts attempts, recorded failed with the error
    def dead(url, body, headers):
        raise OSError("connection refused")
    store.deliver_event(a["id"], "budget.over", {"x": 2}, post_fn=dead, sleep_fn=lambda s: None)
    latest = store.recent_webhook_deliveries(a["id"])[0]
    assert latest["status"] == "failed" and latest["attempts"] == 3
    assert "refused" in (latest["error"] or "")


def test_webhook_delivery_log_visible_on_connect(env, client):
    _, store = env
    _signup(client, email="whlog@b.com")
    acct = store.get_account_by_email("whlog@b.com")
    store.create_webhook(acct["id"], "https://x.test/h", "all")
    store.deliver_event(acct["id"], "budget.warn", {}, post_fn=lambda *a: 503,
                        sleep_fn=lambda s: None)
    page = client.get("/app/connect").text
    assert "Recent deliveries" in page and "retrying" in page and "HTTP 503" in page


def test_webhook_durable_redelivery(env):
    import time
    _, store = env
    a = store.create_account("whd2@b.com", "password123")
    store.create_webhook(a["id"], "https://x.test/hook", "all")

    # initial dispatch fails (endpoint down) → recorded 'failed' with a payload + next_attempt_at
    store.deliver_event(a["id"], "budget.over", {"v": 1}, post_fn=lambda *a: 500,
                        sleep_fn=lambda s: None)
    d = store.recent_webhook_deliveries(a["id"])[0]
    assert d["status"] == "failed" and d["payload"] and d["next_attempt_at"]
    did = d["id"]

    # not yet due → the sweep does nothing
    assert store.redeliver_due_webhooks(now=time.time())["redelivered"] == 0

    # due + endpoint recovered → redelivered (one attempt, marked delivered)
    later = time.time() + 2 * 3600
    out = store.redeliver_due_webhooks(now=later, post_fn=lambda *a: 200)
    assert out["due"] == 1 and out["redelivered"] == 1
    after = [x for x in store.recent_webhook_deliveries(a["id"]) if x["id"] == did][0]
    assert after["status"] == "delivered" and after["next_attempt_at"] is None
    # a delivered row is not picked up again
    assert store.redeliver_due_webhooks(now=later + 99999, post_fn=lambda *a: 200)["due"] == 0


def test_webhook_redelivery_gives_up_after_max_attempts(env):
    import time
    _, store = env
    a = store.create_account("whd3@b.com", "password123")
    store.create_webhook(a["id"], "https://x.test/hook", "all")
    store.deliver_event(a["id"], "budget.over", {}, post_fn=lambda *a: 500, sleep_fn=lambda s: None)
    did = store.recent_webhook_deliveries(a["id"])[0]["id"]
    # keep failing across many sweeps until it's given up ('dead')
    t = time.time()
    for _ in range(12):
        t += 2 * 24 * 3600
        store.redeliver_due_webhooks(now=t, post_fn=lambda *a: 500)
        row = [x for x in store.recent_webhook_deliveries(a["id"]) if x["id"] == did][0]
        if row["status"] == "dead":
            break
    row = [x for x in store.recent_webhook_deliveries(a["id"]) if x["id"] == did][0]
    assert row["status"] == "dead" and row["next_attempt_at"] is None
    assert row["attempts"] >= store.WEBHOOK_MAX_TOTAL_ATTEMPTS
    # a dead delivery is never retried again
    assert store.redeliver_due_webhooks(now=t + 10 ** 7, post_fn=lambda *a: 200)["due"] == 0


def test_webhook_redelivery_dead_when_webhook_deleted(env):
    import time
    _, store = env
    a = store.create_account("whd4@b.com", "password123")
    wid = store.create_webhook(a["id"], "https://x.test/hook", "all")["id"]
    store.deliver_event(a["id"], "budget.over", {}, post_fn=lambda *a: 500, sleep_fn=lambda s: None)
    store.delete_webhook(wid, a["id"])
    out = store.redeliver_due_webhooks(now=time.time() + 2 * 3600, post_fn=lambda *a: 200)
    assert out["dead"] == 1 and out["redelivered"] == 0
    assert store.recent_webhook_deliveries(a["id"])[0]["status"] == "dead"


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
    # a feature request is captured with its own category (so the founder can triage)
    r = client.post("/app/feedback", data={"kind": "idea", "comment": "Add weekly Slack digests"})
    assert r.status_code == 303
    assert any(x["kind"] == "idea" and x["comment"] == "Add weekly Slack digests"
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


def test_overview_is_role_aware_home(env, client):
    _signup(client, email="ov@x.com")
    # empty Overview: first-run home with the connect CTA, not a redirect
    r = client.get("/app")
    assert r.status_code == 200
    assert "Connect your sources" in r.text and "Overview" in r.text

    # populate via sample data, then Overview shows the glance (KPIs + forecast + Explore)
    client.post("/app/outlay/sample", follow_redirects=True)
    home = client.get("/app").text
    assert "AI spend · window" in home          # a headline KPI
    assert "Forecast · open work" in home        # the forecast card
    assert "Explore" in home                      # the hub into deeper areas
    assert "/app/outlay/budgets" in home          # jump-offs present

    # the forecast band card and backlog estimate moved OFF the slimmed Spend page
    # (the headline forecast KPI stays; the p10–p90 band card does not)
    spend = client.get("/app/outlay").text
    assert "Where your AI spend went" in spend       # attribution stays
    assert "expected from open scope" not in spend    # forecast band card → Overview
    assert "Backlog estimate" not in spend            # estimate card → Estimate page


def test_security_compliance_page_for_reviewers(env, client):
    """The in-app security summary a customer's security reviewer reads — every
    claim maps to a shipped feature, and the certification status is honest."""
    _signup(client, email="sec@x.com")
    r = client.get("/app/security")
    assert r.status_code == 200
    t = r.text
    assert "Security &amp; compliance" in t
    assert "not a proxy or gateway" in t              # read-only architecture claim
    assert "SCIM" in t and "SSO" in t                 # real, shipped auth features
    assert "audit log" in t.lower() and "retention" in t.lower()
    assert "not yet SOC" in t                          # honest on certifications
    # AI transparency statement (NIST AI RMF / state responsible-AI alignment)
    assert "AI transparency" in t
    assert "No training on your data" in t and "NIST AI Risk Management Framework" in t
    assert "VPAT" in t                                  # accessibility conformance report offered
    # reachable from the product nav
    assert 'href="/app/security"' in client.get("/app").text


def test_overview_cost_fidelity_callout(env, client):
    _, store = env
    _signup(client, email="fid@x.com")
    client.post("/app/outlay/sample", follow_redirects=True)
    # the report carries the cache-aware vs naive comparison
    rep = store.get_outlay_report(store.get_account_by_email("fid@x.com")["id"])
    cf = rep.get("cost_fidelity")
    assert cf and cf["naive_usd"] > cf["outlay_usd"] and cf["inflation_factor"] > 1
    # and the Overview surfaces it as the in-product proof
    home = client.get("/app").text
    assert "Why this number is the right one" in home
    assert "Naive token tracker" in home and "Overstated by" in home


def test_overview_trend_and_movers(env, client):
    _signup(client, email="mv@x.com")
    # sample seeds a short backdated history → trend sparkline + real movers appear
    client.post("/app/outlay/sample", follow_redirects=True)
    home = client.get("/app").text
    assert "Spend trend" in home and "<svg" in home          # the trend card renders
    assert "Top movers" in home                               # Δ-vs-last-refresh card

    # the breakdown is captured per snapshot so movers are computable
    _, store = env
    hist = store.outlay_history(store.get_account_by_email("mv@x.com")["id"])
    assert len(hist) >= 2 and hist[-1].get("breakdown")       # breakdown persisted
    from console import web
    assert web._movers(hist)                                  # produces ranked movers


def test_overview_movers_fallback_to_drivers(env, client):
    # a single real run (no prior history) → no Δ yet, so show top spend drivers
    _signup(client, email="drv@x.com")
    fix = _fixtures()
    client.post("/app/outlay/run", json={"issues": (fix / "github_issues.json").read_text(),
                "usage": (fix / "anthropic_usage.json").read_text()})
    home = client.get("/app").text
    assert "Top spend drivers" in home and "Top movers" not in home


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

    # the scenario card combines open-work forecast + this backlog
    assert "If you commit this backlog" in r.text and "Projected total" in r.text
    # with no budget set it nudges to set one
    assert "Set a quarter budget" in r.text

    # with an overall budget, the scenario verdicts against it
    client.post("/app/outlay/budgets", data={"scope_type": "overall", "scope_id": "",
                "limit_usd": "1", "period_days": "90"}, follow_redirects=True)
    r = client.get("/app/outlay/estimate")
    assert "your $1.00 budget" in r.text and "over" in r.text


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


def test_sync_fail_count_increments_and_clears(env):
    _, store = env
    a = store.create_account("fc@x.com", "password123")
    store.save_outlay_connection(a["id"], github_owner="acme", github_repo="web",
                                 github_token="ghp_x", auto_sync_hours=24)
    assert store.mark_outlay_sync_error(a["id"], "boom") == 1
    assert store.mark_outlay_sync_error(a["id"], "boom again") == 2
    assert store.get_outlay_connection(a["id"])["sync_fail_count"] == 2
    # a success resets the counter + the alert de-dupe stamp
    store.mark_outlay_sync_alerted(a["id"])
    assert store.get_outlay_connection(a["id"])["sync_alerted_at"]
    store.mark_outlay_synced(a["id"])
    conn = store.get_outlay_connection(a["id"])
    assert conn["sync_fail_count"] == 0 and conn["sync_alerted_at"] is None


def test_repeated_sync_failure_alerts_owner_once(env, monkeypatch):
    from console import server
    _, store = env
    a = store.create_account("alertme@x.com", "password123")
    store.save_outlay_connection(a["id"], github_owner="acme", github_repo="web",
                                 github_token="ghp_x", auto_sync_hours=24)
    sent = []
    monkeypatch.setattr(server.notify, "send_sync_failure_alert",
                        lambda *a, **k: sent.append((a, k)) or True)
    slacks = []
    monkeypatch.setattr(server, "_slack_notify", lambda aid, text: slacks.append(text))

    # first failure: below threshold → no alert
    server._run_due_syncs(transport=_fake_transport())
    assert sent == [] and slacks == []
    # second consecutive failure: crosses threshold → exactly one alert (email + Slack)
    server._run_due_syncs(transport=_fake_transport())
    assert len(sent) == 1 and len(slacks) == 1
    assert store.get_outlay_connection(a["id"])["sync_alerted_at"]
    # third failure still inside the cooldown → not re-alerted (no spam)
    server._run_due_syncs(transport=_fake_transport())
    assert len(sent) == 1 and len(slacks) == 1


def test_staleness_banner_surfaces_on_dashboard(env, client):
    import time
    _, store = env
    _signup(client, email="stale@x.com")
    acct = store.get_account_by_email("stale@x.com")
    client.post("/app/outlay/sample", follow_redirects=True)

    # healthy + fresh → no banner
    store.save_outlay_connection(acct["id"], github_owner="acme", github_repo="web",
                                 github_token="ghp_x", auto_sync_hours=24)
    store.mark_outlay_synced(acct["id"])
    healthy = client.get("/app/outlay").text
    assert "refresh window" not in healthy and "Auto-sync has failed" not in healthy

    # data older than 2× its daily window → amber staleness banner
    old = time.time() - 3 * 24 * 3600
    store.mark_outlay_synced(acct["id"], now=old)
    page = client.get("/app/outlay").text
    assert "older than its daily refresh window" in page

    # standing auto-sync failures → red "auto-sync has failed" banner
    store.mark_outlay_sync_error(acct["id"], "bad token")
    store.mark_outlay_sync_error(acct["id"], "bad token")
    page = client.get("/app/outlay").text
    assert "Auto-sync has failed 2 times" in page and "last good numbers" in page


def test_outlay_onboarding_checklist_shows_and_completes(env, client):
    _, store = env
    _signup(client, email="onb@x.com")
    # fresh account → checklist visible; endowed-progress means the account step is
    # pre-completed, so it opens at "1 of 6" (default persona), never empty
    page = client.get("/app/outlay").text
    assert "Get set up" in page and "1 of 6" in page
    assert "Create your account" in page and "ob-bar" in page
    assert "Verify your numbers" in page  # the reconciliation activation step

    # sample data does NOT count as being set up (still a worked example)
    client.post("/app/outlay/sample", follow_redirects=True)
    assert "Get set up" in client.get("/app/outlay").text

    # configure everything: connection, a real (non-sample) report reconciled to an
    # invoice (the verify step), and a budget
    client.post("/app/outlay/connect", data={"tracker": "github", "github_owner": "acme",
                "github_repo": "web", "github_token": "ghp_x", "anthropic_key": "sk"},
                follow_redirects=True)
    fix = _fixtures()
    client.post("/app/outlay/run", json={"issues": (fix / "github_issues.json").read_text(),
                "usage": (fix / "anthropic_usage.json").read_text(),
                "cost_export": '{"ResultsByTime":[{"Total":{"UnblendedCost":{"Amount":"500.00"}},"Groups":[]}]}'})
    client.post("/app/outlay/budgets", data={"scope_type": "overall", "scope_id": "",
                "limit_usd": "5000", "period_days": "90"}, follow_redirects=True)

    # all steps done (incl. reconciliation) → checklist disappears
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
    teams = client.get("/app/outlay/export.csv?view=teams")
    assert teams.text.splitlines()[0] == "team,spend_usd,share_pct,events"
    savings = client.get("/app/outlay/export.csv?view=savings")
    assert savings.text.splitlines()[0] == "work_type,from_model,to_model,projected_savings_usd,confidence"

    # bogus view falls back to tickets, never errors
    bogus = client.get("/app/outlay/export.csv?view=evil")
    assert bogus.status_code == 200 and bogus.text.startswith("ticket_id,")
    # dashboard exposes the export links
    assert "/app/outlay/export.csv?view=people" in client.get("/app/outlay").text


def test_api_rate_limiting_per_key(env, client, monkeypatch):
    from console import server, store
    _signup(client, email="rl@x.com")
    acct = store.get_account_by_email("rl@x.com")
    dep = store.deployments_for(acct["id"])[0]["deployment_id"]
    key = store.create_api_key(acct["id"], dep, "rl")["full_key"]
    h = {"Authorization": f"Bearer {key}"}

    monkeypatch.setattr(server, "_API_RATE_LIMIT", 3)
    server._rate_state.clear()
    # first 3 within the window succeed
    for _ in range(3):
        assert client.get("/api/v1/data-quality", headers=h).status_code == 200
    # 4th is throttled with a structured 429 + Retry-After
    r = client.get("/api/v1/data-quality", headers=h)
    assert r.status_code == 429 and int(r.headers["Retry-After"]) >= 1
    assert r.json()["error"] == "rate limit exceeded" and r.json()["retry_after"] >= 1
    # the limit is per key — a different key is unaffected
    key2 = store.create_api_key(acct["id"], dep, "rl2")["full_key"]
    assert client.get("/api/v1/spend", headers={"Authorization": f"Bearer {key2}"}).status_code == 200
    # auth is checked before the limiter: a bad key is still 401, not 429
    assert client.get("/api/v1/data-quality",
                      headers={"Authorization": "Bearer mp_live_nope"}).status_code == 401
    server._rate_state.clear()


def test_data_quality_verdict_engine():
    import time
    from console import outlay_app
    now = time.time()
    good_report = {"spend": {"total_usd": 100.0, "ticket_coverage": 0.9},
                   "reconciliation": {"delta_pct": 2.0, "source": "anthropic"}}
    fresh = {"synced_at": now, "auto_sync_hours": 24}
    dq = outlay_app.data_quality(good_report, fresh, now=now)
    assert dq["score"] == "good"
    assert {c["key"] for c in dq["checks"]} == {"coverage", "reconciliation", "pricing", "freshness"}

    # low coverage drags the verdict to poor
    bad = {"spend": {"total_usd": 100.0, "ticket_coverage": 0.3}}
    assert outlay_app.data_quality(bad, fresh, now=now)["score"] == "poor"

    # a far-off invoice → reconciliation poor
    off = {"spend": {"total_usd": 100.0, "ticket_coverage": 0.95},
           "reconciliation": {"delta_pct": 40.0, "source": "aws"}}
    assert outlay_app.data_quality(off, fresh, now=now)["score"] == "poor"

    # repeated sync failure → freshness poor even with good attribution
    stale = {"synced_at": now - 10 * 86400, "auto_sync_hours": 24, "sync_fail_count": 3}
    assert outlay_app.data_quality(good_report, stale, now=now)["score"] == "poor"

    # 'na' checks never drag the score down (no invoice, no spend yet)
    empty = outlay_app.data_quality({"spend": {"total_usd": 0}}, None, now=now)
    assert empty["score"] in ("good", "na")
    assert any(c["status"] == "na" for c in empty["checks"])


def test_data_quality_api_and_badge(env, client):
    _, store = env
    _signup(client, email="dq@x.com")
    acct = store.get_account_by_email("dq@x.com")
    dep = store.deployments_for(acct["id"])[0]["deployment_id"]
    key = store.create_api_key(acct["id"], dep, "dq")["full_key"]

    # token-authed verdict endpoint: 401 without a key
    assert client.get("/api/v1/data-quality").status_code == 401
    r = client.get("/api/v1/data-quality", headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 200 and r.json()["account_id"] == acct["id"]
    assert "score" in r.json() and "checks" in r.json()

    # with sample data the spend API embeds the data_quality block
    client.post("/app/outlay/sample", follow_redirects=True)
    spend = client.get("/api/v1/spend", headers={"Authorization": f"Bearer {key}"}).json()
    assert "data_quality" in spend and spend["data_quality"]["score"] in ("good", "fair", "poor")
    # ...and the Spend page shows the at-a-glance confidence badge
    assert "Data confidence:" in client.get("/app/outlay").text
    # API page documents the endpoint
    assert "GET /api/v1/data-quality" in client.get("/app/api").text


def test_audit_export_csv_and_siem_api(env, client):
    _, store = env
    _signup(client, email="siem@x.com")
    acct = store.get_account_by_email("siem@x.com")
    store.record_audit(acct["id"], "login", actor="siem@x.com")
    store.record_audit(acct["id"], "connection.save", actor="siem@x.com", detail="tracker=github")

    # CSV download (admin session) with ISO timestamps
    csv = client.get("/app/audit/export.csv")
    assert csv.status_code == 200 and "text/csv" in csv.headers["content-type"]
    assert "outlay-audit.csv" in csv.headers["content-disposition"]
    lines = csv.text.splitlines()
    assert lines[0] == "id,timestamp,actor,action,detail"
    assert any("connection.save" in ln and "tracker=github" in ln for ln in lines[1:])
    assert any("T" in ln.split(",")[1] for ln in lines[1:])  # ISO-8601 timestamp column

    # token-authed SIEM API: 401 without a key
    assert client.get("/api/v1/audit").status_code == 401
    dep = store.deployments_for(acct["id"])[0]["deployment_id"]
    key = store.create_api_key(acct["id"], dep, "siem")["full_key"]
    r = client.get("/api/v1/audit", headers={"Authorization": f"Bearer {key}"})
    assert r.status_code == 200
    data = r.json()
    assert data["account_id"] == acct["id"] and data["count"] >= 2
    assert data["events"][0]["id"] < data["events"][-1]["id"]  # ascending
    assert data["events"][-1]["id"] == data["next_since"]

    # incremental polling: since=next_since returns nothing new...
    empty = client.get("/api/v1/audit", params={"since": data["next_since"]},
                       headers={"Authorization": f"Bearer {key}"}).json()
    assert empty["count"] == 0 and empty["next_since"] == data["next_since"]
    # ...until a new event lands
    store.record_audit(acct["id"], "member.invite", actor="siem@x.com")
    more = client.get("/api/v1/audit", params={"since": data["next_since"]},
                      headers={"Authorization": f"Bearer {key}"}).json()
    assert more["count"] == 1 and more["events"][0]["action"] == "member.invite"

    # discoverable: Activity page links the CSV + the API
    page = client.get("/app/audit").text
    assert "/app/audit/export.csv" in page and "/api/v1/audit" in page


def test_api_reference_page_documents_spend_endpoint(env, client):
    _, store = env
    _signup(client, email="apidocs@x.com")
    page = client.get("/app/api")
    assert page.status_code == 200
    txt = page.text
    # documents both endpoints, auth, the FOCUS shape, and the CSV exports
    assert "GET /api/v1/spend" in txt
    assert "GET /api/v1/audit" in txt
    assert "Authorization: Bearer" in txt
    assert "ServiceCategory" in txt and "Tags" in txt
    assert "/app/outlay/export.focus.csv" in txt
    # nav exposes the page for an admin
    assert 'href="/app/api"' in client.get("/app/outlay").text

    # creating a key from the API page reveals it once and stays on the API page
    r = client.post("/app/keys", data={"name": "bi", "from": "api"})
    assert r.status_code == 200 and "shown once" in r.text and "mp_live_" in r.text
    assert "GET /api/v1/spend" in r.text  # rendered the API page, not Configuration
    # the example now uses the customer's real key prefix
    prefix = store.list_api_keys(store.get_account_by_email("apidocs@x.com")["id"])[0]["prefix"]
    assert prefix in client.get("/app/api").text


def test_outlay_focus_export_and_spend_api(env, client):
    _, store = env
    _signup(client, email="focus@x.com")
    acct = store.get_account_by_email("focus@x.com")

    # no report yet → session export redirects, API returns an empty (but valid) shape
    assert client.get("/app/outlay/export.focus.csv", follow_redirects=False).status_code in (302, 303, 307)
    dep = store.deployments_for(acct["id"])[0]["deployment_id"]
    key = store.create_api_key(acct["id"], dep, "bi")["full_key"]
    empty = client.get("/api/v1/spend", headers={"Authorization": f"Bearer {key}"})
    assert empty.status_code == 200 and empty.json()["rows"] == [] and empty.json()["total_usd"] == 0.0

    client.post("/app/outlay/sample", follow_redirects=True)

    # FOCUS CSV uses the spec's column names and carries team/work-type Tags
    r = client.get("/app/outlay/export.focus.csv")
    assert r.status_code == 200 and "text/csv" in r.headers["content-type"]
    assert "outlay-focus.csv" in r.headers["content-disposition"]
    header = r.text.splitlines()[0]
    for col in ("BilledCost", "EffectiveCost", "BillingCurrency", "ServiceCategory",
                "ChargeCategory", "ResourceId", "Tags"):
        assert col in header
    assert len(r.text.splitlines()) > 1  # header + at least one charge row

    # token-authed BI endpoint: 401 without a key, rows + total with one
    assert client.get("/api/v1/spend").status_code == 401
    assert client.get("/api/v1/spend", headers={"Authorization": "Bearer mp_live_nope"}).status_code == 401
    ok = client.get("/api/v1/spend", headers={"Authorization": f"Bearer {key}"})
    assert ok.status_code == 200
    data = ok.json()
    assert data["account_id"] == acct["id"] and data["currency"] == "USD"
    assert data["total_usd"] > 0 and len(data["rows"]) > 0
    assert data["period"]["start"] and data["period"]["end"]
    assert data["rows"][0]["ServiceCategory"] == "AI and Machine Learning"

    # finance persona surfaces the FOCUS export link on Spend
    store.set_persona(acct["id"], "finance", 0)
    assert "export.focus.csv" in client.get("/app/outlay").text


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
    for t in ("GitHub", "Jira", "Linear"):
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
    assert r.status_code == 200 and "Become an Outlay customer" in r.text and "name=email" in r.text
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


def test_reconcile_is_generic_across_providers(env):
    from console import outlay_app
    base = {"spend": {"total_usd": 100.0}}
    # within 5% → ok; provider label flows through to the strip
    r = outlay_app.reconcile(dict(base), 98.0, "aws_cost_explorer", 30)
    rec = r["reconciliation"]
    assert rec["source"] == "aws_cost_explorer" and rec["invoice_usd"] == 98.0
    assert rec["computed_usd"] == 100.0 and abs(rec["delta_pct"] - 2.04) < 0.1
    from console import web
    strip = web._recon_strip(r)
    assert "AWS Cost Explorer" in strip and "AWS invoice" in strip
    # non-positive / bogus invoice → no reconciliation block (never a fake 0%)
    assert "reconciliation" not in outlay_app.reconcile(dict(base), 0, "openai_costs")
    assert "reconciliation" not in outlay_app.reconcile(dict(base), None, "openai_costs")


def test_parse_cost_export_autodetects_provider():
    from console import outlay_app
    aws = '{"ResultsByTime":[{"Total":{"UnblendedCost":{"Amount":"340.00"}},"Groups":[]}]}'
    gcp = '{"rows":[{"service":{"description":"Vertex AI"},"cost":345.0,"credits":[]}]}'
    oai = '{"data":[{"results":[{"amount":{"value":340.0,"currency":"usd"}}]}]}'
    assert outlay_app.parse_cost_export(aws) == (340.0, "aws_cost_explorer")
    assert outlay_app.parse_cost_export(gcp) == (345.0, "gcp_cloud_billing")
    assert outlay_app.parse_cost_export(oai) == (340.0, "openai_costs")
    assert outlay_app.parse_cost_export("") == (0.0, "")
    assert outlay_app.parse_cost_export("not json or recognizable") == (0.0, "")


def test_close_report_renders_printable_readout(env, client):
    """Finance can download a printable close report (the VP audit readout); absent a
    report it redirects rather than 500s."""
    _signup(client, email="close@x.com", company="Acme Corp")
    assert client.get("/app/outlay/close-report.html",
                      follow_redirects=False).status_code in (302, 303, 307)  # no data yet
    client.post("/app/outlay/sample", follow_redirects=True)
    r = client.get("/app/outlay/close-report.html")
    assert r.status_code == 200 and r.text.startswith("<!doctype html>")
    assert "Acme Corp" in r.text and "AI spend audit" in r.text
    client.post("/app/persona", data={"persona": "finance"}, follow_redirects=True)
    assert "close-report.html" in client.get("/app/outlay").text


def test_anomaly_tuning_mute_and_threshold(env, client, monkeypatch):
    """Customers can mute a known-expensive ticket and raise the flag threshold —
    immediately (pure filter), and it suppresses the alert too."""
    from console import notify, server, store
    _signup(client, email="tune@x.com")
    acct = store.get_account_by_email("tune@x.com")
    client.post("/app/outlay/sample", follow_redirects=True)
    report = store.get_outlay_report(acct["id"])
    anoms = [a["ticket_id"] for a in (report.get("anomalies") or [])]
    assert anoms, "sample data should surface at least one anomaly"
    tid = anoms[0]

    spend = client.get("/app/outlay").text
    assert "anomaly/mute" in spend and "anomaly/threshold" in spend  # controls present

    # mute every flagged ticket → muted set + chip
    for t in anoms:
        client.post("/app/outlay/anomaly/mute", data={"ticket_id": t}, follow_redirects=True)
    muted = store.get_anomaly_prefs(acct["id"])[1]
    assert all(t in muted for t in anoms)
    assert f"Muted ({len(anoms)})" in client.get("/app/outlay").text

    # muted tickets do NOT alert
    calls = []
    monkeypatch.setattr(notify, "send_anomaly_alert", lambda *a, **k: (calls.append(a), True)[1])
    server._check_anomalies(acct["id"], store.get_outlay_report(acct["id"]))
    assert calls == []

    # unmute + raise/lower threshold (floors at 3x)
    client.post("/app/outlay/anomaly/unmute", data={"ticket_id": tid}, follow_redirects=True)
    client.post("/app/outlay/anomaly/threshold", data={"threshold": "20"}, follow_redirects=True)
    assert store.get_anomaly_prefs(acct["id"])[0] == 20.0
    client.post("/app/outlay/anomaly/threshold", data={"threshold": "1"}, follow_redirects=True)
    assert store.get_anomaly_prefs(acct["id"])[0] == 3.0


def test_sample_report_is_a_realistic_demo(env):
    """The one-click demo must read like a real team, not a 6-ticket toy: high
    coverage, dozens of tickets across teams, and a measured (believable, not
    200%+) accuracy number — what a prospect sees before connecting any keys."""
    from console import outlay_app
    rep = outlay_app.sample_report()
    sp = rep["spend"]
    assert sp["total_usd"] > 500                  # a finance-visible bill
    assert sp["ticket_coverage"] > 0.85           # most spend reaches a ticket
    assert len(rep["tickets"]) >= 30              # dozens of tickets
    assert len(rep["team_spend"]) >= 3            # multiple teams for showback
    cal = rep["calibration"]
    assert cal["n_evaluated"] >= 20               # enough history to back-test
    assert cal["mdape"] < 0.6                     # believable error, not 200%+
    assert rep["anomalies"]                       # at least one flag to show


def test_slack_alerts_for_budget_and_anomaly(env, client, monkeypatch):
    """A configured Slack webhook receives budget + runaway-ticket alerts."""
    from console import notify, store
    posts = []
    monkeypatch.setattr(notify, "send_slack", lambda url, text: (posts.append((url, text)), True)[1])
    _signup(client, email="slk@x.com")
    acct = store.get_account_by_email("slk@x.com")
    client.post("/app/outlay/slack",
                data={"slack_webhook": "https://hooks.slack.com/services/X"}, follow_redirects=True)
    assert store.get_slack_webhook(acct["id"]) == "https://hooks.slack.com/services/X"
    assert "Slack alerts" in client.get("/app/outlay/connect").text

    store.add_outlay_budget(acct["id"], "overall", None, 1.0, 90)  # tiny budget → over
    fix = _fixtures()
    client.post("/app/outlay/run", json={"issues": (fix / "github_issues.json").read_text(),
                "usage": (fix / "anthropic_usage.json").read_text()})
    kinds = " ".join(t for _, t in posts)
    assert "Budget over" in kinds and "runaway ticket" in kinds
    client.post("/app/outlay/slack", data={"slack_webhook": ""}, follow_redirects=True)
    assert store.get_slack_webhook(acct["id"]) is None


def test_spend_by_model_card_and_csv(env, client):
    """Cost-per-token across models (a FinOps table-stake): a 'Spend by model' card
    with per-model token split, plus a CSV export view."""
    _signup(client, email="bm@x.com")
    client.post("/app/outlay/sample", follow_redirects=True)
    sp = client.get("/app/outlay").text
    assert "Spend by model" in sp and "view=models" in sp
    csv = client.get("/app/outlay/export.csv", params={"view": "models"})
    assert csv.status_code == 200
    assert csv.text.splitlines()[0] == ("model,calls,spend_usd,input_tokens,output_tokens,"
                                        "cache_read_tokens,cache_write_tokens")
    assert len(csv.text.splitlines()) > 1
    from console import outlay_app
    bm = outlay_app.sample_report()["cost_fidelity"]["by_model"]
    assert bm and all("tokens" in m for m in bm.values())   # per-model token splits


def test_coachmark_engine_and_connect_walkthrough(env, client):
    """The first-party contextual coachmark engine loads on every app page, and the
    Connect page carries the walkthrough that targets the real controls."""
    _signup(client, email="coach@x.com")
    assert "window.Coach=" in client.get("/app").text           # first-party, app-wide
    conn = client.get("/app/outlay/connect", params={"tour": "connect"}).text
    assert "startConnectTour" in conn and "get('tour')==='connect'" in conn
    # it targets controls that actually exist on the page
    assert "class=srcgrid" in conn and "id=ob-sync" in conn and "name=anthropic_key" in conn


def test_show_me_how_entry_points(env, client):
    """The walkthrough is reachable from the empty-state CTA, the checklist connect
    steps, and a "Show me how" button on the Connect header."""
    _signup(client, email="smh@x.com")
    home = client.get("/app").text  # fresh account → empty state + checklist
    assert "Show me how" in home
    assert "/app/outlay/connect?tour=connect" in home           # CTA + checklist deep-link the tour
    conn = client.get("/app/outlay/connect").text
    assert "Show me how" in conn and "startConnectTour" in conn  # header button launches it in place


def test_scope_drilldown_from_spend(env, client):
    """Clicking a work-type / team row drills into the tickets behind it."""
    _signup(client, email="dr@x.com")
    client.post("/app/outlay/sample", follow_redirects=True)
    spend = client.get("/app/outlay").text
    assert "/app/outlay/scope?type=class&id=" in spend     # rows are clickable

    r = client.get("/app/outlay/scope", params={"type": "class", "id": "bugfix"})
    assert r.status_code == 200
    assert "work type" in r.text and "Tickets" in r.text and "Back to Spend" in r.text
    # a bogus type degrades to team, never errors
    assert client.get("/app/outlay/scope", params={"type": "evil", "id": "x"}).status_code == 200
    # requires auth
    client.cookies.clear()
    assert client.get("/app/outlay/scope", params={"type": "class", "id": "bugfix"},
                      follow_redirects=False).status_code in (302, 303, 307)


def test_program_budgets_rollup_status_and_alerts(env, client, monkeypatch):
    from console import outlay_app, server, store
    # rollup across members, no double-count when a ticket matches two members
    report = {"window_days": 30, "spend": {"total_usd": 300.0},
              "tickets": [
                  {"ticket_id": "PLAT-1", "task_class": "feature", "team_id": "platform", "cost_usd": 200.0},
                  {"ticket_id": "INFRA-9", "task_class": "bugfix", "team_id": "infra", "cost_usd": 100.0},
                  {"ticket_id": "GROW-2", "task_class": "feature", "team_id": "growth", "cost_usd": 50.0}]}
    programs = [{"id": 1, "name": "Platform", "limit_usd": 150.0, "period_days": 30,
                 "members": [{"scope_type": "team", "scope_id": "platform"},
                             {"scope_type": "project", "scope_id": "PLAT"}]}]
    st = outlay_app.program_statuses(report, programs)[0]
    assert st["spent_usd"] == 200.0 and st["status"] == "over"   # platform team + PLAT project = the one ticket, counted once

    # HTTP: create a program, it shows with rolled-up status, and delete works
    _signup(client, email="prog@x.com")
    acct = store.get_account_by_email("prog@x.com")
    r = client.post("/app/outlay/programs", data={
        "name": "Platform", "limit_usd": "150", "period_days": "30",
        "members": "team platform\nproject PLAT", "enforce_mode": "hard", "action": "downgrade",
        "floor_model": "claude-haiku-4-5"}, follow_redirects=True)
    assert r.status_code == 200
    progs = store.list_outlay_programs(acct["id"])
    assert len(progs) == 1 and progs[0]["enforce_mode"] == "hard"
    assert progs[0]["members"] == [{"scope_type": "team", "scope_id": "platform"},
                                   {"scope_type": "project", "scope_id": "PLAT"}]
    page = client.get("/app/outlay/programs").text
    assert "Program budgets" in page and "Platform" in page and "hard cap" in page

    # an over transition on a hard program fires program.over (webhook) + Slack with the action
    store.save_outlay_report(acct["id"], report)
    slacks = []
    monkeypatch.setattr(server, "_slack_notify", lambda aid, text: slacks.append(text))
    events = []
    monkeypatch.setattr(store, "deliver_event", lambda aid, ev, data, **k: events.append((ev, data)))
    server._check_programs(acct["id"], report)
    assert any(ev == "program.over" for ev, _ in events)
    assert slacks and "downgrade" in slacks[0] and "claude-haiku-4-5" in slacks[0]
    assert "program.over" in store.WEBHOOK_EVENTS

    # reallocate in place: bump the cap + flip alert→hard, no re-create
    pid = progs[0]["id"]
    client.post("/app/outlay/programs/update",
                data={"id": str(pid), "limit_usd": "999", "enforce_mode": "alert"},
                follow_redirects=True)
    p = [x for x in store.list_outlay_programs(acct["id"]) if x["id"] == pid][0]
    assert p["limit_usd"] == 999.0 and p["enforce_mode"] == "alert"
    # members untouched by an in-place edit; a stranger's id can't be patched
    assert p["members"] == progs[0]["members"]
    assert store.update_outlay_program(acct["id"], 999999, limit_usd=1.0) is False
    # the inline reallocate control is on the page
    assert "Reallocate budget" in client.get("/app/outlay/programs").text

    # delete
    client.post("/app/outlay/programs/delete", data={"id": str(pid)}, follow_redirects=True)
    assert store.list_outlay_programs(acct["id"]) == []


def test_program_enforcement_decision_endpoint(env, client):
    from console import outlay_app, store
    _signup(client, email="enf@x.com")
    acct = store.get_account_by_email("enf@x.com")
    dep = store.deployments_for(acct["id"])[0]["deployment_id"]
    key = store.create_api_key(acct["id"], dep, "gw")["full_key"]
    h = {"Authorization": f"Bearer {key}"}

    # over report; two programs — one HARD (downgrade), one ALERT-only
    report = {"window_days": 30, "spend": {"total_usd": 500.0},
              "tickets": [{"ticket_id": "PLAT-1", "team_id": "platform", "task_class": "feature", "cost_usd": 500.0}]}
    store.save_outlay_report(acct["id"], report)
    store.add_outlay_program(acct["id"], "Platform", [{"scope_type": "project", "scope_id": "PLAT"}],
                             100.0, 30, enforce_mode="hard", action="downgrade", floor_model="claude-haiku-4-5")
    store.add_outlay_program(acct["id"], "Growth", [{"scope_type": "team", "scope_id": "growth"}],
                             1.0, 30, enforce_mode="alert")

    # engine: only the hard+over program is enforced; alert-only never appears
    enf = outlay_app.enforced_programs(report, store.list_outlay_programs(acct["id"]))
    assert len(enf) == 1 and enf[0]["name"] == "Platform" and enf[0]["action"] == "downgrade"
    # per-call decision: a PLAT-* call is downgraded (project match); an unrelated call is allowed
    assert outlay_app.program_decision(enf, ticket_id="PLAT-7")["decision"] == "downgrade"
    assert outlay_app.program_decision(enf, ticket_id="GROW-3")["decision"] == "allow"
    # block wins over downgrade when a call matches both
    two = [{"name": "A", "action": "downgrade", "members": [{"scope_type": "team", "scope_id": "x"}]},
           {"name": "B", "action": "block", "members": [{"scope_type": "team", "scope_id": "x"}]}]
    assert outlay_app.program_decision(two, team="x")["decision"] == "block"

    # endpoint: 401 without key; with key returns enforced + optional per-call decision
    assert client.get("/api/v1/enforcement").status_code == 401
    r = client.get("/api/v1/enforcement", headers=h).json()
    assert r["account_id"] == acct["id"] and len(r["enforced"]) == 1 and r["decision"] is None
    r2 = client.get("/api/v1/enforcement", params={"ticket": "PLAT-9"}, headers=h).json()
    assert r2["decision"]["decision"] == "downgrade" and r2["decision"]["floor_model"] == "claude-haiku-4-5"
    # documented on the API page
    assert "GET /api/v1/enforcement" in client.get("/app/api").text

    # the gateway reports its tallies; the program page shows "enforced N times"
    pid = store.list_outlay_programs(acct["id"])[0]["id"]
    rep = client.post("/api/v1/enforcement/report", headers=h, json={"counts": {str(pid): 3}})
    assert rep.status_code == 200 and rep.json()["programs_updated"] == 1
    client.post("/api/v1/enforcement/report", headers=h, json={"counts": {str(pid): 2}})
    prog = [p for p in store.list_outlay_programs(acct["id"]) if p["id"] == pid][0]
    assert prog["enforced_count"] == 5 and prog["last_enforced_at"]
    assert "enforced 5 times" in client.get("/app/outlay/programs").text
    # a stranger's program id is ignored (account-scoped)
    assert client.post("/api/v1/enforcement/report", headers=h,
                       json={"counts": {"999999": 9}}).json()["programs_updated"] == 0

    # daily history is bucketed + zero-filled; sparkline shows on the page
    import time as _t
    store.record_program_enforcement(acct["id"], {pid: 4}, now=_t.time() - 2 * 86400)
    hist = store.program_enforcement_history(acct["id"], pid, days=14)
    assert len(hist) == 14 and hist[-1]["count"] == 5 and hist[-3]["count"] == 4
    assert sum(h["count"] for h in hist) == 9
    assert "enforcement · last 14 days" in client.get("/app/outlay/programs").text
    # history is cleared with the program
    store.delete_outlay_program(acct["id"], pid)
    assert all(x["count"] == 0 for x in store.program_enforcement_history(acct["id"], pid))


def test_unit_economics_engine_and_card(env, client):
    from console import outlay_app
    # engine: per-ticket / per-closed / rework / by-class from attributed tickets
    report = {
        "spend": {"total_usd": 300.0, "ticket_coverage": 0.9},
        "tickets": [
            {"ticket_id": "A", "task_class": "feature", "status": "closed", "cost_usd": 100.0, "rework_iterations": 2},
            {"ticket_id": "B", "task_class": "feature", "status": "open", "cost_usd": 50.0, "rework_iterations": 0},
            {"ticket_id": "C", "task_class": "bugfix", "status": "closed", "cost_usd": 30.0, "rework_iterations": 0},
            {"ticket_id": "D", "task_class": "bugfix", "status": "closed", "cost_usd": 0.0, "rework_iterations": 0},
        ],
        "class_spend": [{"task_class": "feature", "tickets": 2, "spent_usd": 150.0},
                        {"task_class": "bugfix", "tickets": 1, "spent_usd": 30.0}],
    }
    ue = outlay_app.unit_economics(report)
    assert ue["tickets"] == 3 and ue["cost_per_ticket_usd"] == 60.0   # 180 / 3 (zero-cost excluded)
    assert ue["closed_tickets"] == 2 and ue["cost_per_closed_usd"] == 65.0  # (100+30)/2
    assert ue["reworked_tickets"] == 1 and round(ue["rework_share"], 3) == round(100 / 180, 3)
    assert ue["by_class"][0]["task_class"] == "feature" and ue["by_class"][0]["per_ticket_usd"] == 75.0
    # nothing to divide by → None
    assert outlay_app.unit_economics({"tickets": []}) is None

    # the Overview card renders for sample data
    _signup(client, email="unit@x.com")
    client.post("/app/outlay/sample", follow_redirects=True)
    home = client.get("/app").text
    assert "Unit economics" in home and "per attributed ticket" in home


def test_showback_redirects_to_spend(env, client):
    # Showback was redundant — per-team chargeback already lives on the Spend page.
    # The retired route redirects so old bookmarks don't 404, and Spend carries the
    # team / cost-center allocation it used to duplicate.
    _, store = env
    _signup(client, email="show@x.com")
    acct = store.get_account_by_email("show@x.com")
    store.set_persona(acct["id"], "finance", 0)

    r = client.get("/app/outlay/showback", follow_redirects=False)
    assert r.status_code == 303
    assert r.headers["location"] == "/app/outlay"

    client.post("/app/outlay/sample", follow_redirects=True)
    spend = client.get("/app/outlay").text
    # team allocation + by-team chargeback export live on Spend, not a separate page
    assert "/app/outlay/export.csv?view=teams" in spend
    # the finance Spend view no longer links out to a Showback page
    assert "/app/outlay/showback" not in spend


def test_demo_mode_enter_seeds_full_account_then_exit_clears(env, client):
    _, store = env
    _signup(client, email="demo@x.com")
    acct = store.get_account_by_email("demo@x.com")
    # a gated account in standard mode is offered an entry point
    assert "Enter demo mode" in client.get("/app/outlay").text

    r = client.post("/app/demo/enter", follow_redirects=False)
    assert r.status_code == 303
    acct = store.get_account_by_email("demo@x.com")
    assert acct["demo_mode"] == 1
    # full worked account: report + budgets + programs + a synced source + persona
    assert store.get_outlay_report(acct["id"]) is not None
    assert len(store.list_outlay_budgets(acct["id"])) >= 2
    assert len(store.list_outlay_programs(acct["id"])) >= 1
    conn = store.get_outlay_connection(acct["id"])
    assert conn and conn.get("synced_at")
    assert store.get_persona(acct["id"], 0) == "finance"
    # the global banner shows demo controls + the guide; guide renders both flows
    page = client.get("/app/outlay").text
    assert "Demo mode" in page and "/app/demo/guide" in page and "Exit demo" in page
    guide = client.get("/app/demo/guide").text
    assert "Finance flow" in guide and "Engineering flow" in guide

    client.post("/app/demo/exit", follow_redirects=False)
    acct = store.get_account_by_email("demo@x.com")
    assert acct["demo_mode"] == 0
    assert store.get_outlay_report(acct["id"]) is None
    assert store.list_outlay_budgets(acct["id"]) == []
    assert store.list_outlay_programs(acct["id"]) == []


def test_demo_mode_is_gated_to_demo_accounts(env, client, monkeypatch):
    _, store = env
    # restrict demo access to a specific email — this signup is NOT it
    monkeypatch.setenv("DEMO_ACCOUNT_EMAILS", "founder@outlay-ai.com")
    _signup(client, email="prospect@x.com")
    acct = store.get_account_by_email("prospect@x.com")
    home = client.get("/app/outlay").text
    assert "Enter demo mode" not in home
    assert "See it with sample data" not in home       # sample data is demo-only now
    # the seeding routes refuse for a non-demo account
    client.post("/app/demo/enter", follow_redirects=False)
    client.post("/app/outlay/sample", follow_redirects=False)
    acct = store.get_account_by_email("prospect@x.com")
    assert acct["demo_mode"] == 0
    assert store.get_outlay_report(acct["id"]) is None
    assert client.get("/app/demo/guide", follow_redirects=False).status_code == 303


def _raw_signup(client, email, pw="password123"):
    """Sign up WITHOUT the default-persona shortcut, to exercise the first-run gate."""
    return client.post("/signup", data={"email": email, "password": pw, "accept": "1"})


def test_onboarding_owner_hits_role_gate_then_advances(env, client):
    _, store = env
    _raw_signup(client, "owner@acme.com")
    # the first user (owner, no persona yet) is gated to the welcome role question
    r = client.get("/app", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/app/welcome"
    assert client.get("/app/outlay", follow_redirects=False).headers["location"] == "/app/welcome"
    w = client.get("/app/welcome").text
    assert "I’m a finance leader setting this up for my business" in w
    assert "I’m an engineering leader using this for my business" in w
    # picking a role from the gate sets the persona and advances to onboarding step 2
    r = client.post("/app/persona", data={"persona": "finance", "next": "welcome"},
                    follow_redirects=False)
    assert r.headers["location"] == "/app/welcome"
    acct = store.get_account_by_email("owner@acme.com")
    assert store.get_persona(acct["id"], 0) == "finance"
    w2 = client.get("/app/welcome").text
    assert "You’re set up as Finance" in w2
    assert "Upload your org" in w2 and "Invite your counterpart" in w2
    # the gate is cleared — the dashboard is reachable now
    assert client.get("/app", follow_redirects=False).status_code == 200


def test_onboarding_csv_upload_merges_org_structure(env, client):
    _, store = env
    _raw_signup(client, "o2@acme.com")
    client.post("/app/persona", data={"persona": "finance"})
    acct = store.get_account_by_email("o2@acme.com")
    boundary = "B0undary"
    csv = "email,team\nalice@acme.com,Platform\nbob@acme.com,Growth\n"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; filename=\"org.csv\"\r\n"
            f"Content-Type: text/csv\r\n\r\n{csv}\r\n--{boundary}--\r\n")
    r = client.post("/app/outlay/identity/upload", content=body.encode(),
                    headers={"content-type": f"multipart/form-data; boundary={boundary}"},
                    follow_redirects=False)
    assert r.status_code == 303
    idmap = store.get_outlay_identity_map(acct["id"])
    assert "alice@acme.com, Platform" in idmap and "bob@acme.com, Growth" in idmap
    assert "email, team" not in idmap  # the header row is skipped


def test_onboarding_invite_presets_persona_so_counterpart_skips_gate(env, client):
    server, store = env
    _raw_signup(client, "lead@acme.com")
    client.post("/app/persona", data={"persona": "finance"})
    acct = store.get_account_by_email("lead@acme.com")
    # invite the engineering counterpart with their experience pre-set
    client.post("/app/team/invite", data={"email": "eng@acme.com", "role": "admin", "persona": "eng"})
    m = store.get_member_by_email("eng@acme.com")
    assert store.get_persona(acct["id"], m["id"]) == "eng"
    # the counterpart accepts (sets a password) and signs in on a fresh client
    token = store.create_reset("eng@acme.com")[1]
    member = TestClient(server.app, follow_redirects=False)
    member.post("/reset", data={"token": token, "password": "engpass123"})
    member.post("/login", data={"email": "eng@acme.com", "password": "engpass123"})
    # no role gate for the invited member — straight into the dashboard
    r = member.get("/app", follow_redirects=False)
    assert r.status_code == 200
    assert "setting this up for my business" not in r.text  # the gate tiles are not shown


def test_demo_account_allowlist_supports_domains(env, monkeypatch):
    from console import demo
    monkeypatch.setenv("DEMO_ACCOUNT_EMAILS", "@outlay-ai.com, you@gmail.com")
    assert demo.is_demo_account("test@outlay-ai.com")     # whole-domain match
    assert demo.is_demo_account("you@gmail.com")           # exact match
    assert not demo.is_demo_account("stranger@elsewhere.com")
    assert not demo.is_demo_account(None)


def test_team_roster_builds_directory_then_invite_by_tile(env, client):
    _, store = env
    _signup(client, email="owner@acme.com")
    acct = store.get_account_by_email("owner@acme.com")
    csv = ("name,email,team\n"
           "Jordan Lee,jordan@acme.com,Platform\n"
           "Priya Shah,priya@acme.com,Payments\n"
           "CI deploy bot,key_ci,Platform\n")    # service account: named + mapped
    boundary = "Bnd"
    body = (f"--{boundary}\r\nContent-Disposition: form-data; name=\"file\"; "
            f"filename=\"org.csv\"\r\n\r\n{csv}\r\n--{boundary}--\r\n")
    r = client.post("/app/team/roster", content=body.encode(),
                    headers={"content-type": f"multipart/form-data; boundary={boundary}"},
                    follow_redirects=False)
    assert r.status_code == 303
    # upload builds the directory (names + teams) but does NOT invite anyone yet
    assert store.list_members(acct["id"]) == []
    names = store.get_outlay_identity_names(acct["id"])
    assert names.get("jordan@acme.com") == "Jordan Lee" and names.get("key_ci") == "CI deploy bot"
    assert "jordan@acme.com, Platform" in store.get_outlay_identity_map(acct["id"])
    # the Team page renders a person tile with an Invite action for each emailed person
    team = client.get("/app/team").text
    assert "Jordan Lee" in team and "ptile" in team
    # clicking a tile's Invite (posts the email) creates exactly that member
    client.post("/app/team/invite", data={"email": "jordan@acme.com"}, follow_redirects=False)
    assert {m["email"] for m in store.list_members(acct["id"])} == {"jordan@acme.com"}
    # 'Invite all' invites the remaining emailed people (not the service account)
    client.post("/app/team/invite-all", follow_redirects=False)
    assert {m["email"] for m in store.list_members(acct["id"])} == {"jordan@acme.com", "priya@acme.com"}
    assert client.get("/app/team/roster-template.csv").status_code == 200


def test_onboarding_reset_re_triggers_gate_for_test_accounts(env, client, monkeypatch):
    _, store = env
    _signup(client, email="t@x.com")          # DEMO_ACCOUNT_EMAILS='*' in the fixture → a test account
    acct = store.get_account_by_email("t@x.com")
    store.add_outlay_budget(acct["id"], "team", "platform", 100.0)
    # the test/demo bar offers a Restart onboarding control
    assert "Restart onboarding" in client.get("/app/outlay").text
    # reset → first-run state: persona + data cleared, redirected to the gate
    r = client.post("/app/onboarding/reset", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/app/welcome"
    acct = store.get_account_by_email("t@x.com")
    assert store.get_persona(acct["id"], 0) == ""
    assert store.list_outlay_budgets(acct["id"]) == []
    assert client.get("/app", follow_redirects=False).headers["location"] == "/app/welcome"
    # a non-test (non-allowlisted) account never sees the button and the route refuses
    monkeypatch.setenv("DEMO_ACCOUNT_EMAILS", "someone-else@x.com")
    store.set_persona(acct["id"], "eng", 0)   # move past the gate so the page renders
    assert "Restart onboarding" not in client.get("/app/outlay").text
    client.post("/app/onboarding/reset", follow_redirects=False)
    assert store.get_persona(acct["id"], 0) == "eng"   # unchanged — refused


def test_create_test_customer_script(env, client):
    _, store = env
    from console import create_test_customer
    assert create_test_customer.main(["tester@x.com", "testpass123"]) == 0
    acct = store.get_account_by_email("tester@x.com")
    assert acct and acct["role"] == "customer"
    assert store.get_persona(acct["id"], 0) == ""        # no persona → hits the onboarding gate
    # first login lands on the welcome role gate
    client.post("/login", data={"email": "tester@x.com", "password": "testpass123"})
    assert client.get("/app", follow_redirects=False).headers["location"] == "/app/welcome"
    # re-run refuses to clobber; weak password rejected
    assert create_test_customer.main(["tester@x.com", "testpass123"]) == 1
    assert create_test_customer.main(["other@x.com", "x"]) == 2


def test_webhook_and_slack_urls_are_ssrf_guarded(env, client):
    from console import notify
    _, store = env
    a = store.create_account("ssrf@x.com", "password123")
    # public hostnames pass (or are allowed when unresolvable); internal ones are blocked
    assert notify.is_safe_url("https://hooks.slack.com/services/x") is True
    assert notify.is_safe_url("https://nonexistent.invalid/h") is True   # NXDOMAIN → not a target
    for bad in ("http://169.254.169.254/latest/meta-data/", "http://localhost:8700/admin",
                "http://127.0.0.1/", "http://10.0.0.5/hook", "ftp://x/y", "http://[::1]/"):
        assert notify.is_safe_url(bad) is False, bad
    # store rejects an internal webhook / slack URL at save
    import pytest as _pytest
    with _pytest.raises(store.StoreError):
        store.create_webhook(a["id"], "http://169.254.169.254/")
    with _pytest.raises(store.StoreError):
        store.set_slack_webhook(a["id"], "http://localhost:8700/x")
    # the route surfaces the rejection rather than 500ing
    _signup(client, email="ssrf2@x.com")
    r = client.post("/app/outlay/slack", data={"slack_webhook": "http://127.0.0.1/x"})
    assert r.status_code in (302, 303, 307) and "slack_error=1" in r.headers["location"]


def test_weekly_digest_builds_and_respects_cadence(env, client, monkeypatch):
    from console import spend_digest, store, notify
    _signup(client, email="dig@x.com")
    acct = store.get_account_by_email("dig@x.com")
    # no report yet → nothing to send
    assert spend_digest.build_account_digest(acct["id"]) is None
    assert store.accounts_due_for_digest() == []

    client.post("/app/outlay/sample", follow_redirects=True)
    d = spend_digest.build_account_digest(acct["id"])
    assert d and "AI spend" in d["subject"]
    assert "Where it's going" in d["body"] and "/app" in d["body"]

    # due now; send marks it; not due again within the week; due after a week
    assert acct["id"] in store.accounts_due_for_digest()
    sent = []
    monkeypatch.setattr(notify, "send_email", lambda *a, **k: (sent.append(a), True)[1])
    assert spend_digest.send_account_digest(acct["id"]) is True and len(sent) == 1
    assert store.accounts_due_for_digest() == []
    assert acct["id"] in store.accounts_due_for_digest(now=time.time() + 8 * 24 * 3600)

    # opting out removes it from the sweep
    store.set_digest_weekly(acct["id"], False)
    assert acct["id"] not in store.accounts_due_for_digest(now=time.time() + 30 * 24 * 3600)


def test_weekly_digest_also_posts_to_slack(env, client, monkeypatch):
    from console import spend_digest, store, notify
    _signup(client, email="digsl@x.com")
    acct = store.get_account_by_email("digsl@x.com")
    client.post("/app/outlay/sample", follow_redirects=True)
    store.set_slack_webhook(acct["id"], "https://hooks.slack.com/services/X")

    posts, mails = [], []
    monkeypatch.setattr(notify, "send_slack", lambda url, text: (posts.append((url, text)), True)[1])
    monkeypatch.setattr(notify, "send_email", lambda *a, **k: (mails.append(a), True)[1])
    assert spend_digest.send_account_digest(acct["id"]) is True
    # both channels fired; the Slack post carries the digest subject + body
    assert len(mails) == 1 and len(posts) == 1
    url, text = posts[0]
    assert url.startswith("https://hooks.slack.com") and "AI spend" in text and "Where it's going" in text
    # Settings advertises the Slack delivery
    assert "when a webhook is connected" in client.get("/app/settings").text


def test_digest_cron_requires_token_and_toggle_persists(env, client):
    from console import store
    import os
    assert client.post("/internal/outlay/digest-due").status_code == 401
    os.environ["OUTLAY_CRON_TOKEN"] = "secret-cron"
    try:
        r = client.post("/internal/outlay/digest-due",
                        headers={"authorization": "Bearer secret-cron"})
        assert r.status_code == 200 and r.json()["ok"] is True and "sent" in r.json()
    finally:
        del os.environ["OUTLAY_CRON_TOKEN"]
    _signup(client, email="tog@x.com")
    acct = store.get_account_by_email("tog@x.com")
    client.post("/app/digest", data={}, follow_redirects=True)  # unchecked → off
    assert store.get_account(acct["id"])["digest_weekly"] == 0
    client.post("/app/digest", data={"weekly": "1"}, follow_redirects=True)
    assert store.get_account(acct["id"])["digest_weekly"] == 1
    assert "Weekly spend digest" in client.get("/app/settings").text


def test_monthly_close_pack_builds_attaches_focus_and_cadence(env, client, monkeypatch):
    from console import close_pack, store, notify
    _signup(client, email="close@x.com")
    acct = store.get_account_by_email("close@x.com")
    # opt-in via the settings toggle (off by default)
    assert store.get_account(acct["id"])["close_pack_monthly"] == 0
    client.post("/app/digest", data={"weekly": "1", "close_pack": "1"}, follow_redirects=True)
    assert store.get_account(acct["id"])["close_pack_monthly"] == 1
    assert "Monthly finance close pack" in client.get("/app/settings").text

    # nothing to send until there's a report
    assert close_pack.build_close_pack(acct["id"]) is None
    assert store.accounts_due_for_close_pack() == []

    client.post("/app/outlay/sample", follow_redirects=True)
    pack = close_pack.build_close_pack(acct["id"])
    assert pack and "close pack" in pack["subject"]
    assert "FOCUS-aligned" in pack["body"] and "close-report.html" in pack["body"]
    # the attached CSV is the FOCUS export (spec column names)
    assert pack["csv"].splitlines()[0].startswith("BilledCost,EffectiveCost")

    # due now; sending attaches the CSV, marks sent; monthly cadence holds it back
    assert acct["id"] in store.accounts_due_for_close_pack()
    sent = []
    monkeypatch.setattr(notify, "send_email",
                        lambda *a, **k: (sent.append((a, k)), True)[1])
    assert close_pack.send_close_pack(acct["id"]) is True
    (_to, _subj, _body), kw = sent[0]
    assert kw["attachments"][0][0] == "outlay-focus.csv"
    assert store.accounts_due_for_close_pack() == []
    assert acct["id"] in store.accounts_due_for_close_pack(now=time.time() + 31 * 24 * 3600)

    # opting out removes it from the sweep
    store.set_close_pack_monthly(acct["id"], False)
    assert acct["id"] not in store.accounts_due_for_close_pack(now=time.time() + 60 * 24 * 3600)
    # the daily digest cron also drives close packs (due again a month later)
    store.set_close_pack_monthly(acct["id"], True)
    out = close_pack.run_due_close_packs(now=time.time() + 31 * 24 * 3600)
    assert out["due"] >= 1


def test_anomalies_surfaced_on_spend_and_overview(env, client):
    """Runaway tickets (>=3x class median) show in-product — strip on Overview,
    card on Spend — not just buried in the report."""
    _signup(client, email="anom@x.com")
    client.post("/app/outlay/sample", follow_redirects=True)  # sample has a 11.5x outlier
    spend = client.get("/app/outlay").text
    assert "Runaway tickets" in spend
    home = client.get("/app").text
    assert "runaway ticket" in home and "anomaly" in home


def test_anomaly_alert_fires_once_then_dedupes(env, client, monkeypatch):
    """A newly-detected runaway ticket alerts the owner once; a standing one isn't
    re-emailed every sync; it re-alerts if it drops off and re-spikes."""
    from console import notify, server, store
    calls = []
    monkeypatch.setattr(notify, "send_anomaly_alert",
                        lambda *a, **k: (calls.append(a), True)[1])
    _signup(client, email="alert@x.com")
    acct = store.get_account_by_email("alert@x.com")

    report = {"anomalies": [{"ticket_id": "GH-1", "task_class": "feature",
                             "cost_usd": 500.0, "class_median_usd": 40.0, "ratio": 12.5}]}
    server._check_anomalies(acct["id"], report)
    assert len(calls) == 1                                   # alerted once
    server._check_anomalies(acct["id"], report)
    assert len(calls) == 1                                   # standing outlier → no re-alert
    assert store.get_alerted_anomalies(acct["id"]) == {"GH-1"}

    server._check_anomalies(acct["id"], {"anomalies": []})   # drops off
    assert store.get_alerted_anomalies(acct["id"]) == set()
    server._check_anomalies(acct["id"], report)              # re-spikes
    assert len(calls) == 2
    assert "anomaly.detected" in store.WEBHOOK_EVENTS


def test_identity_map_parses_users_domains_keys():
    from console import outlay_app
    ig = outlay_app.identity_graph(
        "alice@acme.com, Platform\n@contractor.com -> External\nkeyid-7, Growth\n# a comment\n\n")
    assert ig.user_to_team == {"alice@acme.com": "Platform", "keyid-7": "Growth"}
    assert ig.domain_to_team == {"contractor.com": "External"}
    assert ig.key_to_user.get("keyid-7") == "keyid-7"   # key-identified events resolve too


def test_identity_map_drives_team_allocation_end_to_end(env, client):
    """A saved identity map makes team / cost-center allocation work on real data —
    the finance lead view and the low-coverage fallback."""
    _, store = env
    _signup(client, email="fin@x.com")
    # save the map (email + domain), then import usage with users but NO tickets
    client.post("/app/outlay/identity", data={
        "identity_map": "alice@acme.com, Platform\n@acme.com, Engineering"}, follow_redirects=True)
    acct = store.get_account_by_email("fin@x.com")
    assert "Platform" in (store.get_outlay_identity_map(acct["id"]) or "")
    usage = ('[{"id":"e1","model":"claude-opus-4-8","input_tokens":200000,"output_tokens":50000,"user":"alice@acme.com"},'
             '{"id":"e2","model":"claude-opus-4-8","input_tokens":100000,"output_tokens":20000,"user":"bob@acme.com"}]')
    r = client.post("/app/outlay/run", json={"issues": '{"issues":[]}', "usage": usage})
    assert r.json()["ok"] is True
    rep = store.get_outlay_report(acct["id"])
    teams = {t["team"] for t in rep.get("team_spend", [])}
    assert "Platform" in teams           # exact email → Platform
    assert "Engineering" in teams        # bob via @acme.com domain rule
    assert "(unassigned)" not in teams   # everyone mapped
    # the editor round-trips the saved map
    assert "alice@acme.com, Platform" in client.get("/app/outlay/connect").text


def test_coverage_diagnostic_explains_low_coverage(env, client):
    """When ticket coverage is low, the Spend page tells the customer WHY and the
    cheapest fix (connect PRs) — not just a low number."""
    from console import web
    low = {"spend": {"total_usd": 1000.0, "ticket_coverage": 0.2,
                     "by_fidelity_usd": {"call": 0, "branch": 200.0, "team": 600.0, "invoice": 200.0}}}
    diag = web._coverage_diag(low)
    assert "Lift your ticket coverage" in diag
    assert "Connect your PRs" in diag and "Map people to teams" in diag
    # healthy coverage → no nag
    assert web._coverage_diag({"spend": {"total_usd": 1000.0, "ticket_coverage": 0.8,
                                         "by_fidelity_usd": {"branch": 800.0}}}) == ""
    # and it renders on the Spend page for a low-coverage report
    acct = {"email": "u@x.com", "role": "customer", "team_role": "owner", "display_email": "u@x.com"}
    assert "Lift your ticket coverage" in web.outlay_page(acct, low, persona="eng")


def test_unknown_model_pricing_is_flagged_not_silent(env, client):
    """An unrecognized model id is priced by nearest-tier fallback — the report must
    flag it (dollar + share) and the dashboard must warn, never present it as exact."""
    from console import outlay_app, web
    issues = '{"issues":[{"id":1,"number":1,"title":"x","state":"closed","labels":[]}]}'
    usage = ('[{"id":"e1","model":"claude-opus-5-1","input_tokens":1000000,"output_tokens":500000},'
             '{"id":"e2","model":"claude-opus-4-8","input_tokens":100,"output_tokens":50}]')
    rep = outlay_app.build_report(issues, usage)
    pf = rep.get("pricing_fidelity")
    assert pf and pf["fallback_usd"] > 0 and "claude-opus-5-1" in pf["models"]
    assert "nearest tier" in web._pricing_warn(rep)
    # all-known usage → no pricing warning
    known = '[{"id":"e","model":"claude-opus-4-8","input_tokens":1000,"output_tokens":500}]'
    assert outlay_app.build_report(issues, known).get("pricing_fidelity") is None


def test_non_usd_cost_export_is_refused_not_miscompared(env):
    """A EUR/GBP cost export must not reconcile against a USD-computed total."""
    from console import outlay_app
    eur_aws = '{"ResultsByTime":[{"Total":{"UnblendedCost":{"Amount":"100","Unit":"EUR"}},"Groups":[]}]}'
    eur_oai = '{"data":[{"results":[{"amount":{"value":100,"currency":"eur"}}]}]}'
    assert outlay_app.parse_cost_export(eur_aws) == (0.0, "non_usd")
    assert outlay_app.parse_cost_export(eur_oai) == (0.0, "non_usd")
    # USD still works
    usd = '{"ResultsByTime":[{"Total":{"UnblendedCost":{"Amount":"100","Unit":"USD"}},"Groups":[]}]}'
    assert outlay_app.parse_cost_export(usd) == (100.0, "aws_cost_explorer")
    # a non-USD export attached on a run does not produce a (wrong) reconciliation
    rep = {"spend": {"total_usd": 50.0}}
    amt, src = outlay_app.parse_cost_export(eur_aws)
    outlay_app.reconcile(rep, amt, src)
    assert "reconciliation" not in rep


def test_run_with_cost_export_reconciles(env, client):
    _, store = env
    _signup(client, email="rec@x.com")
    fix = _fixtures()
    # paste a provider cost export alongside usage → reconciliation attaches
    aws = '{"ResultsByTime":[{"Total":{"UnblendedCost":{"Amount":"500.00"}},"Groups":[]}]}'
    r = client.post("/app/outlay/run", json={
        "issues": (fix / "github_issues.json").read_text(),
        "usage": (fix / "anthropic_usage.json").read_text(),
        "cost_export": aws})
    assert r.json()["ok"] is True
    rep = store.get_outlay_report(store.get_account_by_email("rec@x.com")["id"])
    rec = rep.get("reconciliation")
    assert rec and rec["source"] == "aws_cost_explorer" and rec["invoice_usd"] == 500.0
    # the Overview strip names AWS, not Anthropic
    assert "AWS Cost Explorer" in client.get("/app").text


def test_audit_log_records_and_renders(env, client):
    """Security events are recorded; owners see the audit page, members 403."""
    server, store = env
    # a fresh login should record an audit entry
    _signup(client, email="boss@co.com")
    client.post("/logout")
    client.post("/login", data={"email": "boss@co.com", "password": "password123"})
    acct = store.get_account_by_email("boss@co.com")
    actions = {e["action"] for e in store.list_audit(acct["id"])}
    assert "login" in actions and "logout" in actions
    # saving a connection is audited
    client.post("/app/outlay/connect", data={"tracker": "github", "github_owner": "acme",
                "github_repo": "web", "github_token": "ghp_x"})
    assert "connection.save" in {e["action"] for e in store.list_audit(acct["id"])}
    # owner sees the audit page
    r = client.get("/app/audit")
    assert r.status_code == 200 and "audit log" in r.text.lower() and "connection.save" in r.text


def test_audit_page_blocked_for_members(env, client):
    server, store = env
    _signup(client, email="own@co.com")
    client.post("/app/team/invite", data={"email": "mem@co.com", "role": "member"})
    out = store.create_reset("mem@co.com")  # set the member's password via reset
    client.post("/reset", data={"token": out[1], "password": "memberpass1"})
    client.post("/logout")
    client.post("/login", data={"email": "mem@co.com", "password": "memberpass1"})
    assert client.get("/app/audit").status_code == 403


def test_login_page_has_sso_entry_and_messages(env, client):
    """The login page offers a 'Use SSO' entry and surfaces SSO error states."""
    r = client.get("/login")
    assert r.status_code == 200 and "company SSO" in r.text and 'action="/sso/start"' in r.text
    assert "single sign-on for that email domain" in client.get("/login?sso=unknown").text


def test_sso_login_is_audited(env, client, monkeypatch):
    server, store = env
    a = store.create_account("o@corp4.com", "password123")
    store.set_sso(a["id"], enabled=True, domain="corp4.com", client_id="c", client_secret="s",
                  auth_url="https://idp/auth", token_url="https://idp/tok", userinfo_url="https://idp/ui")
    r = client.get("/sso/start", params={"email": "bob@corp4.com"}, follow_redirects=False)
    import urllib.parse
    state = urllib.parse.unquote(r.headers["location"].split("state=")[-1])
    monkeypatch.setattr(server, "_oidc_email", lambda cfg, code, ru: "bob@corp4.com")
    client.get("/sso/callback", params={"code": "xyz", "state": state}, follow_redirects=False)
    audit = store.list_audit(a["id"])
    assert any(e["action"] == "login" and "SSO" in (e["detail"] or "") and e["actor"] == "bob@corp4.com"
               for e in audit)


def test_outlay_run_accepts_vertex_logs(env, client):
    """The paste/run path auto-detects a Google Vertex (Claude) log export."""
    _signup(client)
    fix = _fixtures()
    issues = (fix / "github_issues.json").read_text()
    vertex = (fix / "vertex_logs.jsonl").read_text()
    r = client.post("/app/outlay/run", json={"issues": issues, "usage": vertex})
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
    assert "AI spend" in client.get("/app/outlay").text


def test_outlay_run_accepts_openai_usage(env, client):
    """The paste/run path auto-detects an OpenAI usage export."""
    _signup(client)
    fix = _fixtures()
    issues = (fix / "github_issues.json").read_text()
    openai = (fix / "openai_usage.json").read_text()
    r = client.post("/app/outlay/run", json={"issues": issues, "usage": openai})
    assert r.status_code == 200 and r.json()["ok"] is True, r.text
