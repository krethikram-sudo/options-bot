"""Outlay console — FastAPI app (web UI + machine API).

VENDOR / INTERNAL. The customer-facing SaaS control plane: accounts, auth,
dashboards, mode control, Stripe billing (20% of realized savings), and the
machine API the gateway/brain consume (entitlement, mode, metering).

Run:
  pip install fastapi uvicorn        # + stripe to enable live billing
  python -m console.server           # http://127.0.0.1:8700
Env: CONSOLE_DB, CONSOLE_SECRET, CONSOLE_BASE_URL, MODELPILOT_BRAIN_URL,
     STRIPE_SECRET_KEY / STRIPE_PRICE_ID / STRIPE_WEBHOOK_SECRET (optional),
     CONSOLE_SECURE_COOKIES=1 (set behind HTTPS).
"""

import asyncio
import os
import secrets
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import (HTMLResponse, JSONResponse, PlainTextResponse,
                               RedirectResponse)

from . import notify, outlay_app, store, stripe_billing, web

COOKIE = "mp_session"
PENDING_2FA_COOKIE = "mp_2fa"  # short-lived marker between password and OTP steps
# Where to send users after they sign out — the public marketing landing page.
LANDING_URL = os.environ.get("LANDING_URL", "https://outlay-ai.com/")
app = FastAPI(title="Outlay console")


@app.on_event("startup")
async def _startup():
    store.init_db()
    app.state.digest_task = None
    hours = float(os.environ.get("CONSOLE_DIGEST_HOURS", "0") or 0)
    if hours > 0:
        import asyncio

        from . import digest

        async def _digest_loop():
            while True:
                await asyncio.sleep(hours * 3600)
                try:
                    await asyncio.to_thread(digest.send_digest)
                except Exception:  # noqa: BLE001 — digest must never crash the server
                    pass

        app.state.digest_task = asyncio.create_task(_digest_loop())

    # Auto-sync sweep: in single-process deploys run it in-process; under a real
    # scheduler hit /internal/outlay/sync-due instead and leave this at 0.
    app.state.autosync_task = None
    every = float(os.environ.get("OUTLAY_AUTOSYNC_EVERY_MIN", "0") or 0)
    if every > 0:
        async def _autosync_loop():
            while True:
                await asyncio.sleep(every * 60)
                try:
                    await asyncio.to_thread(_run_due_syncs)
                except Exception:  # noqa: BLE001 — a sweep must never crash the server
                    pass

        app.state.autosync_task = asyncio.create_task(_autosync_loop())


@app.on_event("shutdown")
async def _shutdown():
    for name in ("digest_task", "autosync_task"):
        task = getattr(app.state, name, None)
        if task is not None:
            task.cancel()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

async def _form(request: Request) -> dict:
    """Parse an application/x-www-form-urlencoded body without python-multipart."""
    raw = (await request.body()).decode("utf-8", "replace")
    return {k: v[-1] for k, v in parse_qs(raw, keep_blank_values=True).items()}


async def _form_multi(request: Request) -> dict:
    """Like _form but keeps all values per key (for checkbox groups)."""
    raw = (await request.body()).decode("utf-8", "replace")
    return parse_qs(raw, keep_blank_values=True)


def _key_deployment(request: Request) -> tuple[str | None, str | None]:
    """Resolve the deployment from an API key in the request, if one is presented.
    Returns (deployment_id, error). error='invalid' means a key was sent but is
    bad/revoked (caller should 401). No key presented -> (None, None) so callers
    fall back to the body/query deployment_id (backward compatible)."""
    auth = request.headers.get("authorization", "")
    tok = auth[7:].strip() if auth[:7].lower() == "bearer " else request.headers.get("x-modelpilot-key", "")
    if not tok:
        return None, None
    resolved = store.resolve_api_key(tok)
    if not resolved:
        return None, "invalid"
    return resolved["deployment_id"], None


def _current(request: Request) -> dict | None:
    tok = request.cookies.get(COOKIE)
    if not tok:
        return None
    sess = store.read_session(tok)
    if not sess:
        return None
    acct = store.get_account(sess["account_id"])
    if not acct or acct["status"] != "active":
        return None
    acct = dict(acct)
    if sess.get("member_id"):
        m = store.get_member(sess["member_id"])
        if not m or m["status"] == "removed" or m["account_id"] != acct["id"]:
            return None
        acct["role"] = "customer"          # team members never inherit vendor-admin
        acct["team_role"] = sess["team_role"]
        acct["member_id"] = m["id"]
        acct["display_email"] = m["email"]
    else:
        acct["team_role"] = "owner"
        acct["member_id"] = 0
        acct["display_email"] = acct["email"]
    return acct


def _set_session(resp, account: dict, team_role: str = "owner", member_id: int = 0,
                 platform_role: str | None = None) -> None:
    secure = os.environ.get("CONSOLE_SECURE_COOKIES") == "1"
    role = platform_role or account["role"]
    resp.set_cookie(COOKIE, store.make_session(account["id"], role, team_role, member_id),
                    httponly=True, samesite="lax", secure=secure, max_age=store.SESSION_TTL)


def _require_team_admin(request: Request):
    """Owner or team-admin only (manage team, billing, settings)."""
    acct = _current(request)
    if not acct:
        return None, _redirect("/login")
    if acct.get("team_role") not in ("owner", "admin"):
        return None, _html(web.page("Forbidden",
                                    "<h1>403</h1><p class=muted>Your role can't do that. Ask an "
                                    "owner or admin on your team.</p>", acct), 403)
    return acct, None


def _redirect(url: str):
    return RedirectResponse(url, status_code=303)


def _html(s: str, status: int = 200):
    return HTMLResponse(s, status_code=status)


def _autoapprove_cfg() -> dict | None:
    """Auto-approval thresholds for floor proposals, from env. Off by default —
    every proposal waits for a human until you opt in."""
    if os.environ.get("CONSOLE_AUTOAPPROVE", "") not in ("1", "true", "yes", "on"):
        return None
    return {"min_samples": int(os.environ.get("CONSOLE_AUTOAPPROVE_MIN_SAMPLES", "30")),
            "min_ni": float(os.environ.get("CONSOLE_AUTOAPPROVE_MIN_NI", "0.95"))}


def _suggestions(cats: list[dict], settings: dict) -> list[str]:
    """Product-improvement hints for the admin from a customer's category data."""
    out = []
    for c in cats:
        routed = c.get("routed") or 0
        esc = c.get("escalations") or 0
        if routed >= 20 and esc / routed > 0.05:
            out.append(f"'{c['category']}': escalation rate {100*esc/routed:.0f}% on {routed} routed "
                       f"— tighten the floor or gate for this category.")
        if routed >= 30 and esc == 0 and (c.get("savings") or 0) > 0:
            out.append(f"'{c['category']}': {routed} routed with zero escalations — safe to loosen "
                       f"the floor a tier and capture more savings.")
    if settings.get("mode") == "guidance":
        out.append("Customer is in guidance mode — nudge them to autopilot to auto-capture savings.")
    return out


