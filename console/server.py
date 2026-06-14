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
app = FastAPI(title="ModelPilot console")


@app.on_event("startup")
def _startup():
    store.init_db()


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

async def _form(request: Request) -> dict:
    """Parse an application/x-www-form-urlencoded body without python-multipart."""
    raw = (await request.body()).decode("utf-8", "replace")
    return {k: v[-1] for k, v in parse_qs(raw, keep_blank_values=True).items()}


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
    return acct


def _set_session(resp, account: dict) -> None:
    secure = os.environ.get("CONSOLE_SECURE_COOKIES") == "1"
    resp.set_cookie(COOKIE, store.make_session(account["id"], account["role"]),
                    httponly=True, samesite="lax", secure=secure, max_age=store.SESSION_TTL)


def _redirect(url: str):
    return RedirectResponse(url, status_code=303)


def _html(s: str, status: int = 200):
    return HTMLResponse(s, status_code=status)


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
    try:
        acct = store.create_account(f.get("email", ""), f.get("password", ""),
                                    company=f.get("company", ""))
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
    if not acct:
        return _html(web.auth_form("login", "Wrong email or password (or account suspended).",
                                   f.get("email", "")), 401)
    resp = _redirect("/admin" if acct["role"] == "admin" else "/app")
    _set_session(resp, acct)
    return resp


@app.post("/logout")
def logout():
    resp = _redirect("/")
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
    return _html(web.dashboard(acct, plan, trial, settings, cycle, lifetime, bill,
                               deps[0] if deps else {"deployment_id": "—"}, cats, proof))


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
    try:
        store.update_settings(
            acct["id"], risk=f.get("risk"), min_model=f.get("min_model", ""),
            telemetry_opt_in=("telemetry_opt_in" in f))
    except store.StoreError:
        pass
    return _redirect("/app/settings?saved=1")


@app.get("/app/connect", response_class=HTMLResponse)
def connect(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    deps = store.deployments_for(acct["id"])
    brain = os.environ.get("MODELPILOT_BRAIN_URL", "https://brain.modelpilot.app")
    console = os.environ.get("CONSOLE_BASE_URL", "https://app.modelpilot.app")
    return _html(web.connect_page(acct, deps, brain, console))


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
        })
    return _html(web.admin_overview(acct, rev, rows))


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
    return _html(web.admin_account_detail(acct, target, plan, trial, settings, bill, cats,
                                          _suggestions(cats, settings), reset_link))


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
def api_entitlement(deployment_id: str):
    """Server-authoritative entitlement + mode for a deployment (brain reads this)."""
    return JSONResponse(store.entitlement(deployment_id))


@app.post("/api/meter")
async def api_meter(request: Request):
    """Accept one aggregate savings report from a gateway. Dollars + counts only —
    reject anything that looks like it carries prompt/output/secret data."""
    body = await request.json()
    if not isinstance(body, dict):
        return JSONResponse({"error": "object required"}, status_code=400)
    lowered = {str(k).lower() for k in body}
    if lowered & store.FORBIDDEN_METER_KEYS:
        return JSONResponse({"error": "payload contains forbidden keys"}, status_code=422)
    dep = body.get("deployment_id")
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
    # Best-effort: push usage to Stripe for paid accounts.
    try:
        acct = store.account_for_deployment(dep)
        if acct:
            stripe_billing.report_usage(acct["id"], res["realized_savings"])
    except Exception:  # noqa: BLE001
        pass
    return JSONResponse(res)


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
