"""Outlay console — HTML rendering (server-side, dependency-free).

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
BRAND = "Outlay"

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
/* navigation progress bar + button busy spinner — feedback during cold starts so
   a slow page never looks unresponsive */
#nprogress{position:fixed;top:0;left:0;right:0;height:3px;z-index:9999;opacity:0;transition:opacity .25s}
#nprogress.on{opacity:1}
#nprogress b{display:block;height:100%;width:0;border-radius:0 3px 3px 0;
  background:linear-gradient(90deg,var(--accent),var(--accent-d));box-shadow:0 0 10px var(--accent);
  transition:width .25s ease}
.btn.loading{position:relative;color:transparent!important;pointer-events:none}
.btn.loading::after{content:"";position:absolute;top:50%;left:50%;width:14px;height:14px;margin:-7px 0 0 -7px;
  border:2px solid rgba(255,255,255,.55);border-top-color:#fff;border-radius:50%;animation:mp-spin .6s linear infinite}
.btn.sec.loading::after{border-color:rgba(0,0,0,.25);border-top-color:#111}
@keyframes mp-spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){#nprogress b{transition:opacity .2s}.btn.loading::after{animation:none}}
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
        # Routing/optimization surfaces (Configuration, Billing) are parked for now;
        # the product is spend attribution + forecasting. Team/SSO live in Settings.
        items = [("/app/outlay", "Spend"), ("/app/settings", "Settings")]
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
            '<a class=brand href="/app">Out<span class=dot>lay</span></a>'
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
            f'<a class=brand href="/">Out<span class=dot>lay</span></a>{nav}'
            f'</div></div><div class=wrap>{body}</div>')
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
<title>{_e(title)} · {BRAND}</title><style>{_CSS}</style></head><body>
<div id=nprogress><b></b></div>
{chrome}
<script>(function(){{var d=document,bar=d.getElementById('nprogress'),fill=bar&&bar.firstChild,t=null,p=0;
function set(v){{p=v;if(fill)fill.style.width=(v*100)+'%';}}
function start(){{if(!bar)return;bar.classList.add('on');set(.08);if(t)clearInterval(t);
  t=setInterval(function(){{set(Math.min(p+(.9-p)*.12+.004,.92));}},300);}}
function done(){{if(t){{clearInterval(t);t=null;}}if(!bar)return;set(1);
  setTimeout(function(){{bar.classList.remove('on');set(0);}},250);
  [].forEach.call(d.querySelectorAll('.btn.loading'),function(b){{b.classList.remove('loading');}});}}
function isFile(h){{return /\\.(csv|json|pdf|zip|png|jpe?g|txt)(\\?|#|$)/i.test(h);}}
function internal(a){{if(!a||a.target==='_blank'||a.hasAttribute('download'))return false;
  var h=a.getAttribute('href')||'';
  if(!h||h.charAt(0)==='#'||/^(mailto:|tel:|javascript:)/i.test(h)||isFile(h))return false;
  return a.origin===location.origin;}}
d.addEventListener('click',function(e){{if(e.defaultPrevented||e.button!==0||e.metaKey||e.ctrlKey||e.shiftKey||e.altKey)return;
  var a=e.target.closest&&e.target.closest('a');if(internal(a))start();}},true);
d.addEventListener('submit',function(e){{var f=e.target;if(!f||f.getAttribute('target')==='_blank')return;start();
  var b=e.submitter||f.querySelector('button[type=submit],button:not([type]),input[type=submit]');
  if(b&&b.classList)b.classList.add('loading');}},true);
window.addEventListener('pageshow',function(ev){{if(ev.persisted)done();}});}})();</script>
<script>(function(){{var d=document;
if(!('IntersectionObserver' in window)||(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches))return;
var els=[].slice.call(d.querySelectorAll('.card,.hero'));
els.forEach(function(c,i){{c.classList.add('reveal');c.style.setProperty('--rd',Math.min(i*55,330)+'ms');}});
var io=new IntersectionObserver(function(es){{es.forEach(function(e){{if(e.isIntersecting){{e.target.classList.add('in');io.unobserve(e.target);}}}});}},{{threshold:.06}});
els.forEach(function(c){{io.observe(c);}});}})();</script>
</body></html>"""


# --------------------------------------------------------------------------- #
# Outlay — spend attribution / forecast dashboard (real engine output)
# --------------------------------------------------------------------------- #

def _outlay_connect(error: str = "", collapsed: bool = False) -> str:
    err = f'<div class="err">{_e(error)}</div>' if error else ""
    summary = ('<summary class="btn sec sm" style="display:inline-block">Update data</summary>'
               if collapsed else "")
    open_attr = "" if collapsed else " open"
    return f"""<details class=card{open_attr}>{summary}
      <h3 style="margin:.2em 0 .4em">Connect your data <span class=muted style="font-weight:400">· read-only</span></h3>
      <p class=muted style="margin:.2em 0 1em">Paste your tracker export (GitHub Issues JSON) and your AI-usage
        export (Anthropic usage JSON). Metadata only — no prompts. Optionally add a planned-work backlog to budget it.</p>
      {err}
      <div style="display:grid;gap:12px">
        <label class=fld><span>Tracker — GitHub Issues JSON</span>
          <textarea id=ol_issues rows=4 placeholder='{{"issues":[ ... ]}}'></textarea></label>
        <label class=fld><span>AI usage — Anthropic usage JSON</span>
          <textarea id=ol_usage rows=4 placeholder='[ {{"id":"e1","model":"claude-...","input_tokens":...}} ]'></textarea></label>
        <label class=fld><span>Planned backlog (optional) — JSON</span>
          <textarea id=ol_planned rows=3 placeholder='{{"items":[{{"id":"PROJ-1","title":"Add SSO","requirements":"...","points":8}}]}}'></textarea></label>
      </div>
      <button class="btn" style="margin-top:12px" onclick="outlayRun(this)">Run the audit</button>
      <script>
      function outlayRun(btn){{btn.classList.add('loading');btn.disabled=true;
        fetch('/app/outlay/run',{{method:'POST',headers:{{'content-type':'application/json'}},
          body:JSON.stringify({{issues:document.getElementById('ol_issues').value,
            usage:document.getElementById('ol_usage').value,
            planned:document.getElementById('ol_planned').value}})}})
        .then(function(r){{return r.json();}}).then(function(d){{
          if(d.ok){{location.reload();}}else{{btn.classList.remove('loading');btn.disabled=false;
            alert(d.error||'Could not run the audit.');}}}})
        .catch(function(){{btn.classList.remove('loading');btn.disabled=false;alert('Network error.');}});}}
      </script>
    </details>"""


def _sparkline(values: list[float], w: int = 120, h: int = 28, color: str = "#13203a") -> str:
    """A tiny inline SVG sparkline of recent spend snapshots. Empty if <2 points."""
    vals = [float(v) for v in values if v is not None]
    if len(vals) < 2:
        return ""
    lo, hi = min(vals), max(vals)
    span = (hi - lo) or 1.0
    n = len(vals)
    pts = " ".join(
        f"{(i/(n-1))*w:.1f},{h - ((v-lo)/span)*(h-4) - 2:.1f}" for i, v in enumerate(vals))
    last_x = w
    last_y = h - ((vals[-1]-lo)/span)*(h-4) - 2
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}" style="display:block">'
            f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="1.5" '
            f'stroke-linejoin="round" stroke-linecap="round"/>'
            f'<circle cx="{last_x-0.5:.1f}" cy="{last_y:.1f}" r="2" fill="{color}"/></svg>')


def _trend_delta(history: list[dict]) -> str:
    """'↑ 12% vs last sync' / '↓ 8% vs last sync' from the last two snapshots."""
    if not history or len(history) < 2:
        return "this window"
    cur, prev = history[-1].get("total_usd", 0), history[-2].get("total_usd", 0)
    if prev <= 0:
        return "this window"
    pct = (cur - prev) / prev * 100
    if abs(pct) < 0.5:
        return "flat vs last sync"
    arrow, color = ("↑", "#b3261e") if pct > 0 else ("↓", "#0f6b4f")
    return f'<span style="color:{color}">{arrow} {abs(pct):.0f}% vs last sync</span>'


def _kpi(label: str, value: str, sub: str = "", color: str = "", sub_raw: bool = False) -> str:
    style = f' style="color:{color}"' if color else ""
    sub_html = sub if sub_raw else _e(sub)
    sub = f'<div class=muted style="font-size:12px;margin-top:2px">{sub_html}</div>' if sub else ""
    return (f'<div class=card style="padding:16px 18px"><div class=muted '
            f'style="font-size:11px;letter-spacing:.04em;text-transform:uppercase">{_e(label)}</div>'
            f'<div style="font-size:26px;font-weight:700;margin-top:6px"{style}>{value}</div>{sub}</div>')


