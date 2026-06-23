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
import json
import os
import secrets
import time
from contextlib import asynccontextmanager
from urllib.parse import parse_qs, quote

from fastapi import FastAPI, Request
from fastapi.responses import (HTMLResponse, JSONResponse, PlainTextResponse,
                               RedirectResponse, Response)

from . import cost_to_serve, demo, notify, outlay_app, store, stripe_billing, web, webauthn_box

COOKIE = "mp_session"
PENDING_2FA_COOKIE = "mp_2fa"  # short-lived marker between password and OTP steps
WA_REG_COOKIE = "mp_wareg"     # short-lived WebAuthn registration challenge
WA_AUTH_COOKIE = "mp_waauth"   # short-lived WebAuthn login-assertion challenge
# Where to send users after they sign out — the public marketing landing page.
LANDING_URL = os.environ.get("LANDING_URL", "https://outlay-ai.com/")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: init the DB and, for single-machine deploys, start the in-process
    background loops (digest / auto-sync / maintenance) driven by the *_EVERY_MIN env
    vars. Shutdown: cancel them. (Under a real external scheduler, leave the env vars at
    0 and POST the /internal/outlay/* endpoints instead — both sweeps are idempotent and
    cadence-guarded, so running them as often as hourly only fires genuinely-due work.)"""
    store.init_db()
    tasks = []

    hours = float(os.environ.get("CONSOLE_DIGEST_HOURS", "0") or 0)
    if hours > 0:
        from . import digest

        async def _digest_loop():
            while True:
                await asyncio.sleep(hours * 3600)
                try:
                    await asyncio.to_thread(digest.send_digest)
                except Exception:  # noqa: BLE001 — digest must never crash the server
                    pass
        tasks.append(asyncio.create_task(_digest_loop()))

    every = float(os.environ.get("OUTLAY_AUTOSYNC_EVERY_MIN", "0") or 0)
    if every > 0:
        async def _autosync_loop():
            while True:
                await asyncio.sleep(every * 60)
                try:
                    summary = await asyncio.to_thread(_run_due_syncs)
                    store.mark_cron_run("sync-due", summary)
                except Exception:  # noqa: BLE001 — a sweep must never crash the server
                    pass
        tasks.append(asyncio.create_task(_autosync_loop()))

    maint = float(os.environ.get("OUTLAY_MAINTENANCE_EVERY_MIN", "0") or 0)
    if maint > 0:
        async def _maintenance_loop():
            while True:
                await asyncio.sleep(maint * 60)
                try:
                    await asyncio.to_thread(_run_maintenance)
                except Exception:  # noqa: BLE001 — a sweep must never crash the server
                    pass
        tasks.append(asyncio.create_task(_maintenance_loop()))

    try:
        yield
    finally:
        for t in tasks:
            t.cancel()


app = FastAPI(title="Outlay console", lifespan=lifespan)


@app.middleware("http")
async def _slide_session(request: Request, call_next):
    """Sliding session refresh + idle enforcement. On each request with a valid session
    cookie, bump its `seen` timestamp (so activity keeps the session alive); if an idle
    timeout is configured and exceeded, drop the cookie instead of refreshing."""
    resp = await call_next(request)
    tok = request.cookies.get(COOKIE)
    if not tok:
        return resp
    # If the handler already managed the session cookie (login, logout, account
    # delete, log-out-everywhere), respect it — never re-issue over a delete/refresh.
    if any(k == b"set-cookie" and v.startswith(COOKIE.encode() + b"=")
           for k, v in resp.raw_headers):
        return resp
    sess = store.read_session(tok)
    if not sess:
        return resp
    secure = os.environ.get("CONSOLE_SECURE_COOKIES") == "1"
    try:
        idle_min = store.get_security_policy(sess["account_id"])["session_idle_min"]
    except Exception:  # noqa: BLE001
        idle_min = 0
    if idle_min and (time.time() - sess.get("seen", sess["issued"])) > idle_min * 60:
        resp.delete_cookie(COOKIE)
        return resp
    fresh = store.reseal_session(tok)
    if fresh and fresh != tok:
        resp.set_cookie(COOKIE, fresh, httponly=True, samesite="lax", secure=secure,
                        max_age=store.SESSION_TTL)
    return resp


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


# --- Public API auth + rate limiting (the /api/v1/* read endpoints) ---------- #
# In-process fixed-window limiter, keyed by API key. The console runs as a single
# Fly machine, so in-memory is sufficient and keeps us dependency-free; it fails
# open across restarts (acceptable for a read-only export API). Tune via env.
import threading as _threading

_API_RATE_LIMIT = int(os.environ.get("OUTLAY_API_RATE_LIMIT", "120"))  # requests/window
_API_RATE_WINDOW = int(os.environ.get("OUTLAY_API_RATE_WINDOW", "60"))  # seconds
_rate_state: dict = {}
_rate_lock = _threading.Lock()


def _rate_ok(key_id, now: float | None = None) -> tuple[bool, int]:
    """Fixed-window counter for one API key. Returns (allowed, retry_after_secs)."""
    if _API_RATE_LIMIT <= 0:
        return True, 0
    import time
    now = now or time.time()
    win = int(now // _API_RATE_WINDOW)
    with _rate_lock:
        slot = _rate_state.get(key_id)
        if not slot or slot[0] != win:
            _rate_state[key_id] = [win, 1]
            return True, 0
        if slot[1] >= _API_RATE_LIMIT:
            retry = int((win + 1) * _API_RATE_WINDOW - now) + 1
            return False, max(1, retry)
        slot[1] += 1
        return True, 0


def _api_auth(request: Request):
    """Resolve + rate-limit a public API request. Returns (resolved, error_response):
    on success (resolved, None); on failure (None, JSONResponse) with 401 or 429."""
    auth = request.headers.get("authorization", "")
    tok = auth[7:].strip() if auth[:7].lower() == "bearer " else request.headers.get("x-modelpilot-key", "")
    resolved = store.resolve_api_key(tok) if tok else None
    if not resolved:
        return None, JSONResponse({"error": "invalid api key"}, status_code=401)
    ok, retry = _rate_ok(resolved.get("key_id"))
    if not ok:
        return None, JSONResponse(
            {"error": "rate limit exceeded", "retry_after": retry},
            status_code=429, headers={"Retry-After": str(retry)})
    return resolved, None


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
    cur_epoch = acct.get("session_epoch", 0) or 0
    if sess.get("member_id"):
        m = store.get_member(sess["member_id"])
        if not m or m["status"] == "removed" or m["account_id"] != acct["id"]:
            return None
        cur_epoch = m.get("session_epoch", 0) or 0
        acct["role"] = "customer"          # team members never inherit vendor-admin
        acct["team_role"] = sess["team_role"]
        acct["member_id"] = m["id"]
        acct["display_email"] = m["email"]
        acct["display_name"] = store.display_name(m)            # the member's own name, not the owner's
        acct["member_name"] = (m.get("name") or "").strip()
        acct["twofa_enabled"] = bool(m.get("twofa_enabled"))   # the member's own MFA state, not the org's
    else:
        acct["team_role"] = "owner"
        acct["member_id"] = 0
        acct["display_email"] = acct["email"]
        acct["display_name"] = store.display_name(acct)
    # A passkey counts as enrolled MFA too — reflect the principal's full second-factor
    # state so the admin require_mfa gate treats a passkey-only user as enrolled.
    try:
        acct["twofa_enabled"] = store.principal_has_mfa(acct["id"], acct.get("member_id", 0) or 0)
    except Exception:  # noqa: BLE001
        pass
    # Session revocation (logout-everywhere / password change) + idle/absolute timeout.
    if sess.get("epoch", 0) != cur_epoch:
        return None
    pol = store.get_security_policy(acct["id"])
    now = time.time()
    if pol["session_idle_min"] and (now - sess.get("seen", sess["issued"])) > pol["session_idle_min"] * 60:
        return None
    if pol["session_max_hours"] and (now - sess["issued"]) > pol["session_max_hours"] * 3600:
        return None
    # Persona (business/eng) drives the role-aware lens *and* nav ordering, so make
    # it available to every page() render — not just the Spend page.
    try:
        acct["persona"] = store.get_persona(acct["id"], acct.get("member_id", 0) or 0)
    except Exception:  # noqa: BLE001 — persona is a lens, never a hard dependency
        acct["persona"] = ""
    # Demo mode: who may toggle it is gated by env; whether it's currently on is the
    # account flag. Both are surfaced to every page() render.
    acct["_can_demo"] = demo.is_demo_account(acct.get("email"))
    return acct


def _set_session(resp, account: dict, team_role: str = "owner", member_id: int = 0,
                 platform_role: str | None = None) -> None:
    secure = os.environ.get("CONSOLE_SECURE_COOKIES") == "1"
    role = platform_role or account["role"]
    if member_id:
        m = store.get_member(member_id)
        epoch = (m or {}).get("session_epoch", 0) or 0
    else:
        epoch = account.get("session_epoch", 0) or 0
    pol = store.get_security_policy(account["id"])
    max_age = pol["session_max_hours"] * 3600 if pol["session_max_hours"] else store.SESSION_TTL
    resp.set_cookie(COOKIE, store.make_session(account["id"], role, team_role, member_id, epoch=epoch),
                    httponly=True, samesite="lax", secure=secure, max_age=max_age)


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


def _audit(account_id: int, action: str, actor: str = "", detail: str = "") -> None:
    """Record a security-relevant event; never let an audit write break the request.
    Authentication/security events (login.fail, 2fa.*, password.reset, policy change,
    log-out-everywhere, lockout) ALSO fire the account's incident/breach webhook so a
    SOC/SIEM gets a signed alert in real time (gov-readiness IR-6 / MD-SOC path)."""
    try:
        store.record_audit(account_id, action, actor=actor, detail=detail)
    except Exception:  # noqa: BLE001
        pass
    if action in store.SECURITY_EVENT_ACTIONS:
        try:
            store.notify_security_event(account_id, action, actor=actor, detail=detail)
        except Exception:  # noqa: BLE001
            pass


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
    """Everyone lands on the role-aware Overview (the Outlay product home). The vendor
    /admin pages are parked with routing and reachable by direct URL when needed."""
    return "/app"


def _needs_welcome(account: dict) -> bool:
    """The first organic user from a company (the account owner) must answer the
    role question before reaching the product. Invited members skip it — their
    persona arrives pre-set on the invite — and the vendor admin is never gated."""
    return (account.get("team_role") == "owner"
            and account.get("role") != "admin"
            and not (account.get("persona") or ""))


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
                            title=f.get("title", ""), tools=f.get("tools", ""),
                            message=f.get("message", ""))
    try:
        notify.send_pilot_request({"name": f.get("name"), "email": email, "company": f.get("company"),
                                   "title": f.get("title"), "tools": f.get("tools"),
                                   "message": f.get("message")})
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
                                    company=f.get("company", ""), name=f.get("name", ""),
                                    consent=True)
    except store.StoreError as e:
        return _html(web.auth_form("signup", str(e), f.get("email", "")), 400)
    resp = _redirect("/app")  # brand-new customer -> Overview (product home)
    _set_session(resp, acct)
    return resp


_SSO_MSG = {
    "unknown": "We couldn't find single sign-on for that email domain. Use your password, or check with your admin.",
    "failed": "Single sign-on didn't complete. Please try again or sign in with your password.",
    "domain": "That account's email domain isn't allowed for SSO here.",
}


@app.get("/login", response_class=HTMLResponse)
def login_form(request: Request):
    if _current(request):
        return _redirect("/app")
    err = _SSO_MSG.get(request.query_params.get("sso", ""), "")
    return _html(web.auth_form("login", err))


@app.post("/login")
async def login(request: Request):
    f = await _form(request)
    email = f.get("email", "")
    locked = store.login_locked(email)
    if locked:
        mins = max(1, locked // 60)
        existing = store.get_account_by_email(email)
        if existing:  # AC-7: a locked account is a security signal — audit + alert the SOC
            _audit(existing["id"], "login.locked", actor=email,
                   detail=f"locked {mins}m after repeated failures")
        return _html(web.auth_form("login", f"Too many failed attempts — try again in {mins} minute"
                                   f"{'s' if mins != 1 else ''}.", email), 429)
    acct = store.authenticate(email, f.get("password", ""))
    if acct:  # account owner
        store.clear_login_throttle(email)
        tf = store.get_2fa(acct["id"])
        if store.principal_has_mfa(acct["id"], 0):  # password OK -> second factor, no session yet
            if tf["enabled"] and tf["channel"] != "totp":  # email/SMS gets a sent code; TOTP/passkey don't
                _issue_and_send_otp(acct, tf)
            resp = _redirect("/login/verify")
            secure = os.environ.get("CONSOLE_SECURE_COOKIES") == "1"
            resp.set_cookie(PENDING_2FA_COOKIE, store.make_pending_2fa(acct["id"]),
                            httponly=True, samesite="lax", secure=secure, max_age=600)
            return resp
        resp = _redirect(_post_auth_dest(acct))  # Setup first if not set up, else Home
        _set_session(resp, acct, "owner", 0)
        _audit(acct["id"], "login", actor=acct["email"], detail="owner · password")
        return resp
    member = store.authenticate_member(email, f.get("password", ""))
    if member:  # invited teammate
        store.clear_login_throttle(email)
        org = store.get_account(member["account_id"])
        if store.principal_has_mfa(org["id"], member["id"]):  # TOTP or passkey — nothing to send
            resp = _redirect("/login/verify")
            secure = os.environ.get("CONSOLE_SECURE_COOKIES") == "1"
            resp.set_cookie(PENDING_2FA_COOKIE,
                            store.make_pending_2fa(org["id"], member_id=member["id"]),
                            httponly=True, samesite="lax", secure=secure, max_age=600)
            return resp
        resp = _redirect("/app")
        _set_session(resp, org, member["role"], member["id"], platform_role="customer")
        _audit(org["id"], "login", actor=member["email"], detail=f"member · role {member['role']}")
        return resp
    # Failed password — throttle the identity (AC-7) and log the attempt.
    store.note_login_failure(email)
    existing = store.get_account_by_email(email)
    if existing:
        _audit(existing["id"], "login.fail", actor=email, detail="bad password")
    return _html(web.auth_form("login", "Wrong email or password (or account suspended).",
                               email), 401)


def _issue_and_send_otp(acct: dict, tf: dict) -> None:
    code = store.issue_otp(acct["id"])
    try:
        notify.send_otp(tf.get("dest") or acct["email"], code, tf.get("channel") or "email")
    except Exception:  # noqa: BLE001 — never break the login flow on a send hiccup
        pass


@app.get("/login/verify", response_class=HTMLResponse)
def verify_2fa_form(request: Request):
    pend = store.read_pending_2fa(request.cookies.get(PENDING_2FA_COOKIE, ""))
    if not pend:
        return _redirect("/login")
    aid, mid = pend
    has_code = store.get_2fa(aid, member_id=mid)["enabled"]                 # TOTP / email code
    has_passkey = bool(store.webauthn_credential_ids(aid, mid)) and webauthn_box.available()
    return _html(web.twofa_verify_form(has_code=has_code, has_passkey=has_passkey))


@app.post("/login/verify")
async def verify_2fa(request: Request):
    pend = store.read_pending_2fa(request.cookies.get(PENDING_2FA_COOKIE, ""))
    if not pend:
        return _redirect("/login")
    aid, mid = pend
    f = await _form(request)
    code = f.get("code", "")
    if mid:  # invited member — TOTP only
        if store.verify_totp(aid, code, member_id=mid):
            member = store.get_member(mid)
            org = store.get_account(aid)
            resp = _redirect("/app")
            _set_session(resp, org, member["role"], member["id"], platform_role="customer")
            resp.delete_cookie(PENDING_2FA_COOKIE)
            _audit(org["id"], "login", actor=member["email"],
                   detail=f"member · password + 2FA (totp) · role {member['role']}")
            return resp
        return _html(web.twofa_verify_form("That code didn't match or has expired."), 401)
    tf = store.get_2fa(aid)
    ok = (store.verify_totp(aid, code) if tf["channel"] == "totp"
          else store.verify_otp(aid, code))
    if ok:
        acct = store.get_account(aid)
        resp = _redirect(_post_auth_dest(acct))
        _set_session(resp, acct, "owner", 0)
        resp.delete_cookie(PENDING_2FA_COOKIE)
        _audit(acct["id"], "login", actor=acct["email"],
               detail=f"owner · password + 2FA ({tf['channel'] or 'otp'})")
        return resp
    return _html(web.twofa_verify_form("That code didn't match or has expired."), 401)


@app.post("/login/verify/resend")
async def verify_2fa_resend(request: Request):
    pend = store.read_pending_2fa(request.cookies.get(PENDING_2FA_COOKIE, ""))
    if not pend:
        return _redirect("/login")
    aid, mid = pend
    if mid:  # member TOTP — nothing to resend (the code lives in their authenticator app)
        return _html(web.twofa_verify_form(note="Open your authenticator app for the current code."))
    acct = store.get_account(aid)
    if acct:
        _issue_and_send_otp(acct, store.get_2fa(aid))
    return _html(web.twofa_verify_form(note="A new code is on its way."))


@app.post("/logout")
def logout(request: Request):
    acct = _current(request)
    if acct:
        _audit(acct["id"], "logout", actor=acct.get("display_email") or acct.get("email", ""))
    resp = _redirect(LANDING_URL)
    resp.delete_cookie(COOKIE)
    return resp


# GET logout so the marketing site's "Sign out" link works as a plain navigation
# (same-site to app.outlay-ai.com → cookie cleared → redirect back to the landing page).
@app.get("/logout")
def logout_get(request: Request):
    return logout(request)


# Lightweight cross-origin session check for the (static) marketing site, so it can show
# "signed in" state. Same-site (outlay-ai.com ⇄ app.outlay-ai.com) so the Lax cookie is sent;
# CORS echoes the marketing origin + allows credentials so the JS can read the result.
_SESSION_CORS_ORIGINS = {"https://outlay-ai.com", "https://www.outlay-ai.com"}


@app.get("/api/session")
def api_session(request: Request):
    acct = _current(request)
    body = ({"signed_in": True, "email": acct.get("display_email") or acct.get("email", ""),
             "name": acct.get("display_name") or ""}
            if acct else {"signed_in": False})
    resp = JSONResponse(body)
    origin = request.headers.get("origin", "")
    if origin in _SESSION_CORS_ORIGINS:
        resp.headers["Access-Control-Allow-Origin"] = origin
        resp.headers["Access-Control-Allow-Credentials"] = "true"
        resp.headers["Vary"] = "Origin"
    resp.headers["Cache-Control"] = "no-store"
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
    try:
        ok = store.consume_reset(token, f.get("password", ""))
    except store.StoreError as e:
        return _html(web.reset_form(token, str(e)), 400)
    if not ok:
        return _html(web.reset_form(token, "That reset link is invalid or expired."), 400)
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
    # First-run gate: an un-onboarded owner can't browse any product page until they
    # answer the role question. Only GET navigations are gated — POST actions (incl.
    # /app/persona, which clears the gate, and /logout) still go through.
    if (request.method == "GET" and _needs_welcome(acct)
            and request.url.path.startswith("/app")
            and request.url.path != "/app/welcome"):
        return acct, _redirect("/app/welcome")
    # Admin-enforced MFA (IA-2): when the org requires MFA, NO principal — owner, admin,
    # or invited member — can use the app until 2FA is enrolled. The Security page (where
    # you enroll), the 2FA endpoints, and logout stay reachable so there's no lock-out loop.
    # acct["twofa_enabled"] reflects the *current principal's* own MFA (member or owner).
    if (request.method == "GET" and not _needs_welcome(acct)
            and request.url.path.startswith("/app")
            and request.url.path not in ("/app/security", "/app/settings")):
        try:
            if store.get_security_policy(acct["id"])["require_mfa"] and not acct.get("twofa_enabled"):
                return acct, _redirect("/app/security?mfa=required")
        except Exception:  # noqa: BLE001 — never hard-fail navigation on a policy read
            pass
    return acct, None


@app.get("/app/welcome", response_class=HTMLResponse)
def app_welcome(request: Request):
    """First-run onboarding: the mandatory role gate, then org-structure + invite."""
    acct, redir = _require(request)
    if redir:
        return redir
    conn = store.get_outlay_connection(acct["id"])
    idmap = store.get_outlay_identity_map(acct["id"]) or ""
    return _html(web.welcome_page(acct, conn, idmap, members=store.list_members(acct["id"])))


@app.get("/app", response_class=HTMLResponse)
def app_dashboard(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    # The role-aware Overview is the product home: a concise glance (KPIs, budget,
    # forecast) with jump-offs into the deeper areas. Attribution detail is on Spend.
    report = store.get_outlay_report(acct["id"])
    budgets = store.list_outlay_budgets(acct["id"])
    statuses = outlay_app.budget_statuses(report, budgets) if report else []
    programs = outlay_app.program_statuses(report, store.list_outlay_programs(acct["id"]),
                                           store.program_histories(acct["id"])) if report else []
    hist = store.outlay_history(acct["id"]) if report else []
    member_id = acct.get("member_id", 0) or 0
    persona = store.get_persona(acct["id"], member_id)
    lens, views, active_view_id = _resolve_home_lens(request, acct["id"], member_id, persona)
    layout = store.get_dashboard_layout(acct["id"], member_id) if persona == "business" else {}
    customize = persona == "business" and request.query_params.get("customize") == "1"
    return _html(web.overview_page(acct, report, statuses, hist,
                                   store.get_outlay_connection(acct["id"]),
                                   has_budget=bool(budgets), persona=persona,
                                   program_statuses=programs, lens=lens, views=views,
                                   active_view_id=active_view_id, layout=layout,
                                   customize=customize))


def _resolve_home_lens(request: Request, account_id: int, member_id: int, persona: str):
    """Resolve the business Home lens from query params + saved views.
    Precedence: explicit ?group/?top (ad-hoc) > ?view=ID > the person's default saved
    view > the opinionated default (group by team, top 5)."""
    if persona != "business":
        return {}, [], 0
    views = store.list_dashboard_views(account_id, member_id)
    q = request.query_params
    valid_groups = set(web.HOME_GROUPINGS)

    def clean(lens):
        g = lens.get("group_by", "team")
        g = g if g in valid_groups else "team"
        try:
            t = int(lens.get("top_n", 5))
        except (TypeError, ValueError):
            t = 5
        return {"group_by": g, "top_n": t if t in (0, 5, 10) else 5}

    if "group" in q or "top" in q:
        return clean({"group_by": q.get("group", "team"), "top_n": q.get("top", 5)}), views, 0
    if q.get("view"):
        try:
            vid = int(q["view"])
        except ValueError:
            vid = 0
        for v in views:
            if v["id"] == vid:
                return clean(v.get("lens") or {}), views, vid
    dv = store.get_default_dashboard_view(account_id, member_id)
    if dv:
        return clean(dv.get("lens") or {}), views, dv["id"]
    return {"group_by": "team", "top_n": 5}, views, 0


@app.post("/app/views")
async def app_views_save(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    name = (f.get("name") or "").strip()
    if name:
        lens = {"group_by": (f.get("group") or "team"), "top_n": int(f.get("top") or 5)}
        store.add_dashboard_view(acct["id"], name, lens, member_id=acct.get("member_id", 0) or 0,
                                 make_default=bool(f.get("make_default")))
    return _redirect("/app")


@app.post("/app/views/default")
async def app_views_default(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        vid = int(f.get("id") or 0)
    except ValueError:
        vid = 0
    store.set_default_dashboard_view(acct["id"], vid, member_id=acct.get("member_id", 0) or 0)
    return _redirect(f"/app?view={vid}" if vid else "/app")


@app.post("/app/views/delete")
async def app_views_delete(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        vid = int(f.get("id") or 0)
    except ValueError:
        vid = 0
    if vid:
        store.delete_dashboard_view(acct["id"], vid, member_id=acct.get("member_id", 0) or 0)
    return _redirect("/app")


@app.post("/app/layout")
async def app_layout(request: Request):
    """Persist the business Home card layout — reorder / hide / show / reset (Phase 3)."""
    acct, redir = _require(request)
    if redir:
        return redir
    member_id = acct.get("member_id", 0) or 0
    f = await _form(request)
    action = f.get("action") or ""
    if action == "reset":
        store.set_dashboard_layout(acct["id"], member_id, {})
        return _redirect("/app?customize=1")
    layout = store.get_dashboard_layout(acct["id"], member_id)
    order = web._home_module_order(layout)
    hidden = [k for k in (layout.get("hidden") or []) if k in web.HOME_MODULES]
    key = f.get("key") or ""
    if key not in web.HOME_MODULES:
        return _redirect("/app?customize=1")
    if action == "hide":
        if key not in hidden:
            hidden.append(key)
    elif action == "show":
        hidden = [k for k in hidden if k != key]
    elif action == "move":
        visible = [k for k in order if k not in hidden]
        if key in visible:
            i = visible.index(key)
            j = i - 1 if f.get("dir") == "up" else i + 1
            if 0 <= j < len(visible):
                visible[i], visible[j] = visible[j], visible[i]
                # rebuild full order: visible (new order) interleaved with hidden at the end
                order = visible + [k for k in order if k in hidden]
    store.set_dashboard_layout(acct["id"], member_id, {"order": order, "hidden": hidden})
    return _redirect("/app?customize=1")


@app.get("/app/estimate", response_class=HTMLResponse)
def app_estimate(request: Request):
    # Parked: the ModelPilot savings-projection page is hidden while Outlay leads
    # with spend forecasting. Redirect any stray bookmark to the Outlay estimate.
    acct, redir = _require(request)
    if redir:
        return redir
    return _redirect("/app/outlay/estimate")


def _slack_notify(account_id: int, text: str) -> None:
    """Post an alert to the account's Slack/Teams webhook if one is configured —
    best-effort, alongside email + webhooks. Slack is where eng + business live."""
    try:
        url = store.get_slack_webhook(account_id)
        if url:
            notify.send_slack(url, text)
    except Exception:  # noqa: BLE001 — alerting must never break the sync path
        pass


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
            scope = s["scope_type"] + (f' "{s["scope_id"]}"' if s.get("scope_id") else "")
            _slack_notify(account_id,
                          f":rotating_light: *Budget {new}* — {scope}: projected "
                          f"${s.get('projected_usd', 0):,.0f} vs ${s.get('limit_usd', 0) or 0:,.0f} limit.")
        store.set_outlay_budget_status(s["id"], new)


def _check_programs(account_id: int, report: dict) -> None:
    """Fire program.warn / program.over on transition. For a 'hard' program, an
    'over' is the signal the opt-in gateway enforces against (block / route-down) —
    so this event is also the automation hook for teams without the gateway."""
    programs = store.list_outlay_programs(account_id)
    if not programs:
        return
    for s in outlay_app.program_statuses(report, programs, store.program_histories(account_id)):
        new, old = s["status"], s.get("last_status")
        if new in ("warn", "over") and new != old:
            store.deliver_event(account_id, f"program.{new}", {
                "program": s.get("name"), "program_id": s.get("id"),
                "enforce_mode": s.get("enforce_mode"), "action": s.get("action"),
                "floor_model": s.get("floor_model"),
                "spent_usd": s["spent_usd"], "limit_usd": s["limit_usd"],
                "projected_usd": s["projected_usd"], "period_days": s.get("period_days")})
            acct = store.get_account(account_id)
            if acct and acct.get("email"):
                try:
                    notify.send_budget_alert(acct["email"], new, s.get("projected_usd", 0),
                                             s.get("limit_usd", 0) or 0,
                                             scope=f'program "{s.get("name")}"', product="Outlay")
                except Exception:  # noqa: BLE001 — alerting never breaks the path
                    pass
            hard = s.get("enforce_mode") == "hard" and new == "over"
            act = (f" — gateway will {s.get('action')}"
                   f"{(' to ' + s.get('floor_model')) if s.get('action') == 'downgrade' and s.get('floor_model') else ''}"
                   if hard else "")
            _slack_notify(account_id,
                          f":rotating_light: *Program {new}* — {s.get('name')}: projected "
                          f"${s.get('projected_usd', 0):,.0f} vs ${s.get('limit_usd', 0) or 0:,.0f} limit{act}.")
        store.set_outlay_program_status(s["id"], new)


def _check_anomalies(account_id: int, report: dict) -> None:
    """Alert on *newly* detected runaway tickets (≥3× their work-type median) — to
    subscribed webhooks and the owner's email. De-duped on ticket id so a standing
    outlier isn't re-emailed every sync; a ticket that drops off and re-spikes does."""
    threshold, muted = store.get_anomaly_prefs(account_id)
    anomalies = [a for a in (report.get("anomalies") or [])
                 if a.get("ratio", 0) >= threshold and a["ticket_id"] not in muted]
    ids = {a["ticket_id"] for a in anomalies}
    already = store.get_alerted_anomalies(account_id)
    new = [a for a in anomalies if a["ticket_id"] not in already]
    if new:
        acct = store.get_account(account_id)
        email = (acct or {}).get("email")
        if email:
            try:
                notify.send_anomaly_alert(email, new, product="Outlay")
            except Exception:  # noqa: BLE001 — alerting must never break the sync path
                pass
        store.deliver_event(account_id, "anomaly.detected", {
            "count": len(new),
            "tickets": [{"ticket_id": a["ticket_id"], "task_class": a["task_class"],
                         "cost_usd": a["cost_usd"], "ratio": a["ratio"]} for a in new]})
        worst = new[0]
        _slack_notify(account_id,
                      f":warning: *{len(new)} runaway ticket{'s' if len(new) != 1 else ''}* — worst "
                      f"{worst['ticket_id']} at {worst.get('ratio', 0):.0f}× its class median "
                      f"(${worst.get('cost_usd', 0):,.0f}).")
    store.set_alerted_anomalies(account_id, ids)


# Alert once auto-sync has failed this many times in a row (a single blip is
# usually transient; a standing failure means a token was revoked / data is stale).
_SYNC_FAIL_ALERT_AT = 2
_SYNC_ALERT_COOLDOWN = 12 * 3600  # don't re-alert more than every 12h while broken


def _alert_sync_failure(account_id: int, fails: int, message: str, now: float | None = None) -> None:
    """On a *persistent* auto-sync failure, tell the owner once (email + Slack) so
    stale data never goes unnoticed. De-duped via sync_alerted_at so a connection
    that stays broken doesn't re-alert every cron tick."""
    if fails < _SYNC_FAIL_ALERT_AT:
        return
    import time
    conn = store.get_outlay_connection(account_id) or {}
    now = now or time.time()
    last = conn.get("sync_alerted_at") or 0
    if last and now - last < _SYNC_ALERT_COOLDOWN:
        return
    since = ""
    if conn.get("synced_at"):
        from datetime import datetime, timezone
        since = datetime.fromtimestamp(conn["synced_at"], timezone.utc).strftime("%b %d, %Y")
    acct = store.get_account(account_id)
    email = (acct or {}).get("email")
    if email:
        try:
            notify.send_sync_failure_alert(email, fails, last_error=message, since=since, product="Outlay")
        except Exception:  # noqa: BLE001 — alerting must never break the sync sweep
            pass
    _slack_notify(account_id,
                  f":warning: *Auto-sync failing* — {fails} attempts in a row. Spend data is going "
                  f"stale{f' (last good {since})' if since else ''}. Fix the connection.")
    store.mark_outlay_sync_alerted(account_id, now=now)


_AUTO_SYNC_CHOICES = (0, 24, 168)  # off · daily · weekly


def _auto_sync_hours(raw) -> int:
    try:
        v = int(raw)
    except (TypeError, ValueError):
        return 0
    return v if v in _AUTO_SYNC_CHOICES else 0


def _parse_date_ts(raw) -> float | None:
    """'YYYY-MM-DD' (from an <input type=date>) → UTC unix ts, or None."""
    raw = (raw or "").strip()
    if not raw:
        return None
    try:
        from datetime import datetime, timezone
        return datetime.strptime(raw, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp()
    except ValueError:
        return None


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
            fails = store.mark_outlay_sync_error(account_id, str(e), now=now)
            _alert_sync_failure(account_id, fails, str(e), now=now)
            failed += 1
            continue
        store.save_outlay_report(account_id, report)
        store.record_outlay_snapshot(account_id, report, now=now)
        store.mark_outlay_synced(account_id, now=now)
        _check_budgets(account_id, report)
        _check_programs(account_id, report)
        _check_anomalies(account_id, report)
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
    store.mark_cron_run("sync-due", summary)
    return JSONResponse({"ok": True, **summary})


@app.post("/internal/outlay/digest-due")
async def app_outlay_digest_due(request: Request):
    """Cron hook: send the weekly spend digest to every account whose cadence has
    elapsed. Same OUTLAY_CRON_TOKEN gate as sync-due; safe to call daily (the
    weekly cadence is enforced per account)."""
    want = os.environ.get("OUTLAY_CRON_TOKEN", "")
    auth = request.headers.get("authorization", "")
    got = auth[7:].strip() if auth[:7].lower() == "bearer " else ""
    if not want or not secrets.compare_digest(got, want):
        return JSONResponse({"ok": False, "error": "unauthorized"}, status_code=401)
    result = await asyncio.to_thread(_run_maintenance)
    return JSONResponse({"ok": True, **result})


def _run_maintenance() -> dict:
    """The daily maintenance bundle: weekly digest + monthly close pack (both
    cadence-guarded per account), durable webhook redelivery, and data-retention
    purge. Idempotent and safe to run as often as hourly — only due work fires.
    Records the run so /admin/health shows freshness. Shared by the cron endpoint
    and the in-process scheduler."""
    from . import close_pack, spend_digest
    summary = spend_digest.run_due_digests()
    close = close_pack.run_due_close_packs()
    webhooks = store.redeliver_due_webhooks()
    pruned = store.prune_webhook_deliveries()  # cap the delivery-log table
    retention = store.purge_due_outlay_history()
    result = {**summary, "close_pack": close, "webhooks": webhooks,
              "deliveries_pruned": pruned, "retention": retention}
    store.mark_cron_run("digest-due", result)
    return result


@app.post("/app/digest")
async def app_digest_toggle(request: Request):
    """Owner toggles the weekly spend digest email on/off."""
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    store.set_digest_weekly(acct["id"], bool(f.get("weekly")))
    store.set_close_pack_monthly(acct["id"], bool(f.get("close_pack")))
    _audit(acct["id"], "digest.toggle",
           actor=acct.get("display_email") or acct.get("email", ""),
           detail=f"weekly={'on' if f.get('weekly') else 'off'} "
                  f"close_pack={'on' if f.get('close_pack') else 'off'}")
    return _redirect("/app/settings#digest")


@app.post("/app/retention")
async def app_retention(request: Request):
    """Owner sets the spend-history retention window (data minimization)."""
    acct, redir = _require(request)
    if redir:
        return redir
    if acct.get("team_role") != "owner":
        return _redirect("/app/settings")
    f = await _form(request)
    try:
        days = int(f.get("retention_days") or 0)
    except (TypeError, ValueError):
        days = 0
    store.set_retention_days(acct["id"], days)
    # Apply immediately so an existing backlog of snapshots is trimmed on save.
    if days:
        store.purge_outlay_history(acct["id"], days)
    _audit(acct["id"], "retention.set",
           actor=acct.get("display_email") or acct.get("email", ""),
           detail=f"days={days or 'forever'}")
    return _redirect("/app/settings?saved=1#retention")


@app.post("/app/outlay/purge")
async def app_outlay_purge(request: Request):
    """Right-to-erasure: wipe ingested spend data (report + history) on demand.
    Owner only; the connection config stays so the customer can re-sync."""
    acct, redir = _require(request)
    if redir:
        return redir
    if acct.get("team_role") != "owner":
        return _redirect("/app/settings")
    f = await _form(request)
    if f.get("confirm", "").strip().lower() != "delete":
        return _redirect("/app/settings?purge_error=1#retention")
    store.purge_outlay_data(acct["id"])
    _audit(acct["id"], "outlay.purge",
           actor=acct.get("display_email") or acct.get("email", ""), detail="report+history")
    return _redirect("/app/settings?purged=1#retention")


@app.get("/app/outlay", response_class=HTMLResponse)
def app_outlay(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    report = store.get_outlay_report(acct["id"])
    budgets = store.list_outlay_budgets(acct["id"])
    statuses = outlay_app.budget_statuses(report, budgets) if report else []
    hist = store.outlay_history(acct["id"]) if report else []
    persona = store.get_persona(acct["id"], acct.get("member_id", 0) or 0)
    return _html(web.outlay_page(acct, report, statuses, hist,
                                 store.get_outlay_connection(acct["id"]),
                                 has_budget=bool(budgets), persona=persona))


@app.get("/app/outlay/scope", response_class=HTMLResponse)
def app_outlay_scope(request: Request, type: str = "team", id: str = ""):
    """Drill-down into the tickets behind one team or work type."""
    acct, redir = _require(request)
    if redir:
        return redir
    scope_type = type if type in ("team", "class") else "team"
    return _html(web.scope_page(acct, store.get_outlay_report(acct["id"]), scope_type, id))


@app.get("/app/outlay/showback")
def app_outlay_showback(request: Request):
    """Retired: per-team chargeback now lives on the Spend page (the team /
    cost-center allocation card + the by-team CSV/FOCUS export). Kept as a
    redirect so old bookmarks and links don't 404."""
    return _redirect("/app/outlay")


@app.post("/app/outlay/anomaly/mute")
async def app_anomaly_mute(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    tid = (f.get("ticket_id") or "").strip()
    if tid:
        store.mute_ticket(acct["id"], tid)
    return _redirect("/app/outlay")


@app.post("/app/outlay/anomaly/unmute")
async def app_anomaly_unmute(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    tid = (f.get("ticket_id") or "").strip()
    if tid:
        store.unmute_ticket(acct["id"], tid)
    return _redirect("/app/outlay")


@app.post("/app/outlay/anomaly/threshold")
async def app_anomaly_threshold(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        store.set_anomaly_threshold(acct["id"], float(f.get("threshold") or 3))
    except (TypeError, ValueError):
        pass
    return _redirect("/app/outlay")


@app.post("/app/outlay/slack")
async def app_outlay_slack(request: Request):
    """Save (or clear) the Slack/Teams incoming-webhook URL for budget + anomaly alerts."""
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        store.set_slack_webhook(acct["id"], f.get("slack_webhook"))
    except store.StoreError:
        return _redirect("/app/outlay/connect?slack_error=1#alerts")
    _audit(acct["id"], "slack.save",
           actor=acct.get("display_email") or acct.get("email", ""),
           detail="set" if (f.get("slack_webhook") or "").strip() else "cleared")
    return _redirect("/app/outlay/connect#alerts")


@app.post("/app/persona")
async def app_set_persona(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    p = (f.get("persona") or "").strip()
    if p in ("business", "eng"):
        store.set_persona(acct["id"], p, member_id=acct.get("member_id", 0) or 0)
    # From the first-run gate, advance to the rest of onboarding (org + invite);
    # the in-app persona switch keeps landing on Spend.
    if (f.get("next") or "") == "welcome":
        return _redirect("/app/welcome")
    return _redirect("/app/outlay")


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
    cost_export = (data.get("cost_export") or "").strip()
    if not issues or not usage:
        return JSONResponse({"ok": False, "error": "Paste both the tracker and AI-usage JSON."})
    try:
        report = outlay_app.build_report(issues, usage, planned,
                                         identity_text=store.get_outlay_identity_map(acct["id"]))
    except ValueError as e:
        return JSONResponse({"ok": False, "error": str(e)})
    except Exception:  # noqa: BLE001
        return JSONResponse({"ok": False, "error": "Could not process that data."})
    # Optional: reconcile against a pasted provider cost/billing export (any provider).
    if cost_export:
        try:
            invoice_usd, source = outlay_app.parse_cost_export(cost_export)
            if invoice_usd > 0:
                outlay_app.reconcile(report, invoice_usd, source, report.get("window_days", 30))
        except Exception:  # noqa: BLE001 — reconciliation is best-effort, never fail the run
            pass
    store.save_outlay_report(acct["id"], report)
    store.record_outlay_snapshot(acct["id"], report)
    _check_budgets(acct["id"], report)
    _check_programs(acct["id"], report)
    _check_anomalies(acct["id"], report)
    return JSONResponse({"ok": True})


@app.post("/app/demo/enter")
async def app_demo_enter(request: Request):
    """Turn demo mode on for a gated demo account — seeds a full worked customer
    (report, budgets, programs, a synced source) and drops into Business."""
    acct, redir = _require(request)
    if redir:
        return redir
    if not acct.get("_can_demo"):
        return _redirect("/app/outlay")
    demo.enter(acct["id"], member_id=acct.get("member_id", 0) or 0)
    _audit(acct["id"], "demo.enter", actor=acct.get("display_email", ""))
    return _redirect("/app/outlay")


@app.post("/app/demo/exit")
async def app_demo_exit(request: Request):
    """Turn demo mode off and wipe the seeded data back to a clean account."""
    acct, redir = _require(request)
    if redir:
        return redir
    if not acct.get("_can_demo"):
        return _redirect("/app/outlay")
    demo.exit(acct["id"])
    _audit(acct["id"], "demo.exit", actor=acct.get("display_email", ""))
    return _redirect("/app/outlay")


@app.post("/app/onboarding/reset")
async def app_onboarding_reset(request: Request):
    """Reset an internal/test account to the first-run new-user state so the
    onboarding role gate can be re-tested. Clears the role choice + any seeded or
    ingested data (report, budgets, programs, connection, team map). Gated to
    demo/test accounts (DEMO_ACCOUNT_EMAILS) — never available to real customers."""
    acct, redir = _require(request)
    if redir:
        return redir
    if not acct.get("_can_demo"):
        return _redirect("/app/outlay")
    demo.clear(acct["id"])  # report/history, budgets, programs, connection
    store.set_outlay_identity_map(acct["id"], None)
    store.set_demo_mode(acct["id"], False)
    store.clear_persona(acct["id"], member_id=acct.get("member_id", 0) or 0)
    _audit(acct["id"], "onboarding.reset", actor=acct.get("display_email", ""))
    return _redirect("/app/welcome")


@app.get("/app/demo/guide", response_class=HTMLResponse)
def app_demo_guide(request: Request):
    """Presenter's talk-track for the live demo — demo accounts only."""
    acct, redir = _require(request)
    if redir:
        return redir
    if not acct.get("_can_demo"):
        return _redirect("/app/outlay")
    return _html(web.demo_guide_page(acct))


@app.post("/app/outlay/sample")
async def app_outlay_sample(request: Request):
    """One-click populated dashboard from bundled fixtures — demo accounts only."""
    acct, redir = _require(request)
    if redir:
        return redir
    if not acct.get("_can_demo"):
        return _redirect("/app/outlay")
    report = outlay_app.sample_report()
    store.save_outlay_report(acct["id"], report)
    # Seed a short synthetic history (backdated) so the worked example shows a real
    # spend trend + movers, not a single point. Clearly flagged as sample data.
    import time
    now = time.time()
    for i, f in enumerate((0.78, 0.86, 0.93)):
        snap = {
            "spend": {"total_usd": (report.get("spend") or {}).get("total_usd", 0.0) * f},
            "forecast": {"expected_usd": (report.get("forecast") or {}).get("expected_usd", 0.0) * f},
            "team_spend": [{"team": t["team"], "spent_usd": t.get("spent_usd", 0.0) * f}
                           for t in (report.get("team_spend") or [])],
            "class_spend": [{"task_class": c["task_class"], "spent_usd": c.get("spent_usd", 0.0) * f}
                            for c in (report.get("class_spend") or [])],
        }
        store.record_outlay_snapshot(acct["id"], snap, now=now - (3 - i) * 86400)
    store.record_outlay_snapshot(acct["id"], report, now=now)
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


@app.post("/app/outlay/identity")
async def app_outlay_identity_save(request: Request):
    """Save the identity→team map (one `identifier, team` per line) that drives
    cost-center allocation when tickets don't carry a team."""
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    store.set_outlay_identity_map(acct["id"], (f.get("identity_map") or "").strip() or None)
    _audit(acct["id"], "identity.save",
           actor=acct.get("display_email") or acct.get("email", ""))
    if (f.get("next") or "") == "welcome":
        return _redirect("/app/welcome")
    return _redirect("/app/outlay/connect#teams")


def _merge_identity_csv(existing: str, csv_text: str) -> str:
    """Merge an uploaded `email,team` CSV into the existing identity-map text. Keeps
    one `identifier, team` per line; later (uploaded) rows win on conflict; a
    header row like `email,team` is skipped."""
    import csv as _csv
    import io as _io
    order: list[str] = []
    mapping: dict[str, tuple[str, str]] = {}

    def add(ident: str, team: str) -> None:
        ident, team = (ident or "").strip(), (team or "").strip()
        if not ident or not team:
            return
        key = ident.lower()
        if key not in mapping:
            order.append(key)
        mapping[key] = (ident, team)

    for line in (existing or "").splitlines():
        if "," in line:
            a, b = line.split(",", 1)
            add(a, b)
    for row in _csv.reader(_io.StringIO(csv_text)):
        if len(row) >= 2:
            if row[0].strip().lower() in ("email", "identifier", "user", "person") \
               and row[1].strip().lower() in ("team", "cost center", "cost_center", "costcenter"):
                continue
            add(row[0], row[1])
    return "\n".join(f"{mapping[k][0]}, {mapping[k][1]}" for k in order)


async def _multipart(request: Request) -> tuple[dict, str | None]:
    """Minimal multipart/form-data parser (the app intentionally avoids the
    python-multipart dependency). Returns (text fields, uploaded file text)."""
    import re as _re
    ctype = request.headers.get("content-type", "")
    if "multipart/form-data" not in ctype or "boundary=" not in ctype:
        return {}, None
    boundary = ctype.split("boundary=", 1)[1].strip().strip('"')
    body = await request.body()
    fields: dict[str, str] = {}
    filetext: str | None = None
    for part in body.split(("--" + boundary).encode()):
        part = part.strip(b"\r\n")
        if not part or part == b"--":
            continue
        head, _, content = part.partition(b"\r\n\r\n")
        head_s = head.decode("utf-8", "replace")
        if "filename=" in head_s or 'name="file"' in head_s:
            filetext = content.decode("utf-8", "replace")
        else:
            m = _re.search(r'name="([^"]+)"', head_s)
            if m:
                fields[m.group(1)] = content.decode("utf-8", "replace").strip()
    return fields, filetext


@app.post("/app/outlay/identity/upload")
async def app_outlay_identity_upload(request: Request):
    """Upload an `email,team` CSV of org structure; merged into the identity map."""
    acct, redir = _require(request)
    if redir:
        return redir
    fields, filetext = await _multipart(request)
    if filetext:
        merged = _merge_identity_csv(store.get_outlay_identity_map(acct["id"]) or "", filetext)
        store.set_outlay_identity_map(acct["id"], merged or None)
        _audit(acct["id"], "identity.upload",
               actor=acct.get("display_email") or acct.get("email", ""))
    if (fields.get("next") or "") == "welcome":
        return _redirect("/app/welcome")
    return _redirect("/app/outlay/connect#teams")


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
    _audit(acct["id"], "connection.save",
           actor=acct.get("display_email") or acct.get("email", ""),
           detail=f"tracker={f.get('tracker') or 'github'}")
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
    _check_programs(acct["id"], report)
    _check_anomalies(acct["id"], report)
    return JSONResponse({"ok": True})


@app.get("/app/outlay/budgets", response_class=HTMLResponse)
def app_outlay_budgets(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    report = store.get_outlay_report(acct["id"])
    statuses = outlay_app.budget_statuses(report, store.list_outlay_budgets(acct["id"]))
    programs = outlay_app.program_statuses(report, store.list_outlay_programs(acct["id"]),
                                           store.program_histories(acct["id"])) if report else []
    return _html(web.budgets_page(acct, report, statuses, outlay_app.project_spend(report),
                                  program_statuses=programs))


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
        _audit(acct["id"], "budget.add", actor=acct.get("display_email") or acct["email"],
               detail=f"{scope}{('/' + f.get('scope_id')) if f.get('scope_id') else ''} "
                      f"${limit:,.0f} / {int(f.get('period_days') or 30)}d")
    return _redirect("/app/outlay/budgets")


@app.post("/app/outlay/budgets/delete")
async def app_outlay_budgets_delete(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    bid = int(f.get("id") or 0)
    store.delete_outlay_budget(acct["id"], bid)
    _audit(acct["id"], "budget.delete", actor=acct.get("display_email") or acct["email"],
           detail=f"budget #{bid}")
    return _redirect("/app/outlay/budgets")


@app.get("/app/outlay/programs", response_class=HTMLResponse)
def app_outlay_programs(request: Request):
    """Program budgets — named budgets spanning several teams / projects / work types,
    with optional hard-cap enforcement via the opt-in gateway."""
    acct, redir = _require(request)
    if redir:
        return redir
    report = store.get_outlay_report(acct["id"])
    statuses = outlay_app.program_statuses(report, store.list_outlay_programs(acct["id"]),
                                           store.program_histories(acct["id"]))
    return _html(web.programs_page(acct, report, statuses))


@app.get("/app/outlay/summary")
def app_outlay_summary(request: Request):
    """The quarterly summary is now consolidated into the business Home — keep the URL
    working (bookmarks, the close-report link) by redirecting there."""
    acct, redir = _require(request)
    if redir:
        return redir
    return _redirect("/app")


@app.get("/app/outlay/governance", response_class=HTMLResponse)
def app_outlay_governance(request: Request):
    """Consolidated business governance — budgets + programs in one deep view."""
    acct, redir = _require(request)
    if redir:
        return redir
    report = store.get_outlay_report(acct["id"])
    budgets = outlay_app.budget_statuses(report, store.list_outlay_budgets(acct["id"])) if report else []
    programs = outlay_app.program_statuses(report, store.list_outlay_programs(acct["id"]),
                                           store.program_histories(acct["id"])) if report else []
    projects = outlay_app.project_spend(report) if report else []
    return _html(web.governance_page(acct, report, budgets, programs, projects))


@app.post("/app/outlay/programs")
async def app_outlay_programs_add(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    name = (f.get("name") or "").strip()
    try:
        limit = float(f.get("limit_usd") or 0)
    except ValueError:
        limit = 0.0
    # members: one per line, "scope_type id" or "scope_type:id" (overall needs no id)
    members = []
    for raw in (f.get("members") or "").splitlines():
        raw = raw.strip()
        if not raw:
            continue
        parts = raw.replace(":", " ", 1).split(None, 1)
        st = parts[0].lower()
        sid = parts[1].strip() if len(parts) > 1 else ""
        if st in ("team", "class", "project", "overall"):
            members.append({"scope_type": st, "scope_id": sid})
    enforce = f.get("enforce_mode") or "alert"
    action = f.get("action") or "block"
    floor = (f.get("floor_model") or "").strip()
    try:
        period = int(f.get("period_days") or 90)
    except ValueError:
        period = 90
    start_ts = _parse_date_ts(f.get("start_date"))
    end_ts = _parse_date_ts(f.get("end_date"))
    if name and limit > 0 and members:
        store.add_outlay_program(acct["id"], name, members, limit, period,
                                 enforce_mode=enforce, action=action, floor_model=floor,
                                 start_ts=start_ts, end_ts=end_ts)
        _audit(acct["id"], "program.create",
               actor=acct.get("display_email") or acct.get("email", ""),
               detail=f"{name} · {enforce} · ${limit:,.0f}/{period}d")
    return _redirect("/app/outlay/programs")


@app.post("/app/outlay/programs/update")
async def app_outlay_programs_update(request: Request):
    """Reallocate / retune a program in place — change its budget, or flip between
    alert-only and a hard cap — without redefining it."""
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    pid = int(f.get("id") or 0)
    kwargs = {}
    if f.get("limit_usd"):
        try:
            kwargs["limit_usd"] = float(f.get("limit_usd"))
        except ValueError:
            pass
    if f.get("enforce_mode") in ("alert", "hard"):
        kwargs["enforce_mode"] = f.get("enforce_mode")
    if kwargs and store.update_outlay_program(acct["id"], pid, **kwargs):
        _audit(acct["id"], "program.update",
               actor=acct.get("display_email") or acct.get("email", ""),
               detail=f"id={pid} " + " ".join(f"{k}={v}" for k, v in kwargs.items()))
    return _redirect("/app/outlay/programs")


@app.post("/app/outlay/programs/delete")
async def app_outlay_programs_delete(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    store.delete_outlay_program(acct["id"], int(f.get("id") or 0))
    return _redirect("/app/outlay/programs")


@app.get("/app/outlay/export.csv")
def app_outlay_export(request: Request, view: str = "tickets"):
    """Download a CSV slice of the report (tickets/people/classes/savings) for business."""
    acct, redir = _require(request)
    if redir:
        return redir
    report = store.get_outlay_report(acct["id"])
    if not report:
        return _redirect("/app/outlay")
    if view not in ("tickets", "people", "classes", "teams", "savings", "models"):
        view = "tickets"
    csv_text = outlay_app.report_csv(report, view)
    return PlainTextResponse(csv_text, media_type="text/csv", headers={
        "content-disposition": f'attachment; filename="outlay-{view}.csv"'})


@app.get("/app/outlay/export.focus.csv")
def app_outlay_export_focus(request: Request):
    """FOCUS-aligned per-ticket charge rows (FinOps Open Cost & Usage Spec column
    names) — load Outlay's attributed spend into any FOCUS-aware FinOps/BI tool."""
    acct, redir = _require(request)
    if redir:
        return redir
    report = store.get_outlay_report(acct["id"])
    if not report:
        return _redirect("/app/outlay")
    return PlainTextResponse(outlay_app.report_focus_csv(report), media_type="text/csv",
                             headers={"content-disposition": 'attachment; filename="outlay-focus.csv"'})


@app.get("/app/outlay/variance.csv")
def app_outlay_variance_csv(request: Request):
    """Quarterly program plan-vs-actual variance report as CSV (for finance)."""
    acct, redir = _require(request)
    if redir:
        return redir
    report = store.get_outlay_report(acct["id"])
    statuses = (outlay_app.program_statuses(report, store.list_outlay_programs(acct["id"]),
                                            store.program_histories(acct["id"])) if report else [])
    rep = outlay_app.variance_report(statuses)
    return PlainTextResponse(outlay_app.variance_report_csv(rep), media_type="text/csv",
                             headers={"content-disposition": f'attachment; filename="outlay-variance-{rep["quarter"].replace(" ", "-")}.csv"'})


@app.get("/api/v1/spend")
def api_v1_spend(request: Request):
    """Token-authed spend export for BI/warehouse pipelines. Bearer (or
    x-modelpilot-key) API key → the account's latest report as FOCUS-aligned rows.
    Read-only; returns the same attributed numbers shown in the console."""
    resolved, err = _api_auth(request)
    if err:
        return err
    report = store.get_outlay_report(resolved["account_id"])
    conn = store.get_outlay_connection(resolved["account_id"])
    if not report:
        return JSONResponse({"account_id": resolved["account_id"], "period": None,
                             "currency": "USD", "total_usd": 0.0,
                             "data_quality": outlay_app.data_quality({}, conn), "rows": []})
    rows = outlay_app.focus_rows(report)
    total = round(sum(float(r.get("BilledCost") or 0) for r in rows), 6)
    period = {"start": rows[0]["ChargePeriodStart"], "end": rows[0]["ChargePeriodEnd"]} if rows else None
    return JSONResponse({"account_id": resolved["account_id"], "period": period,
                         "currency": "USD", "total_usd": total,
                         "data_quality": outlay_app.data_quality(report, conn), "rows": rows})


@app.get("/api/v1/data-quality")
def api_v1_data_quality(request: Request):
    """Token-authed trust summary — coverage, reconciliation, pricing fidelity, and
    freshness rolled into one good/fair/poor verdict. Lightweight (no rows), so a
    pipeline can gate or a monitor can alert on data confidence."""
    resolved, err = _api_auth(request)
    if err:
        return err
    report = store.get_outlay_report(resolved["account_id"])
    conn = store.get_outlay_connection(resolved["account_id"])
    return JSONResponse({"account_id": resolved["account_id"],
                         **outlay_app.data_quality(report or {}, conn)})


@app.get("/api/v1/enforcement")
def api_v1_enforcement(request: Request, ticket: str = "", team: str = "", work_type: str = ""):
    """The hard-cap enforcement decision the opt-in gateway consults. Token-authed.

    Returns the programs currently over their *hard* cap (`enforced`) so the in-path
    client can cache this and match each call's attribution tags to a member scope
    locally. As a convenience it also resolves a single call when `ticket` / `team` /
    `work_type` are supplied → `{decision: allow|block|downgrade, floor_model, …}`.
    Read-only: Outlay returns the verdict; the gateway acts on the traffic."""
    resolved, err = _api_auth(request)
    if err:
        return err
    report = store.get_outlay_report(resolved["account_id"])
    programs = store.list_outlay_programs(resolved["account_id"])
    enforced = outlay_app.enforced_programs(report or {}, programs)
    decision = (outlay_app.program_decision(enforced, ticket_id=ticket, team=team, task_class=work_type)
                if (ticket or team or work_type) else None)
    return JSONResponse({"account_id": resolved["account_id"], "enforced": enforced,
                         "decision": decision})


@app.post("/api/v1/enforcement/report")
async def api_v1_enforcement_report(request: Request):
    """The gateway reports how many calls it blocked / routed down per program, so
    the console can show business the hard cap is actually biting. Token-authed;
    body: {"counts": {"<program_id>": n}}."""
    resolved, err = _api_auth(request)
    if err:
        return err
    try:
        data = await request.json()
    except Exception:  # noqa: BLE001
        data = {}
    counts = (data or {}).get("counts") or {}
    if not isinstance(counts, dict):
        return JSONResponse({"ok": False, "error": "counts must be an object"}, status_code=400)
    hit = store.record_program_enforcement(resolved["account_id"], counts)
    return JSONResponse({"ok": True, "programs_updated": hit})


def _audit_iso(ts) -> str:
    from datetime import datetime, timezone
    try:
        return datetime.fromtimestamp(float(ts), timezone.utc).isoformat()
    except (TypeError, ValueError, OSError):
        return ""


@app.get("/api/v1/audit")
def api_v1_audit(request: Request, since: int = 0, limit: int = 1000):
    """Token-authed audit-log export for SIEM ingestion (Splunk/Datadog/etc).
    Bearer/x-modelpilot-key API key → security events in ascending id order. Poll
    incrementally with `?since=<next_since>` to fetch only new events, gap-free."""
    resolved, err = _api_auth(request)
    if err:
        return err
    rows = store.audit_events(resolved["account_id"], since_id=since, limit=limit)
    events = [{"id": r["id"], "ts": _audit_iso(r["ts"]), "actor": r.get("actor") or "",
               "action": r.get("action") or "", "detail": r.get("detail") or ""} for r in rows]
    next_since = events[-1]["id"] if events else int(since or 0)
    return JSONResponse({"account_id": resolved["account_id"],
                         "next_since": next_since, "count": len(events), "events": events})


@app.get("/app/audit/export.csv")
def app_audit_export(request: Request):
    """Download the full audit trail as CSV (admin session) — for an offline record
    or a one-off SIEM/GRC import."""
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["id", "timestamp", "actor", "action", "detail"])
    for r in store.audit_events(acct["id"], since_id=0, limit=5000):
        w.writerow([r["id"], _audit_iso(r["ts"]), r.get("actor") or "",
                    r.get("action") or "", r.get("detail") or ""])
    return PlainTextResponse(buf.getvalue(), media_type="text/csv",
                             headers={"content-disposition": 'attachment; filename="outlay-audit.csv"'})


@app.get("/app/outlay/close-report.html", response_class=HTMLResponse)
def app_outlay_close_report(request: Request):
    """A printable business close report — the VP-ready audit readout for the current
    window (total, attribution, forecast, flags, accuracy, reconciliation). Opens in
    a new tab; print-to-PDF for the books."""
    acct, redir = _require(request)
    if redir:
        return redir
    report = store.get_outlay_report(acct["id"])
    if not report:
        return _redirect("/app/outlay")
    from outlay.readout import render_html
    company = acct.get("company") or "Your team"
    return HTMLResponse(render_html(report, company=company))


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
    overall = next((b.get("limit_usd", 0) or 0 for b in store.list_outlay_budgets(acct["id"])
                    if b.get("scope_type") == "overall"), 0.0)
    return _html(web.estimate_backlog_page(acct, store.get_outlay_report(acct["id"]),
                                           overall_budget_usd=overall))


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
                                   twofa=request.query_params.get("twofa", ""),
                                   retention_days=store.get_retention_days(acct["id"]),
                                   purged=request.query_params.get("purged") == "1",
                                   purge_error=request.query_params.get("purge_error") == "1"))


_SEC_FLASH = {"mfa": "mfa-required", "policy": "policy-saved", "totp": "totp-on",
              "totpbad": "totp-bad", "loggedout": "logged-out-all", "passkey": "passkey-on"}


def _security_html(acct, enroll_secret="", flash_key=""):
    flash = _SEC_FLASH.get(flash_key, "")
    mid = acct.get("member_id", 0) or 0
    return _html(web.security_page(acct, policy=store.get_security_policy(acct["id"]),
                                   twofa=store.get_2fa(acct["id"], member_id=mid),
                                   enroll_secret=enroll_secret, flash=flash,
                                   passkeys=store.list_webauthn_credentials(acct["id"], mid),
                                   webauthn_on=webauthn_box.available()))


@app.get("/app/security", response_class=HTMLResponse)
def security_get(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    fk = "mfa" if request.query_params.get("mfa") == "required" else request.query_params.get("ok", "")
    return _security_html(acct, flash_key=fk)


@app.post("/app/security/policy")
async def security_policy(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    if acct.get("team_role") not in ("owner", "admin"):
        return _redirect("/app/security")
    f = await _form(request)
    store.update_security_policy(
        acct["id"], require_mfa=bool(f.get("require_mfa")),
        session_idle_min=f.get("session_idle_min") or 0,
        session_max_hours=f.get("session_max_hours") or 0,
        security_webhook=f.get("security_webhook", ""), data_region=f.get("data_region", ""))
    _audit(acct["id"], "security.policy", actor=acct.get("display_email") or acct["email"],
           detail=f"require_mfa={bool(f.get('require_mfa'))}")
    return _redirect("/app/security?ok=policy")


@app.post("/app/security/logout-all")
async def security_logout_all(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    store.bump_session_epoch(acct["id"], acct.get("member_id", 0) or 0)
    _audit(acct["id"], "session.logout_all", actor=acct.get("display_email") or acct["email"])
    # Re-issue this device's session with the new epoch so the current user stays in.
    resp = _redirect("/app/security?ok=loggedout")
    fresh = store.get_account(acct["id"])
    _set_session(resp, fresh, acct.get("team_role", "owner"), acct.get("member_id", 0) or 0,
                 platform_role="customer" if acct.get("member_id") else None)
    return resp


@app.get("/app/security/vpat", response_class=HTMLResponse)
def security_vpat(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    return _html(web.vpat_page(acct))


@app.get("/app/security/ai-card", response_class=HTMLResponse)
def security_ai_card(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    return _html(web.ai_card_page(acct))


# --- two-factor authentication -------------------------------------------- #

@app.post("/app/2fa/start")
async def twofa_start(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    if acct.get("member_id"):   # invited members are authenticator-only (TOTP), no email OTP
        return _redirect("/app/security")
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
    if acct.get("member_id"):   # TOTP-only for members
        return _redirect("/app/security")
    f = await _form(request)
    if store.verify_otp(acct["id"], f.get("code", "")):
        store.set_2fa(acct["id"], "email", acct["email"])
        _audit(acct["id"], "2fa.enable", actor=acct["email"], detail="email codes")
        return _redirect("/app/settings?twofa=on")
    return _redirect("/app/settings?twofa=bad")


@app.post("/app/2fa/totp/start")
async def twofa_totp_start(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    # Generate a fresh secret and show the enrollment panel (secret carried in the form).
    return _security_html(acct, enroll_secret=store.new_totp_secret())


@app.post("/app/2fa/totp/confirm")
async def twofa_totp_confirm(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    secret = (f.get("secret") or "").strip()
    code = (f.get("code") or "").strip().replace(" ", "")
    ok = bool(secret) and any(store.totp_code(secret, time.time() + d * 30) == code for d in (-1, 0, 1))
    if ok:
        store.set_totp(acct["id"], secret, member_id=acct.get("member_id", 0) or 0)
        _audit(acct["id"], "2fa.enable", actor=acct.get("display_email") or acct["email"],
               detail="authenticator app (totp)")
        return _redirect("/app/security?ok=totp")
    return _security_html(acct, enroll_secret=secret, flash_key="totpbad")


@app.post("/app/2fa/disable")
async def twofa_disable(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    store.disable_2fa(acct["id"], member_id=acct.get("member_id", 0) or 0)
    _audit(acct["id"], "2fa.disable", actor=acct.get("display_email") or acct["email"])
    return _redirect("/app/security")


# --- WebAuthn / passkeys (phishing-resistant MFA) ------------------------- #

def _wa_cookie(resp, name: str, challenge_b64: str) -> None:
    secure = os.environ.get("CONSOLE_SECURE_COOKIES") == "1"
    resp.set_cookie(name, store.make_challenge_token(challenge_b64),
                    httponly=True, samesite="lax", secure=secure, max_age=300)


@app.post("/app/2fa/webauthn/options")
async def webauthn_register_options(request: Request):
    """Begin passkey enrollment for the signed-in principal: returns creation options
    (JSON for navigator.credentials.create) and stashes the signed challenge in a cookie."""
    acct, redir = _require(request)
    if redir:
        return JSONResponse({"error": "sign in again"}, status_code=401)
    if not webauthn_box.available():
        return JSONResponse({"error": "passkeys unavailable on this server"}, status_code=501)
    mid = acct.get("member_id", 0) or 0
    handle = f"{acct['id']}-{mid}".encode()
    existing = [webauthn_box.base64url_to_bytes(c) for c in store.webauthn_credential_ids(acct["id"], mid)]
    opts_json, challenge = webauthn_box.registration_options(
        handle, acct.get("display_email") or acct["email"], existing)
    resp = Response(opts_json, media_type="application/json")
    _wa_cookie(resp, WA_REG_COOKIE, challenge)
    return resp


@app.post("/app/2fa/webauthn/verify")
async def webauthn_register_verify(request: Request):
    """Finish enrollment: verify the attestation against the stashed challenge, store
    the credential, and mark the principal MFA-enrolled."""
    acct, redir = _require(request)
    if redir:
        return JSONResponse({"error": "sign in again"}, status_code=401)
    if not webauthn_box.available():
        return JSONResponse({"error": "passkeys unavailable"}, status_code=501)
    challenge = store.read_challenge_token(request.cookies.get(WA_REG_COOKIE, ""))
    if not challenge:
        return JSONResponse({"error": "enrollment expired — try again"}, status_code=400)
    body = await request.json()
    label = (str(body.get("label") or "Passkey"))[:80]
    try:
        reg = webauthn_box.verify_registration(json.dumps(body.get("credential") or {}), challenge)
    except Exception:  # noqa: BLE001 — a bad/forged attestation must not 500
        return JSONResponse({"error": "could not verify that passkey"}, status_code=400)
    mid = acct.get("member_id", 0) or 0
    try:
        store.add_webauthn_credential(acct["id"], mid, reg["credential_id"], reg["public_key"],
                                      reg["sign_count"], label)
    except store.StoreError:
        return JSONResponse({"error": "that passkey is already registered"}, status_code=409)
    _audit(acct["id"], "2fa.enable", actor=acct.get("display_email") or acct["email"],
           detail=f"passkey ({label})")
    resp = JSONResponse({"ok": True})
    resp.delete_cookie(WA_REG_COOKIE)
    return resp


@app.post("/app/2fa/webauthn/delete")
async def webauthn_delete(request: Request):
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    mid = acct.get("member_id", 0) or 0
    if store.delete_webauthn_credential(int(f.get("id") or 0), acct["id"], mid):
        _audit(acct["id"], "2fa.disable", actor=acct.get("display_email") or acct["email"],
               detail="passkey removed")
    return _redirect("/app/security")


@app.post("/login/webauthn/options")
async def login_webauthn_options(request: Request):
    """Begin a passkey login for the pending (post-password) principal."""
    pend = store.read_pending_2fa(request.cookies.get(PENDING_2FA_COOKIE, ""))
    if not pend:
        return JSONResponse({"error": "no pending sign-in"}, status_code=400)
    if not webauthn_box.available():
        return JSONResponse({"error": "passkeys unavailable"}, status_code=501)
    aid, mid = pend
    cred_ids = [webauthn_box.base64url_to_bytes(c) for c in store.webauthn_credential_ids(aid, mid)]
    if not cred_ids:
        return JSONResponse({"error": "no passkeys for this account"}, status_code=400)
    opts_json, challenge = webauthn_box.authentication_options(cred_ids)
    resp = Response(opts_json, media_type="application/json")
    _wa_cookie(resp, WA_AUTH_COOKIE, challenge)
    return resp


@app.post("/login/webauthn/verify")
async def login_webauthn_verify(request: Request):
    """Finish a passkey login: verify the assertion, advance the sign counter, issue
    the session. Returns JSON {ok, redirect} (the browser then navigates)."""
    pend = store.read_pending_2fa(request.cookies.get(PENDING_2FA_COOKIE, ""))
    if not pend:
        return JSONResponse({"error": "no pending sign-in"}, status_code=400)
    challenge = store.read_challenge_token(request.cookies.get(WA_AUTH_COOKIE, ""))
    if not challenge:
        return JSONResponse({"error": "sign-in expired — try again"}, status_code=400)
    aid, mid = pend
    body = await request.json()
    cred_json = json.dumps(body.get("credential") or {})
    cred = store.get_webauthn_credential(webauthn_box.credential_id_of(cred_json))
    # The asserted credential MUST belong to the pending principal (no cross-account).
    if not cred or cred["account_id"] != aid or (cred["member_id"] or 0) != (mid or 0):
        return JSONResponse({"error": "unknown passkey"}, status_code=400)
    try:
        new_count = webauthn_box.verify_authentication(cred_json, challenge, cred["public_key"],
                                                       cred["sign_count"])
    except Exception:  # noqa: BLE001 — bad/replayed/cloned assertion
        return JSONResponse({"error": "could not verify that passkey"}, status_code=400)
    store.update_webauthn_sign_count(cred["id"], new_count)
    org = store.get_account(aid)
    if mid:
        member = store.get_member(mid)
        resp = JSONResponse({"ok": True, "redirect": "/app"})
        _set_session(resp, org, member["role"], member["id"], platform_role="customer")
        _audit(aid, "login", actor=member["email"], detail="member · password + passkey")
    else:
        resp = JSONResponse({"ok": True, "redirect": _post_auth_dest(org)})
        _set_session(resp, org, "owner", 0)
        _audit(aid, "login", actor=org["email"], detail="owner · password + passkey")
    resp.delete_cookie(WA_AUTH_COOKIE)
    resp.delete_cookie(PENDING_2FA_COOKIE)
    return resp


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
    # Capture the why (survives deletion — feedback is anonymized, not deleted). Most valuable signal.
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
    kind = f.get("kind")
    if kind in ("idea", "problem", "praise", "other"):
        # Categorized feedback / feature request from the widget; derive a coarse
        # sentiment so it still shows in the thumbs view, and keep the category.
        rating = {"praise": "up", "problem": "down"}.get(kind)
    else:
        kind = "dashboard"
        rating = f.get("rating") if f.get("rating") in ("up", "down") else None
    comment = (f.get("comment") or "").strip() or None
    try:
        store.record_feedback(acct["id"], kind, rating=rating, comment=comment)
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


@app.post("/app/profile")
async def profile_post(request: Request):
    """Update the current principal's display name (owner or member)."""
    acct, redir = _require(request)
    if redir:
        return redir
    f = await _form(request)
    name = (f.get("name", "") or "").strip()[:120]
    mid = acct.get("member_id", 0) or 0
    if mid:
        store.set_member_name(mid, acct["id"], name)
    else:
        store.set_account_name(acct["id"], name)
    _audit(acct["id"], "profile.name", actor=acct.get("display_email"),
           detail="updated display name")
    return _redirect("/app/settings?saved=1#profile")


def _connect_html(acct: dict, new_key: str = ""):
    deps = store.deployments_for(acct["id"])
    brain = os.environ.get("MODELPILOT_BRAIN_URL", "https://brain.modelpilot.app")
    console = os.environ.get("CONSOLE_BASE_URL", "https://app.outlay-ai.com")
    keys = store.list_api_keys(acct["id"])
    hooks = store.list_webhooks(acct["id"])
    deliveries = store.recent_webhook_deliveries(acct["id"])
    return _html(web.connect_page(acct, deps, brain, console, keys, new_key, hooks, deliveries))


def _api_html(acct: dict, new_key: str = ""):
    base = os.environ.get("CONSOLE_BASE_URL", "https://app.outlay-ai.com")
    return _html(web.api_page(acct, store.list_api_keys(acct["id"]),
                              store.deployments_for(acct["id"]), base_url=base, new_key=new_key))


@app.get("/app/api", response_class=HTMLResponse)
def app_api(request: Request):
    """Developer reference for the read-only spend API + exports (owner/admin only)."""
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    return _api_html(acct)


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
    try:
        exp_days = int(f.get("expires_in_days") or 0) or None
    except (TypeError, ValueError):
        exp_days = None
    new_key = ""
    try:
        new_key = store.create_api_key(acct["id"], dep, f.get("name", ""),
                                       expires_in_days=exp_days)["full_key"]
    except store.StoreError:
        pass
    # show the key once (never recoverable), on whichever surface created it
    if f.get("from") == "api":
        return _api_html(acct, new_key)
    return _connect_html(acct, new_key)


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
    return _redirect("/app/api" if f.get("from") == "api" else "/app/connect")


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
                               store.get_sso(acct["id"]), request.query_params.get("scim_token", ""),
                               roster=request.query_params.get("roster", "")))


@app.get("/app/audit", response_class=HTMLResponse)
def app_audit(request: Request):
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    return _html(web.audit_page(acct, store.list_audit(acct["id"])))


@app.post("/app/team/invite")
async def team_invite(request: Request):
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        m = store.create_member(acct["id"], f.get("email", ""), f.get("role", "member"))
    except store.StoreError:
        return _redirect("/app/welcome" if (f.get("next") or "") == "welcome" else "/app/team")
    # Pre-set the invitee's experience so they skip the first-run role gate — for an
    # invited user we already know who they are and which view fits their role.
    persona = (f.get("persona") or "").strip()
    if persona in ("business", "eng"):
        store.set_persona(acct["id"], persona, member_id=m["id"])
    _audit(acct["id"], "member.invite", actor=acct.get("display_email") or acct.get("email", ""),
           detail=f"{m['email']} as {f.get('role', 'member')}" + (f" ({persona})" if persona else ""))
    out = store.create_reset(m["email"])
    token = out[1] if out else ""
    if token:
        try:
            notify.send_email(m["email"], "You're invited to Outlay",
                              f"You've been added to an Outlay team. Set your password:\n\n"
                              f"{notify.reset_link(token)}")
        except Exception:  # noqa: BLE001
            pass
    if (f.get("next") or "") == "welcome":
        return _redirect("/app/welcome")
    return _redirect(f"/app/team?invite_token={token}")


def _send_invite_email(email: str) -> None:
    """Create a set-password link for an invited member and email it (best-effort)."""
    out = store.create_reset(email)
    token = out[1] if out else ""
    if token:
        try:
            notify.send_email(email, "You're invited to Outlay",
                              f"You've been added to an Outlay team. Set your password:\n\n"
                              f"{notify.reset_link(token)}")
        except Exception:  # noqa: BLE001
            pass


_ROSTER_TEMPLATES = {
    "title": ("name,email,job title\n"
              "Jordan Lee,jordan@acme.com,Senior Engineer\n"
              "Priya Shah,priya@acme.com,Staff Engineer\n"
              "Sam Rivera,sam@acme.com,Engineering Manager\n"
              "CI deploy bot,key_ci_deploy,Service account\n"),
    "team": ("name,email,team\n"
             "Jordan Lee,jordan@acme.com,Platform\n"
             "Priya Shah,priya@acme.com,Payments\n"
             "CI deploy bot,key_ci_deploy,Platform\n"),
}


@app.get("/app/team/roster-template.csv")
def team_roster_template(request: Request):
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    kind = "title" if request.query_params.get("third") == "title" else "team"
    return Response(_ROSTER_TEMPLATES[kind], media_type="text/csv",
                    headers={"Content-Disposition": 'attachment; filename="outlay-org-template.csv"'})


@app.post("/app/team/roster")
async def team_roster(request: Request):
    """Build the people directory from a CSV: name each person (for usage-by-person)
    plus a third detail — a job title (engineering 'direct reports') or a team (cost
    allocation), per the form's `third` field. Columns (header row, any order):
    name, email, and team|job title. Does NOT invite (that's one click per tile)."""
    import csv as _csv
    import io as _io
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    fields, filetext = await _multipart(request)
    nxt = (fields.get("next") or "")
    third_kind = "title" if (fields.get("third") or "").lower() == "title" else "team"
    map_lines: list[str] = []
    names: dict[str, str] = {}
    titles: dict[str, str] = {}
    if filetext:
        rows = [r for r in _csv.reader(_io.StringIO(filetext)) if any(c.strip() for c in r)]
        col = {"name": 0, "email": 1, "third": 2}
        if rows:
            header = [c.strip().lower() for c in rows[0]]
            if any(h in ("name", "email", "identifier", "team", "job title", "title", "role",
                         "department") for h in header):
                col = {}
                for i, h in enumerate(header):
                    if h in ("name", "person", "full name"):
                        col["name"] = i
                    elif h in ("email", "identifier"):
                        col["email"] = i
                    elif h in ("team", "job title", "title", "role", "department"):
                        col["third"] = i
                rows = rows[1:]
        for r in rows:
            def cell(key: str) -> str:
                i = col.get(key)
                return r[i].strip() if i is not None and i < len(r) else ""
            name = cell("name")
            # The "email" column holds the identity we attribute spend to: a person's
            # email, or a service-account / CI key id. Name is display-only.
            ident = cell("email").strip().lower()
            third = cell("third")
            if not ident:
                continue
            if name:
                names[ident] = name
            if third:
                if third_kind == "title":
                    titles[ident] = third
                else:
                    map_lines.append(f"{ident}, {third}")
    if names:
        store.set_outlay_identity_names(acct["id"], names)
    if titles:
        store.set_outlay_identity_titles(acct["id"], titles)
    if map_lines:
        merged = _merge_identity_csv(store.get_outlay_identity_map(acct["id"]) or "",
                                     "\n".join(map_lines))
        store.set_outlay_identity_map(acct["id"], merged or None)
    _audit(acct["id"], "team.roster", actor=acct.get("display_email") or acct.get("email", ""),
           detail=f"named={len(names)} titled={len(titles)} mapped={len(map_lines)}")
    summary = (f"Directory updated — {len(names)} people named"
               + (f", {len(titles)} with a job title" if titles else "")
               + (f", {len(map_lines)} mapped to teams" if map_lines else "")
               + ". Invite anyone with one click below.")
    if nxt == "welcome":
        return _redirect("/app/welcome")
    return _redirect(f"/app/team?roster={quote(summary)}")


@app.post("/app/team/invite-all")
async def team_invite_all(request: Request):
    """Invite every person in the directory who has an email and isn't on the team
    yet — the bulk companion to the per-tile Invite button. Owner/admin-only."""
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    f = await _form(request)
    owner_email = (acct["email"] or "").strip().lower()
    existing = {(m["email"] or "").strip().lower() for m in store.list_members(acct["id"])}
    invited = 0
    for ident in store.get_outlay_identity_names(acct["id"]):
        ident = ident.strip().lower()
        if "@" not in ident or ident.startswith("@") or ident == owner_email or ident in existing:
            continue
        try:
            store.create_member(acct["id"], ident, "member")
        except store.StoreError:
            continue
        _send_invite_email(ident)
        invited += 1
    _audit(acct["id"], "team.invite_all", actor=acct.get("display_email") or acct.get("email", ""),
           detail=f"invited={invited}")
    if (f.get("next") or "") == "welcome":
        return _redirect("/app/welcome")
    return _redirect(f"/app/team?roster={quote(f'Invited {invited} people from your org directory.')}")


@app.post("/app/team/role")
async def team_role(request: Request):
    acct, redir = _require_team_admin(request)
    if redir:
        return redir
    f = await _form(request)
    try:
        store.set_member_role(int(f.get("member_id", "0")), acct["id"], f.get("role", "member"))
        _audit(acct["id"], "member.role", actor=acct.get("display_email") or acct.get("email", ""),
               detail=f"member #{f.get('member_id')} -> {f.get('role', 'member')}")
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
        _audit(acct["id"], "member.remove", actor=acct.get("display_email") or acct.get("email", ""),
               detail=f"member #{f.get('member_id')}")
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
                                    funnel=store.activation_funnel(), feedback=store.list_feedback(30),
                                    fleet_cost=store.fleet_cost_to_serve()))


@app.get("/admin/proposals", response_class=HTMLResponse)
def admin_proposals(request: Request):
    acct, redir = _require_admin(request)
    if redir:
        return redir
    pending = store.list_proposals(status="pending")
    emails = {a["id"]: a["email"] for a in store.list_accounts()}
    return _html(web.admin_proposals_queue(acct, pending, emails))


@app.get("/admin/health", response_class=HTMLResponse)
def admin_health(request: Request):
    """Operator view of scheduled-job freshness — so a missing/broken cron
    scheduler is visible instead of silently skipping the daily sweeps."""
    acct, redir = _require_admin(request)
    if redir:
        return redir
    return _html(web.admin_health_page(acct, store.cron_health(), store.get_cron_runs(),
                                       storage=store.outlay_report_storage_stats()))


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
    n_active = max(1, sum(1 for a in store.list_accounts() if a["status"] != "suspended"))
    cost = cost_to_serve.estimate(store.account_cost_drivers(account_id), active_accounts=n_active)
    return _html(web.admin_account_detail(acct, target, plan, trial, settings, bill, cats,
                                          _suggestions(cats, settings), reset_link, proposals, history,
                                          cost=cost))


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
    reason = store.forbidden_payload_reason(body)
    if reason:
        return JSONResponse({"error": f"payload rejected: {reason}"}, status_code=422)
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
    reason = store.forbidden_payload_reason(body)
    if reason:
        return JSONResponse({"error": f"payload rejected: {reason}"}, status_code=422)
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
    # forbidden key NAMES or credential-looking VALUES at any depth (batch + rows)
    reason = store.forbidden_payload_reason(body)
    if reason:
        return JSONResponse({"error": f"payload rejected: {reason}"}, status_code=422)
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
    resp = _redirect("/app")
    _set_session(resp, org, member["role"], member["id"], platform_role="customer")
    _audit(account_id, "login", actor=email, detail=f"SSO · role {member['role']}")
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
    # `ok` reflects app liveness. `cron` exposes per-job freshness so an external
    # monitor can alert when the scheduler stops driving the sweeps; `cron_ok` is a
    # single rollup (False if any expected job is overdue/never-run).
    try:
        cron = store.cron_health()
    except Exception:  # noqa: BLE001 — health must never throw
        cron = {}
    try:
        storage = store.outlay_report_storage_stats()
    except Exception:  # noqa: BLE001 — health must never throw
        storage = {}
    return {"ok": True, "stripe": stripe_billing.enabled(),
            "cron_ok": all(not c["stale"] for c in cron.values()) if cron else True,
            "cron": cron,
            "storage_ok": not storage.get("over_soft_limit", False),
            "report_max_bytes": storage.get("max_bytes", 0)}


def main():
    import uvicorn
    port = int(os.environ.get("CONSOLE_PORT", "8700"))
    store.init_db()
    print(f"Outlay console on http://127.0.0.1:{port} "
          f"(stripe: {'on' if stripe_billing.enabled() else 'off'})")
    uvicorn.run("console.server:app", host="0.0.0.0", port=port, log_level="warning")


if __name__ == "__main__":
    main()
