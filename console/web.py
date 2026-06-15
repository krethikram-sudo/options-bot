"""ModelPilot console — HTML rendering (server-side, dependency-free).

One small design system (shared CSS) + a function per page. Server-rendered so
the whole console deploys as a single FastAPI service with no build step,
consistent with the existing dashboard/ingest pages.
"""

import html
import os
import time
from datetime import datetime, timezone

from . import store

ACCENT = "#111111"
BRAND = "ModelPilot"

_CSS = """
:root{--accent:#7c3aed;--accent-d:#8b5cf6;--ink:#f4f5f7;--muted:#8b97ad;
  --line:#26262b;--bg:#0a0a0a;--card:#141416;--warn:#fbbf24;--bad:#f87171;
  --vio:#7c3aed;--blue:#2563eb;--grad:linear-gradient(135deg,#7c3aed,#2563eb);
  --disp:"Space Grotesk",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --ease:cubic-bezier(.22,.61,.36,1);}
*{box-sizing:border-box}
body{margin:0;font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  color:var(--ink);-webkit-font-smoothing:antialiased;background:
    radial-gradient(900px 500px at 85% -8%,rgba(124,58,237,.16),transparent 60%),
    radial-gradient(760px 460px at 4% 0%,rgba(37,99,235,.12),transparent 55%),
    var(--bg);background-attachment:fixed}
a{color:var(--accent-d);text-decoration:none}a:hover{text-decoration:underline}
.top{background:rgba(10,10,12,.7);backdrop-filter:blur(10px);border-bottom:1px solid var(--line);position:sticky;top:0;z-index:10}
.top .wrap{max-width:1080px;margin:0 auto;padding:12px 20px;display:flex;align-items:center;gap:18px}
/* left sidebar shell (signed-in) */
.shell{display:flex;min-height:100vh;align-items:stretch}
.side{width:236px;flex-shrink:0;display:flex;flex-direction:column;padding:18px 14px;
  border-right:1px solid var(--line);background:rgba(12,12,15,.55);backdrop-filter:blur(10px);
  position:sticky;top:0;height:100vh}
.side .brand{padding:6px 10px 2px;font-size:19px}
.sidenav{display:flex;flex-direction:column;gap:2px;margin-top:18px}
.sidenav a{color:var(--muted);padding:9px 12px;border-radius:8px;font-weight:500;font-size:14.5px;
  transition:background .15s,color .15s}
.sidenav a:hover{color:var(--ink);background:rgba(255,255,255,.05);text-decoration:none}
.sidenav a.on{color:#fff;background:rgba(124,58,237,.18)}
.navgrp{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--muted);margin:18px 0 6px 12px}
.side-foot{margin-top:auto;padding-top:14px;border-top:1px solid var(--line)}
.side-foot .email{color:var(--muted);font-size:13px;margin-bottom:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.trialpill{display:block;text-align:center;margin-bottom:12px;padding:8px 10px;border-radius:8px;font-size:12.5px;font-weight:600;
  background:rgba(124,58,237,.16);color:#cbb8ff;border:1px solid rgba(124,58,237,.3)}
.trialpill:hover{text-decoration:none;background:rgba(124,58,237,.26)}
.trialpill.warn{background:rgba(251,191,36,.14);color:#fcd34d;border-color:rgba(251,191,36,.32)}
.trialpill.bad{background:rgba(248,113,113,.14);color:#fca5a5;border-color:rgba(248,113,113,.36)}
.main{flex:1;min-width:0}
.inner{max-width:1040px;margin:0 auto;padding:30px 30px 64px}
@media(max-width:820px){
  .shell{flex-direction:column}
  .side{width:auto;height:auto;position:static;flex-direction:row;align-items:center;flex-wrap:wrap;gap:4px;border-right:0;border-bottom:1px solid var(--line)}
  .side .brand{padding:6px 10px}
  .sidenav{flex-direction:row;flex-wrap:wrap;margin:0 0 0 8px;flex:1}
  .navgrp{display:none}
  .side-foot{margin:0 0 0 auto;border:0;padding:0}.side-foot .email{display:none}
  .inner{padding:20px}}
.brand{font-family:var(--disp);font-weight:700;font-size:18px;color:var(--ink);letter-spacing:-.03em}
.brand .dot{color:var(--vio)}
.nav{display:flex;gap:16px;margin-left:8px;flex-wrap:wrap}
.nav a{color:var(--muted);font-weight:500;transition:color .15s}.nav a.on,.nav a:hover{color:var(--ink)}
.spacer{flex:1}
.wrap{max-width:1080px;margin:0 auto;padding:24px 20px}
.muted{color:var(--muted)}.small{font-size:13px}
h1,h2{font-family:var(--disp);letter-spacing:-.02em;color:var(--ink)}
h1{font-size:25px;margin:0 0 4px}h2{font-size:17px;margin:24px 0 12px}
.grid{display:grid;gap:16px}
.cols-3{grid-template-columns:repeat(3,1fr)}.cols-2{grid-template-columns:repeat(2,1fr)}
@media(max-width:760px){.cols-3,.cols-2{grid-template-columns:1fr}}
/* light cards float on the dark canvas: redefine the color vars so every nested
   component inherits light-surface colors automatically */
.card{--ink:#101014;--muted:#6b6b72;--line:#ececef;
  background:#fff;border:1px solid #ececef;border-radius:12px;padding:18px;color:var(--ink);
  box-shadow:0 14px 34px -24px rgba(0,0,0,.7);
  transition:transform .25s var(--ease),box-shadow .25s ease}
.card:hover{transform:translateY(-2px);box-shadow:0 22px 46px -26px rgba(0,0,0,.78)}
.stat{font-family:var(--disp);font-size:30px;font-weight:700;letter-spacing:-.02em;color:var(--ink)}
.stat.green{background:var(--grad);-webkit-background-clip:text;background-clip:text;color:transparent}
.label{font-family:var(--mono);font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:500}
.btn{display:inline-block;background:var(--accent);color:#fff;border:0;border-radius:8px;
  padding:10px 16px;font-size:14px;font-weight:600;cursor:pointer;
  transition:transform .15s var(--ease),background .15s,box-shadow .2s}
.btn:hover{background:var(--accent-d);text-decoration:none;transform:translateY(-1px);box-shadow:0 12px 24px -12px rgba(124,58,237,.6)}
.btn.sec{background:transparent;color:var(--ink);border:1px solid var(--line)}
.btn.sec:hover{background:rgba(255,255,255,.05);box-shadow:none;transform:none}
.btn.bad{background:#b91c1c;color:#fff}.btn.bad:hover{background:#991b1b}.btn.sm{padding:6px 10px;font-size:13px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line)}
th{font-family:var(--mono);font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
tr:hover td{background:rgba(124,58,237,.06)}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.badge.trial{background:#26262b;color:#c2cbdb}.badge.paid{background:var(--vio);color:#fff}
.badge.suspended{background:#3a1a1a;color:#fca5a5}.badge.admin{background:#1e1b3a;color:#c4b5fd}
.badge.off{background:#1e2433;color:#8b97ad}
.bar{height:10px;background:#ececf0;border-radius:6px;overflow:hidden}
.bar>span{display:block;height:100%;background:var(--grad)}
.field{margin:14px 0}.field label{display:block;font-weight:600;margin-bottom:6px}
.field input,.field select{width:100%;padding:10px;border:1px solid var(--line);border-radius:8px;font-size:14px;
  background:#fff;color:var(--ink)}
.field input:focus,.field select:focus{outline:none;border-color:var(--vio);box-shadow:0 0 0 3px rgba(124,58,237,.15)}
.note{background:#15151f;border:1px solid #2a2a3a;color:#d7def0;padding:10px 14px;border-radius:8px;margin:12px 0}
.note.warn{background:#241d10;border-color:#5a4416;color:#fcd34d}
.note.bad{background:#241313;border-color:#5a1f1f;color:#fca5a5}
.modes{display:flex;gap:8px;flex-wrap:wrap}
.modes button{flex:1;min-width:150px;text-align:left;padding:14px;border:2px solid var(--line);
  border-radius:10px;background:#f7f7f8;cursor:pointer;color:var(--ink);transition:border-color .2s,background .2s,transform .2s var(--ease)}
.modes button:hover{transform:translateY(-1px)}
.modes button.on{border-color:var(--vio);background:#f3effe}
.modes b{display:block;font-size:15px}.modes .small{color:var(--muted)}
code{background:#0d0d10;color:#cdd6e6;padding:2px 6px;border-radius:5px;font-size:13px;border:1px solid #26262b}
pre{background:#0d0d10;color:#cdd6e6;padding:16px;border-radius:10px;overflow:auto;font-size:13px;line-height:1.6;border:1px solid #26262b}
.auth{max-width:400px;margin:48px auto}
.center{text-align:center}
.hero{max-width:640px;margin:56px auto;text-align:center}
.hero h1{font-size:40px;letter-spacing:-.035em;line-height:1.05}
.row{display:flex;gap:10px;align-items:center;flex-wrap:wrap}
/* staggered entrance on every page (--rd set per element by JS) */
.reveal{opacity:0;transform:translateY(14px);transition:opacity .55s var(--ease),transform .55s var(--ease);transition-delay:var(--rd,0ms)}
.reveal.in{opacity:1;transform:none}
@media(prefers-reduced-motion:reduce){.reveal{opacity:1;transform:none;transition:none}.card:hover,.modes button:hover{transform:none}}
"""