def _onboarding(conn: dict | None, report: dict | None, has_budget: bool) -> str:
    """A first-run checklist that disappears once the customer is set up. Each step
    reflects real state so it doubles as a 'what's left' guide during a pilot."""
    conn = conn or {}
    tracker = conn.get("tracker") or "github"
    if tracker == "jira":
        has_tracker = bool(conn.get("jira_base_url") and conn.get("jira_token"))
    elif tracker == "linear":
        has_tracker = bool(conn.get("linear_key"))
    else:
        has_tracker = bool(conn.get("github_owner") and conn.get("github_repo") and conn.get("github_token"))
    has_usage = bool(conn.get("anthropic_key") or conn.get("cursor_key"))
    has_report = bool(report) and not (report or {}).get("_sample")
    steps = [
        ("Connect a tracker", has_tracker, "/app/outlay/connect", "Connect"),
        ("Add an AI-usage key (Anthropic or Cursor)", has_usage, "/app/outlay/connect", "Add key"),
        ("Run your first sync", has_report, "/app/outlay/connect", "Sync"),
        ("Set a budget", has_budget, "/app/outlay/budgets", "Set budget"),
    ]
    done = sum(1 for _, d, _, _ in steps if d)
    if done == len(steps):
        return ""
    rows = ""
    for label, d, href, cta in steps:
        mark = '<span style="color:#0f6b4f">✓</span>' if d else '<span style="color:#cbd5e1">○</span>'
        action = "" if d else f'<a href="{href}" class="btn sec sm" style="margin-left:auto">{cta}</a>'
        style = "color:#94a3b8;text-decoration:line-through" if d else ""
        rows += (f'<div style="display:flex;align-items:center;gap:10px;padding:7px 0;border-top:1px solid #f1f5f9">'
                 f'{mark}<span style="{style}">{_e(label)}</span>{action}</div>')
    return (f'<div class=card style="margin-bottom:16px"><div style="display:flex;justify-content:space-between;align-items:baseline">'
            f'<h3 style="margin:.2em 0 .2em">Get set up <span class=muted style="font-weight:400">· {done}/{len(steps)}</span></h3>'
            f'<span class=muted style="font-size:12px">~10 minutes with read-only tokens</span></div>{rows}</div>')


def outlay_page(account: dict, report: dict | None, statuses: list[dict] | None = None,
                history: list[dict] | None = None, conn: dict | None = None,
                has_budget: bool = False) -> str:
    checklist = _onboarding(conn, report, has_budget)
    if not report:
        intro = ('<div class=hero><h1>Your AI spend, on your roadmap.</h1>'
                 '<p class=muted>Connect your data and Outlay maps every dollar to the work that drove it, '
                 'forecasts the quarter, and finds savings — all on metadata, prompts never leave your tools.</p>'
                 '<p style="margin-top:6px"><a class="btn" href="/app/outlay/connect">Connect live (GitHub + Anthropic) →</a>'
                 '<form method=post action="/app/outlay/sample" style="display:inline;margin-left:10px">'
                 '<button class="btn sec">See it with sample data</button></form>'
                 '<span class=muted style="margin-left:10px">or paste exports below</span></p></div>')
        return page("Spend", intro + checklist + _outlay_connect(), account, active="/app/outlay")

    sp = report.get("spend", {})
    fc = report.get("forecast", {})
    recs = report.get("recommendations", [])
    cal = report.get("calibration") or {}
    est = report.get("estimate")

    cov = sp.get("ticket_coverage", 0.0)
    savings = sum(r.get("projected_savings_usd", 0) for r in recs)
    cov_color = "#0f6b4f" if cov >= 0.6 else "#b45309"
    open_items = fc.get("items_costed", 0) + fc.get("items_unclassified", 0)
    kpis = (
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:0 0 18px">'
        + _kpi("AI spend", money(sp.get("total_usd", 0)), _trend_delta(history or []), sub_raw=True)
        + _kpi("Mapped to a ticket", f"{cov*100:.0f}%", money(sp.get("attributed_to_ticket_usd", 0)) + " attributed", cov_color)
        + _kpi("Forecast · open work", money(fc.get("expected_usd", 0)),
               f"likely {money(fc.get('low_usd', 0))}–{money(fc.get('high_usd', 0))}")
        + _kpi("Open work items", str(open_items), f"{fc.get('items_costed', 0)} costed from history")
        + "</div>")

    # Spend by ticket
    tickets = report.get("tickets", [])[:8]
    maxc = max((t.get("cost_usd", 0) for t in tickets), default=1) or 1
    trows = "".join(
        f'<tr><td class=mono>{_e(t.get("ticket_id"))}</td><td>{_e(t.get("task_class"))}</td>'
        f'<td style="text-align:right">{money(t.get("cost_usd",0))}</td>'
        f'<td style="width:120px"><div style="height:6px;border-radius:4px;background:#eee;overflow:hidden">'
        f'<span style="display:block;height:100%;width:{(t.get("cost_usd",0)/maxc)*100:.0f}%;background:#13203a"></span></div></td></tr>'
        for t in tickets) or '<tr><td colspan=4 class=muted>No ticket-attributed spend yet.</td></tr>'
    spark = _sparkline([h.get("total_usd", 0) for h in (history or [])])
    spark_hdr = (f'<div style="display:flex;justify-content:space-between;align-items:center;margin:.2em 0 .6em">'
                 f'<h3 style="margin:0">Where your AI spend went</h3>'
                 f'<span title="Spend over your last {len(history or [])} refreshes">{spark}</span></div>'
                 if spark else '<h3 style="margin:.2em 0 .6em">Where your AI spend went</h3>')
    spend_card = (f'<div class=card>{spark_hdr}'
                  f'<table class=tbl style="width:100%"><tbody>{trows}</tbody></table></div>')

    # Spend by work type (FinOps view)
    cls = report.get("class_spend") or []
    clsmax = max((c.get("spent_usd", 0) for c in cls), default=1) or 1
    crows = "".join(
        f'<tr><td>{_e(c.get("task_class"))}</td>'
        f'<td class=muted style="text-align:right;font-size:12px">{c.get("tickets",0)}</td>'
        f'<td style="text-align:right">{money(c.get("spent_usd",0))}</td>'
        f'<td class=muted style="text-align:right;font-size:12px">{c.get("share",0)*100:.0f}%</td>'
        f'<td style="width:90px"><div style="height:6px;border-radius:4px;background:#eee;overflow:hidden">'
        f'<span style="display:block;height:100%;width:{(c.get("spent_usd",0)/clsmax)*100:.0f}%;background:#13203a"></span></div></td></tr>'
        for c in cls) or '<tr><td colspan=5 class=muted>No work-type spend yet.</td></tr>'
    class_card = (f'<div class=card><h3 style="margin:.2em 0 .6em">Spend by work type</h3>'
                  f'<table class=tbl style="width:100%"><thead><tr>'
                  f'<th style="text-align:left">Work type</th><th style="text-align:right">Tickets</th>'
                  f'<th style="text-align:right">Spend</th><th style="text-align:right">Share</th><th></th>'
                  f'</tr></thead><tbody>{crows}</tbody></table></div>')

    # Forecast + accuracy
    acc = ""
    if cal.get("n_evaluated", 0) > 0:
        acc = (f'<p class=muted style="font-size:12.5px;margin-top:10px">Forecast accuracy (measured): median '
               f'estimate within ~{cal.get("mdape",0)*100:.0f}% of actual on your closed tickets. '
               f'<a href="/app/outlay/accuracy">details →</a></p>')
    fc_card = (f'<div class=card><h3 style="margin:.2em 0 .4em">Forecast · open work</h3>'
               f'<div style="font-size:28px;font-weight:700">{money(fc.get("expected_usd",0))}</div>'
               f'<div class=muted>likely {money(fc.get("low_usd",0))}–{money(fc.get("high_usd",0))} · '
               f'{fc.get("items_costed",0)} items costed, {fc.get("items_unclassified",0)} without history</div>{acc}</div>')

    # Routing/optimization recommendations are parked for now — the product is
    # spend attribution + forecasting. (The engine still computes recs; we just
    # don't surface the "route down" card. Re-add when routing returns.)

    # Spend by engineer (from Anthropic/Cursor user attribution)
    people = [p for p in (report.get("people") or []) if p.get("user") != "(unattributed)"][:8]
    people_card = ""
    if people:
        pmax = max((p.get("spent_usd", 0) for p in people), default=1) or 1
        prows = "".join(
            f'<tr><td>{_e(p.get("user"))}</td>'
            f'<td class=mono style="font-size:12px">{_e(p.get("top_model"))}</td>'
            f'<td style="text-align:right">{money(p.get("spent_usd",0))}</td>'
            f'<td class=muted style="text-align:right;font-size:12px">{p.get("share",0)*100:.0f}%</td>'
            f'<td style="width:110px"><div style="height:6px;border-radius:4px;background:#eee;overflow:hidden">'
            f'<span style="display:block;height:100%;width:{(p.get("spent_usd",0)/pmax)*100:.0f}%;background:#13203a"></span></div></td></tr>'
            for p in people)
        people_card = (f'<div class=card><h3 style="margin:.2em 0 .6em">Spend by engineer '
                       f'<span class=muted style="font-weight:400;font-size:13px">· team-fidelity (user→cost)</span></h3>'
                       f'<table class=tbl style="width:100%"><thead><tr>'
                       f'<th style="text-align:left">Engineer</th><th style="text-align:left">Top model</th>'
                       f'<th style="text-align:right">Spend</th><th style="text-align:right">Share</th><th></th>'
                       f'</tr></thead><tbody>{prows}</tbody></table></div>')

    # Backlog estimate (optional)
    est_card = ""
    if est:
        erows = "".join(
            f'<tr><td class=mono>{_e(e.get("id"))}</td><td>{_e(e.get("task_class"))}'
            f'{(" · "+_e(e.get("complexity_tier"))) if e.get("complexity_tier") else ""}</td>'
            f'<td style="text-align:right">{money(e.get("expected_usd",0))}</td>'
            f'<td class=muted style="font-size:12px">{_e(e.get("confidence"))}</td></tr>'
            for e in est.get("items", []) if e.get("costable"))
        est_card = (f'<div class=card><h3 style="margin:.2em 0 .4em">Backlog estimate</h3>'
                    f'<div style="font-size:24px;font-weight:700">{money(est.get("expected_usd",0))}</div>'
                    f'<div class=muted>likely {money(est.get("low_usd",0))}–{money(est.get("high_usd",0))} · '
                    f'{est.get("items_costed",0)} estimated, {est.get("items_unknown",0)} declined</div>'
                    f'<table class=tbl style="width:100%;margin-top:8px"><tbody>{erows}</tbody></table></div>')

    grid = (f'<div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">{spend_card}{fc_card}</div>'
            f'<div style="margin-top:16px">{class_card}</div>'
            + (f'<div style="margin-top:16px">{people_card}</div>' if people_card else "")
            + (f'<div style="margin-top:16px">{est_card}</div>' if est_card else ""))
    # Sync status — when the data last refreshed and whether it's automatic.
    conn = conn or {}
    asy = conn.get("auto_sync_hours") or 0
    cadence = {24: "auto-syncs daily", 168: "auto-syncs weekly"}.get(asy, "manual sync")
    last = _fmt_date(conn.get("synced_at")) if conn.get("synced_at") else (
        _fmt_date(report.get("_generated_ts")) if report.get("_generated_ts") else "—")
    sync_err = ('<span style="color:#b3261e"> · ⚠ last sync failed — '
                '<a href="/app/outlay/connect" style="color:#b3261e">fix connection →</a></span>'
                if conn.get("last_sync_error") else
                f'<a href="/app/outlay/connect"> · manage connection →</a>')
    sync_line = (f'<div class=muted style="font-size:12.5px;margin:-2px 0 12px">'
                 f'Last refreshed <b>{last}</b> · {cadence}{sync_err}</div>')
    estlink = ('<div style="margin:-4px 0 16px;display:flex;flex-wrap:wrap;gap:16px;align-items:center">'
               '<a href="/app/outlay/accuracy">How accurate is this? →</a>'
               '<a href="/app/outlay/estimate">Estimate your backlog →</a>'
               '<a href="/app/outlay/budgets">Budgets &amp; guardrails →</a>'
               '<span style="flex:1"></span>'
               '<span class=muted style="font-size:12.5px">Export CSV:</span>'
               '<a href="/app/outlay/export.csv?view=tickets">tickets</a>'
               '<a href="/app/outlay/export.csv?view=classes">work types</a>'
               '<a href="/app/outlay/export.csv?view=people">engineers</a></div>')
    bstrip = ""
    if statuses:
        over = [s for s in statuses if s["status"] == "over"]
        warn = [s for s in statuses if s["status"] == "warn"]
        if over or warn:
            c = "#b3261e" if over else "#b45309"
            parts = ([f"{len(over)} over budget"] if over else []) + ([f"{len(warn)} at warn"] if warn else [])
            bstrip = (f'<div class=card style="border-left:4px solid {c};margin-bottom:16px">'
                      f'<b style="color:{c}">⚠ {" · ".join(parts)}</b> — '
                      f'<a href="/app/outlay/budgets">review budgets →</a></div>')
        else:
            bstrip = (f'<div class=card style="border-left:4px solid #0f6b4f;margin-bottom:16px">'
                      f'<b style="color:#0f6b4f">✓ All {len(statuses)} budgets on track</b> — '
                      f'<a href="/app/outlay/budgets">budgets →</a></div>')
    sample = ""
    if report.get("_sample"):
        sample = ('<div class=card style="border-left:4px solid #2563eb;margin-bottom:16px;'
                  'display:flex;justify-content:space-between;align-items:center">'
                  '<span><b style="color:#2563eb">Sample data.</b> This is a worked example so you can see '
                  'the product end-to-end — not your real spend. '
                  '<a href="/app/outlay/connect">Connect your sources →</a></span>'
                  '<form method=post action="/app/outlay/clear" style="margin:0">'
                  '<button class="btn sec sm">Clear sample data</button></form></div>')
    body = kpis + sample + checklist + sync_line + bstrip + estlink + grid + '<div style="margin-top:16px">' + _outlay_connect(collapsed=True) + '</div>'
    return page("Spend", body, account, active="/app/outlay")


