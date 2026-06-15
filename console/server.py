"""ModelPilot console — FastAPI app (web UI + machine API).

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

import os
from urllib.parse import parse_qs

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse

from . import notify, store, stripe_billing, web

COOKIE = "mp_session"
# Where to send users after they sign out — the public marketing landing page.
LANDING_URL = os.environ.get("LANDING_URL", "https://modelpilot.pages.dev/")
app = FastAPI(title="ModelPilot console")


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


@app.on_event("shutdown")
async def _shutdown():
    task = getattr(app.state, "digest_task", None)
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
    if settings.get("mode") == "shadow":
        out.append("Customer is in shadow mode — nudge them to guidance/autopilot to realize savings.")
    return out


# --------------------------------------------------------------------------- #
# Public / auth
# --------------------------------------------------------------------------- #

@app.get("/", response_class=HTMLResponse)
def root(request: Request):
    if _current(request):
        return _redirect("/app")
    return _html(web.landing())


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
    resp = _redirect("/app")
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
        resp = _redirect("/admin" if acct["role"] == "admin" else "/app")
        _set_session(resp, acct, "owner", 0)
        return resp
    member = store.authenticate_member(f.get("email", ""), f.get("password", ""))
    if member:  # invited teammate
        org = store.get_account(member["account_id"])
        resp = _redirect("/app")
        _set_session(resp, org, member["role"], member["id"], platform_role="customer")
        return resp
    return _html(web.auth_form("login", "Wrong email or password (or account suspended).",
                               f.get("email", "")), 401)


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

def _require(request: Request):
    acct = _current(request)
    if not acct:
        return None, _redirect("/login")
    return acct, None


@app.get("/app", response_class=HTMLResponse)
def app_dashboard(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    plan = store.get_plan(acct["id"])
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


@app.get("/app/settings", response_class=HTMLResponse)
def settings_get(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    return _html(web.settings_page(acct, store.get_settings(acct["id"]),
                                   saved=request.query_params.get("saved") == "1"))


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
    console = os.environ.get("CONSOLE_BASE_URL", "https://app.modelpilot.app")
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
                    headers={"content-disposition": "attachment; filename=modelpilot-logs.csv"})


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
            notify.send_email(m["email"], "You're invited to ModelPilot",
                              f"You've been added to a ModelPilot team. Set your password:\n\n"
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
    if stripe_billing.enabled():
        try:
            url = stripe_billing.create_checkout_session(acct)
            if url:
                return _redirect(url)
        except Exception:  # noqa: BLE001 — fall back to recording the plan
            pass
    # Stripe not configured (or hiccup): record the plan so metering/billing continues.
    store.convert_to_paid(acct["id"])
    return _redirect("/app/billing?converted=1")


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
        life = store.savings_summary(a["id"])["savings"]
        cyc_s = store.savings_summary(a["id"], since=cyc)["savings"]
        paid = plan.get("plan") == "paid"
        rows.append({
            **a, "lifetime_savings": life, "cycle_savings": cyc_s,
            "cycle_revenue": (plan.get("rate", 0.2) * cyc_s) if paid else 0.0,
            "plan_label": "paid" if paid else ("suspended" if a["status"] != "active" else "trial"),
            "plan_badge": "paid" if paid else ("suspended" if a["status"] != "active" else "trial"),
            "pending_proposals": len(store.list_proposals(a["id"], status="pending")),
        })
    return _html(web.admin_overview(acct, rev, rows, store.count_pending_proposals()))


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
            stripe_billing.report_usage(acct["id"], res["realized_savings"])
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
    """Live health of ModelPilot services (stdlib pings, short timeout)."""
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
    resp = _redirect("/app")
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
    print(f"ModelPilot console on http://127.0.0.1:{port} "
          f"(stripe: {'on' if stripe_billing.enabled() else 'off'})")
    uvicorn.run("console.server:app", host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