def _e(s) -> str:
    return html.escape(str(s if s is not None else ""))


def money(x) -> str:
    try:
        return "${:,.2f}".format(float(x or 0))
    except (TypeError, ValueError):
        return "$0.00"


# "Equivalent tokens saved": express dollar savings as the number of top-model
# (Claude Opus 4.8) tokens that money would have bought. Opus 4.8 is ~$5/1M in,
# $25/1M out; we use the ~$15/1M blended midpoint. This is an APPROXIMATE,
# clearly-labeled framing of the same dollar savings — routing re-prices the same
# tokens, so this is "what your savings are worth in premium tokens," not tokens
# literally avoided.
_OPUS_BLENDED_PER_1M = 15.0


def equiv_tokens(dollars) -> float:
    try:
        d = float(dollars or 0)
    except (TypeError, ValueError):
        return 0.0
    return (d / _OPUS_BLENDED_PER_1M) * 1_000_000 if d > 0 else 0.0


def fmt_tokens(n) -> str:
    """Compact token count: 2.1M, 840K, 512."""
    try:
        n = float(n or 0)
    except (TypeError, ValueError):
        n = 0.0
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.0f}K"
    return f"{int(n)}"


# --- $ / tokens-saved view toggle (shared by the customer + admin dashboards) ---
_TOK_TIP = ("Approx. Claude Opus 4.8 tokens your savings would buy (~$15/1M blended). "
            "Same dollars shown as premium-token equivalents — routing re-prices the same "
            "tokens, so this is what the savings are worth, not tokens literally avoided.")


def metric_toggle_control() -> str:
    """The $ / Tokens segmented toggle (place in a page header)."""
    return (f'<div class="metric-toggle" title="{_TOK_TIP}">'
            '<button type=button class="seg on" data-metric="usd">$ saved</button>'
            '<button type=button class="seg" data-metric="tok">Tokens saved</button></div>')


def dual_metric(dollars, suffix="tok-eq") -> str:
    """A savings value rendered both as $ and as equivalent tokens; the toggle
    shows one or the other client-side. Pass suffix="" for compact table cells."""
    suf = f'<span class="small muted"> {suffix}</span>' if suffix else ""
    return (f'<span class=m-usd>{money(dollars)}</span>'
            f'<span class=m-tok style="display:none" title="{_TOK_TIP}">'
            f'{fmt_tokens(equiv_tokens(dollars))}{suf}</span>')


def metric_toggle_assets() -> str:
    """CSS + JS for the toggle (include once per page that uses it). Persists the
    choice in localStorage so it sticks across the customer + admin dashboards."""
    return """
    <style>
      .metric-toggle{display:inline-flex;border:1px solid var(--line);border-radius:8px;overflow:hidden;margin-right:10px}
      .metric-toggle .seg{background:transparent;border:0;padding:6px 12px;font:inherit;cursor:pointer;color:var(--muted)}
      .metric-toggle .seg.on{background:var(--vio);color:#fff}
    </style>
    <script>
      (function(){
        function apply(m){
          document.querySelectorAll('.m-usd').forEach(function(e){e.style.display=(m==='tok')?'none':'';});
          document.querySelectorAll('.m-tok').forEach(function(e){e.style.display=(m==='tok')?'':'none';});
          document.querySelectorAll('.metric-toggle .seg').forEach(function(b){b.classList.toggle('on',b.dataset.metric===m);});
        }
        var m=localStorage.getItem('mp_metric')||'usd';
        apply(m);
        document.querySelectorAll('.metric-toggle .seg').forEach(function(b){
          b.addEventListener('click',function(){var x=this.dataset.metric;localStorage.setItem('mp_metric',x);apply(x);});
        });
      })();
    </script>"""


def _fmt_date(ts) -> str:
    if not ts:
        return "—"
    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%b %-d, %Y")