# --------------------------------------------------------------------------- #
# Public / auth
# --------------------------------------------------------------------------- #

def _is_set_up(account: dict) -> bool:
    """Has the customer completed setup (created an API key / sent any traffic)?
    Drives where we land them after auth: Setup first, then Home/Dashboard."""
    try:
        if store.list_api_keys(account["id"]):
            return True
    except Exception:  # noqa: BLE001
        pass
    try:
        return store.savings_summary(account["id"])["requests"] > 0
    except Exception:  # noqa: BLE001
        return False


def _post_auth_dest(account: dict) -> str:
    """Everyone lands on Spend (the Outlay product home). The vendor /admin pages
    are parked with routing and reachable by direct URL when needed."""
    return "/app/outlay"


@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    if _current(request):
        return _redirect("/app")
    return _html(web.landing())


@app.get("/pilot-request", response_class=HTMLResponse)
def pilot_request_form(request: Request):
    return _html(web.pilot_request_page())


@app.post("/pilot-request")
async def pilot_request_submit(request: Request):
    f = await _form(request)
    if (f.get("website") or "").strip():  # honeypot → silently accept (bot)
        return _redirect("/pilot-request/thanks")
    email = (f.get("email") or "").strip()
    if not email or "@" not in email or "." not in email.split("@")[-1]:
        return _html(web.pilot_request_page("Please enter a valid work email.", f), status=400)
    store.add_pilot_request(email=email, name=f.get("name", ""), company=f.get("company", ""),
                            tools=f.get("tools", ""), message=f.get("message", ""))
    try:
        notify.send_pilot_request({"name": f.get("name"), "email": email, "company": f.get("company"),
                                   "tools": f.get("tools"), "message": f.get("message")})
    except Exception:  # noqa: BLE001 — never fail the request on a mail hiccup
        pass
    return _redirect("/pilot-request/thanks")


@app.get("/pilot-request/thanks", response_class=HTMLResponse)
def pilot_request_thanks(request: Request):
    return _html(web.pilot_thanks_page())


@app.get("/signup", response_class=HTMLResponse)
def signup_form(request: Request):
    if _current(request):
        return _redirect("/app")
    return _html(web.auth_form("signup"))


@app.post("/signup")
async def signup(request: Request):
    f = await _form(request)
    if "accept" not in f:
        return _html(web.auth_form("signup", "Please accept the Terms and Privacy Policy to continue.",
                                   f.get("email", "")), 400)
    try:
        acct = store.create_account(f.get("email", ""), f.get("password", ""),
                                    company=f.get("company", ""), consent=True)
    except store.StoreError as e:
        return _html(web.auth_form("signup", str(e), f.get("email", "")), 400)
    resp = _redirect("/app/outlay")  # brand-new customer -> Spend product home
    _set_session(resp, acct)
    return resp


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if _current(request):
        return _redirect("/app")
    return _html(web.auth_form("login"))


@app.post("/login")
async def login(request: Request):
    f = await _form(request)
    acct = store.authenticate(f.get("email", ""), f.get("password", ""))
    if acct:  # account owner
        tf = store.get_2fa(acct["id"])
        if tf["enabled"]:  # password OK -> challenge for a one-time code, no session yet
            _issue_and_send_otp(acct, tf)
            resp = _redirect("/login/verify")
            secure = os.environ.get("CONSOLE_SECURE_COOKIES") == "1"
            resp.set_cookie(PENDING_2FA_COOKIE, store.make_pending_2fa(acct["id"]),
                            httponly=True, samesite="lax", secure=secure, max_age=600)
            return resp
        resp = _redirect(_post_auth_dest(acct))  # Setup first if not set up, else Home
        _set_session(resp, acct, "owner", 0)
        return resp
    member = store.authenticate_member(f.get("email", ""), f.get("password", ""))
    if member:  # invited teammate
        org = store.get_account(member["account_id"])
        resp = _redirect("/app/outlay")
        _set_session(resp, org, member["role"], member["id"], platform_role="customer")
        return resp
    return _html(web.auth_form("login", "Wrong email or password (or account suspended).",
                               f.get("email", "")), 401)


def _issue_and_send_otp(acct: dict, tf: dict) -> None:
    code = store.issue_otp(acct["id"])
    try:
        notify.send_otp(tf.get("dest") or acct["email"], code, tf.get("channel") or "email")
    except Exception:  # noqa: BLE001 — never break the login flow on a send hiccup
        pass


@app.get("/login/verify", response_class=HTMLResponse)
def verify_2fa_form(request: Request):
    if not store.read_pending_2fa(request.cookies.get(PENDING_2FA_COOKIE, "")):
        return _redirect("/login")
    return _html(web.twofa_verify_form())


@app.post("/login/verify")
async def verify_2fa(request: Request):
    aid = store.read_pending_2fa(request.cookies.get(PENDING_2FA_COOKIE, ""))
    if not aid:
        return _redirect("/login")
    f = await _form(request)
    if store.verify_otp(aid, f.get("code", "")):
        acct = store.get_account(aid)
        resp = _redirect(_post_auth_dest(acct))
        _set_session(resp, acct, "owner", 0)
        resp.delete_cookie(PENDING_2FA_COOKIE)
        return resp
    return _html(web.twofa_verify_form("That code didn't match or has expired."), 401)


@app.post("/login/verify/resend")
async def verify_2fa_resend(request: Request):
    aid = store.read_pending_2fa(request.cookies.get(PENDING_2FA_COOKIE, ""))
    if not aid:
        return _redirect("/login")
    acct = store.get_account(aid)
    if acct:
        _issue_and_send_otp(acct, store.get_2fa(aid))
    return _html(web.twofa_verify_form(note="A new code is on its way."))


@app.post("/logout")
def logout():
    resp = _redirect(LANDING_URL)
    resp.delete_cookie(COOKIE)
    return resp


@app.get("/forgot", response_class=HTMLResponse)
def forgot_get():
    return _html(web.forgot_form())


@app.post("/forgot")
async def forgot_post(request: Request):
    f = await _form(request)
    out = store.create_reset(f.get("email", ""))
    if out:  # account exists -> send link (logged in dev). Response is identical either way.
        acct, token = out
        try:
            notify.send_reset(acct["email"], token)
        except Exception:  # noqa: BLE001 — never reveal send status / never 500
            pass
    return _html(web.forgot_form(sent=True))


@app.get("/reset", response_class=HTMLResponse)
def reset_get(request: Request):
    token = request.query_params.get("token", "")
    return _html(web.reset_form(token))


@app.post("/reset")
async def reset_post(request: Request):
    f = await _form(request)
    token = f.get("token", "")
    if not store.consume_reset(token, f.get("password", "")):
        return _html(web.reset_form(token, "That reset link is invalid or expired, or the "
                                           "password is too short."), 400)
    return _redirect("/login")


# --------------------------------------------------------------------------- #
# Customer app
# --------------------------------------------------------------------------- #