def outlay_connect_page(account: dict, conn: dict | None) -> str:
    """Live connectors — read-only tokens to pull a tracker + Anthropic usage."""
    conn = conn or {}
    tracker = conn.get("tracker") or "github"
    owner = _e(conn.get("github_owner") or "")
    repo = _e(conn.get("github_repo") or "")
    jbase = _e(conn.get("jira_base_url") or "")
    jemail = _e(conn.get("jira_email") or "")
    jjql = _e(conn.get("jira_jql") or "")
    sset = lambda k: "✓ saved" if conn.get(k) else "not set"  # noqa: E731
    opt = lambda v: " selected" if tracker == v else ""        # noqa: E731
    asy = conn.get("auto_sync_hours") or 0
    aopt = lambda v: " selected" if asy == v else ""           # noqa: E731
    synced = (f'Last synced {_fmt_date(conn.get("synced_at"))}.'
              if conn.get("synced_at") else "Never synced yet.")
    if asy:
        synced += f' Auto-sync is on ({"daily" if asy == 24 else "weekly"}).'
    err = conn.get("last_sync_error")
    err_banner = (f'<div class=card style="border-left:4px solid #b3261e;margin-bottom:16px">'
                  f'<b style="color:#b3261e">⚠ Last sync failed.</b> {_e(err)} '
                  f'<span class=muted style="font-size:12.5px">Fix the token/fields above and sync again.</span></div>'
                  if err else "")
    form = f"""<div class=hero><h1>Connect your sources <span class=muted style="font-weight:400">· read-only</span></h1>
      <p class=muted>Outlay pulls live from your tracker and AI usage with read-only tokens — metadata only,
        prompts never leave your tools. Or paste exports on the <a href="/app/outlay">Spend</a> tab.</p></div>
      {err_banner}
      <form method=post action="/app/outlay/connect" class=card>
        <label class=fld><span>Tracker</span><select name=tracker>
          <option value=github{opt('github')}>GitHub Issues</option>
          <option value=jira{opt('jira')}>Jira</option>
          <option value=linear{opt('linear')}>Linear</option></select></label>

        <h3 style="margin:1em 0 .6em">GitHub Issues</h3>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <label class=fld><span>Owner</span><input name=github_owner value="{owner}" placeholder="acme"></label>
          <label class=fld><span>Repo</span><input name=github_repo value="{repo}" placeholder="web"></label>
        </div>
        <label class=fld style="margin-top:12px"><span>Read-only token ({sset('github_token')})</span>
          <input name=github_token type=password placeholder="ghp_… (leave blank to keep)"></label>

        <h3 style="margin:1em 0 .6em">Jira</h3>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
          <label class=fld><span>Base URL</span><input name=jira_base_url value="{jbase}" placeholder="https://acme.atlassian.net"></label>
          <label class=fld><span>Email</span><input name=jira_email value="{jemail}" placeholder="you@acme.dev"></label>
        </div>
        <label class=fld style="margin-top:12px"><span>API token ({sset('jira_token')})</span>
          <input name=jira_token type=password placeholder="(leave blank to keep)"></label>
        <label class=fld style="margin-top:12px"><span>JQL (optional)</span>
          <input name=jira_jql value="{jjql}" placeholder="project = ENG AND updated >= -90d"></label>

        <h3 style="margin:1em 0 .6em">Linear</h3>
        <label class=fld><span>API key ({sset('linear_key')})</span>
          <input name=linear_key type=password placeholder="lin_… (leave blank to keep)"></label>

        <h3 style="margin:1em 0 .6em">AI usage <span class=muted style="font-weight:400">· connect one or both</span></h3>
        <label class=fld><span>Anthropic admin API key ({sset('anthropic_key')})</span>
          <input name=anthropic_key type=password placeholder="sk-ant-admin… (leave blank to keep)"></label>
        <label class=fld style="margin-top:12px"><span>Cursor admin API key ({sset('cursor_key')})</span>
          <input name=cursor_key type=password placeholder="key_… (Cursor team admin; leave blank to keep)"></label>

        <h3 style="margin:1em 0 .6em">Auto-sync</h3>
        <label class=fld><span>Keep the audit fresh automatically</span><select name=auto_sync_hours>
          <option value=0{aopt(0)}>Off — sync manually</option>
          <option value=24{aopt(24)}>Daily</option>
          <option value=168{aopt(168)}>Weekly</option></select></label>
        <button class="btn sec" style="margin-top:14px">Save connection</button>
      </form>
      <div class=card style="margin-top:16px">
        <p class=muted style="margin:.2em 0 .8em">{synced}</p>
        <button class="btn" onclick="outlaySync(this)">Sync now &amp; run the audit</button>
        <a class="btn sec" href="/app/outlay" style="margin-left:8px">View Spend →</a>
        <script>function outlaySync(btn){{btn.classList.add('loading');btn.disabled=true;
          fetch('/app/outlay/sync',{{method:'POST'}}).then(function(r){{return r.json();}}).then(function(d){{
            if(d.ok){{location.href='/app/outlay';}}else{{btn.classList.remove('loading');btn.disabled=false;
              alert(d.error||'Sync failed.');}}}})
          .catch(function(){{btn.classList.remove('loading');btn.disabled=false;alert('Network error.');}});}}
        </script>
      </div>"""
    return page("Connect", form, account, active="/app/outlay")