def page(title: str, body: str, account: dict | None = None, active: str = "") -> str:
    if account:
        # Customer-first: a few clear destinations. Logs live inside Home,
        # Team/SSO inside Settings — reached contextually, not as top-level tabs.
        items = [("/app", "Home"), ("/app/connect", "Configuration"),
                 ("/app/settings", "Settings"), ("/app/billing", "Billing")]
        links = "".join(f'<a class="{"on" if active == href else ""}" href="{href}">{_e(label)}</a>'
                        for href, label in items)
        admin = ""
        if account.get("role") == "admin":
            admin = ('<div class=navgrp>Vendor</div>'
                     f'<a class="{"on" if active == "/admin" else ""}" href="/admin">Overview</a>'
                     f'<a class="{"on" if active == "/admin/proposals" else ""}" href="/admin/proposals">Review</a>')
        em = _e(account.get("display_email") or account["email"])
        chrome = (
            '<div class=shell><aside class=side>'
            '<a class=brand href="/app">Model<span class=dot>Pilot</span></a>'
            f'<nav class=sidenav>{links}{admin}</nav>'
            f'<div class=side-foot>{_trial_pill(account)}<div class=email>{em}</div>'
            '<form method=post action="/logout" style="margin:0">'
            '<button class="btn sec sm" style="width:100%">Sign out</button></form></div>'
            f'</aside><main class=main><div class=inner>{_account_trial_banner(account)}{body}</div></main></div>')
    else:
        nav = ('<div class="spacer"></div><div class="nav">'
               '<a href="/login">Sign in</a><a class="btn sm" href="/signup">Start free trial</a></div>')
        chrome = (
            '<div class=top><div class=wrap style="padding-top:12px;padding-bottom:12px">'
            f'<a class=brand href="/">Model<span class=dot>Pilot</span></a>{nav}'
            f'</div></div><div class=wrap>{body}</div>')
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<title>{_e(title)} · {BRAND}</title><style>{_CSS}</style></head><body>
{chrome}
<script>(function(){{var d=document;
if(!('IntersectionObserver' in window)||(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches))return;
var els=[].slice.call(d.querySelectorAll('.card,.hero'));
els.forEach(function(c,i){{c.classList.add('reveal');c.style.setProperty('--rd',Math.min(i*55,330)+'ms');}});
var io=new IntersectionObserver(function(es){{es.forEach(function(e){{if(e.isIntersecting){{e.target.classList.add('in');io.unobserve(e.target);}}}});}},{{threshold:.06}});
els.forEach(function(c){{io.observe(c);}});}})();</script>
</body></html>"""


# --------------------------------------------------------------------------- #
# Auth / public
# --------------------------------------------------------------------------- #

def status_page(components: list[dict]) -> str:
    all_ok = all(c["ok"] for c in components)
    banner = ('<div class="note">All systems operational.</div>' if all_ok else
              '<div class="note bad">Some systems are degraded — see below.</div>')
    rows = ""
    for c in components:
        dot = ("●" )
        color = "#16803d" if c["ok"] else "var(--bad)"
        color = "#111" if c["ok"] else "var(--bad)"
        state = "Operational" if c["ok"] else "Unreachable"
        rows += (f'<tr><td><span style="color:{color};font-weight:700">{dot}</span> {_e(c["name"])}</td>'
                 f'<td>{_e(state)}</td><td class="small muted">{_e(c.get("detail",""))}</td></tr>')
    body = f"""
    <h1>System status</h1>
    <p class=muted>Live health of ModelPilot services. Your gateway always
    <b>fails open</b> — if a service is unreachable, traffic passes straight through to the
    Claude API, unrouted.</p>
    {banner}
    <div class=card style="padding:0"><table>
      <thead><tr><th>Component</th><th>Status</th><th></th></tr></thead>
      <tbody>{rows}</tbody></table></div>
    <p class="small muted" style="margin-top:14px">Checked just now. For incident history or an
    SLA, contact <a href="mailto:krethikram@gmail.com">krethikram@gmail.com</a>.</p>"""
    return page("Status", body)


def landing() -> str:
    body = f"""
    <div class=hero>
      <h1>Cut your Claude bill through model optimization.</h1>
      <p class=muted>ModelPilot routes each request to the cheapest model that's provably
      good enough. Drop-in proxy, no prompt data leaves your box. Start free for 7 days;
      after that you only pay <b>20% of the savings we actually deliver</b>.</p>
      <div class="row center" style="justify-content:center;margin-top:18px">
        <a class=btn href="/signup">Start your 7-day free trial</a>
        <a class="btn sec" href="/login">Sign in</a>
      </div>
      <p class="small muted" style="margin-top:24px">No savings, no bill. Cancel anytime.</p>
    </div>"""
    return page("Cut your Claude bill", body)


def twofa_verify_form(error: str = "", note: str = "") -> str:
    err = f'<div class="note bad">{_e(error)}</div>' if error else ""
    nt = f'<div class="note">{_e(note)}</div>' if note else ""
    body = f"""
    <div class=auth><div class=card>
      <h1>Verify it's you</h1>
      <p class=muted small>Enter the 6-digit code we just sent you. It expires in 10 minutes.</p>
      {err}{nt}
      <form method=post action="/login/verify">
        <div class=field><label>Verification code</label>
          <input name=code inputmode=numeric autocomplete=one-time-code pattern="[0-9]*" maxlength=6
            required placeholder="123456" style="letter-spacing:4px;font-size:18px"></div>
        <button class="btn" style="width:100%">Verify &amp; sign in</button>
      </form>
      <form method=post action="/login/verify/resend" style="margin-top:10px">
        <button class="btn sec sm" style="width:100%">Resend code</button></form>
    </div></div>"""
    return page("Verify", body)


def _twofa_section(account: dict, state: str = "") -> str:
    tf = store.get_2fa(account["id"])
    note = ""
    if state == "on":
        note = '<div class="note">Two-factor authentication is on.</div>'
    elif state == "off":
        note = '<div class="note">Two-factor authentication turned off.</div>'
    elif state == "bad":
        note = '<div class="note bad">That code was wrong or expired — start again.</div>'
    if tf["enabled"]:
        inner = (f'<p class="small muted">On — a one-time code is sent to <b>{_e(tf["dest"])}</b> '
                 f'({_e(tf["channel"])}) at each sign-in.</p>'
                 '<form method=post action="/app/2fa/disable">'
                 '<button class="btn sec sm">Turn off 2FA</button></form>')
    elif state == "verify":
        inner = ('<p class="small muted">We emailed you a 6-digit code — enter it to finish enabling 2FA.</p>'
                 '<form method=post action="/app/2fa/confirm" class=row style="gap:8px">'
                 '<input name=code inputmode=numeric pattern="[0-9]*" maxlength=6 required '
                 'placeholder="123456" style="max-width:150px;letter-spacing:3px">'
                 '<button class=btn>Confirm &amp; enable</button></form>')
    else:
        inner = ('<p class="small muted">Require a one-time code at sign-in (emailed to you). '
                 'Strongly recommended for account security.</p>'
                 '<form method=post action="/app/2fa/start"><button class=btn>Enable email 2FA</button></form>')
    return (f'<div class=card style="margin-top:16px"><div class=label>Two-factor authentication</div>'
            f'{note}{inner}</div>')


def auth_form(kind: str, error: str = "", email: str = "") -> str:
    is_signup = kind == "signup"
    title = "Start your free trial" if is_signup else "Sign in"
    err = f'<div class="note bad">{_e(error)}</div>' if error else ""
    company = ('<div class=field><label>Company <span class=muted>(optional)</span></label>'
               '<input name=company placeholder="Acme Inc."></div>') if is_signup else ""
    consent = ('<div class=field><label class=row style="gap:8px;font-weight:400;font-size:13px">'
               '<input type=checkbox name=accept value=1 required style="width:auto"> '
               'I agree to the <a href="https://modelpilot.pages.dev/legal/terms.html" target=_blank>Terms</a>'
               ' and <a href="https://modelpilot.pages.dev/legal/privacy.html" target=_blank>Privacy Policy</a>.'
               '</label></div>') if is_signup else ""
    beta = ('<p class="small muted center" style="margin-top:10px">ModelPilot is in early access — '
            'we move fast and value your feedback.</p>') if is_signup else ""
    sub = "Create account" if is_signup else "Sign in"
    alt = ('Already have an account? <a href="/login">Sign in</a>' if is_signup
           else 'New here? <a href="/signup">Start a free trial</a> · '
                '<a href="/forgot">Forgot password?</a>')
    body = f"""
    <div class=auth><div class=card>
      <h1>{_e(title)}</h1>
      <p class=muted small>{'7 days free · full features · no card required to start.' if is_signup else 'Welcome back.'}</p>
      {err}
      <form method=post action="/{kind}">
        <div class=field><label>Work email</label>
          <input name=email type=email required value="{_e(email)}" placeholder="you@company.com"></div>
        {company}
        <div class=field><label>Password</label>
          <input name=password type=password required minlength=8 placeholder="At least 8 characters"></div>
        {consent}
        <button class="btn" style="width:100%">{_e(sub)}</button>
      </form>
      {beta}
      <p class="small center muted" style="margin-top:14px">{alt}</p>
    </div></div>"""
    return page(title, body)


# --------------------------------------------------------------------------- #
# Customer dashboard
# --------------------------------------------------------------------------- #

def _trial_banner(plan: dict, trial: dict) -> str:
    if plan.get("plan") == "paid":
        return ""
    if trial["active"]:
        d = trial["days_left"]
        if d <= 2:
            return (f'<div class="note warn">⏳ Only <b>{d} day{"" if d == 1 else "s"} left</b> in your free '
                    f'trial. <a href="/app/billing">Activate billing</a> now to keep your savings — you only '
                    f'pay 20% of what we save you.</div>')
        return (f'<div class="note">You\'re on the free trial — <b>{d} days left</b>. '
                f'<a href="/app/billing">Add billing</a> to keep optimizing after that '
                f'(you only pay 20% of what we save you).</div>')
    return ('<div class="note bad">Your free trial has ended — optimization is <b>paused</b> and your traffic '
            'is passing through unrouted. <a href="/app/billing">Activate billing</a> to resume saving.</div>')


def _trial_meta(account: dict | None):
    """(plan, trial) for an account; (None, None) for vendor admins / on error."""
    if not account or account.get("role") == "admin":
        return None, None
    try:
        return store.get_plan(account["id"]), store.trial_status(account["id"])
    except Exception:  # noqa: BLE001
        return None, None


def _account_trial_banner(account: dict | None) -> str:
    plan, trial = _trial_meta(account)
    return _trial_banner(plan, trial) if plan else ""


def _trial_pill(account: dict | None) -> str:
    plan, trial = _trial_meta(account)
    if not plan or plan.get("plan") == "paid":
        return ""
    if trial["active"]:
        d = trial["days_left"]
        cls = "warn" if d <= 2 else ""
        return f'<a class="trialpill {cls}" href="/app/billing">Trial · {d} day{"" if d == 1 else "s"} left</a>'
    return '<a class="trialpill bad" href="/app/billing">Trial ended · reactivate</a>'


def _budget_card(budget: dict | None) -> str:
    if not budget or not budget.get("enabled"):
        return ""
    pct = min(100, 100 * budget["pct"])
    color = "#dc2626" if budget["over"] else ("#b45309" if budget["warn"] else "var(--accent)")
    state = ("Over budget" if budget["over"] else
             ("Near budget" if budget["warn"] else "Within budget"))
    return f"""<div class=card><div class=label>Spend budget (this cycle)</div>
      <div class=row style="margin:6px 0"><div class=stat style="font-size:22px">{money(budget['spend'])}</div>
        <span class=muted style="margin-left:6px">/ {money(budget['budget'])}</span>
        <div class=spacer></div><span class="small" style="color:{color};font-weight:600">{state}</span></div>
      <div class=bar><span style="width:{pct:.0f}%;background:{color}"></span></div>
      <p class="small muted" style="margin-top:8px">Alerts at {int(budget['alert_pct']*100)}%. Adjust in
      <a href="/app/settings">Settings</a>.</p></div>"""


def dashboard(account: dict, plan: dict, trial: dict, settings: dict,
              cycle: dict, lifetime: dict, bill: dict, deployment: dict,
              cats: list[dict], proof: dict, budget: dict | None = None) -> str:
    mode = settings["mode"]
    mode_badge = {"autopilot": "paid", "guidance": "trial"}.get(mode, "trial")
    routed_pct = (100 * cycle["routed"] / cycle["requests"]) if cycle["requests"] else 0
    # % bill reduction — the early-confidence metric (meaningful even when $ is tiny)
    pct_cycle = round(100 * cycle["savings"] / cycle["baseline"]) if cycle.get("baseline") else 0
    pct_life = round(100 * lifetime["savings"] / lifetime["baseline"]) if lifetime.get("baseline") else 0
    body = f"""
    <div class=row><h1>Dashboard</h1><div class=spacer></div>
      {metric_toggle_control()}
      <span class="badge {mode_badge}">{_e(mode)} mode</span></div>
    <p class=muted>Savings delivered this billing cycle (since {_fmt_date(bill['cycle_start'])}).</p>
    <div class="grid cols-3">
      <div class=card><div class=label>Bill cut this cycle</div>
        <div class="stat green">{pct_cycle}%</div>
        <div class="small muted">{dual_metric(cycle['savings'], suffix="")} saved · {int(cycle['requests']):,} req · {int(cycle['routed']):,} routed</div></div>
      <div class=card><div class=label>{'Your bill this cycle' if bill['is_paid'] else 'Projected bill (free during trial)'}</div>
        <div class=stat>{money(bill['would_bill'])}</div>
        <div class="small muted">{int(bill['rate']*100)}% of savings · you keep {money(bill['cycle_savings']-bill['would_bill'])}</div></div>
      <div class=card><div class=label>Lifetime bill cut</div>
        <div class="stat green">{pct_life}%</div>
        <div class="small muted">{dual_metric(lifetime['savings'], suffix="")} saved · {int(lifetime['requests']):,} requests</div></div>
    </div>

    <h2>Routing mode</h2>
    <div class=card>{mode_toggle(mode)}
      <p class="small muted" style="margin-top:10px">Guidance recommends switches without changing traffic;
      autopilot applies them automatically. Change takes effect on your gateway within seconds.</p>
    </div>

    <div class="grid cols-2" style="margin-top:16px">
      <div class=card><div class=label>Baseline vs. actual (this cycle)</div>
        {_compare_bars(cycle['baseline'], cycle['actual'])}</div>
      {_proof_card(proof)}
    </div>
    {(' <div style="margin-top:16px">' + _budget_card(budget) + '</div>') if (budget and budget.get('enabled')) else ''}

    <h2>Savings by task type <span class="small muted">— where the money comes from</span></h2>
    {_category_savings(cats)}

    <div class=card style="margin-top:16px"><div class=label>Your connection</div>
      <p class="small muted">Point your gateway at ModelPilot with this deployment id:</p>
      <p><code>{_e(deployment['deployment_id'])}</code></p>
      <div class=row><a class="btn sec sm" href="/app/connect">Configuration &amp; deployments</a>
        <a class="btn sec sm" href="/app/logs">View request logs</a></div></div>
    {metric_toggle_assets()}"""
    return page("Home", body, account, "/app")


def _proof_card(proof: dict) -> str:
    comp = proof.get("comparisons") or 0
    rate = proof.get("rate")
    if not comp:
        return ("""<div class=card><div class=label>Quality proof</div>
        <p class="small muted">Run side-by-side checks (<code>modelpilot compare</code>) to populate
        a non-inferiority rate here — proof the cheaper model held up on your own prompts.</p></div>""")
    pct = 100 * rate if rate is not None else 0
    return f"""<div class=card><div class=label>Quality proof (non-inferiority)</div>
      <div class="stat green">{pct:.0f}%</div>
      <div class="small muted">of {int(comp):,} side-by-side comparisons judged non-inferior at the
      cheaper model. Full per-prompt side-by-sides stay on your local gateway dashboard.</div></div>"""


def _category_savings(cats: list[dict]) -> str:
    rows = ""
    for c in cats:
        routed = int(c.get("routed") or 0)
        esc = int(c.get("escalations") or 0)
        esc_rate = (100 * esc / routed) if routed else 0
        rows += (f"<tr><td>{_e(c['category'])}</td><td>{int(c.get('requests') or 0):,}</td>"
                 f"<td>{routed:,}</td><td>{esc_rate:.0f}%</td>"
                 f"<td>{money(c.get('savings'))}</td></tr>")
    if not rows:
        return ('<div class=card class=muted><p class="muted small">No routed traffic yet — '
                'connect your gateway to start seeing savings by task type.</p></div>')
    return (f'<div class=card style="padding:0"><table><thead><tr><th>Task type</th><th>Requests</th>'
            f'<th>Routed</th><th>Escalations</th><th>Savings</th></tr></thead>'
            f'<tbody>{rows}</tbody></table></div>')


def _compare_bars(baseline: float, actual: float) -> str:
    base = max(baseline, actual, 0.0001)
    bw = 100 * baseline / base
    aw = 100 * actual / base
    return f"""
    <div style="margin-top:10px"><div class="row small"><span>Baseline (all top-model)</span>
      <div class=spacer></div><span class=muted>{money(baseline)}</span></div>
      <div class=bar><span style="width:{bw:.0f}%;background:#3a4257"></span></div></div>
    <div style="margin-top:10px"><div class="row small"><span>Actual (with ModelPilot)</span>
      <div class=spacer></div><span class=muted>{money(actual)}</span></div>
      <div class=bar><span style="width:{aw:.0f}%"></span></div></div>"""


def mode_toggle(current: str) -> str:
    opts = [
        ("guidance", "Guidance", "Recommend cheaper models; you stay in control."),
        ("autopilot", "Autopilot", "Auto-route to the cheapest good-enough model."),
    ]
    btns = "".join(
        f'<button name=mode value="{v}" class="{"on" if v==current else ""}">'
        f'<b>{_e(lbl)}</b><span class=small>{_e(desc)}</span></button>'
        for v, lbl, desc in opts)
    return f'<form method=post action="/app/mode"><div class=modes>{btns}</div></form>'


# --------------------------------------------------------------------------- #
# Settings / connect
# --------------------------------------------------------------------------- #

def settings_page(account: dict, settings: dict, saved: bool = False,
                  delete_error: bool = False, twofa: str = "") -> str:
    from .store import RISK_LEVELS
    risk_opts = "".join(
        f'<option value="{r}"{" selected" if settings["risk"]==r else ""}>{r.title()}</option>'
        for r in RISK_LEVELS)
    models = ["", "claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8", "claude-fable-5"]
    model_opts = "".join(
        f'<option value="{m}"{" selected" if settings["min_model"]==m else ""}>'
        f'{m or "No floor (cheapest acceptable)"}</option>' for m in models)
    saved_note = '<div class="note">Settings saved.</div>' if saved else ""
    body = f"""
    <h1>Settings</h1>{saved_note}
    <div class=card>
      <h2 style="margin-top:0">Routing mode</h2>
      {mode_toggle(settings['mode'])}
    </div>
    <div class=card style="margin-top:16px">
      <form method=post action="/app/settings">
        <h2 style="margin-top:0">Routing policy</h2>
        <div class=field><label>Risk tolerance</label>
          <select name=risk>{risk_opts}</select>
          <p class="small muted">Conservative keeps a higher confidence gate; aggressive routes more.</p></div>
        <div class=field><label>Minimum model (quality floor)</label>
          <select name=min_model>{model_opts}</select>
          <p class="small muted">ModelPilot will never route below this model, whatever the classifier says.</p></div>
        <div class=field><label class=row>
          <input type=checkbox name=telemetry_opt_in value=1 {"checked" if settings["telemetry_opt_in"] else ""}
            style="width:auto;margin-right:8px"> Share anonymous, aggregate performance telemetry</label>
          <p class="small muted">Counts and dollars only — never prompt text. Helps us tune routing for your traffic.</p></div>
        <h2>Spend budget</h2>
        <div class=field><label>Monthly spend budget (USD, 0 = no cap)</label>
          <input name=monthly_budget type=number step="0.01" min="0" value="{settings.get('monthly_budget') or 0:g}">
          <p class="small muted">Your model spend through ModelPilot this cycle. We email you when you cross the alert threshold and again if you go over.</p></div>
        <div class=field><label>Alert at (% of budget)</label>
          <input name=budget_alert_pct type=number step="1" min="1" max="100" value="{int((settings.get('budget_alert_pct') or 0.8)*100)}"></div>
        <button class=btn>Save settings</button>
      </form>
    </div>{_settings_links(account)}{_twofa_section(account, twofa)}{_danger_zone(account, delete_error)}"""
    return page("Settings", body, account, "/app/settings")


def _settings_links(account: dict) -> str:
    """Team & access — folded into Settings rather than a top-level tab."""
    if account.get("team_role") not in ("owner", "admin"):
        return ""
    return ('<div class=card style="margin-top:16px"><div class=label>Team &amp; access</div>'
            '<p class="small muted">Invite teammates, manage roles, and configure SSO.</p>'
            '<a class="btn sec sm" href="/app/team">Manage team</a></div>')


def _danger_zone(account: dict, delete_error: bool = False) -> str:
    """Account deletion — owner only. Confirm by typing the account email."""
    if account.get("team_role") != "owner":
        return ""
    email = _e(account.get("email", ""))
    err = ('<div class="note warn">That didn\'t match. Type your account email exactly to confirm.</div>'
           if delete_error else "")
    return f"""
    <div class=card style="margin-top:16px;border:1px solid #e3b3b3">
      <h2 style="margin-top:0">Danger zone</h2>
      <p class="small muted">Permanently delete this account and <b>all</b> its data — deployments,
        API keys, routing history, savings/metering, team members, and settings. This cannot be undone.
        Any active Stripe subscription is cancelled.</p>
      {err}
      <form method=post action="/app/account/delete"
            onsubmit="return confirm('Permanently delete your account and all data? This cannot be undone.')">
        <div class=field><label>Type your email (<b>{email}</b>) to confirm</label>
          <input name=confirm_email type=email autocomplete=off placeholder="{email}" required></div>
        <button class=btn style="background:#b00020;border-color:#b00020">Delete my account</button>
      </form>
    </div>"""


def _api_keys_section(keys: list[dict], deployments: list[dict], new_key: str = "") -> str:
    reveal = ""
    if new_key:
        reveal = (f'<div class="note"><b>Your new API key (shown once — copy it now):</b><br>'
                  f'<code style="word-break:break-all">{_e(new_key)}</code></div>')
    rows = ""
    for k in keys:
        revoked = bool(k.get("revoked_at"))
        status = ('<span class="badge suspended">revoked</span>' if revoked
                  else '<span class="badge paid">active</span>')
        last = _fmt_date(k["last_used_at"]) if k.get("last_used_at") else "never"
        action = ("" if revoked else
                  f'<form method=post action="/app/keys/revoke" style="margin:0">'
                  f'<input type=hidden name=key_id value="{k["id"]}">'
                  f'<button class="btn sec sm">Revoke</button></form>')
        rows += (f"<tr><td>{_e(k.get('name') or 'key')}</td>"
                 f"<td><code>{_e(k['prefix'])}…</code></td><td>{status}</td>"
                 f"<td class='small muted'>{last}</td><td>{action}</td></tr>")
    dep_opts = "".join(f'<option value="{_e(d["deployment_id"])}">{_e(d.get("label") or d["deployment_id"])}</option>'
                       for d in deployments)
    table = (f'<div class=card style="padding:0"><table><thead><tr><th>Name</th><th>Key</th>'
             f'<th>Status</th><th>Last used</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>'
             if rows else '<div class=card><p class="small muted">No API keys yet.</p></div>')
    return f"""
    <h2>API keys</h2>
    <p class="small muted">Authenticate your gateway with a named key instead of the raw deployment id.
    Keys are shown once, hashed at rest, and revocable. Send as <code>Authorization: Bearer &lt;key&gt;</code>
    (or <code>MODELPILOT_API_KEY</code>).</p>
    {reveal}
    {table}
    <div class=card style="margin-top:12px">
      <form method=post action="/app/keys" class=row style="gap:8px">
        <input name=name placeholder="key name (e.g. prod)" style="max-width:200px">
        <select name=deployment_id>{dep_opts}</select>
        <button class=btn>Create API key</button>
      </form>
    </div>"""


def _webhooks_section(webhooks: list[dict]) -> str:
    from .store import WEBHOOK_EVENTS
    rows = ""
    for w in webhooks or []:
        rows += (f"<tr><td class=small>{_e(w['url'])}</td><td class='small muted'>{_e(w['events'])}</td>"
                 f"<td><code>{_e(w['secret'])}</code></td>"
                 f"<td><form method=post action='/app/webhooks/delete' style='margin:0'>"
                 f"<input type=hidden name=webhook_id value='{w['id']}'>"
                 f"<button class='btn sec sm'>Delete</button></form></td></tr>")
    table = (f"<div class=card style='padding:0'><table><thead><tr><th>URL</th><th>Events</th>"
             f"<th>Signing secret</th><th></th></tr></thead><tbody>{rows}</tbody></table></div>"
             if rows else "<div class=card><p class='small muted'>No webhooks yet.</p></div>")
    opts = "".join(f'<option value="{e}">{e}</option>' for e in WEBHOOK_EVENTS)
    return f"""
    <h2>Webhooks</h2>
    <p class="small muted">Get notified of events (budget thresholds, tuning proposals, account
    changes). We POST JSON signed with <code>X-ModelPilot-Signature: sha256=…</code> (HMAC of the body
    with the webhook's signing secret).</p>
    {table}
    <div class=card style="margin-top:12px">
      <form method=post action="/app/webhooks" class=row style="gap:8px">
        <input name=url placeholder="https://your-app.com/hooks/modelpilot" style="min-width:280px">
        <select name=events>
          <option value="all">all events</option>{opts}
        </select>
        <button class=btn>Add webhook</button>
      </form>
    </div>"""


def connect_page(account: dict, deployments: list[dict], brain_url: str, console_url: str,
                 keys: list[dict] | None = None, new_key: str = "",
                 webhooks: list[dict] | None = None) -> str:
    dep = deployments[0]["deployment_id"] if deployments else "—"
    dep_rows = ""
    for d in deployments:
        dep_rows += f"""<tr>
          <td><code>{_e(d['deployment_id'])}</code></td>
          <td><form method=post action="/app/deployments/rename" class=row style="gap:6px">
            <input type=hidden name=deployment_id value="{_e(d['deployment_id'])}">
            <input name=label value="{_e(d.get('label') or '')}" style="padding:6px;max-width:200px">
            <button class="btn sec sm">Rename</button></form></td>
          <td class="small muted">{_fmt_date(d.get('created_at'))}</td></tr>"""
    welcome = ('<div class=note style="margin-bottom:18px"><b>Welcome to ModelPilot 👋</b> '
               'Let\'s get you connected — it takes about five minutes. Once your first requests '
               'flow through, your <a href="/app">Home dashboard</a> lights up with savings.</div>'
               if not keys else "")
    body = f"""
    <h1>Configuration</h1>
    {welcome}
    <p class=muted>ModelPilot is a drop-in proxy for the Claude Messages API. Point your SDK at it —
    only a task category + numeric features ever leave your box, never prompt text or your API key.</p>
    <div class=card>
      <h2 style="margin-top:0">1. Install the client</h2>
      <pre>pip install modelpilot-client</pre>
      <h2>2. Configure</h2>
      <pre>export MODELPILOT_BRAIN_URL={_e(brain_url)}
export MODELPILOT_CONSOLE_URL={_e(console_url)}
export MODELPILOT_API_KEY=mp_live_…        # create one below (recommended)
export MODELPILOT_DEPLOYMENT_ID={_e(dep)}
modelpilot-client            # listens on :8400, proxies to api.anthropic.com</pre>
      <h2>3. Point your SDK at it</h2>
      <pre>from anthropic import Anthropic
client = Anthropic(base_url="http://127.0.0.1:8400")  # your key stays local</pre>
      <p class="small muted">Your mode (set in <a href="/app/settings">Settings</a>) and entitlement are
      enforced server-side; savings are metered automatically so your bill always reflects real,
      delivered savings.</p>
    </div>

    <h2>Deployments</h2>
    <p class="small muted">Run ModelPilot in more than one app or environment (staging, prod, a second
    service). Each gets its own id; savings across all of them roll up to one bill.</p>
    <div class=card style="padding:0"><table>
      <thead><tr><th>Deployment id</th><th>Label</th><th>Created</th></tr></thead>
      <tbody>{dep_rows}</tbody></table></div>
    <div class=card style="margin-top:12px">
      <form method=post action="/app/deployments" class=row style="gap:8px">
        <input name=label placeholder="e.g. production-api" style="max-width:240px">
        <button class=btn>Add deployment</button>
      </form>
    </div>
    {_api_keys_section(keys or [], deployments, new_key)}
    {_webhooks_section(webhooks or [])}
    <h2>Tuning capture <span class="small muted">— optional, stays on your machine</span></h2>
    <div class=card>
      <p class="small muted">ModelPilot tunes routing to your workload from category labels and outcomes —
        no prompt content needed. For <b>sharper</b> per-category tuning you can let the proxy sample a
        fraction of prompts <b>locally, on your own box</b>, to validate cheaper models on your real
        traffic. Captured prompts are used only for local tuning and <b>never leave your machine</b>.
        Off by default.</p>
      <pre>export MODELPILOT_CAPTURE_PCT=0.05   <span class="muted"># sample 5% locally for tuning (0 = off, the default)</span></pre>
      <p class="small muted">Then run <code>modelpilot tune</code> / <code>modelpilot learn-floors</code> on your
        box to turn that local sample into proposed floors — which you review and approve here before anything
        changes. See <a href="/security.html#optimize">how we optimize without seeing your data</a>.</p>
    </div>"""
    return page("Configuration", body, account, "/app/connect")


def _sso_section(sso: dict, scim_token: str = "") -> str:
    from .store import TEAM_ROLES
    s = sso or {}
    chk = "checked" if s.get("enabled") else ""
    role_opts = "".join(f'<option value="{r}"{" selected" if s.get("default_role")==r else ""}>{r}</option>'
                        for r in TEAM_ROLES)

    def v(k):
        return _e(s.get(k) or "")
    scim_note = (f'<div class="note">SCIM token (shown once): <code>{_e(scim_token)}</code><br>'
                 f'<span class=small>Use it as a Bearer token at <code>/scim/v2/Users</code>.</span></div>'
                 if scim_token else "")
    return f"""
    <h2>Single sign-on (OIDC) <span class="small muted">— Enterprise</span></h2>
    <p class="small muted">Let your team sign in via your identity provider. Users go to
    <code>/sso/start?email=you@yourdomain</code>; we route by email domain. Redirect/callback URL:
    <code>{_e(os.environ.get('CONSOLE_BASE_URL','http://127.0.0.1:8700').rstrip('/'))}/sso/callback</code></p>
    <div class=card><form method=post action="/app/sso">
      <div class=field><label class=row><input type=checkbox name=enabled value=1 {chk}
        style="width:auto;margin-right:8px"> Enable SSO</label></div>
      <div class="grid cols-2">
        <div class=field><label>Email domain</label><input name=domain value="{v('domain')}" placeholder="yourdomain.com"></div>
        <div class=field><label>Default role for new users</label><select name=default_role>{role_opts}</select></div>
        <div class=field><label>Client ID</label><input name=client_id value="{v('client_id')}"></div>
        <div class=field><label>Client secret</label><input name=client_secret type=password value="{v('client_secret')}"></div>
        <div class=field><label>Authorization URL</label><input name=auth_url value="{v('auth_url')}" placeholder="https://idp/authorize"></div>
        <div class=field><label>Token URL</label><input name=token_url value="{v('token_url')}" placeholder="https://idp/token"></div>
        <div class=field><label>Userinfo URL</label><input name=userinfo_url value="{v('userinfo_url')}" placeholder="https://idp/userinfo"></div>
      </div>
      <button class=btn>Save SSO</button>
    </form></div>

    <h2>SCIM provisioning</h2>
    <p class="small muted">Auto-provision/deprovision members from your IdP via SCIM 2.0
    (<code>/scim/v2/Users</code>). Generate a bearer token for your IdP connector.</p>
    {scim_note}
    <div class=card><form method=post action="/app/sso/scim">
      <button class="btn sec">{'Regenerate' if s.get('scim_token_hash') else 'Generate'} SCIM token</button>
    </form></div>"""


def team_page(account: dict, members: list[dict], invite_link: str = "",
              sso: dict | None = None, scim_token: str = "") -> str:
    from .store import TEAM_ROLES
    invite_note = (f'<div class="note">Invite sent. Share this set-password link (valid 1h): '
                   f'<a href="{_e(invite_link)}">{_e(invite_link)}</a></div>' if invite_link else "")
    rows = (f'<tr><td>{_e(account["email"])}</td><td><span class="badge paid">owner</span></td>'
            f'<td class="small muted">account owner</td><td></td></tr>')
    for m in members:
        opts = "".join(f'<option value="{r}"{" selected" if m["role"]==r else ""}>{r}</option>'
                       for r in TEAM_ROLES)
        status = "" if m["status"] == "active" else f' <span class="badge trial">{_e(m["status"])}</span>'
        rows += f"""<tr><td>{_e(m['email'])}{status}</td>
          <td><form method=post action="/app/team/role" class=row style="gap:6px">
            <input type=hidden name=member_id value="{m['id']}">
            <select name=role>{opts}</select><button class="btn sec sm">Save</button></form></td>
          <td class="small muted">{_fmt_date(m.get('created_at'))}</td>
          <td><form method=post action="/app/team/remove" style="margin:0">
            <input type=hidden name=member_id value="{m['id']}">
            <button class="btn sec sm">Remove</button></form></td></tr>"""
    role_opts = "".join(f'<option value="{r}">{r}</option>' for r in TEAM_ROLES)
    body = f"""
    <h1>Team</h1>
    <p class=muted>Invite teammates and set their access. Roles: <b>admin</b> (everything),
    <b>billing</b> (dashboard + billing), <b>member</b> (dashboard, logs, connect — read-only).</p>
    {invite_note}
    <div class=card style="padding:0"><table>
      <thead><tr><th>Member</th><th>Role</th><th>Joined</th><th></th></tr></thead>
      <tbody>{rows}</tbody></table></div>
    <div class=card style="margin-top:12px">
      <form method=post action="/app/team/invite" class=row style="gap:8px">
        <input name=email type=email placeholder="teammate@company.com" required style="min-width:240px">
        <select name=role>{role_opts}</select>
        <button class=btn>Invite</button>
      </form>
      <p class="small muted" style="margin-top:8px">They'll get a link to set a password and sign in.</p>
    </div>
    {_sso_section(sso or {}, scim_token)}"""
    return page("Team", body, account, "/app/team")


def logs_page(account: dict, logs: list[dict], total: int) -> str:
    if not logs:
        body = """
        <h1>Request logs</h1>
        <p class=muted>Per-request <b>metadata only</b> — timestamps, models, category, token counts,
          cost, and routed/escalated flags. Prompt text and outputs never leave your box.</p>
        <div class=card><p class="muted">No logs yet. They're <b>opt-in</b>: run your gateway with
          <code>MODELPILOT_LOGS=1</code> (ships metadata to the console) and/or
          <code>MODELPILOT_OTEL_ENDPOINT=…</code> (exports OTLP traces to your own collector).
          See the <a href="https://modelpilot.pages.dev/docs/configuration.html">docs</a>.</p></div>"""
        return page("Logs", body, account, "/app/logs")
    rows = ""
    for r in logs:
        when = _fmt_date(r.get("ts"))
        route = (f'{_e(r.get("original_model"))} → <b>{_e(r.get("routed_model"))}</b>'
                 if r.get("applied") else _e(r.get("original_model") or "—"))
        flags = []
        if r.get("applied"):
            flags.append('<span class="badge paid">routed</span>')
        if r.get("escalated"):
            flags.append('<span class="badge suspended">escalated</span>')
        rows += (f"<tr><td class='small muted'>{when}</td><td>{_e(r.get('category'))}</td>"
                 f"<td class=small>{route}</td>"
                 f"<td>{int((r.get('input_tokens') or 0)+(r.get('output_tokens') or 0)):,}</td>"
                 f"<td>{money(r.get('actual_cost'))}</td><td>{money(r.get('realized_saved'))}</td>"
                 f"<td>{r.get('status_code') or ''}</td><td>{' '.join(flags)}</td></tr>")
    body = f"""
    <div class=row><h1>Request logs</h1><div class=spacer></div>
      <a class="btn sec sm" href="/app/logs.csv">Export CSV</a></div>
    <p class=muted>Per-request <b>metadata only</b> — never prompt text or outputs. Showing the latest
      {len(logs)} of {total:,}.</p>
    <div class=card style="padding:0"><table>
      <thead><tr><th>Time</th><th>Category</th><th>Model</th><th>Tokens</th><th>Cost</th>
        <th>Saved</th><th>Status</th><th></th></tr></thead>
      <tbody>{rows}</tbody></table></div>
    <p class="small muted" style="margin-top:12px">Export to your own observability stack with OTLP:
      set <code>MODELPILOT_OTEL_ENDPOINT</code> on your gateway
      (<a href="https://modelpilot.pages.dev/docs/configuration.html">docs</a>).</p>"""
    return page("Logs", body, account, "/app/logs")


def forgot_form(sent: bool = False, email: str = "") -> str:
    if sent:
        body = """<div class=auth><div class=card>
          <h1>Check your email</h1>
          <p class=muted>If an account exists for that address, we've sent a password-reset link
          (valid for 1 hour). <a href="/login">Back to sign in</a>.</p></div></div>"""
        return page("Reset password", body)
    body = f"""
    <div class=auth><div class=card>
      <h1>Reset your password</h1>
      <p class=muted small>Enter your email and we'll send a reset link.</p>
      <form method=post action="/forgot">
        <div class=field><label>Email</label>
          <input name=email type=email required value="{_e(email)}" placeholder="you@company.com"></div>
        <button class="btn" style="width:100%">Send reset link</button>
      </form>
      <p class="small center muted" style="margin-top:14px"><a href="/login">Back to sign in</a></p>
    </div></div>"""
    return page("Reset password", body)


def reset_form(token: str, error: str = "") -> str:
    err = f'<div class="note bad">{_e(error)}</div>' if error else ""
    body = f"""
    <div class=auth><div class=card>
      <h1>Set a new password</h1>{err}
      <form method=post action="/reset">
        <input type=hidden name=token value="{_e(token)}">
        <div class=field><label>New password</label>
          <input name=password type=password required minlength=8 placeholder="At least 8 characters"></div>
        <button class="btn" style="width:100%">Update password</button>
      </form>
    </div></div>"""
    return page("Set a new password", body)


# --------------------------------------------------------------------------- #
# Billing
# --------------------------------------------------------------------------- #

def billing_page(account: dict, plan: dict, trial: dict, bill: dict,
                 stripe_on: bool, flash: str = "") -> str:
    is_paid = plan.get("plan") == "paid"
    status_badge = ('<span class="badge paid">Paid plan</span>' if is_paid else
                    (f'<span class="badge trial">Trial · {trial["days_left"]}d left</span>'
                     if trial["active"] else '<span class="badge suspended">Trial ended</span>'))
    flash_html = ""
    if flash == "success":
        flash_html = '<div class="note">Billing is active — thanks! Your savings are now being metered.</div>'
    elif flash == "cancel":
        flash_html = '<div class="note warn">Checkout canceled — no changes made.</div>'
    elif flash == "converted":
        flash_html = '<div class="note">Plan activated.</div>'
    if not is_paid and not trial["active"]:
        flash_html = ('<div class="note bad"><b>Your free trial has ended.</b> Optimization is paused — '
                      'activate billing below to resume saving on your Claude bill. You only pay 20% of '
                      'what we save you.</div>' + flash_html)

    if is_paid:
        action = f"""
        <p>You're on the usage-based plan: <b>{int(bill['rate']*100)}% of realized savings</b>.</p>
        <div class="grid cols-2">
          <div><div class=label>Savings this cycle</div><div class="stat green">{money(bill['cycle_savings'])}</div></div>
          <div><div class=label>Your bill this cycle</div><div class=stat>{money(bill['bill'])}</div></div>
        </div>
        <p class="small muted" style="margin-top:10px">Invoiced automatically each cycle via Stripe.
        Net value to you this cycle: <b>{money(bill['net_customer_value'])}</b>.</p>"""
    else:
        stripe_note = ("" if stripe_on else
                       '<p class="small muted">Card collection via Stripe isn\'t configured on this '
                       'instance yet — activating records your plan so metering continues; we\'ll '
                       'reconcile billing when Stripe is connected.</p>')
        action = f"""
        <p>After your trial you pay only <b>{int(bill['rate']*100)}% of the savings we deliver</b> —
        if we don't save you money, you don't pay. Based on this cycle so far, that would be
        <b>{money(bill['would_bill'])}</b> on {money(bill['cycle_savings'])} of savings.</p>
        <form method=post action="/app/billing/convert">
          <button class=btn>{'Add billing & activate paid plan' if stripe_on else 'Activate paid plan'}</button>
        </form>{stripe_note}"""
    body = f"""
    <div class=row><h1>Billing</h1><div class=spacer></div>{status_badge}</div>
    {flash_html}
    <div class=card>{action}</div>
    <div class=card style="margin-top:16px">
      <div class=label>How billing works</div>
      <p class="small muted">We meter the realized savings on every routed request (baseline cost minus
      actual cost — dollars only, never prompt content). Your bill each cycle is {int(bill['rate']*100)}%
      of that. Lifetime savings delivered: <b>{money(bill['lifetime_savings'])}</b>.</p>
    </div>"""
    return page("Billing", body, account, "/app/billing")


# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #

def admin_overview(account: dict, rev: dict, rows: list[dict], pending: int = 0) -> str:
    trs = ""
    for r in rows:
        badge = (f'<span class="badge {r["plan_badge"]}">{_e(r["plan_label"])}</span>')
        admin_tag = ' <span class="badge admin">admin</span>' if r["role"] == "admin" else ""
        pend = (f' <span class="badge trial">{r["pending_proposals"]} to review</span>'
                if r.get("pending_proposals") else "")
        trs += f"""<tr>
          <td><a href="/admin/accounts/{r['id']}">{_e(r['email'])}</a>{admin_tag}{pend}<br>
            <span class="small muted">{_e(r['company'] or '')}</span></td>
          <td>{badge}</td>
          <td>{dual_metric(r['lifetime_savings'], suffix="")}</td>
          <td>{dual_metric(r['cycle_savings'], suffix="")}</td>
          <td>{money(r['cycle_revenue'])}</td>
          <td class="small muted">{_fmt_date(r['created_at'])}</td></tr>"""
    pending_card = (f'<a class=card href="/admin/proposals" style="display:block;text-decoration:none;color:inherit">'
                    f'<div class=label>Tuning to review</div>'
                    f'<div class=stat>{pending}</div>'
                    f'<div class="small muted">auto-proposed floor/rule changes — click to review &amp; bulk-approve</div></a>')
    body = f"""
    <div class=row><h1>Admin · overview</h1><div class=spacer></div>{metric_toggle_control()}</div>
    <p class=muted>Revenue and savings across all customers. Use this to spot where the product is
    (and isn't) delivering value.</p>
    <div class="grid cols-2">
      <div class=card><div class=label>Revenue this cycle</div>
        <div class="stat green">{money(rev['cycle_revenue'])}</div>
        <div class="small muted">lifetime {money(rev['total_revenue'])}</div></div>
      <div class=card><div class=label>Savings delivered this cycle</div>
        <div class=stat>{dual_metric(rev['cycle_savings'])}</div>
        <div class="small muted">lifetime {dual_metric(rev['total_savings_delivered'], suffix="")}</div></div>
    </div>
    <div class="grid cols-2" style="margin-top:16px">
      <div class=card><div class=label>Accounts</div>
        <div class=stat>{rev['n_accounts']}</div>
        <div class="small muted">{rev['n_paid']} paid · {rev['n_trial']} trial · {rev['n_suspended']} suspended</div></div>
      {pending_card}
    </div>
    <h2>Customers</h2>
    <div class=card style="padding:0">
      <table><thead><tr><th>Account</th><th>Plan</th><th>Lifetime savings</th>
        <th>Savings (cycle)</th><th>Revenue (cycle)</th><th>Joined</th></tr></thead>
        <tbody>{trs or '<tr><td colspan=6 class="muted">No accounts yet.</td></tr>'}</tbody></table>
    </div>
    {metric_toggle_assets()}"""
    return page("Admin", body, account, "/admin")


_LADDER_NAMES = ["haiku", "sonnet", "opus", "fable"]


def _tier_name(t) -> str:
    try:
        return _LADDER_NAMES[int(t)]
    except (TypeError, ValueError, IndexError):
        return str(t)


def _proposal_desc(p: dict) -> tuple[str, str, str]:
    """(kind label, human description, evidence/meta) for one proposal."""
    stats = p.get("stats") or {}
    payload = p.get("payload") or {}
    if p["kind"] == "floor":
        cur, prop = payload.get("current_tier"), payload.get("proposed_tier")
        desc = (f"Lower <b>{_e(p['category'])}</b> floor "
                f"{_e(_tier_name(cur))} → <b>{_e(_tier_name(prop))}</b>")
        meta = (f"{int(stats.get('samples', 0))} samples · "
                f"{(100*stats['non_inferior_rate']):.0f}% non-inferior"
                if stats.get("non_inferior_rate") is not None
                else f"{int(stats.get('samples', 0))} samples")
        return "Floor", desc, meta
    sigs = (payload.get("any") or []) + payload.get("regex", [])
    sig_txt = ", ".join(_e(s) for s in sigs[:6]) or "—"
    desc = (f"Rule <b>{_e(payload.get('name') or p['category'])}</b>: classify as "
            f"<b>{_e(p['category'])}</b> when prompt matches <span class=muted>{sig_txt}</span>")
    return "Rule", desc, f"{int(stats.get('samples', 0))} matching samples"


def _proposals_section(target_id: int, proposals: list[dict]) -> str:
    if not proposals:
        return ('<h2>Proposed tuning</h2><div class=card><p class="small muted">No pending '
                'proposals. Customers\' gateways submit auto-derived floor/rule changes here '
                '(validated on their own traffic) for your approval.</p></div>')
    cards = ""
    for p in proposals:
        label, desc, meta = _proposal_desc(p)
        cards += f"""<div class=card style="margin-bottom:10px">
          <div class=row><div><b>{label}</b> · {desc}</div><div class=spacer></div></div>
          <p class="small muted" style="margin:6px 0 10px">{meta}</p>
          <form method=post action="/admin/accounts/{target_id}/proposal" class=row style="gap:8px">
            <input type=hidden name=proposal_id value="{p['id']}">
            <input name=note placeholder="note (optional)" style="padding:6px;max-width:240px">
            <button class="btn sm" name=decision value=approved>Approve</button>
            <button class="btn sec sm" name=decision value=rejected>Reject</button>
          </form></div>"""
    return (f'<h2>Proposed tuning <span class="small muted">— {len(proposals)} pending</span></h2>'
            f'{cards}')


def admin_proposals_queue(account: dict, proposals: list[dict], emails: dict) -> str:
    """Global pending-proposal queue with bulk approve/reject across customers."""
    if not proposals:
        body = ('<h1>Review queue</h1><div class=card><p class=muted>No pending tuning proposals '
                'across any customer.</p></div>')
        return page("Review queue", body, account, "/admin/proposals")
    rows = ""
    for p in proposals:
        label, desc, meta = _proposal_desc(p)
        email = _e(emails.get(p["account_id"], "?"))
        rows += f"""<tr>
          <td><input type=checkbox name=ids value="{p['id']}" checked></td>
          <td><a href="/admin/accounts/{p['account_id']}">{email}</a></td>
          <td><b>{label}</b> · {desc}<br><span class="small muted">{meta}</span></td>
          <td class="small muted">{_fmt_date(p.get('created_at'))}</td></tr>"""
    body = f"""
    <div class=row><h1>Review queue</h1><div class=spacer></div>
      <a class="small" href="/admin">← overview</a></div>
    <p class=muted>{len(proposals)} pending tuning proposal(s) across all customers. Tick the ones
    to act on, add an optional note, then approve or reject in bulk.</p>
    <form method=post action="/admin/proposals/bulk">
      <div class=card style="padding:0"><table>
        <thead><tr>
          <th><label class=row style="gap:4px"><input type=checkbox checked
            onclick="for(const c of document.getElementsByName('ids'))c.checked=this.checked"> all</label></th>
          <th>Customer</th><th>Proposed change</th><th>Submitted</th></tr></thead>
        <tbody>{rows}</tbody></table></div>
      <div class=card style="margin-top:12px"><div class=row style="gap:8px">
        <input name=note placeholder="note applied to all selected (optional)" style="max-width:320px">
        <span class=spacer></span>
        <button class="btn" name=decision value=approved>Approve selected</button>
        <button class="btn sec" name=decision value=rejected>Reject selected</button>
      </div></div>
    </form>"""
    return page("Review queue", body, account, "/admin/proposals")


def _audit_section(history: list[dict]) -> str:
    if not history:
        return ""
    rows = ""
    for p in history:
        payload = p.get("payload") or {}
        if p["kind"] == "floor":
            what = f"floor {_e(p['category'])} → {_e(_tier_name(payload.get('proposed_tier')))}"
        else:
            what = f"rule {_e(payload.get('name') or p['category'])} → {_e(p['category'])}"
        badge = "paid" if p["status"] == "approved" else "suspended"
        note = f' · <span class=muted>{_e(p["note"])}</span>' if p.get("note") else ""
        by = p.get("decided_by_email") or ("auto" if p.get("decided_at") else "—")
        rows += (f"<tr><td>{what}</td>"
                 f"<td><span class='badge {badge}'>{_e(p['status'])}</span></td>"
                 f"<td class='small muted'>{_e(by)}</td>"
                 f"<td class='small muted'>{_fmt_date(p.get('decided_at'))}{note}</td></tr>")
    return (f'<h2>Tuning history <span class="small muted">— audit trail</span></h2>'
            f'<div class=card style="padding:0"><table><thead><tr><th>Change</th><th>Decision</th>'
            f'<th>By</th><th>When</th></tr></thead><tbody>{rows}</tbody></table></div>')


def admin_account_detail(account: dict, target: dict, plan: dict, trial: dict,
                         settings: dict, bill: dict, cats: list[dict],
                         suggestions: list[str], reset_link: str = "",
                         proposals: list[dict] | None = None,
                         history: list[dict] | None = None) -> str:
    cat_rows = ""
    for c in cats:
        esc_rate = (100 * c["escalations"] / c["routed"]) if c["routed"] else 0
        flag = ' <span class="badge suspended">high escalation</span>' if esc_rate > 5 else ""
        cat_rows += f"""<tr><td>{_e(c['category'])}{flag}</td>
          <td>{int(c['requests'] or 0):,}</td><td>{int(c['routed'] or 0):,}</td>
          <td>{int(c['escalations'] or 0):,} ({esc_rate:.0f}%)</td>
          <td>{money(c['savings'])}</td></tr>"""
    sugg = "".join(f"<li>{_e(s)}</li>" for s in suggestions) or "<li class=muted>No suggestions yet.</li>"
    plan_label = plan.get("plan", "trial")
    rate_pct = int(plan.get("rate", 0.2) * 100)
    suspend_btn = (f'<button class="btn bad sm" name=action value=suspend>Suspend</button>'
                   if target["status"] == "active" else
                   f'<button class="btn sm" name=action value=reactivate>Reactivate</button>')
    convert_btn = ('' if plan_label == 'paid' else
                   '<button class="btn sm" name=action value=convert>Mark paid</button>')
    body = f"""
    <div class=row><a href="/admin" class="small">← all customers</a></div>
    <div class=row><h1>{_e(target['email'])}</h1><div class=spacer></div>
      <span class="badge {'paid' if plan_label=='paid' else 'trial'}">{_e(plan_label)}</span>
      {'<span class="badge suspended">suspended</span>' if target['status']!='active' else ''}</div>
    <p class=muted>{_e(target['company'] or '')} · joined {_fmt_date(target['created_at'])} ·
      mode <b>{_e(settings['mode'])}</b> · trial {'active' if trial['active'] else 'ended'}
      ({trial['days_left']}d)</p>

    <div class="grid cols-3">
      <div class=card><div class=label>Lifetime savings</div><div class="stat green">{money(bill['lifetime_savings'])}</div></div>
      <div class=card><div class=label>Savings this cycle</div><div class=stat>{money(bill['cycle_savings'])}</div></div>
      <div class=card><div class=label>Revenue this cycle ({rate_pct}%)</div>
        <div class=stat>{money(bill['would_bill'])}</div></div>
    </div>

    <h2>Per-category performance <span class="small muted">— where routing is (and isn't) working</span></h2>
    <div class=card style="padding:0"><table>
      <thead><tr><th>Category</th><th>Requests</th><th>Routed</th><th>Escalations</th><th>Savings</th></tr></thead>
      <tbody>{cat_rows or '<tr><td colspan=5 class=muted>No metering yet.</td></tr>'}</tbody></table></div>

    <h2>Suggested actions</h2>
    <div class=card><ul style="margin:0;padding-left:20px">{sugg}</ul></div>"""
    reset_note = (f'<div class="note">Reset link (valid 1h): <a href="{_e(reset_link)}">{_e(reset_link)}</a></div>'
                  if reset_link else "")
    body += f"""
    {_proposals_section(target['id'], proposals or [])}
    {_audit_section(history or [])}

    <h2>Manage access</h2>
    {reset_note}
    <div class=card><form method=post action="/admin/accounts/{target['id']}/action">
      <div class=row>
        <button class="btn sm" name=action value=extend_trial>+7 trial days</button>
        {convert_btn}
        {suspend_btn}
        <button class="btn sec sm" name=action value=send_reset>Send reset link</button>
        <span class=spacer></span>
        <label class="small row" style="gap:6px">Rate %
          <input name=rate type=number step=1 min=0 max=100 value="{rate_pct}" style="width:80px">
          <button class="btn sec sm" name=action value=set_rate>Set</button></label>
      </div>
    </form></div>"""
    return page(f"Admin · {target['email']}", body, account, "/admin")