# An expired, unconverted trial can still reach Billing (to convert) — everything
# else in the app is gated until they activate.
_TRIAL_OK_PREFIXES = ("/app/billing",)


def _is_paid(account: dict) -> bool:
    try:
        return store.get_plan(account["id"]).get("plan") == "paid"
    except Exception:  # noqa: BLE001
        return False


def _trial_expired(account: dict) -> bool:
    try:
        return not store.trial_status(account["id"])["active"]
    except Exception:  # noqa: BLE001
        return False


def _require(request: Request):
    acct = _current(request)
    if not acct:
        return None, _redirect("/login")
    # Pilots run free for now — trial-expiry gating to Billing is parked along with
    # the routing/savings billing model. (Re-enable by restoring the check below.)
    return acct, None


@app.get("/app", response_class=HTMLResponse)
def app_dashboard(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    # Routing/optimization is parked for now — Spend is the product home. (To bring
    # the routing console back, remove this redirect; the render below still works.)
    return _redirect("/app/outlay")
    plan = store.get_plan(acct["id"])  # noqa: F841 — preserved for reversibility
    trial = store.trial_status(acct["id"])
    settings = store.get_settings(acct["id"])
    bill = store.bill_estimate(acct["id"])
    cycle = store.savings_summary(acct["id"], since=bill["cycle_start"])
    lifetime = store.savings_summary(acct["id"])
    cats = store.savings_by_category(acct["id"], since=bill["cycle_start"])
    proof = store.proof_summary(acct["id"])
    deps = store.deployments_for(acct["id"])
    budget = store.budget_status(acct["id"])
    return _html(web.dashboard(acct, plan, trial, settings, cycle, lifetime, bill,
                               deps[0] if deps else {"deployment_id": "—"}, cats, proof, budget))


@app.get("/app/estimate", response_class=HTMLResponse)
def app_estimate(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    plan = store.get_plan(acct["id"])
    bill = store.bill_estimate(acct["id"])
    cycle = store.savings_summary(acct["id"], since=bill["cycle_start"])
    lifetime = store.savings_summary(acct["id"])
    return _html(web.estimate_page(acct, plan, cycle, lifetime, bill))


def _budget_email(account_id: int, s: dict) -> None:
    """Email the account owner on a budget transition — webhooks reach machines,
    this reaches a human (the only channel most pilots will have wired up)."""
    acct = store.get_account(account_id)
    email = (acct or {}).get("email")
    if not email:
        return
    scope = s["scope_type"] + (f' "{s["scope_id"]}"' if s.get("scope_id") else "")
    try:
        notify.send_budget_alert(email, s["status"], s.get("projected_usd", 0), s.get("limit_usd", 0) or 0,
                                 scope=scope, product="Outlay")
    except Exception:  # noqa: BLE001 — alerting must never break the sync path
        pass


def _check_budgets(account_id: int, report: dict) -> None:
    """After new data lands, fire budget.warn / budget.over on transition into
    those states — to subscribed webhooks AND the owner's email (so a pilot with
    no webhook still gets the guardrail)."""
    budgets = store.list_outlay_budgets(account_id)
    if not budgets:
        return
    for s in outlay_app.budget_statuses(report, budgets):
        new, old = s["status"], s.get("last_status")
        if new in ("warn", "over") and new != old:
            store.deliver_event(account_id, f"budget.{new}", {
                "scope_type": s["scope_type"], "scope_id": s.get("scope_id"),
                "spent_usd": s["spent_usd"], "limit_usd": s["limit_usd"],
                "projected_usd": s["projected_usd"], "period_days": s.get("period_days")})
            _budget_email(account_id, s)
        store.set_outlay_budget_status(s["id"], new)


_AUTO_SYNC_CHOICES = (0, 24, 168)  # off · daily · weekly


def _auto_sync_hours(raw) -> int:
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return 0
    return v if v in _AUTO_SYNC_CHOICES else 0


def _run_due_syncs(now: float | None = None, transport=None) -> dict:
    """Re-sync every connection whose auto-sync interval has elapsed. Resilient:
    one account's failure (bad token, network) never blocks the rest. Returns a
    summary so the cron endpoint / loop can be observed."""
    due = store.list_due_outlay_connections(now=now)
    synced, failed = 0, 0
    for account_id in due:
        conn = store.get_outlay_connection(account_id)
        if not conn:
            continue
        try:
            report = outlay_app.sync(conn, transport=transport)
        except Exception as e:  # noqa: BLE001 — keep sweeping other accounts
            store.mark_outlay_sync_error(account_id, str(e), now=now)
            failed += 1
            continue
        store.save_outlay_report(account_id, report)
        store.record_outlay_snapshot(account_id, report, now=now)
        store.mark_outlay_synced(account_id, now=now)
        _check_budgets(account_id, report)
        synced += 1
    return {"due": len(due), "synced": synced, "failed": failed}


@app.post("/internal/outlay/sync-due")
async def app_outlay_sync_due(request: Request):
    """Cron hook: an external scheduler (Fly scheduled machine / cron) posts here
    with the OUTLAY_CRON_TOKEN to run all due auto-syncs. No browser session."""
    want = os.environ.get("OUTLAY_CRON_TOKEN", "")
    auth = request.headers.get("authorization", "")
    got = auth[7:].strip() if auth[:7].lower() == "bearer " else ""
    if not want or not secrets.compare_digest(got, want):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    summary = await asyncio.to_thread(_run_due_syncs)
    return JSONResponse({"ok": True, **summary})


@app.get("/app/outlay", response_class=HTMLResponse)
def app_outlay(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    report = store.get_outlay_report(acct["id"])
    budgets = store.list_outlay_budgets(acct["id"])
    statuses = outlay_app.budget_statuses(report, budgets) if report else []
    hist = store.outlay_history(acct["id"]) if report else []
    return _html(web.outlay_page(acct, report, statuses, hist,
                                 store.get_outlay_connection(acct["id"]),
                                 has_budget=bool(budgets)))


@app.post("/app/outlay/run")
async def app_outlay_run(request: Request):
    acct, redir = _require(request)
    if redir:
        return JSONResponse({"ok": False, "error": "Please sign in again."}, status_code=401)
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": "Invalid request."}, status_code=400)
    issues = (data.get("issues") or "").strip()
    usage = (data.get("usage") or "").strip()
    planned = (data.get("planned") or "").strip() or None
    if not issues or not usage:
        return JSONResponse({"ok": False, "error": "Paste both the tracker and AI-usage JSON."})
    try:
        report = outlay_app.build_report(issues, usage, planned)
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)})
    except Exception:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": "Could not process that data."})
    store.save_outlay_report(acct["id"], report)
    store.record_outlay_snapshot(acct["id"], report)
    _check_budgets(acct["id"], report)
    return JSONResponse({"ok": True})