def estimate_backlog_page(account: dict, report: dict | None) -> str:
    """Budget planned work against the cost model learned from connected history."""
    if not (report and report.get("_model")):
        body = ('<div class=hero><h1>Estimate your backlog.</h1>'
                '<p class=muted>Budget planned work before it\'s built. Connect your data on the '
                '<a href="/app/outlay">Spend</a> tab first so Outlay can learn your cost model — then '
                'paste a backlog here.</p></div>'
                '<div class=card><a class="btn" href="/app/outlay">Go to Spend →</a></div>')
        return page("Estimate", body, account, active="/app/outlay")

    form = """<div class=card><h3 style="margin:.2em 0 .4em">Paste a planned backlog</h3>
      <p class=muted style="margin:.2em 0 .8em">A JSON list of items — each with a <b>title</b>, and ideally
        <b>requirements</b>, <b>design_docs</b>, and/or story <b>points</b>. The more scope you give, the tighter the estimate.</p>
      <textarea id=ol_plan rows=6 placeholder='{"items":[{"id":"PROJ-1","title":"Add SSO","requirements":"SAML + SCIM, multi-tenant, audit log","points":8}]}'></textarea>
      <button class="btn" style="margin-top:10px" onclick="estRun(this)">Estimate</button>
      <script>function estRun(btn){btn.classList.add('loading');btn.disabled=true;
        fetch('/app/outlay/estimate/run',{method:'POST',headers:{'content-type':'application/json'},
          body:JSON.stringify({planned:document.getElementById('ol_plan').value})})
        .then(function(r){return r.json();}).then(function(d){if(d.ok){location.reload();}else{
          btn.classList.remove('loading');btn.disabled=false;alert(d.error||'Could not estimate.');}})
        .catch(function(){btn.classList.remove('loading');btn.disabled=false;alert('Network error.');});}
      </script></div>"""

    est = report.get("estimate")
    result = ""
    if est:
        rows = ""
        for e in est.get("items", []):
            if e.get("costable"):
                val = money(e.get("expected_usd", 0))
                band = f'{money(e.get("low_usd", 0))}–{money(e.get("high_usd", 0))}'
                typ = _e(e.get("task_class")) + (f' · {_e(e.get("complexity_tier"))}' if e.get("complexity_tier") else "")
                conf = _e(e.get("confidence"))
            else:
                val, band, typ, conf = "—", "no history", _e(e.get("task_class")), "declined"
            rows += (f'<tr><td class=mono>{_e(e.get("id"))}</td><td>{typ}</td>'
                     f'<td style="text-align:right">{val}</td><td class=muted style="font-size:12px">{band}</td>'
                     f'<td class=muted style="font-size:12px">{conf}</td></tr>')
        tighten = ('<p class=muted style="font-size:12.5px;margin-top:8px">To tighten the estimate, add: '
                   + _e("; ".join(est.get("tighten", []))) + '</p>') if est.get("tighten") else ""
        result = (f'<div class=card style="margin-top:16px"><h3 style="margin:.2em 0 .4em">Backlog estimate</h3>'
                  f'<div style="font-size:28px;font-weight:700">{money(est.get("expected_usd", 0))}</div>'
                  f'<div class=muted>likely {money(est.get("low_usd", 0))}–{money(est.get("high_usd", 0))} · '
                  f'{est.get("items_costed", 0)} estimated, {est.get("items_unknown", 0)} declined</div>'
                  f'<table class=tbl style="width:100%;margin-top:10px"><thead><tr>'
                  f'<th style="text-align:left">Item</th><th style="text-align:left">Type</th>'
                  f'<th style="text-align:right">Estimate</th><th style="text-align:left">Range</th>'
                  f'<th style="text-align:left">Confidence</th></tr></thead><tbody>{rows}</tbody></table>{tighten}</div>')
    return page("Estimate", form + result, account, active="/app/outlay")


def _pct(x, digits: int = 0) -> str:
    try:
        return f"{float(x) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


def accuracy_page(account: dict, report: dict | None) -> str:
    """The honesty layer, front and center: how close our forecast lands on the
    customer's *own* closed tickets, measured leave-one-out. This is the #1
    customer question, so we lead with the measured number and never hide n."""
    head = ('<div class=hero><h1>How accurate is this?</h1>'
            '<p class=muted>We don\'t ask you to trust a vendor benchmark. Outlay back-tests its forecast '
            'on <b>your own closed tickets</b>, leave-one-out: hide a ticket, predict it from the rest, '
            'compare to what it actually cost. Below is that measured error — on your data.</p></div>')
    cal = (report or {}).get("calibration") or {}
    n = cal.get("n_evaluated", 0)
    if not report or n < 1:
        body = (head + '<div class=card><p class=muted>Not enough closed, attributed tickets yet to '
                'measure accuracy. Connect data on the <a href="/app/outlay">Spend</a> tab and let a few '
                'tickets close — accuracy appears here automatically once there\'s history to back-test.</p></div>')
        return page("Accuracy", body, account, active="/app/outlay")

    mdape, within = cal.get("mdape", 0), cal.get("within_p90", 0)
    grade_c = "#0f6b4f" if mdape <= 0.25 else ("#b45309" if mdape <= 0.5 else "#b3261e")
    low = ('<div class=card style="border-left:4px solid #b45309;margin-bottom:16px">'
           f'<b style="color:#b45309">Early read — {n} ticket(s) evaluated.</b> '
           'Treat these as directional until more work closes.</div>') if n < 12 else ""
    kpis = (
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:0 0 18px">'
        + _kpi("Median error (MdAPE)", _pct(mdape), "typical forecast vs actual", grade_c)
        + _kpi("Within the p90 band", _pct(within), "actuals at/under our high estimate",
               "#0f6b4f" if within >= 0.8 else "#b45309")
        + _kpi("Tickets back-tested", str(n), f"{_pct(cal.get('coverage',0))} of closed work")
        + "</div>")

    rows = ""
    for cc in cal.get("by_class", []):
        bias = cc.get("bias", 0)
        bias_txt = ("over-forecasts" if bias > 0.02 else "under-forecasts" if bias < -0.02 else "unbiased")
        bias_c = "#b45309" if abs(bias) > 0.15 else "#475569"
        rows += (f'<tr><td>{_e(cc.get("task_class"))}</td><td style="text-align:right">{cc.get("n",0)}</td>'
                 f'<td style="text-align:right">{_pct(cc.get("mdape",0))}</td>'
                 f'<td style="text-align:right">{_pct(cc.get("within_p90",0))}</td>'
                 f'<td style="color:{bias_c}">{bias_txt} ({_pct(bias,0)})</td></tr>')
    by_class = (f'<div class=card><h3 style="margin:.2em 0 .6em">Accuracy by work type</h3>'
                f'<table class=tbl style="width:100%"><thead><tr>'
                f'<th style="text-align:left">Work type</th><th style="text-align:right">n</th>'
                f'<th style="text-align:right">Median err</th><th style="text-align:right">Within p90</th>'
                f'<th style="text-align:left">Bias</th></tr></thead><tbody>{rows}</tbody></table>'
                f'<p class=muted style="font-size:12px;margin-top:10px">Bias is the average signed error: '
                f'positive means we tend to over-forecast (you\'ll likely spend less), negative the reverse.</p></div>')

    size = cal.get("size") or {}
    size_card = ""
    if size.get("n"):
        if size.get("improves"):
            size_card = (f'<div class=card style="margin-top:16px;border-left:4px solid #0f6b4f">'
                         f'<b style="color:#0f6b4f">Story points help.</b> Conditioning on size cuts median '
                         f'error by {_pct(size.get("error_reduction",0))} vs work-type alone '
                         f'({_pct(size.get("mdape_size",0))} vs {_pct(size.get("mdape_class",0))}, n={size.get("n",0)}). '
                         f'Keep estimating points and forecasts tighten.</div>')
        else:
            size_card = (f'<div class=card style="margin-top:16px"><b>Story points aren\'t adding signal yet</b> '
                         f'on your data (size {_pct(size.get("mdape_size",0))} vs work-type {_pct(size.get("mdape_class",0))}). '
                         f'We fall back to the work-type model, which is doing as well or better.</div>')

    foot = ('<p class=muted style="font-size:12.5px;margin-top:16px">Method: leave-one-out back-test over '
            'closed, ticket-attributed work. We never score a ticket using its own cost. As more work '
            'closes, the sample grows and this number sharpens — re-checked on every sync.</p>')
    return page("Accuracy", head + low + kpis + by_class + size_card + foot, account, active="/app/outlay")


