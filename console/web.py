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
/* Outlay console — matches the marketing site theme (outlay.css): cool
   slate-white canvas, green accent, Inter, dark public header. */
:root{--ink:#0b0f17;--body:#3a4252;--muted:#6b7280;--faint:#9aa1ad;
  --line:#e4e7ec;--line2:#eef1f5;--bg:#ffffff;--paper:#f6f8fa;--paper2:#eef1f5;--navy:#13203a;
  --grn:#0f6b4f;--grn-d:#0a4f3a;--grn-l:#e7f1ec;--warn:#b45309;--bad:#b3261e;
  --mut:#6b7280;--amber:#b45309;--amber-l:#fbf0df;--red:#b3261e;--red-l:#f8e7e4;
  --accent:#0f6b4f;--accent-d:#0a4f3a;--grad:linear-gradient(135deg,#0f6b4f,#13203a);
  --disp:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --sans:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --ease:cubic-bezier(.22,.61,.36,1);}
*{box-sizing:border-box}
body{margin:0;font:16px/1.6 var(--sans);color:var(--body);-webkit-font-smoothing:antialiased;
  background:linear-gradient(180deg,var(--paper),var(--bg) 60%);background-attachment:fixed}
a{color:var(--grn-d);text-decoration:none}a:hover{text-decoration:underline}
.top{background:rgba(11,16,26,.82);backdrop-filter:blur(10px);border-bottom:1px solid rgba(255,255,255,.08);position:sticky;top:0;z-index:10}
.top .wrap{max-width:1080px;margin:0 auto;padding:12px 20px;display:flex;align-items:center;gap:18px}
.top .brand{color:#fff}.top .brand .dot{color:#6ee7b7}
.top .nav a{color:#c4cddb}.top .nav a:hover{color:#fff}
/* left sidebar shell (signed-in) */
.shell{display:flex;min-height:100vh;align-items:stretch}
.side{width:236px;flex-shrink:0;display:flex;flex-direction:column;padding:18px 14px;
  border-right:1px solid var(--line);background:var(--paper);
  position:sticky;top:0;height:100vh}
.side .brand{padding:6px 10px 2px;font-size:21px}
.sidenav{display:flex;flex-direction:column;gap:2px;margin-top:18px}
.sidenav a{color:var(--muted);padding:9px 12px;border-radius:8px;font-weight:500;font-size:14.5px;
  transition:background .15s,color .15s}
.sidenav a:hover{color:var(--ink);background:var(--paper2);text-decoration:none}
.sidenav a.on{color:var(--grn-d);background:var(--grn-l);font-weight:600}
.navgrp{font-family:var(--mono);font-size:11px;text-transform:uppercase;letter-spacing:.06em;color:var(--faint);margin:18px 0 6px 12px}
.side-foot{margin-top:auto;padding-top:14px;border-top:1px solid var(--line)}
.side-foot .email{color:var(--muted);font-size:13px;margin-bottom:8px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.trialpill{display:block;text-align:center;margin-bottom:12px;padding:8px 10px;border-radius:8px;font-size:12.5px;font-weight:600;
  background:var(--grn-l);color:var(--grn-d);border:1px solid rgba(15,107,79,.22)}
.trialpill:hover{text-decoration:none;background:#dcebe3}
.trialpill.warn{background:#fbf0df;color:var(--warn);border-color:rgba(180,83,9,.28)}
.trialpill.bad{background:#f8e7e4;color:var(--bad);border-color:rgba(179,38,30,.3)}
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
.brand{font-family:var(--disp);font-weight:700;font-size:20px;color:var(--ink);letter-spacing:-.02em}
.brand .dot{color:var(--grn)}
.nav{display:flex;gap:16px;margin-left:8px;flex-wrap:wrap}
.nav a{color:var(--muted);font-weight:500;transition:color .15s}.nav a.on,.nav a:hover{color:var(--ink)}
.spacer{flex:1}
.wrap{max-width:1080px;margin:0 auto;padding:24px 20px}
.muted{color:var(--muted)}.small{font-size:13px}
h1,h2{font-family:var(--disp);letter-spacing:-.02em;color:var(--ink);font-weight:600}
h1{font-size:27px;margin:0 0 4px}h2{font-size:18px;margin:24px 0 12px}
.grid{display:grid;gap:16px}
.cols-3{grid-template-columns:repeat(3,1fr)}.cols-2{grid-template-columns:repeat(2,1fr)}
@media(max-width:760px){.cols-3,.cols-2{grid-template-columns:1fr}}
.card{background:#fff;border:1px solid var(--line);border-radius:10px;padding:18px;color:var(--body);
  box-shadow:0 1px 2px rgba(12,14,18,.03);
  transition:transform .25s var(--ease),box-shadow .25s ease}
.card:hover{transform:translateY(-2px);box-shadow:0 18px 38px -26px rgba(12,14,18,.3)}
.stat{font-family:var(--disp);font-size:30px;font-weight:700;letter-spacing:-.02em;color:var(--ink)}
.stat.green{color:var(--grn-d)}
.label{font-family:var(--mono);font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted);font-weight:500}
.btn{display:inline-block;background:var(--accent);color:#fff;border:0;border-radius:6px;
  padding:10px 16px;font-size:14px;font-weight:600;cursor:pointer;
  transition:transform .15s var(--ease),background .15s,box-shadow .2s}
.btn:hover{background:var(--accent-d);text-decoration:none;box-shadow:0 6px 16px -10px rgba(11,79,58,.5)}
.btn.sec{background:#fff;color:var(--ink);border:1px solid var(--line)}
.btn.sec:hover{background:var(--paper);box-shadow:none;transform:none;border-color:#d8d5cc}
.btn.bad{background:var(--bad);color:#fff}.btn.bad:hover{background:#8f1e17}.btn.sm{padding:6px 10px;font-size:13px}
table{width:100%;border-collapse:collapse;font-size:14px}
th,td{text-align:left;padding:10px 12px;border-bottom:1px solid var(--line)}
th{font-family:var(--mono);font-size:12px;text-transform:uppercase;letter-spacing:.04em;color:var(--muted)}
tr:hover td{background:var(--paper)}
.badge{display:inline-block;padding:2px 9px;border-radius:999px;font-size:12px;font-weight:600}
.badge.trial{background:var(--paper2);color:var(--body)}.badge.paid{background:var(--grn);color:#fff}
.badge.suspended{background:#f8e7e4;color:var(--bad)}.badge.admin{background:var(--grn-l);color:var(--grn-d)}
.badge.off{background:var(--paper2);color:var(--muted)}
.bar{height:10px;background:var(--line2);border-radius:6px;overflow:hidden}
.bar>span{display:block;height:100%;background:var(--grn)}
.field{margin:14px 0}.field label{display:block;font-weight:600;margin-bottom:6px;color:var(--ink)}
.field input,.field select{width:100%;padding:10px;border:1px solid var(--line);border-radius:8px;font-size:14px;
  background:#fff;color:var(--ink)}
.field input:focus,.field select:focus{outline:none;border-color:var(--grn);box-shadow:0 0 0 3px rgba(15,107,79,.15)}
.note{background:var(--grn-l);border:1px solid rgba(15,107,79,.2);color:var(--grn-d);padding:10px 14px;border-radius:8px;margin:12px 0}
.note.warn{background:#fbf0df;border-color:rgba(180,83,9,.3);color:var(--warn)}
.note.bad{background:#f8e7e4;border-color:rgba(179,38,30,.3);color:var(--bad)}
.modes{display:flex;gap:8px;flex-wrap:wrap}
.modes button{flex:1;min-width:150px;text-align:left;padding:14px;border:2px solid var(--line);
  border-radius:10px;background:var(--paper);cursor:pointer;color:var(--ink);transition:border-color .2s,background .2s,transform .2s var(--ease)}
.modes button:hover{transform:translateY(-1px)}
.modes button.on{border-color:var(--grn);background:var(--grn-l)}
.modes b{display:block;font-size:15px}.modes .small{color:var(--muted)}
code{background:var(--paper2);color:var(--navy);padding:2px 6px;border-radius:5px;font-size:13px;border:1px solid var(--line)}
pre{background:var(--paper2);color:var(--navy);padding:16px;border-radius:10px;overflow:auto;font-size:13px;line-height:1.6;border:1px solid var(--line)}
.auth{max-width:400px;margin:48px auto}
.center{text-align:center}
.hero{max-width:640px;margin:40px auto 28px;text-align:left}
.hero h1{font-size:34px;letter-spacing:-.02em;line-height:1.08}
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
  background:linear-gradient(90deg,var(--grn),var(--grn-d));box-shadow:0 0 10px rgba(15,107,79,.5);
  transition:width .25s ease}
.btn.loading{position:relative;color:transparent!important;pointer-events:none}
.btn.loading::after{content:"";position:absolute;top:50%;left:50%;width:14px;height:14px;margin:-7px 0 0 -7px;
  border:2px solid rgba(255,255,255,.55);border-top-color:#fff;border-radius:50%;animation:mp-spin .6s linear infinite}
.btn.sec.loading::after{border-color:rgba(0,0,0,.25);border-top-color:#111}
@keyframes mp-spin{to{transform:rotate(360deg)}}
@media(prefers-reduced-motion:reduce){#nprogress b{transition:opacity .2s}.btn.loading::after{animation:none}}

/* ---- Outlay dashboard component library (ported from the marketing site) ---- */
.ohead{margin:2px 0 20px}
.ohead h1{font-family:var(--disp);font-size:26px;color:var(--ink);font-weight:600;letter-spacing:-.015em;margin:0}
.ohead p{color:var(--muted);font-size:14.5px;margin:6px 0 0}
.kpis{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:0 0 18px}
@media(max-width:880px){.kpis{grid-template-columns:repeat(2,1fr)}}
.kpi{background:#fff;border:1px solid var(--line);border-radius:13px;padding:15px 17px}
.kpi .l{font-size:10.5px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--muted)}
.kpi .v{font-family:var(--disp);font-weight:700;font-size:27px;color:var(--ink);letter-spacing:-.02em;margin-top:6px;line-height:1.1}
.kpi .v.grn{color:var(--grn-d)}
.kpi .s{font-size:11.5px;color:var(--muted);margin-top:3px}
.ocard{background:#fff;border:1px solid var(--line);border-radius:14px;padding:18px 20px}
.ocard+.ocard,.ocard{margin-top:0}
.ogrid{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media(max-width:760px){.ogrid{grid-template-columns:1fr}}
.dh{font-family:var(--disp);font-size:15px;color:var(--ink);font-weight:600;margin:0 0 12px;display:flex;justify-content:space-between;align-items:center;gap:10px}
.dh .sub{font-family:var(--sans);font-weight:400;font-size:12.5px;color:var(--muted)}
.erow{display:grid;grid-template-columns:1fr auto;gap:3px 12px;align-items:center;padding:9px 0;border-bottom:1px solid var(--line2)}
.erow:last-child{border-bottom:none}
.erow .nm{font-size:13.5px;color:var(--ink);font-weight:500}
.erow .nm small{color:var(--faint);font-weight:400}
.erow .amt{font-size:13.5px;font-weight:600;color:var(--ink);text-align:right;font-variant-numeric:tabular-nums}
.erow .shr{font-size:12px;color:var(--muted);text-align:right;font-variant-numeric:tabular-nums}
.erow .ebar{grid-column:1/3;height:6px;border-radius:5px;background:#eceae3;overflow:hidden;margin-top:3px}
.erow .ebar>span{display:block;height:100%;border-radius:5px}
.bignum{display:flex;align-items:baseline;gap:10px;margin:2px 0}
.bignum .v{font-family:var(--disp);font-weight:700;font-size:32px;color:var(--ink);letter-spacing:-.02em}
.bignum .of{font-size:13px;color:var(--muted)}
.band{height:9px;border-radius:6px;background:#eceae3;position:relative;margin:14px 0 6px;overflow:hidden}
.band>span{position:absolute;top:0;bottom:0;background:linear-gradient(90deg,var(--grn-l),var(--grn));border-radius:6px}
.bandlab{display:flex;justify-content:space-between;font-size:11.5px;color:var(--muted);font-variant-numeric:tabular-nums}
.dual{display:grid;gap:8px;margin-top:12px}
.dual .r{display:flex;justify-content:space-between;font-size:12.5px;color:var(--muted)}
.dual .r b{color:var(--ink);font-variant-numeric:tabular-nums}
.dual .track{height:8px;border-radius:6px;background:#eceae3;overflow:hidden}
.dual .track>span{display:block;height:100%;border-radius:6px}
.flagbox{background:var(--amber-l);border:1px solid #e6cfa0;border-radius:11px;padding:11px 13px;font-size:12.5px;color:#7a3d08;margin-top:14px}
.okbox{background:var(--grn-l);border:1px solid #cfe3d8;border-radius:11px;padding:11px 13px;font-size:12.5px;color:var(--grn-d);margin-top:14px}
.otag{font-size:10px;font-weight:700;letter-spacing:.04em;text-transform:uppercase;border-radius:999px;padding:2px 9px}
.otag.ok{color:var(--grn-d);background:var(--grn-l)}.otag.warn{color:var(--amber);background:var(--amber-l)}.otag.over{color:var(--red);background:var(--red-l)}.otag.ex{color:var(--muted);background:var(--paper2);border:1px solid var(--line)}
.ostrip{border-radius:12px;padding:12px 16px;margin-bottom:16px;display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:13.5px}
.olinks{display:flex;flex-wrap:wrap;gap:8px 18px;align-items:center;margin:0 0 18px;font-size:13.5px}
.olinks .sp{flex:1}
.syncline{color:var(--muted);font-size:12.5px;margin:-6px 0 16px}
/* form fields used on Connect / Estimate / Budgets */
.fld{display:flex;flex-direction:column;gap:5px}
.fld>span{font-size:12.5px;font-weight:600;color:var(--ink)}
.fld input,.fld select,.fld textarea{padding:10px 12px;border:1px solid var(--line);border-radius:9px;
  font:inherit;font-size:14px;background:#fff;color:var(--ink);width:100%}
.fld input:focus,.fld select:focus,.fld textarea:focus,textarea:focus{outline:none;border-color:var(--grn);box-shadow:0 0 0 3px rgba(15,107,79,.15)}
.ocard textarea,textarea{width:100%;padding:11px 13px;border:1px solid var(--line);border-radius:10px;
  font:inherit;font-size:13.5px;background:#fff;color:var(--ink);font-family:var(--mono)}
.ocard h3{font-family:var(--disp);font-size:15px;color:var(--ink);font-weight:600;margin:0 0 6px}
.ohead h1 .muted{font-weight:400}
.chip{display:inline-block;background:var(--paper2);border:1px solid var(--line);border-radius:999px;
  padding:3px 10px;margin:0 6px 6px 0;font-size:12.5px;color:var(--body)}
.chip .mono{font-family:var(--mono);color:var(--ink)}
.bcard{background:#fff;border:1px solid var(--line);border-radius:13px;padding:15px 17px;margin-top:12px}
.exrow{display:grid;grid-template-columns:1fr auto;align-items:center;gap:2px 12px;padding:11px 2px;border-top:1px solid var(--line);text-decoration:none}
.exrow:first-of-type{border-top:none}
.exrow:hover{text-decoration:none}
.exrow .nm{font-weight:600;color:var(--ink);font-size:14px}
.exrow:hover .nm{color:var(--grn-d)}
.exrow .exd{grid-column:1;font-size:12.5px;color:var(--muted);line-height:1.45}
.exrow .exarr{grid-row:1/3;color:var(--muted);font-weight:600;align-self:center}
.exrow:hover .exarr{color:var(--grn-d)}
.trow{display:flex;align-items:center;gap:10px;padding:11px 2px;border-top:1px solid var(--line)}
.trow:first-child{border-top:none}
.trow .nm{flex:1;font-weight:600;color:var(--ink);font-size:14px}
.trow .nm small{font-weight:400;color:var(--muted)}
.trow-act{display:flex;gap:6px;align-items:center;margin:0}
.trow select{padding:7px 9px;border:1px solid var(--line);border-radius:8px;font:inherit;background:#fff}
.rolelegend{display:flex;flex-wrap:wrap;gap:6px 18px;margin-top:14px;padding-top:12px;border-top:1px solid var(--line);font-size:12.5px;color:var(--muted)}
.rolelegend b{color:var(--ink)}
@media(max-width:560px){.trow{flex-wrap:wrap}.trow .nm{flex-basis:100%}}
.fidgrid{display:flex;gap:28px;flex-wrap:wrap;margin:6px 0 12px}
.fidcell{display:flex;flex-direction:column;gap:3px}
.fidlab{font-size:11px;font-family:var(--mono);text-transform:uppercase;letter-spacing:.05em;color:var(--faint)}
.fidbig{font-size:25px;font-weight:700;color:var(--ink);font-variant-numeric:tabular-nums;line-height:1.1}
.fidbig.grn{color:var(--grn-d)}
.fidbig.naive{color:var(--muted);text-decoration:line-through;text-decoration-color:var(--amber);text-decoration-thickness:2px}
.cstep{display:flex;gap:11px;align-items:flex-start;margin:22px 0 10px}
.cstep:first-child{margin-top:4px}
.cnum{flex:none;width:24px;height:24px;border-radius:50%;background:var(--ink);color:#fff;font-size:13px;font-weight:600;display:flex;align-items:center;justify-content:center}
.cstep b{font-size:15px;color:var(--ink)}
.cmut{display:block;font-size:12.5px;color:var(--muted);margin-top:2px;line-height:1.5}
.srcgrid{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin:4px 0 2px}
.srctile{position:relative}
.srctile input{position:absolute;opacity:0;width:0;height:0}
.srctile label{display:block;border:1px solid var(--line);border-radius:11px;padding:12px 13px;cursor:pointer;font-weight:600;font-size:14px;color:var(--ink);transition:border-color .12s,background .12s,box-shadow .12s}
.srctile label small{display:block;font-weight:400;font-size:11.5px;color:var(--muted);margin-top:3px}
.srctile label:hover{border-color:var(--grn)}
.srctile input:checked+label{border-color:var(--grn);background:var(--grn-l);box-shadow:0 0 0 3px rgba(15,107,79,.12)}
.srctile input:focus-visible+label{border-color:var(--grn);box-shadow:0 0 0 3px rgba(15,107,79,.25)}
.srcpanel{display:none;margin-top:12px}
.srcpanel.on{display:block}
.hintbox{background:var(--paper2);border:1px solid var(--line);border-radius:10px;padding:11px 13px;font-size:12.5px;color:var(--muted);margin-top:12px;line-height:1.55}
@media(max-width:560px){.srcgrid{grid-template-columns:1fr}}
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
      .metric-toggle .seg.on{background:var(--grn);color:#fff}
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


def _sidenav(account: dict, active: str) -> str:
    """Role-aware product navigation.

    The IA is grouped: ANALYZE (the spend/forecast surfaces a user works in daily),
    SOURCES (where data comes in), and WORKSPACE (team/settings/activity admin).
    Persona (finance/eng) only reorders the ANALYZE group so each role sees its
    primary surface first — finance leads with budgets, engineering with estimates —
    without hiding anything. Team/Activity are owner/admin-only."""
    persona = (account.get("persona") or "").lower()
    is_admin = account.get("team_role") in ("owner", "admin")

    spend = ("/app/outlay", "Spend")
    accuracy = ("/app/outlay/accuracy", "Accuracy")
    budgets = ("/app/outlay/budgets", "Budgets")
    estimate = ("/app/outlay/estimate", "Estimate")
    if persona == "eng":
        analyze = [spend, accuracy, estimate, budgets]
    elif persona == "finance":
        analyze = [spend, budgets, accuracy, estimate]
    else:
        analyze = [spend, accuracy, budgets, estimate]

    sources = [("/app/outlay/connect", "Connect")]

    workspace: list[tuple[str, str]] = []
    if is_admin:
        workspace.append(("/app/team", "Team"))
    workspace.append(("/app/settings", "Settings"))
    if is_admin:
        workspace.append(("/app/audit", "Activity"))

    def grp(label: str, items: list[tuple[str, str]]) -> str:
        rows = "".join(
            f'<a class="{"on" if active == href else ""}" href="{href}">{_e(text)}</a>'
            for href, text in items)
        return f'<div class=navgrp>{label}</div>{rows}'

    home = f'<a class="{"on" if active == "/app" else ""}" href="/app">Overview</a>'
    return home + grp("Analyze", analyze) + grp("Sources", sources) + grp("Workspace", workspace)


def page(title: str, body: str, account: dict | None = None, active: str = "", bare: bool = False) -> str:
    if account:
        links = _sidenav(account, active)
        # Routing-era vendor Overview/Review are parked; keep just the leads inbox.
        admin = ""
        if account.get("role") == "admin":
            admin = ('<div class=navgrp>Vendor</div>'
                     f'<a class="{"on" if active == "/admin/leads" else ""}" href="/admin/leads">Pilot requests</a>')
        em = _e(account.get("display_email") or account["email"])
        chrome = (
            '<div class=shell><aside class=side>'
            '<a class=brand href="/app">Outlay<span class=dot>.ai</span></a>'
            f'<nav class=sidenav>{links}{admin}</nav>'
            f'<div class=side-foot>{_trial_pill(account)}<div class=email>{em}</div>'
            '<form method=post action="/logout" style="margin:0">'
            '<button class="btn sec sm" style="width:100%">Sign out</button></form></div>'
            f'</aside><main class=main><div class=inner>{_account_trial_banner(account)}{body}</div></main></div>')
    elif bare:
        # Minimal public header (brand only) — for the pilot-request form etc.
        chrome = (
            '<div class=top><div class=wrap style="padding-top:12px;padding-bottom:12px">'
            f'<a class=brand href="https://outlay-ai.com/">Outlay<span class=dot>.ai</span></a></div></div>'
            f'<div class=wrap style="max-width:640px">{body}</div>')
    else:
        nav = ('<div class="spacer"></div><div class="nav">'
               '<a href="/login">Sign in</a><a class="btn sm" href="/signup">Start free trial</a></div>')
        chrome = (
            '<div class=top><div class=wrap style="padding-top:12px;padding-bottom:12px">'
            f'<a class=brand href="/">Outlay<span class=dot>.ai</span></a>{nav}'
            f'</div></div><div class=wrap>{body}</div>')
    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;450;500;600;700&display=swap" rel="stylesheet">
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
        export — <b>Anthropic</b>, <b>AWS Bedrock</b>, <b>Google Vertex</b>, or <b>OpenAI / Azure</b> usage (auto-detected).
        Metadata only — no prompts. Optionally add a planned-work backlog to budget it.</p>
      {err}
      <div style="display:grid;gap:12px">
        <label class=fld><span>Tracker — GitHub Issues JSON</span>
          <textarea id=ol_issues rows=4 placeholder='{{"issues":[ ... ]}}'></textarea></label>
        <label class=fld><span>AI usage — Anthropic usage JSON <span class=muted style="font-weight:400">or Bedrock / Vertex / OpenAI exports</span></span>
          <textarea id=ol_usage rows=4 placeholder='Anthropic: [ {{"id":"e1","model":"claude-...","input_tokens":...}} ]   ·   Bedrock: {{"modelId":"...","input":{{"inputTokenCount":...}}, ...}} per line'></textarea></label>
        <label class=fld><span>Provider cost export (optional) — reconcile to your invoice
            <span class=muted style="font-weight:400">AWS Cost Explorer / GCP Cloud Billing / OpenAI Costs (auto-detected)</span></span>
          <textarea id=ol_cost rows=3 placeholder='AWS: {{"ResultsByTime":[ ... ]}}   ·   OpenAI: {{"data":[{{"results":[{{"amount":{{"value":...}}}}]}}]}}'></textarea></label>
        <label class=fld><span>Planned backlog (optional) — JSON</span>
          <textarea id=ol_planned rows=3 placeholder='{{"items":[{{"id":"PROJ-1","title":"Add SSO","requirements":"...","points":8}}]}}'></textarea></label>
      </div>
      <button class="btn" style="margin-top:12px" onclick="outlayRun(this)">Run the audit</button>
      <script>
      function outlayRun(btn){{btn.classList.add('loading');btn.disabled=true;
        fetch('/app/outlay/run',{{method:'POST',headers:{{'content-type':'application/json'}},
          body:JSON.stringify({{issues:document.getElementById('ol_issues').value,
            usage:document.getElementById('ol_usage').value,
            cost_export:document.getElementById('ol_cost').value,
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


def _onboarding(conn: dict | None, report: dict | None, has_budget: bool, persona: str = "") -> str:
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


def _recon_strip(report: dict) -> str:
    """Reconciliation banner: Outlay's computed spend vs the provider's billed figure.
    The thing that lets finance trust the number."""
    rec = (report or {}).get("reconciliation") or {}
    inv = rec.get("invoice_usd")
    if not inv:
        return ""
    # Provider-aware labels — reconciliation now spans every connector.
    src = rec.get("source", "")
    provider, source_label = {
        "anthropic_cost_report": ("Anthropic", "Anthropic Cost Report"),
        "aws_cost_explorer": ("AWS", "AWS Cost Explorer"),
        "gcp_cloud_billing": ("Google Cloud", "GCP Cloud Billing"),
        "openai_costs": ("OpenAI", "OpenAI Costs API"),
    }.get(src, ("provider", "provider cost report"))
    comp = rec.get("computed_usd", 0.0)
    dp = rec.get("delta_pct", 0.0)
    within = abs(dp) <= 5
    tone, bg, col = (("ok", "var(--grn-l)", "var(--grn-d)") if within
                     else ("warn", "var(--amber-l)", "var(--amber)"))
    if within:
        msg = f"within {abs(dp):.0f}% of your {provider} invoice"
    else:
        msg = (f"{abs(dp):.0f}% {'over' if dp > 0 else 'under'} the {provider} invoice — "
               f"likely uncovered usage or pricing drift")
    return (f'<div class=ostrip style="background:{bg}"><span>'
            f'<span class="otag {tone}">reconciled</span> '
            f'computed <b>{money(comp)}</b> vs billed <b>{money(inv)}</b> · '
            f'<b style="color:{col}">{msg}</b></span>'
            f'<span class=muted style="font-size:12px">{_e(source_label)}</span></div>')


def _pricing_warn(report: dict) -> str:
    """Honest flag when some spend was priced by nearest-tier fallback (an
    unrecognized model id). For a finance product, an estimated number must never
    masquerade as exact — so we name it and the dollar amount. Hidden below 0.5%."""
    pf = (report or {}).get("pricing_fidelity") or {}
    usd, share = pf.get("fallback_usd", 0.0), pf.get("fallback_share", 0.0)
    if not usd or share < 0.005:
        return ""
    models = ", ".join(pf.get("models", [])[:4]) or "unrecognized model(s)"
    return (f'<div class=ostrip style="background:var(--amber-l)">'
            f'<span><span class="otag warn">pricing</span> '
            f'<b style="color:var(--amber)">{money(usd)} ({share*100:.0f}%)</b> was priced at the nearest '
            f'tier — these model ids aren\'t in our price book yet: <b>{_e(models)}</b>. '
            f'Reconciliation against your invoice will catch any gap.</span>'
            f'<span class=muted style="font-size:12px">tell us to add exact rates</span></div>')


def _coverage_diag(report: dict) -> str:
    """When ticket coverage is low, explain *why* (from the fidelity breakdown) and
    the cheapest way to lift it — turning a weak number into a guided next step
    instead of a dead end. Hidden when coverage is healthy."""
    sp = (report or {}).get("spend") or {}
    total = sp.get("total_usd", 0.0)
    cov = sp.get("ticket_coverage", 0.0)
    if total <= 0 or cov >= 0.5:
        return ""
    bf = sp.get("by_fidelity_usd") or {}
    team_usd = bf.get("team", 0.0)        # reached a team, but no ticket → branch had no ticket/PR link
    inv_usd = bf.get("invoice", 0.0)      # no ticket and no team signal at all
    recs = ""
    if team_usd > 0:
        recs += (f'<li><b>{money(team_usd)}</b> ran on branches with no ticket or linked PR. '
                 f'<b>Connect your PRs</b> — most reference the issue they close ("Closes #123"), '
                 f'which recovers the link automatically, no branch renaming. '
                 f'<a href="/app/outlay/connect">Connect →</a></li>')
    if inv_usd > 0:
        recs += (f'<li><b>{money(inv_usd)}</b> had no team or ticket signal. Map people to teams '
                 f'(email / API-key id → team) so at least cost-center allocation lands. '
                 f'<a href="/app/outlay/connect#teams">Set up →</a></li>')
    if not recs:
        return ""
    return (f'<div class=ocard style="border-color:var(--amber);background:var(--amber-l)">'
            f'<div class=dh>Lift your ticket coverage'
            f'<span class=sub>{cov*100:.0f}% mapped to a ticket</span></div>'
            f'<p class=muted style="font-size:13px;margin:0 0 8px">Coverage depends on resolving each '
            f'AI call\'s branch to a ticket. Here\'s where yours is leaking — and the no-effort fix:</p>'
            f'<ul style="margin:0;padding-left:18px;font-size:13px;line-height:1.6">{recs}</ul></div>')


def _persona_card(value: str, title: str, desc: str) -> str:
    return (f'<form method=post action="/app/persona" style="margin:0">'
            f'<input type=hidden name=persona value="{value}">'
            f'<button class=bcard style="width:100%;text-align:left;cursor:pointer">'
            f'<b style="font-size:15px;color:var(--ink)">{_e(title)}</b>'
            f'<div class=muted style="font-size:13px;margin-top:6px;line-height:1.5">{_e(desc)}</div>'
            f'<div style="margin-top:12px;color:var(--grn-d);font-weight:600;font-size:13px">Use this view →</div>'
            f'</button></form>')


def _persona_switch(persona: str) -> str:
    """Small affordance to flip between the finance and engineering views."""
    if persona not in ("finance", "eng"):
        return ""
    cur = "Finance" if persona == "finance" else "Engineering"
    other, label = ("eng", "Engineering") if persona == "finance" else ("finance", "Finance")
    return (f'<div class=syncline style="margin:-4px 0 16px">Viewing as <b>{cur}</b> · '
            f'<form method=post action="/app/persona" style="display:inline;margin:0">'
            f'<input type=hidden name=persona value="{other}">'
            f'<button class="btn sec sm" style="padding:2px 9px;font-size:12px">Switch to {label} view</button>'
            f'</form></div>')


def _persona_chooser() -> str:
    """First-run: let the customer pick the experience tailored to their role."""
    return (
        '<div class=ocard style="margin-bottom:18px">'
        '<div class=dh>How will you use Outlay? '
        '<span class=sub>Pick the view that fits your role — you can switch anytime in Settings.</span></div>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px" class=cols-2>'
        + _persona_card("finance", "Finance / FinOps",
                        "Total AI spend, the quarter forecast vs budget, spend by team and project, "
                        "and alerts before you overspend.")
        + _persona_card("eng", "Engineering leader",
                        "Spend by epic, sprint, and engineer, anomaly flags on runaway tickets, and "
                        "estimates for planned work before you build it.")
        + '</div></div>')


def _kpicard(label, value, sub, grn=False) -> str:
    return (f'<div class=kpi><div class=l>{_e(label)}</div>'
            f'<div class="v{" grn" if grn else ""}">{value}</div><div class=s>{sub}</div></div>')


def _kpis_row(report: dict, history: list[dict] | None, persona: str) -> str:
    """The four headline KPIs — shared by Overview and Spend. Order is role-aware:
    finance leads spend→forecast, engineering leads spend→coverage."""
    sp = report.get("spend", {})
    fc = report.get("forecast", {})
    cov = sp.get("ticket_coverage", 0.0)
    open_items = fc.get("items_costed", 0) + fc.get("items_unclassified", 0)
    spend_kpi = _kpicard("AI spend · window", money(sp.get("total_usd", 0)), _trend_delta(history or []))
    cov_kpi = _kpicard("Mapped to a ticket", f"{cov*100:.0f}%",
                       money(sp.get("attributed_to_ticket_usd", 0)) + " attributed", grn=cov >= 0.6)
    fc_kpi = _kpicard("Forecast · open work", money(fc.get("expected_usd", 0)),
                      f"likely {money(fc.get('low_usd', 0))}–{money(fc.get('high_usd', 0))}")
    open_kpi = _kpicard("Open work items", str(open_items),
                        f"{fc.get('items_costed', 0)} costed from history")
    order = (spend_kpi + fc_kpi + cov_kpi + open_kpi) if persona == "finance" \
        else (spend_kpi + cov_kpi + fc_kpi + open_kpi)
    return '<div class=kpis>' + order + '</div>'


def _forecast_card(report: dict) -> str:
    """The p10–p90 forecast band for open work, with measured-accuracy callout."""
    fc = report.get("forecast", {})
    cal = report.get("calibration") or {}
    acc = ""
    if cal.get("n_evaluated", 0) > 0:
        acc = (f'<div class=okbox><b>Forecast accuracy (measured):</b> median estimate within '
               f'~{cal.get("mdape",0)*100:.0f}% of actual on your closed tickets (leave-one-out). '
               f'<a href="/app/outlay/accuracy">details →</a></div>')
    return (f'<div class=ocard><div class=dh>Forecast · open work</div>'
            f'<div class=bignum><span class=v>{money(fc.get("expected_usd",0))}</span>'
            f'<span class=of>expected from open scope</span></div>'
            f'<div class=band><span style="left:13%;width:74%"></span></div>'
            f'<div class=bandlab><span>p10 · {money(fc.get("low_usd",0))}</span>'
            f'<span>p90 · {money(fc.get("high_usd",0))}</span></div>'
            f'<div class=muted style="font-size:12.5px;margin-top:8px">{fc.get("items_costed",0)} items '
            f'costed, {fc.get("items_unclassified",0)} without history.</div>{acc}</div>')


def _budget_strip(statuses: list[dict] | None) -> str:
    """One-line budget status banner (over / warn / all-on-track)."""
    if not statuses:
        return ""
    over = [s for s in statuses if s["status"] == "over"]
    warn = [s for s in statuses if s["status"] == "warn"]
    if over or warn:
        tone, tag = ("over", "over") if over else ("warn", "warn")
        bg = {"over": "var(--red-l)", "warn": "var(--amber-l)"}[tone]
        col = {"over": "var(--red)", "warn": "var(--amber)"}[tone]
        parts = ([f"{len(over)} over budget"] if over else []) + ([f"{len(warn)} at warn"] if warn else [])
        return (f'<div class=ostrip style="background:{bg}"><span><span class="otag {tag}">budget</span> '
                f'<b style="color:{col}">{" · ".join(parts)}</b></span>'
                f'<a href="/app/outlay/budgets">review budgets →</a></div>')
    return (f'<div class=ostrip style="background:var(--grn-l)">'
            f'<span><span class="otag ok">budget</span> <b style="color:var(--grn-d)">'
            f'All {len(statuses)} on track</b></span>'
            f'<a href="/app/outlay/budgets">manage budgets →</a></div>')


def _anomaly_strip(report: dict) -> str:
    """One-line Overview banner: N runaway tickets and the spend above their class
    median. The guardrail that binds on outliers, not on every task."""
    an = (report or {}).get("anomalies") or []
    if not an:
        return ""
    over = sum(max(0.0, a.get("cost_usd", 0) - a.get("class_median_usd", 0)) for a in an)
    top = an[0]
    return (f'<div class=ostrip style="background:var(--amber-l)">'
            f'<span><span class="otag warn">anomaly</span> '
            f'<b style="color:var(--amber)">{len(an)} runaway ticket{"s" if len(an) != 1 else ""}</b> · '
            f'{money(over)} above class median '
            f'(worst: <b>{_e(top.get("ticket_id"))}</b> at {top.get("ratio", 0):.0f}×)</span>'
            f'<a href="/app/outlay">review →</a></div>')


def _anomaly_card(report: dict) -> str:
    """The runaway-ticket detail: each outlier, its cost vs its work-type median,
    and how many times over. Sorted worst-first (already sorted by the engine)."""
    an = (report or {}).get("anomalies") or []
    if not an:
        return ""
    worst = an[0].get("ratio", 1) or 1
    rows = ""
    for a in an[:8]:
        ratio = a.get("ratio", 0)
        col = "var(--red)" if ratio >= 5 else "var(--amber)"
        med = a.get("class_median_usd", 0)
        rows += (f'<div class=erow><span class=nm>{_e(a.get("ticket_id"))} '
                 f'<small>· {_e(a.get("task_class"))} · vs {money(med)} median</small></span>'
                 f'<span class=amt>{money(a.get("cost_usd", 0))} '
                 f'<span style="color:{col};font-weight:600;font-size:12px">{ratio:.0f}×</span></span>'
                 f'<div class=ebar><span style="width:{min(100, ratio / worst * 100):.0f}%;'
                 f'background:{col}"></span></div></div>')
    return (f'<div class=ocard><div class=dh>Runaway tickets'
            f'<span class=sub>&ge;3&times; their work-type median</span></div>{rows}'
            f'<p class=muted style="font-size:12px;margin-top:10px">Where a single ticket is burning far '
            f'more than its peers — the place to look first, not an average everyone pays.</p></div>')


def _sample_strip(report: dict) -> str:
    """Banner shown while viewing the worked sample dataset rather than real spend."""
    if not report.get("_sample"):
        return ""
    return ('<div class=ostrip style="background:#eef2fb;border:1px solid #d3def5">'
            '<span><b style="color:#2451b3">Sample data</b> — a worked example so you can see the '
            'product end-to-end, not your real spend. <a href="/app/outlay/connect">Connect your sources →</a></span>'
            '<form method=post action="/app/outlay/clear" style="margin:0">'
            '<button class="btn sec sm">Clear sample data</button></form></div>')


def _sync_line(report: dict, conn: dict | None) -> str:
    """The 'last refreshed · cadence · manage connection' footer line."""
    conn = conn or {}
    asy = conn.get("auto_sync_hours") or 0
    cadence = {24: "auto-syncs daily", 168: "auto-syncs weekly"}.get(asy, "manual sync")
    last = _fmt_date(conn.get("synced_at")) if conn.get("synced_at") else (
        _fmt_date(report.get("_generated_ts")) if report.get("_generated_ts") else "—")
    sync_err = ('<span style="color:var(--red)"> · ⚠ last sync failed — '
                '<a href="/app/outlay/connect" style="color:var(--red)">fix connection →</a></span>'
                if conn.get("last_sync_error") else
                ' · <a href="/app/outlay/connect">manage connection →</a>')
    return f'<div class=syncline>Last refreshed <b>{last}</b> · {cadence}{sync_err}</div>'


def _trend_card(history: list[dict] | None) -> str:
    """Spend over recent refreshes — a bigger sparkline than the KPI, with the
    delta vs the last refresh. Empty until there are at least two snapshots."""
    hist = history or []
    vals = [h.get("total_usd", 0.0) for h in hist]
    spark = _sparkline(vals, w=300, h=56, color="#0f6b4f")
    if not spark:  # < 2 points
        return ""
    cur = vals[-1]
    lo, hi = min(vals), max(vals)
    delta = _trend_delta(hist)
    return (f'<div class=ocard><div class=dh>Spend trend'
            f'<span class=sub>last {len(vals)} refreshes</span></div>'
            f'<div class=bignum><span class=v>{money(cur)}</span>'
            f'<span class=of>{delta}</span></div>'
            f'<div style="margin:10px 0 4px">{spark}</div>'
            f'<div class=bandlab><span>low · {money(lo)}</span><span>high · {money(hi)}</span></div></div>')


def _movers(history: list[dict] | None):
    """Biggest category changes between the two most recent refreshes. Prefers the
    team/cost-center axis when present, else work type. None until two snapshots
    carry a breakdown (older snapshots predate the breakdown column)."""
    snaps = [h for h in (history or []) if h.get("breakdown")]
    if len(snaps) < 2:
        return None
    cur, prev = snaps[-1]["breakdown"], snaps[-2]["breakdown"]
    axis = "team" if cur.get("team") else "class"
    c, p = cur.get(axis, {}) or {}, prev.get(axis, {}) or {}
    rows = []
    for name in set(c) | set(p):
        now_v, was_v = float(c.get(name, 0.0)), float(p.get(name, 0.0))
        delta = now_v - was_v
        if abs(delta) < 0.005:
            continue
        rows.append({"name": name, "axis": axis, "now": now_v, "delta": delta,
                     "pct": (delta / was_v * 100) if was_v else None})
    rows.sort(key=lambda r: abs(r["delta"]), reverse=True)
    return rows[:3] or None


def _movers_card(history: list[dict] | None, report: dict) -> str:
    """Top movers (Δ since last refresh) when we have history; otherwise the largest
    current spend drivers — always populated, never a dead card."""
    movers = _movers(history)
    if movers:
        axis_label = "team" if movers[0]["axis"] == "team" else "work type"
        rows = ""
        for m in movers:
            up = m["delta"] > 0
            arrow, col = ("↑", "var(--amber)") if up else ("↓", "var(--grn-d)")
            pct = f' {arrow} {abs(m["pct"]):.0f}%' if m["pct"] is not None else f' {arrow} new'
            rows += (f'<div class=erow><span class=nm>{_e(m["name"])}</span>'
                     f'<span class=amt>{money(m["now"])}'
                     f'<span style="color:{col};font-weight:600;font-size:12px">{pct}</span></span>'
                     f'<div class=ebar><span style="width:0"></span></div></div>')
        return (f'<div class=ocard><div class=dh>Top movers'
                f'<span class=sub>Δ by {axis_label} vs last refresh</span></div>{rows}</div>')
    # Fallback: largest spend drivers from the current report (no delta yet)
    teams = [t for t in (report.get("team_spend") or []) if t.get("team") != "(unassigned)"]
    if teams:
        items = [(t["team"], t.get("spent_usd", 0.0)) for t in teams[:3]]
        axis_label = "team"
    else:
        items = [(c["task_class"], c.get("spent_usd", 0.0)) for c in (report.get("class_spend") or [])[:3]]
        axis_label = "work type"
    if not items:
        return ""
    mx = max((v for _, v in items), default=1) or 1
    rows = "".join(
        f'<div class=erow><span class=nm>{_e(n)}</span><span class=amt>{money(v)}</span>'
        f'<div class=ebar><span style="width:{max(2,min(100,v/mx*100)):.0f}%;background:var(--grn)"></span></div></div>'
        for n, v in items)
    return (f'<div class=ocard><div class=dh>Top spend drivers'
            f'<span class=sub>largest by {axis_label} this window</span></div>{rows}'
            f'<p class=muted style="font-size:12px;margin-top:10px">Movement vs the previous refresh '
            f'appears here once you have two syncs of history.</p></div>')


def _fidelity_callout(report: dict, persona: str = "") -> str:
    """The proof, in-product: a naive token-count tracker would overstate this bill
    N× because cache reads dominate. Shown only when the gap is material so it lands
    as a real reassurance, not noise. Mirrors modelpilot/OUTLAY_PROOF.md."""
    cf = (report or {}).get("cost_fidelity") or {}
    correct, naive = cf.get("outlay_usd", 0.0), cf.get("naive_usd", 0.0)
    infl = cf.get("inflation_factor", 0.0)
    if not naive or infl < 1.15:   # no meaningful cache-driven gap → don't cry wolf
        return ""
    share = cf.get("cache_read_share", 0.0)
    who = ("Your reported AI spend is the cache-aware figure"
           if persona == "finance" else "This is the cache-aware figure")
    return (
        '<div class=ocard style="border-color:var(--grn);background:linear-gradient(180deg,var(--grn-l),#fff)">'
        '<div class=dh>Why this number is the right one</div>'
        '<div class=fidgrid>'
        f'<div class=fidcell><span class=fidlab>Outlay · cache-aware</span>'
        f'<span class="fidbig grn">{money(correct)}</span></div>'
        f'<div class=fidcell><span class=fidlab>Naive token tracker</span>'
        f'<span class="fidbig naive">{money(naive)}</span></div>'
        f'<div class=fidcell><span class=fidlab>Overstated by</span>'
        f'<span class=fidbig>{infl:.1f}×</span></div>'
        '</div>'
        f'<p class=muted style="font-size:12.5px;margin:0;line-height:1.55">{who}. '
        f'<b>{share*100:.0f}%</b> of your input tokens are cache reads, billed at ~1/10th of base input. '
        f'A tracker that prices them at full rate would report <b>{money(naive)}</b> — Outlay costs each '
        f'token class correctly, then reconciles against the provider invoice.</p>'
        '</div>')


def _explore_card(persona: str) -> str:
    """Overview's hub: short, role-ordered jump-offs into the deeper product areas."""
    dest = {
        "spend": ("/app/outlay", "Spend attribution",
                  "Where every dollar went — by ticket, work type, team, and engineer."),
        "accuracy": ("/app/outlay/accuracy", "Forecast accuracy",
                     "How close the forecast lands on your own closed tickets."),
        "budgets": ("/app/outlay/budgets", "Budgets & guardrails",
                    "Set limits by scope and get warned before you overspend."),
        "estimate": ("/app/outlay/estimate", "Estimate planned work",
                     "Price a backlog before you build it, from your learned cost model."),
    }
    order = (["spend", "budgets", "accuracy", "estimate"] if persona == "finance"
             else ["spend", "estimate", "accuracy", "budgets"])
    rows = ""
    for key in order:
        href, title, desc = dest[key]
        rows += (f'<a class=exrow href="{href}"><span class=nm>{_e(title)}</span>'
                 f'<span class=exd>{_e(desc)}</span><span class=exarr>→</span></a>')
    return f'<div class=ocard><div class=dh>Explore</div>{rows}</div>'


def overview_page(account: dict, report: dict | None, statuses: list[dict] | None = None,
                  history: list[dict] | None = None, conn: dict | None = None,
                  has_budget: bool = False, persona: str = "") -> str:
    """The role-aware home — the first screen after sign-in. A concise glance
    (KPIs, budget status, forecast) with jump-offs into the deeper areas; the
    attribution detail lives on the Spend page."""
    chooser = _persona_chooser() if persona not in ("finance", "eng") else ""
    checklist = _onboarding(conn, report, has_budget, persona)
    if not report:
        if persona == "finance":
            intro = (
                '<div class=ohead><h1>Put your AI spend on a budget.</h1>'
                '<p>Connect your AI usage and your tracker — read-only — and Outlay shows total AI spend, '
                'forecasts the quarter against budget, breaks it down by team and project, and alerts you '
                '<b>before</b> you overspend. Nothing sensitive leaves your environment.</p></div>')
        else:
            intro = (
                '<div class=ohead><h1>Your AI spend, on your roadmap.</h1>'
                '<p>Connect your tracker and AI usage — read-only — and Outlay maps every dollar to the work '
                'that drove it, forecasts the quarter, estimates planned work, and holds it to budget. '
                'Prompts never leave your tools.</p></div>')
        cta = ('<div class="row" style="margin:0 0 22px">'
               '<a class="btn" href="/app/outlay/connect">Connect your sources →</a>'
               '<form method=post action="/app/outlay/sample" style="margin:0">'
               '<button class="btn sec">See it with sample data</button></form></div>')
        return page("Home", chooser + intro + cta + checklist + _outlay_connect(),
                    account, active="/app")

    if persona == "finance":
        head = ('<div class=ohead><h1>Your AI spend at a glance</h1>'
                '<p>Total spend, the forecast against budget, and where to look next.</p></div>')
    else:
        head = ('<div class=ohead><h1>AI spend at a glance</h1>'
                '<p>The headline numbers, your budget status, and where to dig in.</p></div>')

    # Trend + movers row — lay out as a pair when both are present, else a single
    # full-width card (the trend card is empty until there are two refreshes).
    trend, movers = _trend_card(history), _movers_card(history, report)
    cards = [c for c in (trend, movers) if c]
    if len(cards) == 2:
        tm_row = '<div class=ogrid style="margin-top:16px">' + cards[0] + cards[1] + '</div>'
    elif cards:
        tm_row = '<div style="margin-top:16px">' + cards[0] + '</div>'
    else:
        tm_row = ""

    fidelity = _fidelity_callout(report, persona)
    fidelity = f'<div style="margin-top:16px">{fidelity}</div>' if fidelity else ""

    body = (chooser + head + _persona_switch(persona) + _sample_strip(report) + checklist
            + _budget_strip(statuses) + _anomaly_strip(report) + _kpis_row(report, history, persona)
            + _recon_strip(report) + _pricing_warn(report)
            + fidelity + tm_row
            + '<div class=ogrid style="margin-top:16px">' + _forecast_card(report)
            + _explore_card(persona) + '</div>' + _sync_line(report, conn))
    return page("Home", body, account, active="/app")


def outlay_page(account: dict, report: dict | None, statuses: list[dict] | None = None,
                history: list[dict] | None = None, conn: dict | None = None,
                has_budget: bool = False, persona: str = "") -> str:
    chooser = _persona_chooser() if persona not in ("finance", "eng") else ""
    checklist = _onboarding(conn, report, has_budget, persona)
    if not report:
        if persona == "finance":
            intro = (
                '<div class=ohead><h1>Put your AI spend on a budget.</h1>'
                '<p>Connect your AI usage and your tracker — read-only — and Outlay shows total AI spend, '
                'forecasts the quarter against budget, breaks it down by team and project, and alerts you '
                '<b>before</b> you overspend. Nothing sensitive leaves your environment.</p></div>')
        else:
            intro = (
                '<div class=ohead><h1>Your AI spend, on your roadmap.</h1>'
                '<p>Connect your tracker and AI usage — read-only — and Outlay maps every dollar to the work '
                'that drove it, forecasts the quarter, estimates planned work, and holds it to budget. '
                'Prompts never leave your tools.</p></div>')
        cta = ('<div class="row" style="margin:0 0 22px">'
               '<a class="btn" href="/app/outlay/connect">Connect your sources →</a>'
               '<form method=post action="/app/outlay/sample" style="margin:0">'
               '<button class="btn sec">See it with sample data</button></form></div>')
        return page("Spend", chooser + intro + cta + checklist + _outlay_connect(),
                    account, active="/app/outlay")

    sp = report.get("spend", {})
    cov = sp.get("ticket_coverage", 0.0)

    if persona == "finance":
        ohead = ('<div class=ohead><h1>Where your AI spend goes</h1>'
                 '<p>Every dollar attributed — by team and cost-center, work type, and ticket. '
                 'Forecast and budget live on <a href="/app">Overview</a>.</p></div>')
    else:
        ohead = ('<div class=ohead><h1>Where your AI spend goes</h1>'
                 '<p>Every dollar mapped to the work that drove it — by ticket, work type, and engineer. '
                 'Forecast and estimates live on <a href="/app">Overview</a>.</p></div>')

    kpis = _kpis_row(report, history, persona)

    def _erow(name, sub, amount, bar_pct, color="var(--grn)"):
        sub_html = f' <small>· {_e(sub)}</small>' if sub else ""
        return (f'<div class=erow><span class=nm>{_e(name)}{sub_html}</span>'
                f'<span class=amt>{amount}</span>'
                f'<div class=ebar><span style="width:{max(2,min(100,bar_pct)):.0f}%;background:{color}"></span></div></div>')

    # Spend by ticket
    tickets = report.get("tickets", [])[:8]
    maxc = max((t.get("cost_usd", 0) for t in tickets), default=1) or 1
    trows = "".join(
        _erow(t.get("ticket_id"), t.get("task_class"), money(t.get("cost_usd", 0)),
              t.get("cost_usd", 0) / maxc * 100, "var(--amber)" if i == 0 else "var(--grn)")
        for i, t in enumerate(tickets)) or '<p class=muted style="font-size:13px">No ticket-attributed spend yet.</p>'
    spark = _sparkline([h.get("total_usd", 0) for h in (history or [])])
    sub = f'<span class=sub title="Spend over your last {len(history or [])} refreshes">{spark}</span>' if spark else ""
    spend_card = (f'<div class=ocard><div class=dh>Where your AI spend went{sub}</div>{trows}</div>')

    # Spend by work type
    cls = report.get("class_spend") or []
    clsmax = max((c.get("spent_usd", 0) for c in cls), default=1) or 1
    crows = "".join(
        _erow(c.get("task_class"), f'{c.get("tickets",0)} tickets · {c.get("share",0)*100:.0f}%',
              money(c.get("spent_usd", 0)), c.get("spent_usd", 0) / clsmax * 100)
        for c in cls) or '<p class=muted style="font-size:13px">No work-type spend yet.</p>'
    class_card = f'<div class=ocard><div class=dh>Spend by work type</div>{crows}</div>'

    # Spend by engineer
    people = [p for p in (report.get("people") or []) if p.get("user") != "(unattributed)"][:8]
    people_card = ""
    if people:
        pmax = max((p.get("spent_usd", 0) for p in people), default=1) or 1
        prows = "".join(
            _erow(p.get("user"), f'{p.get("top_model")} · {p.get("share",0)*100:.0f}%',
                  money(p.get("spent_usd", 0)), p.get("spent_usd", 0) / pmax * 100)
            for p in people)
        people_card = (f'<div class=ocard><div class=dh>Spend by engineer'
                       f'<span class=sub>team-fidelity · user→cost</span></div>{prows}</div>')

    # Spend by team / cost-center (finance allocation view)
    teams = report.get("team_spend") or []
    team_card = ""
    if any(t.get("team") != "(unassigned)" for t in teams):
        tmax = max((t.get("spent_usd", 0) for t in teams), default=1) or 1
        trows = "".join(
            _erow(("Unassigned" if t.get("team") == "(unassigned)" else t.get("team")),
                  f'{t.get("share",0)*100:.0f}% of attributed',
                  money(t.get("spent_usd", 0)), t.get("spent_usd", 0) / tmax * 100,
                  "#cfcabb" if t.get("team") == "(unassigned)" else "var(--grn)")
            for t in teams)
        team_card = (f'<div class=ocard><div class=dh>Spend by team / cost-center'
                     f'<span class=sub>allocation</span></div>{trows}</div>')

    anomaly_card = _anomaly_card(report)
    anomaly_row = f'<div style="margin-top:16px">{anomaly_card}</div>' if anomaly_card else ""

    # Attribution-only grid — forecast/estimate now live on Overview and their
    # own pages, so Spend stays focused on "where every dollar went".
    if persona == "finance":
        # Finance leads with team/cost-center allocation, then work-type, then ticket
        # detail; per-engineer (individual-name) detail is an engineering concern.
        g1 = f'<div class=ogrid>{team_card or class_card}{spend_card}</div>'
        extra = f'<div style="margin-top:16px">{class_card}</div>' if team_card else ""
        grid = g1 + extra + anomaly_row
    else:
        g1 = f'<div class=ogrid>{spend_card}{class_card}</div>'
        g2 = (f'<div style="margin-top:16px">{people_card}</div>' if people_card else "")
        grid = g1 + g2 + anomaly_row

    if persona == "finance":
        olinks = ('<div class=olinks>'
                  '<a href="/app/outlay/budgets">Budgets &amp; guardrails →</a>'
                  '<a href="/app/outlay/accuracy">How accurate is this? →</a>'
                  '<a href="/app/outlay/estimate">Estimate planned work →</a>'
                  '<span class=sp></span>'
                  '<span class=muted style="font-size:12.5px">Export CSV:</span>'
                  '<a href="/app/outlay/export.csv?view=tickets">by ticket</a>'
                  '<a href="/app/outlay/export.csv?view=classes">by work type</a></div>')
    else:
        olinks = ('<div class=olinks>'
                  '<a href="/app/outlay/accuracy">How accurate is this? →</a>'
                  '<a href="/app/outlay/estimate">Estimate your backlog →</a>'
                  '<a href="/app/outlay/budgets">Budgets &amp; guardrails →</a>'
                  '<span class=sp></span>'
                  '<span class=muted style="font-size:12.5px">Export CSV:</span>'
                  '<a href="/app/outlay/export.csv?view=tickets">tickets</a>'
                  '<a href="/app/outlay/export.csv?view=classes">work types</a>'
                  '<a href="/app/outlay/export.csv?view=people">engineers</a></div>')

    cov_diag = _coverage_diag(report)
    cov_diag = f'<div style="margin:16px 0">{cov_diag}</div>' if cov_diag else ""

    body = (chooser + ohead + _persona_switch(persona) + _sample_strip(report) + checklist
            + _budget_strip(statuses) + kpis + _recon_strip(report) + _pricing_warn(report)
            + cov_diag + _sync_line(report, conn) + olinks + grid)
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
    idmap = _e(conn.get("identity_map") or "")
    sset = lambda k: "✓ saved" if conn.get(k) else "not set"  # noqa: E731
    chk = lambda v: " checked" if tracker == v else ""         # noqa: E731
    asy = conn.get("auto_sync_hours") or 0
    aopt = lambda v: " selected" if asy == v else ""           # noqa: E731
    synced = (f'Last synced {_fmt_date(conn.get("synced_at"))}.'
              if conn.get("synced_at") else "Never synced yet.")
    if asy:
        synced += f' Auto-sync is on ({"daily" if asy == 24 else "weekly"}).'
    err = conn.get("last_sync_error")
    err_banner = (f'<div class=ostrip style="background:var(--red-l)"><span><span class="otag over">sync</span> '
                  f'<b style="color:var(--red)">Last sync failed.</b> {_e(err)}</span></div>'
                  if err else "")

    def _tile(value: str, title: str, sub: str) -> str:
        return (f'<div class=srctile><input type=radio name=tracker id=trk-{value} value={value}{chk(value)}>'
                f'<label for=trk-{value}>{_e(title)}<small>{_e(sub)}</small></label></div>')

    form = f"""<div class=ohead><h1>Connect your sources <span class=muted>· read-only</span></h1>
      <p>Two things to connect: your <b>tracker</b> (so spend maps to tickets, sprints, and people) and your
        <b>AI usage</b> (the spend itself). Read-only tokens, metadata only — prompts never leave your tools.</p></div>
      {err_banner}
      <form method=post action="/app/outlay/connect" class=ocard>

        <div class=cstep><span class=cnum>1</span><div><b>Choose your tracker</b>
          <span class=cmut>Where your work lives — Outlay maps spend to its tickets, epics, and teams.</span></div></div>
        <div class=srcgrid>
          {_tile('github', 'GitHub', 'Issues & PRs')}
          {_tile('jira', 'Jira', 'Projects & epics')}
          {_tile('linear', 'Linear', 'Issues & cycles')}
        </div>

        <div class=srcpanel data-when=github>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <label class=fld><span>Owner</span><input name=github_owner value="{owner}" placeholder="acme"></label>
            <label class=fld><span>Repo</span><input name=github_repo value="{repo}" placeholder="web"></label>
          </div>
          <label class=fld style="margin-top:12px"><span>Read-only token ({sset('github_token')})</span>
            <input name=github_token type=password placeholder="ghp_… (leave blank to keep)"></label>
        </div>

        <div class=srcpanel data-when=jira>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
            <label class=fld><span>Base URL</span><input name=jira_base_url value="{jbase}" placeholder="https://acme.atlassian.net"></label>
            <label class=fld><span>Email</span><input name=jira_email value="{jemail}" placeholder="you@acme.dev"></label>
          </div>
          <label class=fld style="margin-top:12px"><span>API token ({sset('jira_token')})</span>
            <input name=jira_token type=password placeholder="(leave blank to keep)"></label>
          <label class=fld style="margin-top:12px"><span>JQL (optional)</span>
            <input name=jira_jql value="{jjql}" placeholder="project = ENG AND updated >= -90d"></label>
        </div>

        <div class=srcpanel data-when=linear>
          <label class=fld><span>API key ({sset('linear_key')})</span>
            <input name=linear_key type=password placeholder="lin_… (leave blank to keep)"></label>
        </div>

        <div class=cstep><span class=cnum>2</span><div><b>Connect your AI usage</b>
          <span class=cmut>At least one. This is the spend Outlay attributes and forecasts.</span></div></div>
        <label class=fld><span>Anthropic admin API key ({sset('anthropic_key')})</span>
          <input name=anthropic_key type=password placeholder="sk-ant-admin… (leave blank to keep)"></label>
        <label class=fld style="margin-top:12px"><span>Cursor admin API key ({sset('cursor_key')})</span>
          <input name=cursor_key type=password placeholder="key_… (Cursor team admin; leave blank to keep)"></label>
        <div class=hintbox>Running on <b>AWS Bedrock</b>, <b>Google Vertex</b>, or <b>OpenAI / Azure</b>?
          Export your usage and drop it in on the <a href="/app/outlay">Spend</a> tab — the format is auto-detected.
          Live cloud pull for those is coming.</div>

        <div class=cstep><span class=cnum>3</span><div><b>Keep it fresh</b>
          <span class=cmut>Re-pull on a schedule so the audit and forecast stay current.</span></div></div>
        <label class=fld><span>Auto-sync</span><select name=auto_sync_hours>
          <option value=0{aopt(0)}>Off — sync manually</option>
          <option value=24{aopt(24)}>Daily</option>
          <option value=168{aopt(168)}>Weekly</option></select></label>

        <button class="btn sec" style="margin-top:18px">Save connection</button>
        <script>(function(){{var f=document.currentScript.closest('form');if(!f)return;
          function reveal(){{var r=f.querySelector('input[name=tracker]:checked'),v=r?r.value:'';
            [].forEach.call(f.querySelectorAll('.srcpanel'),function(p){{p.classList.toggle('on',p.dataset.when===v);}});}}
          [].forEach.call(f.querySelectorAll('input[name=tracker]'),function(i){{i.addEventListener('change',reveal);}});
          reveal();}})();</script>
      </form>
      <div class=ocard style="margin-top:16px">
        <p class=muted style="margin:0 0 12px;font-size:13.5px">{synced}</p>
        <button class="btn" onclick="outlaySync(this)">Sync now &amp; run the audit</button>
        <a class="btn sec" href="/app/outlay" style="margin-left:8px">View Spend →</a>
        <script>function outlaySync(btn){{btn.classList.add('loading');btn.disabled=true;
          fetch('/app/outlay/sync',{{method:'POST'}}).then(function(r){{return r.json();}}).then(function(d){{
            if(d.ok){{location.href='/app/outlay';}}else{{btn.classList.remove('loading');btn.disabled=false;
              alert(d.error||'Sync failed.');}}}})
          .catch(function(){{btn.classList.remove('loading');btn.disabled=false;alert('Network error.');}});}}
        </script>
      </div>
      <div class=ocard style="margin-top:16px" id=teams>
        <div class=dh>Map people to teams <span class=sub>for cost-center allocation</span></div>
        <p class=muted style="margin:-4px 0 10px;font-size:13.5px">Optional but powerful: map each engineer's
          email (or API-key id) to a team, so spend allocates by cost-center even when your tickets don't
          carry a team. One per line — <code>alice@acme.com, Platform</code> — or map a whole domain with
          <code>@acme.com, Internal</code>. This is what fills the finance "Spend by team" view.</p>
        <form method=post action="/app/outlay/identity">
          <textarea name=identity_map rows=5 placeholder="alice@acme.com, Platform
bob@acme.com, Growth
@contractor.com, External">{idmap}</textarea>
          <button class="btn sec" style="margin-top:12px">Save team map</button>
        </form>
      </div>"""
    return page("Connect", form, account, active="/app/outlay/connect")


def estimate_backlog_page(account: dict, report: dict | None) -> str:
    """Budget planned work against the cost model learned from connected history."""
    head = ('<div class=ohead><h1>Estimate your backlog</h1>'
            '<p>Price planned work before it\'s built. Outlay costs each item against the model it learned '
            'from your delivered work — the more scope you give (requirements, design docs, points), the '
            'tighter the range.</p></div>')
    if not (report and report.get("_model")):
        body = (head + '<div class=ocard><p class=muted style="margin:0 0 12px">Connect your data on the '
                '<a href="/app/outlay">Spend</a> tab first so Outlay can learn your cost model — then '
                'estimate a backlog here.</p><a class="btn" href="/app/outlay">Go to Spend →</a></div>')
        return page("Estimate", body, account, active="/app/outlay/estimate")

    form = """<div class=ocard><div class=dh>Paste a planned backlog</div>
      <p class=muted style="margin:-4px 0 10px;font-size:13.5px">A JSON list of items — each with a <b>title</b>, and ideally
        <b>requirements</b>, <b>design_docs</b>, and/or story <b>points</b>.</p>
      <textarea id=ol_plan rows=6 placeholder='{"items":[{"id":"PROJ-1","title":"Add SSO","requirements":"SAML + SCIM, multi-tenant, audit log","points":8}]}'></textarea>
      <button class="btn" style="margin-top:12px" onclick="estRun(this)">Estimate →</button>
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
        emax = max((e.get("expected_usd", 0) for e in est.get("items", [])), default=1) or 1
        rows = ""
        for e in est.get("items", []):
            if e.get("costable"):
                typ = _e(e.get("task_class")) + (f' · {_e(e.get("complexity_tier"))}' if e.get("complexity_tier") else "")
                sub = f'{typ} · {money(e.get("low_usd",0))}–{money(e.get("high_usd",0))} · {_e(e.get("confidence"))}'
                rows += (f'<div class=erow><span class=nm>{_e(e.get("id"))} <small>· {sub}</small></span>'
                         f'<span class=amt>{money(e.get("expected_usd",0))}</span>'
                         f'<div class=ebar><span style="width:{min(100,e.get("expected_usd",0)/emax*100):.0f}%;background:var(--grn)"></span></div></div>')
            else:
                rows += (f'<div class=erow><span class=nm>{_e(e.get("id"))} '
                         f'<small>· {_e(e.get("task_class"))} · needs scope to cost</small></span>'
                         f'<span class=amt style="color:var(--muted)">—</span>'
                         f'<div class=ebar></div></div>')
        tighten = ('<p class=muted style="font-size:12.5px;margin-top:10px">To tighten the estimate, add: '
                   + _e("; ".join(est.get("tighten", []))) + '.</p>') if est.get("tighten") else ""
        result = (f'<div class=ocard style="margin-top:16px"><div class=dh>Backlog estimate</div>'
                  f'<div class=bignum><span class=v>{money(est.get("expected_usd", 0))}</span>'
                  f'<span class=of>likely {money(est.get("low_usd", 0))}–{money(est.get("high_usd", 0))}</span></div>'
                  f'<div class=muted style="font-size:12.5px;margin:2px 0 12px">{est.get("items_costed", 0)} '
                  f'estimated, {est.get("items_unknown", 0)} declined.</div>{rows}{tighten}</div>')
    return page("Estimate", head + form + result, account, active="/app/outlay/estimate")


def _pct(x, digits: int = 0) -> str:
    try:
        return f"{float(x) * 100:.{digits}f}%"
    except (TypeError, ValueError):
        return "—"


def accuracy_page(account: dict, report: dict | None) -> str:
    """The honesty layer, front and center: how close our forecast lands on the
    customer's *own* closed tickets, measured leave-one-out. This is the #1
    customer question, so we lead with the measured number and never hide n."""
    head = ('<div class=ohead><h1>How accurate is this?</h1>'
            '<p>We don\'t ask you to trust a vendor benchmark. Outlay back-tests its forecast on '
            '<b>your own closed tickets</b>, leave-one-out: hide a ticket, predict it from the rest, '
            'compare to what it actually cost. Below is that measured error — on your data.</p></div>')
    cal = (report or {}).get("calibration") or {}
    n = cal.get("n_evaluated", 0)
    if not report or n < 1:
        body = (head + '<div class=ocard><p class=muted style="margin:0">Not enough closed, attributed '
                'tickets yet to measure accuracy. Connect data on the <a href="/app/outlay">Spend</a> tab '
                'and let a few tickets close — accuracy appears here automatically once there\'s history '
                'to back-test.</p></div>')
        return page("Accuracy", body, account, active="/app/outlay/accuracy")

    mdape, within = cal.get("mdape", 0), cal.get("within_p90", 0)
    low = (f'<div class=flagbox style="margin-bottom:16px"><b>Early read — {n} ticket(s) evaluated.</b> '
           'Treat these as directional until more work closes.</div>') if n < 12 else ""

    def _kpicard(label, value, sub, grn=False):
        return (f'<div class=kpi><div class=l>{_e(label)}</div>'
                f'<div class="v{" grn" if grn else ""}">{value}</div><div class=s>{_e(sub)}</div></div>')
    kpis = ('<div class=kpis style="grid-template-columns:repeat(3,1fr)">'
            + _kpicard("Median error (MdAPE)", _pct(mdape), "typical forecast vs actual", grn=mdape <= 0.25)
            + _kpicard("Within the p90 band", _pct(within), "actuals at/under our high estimate", grn=within >= 0.8)
            + _kpicard("Tickets back-tested", str(n), f"{_pct(cal.get('coverage',0))} of closed work")
            + '</div>')

    rows = ""
    cmax = max((cc.get("mdape", 0) for cc in cal.get("by_class", [])), default=1) or 1
    for cc in cal.get("by_class", []):
        bias = cc.get("bias", 0)
        bias_txt = ("over-forecasts" if bias > 0.02 else "under-forecasts" if bias < -0.02 else "unbiased")
        col = "var(--amber)" if cc.get("mdape", 0) > 0.4 else "var(--grn)"
        rows += (f'<div class=erow><span class=nm>{_e(cc.get("task_class"))} '
                 f'<small>· n={cc.get("n",0)} · {bias_txt} ({_pct(bias,0)})</small></span>'
                 f'<span class=amt>{_pct(cc.get("mdape",0))} <span style="color:var(--muted);font-weight:400">err</span></span>'
                 f'<div class=ebar><span style="width:{min(100,cc.get("mdape",0)/cmax*100):.0f}%;background:{col}"></span></div></div>')
    by_class = (f'<div class=ocard><div class=dh>Accuracy by work type<span class=sub>lower error is better</span></div>{rows}'
                f'<p class=muted style="font-size:12px;margin-top:10px">Bias is the average signed error: '
                'positive means we tend to over-forecast (you\'ll likely spend less), negative the reverse.</p></div>')

    size = cal.get("size") or {}
    size_card = ""
    if size.get("n"):
        if size.get("improves"):
            size_card = (f'<div class=okbox style="margin-top:16px"><b>Story points help.</b> Conditioning on '
                         f'size cuts median error by {_pct(size.get("error_reduction",0))} vs work-type alone '
                         f'({_pct(size.get("mdape_size",0))} vs {_pct(size.get("mdape_class",0))}, n={size.get("n",0)}). '
                         f'Keep estimating points and forecasts tighten.</div>')
        else:
            size_card = (f'<div class=ocard style="margin-top:16px"><b>Story points aren\'t adding signal yet</b> '
                         f'on your data (size {_pct(size.get("mdape_size",0))} vs work-type {_pct(size.get("mdape_class",0))}). '
                         f'We fall back to the work-type model, which is doing as well or better.</div>')

    foot = ('<p class=muted style="font-size:12.5px;margin-top:16px">Method: leave-one-out back-test over '
            'closed, ticket-attributed work. We never score a ticket using its own cost. As more work '
            'closes, the sample grows and this number sharpens — re-checked on every sync.</p>')
    return page("Accuracy", head + low + kpis + by_class + size_card + foot, account, active="/app/outlay/accuracy")


def budgets_page(account: dict, report: dict | None, statuses: list[dict],
                 projects: list[dict] | None = None) -> str:
    """Set budgets by scope and see spend-vs-budget with pace projection."""
    tones = {"ok": ("var(--grn)", "var(--grn-d)"), "warn": ("var(--amber)", "var(--amber)"),
             "over": ("var(--red)", "var(--red)")}
    note = "" if report else ('<div class=ocard style="margin-bottom:16px"><p class=muted style="margin:0">'
                              'Connect data on the <a href="/app/outlay">Spend</a> tab to see live status.</p></div>')
    rows = ""
    for s in statuses:
        bar, txt = tones.get(s["status"], tones["ok"])
        name = _e(s["scope_type"]) + (f': {_e(s["scope_id"])}' if s.get("scope_id") else "")
        w = min(max(s.get("pct_used", 0), 0), 1) * 100
        rows += (f'<div class=bcard><div style="display:flex;justify-content:space-between;align-items:center;gap:10px">'
                 f'<b style="font-size:14px">{name}</b>'
                 f'<span class="otag {s["status"]}">{_e(s["status"])}</span></div>'
                 f'<div class=dual style="margin-top:10px"><div class=track>'
                 f'<span style="width:{w:.0f}%;background:{bar}"></span></div></div>'
                 f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">'
                 f'<span class=muted style="font-size:12.5px">{money(s.get("spent_usd",0))} of {money(s["limit_usd"])} · '
                 f'projected <b style="color:{txt}">{money(s.get("projected_usd",0))}</b> / {int(s.get("period_days") or 30)}d</span>'
                 f'<form method=post action="/app/outlay/budgets/delete" style="margin:0">'
                 f'<input type=hidden name=id value="{s["id"]}">'
                 f'<button class="btn sec sm">Remove</button></form></div></div>')
    rows = (f'<div class=ocard><div class=dh>Your budgets</div>{rows}</div>' if statuses
            else '<div class=ocard><p class=muted style="margin:0">No budgets yet — add one below.</p></div>')
    # Project/epic pick-list so users know which keys they can budget against.
    pref = ""
    if projects:
        chips = "".join(
            f'<span class=chip><span class=mono>{_e(p["project"])}</span> · {money(p.get("spent_usd",0))}</span>'
            for p in projects[:12])
        pref = (f'<div class=ocard style="margin-top:16px"><div class=dh>Spend by project / epic</div>'
                f'<p class=muted style="font-size:13px;margin:-4px 0 10px">Budget any of these by choosing '
                f'<b>Project / epic</b> below and pasting the key.</p>{chips}</div>')
    add = """<div class=ocard style="margin-top:16px"><div class=dh>Add a budget</div>
      <form method=post action="/app/outlay/budgets">
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:12px;align-items:end">
          <label class=fld><span>Scope</span><select name=scope_type>
            <option value=overall>Overall</option><option value=team>Team</option>
            <option value=class>Work type</option><option value=project>Project / epic</option></select></label>
          <label class=fld><span>Scope id (team / type / key)</span><input name=scope_id placeholder="platform / bugfix / PROJ"></label>
          <label class=fld><span>Limit (USD)</span><input name=limit_usd type=number step=any placeholder="5000"></label>
          <label class=fld><span>Period (days)</span><input name=period_days type=number value=90></label>
        </div>
        <button class="btn" style="margin-top:14px">Add budget</button>
      </form></div>"""
    head = ('<div class=ohead><h1>Budgets &amp; guardrails</h1>'
            '<p>Set a budget by scope; Outlay projects your spend to the period and flags it '
            '<b>before</b> you go over — not at month-end.</p></div>')
    return page("Budgets", head + note + rows + pref + add, account, active="/app/outlay/budgets")


def pilot_request_page(error: str = "", values: dict | None = None) -> str:
    """Public, branded design-partner pilot request form (replaces the mailto CTA)."""
    v = values or {}
    err = f'<div class=ostrip style="background:var(--red-l);margin-bottom:14px"><span>{_e(error)}</span></div>' if error else ""
    body = (
        '<div class=ohead style="margin-top:30px"><h1>Request a design-partner pilot</h1>'
        '<p>Tell us a bit about your team and we\'ll get back to you within a day. A pilot is read-only, '
        '~2 weeks, and free — we map your real AI spend to your roadmap and forecast the quarter.</p></div>'
        f'{err}'
        '<form method=post action="/pilot-request" class=ocard>'
        '<input type=text name=website style="display:none" tabindex=-1 autocomplete=off>'  # honeypot
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px">'
        f'<label class=fld><span>Name</span><input name=name value="{_e(v.get("name",""))}" placeholder="Jane Doe"></label>'
        f'<label class=fld><span>Work email *</span><input name=email type=email required value="{_e(v.get("email",""))}" placeholder="jane@acme.dev"></label>'
        '</div>'
        '<div style="display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px">'
        f'<label class=fld><span>Company</span><input name=company value="{_e(v.get("company",""))}" placeholder="Acme"></label>'
        f'<label class=fld><span>Title</span><input name=title value="{_e(v.get("title",""))}" placeholder="Head of Engineering"></label>'
        '</div>'
        f'<label class=fld style="margin-top:14px"><span>What AI tools do you use?</span>'
        f'<input name=tools value="{_e(v.get("tools",""))}" placeholder="Claude Code, Cursor, the Anthropic API…"></label>'
        f'<label class=fld style="margin-top:14px"><span>Anything you want us to know?</span>'
        f'<textarea name=message rows=4 placeholder="Team size, what\'s driving the AI bill, what you\'re hoping to learn…">{_e(v.get("message",""))}</textarea></label>'
        '<button class="btn" style="margin-top:16px">Send request →</button>'
        '<p class=muted style="font-size:12px;margin:12px 0 0">We\'ll only use this to follow up about a pilot. '
        'No spam.</p>'
        '</form>')
    return page("Request a pilot", body, bare=True)


def audit_page(account: dict, entries: list[dict]) -> str:
    """Owner/admin audit trail — security-relevant activity, newest first."""
    head = ('<div class=ohead><h1>Activity &amp; audit log</h1>'
            '<p>Security-relevant events on your account — sign-ins, connection changes, and team '
            'changes. Newest first.</p></div>')
    if not entries:
        return page("Activity", head + '<div class=ocard><p class=muted style="margin:0">'
                    'No activity recorded yet.</p></div>', account, active="/app/audit")
    rows = ""
    for e in entries:
        rows += (f'<tr><td class=muted style="white-space:nowrap">{_fmt_date(e.get("ts"))}</td>'
                 f'<td style="font-size:13.5px">{_e(e.get("actor") or "—")}</td>'
                 f'<td><span class="otag ex">{_e(e.get("action") or "")}</span></td>'
                 f'<td class=muted style="font-size:13px">{_e(e.get("detail") or "")}</td></tr>')
    table = (f'<div class=ocard><div class=dh>Recent activity '
             f'<span class=sub>{len(entries)} events</span></div>'
             f'<table><thead><tr><th>When</th><th>Who</th><th>Action</th><th>Detail</th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div>')
    return page("Activity", head + table, account, active="/app/audit")


def leads_page(account: dict, leads: list[dict]) -> str:
    """Admin inbox of inbound pilot requests from the public form."""
    head = (f'<div class=ohead><h1>Pilot requests <span class=muted>· {len(leads)}</span></h1>'
            '<p>Inbound design-partner requests from <a href="https://app.outlay-ai.com/pilot-request">'
            'the form</a>. Also emailed to your inbox when SMTP is configured.</p></div>')
    if not leads:
        return page("Pilot requests", head + '<div class=ocard><p class=muted style="margin:0">'
                    'No requests yet.</p></div>', account, active="/admin/leads")
    cards = ""
    for ld in leads:
        when = _fmt_date(ld.get("ts"))
        company = _e(ld.get("company") or "—")
        name = _e(ld.get("name") or "")
        email = _e(ld.get("email") or "")
        title = f' · {_e(ld.get("title"))}' if ld.get("title") else ""
        tools = f'<div class=muted style="font-size:12.5px;margin-top:4px">Tools: {_e(ld.get("tools"))}</div>' if ld.get("tools") else ""
        msg = f'<div style="font-size:13.5px;margin-top:8px;white-space:pre-wrap">{_e(ld.get("message"))}</div>' if ld.get("message") else ""
        cards += (f'<div class=bcard><div style="display:flex;justify-content:space-between;align-items:baseline;gap:10px">'
                  f'<b style="font-size:14.5px">{company}</b><span class=muted style="font-size:12px">{when}</span></div>'
                  f'<div style="font-size:13.5px;margin-top:3px">{name}{title} · '
                  f'<a href="mailto:{email}?subject=Your%20Outlay%20pilot">{email}</a></div>{tools}{msg}</div>')
    return page("Pilot requests", head + f'<div class=ocard><div class=dh>Inbox</div>{cards}</div>',
                account, active="/admin/leads")


def pilot_thanks_page() -> str:
    body = ('<div class=ohead style="margin-top:40px"><h1>Thanks — we\'ll be in touch.</h1>'
            '<p>Your pilot request is in. We read every one and typically reply within a day '
            '(from <b>hello@outlay-ai.com</b> — keep an eye on spam just in case).</p></div>'
            '<a class="btn sec" href="https://outlay-ai.com/">← Back to outlay-ai.com</a>')
    return page("Thanks", body, bare=True)


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
    SLA, contact <a href="mailto:hello@outlay-ai.com">hello@outlay-ai.com</a>.</p>"""
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
        from . import notify
        warn = ('' if notify.enabled() else
                '<div class="note warn">Email sending isn\'t configured yet, so the verification code '
                'can\'t be delivered. Set the <code>SMTP_*</code> secrets first, then enable 2FA.</div>')
        inner = ('<p class="small muted">Require a one-time code at sign-in (emailed to you). '
                 'Strongly recommended for account security.</p>' + warn +
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
    sso = ('' if is_signup else
           '<div class=field style="margin-top:18px;border-top:1px solid var(--line);padding-top:16px">'
           '<label class=row style="gap:0;font-weight:600;font-size:13px;color:var(--muted)">'
           'Or sign in with your company SSO</label>'
           '<form method=get action="/sso/start" style="display:flex;gap:8px;margin-top:6px">'
           '<input name=email type=email required placeholder="you@company.com" '
           'style="flex:1">'
           '<button class="btn sec" type=submit style="white-space:nowrap">Use SSO</button>'
           '</form></div>')
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
      {sso}
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
    # Routing-mode / routing-policy / model-spend-budget cards are parked along with
    # the optimization engine — Settings now covers account, team, and security only.
    # (Budgets for the spend product live at /app/outlay/budgets.) The /app/settings
    # POST route still accepts the legacy fields, so this is a UI-only change.
    saved_note = '<div class="note">Settings saved.</div>' if saved else ""
    body = (f"<h1>Settings</h1>{saved_note}"
            f"{_settings_links(account)}{_digest_section(account)}{_twofa_section(account, twofa)}"
            f"{_danger_zone(account, delete_error)}")
    return page("Settings", body, account, "/app/settings")


def _digest_section(account: dict) -> str:
    """Toggle the weekly spend digest email (on by default)."""
    on = account.get("digest_weekly", 1) in (1, True, "1")
    checked = " checked" if on else ""
    return f"""
    <div class=card style="margin-top:16px" id=digest>
      <div class=label>Weekly spend digest</div>
      <p class="small muted" style="margin:.2em 0 .8em">A short Monday email — total AI spend and the
        week-over-week trend, top team &amp; work type, budget status, and any runaway tickets.
        Sent to the account owner ({_e(account.get("email", ""))}).</p>
      <form method=post action="/app/digest" style="display:flex;gap:10px;align-items:center">
        <label style="display:flex;gap:8px;align-items:center;font-size:14px;cursor:pointer">
          <input type=checkbox name=weekly value=1{checked}> Email me the weekly digest</label>
        <button class="btn sec sm">Save</button>
      </form>
    </div>"""


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
      <p class="small muted">Permanently delete this account and <b>all</b> its data — connected sources,
        spend reports, budgets, team members, and settings. This cannot be undone.</p>
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
    invite_note = (f'<div class=okbox style="margin-bottom:16px"><b>Invite sent.</b> Share this '
                   f'set-password link (valid 1 hour): <a href="{_e(invite_link)}">{_e(invite_link)}</a></div>'
                   if invite_link else "")
    active = [m for m in members if m["status"] == "active"]
    seats = 1 + len(active)  # owner + active members

    owner_row = (f'<div class=trow><span class=nm>{_e(account["email"])} '
                 f'<span class="otag ok">owner</span><small> · account owner</small></span></div>')
    rows = owner_row
    for m in members:
        opts = "".join(f'<option value="{r}"{" selected" if m["role"]==r else ""}>{r}</option>'
                       for r in TEAM_ROLES)
        pending = ("" if m["status"] == "active"
                   else f' <span class="otag warn">{_e(m["status"])}</span>')
        rows += f"""<div class=trow>
          <span class=nm>{_e(m['email'])}{pending}<small> · joined {_fmt_date(m.get('created_at'))}</small></span>
          <form method=post action="/app/team/role" class=trow-act>
            <input type=hidden name=member_id value="{m['id']}">
            <select name=role>{opts}</select><button class="btn sec sm">Save</button></form>
          <form method=post action="/app/team/remove" class=trow-act style="margin:0">
            <input type=hidden name=member_id value="{m['id']}">
            <button class="btn sec sm">Remove</button></form></div>"""
    role_opts = "".join(f'<option value="{r}">{r}</option>' for r in TEAM_ROLES)

    head = ('<div class=ohead><h1>Team &amp; access</h1>'
            '<p>Invite teammates, set their access, and connect SSO. Everyone shares this workspace\'s '
            'spend, forecasts, and budgets.</p></div>')
    members_card = (f'<div class=ocard><div class=dh>Members'
                    f'<span class=sub>{seats} with access</span></div>{rows}</div>')
    invite_card = f"""<div class=ocard style="margin-top:16px"><div class=dh>Invite a teammate</div>
      <form method=post action="/app/team/invite" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
        <label class=fld style="flex:1;min-width:240px"><span>Work email</span>
          <input name=email type=email placeholder="teammate@company.com" required></label>
        <label class=fld style="min-width:150px"><span>Role</span>
          <select name=role>{role_opts}</select></label>
        <button class=btn>Send invite</button>
      </form>
      <div class=rolelegend>
        <span><b>admin</b> — full access, including team &amp; billing</span>
        <span><b>billing</b> — dashboards + billing</span>
        <span><b>member</b> — dashboards, logs &amp; connect (read-only)</span>
      </div>
      <p class=muted style="font-size:12.5px;margin-top:6px">They'll get a link to set a password and sign in.</p>
    </div>"""
    body = head + invite_note + members_card + invite_card + _sso_section(sso or {}, scim_token)
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