@app.post("/app/outlay/sample")
async def app_outlay_sample(request: Request):
    """One-click populated dashboard from bundled fixtures — for prospects/demos."""
    acct, redir = _require(request)
    if redir:
        return redir
    report = outlay_app.sample_report()
    store.save_outlay_report(acct["id"], report)
    store.record_outlay_snapshot(acct["id"], report)
    return _redirect("/app/outlay")


@app.post("/app/outlay/clear")
async def app_outlay_clear(request: Request):
    """Drop the current report + history (used to clear sample data)."""
    acct, redir = _require(request)
    if redir:
        return redir
    store.delete_outlay_report(acct["id"])
    return _redirect("/app/outlay")


@app.get("/app/outlay/connect", response_class=HTMLResponse)
def app_outlay_connect(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    return _html(web.outlay_connect_page(acct, store.get_outlay_connection(acct["id"])))


@app.post("/app/outlay/connect")
async def app_outlay_connect_save(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    store.save_outlay_connection(
        acct["id"], github_owner=f.get("github_owner"), github_repo=f.get("github_repo"),
        github_token=f.get("github_token"), anthropic_key=f.get("anthropic_key"),
        tracker=f.get("tracker"), jira_base_url=f.get("jira_base_url"),
        jira_email=f.get("jira_email"), jira_token=f.get("jira_token"),
        jira_jql=f.get("jira_jql"), linear_key=f.get("linear_key"),
        cursor_key=f.get("cursor_key"),
        auto_sync_hours=_auto_sync_hours(f.get("auto_sync_hours")))
    return _redirect("/app/outlay/connect")


@app.post("/app/outlay/sync")
async def app_outlay_sync(request: Request):
    acct, redir = _require(request)
    if redir:
        return JSONResponse({"ok": False, "error": "Please sign in again."}, status_code=401)
    conn = store.get_outlay_connection(acct["id"])
    if not conn:
        return JSONResponse({"ok": False, "error": "Add your connection details first."})
    try:
        report = outlay_app.sync(conn)
    except ValueError as e:
        store.mark_outlay_sync_error(acct["id"], str(e))
        return JSONResponse({"ok": False, "error": str(e)})
    except Exception:  # noqa: BLE001
        msg = "Sync failed. Check your tokens and try again."
        store.mark_outlay_sync_error(acct["id"], msg)
        return JSONResponse({"ok": False, "error": msg})
    store.save_outlay_report(acct["id"], report)
    store.record_outlay_snapshot(acct["id"], report)
    store.mark_outlay_synced(acct["id"])
    _check_budgets(acct["id"], report)
    return JSONResponse({"ok": True})


@app.get("/app/outlay/budgets", response_class=HTMLResponse)
def app_outlay_budgets(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    report = store.get_outlay_report(acct["id"])
    statuses = outlay_app.budget_statuses(report, store.list_outlay_budgets(acct["id"]))
    return _html(web.budgets_page(acct, report, statuses, outlay_app.project_spend(report)))


@app.post("/app/outlay/budgets")
async def app_outlay_budgets_add(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        limit = float(f.get("limit_usd") or 0)
    except ValueError:
        limit = 0.0
    scope = f.get("scope_type") or "overall"
    if scope not in ("overall", "team", "class", "project"):
        scope = "overall"
    if limit > 0:
        store.add_outlay_budget(acct["id"], scope, f.get("scope_id"), limit,
                                int(f.get("period_days") or 30))
    return _redirect("/app/outlay/budgets")


@app.post("/app/outlay/budgets/delete")
async def app_outlay_budgets_delete(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    store.delete_outlay_budget(acct["id"], int(f.get("id") or 0))
    return _redirect("/app/outlay/budgets")


@app.get("/app/outlay/export.csv")
def app_outlay_export(request: Request, view: str = "tickets"):
    """Download a CSV slice of the report (tickets/people/classes/savings) for finance."""
    acct, redir = _require(request)
    if redir:
        return redir
    report = store.get_outlay_report(acct["id"])
    if not report:
        return _redirect("/app/outlay")
    if view not in ("tickets", "people", "classes", "savings"):
        view = "tickets"
    csv_text = outlay_app.report_csv(report, view)
    return PlainTextResponse(csv_text, media_type="text/csv", headers={
        "content-disposition": f'attachment; filename="outlay-{view}.csv"'})


@app.get("/app/outlay/accuracy", response_class=HTMLResponse)
def app_outlay_accuracy(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    return _html(web.accuracy_page(acct, store.get_outlay_report(acct["id"])))


@app.get("/app/outlay/estimate", response_class=HTMLResponse)
def app_outlay_estimate(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    return _html(web.estimate_backlog_page(acct, store.get_outlay_report(acct["id"])))


@app.post("/app/outlay/estimate/run")
async def app_outlay_estimate_run(request: Request):
    acct, redir = _require(request)
    if redir:
        return JSONResponse({"ok": False, "error": "Please sign in again."}, status_code=401)
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": "Invalid request."}, status_code=400)
    planned = (data.get("planned") or "").strip()
    if not planned:
        return JSONResponse({"ok": False, "error": "Paste a planned backlog (JSON)."})
    report = store.get_outlay_report(acct["id"])
    model = report.get("_model") if report else None
    if not model:
        return JSONResponse({"ok": False, "error": "Connect or upload data on the Spend tab first."})
    try:
        est = outlay_app.estimate_with_model(model, planned)
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)})
    except Exception:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": "Could not estimate that backlog."})
    report["estimate"] = est
    store.save_outlay_report(acct["id"], report)
    return JSONResponse({"ok": True})


@app.post("/app/mode")
async def app_mode(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        store.update_settings(acct["id"], mode=f.get("mode"))
    except store.StoreError:
        pass
    ref = request.headers.get("referer", "")
    return _redirect("/app/settings" if "settings" in ref else "/app")


@app.post("/app/autopilot")
async def app_autopilot(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        store.update_settings(acct["id"], autopilot_pct=int(f.get("autopilot_pct")))
    except (store.StoreError, ValueError, TypeError):
        pass
    ref = request.headers.get("referer", "")
    return _redirect("/app/settings" if "settings" in ref else "/app")


@app.get("/app/settings", response_class=HTMLResponse)
def settings_get(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    return _html(web.settings_page(acct, store.get_settings(acct["id"]),
                                   saved=request.query_params.get("saved") == "1",
                                   delete_error=request.query_params.get("delete_error") == "1",
                                   twofa=request.query_params.get("twofa", "")))


# --- two-factor authentication -------------------------------------------- #

@app.post("/app/2fa/start")
async def twofa_start(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    code = store.issue_otp(acct["id"])
    try:  # email channel: code goes to the account email (no tampering possible)
        notify.send_otp(acct["email"], code, "email")
    except Exception:  # noqa: BLE001
        pass
    return _redirect("/app/settings?twofa=verify")


@app.post("/app/2fa/confirm")
async def twofa_confirm(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    if store.verify_otp(acct["id"], f.get("code", "")):
        store.set_2fa(acct["id"], "email", acct["email"])
        return _redirect("/app/settings?twofa=on")
    return _redirect("/app/settings?twofa=bad")


@app.post("/app/2fa/disable")
async def twofa_disable(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    store.disable_2fa(acct["id"])
    return _redirect("/app/settings?twofa=off")


@app.post("/app/account/delete")
async def account_delete(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    # Only the account owner may delete the whole account — not invited teammates.
    if acct.get("team_role") != "owner":
        return _html(web.page("Forbidden", "<h1>403</h1><p class=muted>Only the account owner can "
                              "delete the account. Ask your owner, or remove yourself from Team.</p>",
                              acct), 403)
    f = await _form(request)
    # Confirm by typing the account email — guards against accidental deletion.
    if f.get("confirm_email", "").strip().lower() != (acct.get("email") or "").lower():
        return _redirect("/app/settings?delete_error=1")
    # Capture the why (survives deletion — feedback isn't cascade-deleted). Most valuable signal.
    reason = (f.get("reason") or "").strip()
    if reason:
        try:
            store.record_feedback(acct["id"], "cancel", comment=reason)
        except Exception:  # noqa: BLE001 — never block deletion on feedback
            pass
    stripe_billing.cancel_subscription(acct["id"])  # best-effort; never raises
    store.delete_account(acct["id"])
    resp = _redirect(LANDING_URL)  # account gone -> back to the public landing page
    resp.delete_cookie(COOKIE)
    return resp


@app.post("/app/feedback")
async def app_feedback(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    rating = f.get("rating") if f.get("rating") in ("up", "down") else None
    try:
        store.record_feedback(acct["id"], "dashboard", rating=rating, comment=f.get("comment"))
    except store.StoreError:
        pass
    ref = request.headers.get("referer", "")
    return _redirect("/app/settings?fb=1" if "settings" in ref else "/app?fb=1")


@app.post("/app/settings")
async def settings_post(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    kw = {"risk": f.get("risk"), "min_model": f.get("min_model", ""),
          "telemetry_opt_in": ("telemetry_opt_in" in f)}
    try:
        kw["monthly_budget"] = float(f.get("monthly_budget", "") or 0)
    except ValueError:
        pass
    try:
        kw["budget_alert_pct"] = float(f.get("budget_alert_pct", "") or 80) / 100.0
    except ValueError:
        pass
    try:
        store.update_settings(acct["id"], **kw)
    except store.StoreError:
        pass
    return _redirect("/app/settings?saved=1")


def _connect_html(acct: dict, new_key: str = ""):
    deps = store.deployments_for(acct["id"])
    brain = os.environ.get("MODELPILOT_BRAIN_URL", "https://brain.modelpilot.app")
    console = os.environ.get("CONSOLE_BASE_URL", "https://app.outlay-ai.com")
    keys = store.list_api_keys(acct["id"])
    hooks = store.list_webhooks(acct["id"])
    return _html(web.connect_page(acct, deps, brain, console, keys, new_key, hooks))


@app.post("/app/webhooks")
async def create_webhook(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        store.create_webhook(acct["id"], f.get("url", ""), f.get("events", "all"))
    except store.StoreError:
        pass
    return _redirect("/app/connect")


@app.post("/app/webhooks/delete")
async def delete_webhook(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        store.delete_webhook(int(f.get("webhook_id", "0")), acct["id"])
    except ValueError:
        pass
    return _redirect("/app/connect")


@app.get("/app/connect", response_class=HTMLResponse)
def connect(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    return _connect_html(acct)


@app.post("/app/keys")
async def create_key(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    deps = store.deployments_for(acct["id"])
    dep = f.get("deployment_id") or (deps[0]["deployment_id"] if deps else "")
    new_key = ""
    try:
        new_key = store.create_api_key(acct["id"], dep, f.get("name", ""))["full_key"]
    except store.StoreError:
        pass
    return _connect_html(acct, new_key)  # show the key once (never recoverable)


@app.post("/app/keys/revoke")
async def revoke_key(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        store.revoke_api_key(int(f.get("key_id", "0")), acct["id"])
    except ValueError:
        pass
    return _redirect("/app/connect")


@app.post("/app/deployments")
async def create_deployment(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    store.create_deployment(acct["id"], label=f.get("label", ""))
    return _redirect("/app/connect")


@app.post("/app/deployments/rename")
async def rename_deployment(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    store.rename_deployment(f.get("deployment_id", ""), acct["id"], f.get("label", ""))
    return _redirect("/app/connect")


@app.get("/app/logs", response_class=HTMLResponse)
def logs_get(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    return _html(web.logs_page(acct, store.recent_logs(acct["id"], 200),
                               store.logs_count(acct["id"])))


@app.get("/app/logs.csv")
def logs_csv(request: Request):
    acct = _current(request)
    if not acct:
        return _redirect("/login")
    import csv
    import io
    rows = store.recent_logs(acct["id"], 5000)
    buf = io.StringIO()
    cols = ["ts", "category", "original_model", "routed_model", "applied", "escalated",
            "action", "status_code", "input_tokens", "output_tokens",
            "baseline_cost", "actual_cost", "realized_saved"]
    w = csv.DictWriter(buf, fieldnames=cols, extrasaction="ignore")
    w.writeheader()
    for r in rows:
        w.writerow(r)
    from fastapi.responses import Response
    return Response(buf.getvalue(), media_type="text/csv",
                    headers={"content-disposition": "attachment; filename=outlay-logs.csv"})


@app.get("/app/team", response_class=HTMLResponse)
def team_get(request: Request):
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    tok = request.query_params.get("invite_token", "")
    invite_link = notify.reset_link(tok) if tok else ""
    return _html(web.team_page(acct, store.list_members(acct["id"]), invite_link,
                               store.get_sso(acct["id"]), request.query_params.get("scim_token", "")))


@app.post("/app/team/invite")
async def team_invite(request: Request):
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        m = store.create_member(acct["id"], f.get("email", ""), f.get("role", "member"))
    except store.StoreError:
        return _redirect("/app/team")
    out = store.create_reset(m["email"])
    token = out[1] if out else ""
    if token:
        try:
            notify.send_email(m["email"], "You're invited to Outlay",
                              f"You've been added to an Outlay team. Set your password:\n\n"
                              f"{notify.reset_link(token)}")
        except Exception:  # noqa: BLE001
            pass
    return _redirect(f"/app/team?invite_token={token}")


@app.post("/app/team/role")
async def team_role(request: Request):
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        store.set_member_role(int(f.get("member_id", "0")), acct["id"], f.get("role", "member"))
    except (ValueError, store.StoreError):
        pass
    return _redirect("/app/team")


@app.post("/app/team/remove")
async def team_remove(request: Request):
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        store.remove_member(int(f.get("member_id", "0")), acct["id"])
    except ValueError:
        pass
    return _redirect("/app/team")


@app.get("/app/billing", response_class=HTMLResponse)
def billing_get(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    checkout = request.query_params.get("checkout")
    session_id = request.query_params.get("session_id")
    flash = ""
    if checkout == "success" and session_id:
        try:
            if stripe_billing.finalize_checkout(acct, session_id):
                flash = "success"
        except Exception:  # noqa: BLE001 — never break billing page on Stripe hiccup
            flash = ""
    elif checkout == "cancel":
        flash = "cancel"
    elif request.query_params.get("converted") == "1":
        flash = "converted"
    plan = store.get_plan(acct["id"])
    trial = store.trial_status(acct["id"])
    bill = store.bill_estimate(acct["id"])
    return _html(web.billing_page(acct, plan, trial, bill, stripe_billing.enabled(), flash))


@app.post("/app/billing/convert")
async def billing_convert(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    if acct.get("team_role") not in ("owner", "admin", "billing"):
        return _html(web.page("Forbidden", "<h1>403</h1><p class=muted>Billing changes need an "
                              "owner, admin, or billing role.</p>", acct), 403)
    f = await _form(request)
    tier = f.get("tier", "payg")
    if tier not in store.TIERS:
        tier = "payg"
    if stripe_billing.enabled():
        try:
            url = stripe_billing.create_checkout_session(acct, tier)
            if url:
                return _redirect(url)
        except Exception as e:  # noqa: BLE001 — log, then fall back to recording the plan
            import sys
            import traceback
            print(f"[billing] checkout session failed: {e!r}", file=sys.stderr)
            traceback.print_exc()
    # Stripe not configured (or hiccup): record the plan + tier so metering continues.
    store.convert_to_paid(acct["id"])
    store.set_tier(acct["id"], tier)
    return _redirect(f"/app/billing?converted=1&tier={tier}")


# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #

def _require_admin(request: Request):
    acct = _current(request)
    if not acct:
        return None, _redirect("/login")
    if acct["role"] != "admin":
        return None, _html(web.page("Forbidden",
                                    "<h1>403</h1><p class=muted>Admin access required.</p>", acct), 403)
    return acct, None


@app.get("/admin/leads", response_class=HTMLResponse)
def admin_leads(request: Request):
    acct, redir = _require_admin(request)
    if redir:
        return redir
    return _html(web.leads_page(acct, store.list_pilot_requests()))


@app.get("/admin", response_class=HTMLResponse)
def admin_overview(request: Request):
    acct, redir = _require_admin(request)
    if redir:
        return redir
    rev = store.revenue_overview()
    cyc = store.cycle_start()
    rows = []
    for a in store.list_accounts():
        plan = store.get_plan(a["id"])
        life = store.savings_summary(a["id"])
        cyc_sum = store.savings_summary(a["id"], since=cyc)
        cyc_s = cyc_sum["savings"]
        paid = plan.get("plan") == "paid"
        rows.append({
            **a, "lifetime_savings": life["savings"], "cycle_savings": cyc_s,
            "cycle_pct": round(100 * cyc_s / cyc_sum["baseline"]) if cyc_sum.get("baseline") else 0,
            "cycle_revenue": (plan.get("rate", 0.2) * cyc_s) if paid else 0.0,
            "plan_label": "paid" if paid else ("suspended" if a["status"] != "active" else "trial"),
            "plan_badge": "paid" if paid else ("suspended" if a["status"] != "active" else "trial"),
            "pending_proposals": len(store.list_proposals(a["id"], status="pending")),
        })
    return _html(web.admin_overview(acct, rev, rows, store.count_pending_proposals(),
                                    funnel=store.activation_funnel(), feedback=store.list_feedback(30)))


@app.get("/admin/proposals", response_class=HTMLResponse)
def admin_proposals(request: Request):
    acct, redir = _require_admin(request)
    if redir:
        return redir
    pending = store.list_proposals(status="pending")
    emails = {a["id"]: a["email"] for a in store.list_accounts()}
    return _html(web.admin_proposals_queue(acct, pending, emails))


@app.post("/admin/proposals/bulk")
async def admin_proposals_bulk(request: Request):
    acct, redir = _require_admin(request)
    if redir:
        return redir
    data = await _form_multi(request)
    decision = (data.get("decision") or [""])[-1]
    note = (data.get("note") or [""])[-1] or None
    if decision in ("approved", "rejected"):
        for sid in data.get("ids", []):
            try:
                store.decide_proposal(int(sid), decision, decided_by=acct["id"], note=note)
            except (ValueError, store.StoreError):
                pass
    return _redirect("/admin/proposals")


@app.get("/admin/accounts/{account_id}", response_class=HTMLResponse)
def admin_account(request: Request, account_id: int):
    acct, redir = _require_admin(request)
    if redir:
        return redir
    target = store.get_account(account_id)
    if not target:
        return _html(web.page("Not found", "<h1>404</h1>", acct), 404)
    plan = store.get_plan(account_id)
    trial = store.trial_status(account_id)
    settings = store.get_settings(account_id)
    bill = store.bill_estimate(account_id)
    cats = store.savings_by_category(account_id)
    reset_token = request.query_params.get("reset_token", "")
    reset_link = notify.reset_link(reset_token) if reset_token else ""
    proposals = store.list_proposals(account_id, status="pending")
    history = store.proposal_history(account_id)
    return _html(web.admin_account_detail(acct, target, plan, trial, settings, bill, cats,
                                          _suggestions(cats, settings), reset_link, proposals, history))


@app.post("/admin/accounts/{account_id}/proposal")
async def admin_decide_proposal(request: Request, account_id: int):
    acct, redir = _require_admin(request)
    if redir:
        return redir
    f = await _form(request)
    decision = f.get("decision")
    try:
        pid = int(f.get("proposal_id", "0"))
    except ValueError:
        pid = 0
    if decision in ("approved", "rejected") and pid:
        try:
            store.decide_proposal(pid, decision, decided_by=acct["id"], note=f.get("note"))
        except store.StoreError:
            pass
    return _redirect(f"/admin/accounts/{account_id}")


@app.post("/admin/accounts/{account_id}/action")
async def admin_action(request: Request, account_id: int):
    acct, redir = _require_admin(request)
    if redir:
        return redir
    f = await _form(request)
    action = f.get("action")
    if action == "extend_trial":
        store.extend_trial(account_id, 7)
    elif action == "convert":
        store.convert_to_paid(account_id)
    elif action == "suspend":
        store.set_status(account_id, "suspended")
        store.deliver_event(account_id, "account.suspended", {"account_id": account_id})
    elif action == "reactivate":
        store.set_status(account_id, "active")
    elif action == "set_rate":
        try:
            store.set_rate(account_id, float(f.get("rate", "20")) / 100.0)
        except ValueError:
            pass
    elif action == "send_reset":
        target = store.get_account(account_id)
        if target:
            out = store.create_reset(target["email"])
            if out:
                _, token = out
                try:
                    notify.send_reset(target["email"], token)
                except Exception:  # noqa: BLE001
                    pass
                return _redirect(f"/admin/accounts/{account_id}?reset_token={token}")
    return _redirect(f"/admin/accounts/{account_id}")


# --------------------------------------------------------------------------- #
# Machine API (gateway / brain)
# --------------------------------------------------------------------------- #

@app.get("/api/entitlement")
def api_entitlement(request: Request, deployment_id: str = ""):
    """Server-authoritative entitlement + mode for a deployment (brain reads this).
    Accepts an API key (Bearer) or a deployment_id query param."""
    key_dep, err = _key_deployment(request)
    if err:
        return JSONResponse({"error": "invalid api key"}, status_code=401)
    return JSONResponse(store.entitlement(key_dep or deployment_id))


@app.post("/api/meter")
async def api_meter(request: Request):
    """Accept one aggregate savings report from a gateway. Dollars + counts only —
    reject anything that looks like it carries prompt/output/secret data."""
    key_dep, err = _key_deployment(request)
    if err:
        return JSONResponse({"error": "invalid api key"}, status_code=401)
    body = await request.json()
    if not isinstance(body, dict):
        return JSONResponse({"error": "object required"}, status_code=400)
    lowered = {str(k).lower() for k in body}
    if lowered & store.FORBIDDEN_METER_KEYS:
        return JSONResponse({"error": "payload contains forbidden keys"}, status_code=422)
    dep = key_dep or body.get("deployment_id")
    if not dep:
        return JSONResponse({"error": "deployment_id required"}, status_code=400)
    try:
        res = store.record_meter(
            dep, requests=body.get("requests", 0), routed=body.get("routed", 0),
            escalations=body.get("escalations", 0),
            baseline_cost=body.get("baseline_cost", 0.0),
            actual_cost=body.get("actual_cost", 0.0),
            realized_savings=body.get("realized_savings"),
            opportunity_saved=body.get("opportunity_saved", 0.0),
            caching_saved=body.get("caching_saved", 0.0),
            category=body.get("category"))
    except store.StoreError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    # Optional aggregate proof counts (side-by-side non-inferiority — counts only).
    if body.get("comparisons") or body.get("non_inferior"):
        try:
            store.record_proof(dep, int(body.get("comparisons", 0)),
                               int(body.get("non_inferior", 0)))
        except store.StoreError:
            pass
    # Best-effort: push usage to Stripe for paid accounts + fire budget alerts.
    try:
        acct = store.account_for_deployment(dep)
        if acct:
            # Report inline AND mark the row reported, so the sync backstop never
            # double-bills the same savings. If the push didn't happen (not paid /
            # Stripe off / sub-cent), the row stays unreported for sync to retry.
            if stripe_billing.report_usage(acct["id"], res["realized_savings"]):
                store.mark_meter_reported(res["meter_id"])
            alert = store.budget_alert_pending(acct["id"])
            if alert:
                try:
                    notify.send_budget_alert(acct["email"], alert["level"],
                                             alert["spend"], alert["budget"])
                except Exception:  # noqa: BLE001
                    pass
                store.deliver_event(acct["id"], f"budget.{alert['level']}",
                                    {"spend": alert["spend"], "budget": alert["budget"]})
    except Exception:  # noqa: BLE001
        pass
    return JSONResponse(res)


@app.post("/api/proposals")
async def api_proposals(request: Request):
    """A gateway submits an auto-derived tuning proposal (Track A floor / Track C
    rule). Aggregate spec + stats only — reject anything carrying prompt/output
    text or secrets (defense in depth)."""
    key_dep, err = _key_deployment(request)
    if err:
        return JSONResponse({"error": "invalid api key"}, status_code=401)
    body = await request.json()
    if not isinstance(body, dict):
        return JSONResponse({"error": "object required"}, status_code=400)
    if {str(k).lower() for k in body} & store.FORBIDDEN_METER_KEYS:
        return JSONResponse({"error": "payload contains forbidden keys"}, status_code=422)
    dep = key_dep or body.get("deployment_id")
    kind = body.get("kind")
    category = body.get("category")
    if not (dep and kind and category):
        return JSONResponse({"error": "deployment_id, kind, category required"}, status_code=400)
    try:
        res = store.submit_proposal(dep, kind, category, body.get("payload") or {},
                                    body.get("stats") or {}, autoapprove=_autoapprove_cfg())
    except store.StoreError as e:
        code = 404 if "unknown deployment" in str(e) else 400
        return JSONResponse({"error": str(e)}, status_code=code)
    if not res.get("auto_approved"):
        store.deliver_event(res["account_id"], "proposal.pending",
                            {"kind": kind, "category": category})
    return JSONResponse(res)


@app.post("/api/logs")
async def api_logs(request: Request):
    """Accept a batch of opt-in per-request METADATA logs. Reject anything that
    looks like it carries prompt/output/secret data (defense in depth)."""
    key_dep, err = _key_deployment(request)
    if err:
        return JSONResponse({"error": "invalid api key"}, status_code=401)
    body = await request.json()
    if not isinstance(body, dict):
        return JSONResponse({"error": "object required"}, status_code=400)
    dep = key_dep or body.get("deployment_id")
    logs = body.get("logs") or []
    if not dep:
        return JSONResponse({"error": "deployment_id required"}, status_code=400)
    # forbidden keys at the batch level OR in any row
    seen = {str(k).lower() for k in body}
    for r in logs:
        if isinstance(r, dict):
            seen |= {str(k).lower() for k in r}
    if seen & store.FORBIDDEN_METER_KEYS:
        return JSONResponse({"error": "payload contains forbidden keys"}, status_code=422)
    try:
        res = store.record_logs(dep, logs)
    except store.StoreError as e:
        return JSONResponse({"error": str(e)}, status_code=404)
    return JSONResponse(res)


@app.get("/api/policy")
def api_policy(request: Request, deployment_id: str = ""):
    """Approved per-customer policy for a deployment: floors (applied by the brain)
    and rules (loaded by the gateway). Accepts an API key (Bearer) or deployment_id."""
    key_dep, err = _key_deployment(request)
    if err:
        return JSONResponse({"error": "invalid api key"}, status_code=401)
    return JSONResponse(store.approved_policy_for_deployment(key_dep or deployment_id))


@app.post("/api/stripe/webhook")
async def stripe_webhook(request: Request):
    """Stripe events (subscription lifecycle). Verifies signature when configured."""
    if not stripe_billing.enabled():
        return JSONResponse({"ok": True, "stripe": "disabled"})
    payload = await request.body()
    sig = request.headers.get("stripe-signature", "")
    secret = os.environ.get("STRIPE_WEBHOOK_SECRET")
    try:
        import stripe
        if secret:
            event = stripe.Webhook.construct_event(payload, sig, secret)
        else:
            event = (await request.json())
        etype = event["type"] if isinstance(event, dict) else event.type
    except Exception as e:  # noqa: BLE001
        return JSONResponse({"error": str(e)}, status_code=400)
    return JSONResponse({"ok": True, "type": etype})


def _check_components() -> list[dict]:
    """Live health of Outlay services (stdlib pings, short timeout)."""
    import urllib.request
    comps = [{"name": "Console & dashboard", "ok": True, "detail": "operational"}]
    targets = [("Routing brain", os.environ.get("MODELPILOT_BRAIN_URL", "")),
               ("Telemetry ingest", os.environ.get("MODELPILOT_INGEST_URL", ""))]
    for name, base in targets:
        base = (base or "").rstrip("/")
        if not base:
            continue
        ok = False
        try:
            with urllib.request.urlopen(base + "/health", timeout=2) as r:
                ok = r.status == 200
        except Exception:  # noqa: BLE001
            ok = False
        comps.append({"name": name, "ok": ok, "detail": "operational" if ok else "unreachable"})
    return comps


@app.get("/status", response_class=HTMLResponse)
def status_page(request: Request):
    return _html(web.status_page(_check_components()))


# --------------------------------------------------------------------------- #
# SSO (OIDC) — per-account, email-domain routed. Token/userinfo fetch is a
# module function so it's testable without a live IdP.
# --------------------------------------------------------------------------- #

def _redirect_uri() -> str:
    return os.environ.get("CONSOLE_BASE_URL", "http://127.0.0.1:8700").rstrip("/") + "/sso/callback"


def _oidc_email(cfg: dict, code: str, redirect_uri: str) -> str | None:
    """Exchange an auth code for the user's email via the account's IdP."""
    import urllib.parse
    import urllib.request
    try:
        data = urllib.parse.urlencode({
            "grant_type": "authorization_code", "code": code, "redirect_uri": redirect_uri,
            "client_id": cfg["client_id"], "client_secret": cfg["client_secret"]}).encode()
        req = urllib.request.Request(cfg["token_url"], data=data,
                                     headers={"accept": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=8) as r:
            tok = json.loads(r.read())
        access = tok.get("access_token")
        if not access:
            return None
        ui = urllib.request.Request(cfg["userinfo_url"],
                                    headers={"authorization": f"Bearer {access}"})
        with urllib.request.urlopen(ui, timeout=8) as r:
            info = json.loads(r.read())
        return (info.get("email") or "").strip().lower() or None
    except Exception:  # noqa: BLE001
        return None


@app.get("/sso/start")
def sso_start(request: Request, email: str = ""):
    import urllib.parse
    domain = email.split("@")[-1].strip().lower() if "@" in email else ""
    cfg = store.sso_by_domain(domain) if domain else None
    if not cfg or not cfg.get("auth_url"):
        return _redirect("/login?sso=unknown")
    state = store.make_session(cfg["account_id"], "sso", "state", 0)
    q = urllib.parse.urlencode({"response_type": "code", "client_id": cfg["client_id"],
                                "redirect_uri": _redirect_uri(), "scope": "openid email", "state": state})
    return _redirect(f"{cfg['auth_url']}?{q}")


@app.get("/sso/callback")
def sso_callback(request: Request):
    code = request.query_params.get("code", "")
    state = request.query_params.get("state", "")
    sess = store.read_session(state)
    if not code or not sess or sess.get("team_role") != "state":
        return _redirect("/login?sso=failed")
    account_id = sess["account_id"]
    cfg = store.get_sso(account_id)
    if not cfg.get("enabled"):
        return _redirect("/login?sso=failed")
    email = _oidc_email(cfg, code, _redirect_uri())
    if not email:
        return _redirect("/login?sso=failed")
    # optional domain guard
    if cfg.get("domain") and not email.endswith("@" + cfg["domain"]):
        return _redirect("/login?sso=domain")
    try:
        member = store.provision_member(account_id, email, cfg.get("default_role", "member"))
    except store.StoreError:
        return _redirect("/login?sso=failed")
    org = store.get_account(account_id)
    resp = _redirect("/app/outlay")
    _set_session(resp, org, member["role"], member["id"], platform_role="customer")
    return resp


# --------------------------------------------------------------------------- #
# SCIM 2.0 (Users) — automated provisioning from the IdP (Bearer SCIM token)
# --------------------------------------------------------------------------- #

def _scim_account(request: Request) -> int | None:
    auth = request.headers.get("authorization", "")
    tok = auth[7:].strip() if auth[:7].lower() == "bearer " else ""
    return store.resolve_scim_token(tok)


def _scim_user(m: dict) -> dict:
    return {"schemas": ["urn:ietf:params:scim:schemas:core:2.0:User"], "id": str(m["id"]),
            "userName": m["email"], "active": m["status"] != "removed",
            "emails": [{"value": m["email"], "primary": True}]}


@app.post("/scim/v2/Users")
async def scim_create(request: Request):
    aid = _scim_account(request)
    if aid is None:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    body = await request.json()
    email = (body.get("userName") or (body.get("emails") or [{}])[0].get("value") or "").lower()
    if not email:
        return JSONResponse({"detail": "userName required"}, status_code=400)
    try:
        m = store.provision_member(aid, email, store.get_sso(aid).get("default_role", "member"))
    except store.StoreError as e:
        return JSONResponse({"detail": str(e)}, status_code=409)
    return JSONResponse(_scim_user(m), status_code=201)


@app.get("/scim/v2/Users")
def scim_list(request: Request):
    aid = _scim_account(request)
    if aid is None:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    members = store.list_members(aid)
    return JSONResponse({"schemas": ["urn:ietf:params:scim:api:messages:2.0:ListResponse"],
                         "totalResults": len(members), "Resources": [_scim_user(m) for m in members]})


@app.api_route("/scim/v2/Users/{member_id}", methods=["DELETE", "PATCH"])
async def scim_deactivate(request: Request, member_id: int):
    aid = _scim_account(request)
    if aid is None:
        return JSONResponse({"detail": "unauthorized"}, status_code=401)
    store.remove_member(member_id, aid)
    return JSONResponse({}, status_code=204)


# --------------------------------------------------------------------------- #
# SSO config (owner/admin)
# --------------------------------------------------------------------------- #

@app.post("/app/sso")
async def sso_save(request: Request):
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    f = await _form(request)
    store.set_sso(acct["id"], enabled=("enabled" in f), domain=f.get("domain", ""),
                  client_id=f.get("client_id", ""), client_secret=f.get("client_secret", ""),
                  auth_url=f.get("auth_url", ""), token_url=f.get("token_url", ""),
                  userinfo_url=f.get("userinfo_url", ""), default_role=f.get("default_role", "member"))
    return _redirect("/app/team")


@app.post("/app/sso/scim")
async def sso_scim_token(request: Request):
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    token = store.rotate_scim_token(acct["id"])
    return _redirect(f"/app/team?scim_token={token}")


@app.get("/api/health")
@app.get("/healthz")
def health():
    return {"ok": True, "stripe": stripe_billing.enabled()}


def main():
    import uvicorn
    port = int(os.environ.get("CONSOLE_PORT", "8700"))
    store.init_db()
    print(f"Outlay console on http://127.0.0.1:{port} "
          f"(stripe: {'on' if stripe_billing.enabled() else 'off'})")
    uvicorn.run("console.server:app", host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