def budgets_page(account: dict, report: dict | None, statuses: list[dict],
                 projects: list[dict] | None = None) -> str:
    """Set budgets by scope and see spend-vs-budget with pace projection."""
    colors = {"ok": "#0f6b4f", "warn": "#b45309", "over": "#b3261e"}
    note = "" if report else ('<div class=card><p class=muted>Connect data on the '
                              '<a href="/app/outlay">Spend</a> tab to see live status.</p></div>')
    rows = ""
    for s in statuses:
        c = colors.get(s["status"], "#0f6b4f")
        name = _e(s["scope_type"]) + (f': {_e(s["scope_id"])}' if s.get("scope_id") else "")
        w = min(max(s.get("pct_used", 0), 0), 1) * 100
        rows += (f'<div class=card style="margin-top:10px"><div style="display:flex;justify-content:space-between;align-items:baseline">'
                 f'<b>{name}</b><span class="pill" style="background:{c}22;color:{c}">{_e(s["status"])}</span></div>'
                 f'<div style="height:8px;border-radius:5px;background:#eee;overflow:hidden;margin:8px 0 6px">'
                 f'<span style="display:block;height:100%;width:{w:.0f}%;background:{c}"></span></div>'
                 f'<div class=muted style="font-size:13px">{money(s.get("spent_usd",0))} of {money(s["limit_usd"])} '
                 f'this window · projected <b style="color:{c}">{money(s.get("projected_usd",0))}</b> over {int(s.get("period_days") or 30)} days'
                 f'<form method=post action="/app/outlay/budgets/delete" style="display:inline;margin-left:10px">'
                 f'<input type=hidden name=id value="{s["id"]}">'
                 f'<button class="btn sec sm">Remove</button></form></div></div>')
    if not statuses:
        rows = '<p class=muted>No budgets yet — add one below.</p>'
    # Project/epic pick-list so users know which keys they can budget against.
    pref = ""
    if projects:
        chips = "".join(
            f'<span class="pill" style="background:#13203a11;margin:0 6px 6px 0;display:inline-block">'
            f'<span class=mono>{_e(p["project"])}</span> · {money(p.get("spent_usd",0))}</span>'
            for p in projects[:12])
        pref = (f'<div class=card style="margin-top:16px"><h3 style="margin:.2em 0 .4em">Spend by project / epic</h3>'
                f'<p class=muted style="font-size:13px;margin:.2em 0 .8em">Budget any of these by choosing '
                f'<b>Project / epic</b> below and pasting the key.</p>{chips}</div>')
    add = """<div class=card style="margin-top:16px"><h3 style="margin:.2em 0 .6em">Add a budget</h3>
      <form method=post action="/app/outlay/budgets">
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:10px;align-items:end">
          <label class=fld><span>Scope</span><select name=scope_type>
            <option value=overall>Overall</option><option value=team>Team</option>
            <option value=class>Work type</option><option value=project>Project / epic</option></select></label>
          <label class=fld><span>Scope id (team / type / key)</span><input name=scope_id placeholder="platform / bugfix / PROJ"></label>
          <label class=fld><span>Limit (USD)</span><input name=limit_usd type=number step=any placeholder="5000"></label>
          <label class=fld><span>Period (days)</span><input name=period_days type=number value=90></label>
        </div>
        <button class="btn" style="margin-top:12px">Add budget</button>
      </form></div>"""
    add = pref + add
    head = ('<div class=hero><h1>Budgets &amp; guardrails.</h1>'
            '<p class=muted>Set a budget by scope; Outlay projects your spend to the period and flags it '
            '<b>before</b> you go over — not at month-end.</p></div>')
    return page("Budgets", head + note + rows + add, account, active="/app/outlay")


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
    <p class=muted>Live health of Outlay services. Your gateway always
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
      <p class=muted>Outlay routes each request to the cheapest model that's provably
      good enough. Drop-in proxy, no prompt data leaves your system. Start free for 7 days;
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
               'I agree to the <a href="https://outlay-ai.com/legal/terms.html" target=_blank>Terms</a>'
               ' and <a href="https://outlay-ai.com/legal/privacy.html" target=_blank>Privacy Policy</a>.'
               '</label></div>') if is_signup else ""
    beta = ('<p class="small muted center" style="margin-top:10px">Outlay is in early access — '
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
        <div class="small muted">{dual_metric(cycle['savings'], suffix="")} saved · {pct_life}% lifetime · {int(cycle['requests']):,} req · {int(cycle['routed']):,} routed</div></div>
      {_quality_card_top(proof, cycle)}
      <div class=card><div class=label>{'Your bill this cycle' if bill['is_paid'] else 'Projected bill (free during trial)'}</div>
        <div class=stat>{money(bill['would_bill'])}</div>
        <div class="small muted">{int(bill['rate']*100)}% of savings · you keep {money(bill['cycle_savings']-bill['would_bill'])}</div></div>
    </div>
    {_caching_card(cycle)}
    {_opportunity_card(cycle)}

    <h2>Routing mode</h2>
    <div class=card>{mode_toggle(mode, plan.get("plan") == "paid")}
      <p class="small muted" style="margin-top:10px">Guidance recommends switches without changing traffic;
      autopilot applies them automatically. Change takes effect on your gateway within seconds.</p>
      {_autopilot_ramp(int(settings.get('autopilot_pct', 100)), mode)}
    </div>

    <div class="grid cols-2" style="margin-top:16px">
      <div class=card><div class=label>Baseline vs. actual (this cycle)</div>
        {_compare_bars(cycle['baseline'], cycle['actual'])}</div>
      {_proof_card(proof)}
    </div>
    {(' <div style="margin-top:16px">' + _budget_card(budget) + '</div>') if (budget and budget.get('enabled')) else ''}

    <h2>Savings by task type <span class="small muted">— where the money comes from</span></h2>
    {_category_savings(cats)}
    {_feedback_widget()}

    <div class=card style="margin-top:16px"><div class=label>Your connection</div>
      <p class="small muted">Point your gateway at Outlay with this deployment id:</p>
      <p><code>{_e(deployment['deployment_id'])}</code></p>
      <div class=row><a class="btn sec sm" href="/app/connect">Configuration &amp; deployments</a>
        <a class="btn sec sm" href="/app/logs">View request logs</a>
        <a class="btn sec sm" href="/app/estimate">Savings projection</a></div></div>
    {metric_toggle_assets()}"""
    return page("Home", body, account, "/app")


# Projector JS (plain string — NOT an f-string — to avoid brace escaping). Mirrors
# the public /estimator.html logic; seeded with the customer's real baseline spend.
_PROJECTOR_JS = """<script>(function(){
  var B={"claude-haiku-4-5":3,"claude-sonnet-4-6":9,"claude-opus-4-8":15,"claude-fable-5":30};
  var R={routine:0.65,mixed:0.45,complex:0.25}, CONSERV=0.7, FLOOR="claude-haiku-4-5", FEE=0.20;
  function money(x){return "$"+Math.round(x).toLocaleString();}
  function go(){
    var spend=Math.max(0,parseFloat((document.getElementById("pspend")||{}).value)||0);
    var model=(document.getElementById("pmodel")||{}).value||"claude-opus-4-8";
    if(model==="unsure")model="claude-opus-4-8";
    var prof=((document.querySelector('input[name=pprofile]:checked'))||{}).value||"mixed";
    var el=document.getElementById("presult"); if(!el)return;
    var base=B[model],target=B[FLOOR],r=R[prof];
    if(model==="claude-haiku-4-5"||base<=target){el.innerHTML='<div class="small muted">You\\'re already on the cheapest tier — model-routing won\\'t cut much. Prompt caching + the Batch API may still help (we capture those too).</div>';return;}
    var redu=1-target/base, hi=spend*r*redu, lo=hi*CONSERV;
    el.innerHTML='<div class="stat green">'+money(lo)+'–'+money(hi)+'<span class="small muted">/mo</span></div>'+
      '<div class="small muted">projected savings — ~'+Math.round(lo/spend*100||0)+'–'+Math.round(hi/spend*100||0)+'% of bill · you keep ~'+money((lo+hi)/2*(1-FEE))+'/mo after the 20% fee</div>';
  }
  document.addEventListener("input",go);document.addEventListener("change",go);go();
})();</script>"""


def estimate_page(account: dict, plan: dict, cycle: dict, lifetime: dict, bill: dict) -> str:
    """Logged-in savings view: MEASURED savings from the customer's own traffic +
    an annualized run-rate, plus a what-if projector seeded with their real baseline."""
    rate = float(bill.get("rate", 0.20))
    base_m = float(cycle.get("baseline") or 0.0)      # this cycle's baseline spend (~monthly)
    saved_m = float(cycle.get("savings") or 0.0)
    reqs = int(cycle.get("requests") or 0)
    has = reqs > 0 and base_m > 0
    if has:
        pct = round(100 * saved_m / base_m)
        ann_saved = saved_m * 12
        ann_net = ann_saved * (1 - rate)
        measured = f"""<div class="grid cols-3">
      <div class=card><div class=label>Measured savings this cycle</div>
        <div class="stat green">{money(saved_m)}</div>
        <div class="small muted">{pct}% off your baseline of {money(base_m)}</div></div>
      <div class=card><div class=label>Annualized at this run-rate</div>
        <div class="stat green">{money(ann_saved)}<span class="small muted">/yr</span></div>
        <div class="small muted">you keep ~{money(ann_net)}/yr after the {int(rate*100)}% fee</div></div>
      <div class=card><div class=label>Proven on</div>
        <div class=stat>{reqs:,}</div>
        <div class="small muted">requests this cycle · measured vs a held-out control arm</div></div>
    </div>
    <p class="small muted">These are <b>measured</b>, not estimated — computed from your own traffic.</p>"""
        seed = int(round(base_m))
    else:
        measured = ('<div class="note">No routed traffic yet — connect your gateway to measure real '
                    'savings. Use the projector below to see the potential, then connect to prove it.</div>')
        seed = 5000
    models = [("claude-opus-4-8", "Claude Opus 4.8"), ("claude-fable-5", "Claude Fable 5"),
              ("claude-sonnet-4-6", "Claude Sonnet 4.6"), ("claude-haiku-4-5", "Claude Haiku 4.5"),
              ("unsure", "Not sure / a mix")]
    model_opts = "".join(f'<option value="{v}">{_e(l)}</option>' for v, l in models)
    body = f"""
    <h1>Savings projection</h1>
    {measured}
    <h2>What-if projector</h2>
    <div class=card>
      <p class="small muted">Model a different spend or task mix. {'Seeded with your measured baseline.' if has else 'Estimate only — connect to measure it for real.'}</p>
      <div class="grid cols-2">
        <div class=field><label>Monthly Claude spend (USD)</label>
          <input id=pspend type=number min=0 step=50 value="{seed}"></div>
        <div class=field><label>Main model today</label>
          <select id=pmodel>{model_opts}</select></div>
      </div>
      <div class=field><label>Traffic profile</label>
        <label class=row style="font-weight:400"><input type=radio name=pprofile value=routine style="width:auto;margin-right:8px"> Mostly routine (classification, extraction, summaries, simple Q&amp;A)</label>
        <label class=row style="font-weight:400"><input type=radio name=pprofile value=mixed checked style="width:auto;margin-right:8px"> A mix</label>
        <label class=row style="font-weight:400"><input type=radio name=pprofile value=complex style="width:auto;margin-right:8px"> Mostly complex reasoning / coding / agents</label>
      </div>
      <div id=presult style="margin-top:10px"></div>
      <p class="small muted" style="margin-top:10px">Routable traffic is priced at Claude Haiku list rates (blended); the low end assumes a real router captures ~70% of the headroom and quality floors keep hard tasks on the top model. A projection — your exact number is measured on your traffic.</p>
    </div>
    <div class=row style="margin-top:14px"><a class="btn sec sm" href="/app/connect">Configuration &amp; connect</a>
      <a class="btn sec sm" href="/app">Back to dashboard</a></div>
    {_PROJECTOR_JS}"""
    return page("Savings projection", body, account, "/app")


def _quality_card_top(proof: dict, cycle: dict) -> str:
    """First-class quality metric for the top of the dashboard — equal billing with
    savings. Leads with the measured non-inferiority rate when available; otherwise
    shows that quality is actively protected on every request (floor + auto-escalation)."""
    comp = proof.get("comparisons") or 0
    rate = proof.get("rate")
    routed = int(cycle.get("routed") or 0)
    esc = int(cycle.get("escalations") or 0)
    if comp and rate is not None:
        pct = 100 * rate
        return (f'<div class=card><div class=label>Quality preserved</div>'
                f'<div class="stat green">{pct:.0f}%</div>'
                f'<div class="small muted">non-inferior to the top model across '
                f'{int(comp):,} side-by-side checks · {esc:,} auto-escalations this cycle</div></div>')
    return ('<div class=card><div class=label>Quality preserved</div>'
            '<div class="stat green">Protected</div>'
            f'<div class="small muted">quality floor + auto-escalation guard every request '
            f'({esc:,} escalated of {routed:,} routed this cycle). Run '
            f'<code>modelpilot compare</code> for a measured non-inferiority rate.</div></div>')


def _opportunity_card(cycle: dict) -> str:
    """Realization callout: additional savings the gateway found beyond model routing
    (uncached reusable prompts, latency-tolerant traffic) but that aren't captured
    yet. Estimated, never billed — only realized savings bill."""
    opp = float(cycle.get("opportunity") or 0.0)
    if opp <= 0:
        return ""
    return (f'<div class=card style="margin-top:16px;border-left:3px solid var(--accent)">'
            f'<div class=label>Additional potential savings this cycle</div>'
            f'<div class=stat>{money(opp)}</div>'
            f'<div class="small muted">Money left on the table <i>beyond</i> model routing — mostly '
            f'uncached reusable prompts and latency-tolerant traffic that could use the Batch API. '
            f'Your gateway flags these per request (<code>x-modelpilot-opportunity-*</code> response '
            f'headers); enabling them captures the savings with no quality change. Estimate only — '
            f'never billed.</div></div>')


def _caching_card(cycle: dict) -> str:
    """Goodwill callout: savings we captured for free by auto-applying prompt
    caching. Measured exactly from your token usage; never billed."""
    cached = float(cycle.get("caching") or 0.0)
    if cached <= 0:
        return ""
    return (f'<div class=card style="margin-top:16px;border-left:3px solid var(--ok,#16a34a)">'
            f'<div class=label>Caching savings captured this cycle</div>'
            f'<div class="stat green">{money(cached)}</div>'
            f'<div class="small muted">Delivered free by auto-applying prompt caching on your '
            f'reusable prompts — measured exactly from your token usage (cache reads bill at ~10% '
            f'of input price). <b>Never billed</b> — this one\'s on us.</div></div>')


def _autopilot_ramp(pct: int, mode: str) -> str:
    """Gradual autopilot rollout control — auto-route a chosen share of eligible
    traffic, ramping up as trust builds. Only takes effect in autopilot."""
    presets = [10, 25, 50, 100]
    active = mode == "autopilot"
    btns = "".join(
        f'<button name=autopilot_pct value="{p}" class="btn sm{"" if p==pct else " sec"}"'
        f' style="margin-right:6px">{p}%</button>'
        for p in presets)
    if active:
        note = (f"Autopilot is auto-routing <b>{pct}%</b> of eligible traffic. "
                "Start low to build confidence, then ramp to 100% — held-back requests "
                "are still recommended, just not auto-applied.")
    else:
        note = ("Choose how much traffic Autopilot will auto-route once you enable it. "
                "Ramp up gradually as you build trust.")
    op = "" if active else ' style="opacity:.55"'
    return (f'<div class=field{op}><label style="margin-top:6px">Autopilot rollout</label>'
            f'<form method=post action="/app/autopilot">{btns}</form>'
            f'<p class="small muted" style="margin-top:8px">{note}</p></div>')


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
    <div style="margin-top:10px"><div class="row small"><span>Actual (with Outlay)</span>
      <div class=spacer></div><span class=muted>{money(actual)}</span></div>
      <div class=bar><span style="width:{aw:.0f}%"></span></div></div>"""


def mode_toggle(current: str, paid: bool = False) -> str:
    opts = [
        ("guidance", "Guidance", "Recommend cheaper models; you stay in control. (Free trial only.)"),
        ("autopilot", "Autopilot", "Auto-route to the cheapest good-enough model."),
    ]
    if paid:  # paid plans are autopilot-only — guidance is a trial-only "try it first" mode
        opts = [o for o in opts if o[0] != "guidance"]
    btns = "".join(
        f'<button name=mode value="{v}" class="{"on" if v==current else ""}">'
        f'<b>{_e(lbl)}</b><span class=small>{_e(desc)}</span></button>'
        for v, lbl, desc in opts)
    note = ('<p class="small muted" style="margin-top:8px">Guidance is available during the free trial; '
            'paid plans run on autopilot.</p>') if paid else ""
    return f'<form method=post action="/app/mode"><div class=modes>{btns}</div></form>{note}'


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
      {mode_toggle(settings['mode'], store.get_plan(account["id"]).get("plan") == "paid")}
      {_autopilot_ramp(int(settings.get('autopilot_pct', 100)), settings['mode'])}
    </div>
    <div class=card style="margin-top:16px">
      <form method=post action="/app/settings">
        <h2 style="margin-top:0">Routing policy</h2>
        <div class=field><label>Risk tolerance</label>
          <select name=risk>{risk_opts}</select>
          <p class="small muted">Conservative keeps a higher confidence gate; aggressive routes more.</p></div>
        <div class=field><label>Minimum model (quality floor)</label>
          <select name=min_model>{model_opts}</select>
          <p class="small muted">Outlay will never route below this model, whatever the classifier says.</p></div>
        <div class=field><label class=row>
          <input type=checkbox name=telemetry_opt_in value=1 {"checked" if settings["telemetry_opt_in"] else ""}
            style="width:auto;margin-right:8px"> Share anonymous, aggregate performance telemetry</label>
          <p class="small muted">Counts and dollars only — never prompt text. Helps us tune routing for your traffic.</p></div>
        <h2>Spend budget</h2>
        <div class=field><label>Monthly spend budget (USD, 0 = no cap)</label>
          <input name=monthly_budget type=number step="0.01" min="0" value="{settings.get('monthly_budget') or 0:g}">
          <p class="small muted">Your model spend through Outlay this cycle. We email you when you cross the alert threshold and again if you go over.</p></div>
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
        <div class=field><label>What made you leave? <span class="small muted">(optional, helps us a lot)</span></label>
          <textarea name=reason rows=2 placeholder="e.g. savings weren't enough / too hard to set up / quality concern"></textarea></div>
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
    changes). We POST JSON signed with <code>X-Outlay-Signature: sha256=…</code> (HMAC of the body
    with the webhook's signing secret).</p>
    {table}
    <div class=card style="margin-top:12px">
      <form method=post action="/app/webhooks" class=row style="gap:8px">
        <input name=url placeholder="https://your-app.com/hooks/outlay" style="min-width:280px">
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
    welcome = ('<div class=note style="margin-bottom:18px"><b>Welcome to Outlay 👋</b> '
               'Let\'s get you connected — it takes about five minutes. Once your first requests '
               'flow through, your <a href="/app">Home dashboard</a> lights up with savings.</div>'
               if not keys else "")
    body = f"""
    <h1>Configuration</h1>
    {welcome}
    <p class=muted>Outlay is a drop-in proxy for the Claude Messages API. Point your SDK at it —
    only a task category + numeric features ever leave your system, never prompt text or your API key.</p>
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
    <p class="small muted">Run Outlay in more than one app or environment (staging, prod, a second
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
    {_tuning_capture_section(account)}"""
    return page("Configuration", body, account, "/app/connect")


def _tuning_capture_section(account: dict) -> str:
    """Per-customer tuning — gated to the Self-optimize / Managed tiers. Tuning is
    driven by traffic metadata only (no prompt content ever reaches us)."""
    tier = store.get_tier(account["id"])
    if tier == "payg":
        return ("""
    <h2>Per-customer tuning <span class="small muted">— Self-optimize plan</span></h2>
    <div class=card>
      <p class="small muted">On the <b>Self-optimize</b> plan, Outlay tunes routing to <b>your</b>
        workload — learning per-category quality floors from your own traffic (category labels, token
        counts, routing outcomes — <b>never prompt content</b>) and proposing safe, judge-validated
        changes you approve. It gets cheaper-safe the more you use it.</p>
      <a class="btn sm" href="/app/billing">See plans</a>
    </div>""")
    return ("""
    <h2>Per-customer tuning <span class="small muted">— active on your plan</span></h2>
    <div class=card>
      <p class="small muted">Outlay continuously tunes routing to <b>your</b> workload from your
        traffic metadata — category labels, token counts, and routing outcomes — <b>never prompt
        content</b>. Proposed per-category floor changes appear for you to review and approve; nothing
        to install. See <a href="/security.html#optimize">how we optimize without seeing your data</a>.</p>
    </div>""")


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
          cost, and routed/escalated flags. Prompt text and outputs never leave your system.</p>
        <div class=card><p class="muted">No logs yet. They're <b>opt-in</b>: run your gateway with
          <code>MODELPILOT_LOGS=1</code> (ships metadata to the console) and/or
          <code>MODELPILOT_OTEL_ENDPOINT=…</code> (exports OTLP traces to your own collector).
          See the <a href="https://outlay-ai.com/docs/configuration.html">docs</a>.</p></div>"""
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
      (<a href="https://outlay-ai.com/docs/configuration.html">docs</a>).</p>"""
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
    tier = plan.get("tier") or "payg"
    tier_badge = f'<span class="badge admin">{_e(store.TIER_LABELS.get(tier, tier))}</span>'
    status_badge = (('<span class="badge paid">Paid plan</span>' if is_paid else
                    (f'<span class="badge trial">Trial · {trial["days_left"]}d left</span>'
                     if trial["active"] else '<span class="badge suspended">Trial ended</span>')) + " " + tier_badge)
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
    {_tier_decision_panel(bill, tier)}
    {_tier_options(plan, stripe_on)}
    <div class=card style="margin-top:16px">
      <div class=label>How billing works</div>
      <p class="small muted">We meter the realized savings on every routed request (baseline cost minus
      actual cost — dollars only, never prompt content). Your bill each cycle is {int(bill['rate']*100)}%
      of that. Lifetime savings delivered: <b>{money(bill['lifetime_savings'])}</b>.</p>
    </div>"""
    return page("Billing", body, account, "/app/billing")


# Self-optimize uplift: how much MORE the bill is cut when routing is tuned on the
# customer's own traffic vs. the global PAYG floors. Range is honest/illustrative —
# the exact figure is measured on each customer's own data once they're on the tier.
# (Methodology + measurement in modelpilot/SELF_OPTIMIZE_EVAL.md.)
SELFOPT_UPLIFT_LO = 0.15
SELFOPT_UPLIFT_HI = 0.35
SELFOPT_FEE = 99.0
_PAYG_RATE, _SUB_RATE = 0.20, 0.15


def _tier_decision_panel(bill: dict, current_tier: str) -> str:
    """Personalized PAYG-vs-Self-optimize comparison from the customer's own savings,
    so they can decide with real numbers. Two value drivers, both shown: the rate cut
    (20%->15%, guaranteed) and the tuning uplift (estimated 15-35% more savings)."""
    S = float(bill.get("cycle_savings") or 0.0)
    u_mid = (SELFOPT_UPLIFT_LO + SELFOPT_UPLIFT_HI) / 2
    breakeven = SELFOPT_FEE / ((1 + u_mid) * (1 - _SUB_RATE) - (1 - _PAYG_RATE))
    if S < 1:
        return (f'<div class=card style="margin-top:16px"><div class=label>Which tier is right for you?</div>'
                f'<p class="small muted">Once you have a billing cycle of routed traffic, a personalized '
                f'comparison appears here. Rule of thumb: <b>Pay-as-you-go</b> (20% of savings, no fee) is best '
                f'while you ramp; <b>Self-optimize</b> ($99/mo + 15%) pulls ahead once your monthly savings clear '
                f'~{money(breakeven)} — it both cuts the rate <i>and</i> tunes routing on your own traffic for an '
                f'estimated {int(SELFOPT_UPLIFT_LO*100)}–{int(SELFOPT_UPLIFT_HI*100)}% more savings.</p></div>')
    payg_keep = (1 - _PAYG_RATE) * S
    rate_only = (1 - _SUB_RATE) * S - SELFOPT_FEE                 # guaranteed: rate cut, zero tuning uplift
    keep_lo = (1 - _SUB_RATE) * S * (1 + SELFOPT_UPLIFT_LO) - SELFOPT_FEE
    keep_hi = (1 - _SUB_RATE) * S * (1 + SELFOPT_UPLIFT_HI) - SELFOPT_FEE
    delta_mid = ((keep_lo + keep_hi) / 2) - payg_keep
    verdict = ("Self-optimize likely nets you more" if delta_mid > 0
               else "Pay-as-you-go is likely the better deal for now")
    sign = "+" if delta_mid >= 0 else "−"
    return f"""<div class=card style="margin-top:16px">
      <div class=label>Which tier is right for you? <span class="small muted">— from your own savings</span></div>
      <p class="small muted" style="margin:6px 0 12px">Your savings this cycle: <b>{money(S)}</b>. Self-optimize has
      two effects: a <b>guaranteed rate cut</b> (20% → 15%) and an <b>estimated {int(SELFOPT_UPLIFT_LO*100)}–{int(SELFOPT_UPLIFT_HI*100)}%
      more savings</b> from tuning routing on your own traffic.</p>
      <table><thead><tr><th>Plan</th><th>You keep this cycle</th></tr></thead><tbody>
        <tr><td>Pay-as-you-go (20%, no fee)</td><td>{money(payg_keep)}</td></tr>
        <tr><td>Self-optimize — rate cut only (worst case)</td><td>{money(rate_only)}</td></tr>
        <tr><td>Self-optimize — with {int(SELFOPT_UPLIFT_LO*100)}–{int(SELFOPT_UPLIFT_HI*100)}% tuning uplift</td>
            <td>{money(keep_lo)} – {money(keep_hi)}</td></tr>
      </tbody></table>
      <p class="small muted" style="margin-top:10px"><b>{_e(verdict)}</b> — about <b>{sign}{money(abs(delta_mid))}</b>/cycle
      vs pay-as-you-go at the midpoint estimate. The uplift range is illustrative; your <i>exact</i> figure is
      measured on your own traffic (held-out control arm) once you switch — never a guess after the fact.</p>
    </div>"""


def _tier_options(plan: dict, stripe_on: bool) -> str:
    """The three pricing tiers with switch/upgrade controls; current tier marked."""
    current = plan.get("tier") or "payg"
    defs = [
        ("payg", "Pay-as-you-go", "20% of savings",
         "No subscription — pure pay-for-savings."),
        ("self_optimize", "Self-optimize", "$99/mo + 15%",
         "Routing tuned to your own traffic (metadata only — never your content)."),
        ("managed", "Managed", "Subscription + 15%",
         "We continuously tune routing to your traffic for you (metadata only). Subscription pricing coming soon."),
    ]
    cards = ""
    for key, name, price, desc in defs:
        if key == current:
            ctl = '<span class="badge paid">Current plan</span>'
        else:
            label = "Switch" if key == "payg" else "Upgrade"
            ctl = (f'<form method=post action="/app/billing/convert" style="margin:0">'
                   f'<input type=hidden name=tier value="{key}">'
                   f'<button class="btn sm">{label}</button></form>')
        cards += (f'<div class=card style="margin:0"><div class=label>{_e(name)}</div>'
                  f'<div class=stat style="font-size:21px">{_e(price)}</div>'
                  f'<p class="small muted" style="min-height:54px">{_e(desc)}</p>{ctl}</div>')
    return f'<h2 style="margin-top:22px">Plans</h2><div class="grid cols-3">{cards}</div>'


# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #

def _feedback_widget() -> str:
    return ('<div class=card style="margin-top:16px"><div class=label>How\'s Outlay working for you?</div>'
            '<form method=post action="/app/feedback" class=row '
            'style="gap:8px;flex-wrap:wrap;align-items:center;margin-top:8px">'
            '<button name=rating value=up class="btn sm sec" title="Going well">&#128077;</button>'
            '<button name=rating value=down class="btn sm sec" title="Not great">&#128078;</button>'
            '<input name=comment placeholder="Anything we should know? (optional)" '
            'style="flex:1;min-width:220px;padding:8px 10px;border:1px solid var(--line);border-radius:8px">'
            '<button class="btn sm">Send</button></form>'
            '<p class="small muted" style="margin-top:6px">Goes straight to the founder — just your note, '
            'never any prompt content.</p></div>')


def _funnel_panel(funnel: dict | None) -> str:
    if not funnel:
        return ""
    su = funnel["signed_up"] or 1
    stages = [("Signed up", funnel["signed_up"]), ("Set up (key)", funnel["set_up"]),
              ("Routed traffic", funnel["routed"]), ("Proven savings", funnel["proven"]),
              ("Paid", funnel["paid"])]
    cells = "".join(
        f'<div style="text-align:center;min-width:96px"><div class=stat>{n}</div>'
        f'<div class="small muted">{_e(lbl)}<br>{round(100*n/su)}%</div></div>'
        for lbl, n in stages)
    return ('<h2>Activation funnel</h2><div class=card>'
            f'<div class=row style="gap:24px;flex-wrap:wrap;align-items:flex-end">{cells}</div>'
            '<p class="small muted" style="margin-top:10px">% of signups. The gap into '
            '<b>Proven savings</b> is the activation (aha) moment; the gap into <b>Paid</b> is the '
            'willingness-to-pay signal — the question our whole model rests on.</p></div>')


def _feedback_panel(feedback: list[dict] | None) -> str:
    if not feedback:
        return '<h2>Recent feedback</h2><div class=card><p class=muted>No feedback yet.</p></div>'
    trs = ""
    for r in feedback:
        rate = {"up": "&#128077;", "down": "&#128078;"}.get(r.get("rating") or "", "")
        trs += (f'<tr><td class="small muted">{_fmt_date(r["ts"])}</td>'
                f'<td>{_e(r.get("email") or "—")}</td><td class="small">{_e(r["kind"])}</td>'
                f'<td>{rate}</td><td>{_e(r.get("comment") or "")}</td></tr>')
    return ('<h2>Recent feedback</h2><div class=card style="padding:0"><table>'
            '<thead><tr><th>When</th><th>Account</th><th>Kind</th><th>Rating</th><th>Comment</th></tr></thead>'
            f'<tbody>{trs}</tbody></table></div>')


def admin_overview(account: dict, rev: dict, rows: list[dict], pending: int = 0,
                   funnel: dict | None = None, feedback: list[dict] | None = None) -> str:
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
          <td><b>{r.get('cycle_pct', 0)}%</b></td>
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
      <div class=card><div class=label>Bill cut delivered (cycle)</div>
        <div class="stat green">{rev.get('cycle_pct', 0)}%</div>
        <div class="small muted">{dual_metric(rev['cycle_savings'], suffix="")} saved · lifetime {rev.get('total_pct', 0)}%</div></div>
    </div>
    <div class="grid cols-2" style="margin-top:16px">
      <div class=card><div class=label>Accounts</div>
        <div class=stat>{rev['n_accounts']}</div>
        <div class="small muted">{rev['n_paid']} paid · {rev['n_trial']} trial · {rev['n_suspended']} suspended</div></div>
      {pending_card}
    </div>
    {_funnel_panel(funnel)}
    <h2>Customers</h2>
    <div class=card style="padding:0">
      <table><thead><tr><th>Account</th><th>Plan</th><th>Lifetime savings</th>
        <th>Savings (cycle)</th><th>Cut (cycle)</th><th>Revenue (cycle)</th><th>Joined</th></tr></thead>
        <tbody>{trs or '<tr><td colspan=7 class="muted">No accounts yet.</td></tr>'}</tbody></table>
    </div>
    {_feedback_panel(feedback)}
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
