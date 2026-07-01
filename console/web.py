"""Outlay console — HTML rendering (server-side, dependency-free).

One small design system (shared CSS) + a function per page. Server-rendered so
the whole console deploys as a single FastAPI service with no build step,
consistent with the existing dashboard/ingest pages.
"""

import html
import json as _json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import quote

from . import store

BRAND = "Outlay"

_CSS = """
/* Outlay console — matches the marketing site theme (outlay.css): cool
   slate-white canvas, green accent, Inter, dark public header. */
/* "The Document" brand (2026-07): bond paper + warm ink + one money-green,
   ink hairlines, mono tabular figures — the console matches the marketing. */
:root{--ink:#101010;--body:#41413d;--muted:#6b6b63;--faint:#84847c;
  --line:#dededa;--line2:#ecece7;--bg:#fcfcfa;--paper:#f4f4f0;--paper2:#ecece7;--navy:#101010;
  --grn:#0b6a4a;--grn-d:#085239;--grn-l:#e8f1ec;--warn:#9a4708;--bad:#b23a2c;
  --mut:#6b6b63;--amber:#9a4708;--amber-l:#f9f0e0;--red:#b23a2c;--red-l:#f7e9e6;
  --accent:#0b6a4a;--accent-d:#085239;--grad:linear-gradient(135deg,#0b6a4a,#101010);
  --disp:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --sans:"Inter",-apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  --mono:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;
  --ease:cubic-bezier(.22,.61,.36,1);}
*{box-sizing:border-box}
body{margin:0;font:16px/1.6 var(--sans);color:var(--body);-webkit-font-smoothing:antialiased;
  background:var(--bg)}
a{color:var(--grn-d);text-decoration:none}a:hover{text-decoration:underline}
p a,li a,td a,.note a,.dh a,.muted a,.ostrip a,.hintbox a,.sub a,small a,.ohead a,.dq a{text-decoration:underline}
.top{background:rgba(16,16,16,.94);backdrop-filter:blur(10px);border-bottom:1px solid #3a3a34;position:sticky;top:0;z-index:10}
.top .wrap{max-width:1080px;margin:0 auto;padding:12px 20px;display:flex;align-items:center;gap:18px}
.top .brand{color:#fff}.top .brand .dot{color:#7ec9a4}
.top .nav a{color:#b9b9af}.top .nav a:hover{color:#fff}
/* left sidebar shell (signed-in) */
.shell{display:flex;min-height:100vh;align-items:stretch}
/* first-run takeover: blur the whole app behind a centered, undismissable modal */
.shell.blurred{filter:blur(6px);pointer-events:none;user-select:none}
.takeover{position:fixed;inset:0;z-index:60;display:flex;align-items:center;justify-content:center;
  padding:24px;background:rgba(17,22,32,.34);backdrop-filter:blur(2px);-webkit-backdrop-filter:blur(2px)}
.tk-card{background:#fff;border:1px solid var(--line);border-radius:18px;width:100%;max-width:780px;
  padding:30px 34px;box-shadow:0 40px 90px -30px rgba(0,0,0,.55);max-height:92vh;overflow-y:auto}
.tk-card h1{font-size:25px;margin:.15em 0 .25em}
@media(max-width:760px){.tk-card{padding:24px 20px}}
.side{width:236px;flex-shrink:0;display:flex;flex-direction:column;padding:18px 14px;
  border-right:1px solid var(--line);background:var(--paper);
  position:sticky;top:0;height:100vh;overflow-y:auto}
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
.eyebrow{font-family:var(--mono);font-size:12px;font-weight:500;letter-spacing:.12em;text-transform:uppercase;color:var(--mut);margin-bottom:10px}
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
a.kpi{display:block;text-decoration:none;position:relative;transition:border-color .12s,box-shadow .12s}
a.kpi:hover{border-color:#cdd3d9;box-shadow:0 2px 12px -7px rgba(0,0,0,.22);text-decoration:none}
a.kpi .kdrill{position:absolute;top:13px;right:14px;color:var(--faint);font-size:13px;opacity:0;transition:opacity .12s}
a.kpi:hover .kdrill{opacity:1;color:var(--grn-d)}
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
/* org directory — a visual tile per person */
.pgrid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:12px;margin-top:6px}
.ptile{display:flex;align-items:flex-start;gap:11px;border:1px solid var(--line);border-radius:12px;
  padding:12px 13px;background:#fff}
.pav{flex:none;width:34px;height:34px;border-radius:50%;background:var(--grn-l,#e7f1ec);color:var(--grn-d);
  font-weight:700;font-size:12.5px;display:flex;align-items:center;justify-content:center;letter-spacing:.02em}
.pmeta{flex:1;min-width:0}
.pnm{font-size:14px;font-weight:600;color:var(--ink);line-height:1.25;overflow:hidden;text-overflow:ellipsis}
.psub{font-size:12px;color:var(--muted);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ptt{display:inline-block;margin-top:6px;font-size:11px;color:var(--mut);background:var(--paper,#f6f8fa);
  border:1px solid var(--line2);border-radius:999px;padding:1px 8px}
.pact{flex:none;display:flex;flex-direction:column;gap:6px;align-items:flex-end}
.pact select{padding:5px 8px;border:1px solid var(--line);border-radius:8px;font:inherit;font-size:12px}
/* demo-mode banner (gated to demo accounts) */
.demobar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin:0 0 18px;padding:9px 14px;
  border:1px solid #e7d3a1;background:#fbf3dd;border-radius:11px;font-size:13px}
.demobar.off{background:var(--paper,#f6f8fa);border-color:var(--line)}
.demobar .dl{font-weight:700;color:#7a5a12;letter-spacing:.02em;white-space:nowrap}
.demobar.off .dl{color:var(--muted)}
.demobar .dt{color:#6b5a32}
.demobar.off .dt{color:var(--muted)}
.demobar .sp{flex:1}
.demobar .segwrap{display:inline-flex;border:1px solid #e0c987;border-radius:8px;overflow:hidden}
.demobar .seg{background:transparent;border:0;padding:5px 12px;font:inherit;font-size:12.5px;cursor:pointer;color:#7a5a12}
.demobar .seg.on{background:#caa64a;color:#fff;font-weight:600}
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
.fa-list{margin-top:4px}
.fa-row{display:flex;align-items:center;gap:10px;padding:10px 2px;border-top:1px solid var(--line2);font-size:13.5px;line-height:1.45}
.fa-row:first-child{border-top:none}
.fa-txt{flex:1;color:var(--body)}
a.fa-txt{text-decoration:none}
a.fa-txt:hover{text-decoration:underline}
.fa-row{border-radius:8px}
.fa-row:hover{background:var(--paper)}
.fa-dot{width:9px;height:9px;border-radius:999px;flex:none;display:inline-block}
.fa-row .btn{flex:none}
/* When an alert deep-links here, briefly ring the exact card that needs fixing. */
.bcard:target{border-color:var(--amber);box-shadow:0 0 0 3px var(--amber-l);scroll-margin-top:80px;animation:fa-flag 2s ease-out 1}
@keyframes fa-flag{0%{box-shadow:0 0 0 7px var(--amber-l)}100%{box-shadow:0 0 0 3px var(--amber-l)}}
.ptl-track{position:relative;height:8px;border-radius:999px;background:var(--paper2);overflow:hidden;margin:6px 0}
.ptl-fill{position:absolute;left:0;top:0;bottom:0;background:var(--grn)}
.ptl-now{position:absolute;top:-3px;bottom:-3px;width:2px;background:var(--ink)}
.mbar{display:flex;align-items:center;gap:8px;font-size:12px;margin-top:5px}
.mbar .ml{width:62px;color:var(--muted);flex:none}
.mbar .mt{flex:1;height:7px;border-radius:999px;background:var(--paper2);overflow:hidden;position:relative}
.mbar .mt span{position:absolute;left:0;top:0;bottom:0;border-radius:999px}
.mbar .mv{width:74px;text-align:right;flex:none;font-variant-numeric:tabular-nums}
.lensbar{margin-top:16px;border:1px solid var(--line);border-radius:12px;background:var(--paper);padding:10px 12px}
.lensrow{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.lensbar .lab{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--faint);font-weight:600}
.lensform{display:flex;align-items:center;gap:8px;margin:0}
.lensform select{padding:5px 8px;border:1px solid var(--line);border-radius:8px;font-size:13px;background:#fff}
.lensbar .lsp{flex:1}
.saveview{display:flex;align-items:center;gap:6px;margin:0}
.saveview input[name=name]{padding:5px 9px;border:1px solid var(--line);border-radius:8px;font-size:13px;width:160px}
.defck{font-size:12px;color:var(--muted);display:flex;align-items:center;gap:3px}
.vchips{display:flex;align-items:center;gap:6px;flex-wrap:wrap;margin-top:9px;padding-top:9px;border-top:1px solid var(--line2)}
.vchip{font-size:12.5px;padding:3px 10px;border-radius:999px;border:1px solid var(--line);background:#fff;color:var(--body);text-decoration:none}
.vchip.on{background:var(--grn-l);border-color:var(--grn);color:var(--grn-d);font-weight:600}
.vchip-wrap{display:inline-flex;align-items:center;gap:2px}
.vx{border:none;background:none;color:var(--faint);cursor:pointer;font-size:14px;line-height:1;padding:0 2px}
.vx:hover{color:var(--red)}
.custbar{display:flex;align-items:center;gap:10px;flex-wrap:wrap;margin-top:16px;padding:10px 14px;border-radius:10px;background:var(--grn-l);border:1px solid var(--grn);font-size:13px;color:var(--grn-d)}
.modcell{position:relative}
.modhdr{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:6px}
.modname{font-size:11px;text-transform:uppercase;letter-spacing:.05em;color:var(--faint);font-weight:600}
.modctrls{display:flex;align-items:center;gap:4px}
.modctrls form{margin:0}
.modbtn{border:1px solid var(--line);background:#fff;border-radius:7px;font-size:12px;padding:3px 8px;cursor:pointer;color:var(--body)}
.modbtn:hover:not(:disabled){border-color:var(--grn);color:var(--grn-d)}
.modbtn:disabled{opacity:.35;cursor:default}
.hidetray{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:14px;padding:12px;border:1px dashed var(--line);border-radius:10px}
.hidetray form{margin:0}.hidetray .vchip{cursor:pointer}
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
.ob-bar{height:7px;border-radius:5px;background:var(--paper2);overflow:hidden;margin:4px 0 12px}
.ob-bar>span{display:block;height:100%;border-radius:5px;background:var(--grn);transition:width .4s ease}
.ob-row{display:flex;align-items:center;gap:10px;padding:8px 0;border-top:1px solid var(--line2,#f1f5f9);font-size:14px}
.ob-tick{color:var(--grn-d);font-weight:700}
.ob-dot{color:#cbd5e1}
.ob-label{color:var(--ink)}
.ob-done .ob-label{color:#646b78;text-decoration:line-through}
.coach-spot{position:fixed;z-index:9998;border-radius:9px;pointer-events:none;
  box-shadow:0 0 0 9999px rgba(8,16,24,.55),0 0 0 2px var(--grn) inset;
  transition:top .2s,left .2s,width .2s,height .2s}
.coach-tip{position:fixed;z-index:9999;width:320px;max-width:calc(100vw - 24px);background:#fff;
  border:1px solid var(--line);border-radius:12px;box-shadow:0 18px 40px -16px rgba(8,16,24,.45);
  padding:14px 16px;font-size:13.5px;outline:none}
.coach-h{font-weight:700;font-size:15px;color:var(--ink);margin-bottom:5px}
.coach-b{color:var(--muted);line-height:1.5;margin-bottom:12px}
.coach-f{display:flex;align-items:center;gap:8px}
.coach-step{font-family:var(--mono);font-size:11.5px;color:var(--faint)}
a.nm{text-decoration:none;color:var(--ink)}
a.nm:hover{color:var(--grn-d);text-decoration:none}
a.nm .drill{color:var(--faint);font-size:12px;opacity:0;transition:opacity .12s}
a.nm:hover .drill{opacity:1;color:var(--grn-d)}
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
    The ANALYZE group is role-aware — each persona surfaces *different* primary
    capabilities, not just a reorder: business/FinOps gets the allocate-budget-govern
    tools (per-team chargeback lives on Spend + Programs enforcement); engineering
    gets the ship-efficiently tools (Accuracy + Estimate). Nothing is truly hidden —
    the other surfaces stay reachable via the Overview's Explore hub and contextual
    links on Spend. Team/Activity are owner/admin-only."""
    persona = (account.get("persona") or "").lower()
    is_admin = account.get("team_role") in ("owner", "admin")

    spend = ("/app/outlay", "Spend")
    governance = ("/app/outlay/governance", "Governance")
    commitments = ("/app/outlay/commitment", "Commitments")
    # Unified, consolidated analyze nav for every persona — three destinations:
    #   Spend (attribution detail) · Governance (budgets + programs) · Commitments
    #   (how to pay). Overview (Home) is the consolidated default landing.
    # Accuracy, Estimate, and Budgets are reachable from the Spend page's links
    # (and Budgets lives inside Governance), so they no longer need top-level slots.
    analyze = [spend, governance, commitments]

    # Sources is the *setup* surface — connecting trackers + AI usage and the
    # machine API. That's engineering's job. Business consumes the spend after
    # the fact and never connects anything, so it has no Sources group at all.
    sources: list[tuple[str, str]] = []
    if persona != "business":
        sources.append(("/app/outlay/connect", "Connect"))
        if is_admin:
            sources.append(("/app/api", "API"))

    workspace: list[tuple[str, str]] = []
    if is_admin:
        workspace.append(("/app/team", "Team"))
    workspace.append(("/app/settings", "Settings"))
    workspace.append(("/app/security", "Security"))
    if is_admin:
        workspace.append(("/app/audit", "Activity"))

    def grp(label: str, items: list[tuple[str, str]]) -> str:
        rows = "".join(
            f'<a class="{"on" if active == href else ""}" href="{href}">{_e(text)}</a>'
            for href, text in items)
        return f'<div class=navgrp>{label}</div>{rows}'

    home_label = "Home" if persona == "business" else "Overview"
    home = f'<a class="{"on" if active == "/app" else ""}" href="/app">{home_label}</a>'
    out = home + grp("Analyze", analyze)
    if sources:
        out += grp("Sources", sources)
    return out + grp("Workspace", workspace)


# In-house contextual coachmark engine — first-party, zero dependencies, no
# third-party script (a privacy/security feature, per the onboarding research).
# Spotlights the real control the user needs next; WCAG 2.2 SC 1.4.13-compliant
# (Esc-dismissable, keyboard-operable, persistent until dismissed). Non-blocking:
# the highlighted control stays clickable so users learn by doing.
_COACH_JS = r"""
window.Coach=(function(){
  var steps=[],i=0,box,tip,on=false,prevFocus=null;
  function q(s){try{return document.querySelector(s);}catch(e){return null;}}
  function clamp(v,a,b){return Math.max(a,Math.min(b,v));}
  function esc(s){var d=document.createElement('div');d.textContent=s||'';return d.innerHTML;}
  function place(){
    var st=steps[i],t=st.target?q(st.target):null;
    if(st.target&&!t){return adv(1);}
    if(t){
      var r=t.getBoundingClientRect(),pad=6;
      box.style.display='block';
      box.style.top=(r.top-pad)+'px';box.style.left=(r.left-pad)+'px';
      box.style.width=(r.width+2*pad)+'px';box.style.height=(r.height+2*pad)+'px';
      try{t.scrollIntoView({block:'center',behavior:'smooth'});}catch(e){}
      var w=320, below=r.bottom+12, above=r.top-12;
      var top=(below+180<window.innerHeight)?below:Math.max(12,above-160);
      tip.style.left=clamp(r.left,12,window.innerWidth-w-12)+'px';
      tip.style.top=top+'px';tip.style.transform='';
    }else{
      box.style.display='none';
      tip.style.left='50%';tip.style.top='90px';tip.style.transform='translateX(-50%)';
    }
  }
  function render(){
    var st=steps[i],last=i===steps.length-1;
    tip.innerHTML='<div class=coach-h>'+esc(st.title)+'</div>'+
      '<div class=coach-b>'+(st.text||'')+'</div>'+
      '<div class=coach-f><span class=coach-step>'+(i+1)+' / '+steps.length+'</span>'+
      '<span style="flex:1"></span>'+
      '<button type=button data-coach=skip class="btn sec sm">Skip</button>'+
      (i>0?'<button type=button data-coach=back class="btn sec sm">Back</button>':'')+
      '<button type=button data-coach=next class="btn sm">'+(last?'Done':'Next')+'</button></div>';
  }
  function adv(d){var n=i+d;if(n<0)n=0;if(n>=steps.length){return stop();}i=n;place();render();}
  function key(e){if(!on)return;if(e.key==='Escape'){stop();}else if(e.key==='ArrowRight'){adv(1);}else if(e.key==='ArrowLeft'){adv(-1);}}
  function stop(){on=false;document.removeEventListener('keydown',key,true);
    window.removeEventListener('resize',place);window.removeEventListener('scroll',place,true);
    if(box)box.remove();if(tip)tip.remove();box=tip=null;
    if(prevFocus&&prevFocus.focus){try{prevFocus.focus();}catch(e){}}}
  function build(){
    box=document.createElement('div');box.className='coach-spot';
    tip=document.createElement('div');tip.className='coach-tip';
    tip.setAttribute('role','dialog');tip.setAttribute('aria-modal','false');tip.tabIndex=-1;
    document.body.appendChild(box);document.body.appendChild(tip);
    tip.addEventListener('click',function(e){var a=e.target.closest('[data-coach]');if(!a)return;
      var k=a.getAttribute('data-coach');if(k==='skip')stop();else if(k==='back')adv(-1);else adv(1);});
  }
  function start(list){if(!list||!list.length)return;if(on)stop();
    steps=list;i=0;on=true;prevFocus=document.activeElement;build();place();render();
    document.addEventListener('keydown',key,true);
    window.addEventListener('resize',place);window.addEventListener('scroll',place,true);
    setTimeout(function(){if(tip)tip.focus();},60);}
  return {start:start,stop:stop};
})();
"""


# The "Connect your sources" walkthrough — spotlights the real tracker tiles, the
# AI-usage key field, and the run button. Auto-starts on ?tour=connect (from a
# "Show me how" entry point); also exposed as window.startConnectTour().
_CONNECT_TOUR_JS = r"""
<script>(function(){
  function run(){
    if(!window.Coach)return;
    window.Coach.start([
      {target:'.srcgrid',title:'Step 1 — Pick your tracker',
       text:'Choose where your work lives (GitHub, Jira, or Linear). Only the selected tracker’s fields appear below.'},
      {target:'input[name=anthropic_key]',title:'Step 2 — Connect your AI usage',
       text:'Paste a read-only Anthropic admin key (or a Cursor key). Running on Bedrock / Vertex / OpenAI? Those import on the Spend tab.'},
      {target:'#ob-sync',title:'Step 3 — Run your first audit',
       text:'Click here to pull your data and see every dollar mapped to the work that drove it.'}
    ]);
  }
  window.startConnectTour=run;
  if(new URLSearchParams(location.search).get('tour')==='connect'){
    if(document.readyState!=='loading')setTimeout(run,300);
    else document.addEventListener('DOMContentLoaded',function(){setTimeout(run,300);});
  }
})();</script>
"""


def page(title: str, body: str, account: dict | None = None, active: str = "", bare: bool = False,
         overlay: str = "") -> str:
    if account:
        links = _sidenav(account, active)
        # Routing-era vendor Overview/Review are parked; keep just the leads inbox.
        admin = ""
        if account.get("role") == "admin":
            admin = ('<div class=navgrp>Vendor</div>'
                     f'<a class="{"on" if active == "/admin/leads" else ""}" href="/admin/leads">Pilot requests</a>'
                     f'<a class="{"on" if active == "/admin/health" else ""}" href="/admin/health">Scheduler health</a>')
        em = _e(account.get("display_email") or account["email"])
        # Prefer a real display name (set in Settings) over the raw email in the sidebar.
        _dn = (account.get("display_name") or "").strip()
        who = (f'<div class=who style="font-weight:600;font-size:13px;'
               f'overflow:hidden;text-overflow:ellipsis;white-space:nowrap">{_e(_dn)}</div>'
               f'<div class=email>{em}</div>') if _dn and _dn != em else f'<div class=email>{em}</div>'
        # `overlay` is an undismissable, centered takeover (the first-run role gate):
        # the app renders behind it, blurred and non-interactive, so the customer
        # can't move on until they choose.
        shell_cls = "shell blurred" if overlay else "shell"
        takeover = f'<div class=takeover><div class=tk-card>{overlay}</div></div>' if overlay else ""
        chrome = (
            f'<div class="{shell_cls}"><aside class=side>'
            '<a class=brand href="https://outlay-ai.com/">Outlay<span class=dot>.ai</span></a>'
            f'<nav class=sidenav>{links}{admin}</nav>'
            f'<div class=side-foot>{_trial_pill(account)}{who}'
            '<form method=post action="/logout" style="margin:0">'
            '<button class="btn sec sm" style="width:100%;color:var(--red)">Sign out</button></form></div>'
            f'</aside><main class=main><div class=inner>{_demo_banner(account)}'
            f'{body}</div></main></div>'
            f'{takeover}')
    elif bare:
        # Minimal public header (brand only) — for the pilot-request form etc.
        chrome = (
            '<div class=top><div class=wrap style="padding-top:12px;padding-bottom:12px">'
            f'<a class=brand href="https://outlay-ai.com/">Outlay<span class=dot>.ai</span></a></div></div>'
            f'<div class=wrap style="max-width:640px">{body}</div>')
    else:
        nav = ('<div class="spacer"></div><div class="nav">'
               '<a href="/login">Sign in</a><a class="btn sm" href="/pilot-request">Become a customer</a></div>')
        chrome = (
            '<div class=top><div class=wrap style="padding-top:12px;padding-bottom:12px">'
            f'<a class=brand href="https://outlay-ai.com/">Outlay<span class=dot>.ai</span></a>{nav}'
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
<script>{_COACH_JS}</script>
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


def _onboarding(conn: dict | None, report: dict | None, has_budget: bool, persona: str = "",
                demo_mode: bool = False) -> str:
    """A first-run checklist that disappears once the customer is set up. Each step
    reflects real state so it doubles as a 'what's left' guide during a pilot. In
    demo mode it's hidden — the account is presented as an already-running customer."""
    if demo_mode:
        return ""
    # Business never does setup — connecting trackers, AI usage, running audits and
    # reconciling are all engineering's job. Business manages the spend after the
    # fact, so the setup checklist is hidden entirely for the business persona.
    if persona == "business":
        return ""
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
    has_identity = bool(conn.get("identity_map"))
    has_reconciled = bool(((report or {}).get("reconciliation") or {}).get("invoice_usd"))
    # Endowed progress: the account already exists, so the checklist opens non-empty
    # (a robust completion nudge — goal-gradient/endowed-progress, Kivetz 2006).
    # Each step deep-links to the real control; `tour` keys a contextual walkthrough.
    steps = [
        ("Create your account", True, "/app", "", None),
        ("Connect a tracker", has_tracker, "/app/outlay/connect", "Connect", "connect"),
        ("Connect your AI usage", has_usage, "/app/outlay/connect", "Add key", "connect"),
        ("Run your first audit", has_report, "/app/outlay/connect", "Run", "connect"),
        # Verifying the total reconciles to a real invoice is what turns "a number"
        # into "a number business trusts" — the activation step the trust work feeds.
        ("Verify your numbers", has_reconciled, "/app/outlay/connect", "Reconcile", "connect"),
    ]
    if persona == "business":
        # Cost-center allocation is the business lead view — make it a setup step.
        steps.append(("Map people to teams", has_identity, "/app/outlay/connect#teams", "Map teams", "teams"))
    steps.append(("Set a budget", has_budget, "/app/outlay/budgets", "Set a budget", "budgets"))

    total = len(steps)
    done = sum(1 for s in steps if s[1])
    if done == total:
        return ""
    pct = int(round(done / total * 100))
    rows = ""
    for label, d, href, cta, tour in steps:
        # Connect-flow steps launch the contextual walkthrough (?tour=connect),
        # so clicking the checklist item guides the user through the real controls.
        link = f"{href}?tour=connect" if tour == "connect" else href
        mark = ('<span class=ob-tick>✓</span>' if d else '<span class=ob-dot>○</span>')
        action = "" if d else f'<a href="{link}" class="btn sec sm" style="margin-left:auto">{cta}</a>'
        cls = " ob-done" if d else ""
        rows += (f'<div class="ob-row{cls}">{mark}<span class=ob-label>{_e(label)}</span>{action}</div>')
    return (
        '<div class="card ob-card" style="margin-bottom:16px">'
        '<div style="display:flex;justify-content:space-between;align-items:baseline">'
        f'<h3 style="margin:.2em 0 .2em">Get set up <span class=muted style="font-weight:400">· {done} of {total}</span></h3>'
        '<span class=muted style="font-size:12px">~10 minutes with read-only tokens</span></div>'
        f'<div class=ob-bar><span style="width:{pct}%"></span></div>{rows}</div>')


def _recon_strip(report: dict) -> str:
    """Reconciliation banner: Outlay's computed spend vs the provider's billed figure.
    The thing that lets business trust the number."""
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
    unrecognized model id). For a business product, an estimated number must never
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

    def _share(x):
        return f"{x / total * 100:.0f}%" if total > 0 else "0%"

    recs = ""
    if team_usd > 0:
        recs += (f'<li><b>{money(team_usd)}</b> (<b>{_share(team_usd)}</b> of spend) ran on branches with '
                 f'no ticket or linked PR. <b>Connect your PRs</b> — most reference the issue they close '
                 f'("Closes #123"), which recovers the link automatically, no branch renaming. '
                 f'<a href="/app/outlay/connect">Connect →</a></li>')
    if inv_usd > 0:
        recs += (f'<li><b>{money(inv_usd)}</b> (<b>{_share(inv_usd)}</b> of spend) had no team or ticket '
                 f'signal. Map people to teams (email / API-key id → team) so at least cost-center '
                 f'allocation lands. <a href="/app/outlay/connect#teams">Set up →</a></li>')
    if not recs:
        return ""
    # Honest upper bound: the team-tier spend already resolves to a team, so linking PRs
    # could lift ticket coverage by AT MOST its share (only the calls whose PR references
    # an issue actually recover). Framed as a ceiling — never a promised number.
    headroom = ""
    if team_usd > 0:
        headroom = (f'<p class="small muted" style="margin:8px 0 0">Connecting PRs could lift ticket '
                    f'coverage by <b>up to +{_share(team_usd)}</b> (to ~{min(100, (cov + team_usd / total) * 100):.0f}%) '
                    f'— only the calls whose PR references an issue recover, so treat it as a ceiling.</p>')
    return (f'<div class=ocard style="border-color:var(--amber);background:var(--amber-l)">'
            f'<div class=dh>Lift your ticket coverage'
            f'<span class=sub>{cov*100:.0f}% mapped to a ticket</span></div>'
            f'<p class=muted style="font-size:13px;margin:0 0 8px">Coverage depends on resolving each '
            f'AI call\'s branch to a ticket. Here\'s where yours is leaking — and the no-effort fix:</p>'
            f'<ul style="margin:0;padding-left:18px;font-size:13px;line-height:1.6">{recs}</ul>{headroom}</div>')


def _demo_banner(account: dict) -> str:
    """Global demo-mode strip. ON → persona toggle + guide + exit. For a gated demo
    account NOT in demo mode → a single 'Enter demo mode' affordance. Hidden for
    everyone else, so prospects/customers never see demo controls or sample data."""
    on = bool(account.get("demo_mode"))
    can = bool(account.get("_can_demo"))
    if not on and not can:
        return ""
    if not on:
        # Internal/test bar: standard experience + testing tools (re-run onboarding,
        # enter demo mode). Only ever shown to DEMO_ACCOUNT_EMAILS accounts.
        reset = ('<form method=post action="/app/onboarding/reset" style="margin:0" '
                 'onsubmit="return confirm(\'Reset this account to the first-run new-user '
                 'state? This clears the role choice and any spend data so you can re-run '
                 'onboarding.\')">'
                 '<button class="btn sec sm">Restart onboarding</button></form>')
        return ('<div class="demobar off"><span class=dl>Test account</span>'
                '<span class=dt>Standard customer experience.</span>'
                '<span class=sp></span>' + reset +
                '<form method=post action="/app/demo/enter" style="margin:0">'
                '<button class="btn sec sm">Enter demo mode →</button></form></div>')
    # The Business/Engineering persona toggle is gone — the dashboard is now one
    # unified adaptive view, so there are no separate "personas" to switch between
    # in a demo.
    return ('<div class="demobar"><span class=dl>● Demo mode</span>'
            '<span class=dt>Sample data — for live demos.</span>'
            '<span class=sp></span>'
            '<a class="btn sec sm" href="/app/demo/guide">Demo guide</a>'
            '<form method=post action="/app/demo/exit" style="margin:0">'
            '<button class="btn sec sm">Exit demo</button></form></div>')


def demo_guide_page(account: dict) -> str:
    """The presenter's talk track — the order to walk a prospect through each
    persona. Only reachable in demo mode (gated route)."""
    from . import demo as _demo

    def flow(persona: str, title: str, blurb: str) -> str:
        steps = ""
        for label, href, note in _demo.SCRIPT.get(persona, []):
            steps += (f'<li style="margin:10px 0;line-height:1.5"><a href="{href}"><b>{_e(label)}</b></a> '
                      f'<span class=muted>— {_e(note)}</span></li>')
        switch = (f'<form method=post action="/app/persona" style="margin:0 0 12px">'
                  f'<input type=hidden name=persona value="{persona}">'
                  f'<button class="btn sec sm">Switch to {_e(title)} view →</button></form>')
        return (f'<div class=ocard style="margin-top:16px"><div class=dh>{_e(title)} flow '
                f'<span class=sub>{_e(blurb)}</span></div>{switch}'
                f'<ol style="margin:6px 0 0;padding-left:20px">{steps}</ol></div>')

    body = (
        '<div class=ohead><h1>Demo guide</h1>'
        '<p>A suggested walkthrough for a live demo. Start with Business, then switch to '
        'Engineering — the nav and KPIs change with each persona. Everything here is seeded '
        'sample data.</p></div>'
        + flow("business", "Business", "allocate · budget · govern")
        + flow("eng", "Engineering", "forecast · estimate · ship efficiently")
        + '<p class=muted style="font-size:12.5px;margin-top:16px">Done? Use <b>Exit demo</b> in the '
          'top banner to wipe the sample data and return to the standard customer experience.</p>')
    return page("Demo guide", body, account, active="/app/outlay")


def _role_gate(next_to: str = "welcome") -> str:
    """The first-run question. Everyone gets the same unified dashboard — this only
    sets who connects the data (the setup path): 'eng' gets the connect/Sources
    setup surfaces; 'business' gets the attributed dashboard once a counterpart
    wires up the sources."""
    def tile(value: str, title: str, blurb: str) -> str:
        return (f'<form method=post action="/app/persona" style="margin:0;display:flex">'
                f'<input type=hidden name=persona value="{value}">'
                f'<input type=hidden name=next value="{next_to}">'
                f'<button class="bcard" style="width:100%;text-align:left;cursor:pointer;'
                f'display:flex;flex-direction:column">'
                f'<div style="font-size:16px;font-weight:700;color:var(--ink);line-height:1.35">{_e(title)}</div>'
                f'<div class=muted style="font-size:13px;margin-top:10px;line-height:1.55;flex:1">{_e(blurb)}</div>'
                f'<div style="margin-top:16px;color:var(--grn-d);font-weight:600;font-size:13px">Continue →</div>'
                f'</button></form>')
    tiles = (
        tile("eng", "I’ll connect our data",
             "You’ll wire up your work tracker and AI usage (read-only, a few minutes). Outlay then "
             "attributes every dollar to the work, and your whole team sees the same dashboard.")
        + tile("business", "Someone else connects our data",
               "Your engineering counterpart wires up the sources. You’ll get the attributed spend, "
               "the forecast vs budget, and the guardrails — with no setup on your side."))
    return ('<p class=muted style="font-size:13.5px;margin:0 0 14px">This just sets who connects the '
            'data — everyone sees the same dashboard.</p>'
            f'<div class=cols-2 style="display:grid;gap:16px">{tiles}</div>')


def _org_upload_form(next_to: str = "", kind: str = "title") -> str:
    """Upload that builds the people directory from a CSV (name, email, + a third
    detail). `kind="title"` → engineering 'direct reports' with a **job title**;
    `kind="team"` → a **team** for cost allocation. Names show spend by person."""
    nx = f'<input type=hidden name=next value="{next_to}">' if next_to else ""
    if kind == "title":
        title, sub, third, ex = ("Upload your direct reports", "names + job titles",
                                 "job title", "Jordan&nbsp;Lee, jordan@acme.com, Senior Engineer")
        third_desc = 'their <b>job title</b>'
    else:
        title, sub, third, ex = ("Upload your org", "names + teams",
                                 "team", "Jordan&nbsp;Lee, jordan@acme.com, Platform")
        third_desc = 'their <b>team</b> for cost-center allocation'
    return (
        f'<div class=ocard style="margin-top:16px"><div class=dh>{title} '
        f'<span class=sub>{sub}</span></div>'
        f'<p class=muted style="margin:-4px 0 12px;font-size:13.5px">One CSV builds your directory. Each '
        f'row is one person — we use their <b>name</b> to show spend by person (not just an email) and '
        f'record {third_desc}. Columns: <code>name</code>, <code>email</code>, <code>{third}</code>. '
        f'For a <b>service account / CI key</b>, put its key id in the email column and a friendly name. '
        f'<b>Then invite anyone with one click</b> from their tile below.</p>'
        f'<form method=post action="/app/team/roster" enctype="multipart/form-data" '
        f'style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">{nx}'
        f'<input type=hidden name=third value="{kind}">'
        f'<input type=file name=file accept=".csv,text/csv" required style="font-size:13px;max-width:240px">'
        f'<button class="btn">Upload</button>'
        f'<a class="btn sec sm" href="/app/team/roster-template.csv?third={kind}">Download template</a></form>'
        f'<p class=muted style="font-size:12px;margin-top:8px">Example row: <code>{ex}</code>.</p></div>')


def _parse_team_map(text: str) -> dict:
    """identity-map text → {identifier: team} (exact ids; includes @domain rules)."""
    out: dict[str, str] = {}
    for line in (text or "").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        sep = "->" if "->" in line else ("," if "," in line else None)
        if not sep:
            continue
        a, b = line.split(sep, 1)
        a, b = a.strip().lower(), b.strip()
        if a and b:
            out[a] = b
    return out


def _org_directory(account: dict, members: list[dict], next_to: str = "") -> str:
    """The org as a grid of person tiles — name, email/id, team — each with a
    one-click action: Invite (someone not yet on the team), role/remove (a member),
    or a 'service account' tag (a non-email identity). Built from the uploaded org
    (names + team map) unioned with actual members. Hidden until there's anyone."""
    from .store import TEAM_ROLES
    aid = account.get("id")
    names = store.get_outlay_identity_names(aid) if aid else {}
    titles = store.get_outlay_identity_titles(aid) if aid else {}
    teammap = _parse_team_map(store.get_outlay_identity_map(aid) if aid else "")
    owner = (account.get("email") or "").strip().lower()
    member_by = {(m.get("email") or "").strip().lower(): m for m in (members or [])}
    nx = f'<input type=hidden name=next value="{next_to}">' if next_to else ""

    ids = {i for i in (set(names) | set(titles) | set(member_by))
           if not i.startswith("@") and i != owner}
    if not names and not titles and not members:
        return ""

    def initials(label: str) -> str:
        parts = [p for p in re.split(r"[\s@._-]+", label) if p]
        return _e((parts[0][:1] + (parts[1][:1] if len(parts) > 1 else "")).upper() or "?")

    def team_tag(i: str) -> str:
        # Prefer a job title (engineering direct reports); fall back to team.
        t = titles.get(i) or teammap.get(i, "")
        return f'<span class=ptt>{_e(t)}</span>' if t else ""

    def tile(disp: str, sub: str, i: str, action: str, badge: str = "") -> str:
        return (f'<div class=ptile><div class=pav>{initials(disp or sub)}</div>'
                f'<div class=pmeta><div class=pnm>{_e(disp)}{badge}</div>'
                f'<div class=psub>{_e(sub)}</div>{team_tag(i)}</div>'
                f'<div class=pact>{action}</div></div>')

    tiles = (tile(account.get("email", ""), "account owner", owner,
                  '<span class="otag ok">owner</span>'))
    n_invitable = 0
    for i in sorted(ids, key=lambda x: (names.get(x) or x).lower()):
        nm = names.get(i)
        is_email = "@" in i and not i.startswith("@")
        m = member_by.get(i)
        if m:
            opts = "".join(f'<option value="{r}"{" selected" if m["role"]==r else ""}>{r}</option>'
                           for r in TEAM_ROLES)
            badge = ("" if m["status"] == "active"
                     else f' <span class="otag warn">{_e(m["status"])}</span>')
            action = (f'<form method=post action="/app/team/role" style="margin:0;display:flex;gap:6px">'
                      f'<input type=hidden name=member_id value="{m["id"]}">'
                      f'<select name=role>{opts}</select><button class="btn sec sm">Save</button></form>'
                      f'<form method=post action="/app/team/remove" style="margin:6px 0 0">'
                      f'<input type=hidden name=member_id value="{m["id"]}">'
                      f'<button class="btn sec sm">Remove</button></form>')
            tiles += tile(nm or m["email"], i, i, action, badge)
        elif is_email:
            n_invitable += 1
            action = (f'<form method=post action="/app/team/invite" style="margin:0">'
                      f'{nx}<input type=hidden name=email value="{_e(i)}">'
                      f'<button class="btn sm">Invite</button></form>')
            tiles += tile(nm or i, i, i, action)
        else:
            tiles += tile(nm or i, "service account", i,
                          '<span class=muted style="font-size:12px">mapped</span>')

    invite_all = ""
    if n_invitable:
        invite_all = (f'<form method=post action="/app/team/invite-all" style="margin:0">{nx}'
                      f'<button class="btn sec sm">Invite all {n_invitable} not yet invited</button></form>')
    count = 1 + len(ids)
    return (f'<div class=ocard style="margin-top:16px"><div class=dh '
            f'style="display:flex;justify-content:space-between;align-items:center;gap:10px">'
            f'<span>Your org <span class=sub>{count} {"person" if count == 1 else "people"}</span></span>'
            f'{invite_all}</div><div class=pgrid>{tiles}</div></div>')


def welcome_page(account: dict, conn: dict | None, idmap: str = "",
                 members: list[dict] | None = None) -> str:
    """First-run onboarding takeover. Step 1 (no persona yet) is the mandatory role
    gate; once a role is chosen it becomes Step 2 — add org structure + invite the
    counterpart — with a clear jump to the dashboard."""
    persona = (account.get("persona") or "").lower()
    if persona not in ("business", "eng"):
        # Step 1 — an undismissable, centered takeover over the blurred app. The
        # customer can't proceed to anything until they identify their role.
        gate = ('<div class=eyebrow style="font-size:11.5px;font-weight:600;letter-spacing:.1em;'
                'text-transform:uppercase;color:var(--grn-d)">Welcome to Outlay</div>'
                '<h1>First, who are you?</h1>'
                '<p class=muted style="margin:-2px 0 18px;max-width:60ch">This tailors your whole '
                'experience. You’ll invite your counterpart next, and can switch views anytime in '
                'Settings.</p>'
                + _role_gate("welcome"))
        # A faint dashboard skeleton sits behind the blur so the takeover reads as a
        # modal over the product, not a blank page.
        skel_kpi = '<div class=kpi><div class=l>&nbsp;</div><div class=v>—</div><div class=s>&nbsp;</div></div>'
        behind = ('<div class=ohead><h1>Your AI spend at a glance</h1>'
                  '<p>Setting up your workspace…</p></div>'
                  f'<div class=kpis>{skel_kpi * 4}</div>'
                  '<div class=ocard style="height:150px"></div>'
                  '<div class=ocard style="height:150px;margin-top:16px"></div>')
        return page("Welcome", behind, account, active="/app", overlay=gate)

    fin = persona == "business"
    counter_persona = "eng" if fin else "business"
    counter_label = "engineering leader" if fin else "business leader"
    placeholder = "vp.eng@company.com" if fin else "cfo@company.com"

    # Share with the other discipline's leader. Single fixed role (no picker): the
    # business leader invites their engineering counterpart, and vice-versa.
    share_title = "Invite your counterpart" if fin else "Share with your business partner"
    share_btn = "Send invite" if fin else "Share with business"
    share_card = (
        f'<div class=ocard style="margin-top:16px"><div class=dh>{share_title}</div>'
        f'<p class=muted style="margin:-4px 0 10px;font-size:13.5px">Outlay is best when business and '
        f'engineering share one workspace. Invite your {counter_label} — they’ll land straight in their own '
        f'view, with no setup question to answer.</p>'
        '<form method=post action="/app/team/invite" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">'
        '<input type=hidden name=next value="welcome"><input type=hidden name=role value="admin">'
        f'<input type=hidden name=persona value="{counter_persona}">'
        '<label class=fld style="flex:1;min-width:260px"><span>Their work email</span>'
        f'<input name=email type=email placeholder="{placeholder}" required></label>'
        f'<button class=btn>{share_btn}</button></form>'
        '<p class=muted style="font-size:12.5px;margin-top:6px">They get a link to set a password. '
        'Manage everyone on the <a href="/app/team">Team</a> page.</p></div>')

    done = ('<div style="margin-top:20px;display:flex;gap:12px;align-items:center">'
            '<a class="btn" href="/app/outlay">Go to my dashboard →</a>'
            '<span class=muted style="font-size:12.5px">These steps are optional — you can do them later '
            'from Connect and Team.</span></div>')
    if fin:
        # Business: just share with the engineering counterpart (no org upload).
        intro = '<p>Invite your engineering counterpart, then jump into the product.</p>'
        body = f'<div class=ohead><h1>You’re set up as Business</h1>{intro}</div>' + share_card + done
    else:
        # Engineering: upload direct reports (job titles), then share with business.
        intro = ('<p>Upload your direct reports and invite them with one click, share with your business '
                 'partner, then jump into the product.</p>')
        body = (f'<div class=ohead><h1>You’re set up as Engineering</h1>{intro}</div>'
                + _org_upload_form("welcome", "title")
                + _org_directory(account, members or [], "welcome") + share_card + done)
    return page("Welcome", body, account, active="/app")


def _kpicard(label, value, sub, grn=False, href=None) -> str:
    inner = (f'<div class=l>{_e(label)}</div>'
             f'<div class="v{" grn" if grn else ""}">{value}</div><div class=s>{sub}</div>')
    if href:
        return f'<a class=kpi href="{href}">{inner}<span class=kdrill>→</span></a>'
    return f'<div class=kpi>{inner}</div>'


def _hero_unit_cost(report: dict) -> str:
    """The anchor metric — cost per *delivered* unit of work — as a hero band.

    Not 'we spent $X' but 'each shipped feature/bugfix cost $Y' — the single number
    finance and eng both understand. Per-class chips show where the cost concentrates."""
    from outlay.units import cost_per_unit
    u = cost_per_unit(report)
    if not u["units_shipped"]:
        return ""
    # Chips drill into that work type's tickets — fluid drill-down from the anchor
    # metric (total → class → the tickets behind it).
    chips = "".join(
        f'<a href="/app/outlay/scope?type=class&id={quote(str(c["task_class"] or ""))}" '
        f'style="border:1px solid #cfe6dc;border-radius:999px;padding:4px 11px;'
        f'font-size:12.5px;color:var(--grn-d);text-decoration:none">'
        f'<b>{money(c["cost_per_unit_usd"])}</b> '
        f'<span style="color:var(--mut)">/ {_e(c["task_class"])} →</span></a>'
        for c in u["by_class"][:5])
    return (
        '<div class=ocard style="background:var(--grn-l);border-color:#bfe3d4;margin-bottom:14px">'
        '<div style="display:flex;align-items:baseline;gap:14px;flex-wrap:wrap">'
        f'<span style="font-size:30px;font-weight:700;letter-spacing:-.01em;color:var(--grn-d)">'
        f'{money(u["cost_per_unit_usd"])}</span>'
        '<span style="font-size:14px;color:var(--grn-d);font-weight:600">AI cost per shipped unit of work</span>'
        f'<span style="font-size:12.5px;color:var(--mut)">across {u["units_shipped"]} delivered items '
        f'· {money(u["total_attributed_usd"])} attributed</span></div>'
        f'<div style="display:flex;gap:8px;flex-wrap:wrap;margin-top:12px">{chips}</div></div>')


def _trust_panel(report: dict, conn: dict | None = None) -> str:
    """ONE consolidated trust/data-quality panel — replaces the four strips that used
    to stack on Spend (data-quality badge + "measured, not asserted" strip +
    reconciliation strip + coverage diagnostic). No information lost: the headline
    measured facts lead, a Good/Fair/Poor verdict chip rolls it up, and the detailed
    checks (coverage, reconciliation, pricing fidelity, sync) collapse under a
    disclosure. The Weave move — lead with the validation — minus the clutter."""
    sp = report.get("spend", {}) or {}
    if not sp.get("total_usd", 0):
        return ""
    cal = report.get("calibration") or {}
    bf = sp.get("by_fidelity_usd", {}) or {}
    attributed = sp.get("attributed_to_ticket_usd", 0.0) or 0.0

    facts = []
    if cal.get("n_evaluated", 0) > 0:
        facts.append(
            f'<b>Forecast within ~{cal.get("mdape", 0) * 100:.0f}%</b> of actual '
            f'<span class=muted>(back-test, n={cal.get("n_evaluated")})</span>')
    high = (bf.get("call", 0.0) or 0.0) + (bf.get("branch", 0.0) or 0.0) + (bf.get("session", 0.0) or 0.0)
    if attributed > 0:
        facts.append(f'<b>{high / attributed * 100:.0f}%</b> joined at ticket-level fidelity')

    # Rolled-up verdict + the per-signal checks (coverage / reconciliation / pricing / sync).
    from . import outlay_app  # lazy: outlay_app never imports web
    dq = outlay_app.data_quality(report, conn or {})
    vmap = {"good": ("Good", "var(--grn-d)", "var(--grn-l)"),
            "fair": ("Fair", "var(--amber)", "var(--amber-l)"),
            "poor": ("Poor", "var(--red)", "var(--red-l)")}
    chip = ""
    if dq.get("score") in vmap:
        lab, col, bg = vmap[dq["score"]]
        chip = (f'<span style="font-size:11.5px;font-weight:700;color:{col};background:{bg};'
                f'border-radius:999px;padding:3px 10px">Data quality: {lab}</span>')
    rows = ""
    for c in dq.get("checks", []):
        st = c.get("status", "na")
        if st == "na":
            continue
        dot = {"good": "var(--grn-d)", "fair": "var(--amber)", "poor": "var(--red)"}.get(st, "var(--mut)")
        rows += (f'<li style="margin:4px 0"><span style="color:{dot}">●</span> '
                 f'<b>{_e(c.get("label",""))}</b> — <span class=muted>{_e(c.get("detail",""))}</span></li>')
    details = (f'<details style="margin-top:10px"><summary class=muted '
               f'style="font-size:12.5px;cursor:pointer">Data-quality checks</summary>'
               f'<ul style="list-style:none;padding:8px 0 0;font-size:13px">{rows}</ul></details>') if rows else ""

    if not facts and not chip:
        return ""
    items = ' &nbsp;·&nbsp; '.join(facts) or '<span class=muted>Coverage, reconciliation and pricing checks below.</span>'
    return (
        '<div class=ocard style="border-color:#bfe3d4;margin-bottom:14px">'
        '<div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">'
        '<span style="font-size:12px;font-weight:700;letter-spacing:.05em;text-transform:uppercase;'
        'color:var(--grn-d)">✓ Measured, not asserted</span>'
        f'{chip}<a class=sub href="/app/outlay/accuracy" style="margin-left:auto">How we measure →</a></div>'
        f'<div style="font-size:13.5px;color:var(--body);margin-top:8px">{items}</div>'
        f'{details}</div>')


def _spend_dim_panel(dims: list, sub_html: str = "") -> str:
    """One 'Where your AI spend went' card with a CSS-only dimension toggle (no JS) —
    replaces the four stacked breakdown cards (ticket / work type / team / engineer).
    `dims` = [(id, label, rows_html), ...]; the first is shown by default. Mirrors the
    lens switcher the Overview already uses."""
    dims = [d for d in dims if d]
    if not dims:
        return ""
    radios = "".join('<input type=radio name=spdim id=sp-%s class=sptab%s>'
                     % (d[0], " checked" if i == 0 else "") for i, d in enumerate(dims))
    tabs = "".join('<label for=sp-%s>%s</label>' % (d[0], _e(d[1])) for d in dims)
    panes = "".join('<div class="sppane sp-%s">%s</div>' % (d[0], d[2]) for d in dims)
    show = "".join(
        ("#sp-%s:checked~.sptabs label[for=sp-%s]{background:var(--grn-l);border-color:#bfe3d4;"
         "color:var(--grn-d);font-weight:600}#sp-%s:checked~.sp-%s{display:block}")
        % (d[0], d[0], d[0], d[0]) for d in dims)
    css = ("<style>.sptab{position:absolute;opacity:0;width:0;height:0}"
           ".sptabs{display:flex;gap:6px;flex-wrap:wrap;margin:2px 0 12px}"
           ".sptabs label{font-size:12.5px;padding:5px 11px;border:1px solid var(--line);"
           "border-radius:999px;cursor:pointer;color:var(--muted)}"
           ".sppane{display:none}" + show + "</style>")
    return ('<div class=ocard>%s%s<div class=dh>Where your AI spend went%s</div>'
            '<div class=sptabs>%s</div>%s</div>') % (css, radios, sub_html, tabs, panes)


def _kpis_row(report: dict, history: list[dict] | None, persona: str = "") -> str:
    """The four headline KPIs — one unified set for everyone (no persona split):
    money · attribution coverage · runaway tickets · forecast. Team/cost-center
    allocation now lives one click away in the breakdown panel's "By team" tab, so
    finance and engineering share the same headline. Each KPI drills into the
    surface that explains it."""
    sp = report.get("spend", {})
    fc = report.get("forecast", {})
    cov = sp.get("ticket_coverage", 0.0)
    spend_kpi = _kpicard("AI spend · window", money(sp.get("total_usd", 0)), _trend_delta(history or []))
    cov_kpi = _kpicard("Mapped to a ticket", f"{cov*100:.0f}%",
                       money(sp.get("attributed_to_ticket_usd", 0)) + " attributed", grn=cov >= 0.6)
    anoms = report.get("anomalies") or []
    top = anoms[0] if anoms else None
    anom_kpi = _kpicard(
        "Runaway tickets", str(len(anoms)),
        (f"top: {_e(str(top['ticket_id']))} · {top['ratio']:.1f}× median" if top else "none over threshold"),
        grn=not anoms,
        href=(f'/app/outlay/scope?type=class&id={quote(str(top.get("task_class") or ""))}'
              if top and top.get("task_class") else None))
    fc_kpi = _kpicard("Forecast · open work", money(fc.get("expected_usd", 0)),
                      f"likely {money(fc.get('low_usd', 0))}–{money(fc.get('high_usd', 0))}",
                      href="/app/outlay/estimate")
    return '<div class=kpis>' + spend_kpi + cov_kpi + anom_kpi + fc_kpi + '</div>'


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


def _anomaly_prefs(conn: dict | None) -> tuple[float, set]:
    """(threshold, muted_ids) from the stored connection row — floored at 3×."""
    conn = conn or {}
    thr = conn.get("anomaly_threshold")
    thr = float(thr) if thr and thr >= 3.0 else 3.0
    try:
        muted = set(_json.loads(conn.get("muted_tickets") or "[]"))
    except (ValueError, TypeError):
        muted = set()
    return thr, muted


def _visible_anomalies(report: dict, threshold: float, muted) -> list:
    """Anomalies after the customer's tuning: at/above their threshold and not muted.
    Each anomaly carries its ratio, so this is a pure filter — no re-run needed."""
    muted = muted or set()
    return [a for a in ((report or {}).get("anomalies") or [])
            if a.get("ratio", 0) >= threshold and a.get("ticket_id") not in muted]


def _anomaly_strip(report: dict, threshold: float = 3.0, muted=None) -> str:
    """One-line Overview banner: N runaway tickets and the spend above their class
    median. The guardrail that binds on outliers, not on every task."""
    an = _visible_anomalies(report, threshold, muted)
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


def _anomaly_card(report: dict, threshold: float = 3.0, muted=None, controls: bool = False) -> str:
    """The runaway-ticket detail: each outlier, its cost vs its work-type median, and
    how many times over. With `controls`, adds a threshold tuner, per-row mute, and
    an unmute list — so a known-expensive ticket can be silenced and the bar raised."""
    muted = muted or set()
    an = _visible_anomalies(report, threshold, muted)
    raw = (report or {}).get("anomalies") or []
    if not an and not (controls and (muted or raw)):
        return ""
    worst = (an[0].get("ratio", 1) if an else 1) or 1
    rows = ""
    for a in an[:12]:
        ratio = a.get("ratio", 0)
        col = "var(--red)" if ratio >= 5 else "var(--amber)"
        med = a.get("class_median_usd", 0)
        tid = a.get("ticket_id")
        mute_btn = (f'<form method=post action="/app/outlay/anomaly/mute" style="margin:0 0 0 8px;display:inline">'
                    f'<input type=hidden name=ticket_id value="{_e(tid)}">'
                    f'<button class="btn sec sm" style="padding:1px 7px;font-size:11px">mute</button></form>'
                    if controls else "")
        rows += (f'<div class=erow><span class=nm>{_e(tid)} '
                 f'<small>· {_e(a.get("task_class"))} · vs {money(med)} median</small></span>'
                 f'<span class=amt>{money(a.get("cost_usd", 0))} '
                 f'<span style="color:{col};font-weight:600;font-size:12px">{ratio:.0f}×</span>{mute_btn}</span>'
                 f'<div class=ebar><span style="width:{min(100, ratio / worst * 100):.0f}%;'
                 f'background:{col}"></span></div></div>')
    if not rows:
        rows = '<p class=muted style="font-size:13px;margin:0">No tickets above your current threshold.</p>'

    tuner = ""
    if controls:
        unmute = ""
        if muted:
            chips = "".join(
                f'<form method=post action="/app/outlay/anomaly/unmute" style="margin:0;display:inline">'
                f'<input type=hidden name=ticket_id value="{_e(m)}">'
                f'<button class="btn sec sm" style="padding:1px 7px;font-size:11px">{_e(m)} ✕</button></form>'
                for m in sorted(muted))
            unmute = (f'<div style="margin-top:10px;display:flex;gap:6px;flex-wrap:wrap;align-items:center">'
                      f'<span class=muted style="font-size:12px">Muted ({len(muted)}):</span>{chips}</div>')
        tuner = (
            f'<div style="margin-top:12px;padding-top:12px;border-top:1px solid var(--line);'
            f'display:flex;gap:8px;align-items:center;flex-wrap:wrap">'
            f'<form method=post action="/app/outlay/anomaly/threshold" style="margin:0;display:flex;gap:6px;align-items:center">'
            f'<span class=muted style="font-size:12.5px">Flag at</span>'
            f'<input name=threshold type=number min=3 max=50 step=1 value="{threshold:.0f}" '
            f'aria-label="Anomaly flag threshold, multiples of the class median" '
            f'style="width:64px;padding:5px 8px;border:1px solid var(--line);border-radius:8px">'
            f'<span class=muted style="font-size:12.5px">× class median</span>'
            f'<button class="btn sec sm">Apply</button></form></div>{unmute}')

    return (f'<div class=ocard><div class=dh>Runaway tickets'
            f'<span class=sub>&ge;{threshold:.0f}&times; their work-type median</span></div>{rows}'
            f'<p class=muted style="font-size:12px;margin-top:10px">Where a single ticket is burning far '
            f'more than its peers — the place to look first, not an average everyone pays.</p>{tuner}</div>')


def _model_card(report: dict) -> str:
    """Spend + token usage per model — the FinOps 'cost-per-token across models'
    view. Reads cost_fidelity.by_model (cost, events, and the token split that
    makes the cache-aware number defensible)."""
    cf = (report or {}).get("cost_fidelity") or {}
    bm = cf.get("by_model") or {}
    if not bm:
        return ""
    mx = max((m.get("outlay_usd", 0) for m in bm.values()), default=1) or 1
    rows = ""
    for name, m in bm.items():
        tok = m.get("tokens") or {}
        total_tok = sum(int(tok.get(k, 0)) for k in ("input", "output", "cache_read", "cache_write"))
        cr = int(tok.get("cache_read", 0))
        cache_pct = f" · {cr / total_tok * 100:.0f}% cache" if total_tok else ""
        rows += (f'<div class=erow><span class=nm>{_e(name)} '
                 f'<small>· {m.get("events", 0):,} calls · {total_tok / 1e6:.1f}M tokens{cache_pct}</small></span>'
                 f'<span class=amt>{money(m.get("outlay_usd", 0))}</span>'
                 f'<div class=ebar><span style="width:{max(2, m.get("outlay_usd", 0) / mx * 100):.0f}%;'
                 f'background:var(--grn)"></span></div></div>')
    return (f'<div class=ocard><div class=dh>Spend by model'
            f'<a class=sub href="/app/outlay/export.csv?view=models">export →</a></div>{rows}'
            f'<p class=muted style="font-size:12px;margin-top:10px">Each model priced per token class '
            f'(input / output / cache read / cache write) — cache reads bill at ~1/10th, which is why the '
            f'per-model number is far below a naive token count.</p></div>')


def _sample_strip(report: dict, account: dict | None = None) -> str:
    """Banner shown while viewing the worked sample dataset rather than real spend.
    Suppressed in demo mode — the global demo banner already says so."""
    if not report.get("_sample") or (account or {}).get("demo_mode"):
        return ""
    return ('<div class=ostrip style="background:#eef2fb;border:1px solid #d3def5">'
            '<span><b style="color:#2451b3">Sample data</b> — a worked example so you can see the '
            'product end-to-end, not your real spend. <a href="/app/outlay/connect">Connect your sources →</a></span>'
            '<form method=post action="/app/outlay/clear" style="margin:0">'
            '<button class="btn sec sm">Clear sample data</button></form></div>')


def _data_quality_badge(report: dict, conn: dict | None) -> str:
    """A single 'can I trust these numbers?' verdict — Good / Fair / Poor — with the
    contributing checks one click away. The individual signals already render as
    strips below; this is the at-a-glance rollup business asked for. Hidden until
    there's real spend to judge."""
    if not (report or {}).get("spend", {}).get("total_usd", 0):
        return ""
    from . import outlay_app  # lazy: outlay_app never imports web
    dq = outlay_app.data_quality(report, conn or {})
    score = dq.get("score", "na")
    if score == "na":
        return ""
    tone = {"good": ("var(--grn-d)", "var(--grn-l)", "Good"),
            "fair": ("var(--amber)", "var(--amber-l)", "Fair"),
            "poor": ("var(--red)", "var(--red-l)", "Poor")}[score]
    mark = {"good": "✓", "fair": "•", "poor": "⚠"}[score]
    rows = ""
    for c in dq.get("checks", []):
        st = c.get("status", "na")
        dot = {"good": "var(--grn-d)", "fair": "var(--amber)",
               "poor": "var(--red)", "na": "var(--mut)"}.get(st, "var(--mut)")
        lab = "n/a" if st == "na" else st
        rows += (f'<li style="margin:4px 0"><span style="color:{dot};font-weight:600">●</span> '
                 f'<b>{_e(c.get("label",""))}</b> — <span class=muted>{_e(c.get("detail",""))}</span> '
                 f'<span style="color:{dot};font-size:11px;text-transform:uppercase">{lab}</span></li>')
    return (f'<details class=dqbadge style="margin:0 0 14px">'
            f'<summary style="display:inline-flex;align-items:center;gap:8px;cursor:pointer;'
            f'padding:5px 11px;border-radius:999px;background:{tone[1]};color:{tone[0]};'
            f'font-size:13px;font-weight:600;list-style:none">'
            f'{mark} Data confidence: {tone[2]}<span class=muted style="font-weight:400;font-size:12px">'
            f'· what\'s this?</span></summary>'
            f'<ul style="margin:10px 0 0;padding-left:4px;list-style:none;font-size:13px">{rows}</ul>'
            f'</details>')


def _staleness_banner(report: dict, conn: dict | None) -> str:
    """Loud, top-of-page banner when the numbers may be stale — the #1 silent
    failure for a spend tool is data that quietly stopped updating. Fires when
    auto-sync is failing, or when data is well past its expected refresh window
    (cron down, token revoked). Stays hidden when the pipeline is healthy."""
    import time
    conn = conn or {}
    synced_at = conn.get("synced_at")
    asy = conn.get("auto_sync_hours") or 0
    failing = conn.get("sync_fail_count") or 0
    # How long since the last *successful* refresh?
    age_h = ((time.time() - synced_at) / 3600) if synced_at else None

    # Standing auto-sync failure → data is frozen at the last good pull.
    if failing >= 2 and asy:
        last = _fmt_date(synced_at) if synced_at else "never"
        return (f'<div class=ostrip style="background:var(--red-l)">'
                f'<span><span class="otag over">stale</span> '
                f'<b style="color:var(--red)">Auto-sync has failed {failing} times.</b> '
                f"You're seeing the last good numbers from <b>{last}</b>, not current spend. "
                f'<a href="/app/outlay/connect" style="color:var(--red)">Fix the connection →</a></span></div>')
    # Auto-sync on and data is past ~2× its interval → the refresh pipeline stalled.
    if asy and age_h is not None and age_h > 2 * asy:
        days = age_h / 24
        when = f"{days:.0f} days" if days >= 1.5 else f"{age_h:.0f} hours"
        return (f'<div class=ostrip style="background:var(--amber-l)">'
                f'<span><span class="otag warn">stale</span> '
                f'<b style="color:var(--amber)">Data is {when} old</b> — older than its '
                f'{"daily" if asy == 24 else "weekly"} refresh window. The auto-sync may have stalled. '
                f'<a href="/app/outlay/connect">Check the connection →</a> or refresh now.</span></div>')
    return ""


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
           if persona == "business" else "This is the cache-aware figure")
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


def _finance_waiting(account: dict) -> str:
    """The business empty-state. Business never connects anything — engineering does
    all the setup. So instead of a 'Connect your sources' CTA, business sees a calm
    'your data is on its way' state with a one-click invite for the engineering
    counterpart who actually wires up the sources."""
    intro = (
        '<div class=ohead><h1>Your AI spend dashboard is on its way.</h1>'
        '<p>Outlay connects to your AI usage and work tracker — read-only — and turns it into '
        'total spend, a quarter forecast against budget, and a breakdown by team and project. '
        '<b>That setup is engineering’s job</b>, not yours. Once your engineering counterpart connects '
        'the sources, your numbers fill in here automatically — nothing for you to install.</p></div>')
    # Sample preview stays demo-account-only (the standing rule), so the founder can
    # walk a business prospect through the real dashboard instead of an empty room.
    preview = ('<div class="row" style="margin:0 0 18px"><form method=post action="/app/outlay/sample" '
               'style="margin:0"><button class="btn">See it with sample data →</button></form>'
               '<span class=muted style="font-size:12.5px;align-self:center">Preview the business dashboard '
               'with a worked example.</span></div>') if account.get("_can_demo") else ""
    steps = (
        '<div class=ocard style="margin-top:4px"><div class=dh>What happens next</div>'
        '<ol style="margin:6px 0 0;padding-left:20px;font-size:14px;line-height:1.7">'
        '<li>Your engineering counterpart connects the AI provider + tracker (read-only).</li>'
        '<li>Outlay runs the first audit and reconciles it to the real invoice.</li>'
        '<li>Your spend, forecast, and per-team breakdown appear on this page.</li>'
        '</ol></div>')
    invite = (
        '<div class=ocard style="margin-top:16px"><div class=dh>Invite your engineering counterpart</div>'
        '<p class=muted style="margin:-4px 0 10px;font-size:13.5px">They’ll land straight in their own '
        'engineering view and do the one-time connection. You’ll see the data the moment they sync.</p>'
        '<form method=post action="/app/team/invite" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">'
        '<input type=hidden name=role value="admin"><input type=hidden name=persona value="eng">'
        '<label class=fld style="flex:1;min-width:260px"><span>Their work email</span>'
        '<input name=email type=email placeholder="vp.eng@company.com" required></label>'
        '<button class=btn>Send invite</button></form>'
        '<p class=muted style="font-size:12.5px;margin-top:6px">Manage everyone on the '
        '<a href="/app/team">Team</a> page.</p></div>')
    return intro + preview + steps + invite


def _fa_item(sev: int, color: str, text_html: str, href: str, label: str) -> tuple:
    """One 'Needs your attention' row: a colored dot, the alert text (itself clickable
    and deep-linked to the exact item that needs fixing — not a generic list), and an
    action button to the same place. So the customer can click the flag and act on it."""
    return (sev,
            f'<span class=fa-dot style="background:{color}"></span>'
            f'<a class=fa-txt href="{href}">{text_html}</a>'
            f'<a class="btn sec sm" href="{href}">{label}</a>')


def _attention_card(items: list, all_clear: str) -> str:
    """Render ONE 'Needs your attention' card from (severity, html) items — or the
    supplied all-clear when there's nothing to flag. Shared by the finance panel,
    the eng panel, and the unified Home (which merges both)."""
    items = sorted(items, key=lambda x: x[0], reverse=True)
    if not items:
        return all_clear
    n_over = sum(1 for sev, _ in items if sev == 2)
    rows = "".join(f'<div class=fa-row>{h}</div>' for _, h in items)
    headline = (f'{n_over} need{"s" if n_over == 1 else ""} action' if n_over
                else f'{len(items)} to keep an eye on')
    accent = "var(--red)" if n_over else "var(--amber)"
    return (f'<div class=ocard style="margin-bottom:16px;border-color:{accent}">'
            f'<div class=dh style="display:flex;align-items:center;gap:8px">Needs your attention '
            f'<span class="otag {"over" if n_over else "warn"}">{headline}</span></div>'
            f'<div class=fa-list>{rows}</div></div>')


def _attention_dedupe(items: list) -> list:
    """Merge finance + eng attention items: the same target (deep-link href) about the
    same subject (first bolded name) is the same problem stated twice — keep the first.
    This is what stops the unified Home showing 'Needs your attention' twice with the
    same runaway tickets and over-budgets in both."""
    seen, out = set(), []
    for sev, h in items:
        mh = re.search(r'href="([^"]+)"', h)
        mb = re.search(r"<b>(.*?)</b>", h)
        key = (mh.group(1) if mh else "", mb.group(1) if mb else h[:60])
        if key in seen:
            continue
        seen.add(key)
        out.append((sev, h))
    return out


_FIN_ALL_CLEAR = (
    '<div class=ocard style="margin-bottom:16px;border-color:var(--grn);background:var(--grn-l)">'
    '<div style="display:flex;align-items:center;gap:8px">'
    '<span class=fa-dot style="background:var(--grn-d)"></span>'
    '<b style="color:var(--grn-d)">All programs and budgets are on track.</b>'
    '<span class=muted style="font-size:12.5px">No overspend projected and no runaway '
    'tickets — nothing to action right now.</span></div></div>')


def _attention_combined(report: dict | None, conn: dict | None, history: list[dict] | None,
                        budget_statuses: list[dict] | None,
                        program_statuses: list[dict] | None) -> str:
    """The unified Home panel: business signals (budgets/programs/runaways) and
    engineering signals (sync health, coverage, spikes, pricing fidelity) merged into
    ONE deduped 'Needs your attention' card."""
    items = _attention_dedupe(
        _finance_attention_items(report, budget_statuses, program_statuses)
        + _eng_attention_items(report, conn, history, budget_statuses))
    return _attention_card(items, _FIN_ALL_CLEAR)


def _finance_attention(report: dict | None, budget_statuses: list[dict] | None,
                       program_statuses: list[dict] | None) -> str:
    """Business's 'review these' panel (card form) — see _finance_attention_items."""
    return _attention_card(_finance_attention_items(report, budget_statuses, program_statuses),
                           _FIN_ALL_CLEAR)


def _finance_attention_items(report: dict | None, budget_statuses: list[dict] | None,
                             program_statuses: list[dict] | None) -> list:
    """Business's 'review these' signals — auto-flags what's off track so business can act
    without drilling into the data: programs/budgets already over or projected to
    overspend, and runaway tickets. Each item is plain language with the dollar figure
    and a one-click deep link to address it."""
    items = []  # (severity, html) — severity 2 = over, 1 = warn/anomaly

    def over_amt(s):
        return (s.get("projected_usd", 0) or 0) - (s.get("limit_usd", 0) or 0)

    for s in (program_statuses or []):
        if not s.get("limit_usd"):
            continue
        nm = _e(s.get("name") or "program")
        tl = s.get("timeline") or {}
        pc = s.get("pacing") or {}
        pr = s.get("progress") or {}
        ready = pc.get("ready")
        proj = pc.get("projected_end_usd", 0) if ready else s.get("projected_usd", 0)
        # Earned-value (forecast vs actual on completed work) adds an execution read on top
        # of the budget overspend flag — append it when we have a confident rating.
        ev = pr if pr.get("ready") else None
        if ev and abs(ev.get("cost_variance_pct", 0)) >= 0.05:
            cv = ev["cost_variance_pct"] * 100
            ev_bit = (f' · completed work is <b>{abs(cv):.0f}% {"over" if cv > 0 else "under"} '
                      f'forecast</b> at {ev.get("progress_pct",0)*100:.0f}% done')
        else:
            ev_bit = ""
        if ready and pc.get("projected_breach_date") and pc["projected_breach_date"] != "now":
            when = f' — projected to exceed budget on <b>{_e(pc["projected_breach_date"])}</b>'
        elif tl.get("breach_month"):
            when = f' — set to breach in <b>{_e(tl["breach_month"])}</b>'
        else:
            when = ""
        over = (proj or 0) - (s.get("limit_usd", 0) or 0)
        phref = f'/app/outlay/programs#prog-{s.get("id")}'
        if s.get("status") == "over":
            already = (s.get("spent_usd", 0) or 0) >= (s.get("limit_usd", 0) or 0)
            verb = ("is off track on forecast" if (ev and ev["status"] == "over"
                                                   and not (already or over > 0))
                    else ("is already over budget" if already else "is projected to overspend"))
            items.append(_fa_item(2, "var(--red)",
                          f'Program <b>{nm}</b> {verb} — projected '
                          f'<b>{money(proj)}</b> vs {money(s.get("limit_usd",0))} cap '
                          f'({money(abs(over))} over){ev_bit}{when}.',
                          phref, "Raise cap or enforce →"))
        elif s.get("status") == "warn":
            items.append(_fa_item(1, "var(--amber)",
                          f'Program <b>{nm}</b> is tracking hot — projected '
                          f'<b>{money(proj)}</b> of {money(s.get("limit_usd",0))} '
                          f'({s.get("pct_used",0)*100:.0f}% used){ev_bit}{when}.',
                          phref, "Reallocate →"))

    for s in (budget_statuses or []):
        if not s.get("limit_usd"):
            continue
        scope = _e(s.get("scope_type") or "") + (f' {_e(s.get("scope_id"))}' if s.get("scope_id") else "")
        scope = scope.strip() or "overall"
        bhref = f'/app/outlay/budgets#budget-{s.get("id")}'
        if s.get("status") == "over":
            already = (s.get("spent_usd", 0) or 0) >= (s.get("limit_usd", 0) or 0)
            verb = "is already over budget" if already else "is projected to overspend"
            items.append(_fa_item(2, "var(--red)",
                          f'Budget <b>{scope}</b> {verb} — projected '
                          f'<b>{money(s.get("projected_usd",0))}</b> vs {money(s.get("limit_usd",0))} '
                          f'({money(abs(over_amt(s)))} over).',
                          bhref, "Adjust limit →"))
        elif s.get("status") == "warn":
            items.append(_fa_item(1, "var(--amber)",
                          f'Budget <b>{scope}</b> is tracking hot — projected '
                          f'<b>{money(s.get("projected_usd",0))}</b> of {money(s.get("limit_usd",0))} '
                          f'({s.get("pct_used",0)*100:.0f}% used).',
                          bhref, "Adjust limit →"))

    for a in (report or {}).get("anomalies", [])[:3]:
        tid = _e(str(a.get("ticket_id")))
        cls = a.get("task_class")
        href = (f'/app/outlay/scope?type=class&id={quote(str(cls))}' if cls else "/app/outlay")
        items.append(_fa_item(1, "var(--amber)",
                      f'Runaway ticket <b>{tid}</b> cost '
                      f'<b>{money(a.get("cost_usd",0))}</b> — {a.get("ratio",0):.1f}× its '
                      f'{_e(str(cls or "work-type"))} median.',
                      href, "Investigate →"))

    return items


_ENG_ALL_CLEAR = (
    '<div class=ocard style="margin-bottom:16px;border-color:var(--grn);background:var(--grn-l)">'
    '<div style="display:flex;align-items:center;gap:8px">'
    '<span class=fa-dot style="background:var(--grn-d)"></span>'
    '<b style="color:var(--grn-d)">Healthy — nothing to fix right now.</b>'
    '<span class=muted style="font-size:12.5px">No runaway tickets, coverage is solid, '
    'and the last sync succeeded.</span></div></div>')


def _eng_attention(report: dict | None, conn: dict | None, history: list[dict] | None,
                   budget_statuses: list[dict] | None) -> str:
    """Engineering's 'go fix this' panel (card form) — see _eng_attention_items."""
    return _attention_card(_eng_attention_items(report, conn, history, budget_statuses),
                           _ENG_ALL_CLEAR)


def _eng_attention_items(report: dict | None, conn: dict | None, history: list[dict] | None,
                         budget_statuses: list[dict] | None) -> list:
    """Engineering's 'go fix this' signals — operational, not budget-governance: runaway
    tickets, attribution leaks, a sudden spend jump, a stale/failed sync, and spend
    priced by a fallback tier. Each one click to the fix."""
    report = report or {}
    conn = conn or {}
    sp = report.get("spend", {}) or {}
    items = []  # (severity, html); 2 = fix now, 1 = keep an eye

    if conn.get("last_sync_error"):
        items.append(_fa_item(2, "var(--red)",
                      '<b>Last sync failed</b> — your numbers may be stale until it succeeds.',
                      "/app/outlay/connect", "Check connection →"))

    for a in report.get("anomalies", [])[:3]:
        tid = _e(str(a.get("ticket_id")))
        cls = a.get("task_class")
        href = (f'/app/outlay/scope?type=class&id={quote(str(cls))}' if cls else "/app/outlay")
        items.append(_fa_item(2, "var(--red)",
                      f'Runaway ticket <b>{tid}</b> burned '
                      f'<b>{money(a.get("cost_usd",0))}</b> — <b>{a.get("ratio",0):.1f}×</b> its '
                      f'{_e(str(cls or "work-type"))} median. Worth a look before it repeats.',
                      href, "Investigate →"))

    total = sp.get("total_usd", 0.0)
    cov = sp.get("ticket_coverage", 0.0)
    if total > 0 and 0 < cov < 0.7:
        unmapped = max(0.0, total - sp.get("attributed_to_ticket_usd", 0.0))
        items.append(_fa_item(1, "var(--amber)",
                      f'<b>{money(unmapped)}</b> ({(1-cov)*100:.0f}%) of spend isn\'t '
                      'mapped to a ticket yet — connect PRs or map team identities to recover it.',
                      "/app/outlay/connect#teams", "Lift coverage →"))

    hist = history or []
    if len(hist) >= 2:
        cur, prev = hist[-1].get("total_usd", 0), hist[-2].get("total_usd", 0)
        if prev > 0 and (cur - prev) / prev >= 0.25:
            items.append(_fa_item(1, "var(--amber)",
                          f'AI spend <b>jumped {((cur-prev)/prev)*100:.0f}%</b> vs last '
                          f'sync ({money(prev)} → {money(cur)}). See what moved.',
                          "/app/outlay", "See movers →"))

    pf = report.get("pricing_fidelity") or {}
    if pf.get("fallback_usd", 0) and pf.get("fallback_share", 0) >= 0.005:
        models = ", ".join(pf.get("models", [])[:3]) or "unrecognized model(s)"
        items.append(_fa_item(1, "var(--amber)",
                      f'<b>{money(pf["fallback_usd"])}</b> '
                      f'({pf["fallback_share"]*100:.0f}%) was priced at the nearest tier — '
                      f'<b>{_e(models)}</b> aren\'t in the price book yet.',
                      "/app/outlay", "Details →"))

    for s in (budget_statuses or []):
        if s.get("limit_usd") and s.get("status") == "over":
            scope = (_e(s.get("scope_type") or "") + (f' {_e(s.get("scope_id"))}' if s.get("scope_id") else "")).strip() or "overall"
            items.append(_fa_item(2, "var(--red)",
                          f'Budget <b>{scope}</b> is over — projected '
                          f'<b>{money(s.get("projected_usd",0))}</b> vs {money(s.get("limit_usd",0))}.',
                          f'/app/outlay/budgets#budget-{s.get("id")}', "Adjust limit →"))

    return items


HOME_GROUPINGS = {
    "team": "Team / cost-center", "class": "Work type",
    "project": "Project / epic", "person": "Engineer",
}


def _breakdown_rows(report: dict, group_by: str) -> tuple[str, list[dict]]:
    """(card title, rows) for a Home breakdown dimension. Each row: label, usd, share,
    and a drill href (a scope page where one exists, else the Spend tab)."""
    from . import outlay_app
    if group_by == "class":
        data = [{"label": c["task_class"], "usd": c.get("spent_usd", 0), "share": c.get("share", 0),
                 "href": f'/app/outlay/scope?type=class&id={quote(str(c["task_class"]))}'}
                for c in outlay_app.class_spend(report)]
        return "By work type", data
    if group_by == "project":
        data = [{"label": p["project"], "usd": p.get("spent_usd", 0), "share": p.get("share", 0),
                 "href": "/app/outlay"} for p in outlay_app.project_spend(report) if p.get("project")]
        return "By project / epic", data
    if group_by == "person":
        total = (report.get("spend", {}) or {}).get("total_usd", 0) or 1
        data = [{"label": p["user"], "usd": p.get("spent_usd", 0),
                 "share": p.get("share", p.get("spent_usd", 0) / total), "href": "/app/outlay"}
                for p in (report.get("people") or []) if p.get("user")]
        return "By engineer", data
    data = [{"label": t["team"], "usd": t.get("spent_usd", 0), "share": t.get("share", 0),
             "href": f'/app/outlay/scope?type=team&id={quote(str(t["team"]))}'}
            for t in (report.get("team_spend") or []) if t.get("team")]
    return "By team / cost-center", data


def _home_breakdown_card(report: dict, group_by: str = "team", top_n: int = 5) -> str:
    """The consolidated 'where it landed' card on the business Home — re-sliced by the
    Home lens (team / work type / project / engineer), top-N, with per-row drill-downs."""
    title, data = _breakdown_rows(report, group_by)
    if not data:
        return (f'<div class=ocard><div class=dh>{_e(title)}</div>'
                '<p class=muted style="margin:0;font-size:13px">No data for this breakdown yet.</p></div>')
    dmax = max([d["usd"] for d in data] + [1]) or 1
    shown = data if (top_n or 0) <= 0 else data[:top_n]
    rows = "".join(
        f'<div class=erow><a class=nm href="{d["href"]}">{_e(str(d["label"]))} '
        f'<small>· {d["share"]*100:.0f}%</small> <span class=drill>→</span></a>'
        f'<span class=amt>{money(d["usd"])}</span>'
        f'<div class=ebar><span style="width:{d["usd"]/dmax*100:.0f}%;background:var(--grn)"></span></div></div>'
        for d in shown)
    more = (f'<a class=sub href="/app/outlay">all {len(data)} →</a>' if len(data) > len(shown)
            else '<a class=sub href="/app/outlay">details →</a>')
    return f'<div class=ocard><div class=dh>{_e(title)}{more}</div>{rows}</div>'


def _lens_bar(group_by: str, top_n: int, views: list[dict], active_view_id: int = 0) -> str:
    """The business Home lens + saved-views control. Group-by + Top-N re-slice the
    breakdown card (GET, server-rendered); saved views capture a named lens, one of
    which can be the person's default landing."""
    def opt(v, cur, label):
        return f'<option value="{v}"{" selected" if str(cur) == str(v) else ""}>{_e(label)}</option>'
    grp = "".join(opt(k, group_by, lbl) for k, lbl in HOME_GROUPINGS.items())
    tops = "".join(opt(n, top_n, ("All" if n == 0 else f"Top {n}")) for n in (5, 10, 0))
    lens_form = (
        '<form method=get action="/app" class=lensform>'
        f'<span class=lab>Group by</span><select name=group aria-label="Group spend by" onchange="this.form.submit()">{grp}</select>'
        f'<span class=lab>Show</span><select name=top aria-label="Number of rows to show" onchange="this.form.submit()">{tops}</select>'
        '<noscript><button class="btn sec sm">Apply</button></noscript></form>')
    chips = '<a class="vchip' + (' on' if not active_view_id else '') + '" href="/app">Default</a>'
    for v in views:
        on = " on" if v["id"] == active_view_id else ""
        star = "★ " if v.get("is_default") else ""
        chips += (f'<span class=vchip-wrap><a class="vchip{on}" href="/app?view={v["id"]}">{star}{_e(v["name"])}</a>'
                  f'<form method=post action="/app/views/delete" style="display:inline">'
                  f'<input type=hidden name=id value="{v["id"]}">'
                  f'<button class=vx title="Delete view">×</button></form></span>')
    save = (
        '<form method=post action="/app/views" class=saveview>'
        f'<input type=hidden name=group value="{_e(group_by)}"><input type=hidden name=top value="{int(top_n)}">'
        '<input name=name aria-label="Name this saved view" placeholder="Save this view as…" maxlength=60 required>'
        '<label class=defck><input type=checkbox name=make_default value=1> default</label>'
        '<button class="btn sec sm">Save</button></form>')
    setdef = ""
    if active_view_id:
        setdef = (f'<form method=post action="/app/views/default" style="display:inline">'
                  f'<input type=hidden name=id value="{active_view_id}">'
                  f'<button class="btn sec sm">Make default</button></form>')
    return (f'<div class=lensbar><div class=lensrow>{lens_form}<span class=lsp></span>{setdef}{save}</div>'
            f'<div class=vchips><span class=lab>Views</span>{chips}</div></div>')


def _home_governance_card(program_statuses: list[dict], budget_statuses: list[dict]) -> str:
    """Consolidated governance card for the business Home — a roll-up of program/budget
    status with a drill into the Governance deep view."""
    progs = program_statuses or []
    buds = budget_statuses or []
    n = len(progs) + len(buds)
    if not n:
        return ('<div class=ocard><div class=dh>Governance<a class=sub href="/app/outlay/governance">set up →</a></div>'
                '<p class=muted style="margin:0;font-size:13px">No budgets or programs yet. Cap a body of work '
                'across teams with a <a href="/app/outlay/governance">program budget</a>.</p></div>')
    over = [s for s in progs + buds if s.get("status") == "over"]
    warn = [s for s in progs + buds if s.get("status") == "warn"]
    if over:
        tag = f'<span class="otag over">{len(over)} over</span>'
    elif warn:
        tag = f'<span class="otag warn">{len(warn)} tracking hot</span>'
    else:
        tag = '<span class="otag ok">all on track</span>'
    rows = ""
    for s in (progs[:4] or []):
        st = s.get("status", "ok")
        col = {"ok": "var(--grn-d)", "warn": "var(--amber)", "over": "var(--red)"}.get(st)
        tl = s.get("timeline") or {}
        when = f' · breach {_e(tl["breach_month"])}' if tl.get("breach_month") else ""
        rows += (f'<div class=erow><a class=nm href="/app/outlay/governance">{_e(s.get("name"))} '
                 f'<small style="color:{col}">· {st}{when}</small> <span class=drill>→</span></a>'
                 f'<span class=amt>{money(s.get("spent_usd",0))}<small class=muted> / {money(s.get("limit_usd",0))}</small></span></div>')
    return (f'<div class=ocard><div class=dh style="display:flex;align-items:center;gap:8px">Governance {tag}'
            f'<a class=sub href="/app/outlay/governance" style="margin-left:auto">manage →</a></div>{rows}</div>')


def _home_greeting(account: dict) -> str:
    """A small, friendly 'welcome back, <first name>' over the Overview header — only
    when the person has set a real name (never the email alias, which reads oddly)."""
    name = ((account.get("member_name") if account.get("member_id") else account.get("name")) or "").strip()
    if not name:
        return ""
    first = name.split()[0]
    return (f'<div class="small muted" style="margin:0 0 2px;font-weight:600">'
            f'Welcome back, {_e(first)} \U0001F44B</div>')


def overview_page(account: dict, report: dict | None, statuses: list[dict] | None = None,
                  history: list[dict] | None = None, conn: dict | None = None,
                  has_budget: bool = False, persona: str = "",
                  program_statuses: list[dict] | None = None,
                  lens: dict | None = None, views: list[dict] | None = None,
                  active_view_id: int = 0, layout: dict | None = None,
                  customize: bool = False) -> str:
    """The role-aware home — the first screen after sign-in. A concise glance
    (KPIs, budget status, forecast) with jump-offs into the deeper areas; the
    attribution detail lives on the Spend page."""
    checklist = _onboarding(conn, report, has_budget, persona, demo_mode=bool(account.get("demo_mode")))
    # The trial banner lives on Overview only (the home screen) — the sidebar pill
    # persists trial status on every other page, so it isn't repeated app-wide.
    tb = _account_trial_banner(account)
    if not report:
        # Business does no setup — show the 'data on its way' + invite-engineering
        # state rather than a connect CTA. (This is a functional role difference, not
        # a cosmetic one: finance consumes the data, engineering wires it up.)
        if persona == "business":
            return page("Home", tb + _finance_waiting(account), account, active="/app")
        intro = (
            '<div class=ohead><h1>Your AI spend, on your roadmap.</h1>'
            '<p>Connect your tracker and AI usage — read-only — and Outlay maps every dollar to the work '
            'that drove it, forecasts the quarter, estimates planned work, and holds it to budget. '
            'Prompts never leave your tools.</p></div>')
        sample_btn = ('<form method=post action="/app/outlay/sample" style="margin:0">'
                      '<button class="btn sec">See it with sample data</button></form>'
                      if account.get("_can_demo") else '')
        cta = ('<div class="row" style="margin:0 0 22px">'
               '<a class="btn" href="/app/outlay/connect?tour=connect">Connect your sources →</a>'
               + sample_btn +
               '<a class="btn sec" href="/app/outlay/connect?tour=connect">Show me how</a></div>')
        return page("Home", tb + intro + cta + checklist + _outlay_connect(),
                    account, active="/app")

    greet = _home_greeting(account)
    head = (f'<div class=ohead>{greet}<h1>{_quarter_label()} at a glance</h1>'
            '<p>What needs action, the headline numbers, and where your spend landed — '
            'drill into any card for the detail.</p></div>')

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
    unit = _unit_econ_card(report)
    unit = f'<div style="margin-top:16px">{unit}</div>' if unit else ""

    # One unified Home for every persona, F-pattern: act-first attention panel → KPI
    # scorecard → consolidated trust panel → trend band → the lens-based drill-in
    # cards (where it landed · governance · forecast · reports). The lens tabs let
    # anyone group by team / work type / project / engineer — no persona toggle. Deep
    # detail lives one click away on Spend / Governance / Estimate.
    # "Needs your attention" for everyone — budget/program off-track (finance) AND
    # the operational signals (runaway tickets, coverage leaks, spend spikes, stale
    # sync, pricing gaps). Each panel renders only what it has to flag.
    attention = _attention_combined(report, conn, history, statuses, program_statuses)
    lens = lens or {}
    group_by = lens.get("group_by", "team")
    top_n = int(lens.get("top_n", 5))
    lens_bar = _lens_bar(group_by, top_n, views or [], active_view_id)
    cards = {
        "breakdown": _home_breakdown_card(report, group_by, top_n),
        "governance": _home_governance_card(program_statuses, statuses),
        "forecast": _forecast_card(report),
        "actions": _home_actions_card(),
    }
    modules = _home_modules(cards, layout or {}, customize)
    body = (tb + head + _staleness_banner(report, conn)
            + _sample_strip(report, account) + checklist
            + attention
            + _kpis_row(report, history)
            + _trust_panel(report, conn) + _pricing_warn(report) + fidelity + unit + tm_row
            + lens_bar + modules + _sync_line(report, conn))
    return page("Home", body, account, active="/app")


def _home_actions_card() -> str:
    """Business Home quick-actions card — the board readout and the deep views."""
    return ('<div class=ocard><div class=dh>Reports &amp; deep views</div>'
            '<a class=exrow href="/app/outlay/close-report.html" target=_blank>'
            '<span class=nm>Board readout (print to PDF)</span>'
            '<span class=exd>A one-page AI-spend audit for the board.</span><span class=exarr>→</span></a>'
            '<a class=exrow href="/app/outlay"><span class=nm>Full spend breakdown</span>'
            '<span class=exd>Every dollar by team, work type, and ticket.</span><span class=exarr>→</span></a>'
            '<a class=exrow href="/app/outlay/governance"><span class=nm>Budgets &amp; programs</span>'
            '<span class=exd>Caps, timelines, and enforcement.</span><span class=exarr>→</span></a></div>')


HOME_MODULES = ["breakdown", "governance", "forecast", "actions"]
HOME_MODULE_TITLES = {"breakdown": "Where it landed", "governance": "Governance",
                      "forecast": "Forecast · open work", "actions": "Reports & deep views"}


def _home_module_order(layout: dict) -> list[str]:
    """Saved order, filtered to known modules, with any new modules appended — so the
    layout survives us adding cards later."""
    saved = [k for k in (layout.get("order") or []) if k in HOME_MODULES]
    return saved + [k for k in HOME_MODULES if k not in saved]


def _home_modules(cards: dict, layout: dict, customize: bool) -> str:
    """The customizable module deck on the business Home — render the cards in the
    person's saved order, omitting hidden ones. In customize mode each card gets
    move/hide controls and hidden cards can be re-added, all persisted per person."""
    order = _home_module_order(layout)
    hidden = set(layout.get("hidden") or [])
    visible = [k for k in order if k not in hidden]

    if not customize:
        bar = ('<div style="display:flex;justify-content:flex-end;margin-top:16px">'
               '<a class="btn sec sm" href="/app?customize=1">⚙ Customize</a></div>')
        cells = "".join(f'<div>{cards[k]}</div>' for k in visible if k in cards)
        return bar + f'<div class=ogrid style="margin-top:8px">{cells}</div>'

    # Customize mode: control header per card + hidden tray + toolbar.
    bar = ('<div class=custbar><span><b>Customizing your dashboard</b> — reorder with ↑ ↓, hide cards '
           'you don\'t use. Saved to your login.</span><span class=lsp></span>'
           '<form method=post action="/app/layout" style="margin:0"><input type=hidden name=action value=reset>'
           '<button class="btn sec sm">Reset to default</button></form>'
           '<a class="btn sm" href="/app">Done</a></div>')
    cells = ""
    for i, k in enumerate(visible):
        if k not in cards:
            continue
        up = (f'<form method=post action="/app/layout"><input type=hidden name=action value=move>'
              f'<input type=hidden name=key value="{k}"><input type=hidden name=dir value=up>'
              f'<button class=modbtn title="Move up"{" disabled" if i == 0 else ""}>↑</button></form>')
        down = (f'<form method=post action="/app/layout"><input type=hidden name=action value=move>'
                f'<input type=hidden name=key value="{k}"><input type=hidden name=dir value=down>'
                f'<button class=modbtn title="Move down"{" disabled" if i == len(visible)-1 else ""}>↓</button></form>')
        hide = (f'<form method=post action="/app/layout"><input type=hidden name=action value=hide>'
                f'<input type=hidden name=key value="{k}"><button class=modbtn title="Hide">Hide ✕</button></form>')
        ctrl = (f'<div class=modhdr><span class=modname>{_e(HOME_MODULE_TITLES.get(k, k))}</span>'
                f'<span class=modctrls>{up}{down}{hide}</span></div>')
        cells += f'<div class=modcell>{ctrl}{cards[k]}</div>'
    grid = f'<div class=ogrid style="margin-top:8px">{cells}</div>'
    tray = ""
    if hidden:
        chips = "".join(
            f'<form method=post action="/app/layout" style="display:inline"><input type=hidden name=action value=show>'
            f'<input type=hidden name=key value="{k}"><button class="vchip">+ {_e(HOME_MODULE_TITLES.get(k, k))}</button></form>'
            for k in order if k in hidden)
        tray = (f'<div class=hidetray><span class=lab>Hidden cards</span>{chips}</div>')
    return bar + grid + tray


def _unit_econ_card(report: dict) -> str:
    """Unit economics — cost per ticket / per closed ticket, the rework tax, and the
    priciest work types per unit. Reframes spend as efficiency. Hidden until there's
    enough attributed coverage that the per-unit number means something."""
    from . import outlay_app
    cov = (report or {}).get("spend", {}).get("ticket_coverage", 0.0)
    ue = outlay_app.unit_economics(report)
    if not ue or ue["tickets"] < 3 or cov < 0.3:
        return ""  # too little attributed for a per-ticket number to be honest
    per_closed = (f'<div class=kpi><div class=l>per closed ticket · {ue["closed_tickets"]} closed</div>'
                  f'<div class=v>{money(ue["cost_per_closed_usd"])}</div></div>'
                  if ue.get("cost_per_closed_usd") is not None else "")
    rework = ""
    if ue["rework_share"] > 0.01:
        rework = (f'<div class=kpi><div class=l>spend on reworked tickets · {ue["reworked_tickets"]} reworked</div>'
                  f'<div class=v>{ue["rework_share"]*100:.0f}%</div></div>')
    kpis = (f'<div class=kpi><div class=l>per attributed ticket · {ue["tickets"]} tickets</div>'
            f'<div class=v>{money(ue["cost_per_ticket_usd"])}</div></div>'
            f'{per_closed}{rework}')
    rows = "".join(
        f'<div class=erow><a class=nm href="/app/outlay/scope?type=class&id={quote(str(c["task_class"]))}">'
        f'{_e(c["task_class"])} <small>· {c["tickets"]} tickets</small> <span class=drill>→</span></a>'
        f'<span class=amt>{money(c["per_ticket_usd"])}<small class=muted> /ticket</small></span></div>'
        for c in ue["by_class"])
    by = (f'<div style="margin-top:6px"><div class=muted style="font-size:12px;text-transform:uppercase;'
          f'letter-spacing:.04em;margin-bottom:4px">Priciest work, per ticket</div>{rows}</div>') if rows else ""
    return (f'<div class=ocard><div class=dh>Unit economics'
            f'<span class=sub>cost per unit of work</span></div>'
            f'<div class=kpirow style="display:flex;gap:26px;flex-wrap:wrap;margin:2px 0 10px">{kpis}</div>{by}</div>')


def outlay_page(account: dict, report: dict | None, statuses: list[dict] | None = None,
                history: list[dict] | None = None, conn: dict | None = None,
                has_budget: bool = False, persona: str = "") -> str:
    chooser = ""  # unified view — no persona chooser
    checklist = _onboarding(conn, report, has_budget, persona, demo_mode=bool(account.get("demo_mode")))
    if not report:
        intro = (
            '<div class=ohead><h1>Your AI spend, on your roadmap.</h1>'
            '<p>Connect your tracker and AI usage — read-only — and Outlay maps every dollar to the work '
            'that drove it, forecasts the quarter, estimates planned work, and holds it to budget. '
            'Prompts never leave your tools.</p></div>')
        sample_btn = ('<form method=post action="/app/outlay/sample" style="margin:0">'
                      '<button class="btn sec">See it with sample data</button></form>'
                      if account.get("_can_demo") else '')
        cta = ('<div class="row" style="margin:0 0 22px">'
               '<a class="btn" href="/app/outlay/connect?tour=connect">Connect your sources →</a>'
               + sample_btn +
               '<a class="btn sec" href="/app/outlay/connect?tour=connect">Show me how</a></div>')
        return page("Spend", chooser + intro + cta + checklist + _outlay_connect(),
                    account, active="/app/outlay")

    sp = report.get("spend", {})
    cov = sp.get("ticket_coverage", 0.0)

    # One unified header for every role — switch the breakdown lens (ticket / work
    # type / team / engineer) right on the page instead of switching personas.
    ohead = ('<div class=ohead><h1>Where your AI spend goes</h1>'
             '<p>Every dollar mapped to the work that drove it — by ticket, work type, team, and '
             'engineer. Forecast and budget live on <a href="/app">Overview</a>.</p></div>')

    kpis = _kpis_row(report, history)

    def _erow(name, sub, amount, bar_pct, color="var(--grn)", href=None):
        sub_html = f' <small>· {_e(sub)}</small>' if sub else ""
        nm = (f'<a class=nm href="{href}">{_e(name)}{sub_html} <span class=drill>→</span></a>'
              if href else f'<span class=nm>{_e(name)}{sub_html}</span>')
        return (f'<div class=erow>{nm}<span class=amt>{amount}</span>'
                f'<div class=ebar><span style="width:{max(2,min(100,bar_pct)):.0f}%;background:{color}"></span></div></div>')

    _no = lambda lbl: f'<p class=muted style="font-size:13px">No {lbl} spend yet.</p>'

    # Rows per dimension (built once, shown via the tabbed panel below).
    tickets = report.get("tickets", [])[:8]
    maxc = max((t.get("cost_usd", 0) for t in tickets), default=1) or 1
    ticket_rows = "".join(
        _erow(t.get("ticket_id"), t.get("task_class"), money(t.get("cost_usd", 0)),
              t.get("cost_usd", 0) / maxc * 100, "var(--amber)" if i == 0 else "var(--grn)")
        for i, t in enumerate(tickets)) or _no("ticket-attributed")

    cls = report.get("class_spend") or []
    clsmax = max((c.get("spent_usd", 0) for c in cls), default=1) or 1
    class_rows = "".join(
        _erow(c.get("task_class"), f'{c.get("tickets",0)} tickets · {c.get("share",0)*100:.0f}%',
              money(c.get("spent_usd", 0)), c.get("spent_usd", 0) / clsmax * 100,
              href=f'/app/outlay/scope?type=class&id={quote(str(c.get("task_class") or ""))}')
        for c in cls) or _no("work-type")

    names = store.get_outlay_identity_names(account["id"]) if account and account.get("id") else {}
    people = [p for p in (report.get("people") or []) if p.get("user") != "(unattributed)"][:8]
    def _who(u: str) -> str:
        nm = names.get((u or "").strip().lower())
        return f"{nm} · {u}" if nm else (u or "")
    pmax = max((p.get("spent_usd", 0) for p in people), default=1) or 1
    people_rows = "".join(
        _erow(_who(p.get("user")), f'{p.get("top_model")} · {p.get("share",0)*100:.0f}%',
              money(p.get("spent_usd", 0)), p.get("spent_usd", 0) / pmax * 100)
        for p in people)

    teams = report.get("team_spend") or []
    has_team = any(t.get("team") != "(unassigned)" for t in teams)
    tmax = max((t.get("spent_usd", 0) for t in teams), default=1) or 1
    team_rows = "".join(
        _erow(("Unassigned" if t.get("team") == "(unassigned)" else t.get("team")),
              f'{t.get("share",0)*100:.0f}% of attributed',
              money(t.get("spent_usd", 0)), t.get("spent_usd", 0) / tmax * 100,
              "#cfcabb" if t.get("team") == "(unassigned)" else "var(--grn)",
              href=f'/app/outlay/scope?type=team&id={quote(str(t.get("team") or ""))}')
        for t in teams)

    # One tabbed panel, one set of lenses for everyone: ticket → work type → team →
    # engineer (finance and engineering both switch the tab they care about, instead
    # of switching personas).
    dims = [("ticket", "By ticket", ticket_rows), ("class", "By work type", class_rows)] + \
           ([("team", "By team", team_rows)] if has_team else []) + \
           ([("eng", "By engineer", people_rows)] if people else [])

    spark = _sparkline([h.get("total_usd", 0) for h in (history or [])])
    sub = f'<span class=sub title="Spend over your last {len(history or [])} refreshes">{spark}</span>' if spark else ""
    breakdown = _spend_dim_panel(dims, sub)

    _athr, _amuted = _anomaly_prefs(conn)
    anomaly_card = _anomaly_card(report, _athr, _amuted, controls=True)
    anomaly_row = f'<div style="margin-top:16px">{anomaly_card}</div>' if anomaly_card else ""
    model_card = _model_card(report)
    model_row = f'<div style="margin-top:16px">{model_card}</div>' if model_card else ""

    grid = breakdown + model_row + anomaly_row

    # One unified link bar (the union of what business + engineering each had).
    olinks = ('<div class=olinks>'
              '<a href="/app/outlay/accuracy">How accurate is this? →</a>'
              '<a href="/app/outlay/estimate">Estimate planned work →</a>'
              '<a href="/app/outlay/budgets">Budgets &amp; guardrails →</a>'
              '<a href="/app/outlay/programs">Program budgets →</a>'
              '<a href="/app/outlay/close-report.html" target=_blank>Close report →</a>'
              '<span class=sp></span>'
              '<span class=muted style="font-size:12.5px">Export CSV:</span>'
              '<a href="/app/outlay/export.csv?view=tickets">by ticket</a>'
              '<a href="/app/outlay/export.csv?view=teams" title="Per-team / cost-center allocation for showback / chargeback">by team</a>'
              '<a href="/app/outlay/export.csv?view=classes">by work type</a>'
              '<a href="/app/outlay/export.csv?view=people">by engineer</a>'
              '<a href="/app/outlay/export.focus.csv" '
              'title="FinOps Open Cost &amp; Usage Spec column names — load into any FOCUS-aware BI tool">'
              'FOCUS</a></div>')

    # The coverage diagnostic is a conditional, actionable nudge — shown to everyone,
    # but only when ticket coverage is low (with the cheapest fix). An alert, not
    # always-on clutter.
    cov_diag = _coverage_diag(report)
    cov_diag = f'<div style="margin:16px 0">{cov_diag}</div>' if cov_diag else ""

    # One unified Spend view — no persona toggle. The breakdown panel's lens tabs
    # (ticket / work type / team / engineer) replace switching personas.
    body = (chooser + ohead + _staleness_banner(report, conn)
            + _sample_strip(report, account) + checklist + _budget_strip(statuses)
            + _hero_unit_cost(report) + _trust_panel(report, conn) + kpis + _pricing_warn(report)
            + cov_diag + _sync_line(report, conn) + olinks + grid)
    return page("Spend", body, account, active="/app/outlay")


def scope_page(account: dict, report: dict | None, scope_type: str, scope_id: str) -> str:
    """Drill-down: the tickets behind one team or work-type, biggest first, with the
    runaway outliers in that scope flagged. Reached by clicking a row on Spend."""
    back = '<p style="margin:0 0 14px"><a href="/app/outlay">&larr; Back to Spend</a></p>'
    if not report:
        return page("Detail", back + '<div class=ocard><p class=muted style="margin:0">No data yet.</p></div>',
                    account, active="/app/outlay")
    all_tix = report.get("tickets", [])
    if scope_type == "team":
        label, kind = scope_id, "team / cost-center"
        tix = [t for t in all_tix if (t.get("team_id") or "(unassigned)") == scope_id]
    else:
        scope_type = "class"
        label, kind = scope_id, "work type"
        tix = [t for t in all_tix if t.get("task_class") == scope_id]
    tix = sorted(tix, key=lambda t: t.get("cost_usd", 0), reverse=True)
    total = sum(t.get("cost_usd", 0) for t in tix)
    anom_ids = {a.get("ticket_id"): a.get("ratio", 0) for a in (report.get("anomalies") or [])}

    head = (f'<div class=ohead><h1>{_e(label)} <span class=muted>· {kind}</span></h1>'
            f'<p>{money(total)} across {len(tix)} ticket{"s" if len(tix) != 1 else ""} in this window.</p></div>')
    if not tix:
        body = back + head + '<div class=ocard><p class=muted style="margin:0">No ticket-attributed spend in this scope.</p></div>'
        return page("Detail", body, account, active="/app/outlay")

    maxc = max((t.get("cost_usd", 0) for t in tix), default=1) or 1
    rows = ""
    for t in tix[:50]:
        ratio = anom_ids.get(t.get("ticket_id"))
        flag = (f' <span style="color:var(--amber);font-weight:600;font-size:12px">{ratio:.0f}× runaway</span>'
                if ratio else "")
        sub = t.get("task_class") if scope_type == "team" else (t.get("team_id") or "unassigned")
        col = "var(--amber)" if ratio else "var(--grn)"
        rows += (f'<div class=erow><span class=nm>{_e(t.get("ticket_id"))} '
                 f'<small>· {_e(sub)} · {_e(t.get("status"))}</small>{flag}</span>'
                 f'<span class=amt>{money(t.get("cost_usd", 0))}</span>'
                 f'<div class=ebar><span style="width:{max(2, t.get("cost_usd",0)/maxc*100):.0f}%;'
                 f'background:{col}"></span></div></div>')
    card = f'<div class=ocard><div class=dh>Tickets<span class=sub>biggest first</span></div>{rows}</div>'
    csv_view = "tickets"
    export = (f'<div class=olinks style="margin-top:14px">'
              f'<a href="/app/outlay/export.csv?view=tickets">Export all tickets (CSV)</a></div>')
    return page("Detail", back + head + card + export, account, active="/app/outlay")


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
    slack_url = _e(conn.get("slack_webhook") or "")
    slack_state = ('<b style="color:var(--grn-d)">✓ Slack connected.</b>' if conn.get("slack_webhook")
                   else "")
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

    form = f"""<div class=ohead><h1>Connect your sources <span class=muted>· read-only</span>
        <button type=button class="btn sec sm" style="margin-left:10px;vertical-align:middle"
          onclick="window.startConnectTour&amp;&amp;window.startConnectTour()">Show me how</button></h1>
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
        <button class="btn" id=ob-sync onclick="outlaySync(this)">Sync now &amp; run the audit</button>
        <a class="btn sec" href="/app/outlay" style="margin-left:8px">View Spend →</a>
        <script>function outlaySync(btn){{btn.classList.add('loading');btn.disabled=true;
          fetch('/app/outlay/sync',{{method:'POST'}}).then(function(r){{return r.json();}}).then(function(d){{
            if(d.ok){{location.href='/app/outlay';}}else{{btn.classList.remove('loading');btn.disabled=false;
              alert(d.error||'Sync failed.');}}}})
          .catch(function(){{btn.classList.remove('loading');btn.disabled=false;alert('Network error.');}});}}
        </script>
      </div>
      <p class=cmut style="margin:18px 2px 6px;font-size:12.5px;text-transform:uppercase;letter-spacing:.06em">Optional — refine after your first sync</p>
      <details class=ocard id=teams>
        <summary class=dh style="cursor:pointer;list-style:none">Map identities to teams <span class=sub>for cost-center allocation</span></summary>
        <p class=muted style="margin:8px 0 10px;font-size:13.5px">Map an
          <b>identity</b> — a person's email, a whole <code>@domain</code>, or a <b>service-account /
          CI key id</b> — to a team, one per line. Handy for <b>bots/CI keys</b> (agent spend often runs
          under a service account; unmapped identities land in "Unassigned"). Examples —
          <code>alice@acme.com, Platform</code>, <code>@acme.com, Internal</code>,
          <code>ci-deploy-bot, Platform</code>.</p>
        <form method=post action="/app/outlay/identity">
          <textarea name=identity_map aria-label="Identity map (email or handle, team per line)" rows=5 placeholder="alice@acme.com, Platform
@acme.com, Internal
ci-deploy-bot, Platform">{idmap}</textarea>
          <button class="btn sec" style="margin-top:12px">Save team map</button>
        </form>
      </details>
      <details class=ocard style="margin-top:12px" id=alerts>
        <summary class=dh style="cursor:pointer;list-style:none">Slack alerts <span class=sub>where eng &amp; business live</span></summary>
        <p class=muted style="margin:8px 0 10px;font-size:13.5px">Get budget and runaway-ticket alerts in
          Slack (or Teams). Paste an <a href="https://api.slack.com/messaging/webhooks" target=_blank>incoming
          webhook URL</a> — we post a one-line alert when a budget trips or a ticket goes runaway.
          {slack_state}</p>
        <form method=post action="/app/outlay/slack" style="display:flex;gap:10px;flex-wrap:wrap;align-items:end">
          <label class=fld style="flex:1;min-width:280px"><span>Incoming webhook URL</span>
            <input name=slack_webhook type=url placeholder="https://hooks.slack.com/services/…" value="{slack_url}"></label>
          <button class="btn sec">Save</button>
        </form>
      </details>
      <script>(function(){{var h=location.hash;if(h){{var el=document.querySelector(h);
        if(el&&el.tagName==='DETAILS'){{el.open=true;el.scrollIntoView();}}}}}})();</script>"""
    return page("Connect", form + _CONNECT_TOUR_JS, account, active="/app/outlay/connect")


def _scenario_card(report: dict, overall_budget_usd: float = 0.0, additive: bool = True) -> str:
    """'If we commit this backlog…' — the planner's question. When `additive` (a pasted
    what-if), combines the open-work forecast with the pasted backlog estimate. When
    not additive (we're already showing the *connected* open backlog), the estimate IS
    the open work, so the projection is the backlog total alone — no double-count.
    Only renders once a backlog has been estimated."""
    est = (report or {}).get("estimate") or {}
    if not est:
        return ""
    fc = (report or {}).get("forecast") or {}
    f_exp = fc.get("expected_usd", 0.0)
    e_exp, e_lo, e_hi = est.get("expected_usd", 0.0), est.get("low_usd", 0.0), est.get("high_usd", 0.0)
    if additive:
        total, lo, hi = f_exp + e_exp, fc.get("low_usd", 0.0) + e_lo, fc.get("high_usd", 0.0) + e_hi
        lines = (f'<div class=dual style="margin-top:4px">'
                 f'<div class=r><span>Open work, forecast</span><b class=num>{money(f_exp)}</b></div>'
                 f'<div class=r><span>+ this backlog, if committed</span><b class=num>{money(e_exp)}</b></div>'
                 f'<div class=r style="border-top:1px solid var(--line);padding-top:7px;margin-top:3px">'
                 f'<span><b>= Projected total</b></span><b class=num>{money(total)}</b></div></div>')
    else:
        total, lo, hi = e_exp, e_lo, e_hi
        lines = (f'<div class=dual style="margin-top:4px">'
                 f'<div class=r><span>Open backlog, forecast</span><b class=num>{money(e_exp)}</b></div></div>')

    if overall_budget_usd and overall_budget_usd > 0:
        delta = total - overall_budget_usd
        over = delta > 0
        tone = "over" if over else "ok"
        col = "var(--red)" if over else "var(--grn-d)"
        verdict = (f'<b style="color:{col}">{money(abs(delta))} {"over" if over else "under"}</b> '
                   f'your {money(overall_budget_usd)} budget')
        bmax = max(total, overall_budget_usd) or 1
        bars = (f'<div class=dual style="margin-top:12px">'
                f'<div class=r><span>Quarter budget</span><span class=num>{money(overall_budget_usd)}</span></div>'
                f'<div class=track><span style="width:{overall_budget_usd/bmax*100:.0f}%;background:#9aa3b3"></span></div>'
                f'<div class=r><span>Projected if you commit this</span><span class=num>{money(total)}</span></div>'
                f'<div class=track><span style="width:{total/bmax*100:.0f}%;background:{col}"></span></div></div>')
        lead = "Committing this backlog lands you" if additive else "Your open backlog lands you"
        foot = f'<p class=muted style="font-size:12.5px;margin:12px 0 0">{lead} {verdict} — likely {money(lo)}–{money(hi)}.</p>'
        tag = f'<span class="otag {tone}">{"over" if over else "on track"}</span>'
    else:
        bars = ""
        foot = (f'<p class=muted style="font-size:12.5px;margin:12px 0 0">Likely {money(lo)}–{money(hi)}. '
                f'<a href="/app/outlay/budgets">Set a quarter budget</a> to see this against your target.</p>')
        tag = '<span class="otag ex">scenario</span>'
    heading = "If you commit this backlog" if additive else "Open backlog vs quarter budget"
    return (f'<div class=ocard style="margin-top:16px"><div class=dh>{heading}{tag}</div>'
            f'<div class=bignum><span class=v>{money(total)}</span>'
            f'<span class=of>projected quarter total</span></div>{lines}{bars}{foot}</div>')


def estimate_backlog_page(account: dict, report: dict | None, overall_budget_usd: float = 0.0) -> str:
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

    est = report.get("estimate")
    from_backlog = bool((est or {}).get("from_backlog"))

    # The paste box is the *secondary* path — a what-if on a hypothetical/planned
    # backlog. The default view already prices the connected open backlog, so this
    # is collapsed unless the user wants to model something they haven't filed yet.
    paste_title = "Price a different backlog" if from_backlog else "Paste a planned backlog"
    form = f"""<details class=ocard{"" if from_backlog else " open"} style="margin-top:16px"><summary class=dh style="cursor:pointer;list-style:none">{paste_title}<span class=muted style="font-weight:400;font-size:12px"> · optional what-if</span></summary>
      <p class=muted style="margin:8px 0 10px;font-size:13.5px">Model work you haven't filed yet. A JSON list of items — each with a <b>title</b>, and ideally
        <b>requirements</b>, <b>design_docs</b>, and/or story <b>points</b>.</p>
      <textarea id=ol_plan aria-label="Planned backlog as JSON" rows=6 placeholder='{{"items":[{{"id":"PROJ-1","title":"Add SSO","requirements":"SAML + SCIM, multi-tenant, audit log","points":8}}]}}'></textarea>
      <button class="btn" style="margin-top:12px" onclick="estRun(this)">Estimate →</button>
      <script>function estRun(btn){{btn.classList.add('loading');btn.disabled=true;
        fetch('/app/outlay/estimate/run',{{method:'POST',headers:{{'content-type':'application/json'}},
          body:JSON.stringify({{planned:document.getElementById('ol_plan').value}})}})
        .then(function(r){{return r.json();}}).then(function(d){{if(d.ok){{location.reload();}}else{{
          btn.classList.remove('loading');btn.disabled=false;alert(d.error||'Could not estimate.');}}}})
        .catch(function(){{btn.classList.remove('loading');btn.disabled=false;alert('Network error.');}});}}
      </script></details>"""

    result = ""
    if est:
        items = sorted(est.get("items", []), key=lambda e: e.get("expected_usd", 0) or 0, reverse=True)
        emax = max((e.get("expected_usd", 0) for e in items), default=1) or 1
        CAP = 15
        rows = ""
        for e in items[:CAP]:
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
        more = (f'<p class=muted style="font-size:12px;margin-top:8px">+ {len(items)-CAP} more items '
                f'in the backlog (totaled above).</p>') if len(items) > CAP else ""
        tighten = ('<p class=muted style="font-size:12.5px;margin-top:10px">To tighten the estimate, add: '
                   + _e("; ".join(est.get("tighten", []))) + '.</p>') if est.get("tighten") else ""
        if from_backlog:
            title = "Your open backlog, priced"
            blurb = (f'<p class=muted style="margin:-4px 0 10px;font-size:13px">The {est.get("items_costed",0)+est.get("items_unknown",0)} '
                     f'open tickets from your connected tracker, each priced against your learned cost model — '
                     f'biggest first. No paste required.</p>')
        else:
            title = "Backlog estimate"
            blurb = ""
        result = (f'<div class=ocard style="margin-top:16px"><div class=dh>{title}</div>{blurb}'
                  f'<div class=bignum><span class=v>{money(est.get("expected_usd", 0))}</span>'
                  f'<span class=of>likely {money(est.get("low_usd", 0))}–{money(est.get("high_usd", 0))}</span></div>'
                  f'<div class=muted style="font-size:12.5px;margin:2px 0 12px">{est.get("items_costed", 0)} '
                  f'estimated, {est.get("items_unknown", 0)} need scope.</div>{rows}{more}{tighten}</div>')
    # The additive "open work + this backlog" scenario only makes sense for a *pasted*
    # what-if. When we're already showing the connected open backlog, it IS the open
    # work — adding the forecast on top would double-count — so show a budget check
    # on the backlog total instead.
    scenario = _scenario_card(report, overall_budget_usd, additive=not from_backlog)
    # Lead with the priced backlog; the what-if paste box sits below it.
    return page("Estimate", head + result + form + scenario, account, active="/app/outlay/estimate")


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


def _budgets_section(account: dict, report: dict | None, statuses: list[dict],
                     projects: list[dict] | None = None) -> str:
    """The budgets management UI (status list + project pick-list + add form), without
    the page chrome — composed by both the standalone Budgets page and Governance."""
    tones = {"ok": ("var(--grn)", "var(--grn-d)"), "warn": ("var(--amber)", "var(--amber)"),
             "over": ("var(--red)", "var(--red)")}
    note = "" if report else ('<div class=ocard style="margin-bottom:16px"><p class=muted style="margin:0">'
                              'Connect data on the <a href="/app/outlay">Spend</a> tab to see live status.</p></div>')
    rows = ""
    for s in statuses:
        bar, txt = tones.get(s["status"], tones["ok"])
        name = _e(s["scope_type"]) + (f': {_e(s["scope_id"])}' if s.get("scope_id") else "")
        w = min(max(s.get("pct_used", 0), 0), 1) * 100
        rows += (f'<div class=bcard id="budget-{s["id"]}">'
                 f'<div style="display:flex;justify-content:space-between;align-items:center;gap:10px">'
                 f'<b style="font-size:14px">{name}</b>'
                 f'<span class="otag {s["status"]}">{_e(s["status"])}</span></div>'
                 f'<div class=dual style="margin-top:10px"><div class=track>'
                 f'<span style="width:{w:.0f}%;background:{bar}"></span></div></div>'
                 f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">'
                 f'<span class=muted style="font-size:12.5px">{money(s.get("spent_usd",0))} of {money(s["limit_usd"])} · '
                 f'projected <b style="color:{txt}">{money(s.get("projected_usd",0))}</b> / {int(s.get("period_days") or 30)}d</span>'
                 f'<form method=post action="/app/outlay/budgets/delete" style="margin:0">'
                 f'<input type=hidden name=id value="{s["id"]}">'
                 f'<button class="btn sec sm">Remove</button></form></div>'
                 # Address an over/at-risk budget in place: raise (or lower) the limit.
                 f'<form method=post action="/app/outlay/budgets/update" '
                 f'style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px;'
                 f'border-top:1px solid var(--line);padding-top:10px">'
                 f'<input type=hidden name=id value="{s["id"]}">'
                 f'<span class=muted style="font-size:12px">Adjust limit</span>'
                 f'<input name=limit_usd type=number step=any placeholder="{int(s.get("limit_usd") or 0)}" '
                 f'style="width:120px;padding:6px 9px;border:1px solid var(--line);border-radius:8px">'
                 f'<input name=period_days type=number placeholder="{int(s.get("period_days") or 30)}" '
                 f'title="period (days)" style="width:90px;padding:6px 9px;border:1px solid var(--line);border-radius:8px">'
                 f'<button class="btn sec sm">Save</button></form></div>')
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
    return note + rows + pref + add


def budgets_page(account: dict, report: dict | None, statuses: list[dict],
                 projects: list[dict] | None = None,
                 program_statuses: list[dict] | None = None) -> str:
    """The engineering budgets + project-burn page: budget a scope, and watch each
    project/program burn down its compute over its timeline (start/end + month-by-month
    projection) so you can optimize before it breaches."""
    head = ('<div class=ohead><h1>Budgets &amp; project burn</h1>'
            '<p>Budget a scope and watch it project against your pace. <b>Projects</b> cap a body of '
            'work across teams with a start/end timeline and a month-by-month burn — so you can route '
            'down or tune <b>before</b> a project blows its compute budget.</p></div>')
    burn = ""
    if program_statuses:
        burn = (f'<h2 style="font-size:16px;margin:18px 0 6px">Project burn</h2>'
                f'{_programs_section(account, report, program_statuses)}'
                f'<h2 style="font-size:16px;margin:24px 0 6px">Scope budgets</h2>')
    return page("Budgets", head + burn + _budgets_section(account, report, statuses, projects),
                account, active="/app/outlay/budgets")


def _program_timeline_html(s: dict) -> str:
    """Per-program calendar timeline + month-by-month projection — so business sees
    *when* a program is set to breach, with start/end dates and a pro-rated cap line."""
    tl = s.get("timeline") or {}
    if not tl:
        return ""
    limit = s.get("limit_usd", 0) or 0
    frac = min(max(tl.get("frac_elapsed", 0), 0), 1) * 100
    breach = tl.get("breach_month")
    breach_html = (f'<span style="color:var(--red);font-weight:600">set to breach {_e(breach)}</span>'
                   if breach else '<span style="color:var(--grn-d)">on track to stay in budget</span>')
    months = tl.get("months") or []
    mmax = max([m.get("cum_projected_usd", 0) for m in months] + [limit, 1]) or 1
    mrows = ""
    for m in months:
        cum = m.get("cum_projected_usd", 0)
        cap = m.get("cap_to_date_usd", 0)
        col = "var(--red)" if m.get("over") else ("var(--grn)" if m.get("past") else "var(--amber)")
        cappct = min(cap / mmax * 100, 100)
        mrows += (f'<div class=mbar><span class=ml>{_e(m.get("label"))}</span>'
                  f'<span class=mt><span style="width:{min(cum/mmax*100,100):.0f}%;background:{col}"></span>'
                  f'<span style="left:{cappct:.0f}%;width:2px;background:var(--ink);opacity:.5"></span></span>'
                  f'<span class=mv>{money(cum)}</span></div>')
    return (f'<div style="margin-top:12px;border-top:1px solid var(--line);padding-top:10px">'
            f'<div style="display:flex;justify-content:space-between;font-size:12px;color:var(--muted)">'
            f'<span>{_e(tl.get("start",""))}</span>'
            f'<span>{tl.get("days_left",0)} days left · {breach_html}</span>'
            f'<span>{_e(tl.get("end",""))}</span></div>'
            f'<div class=ptl-track><span class=ptl-fill style="width:{frac:.0f}%"></span>'
            f'<span class=ptl-now style="left:{frac:.0f}%"></span></div>'
            f'<div class=muted style="font-size:11.5px;margin:6px 0 2px;text-transform:uppercase;'
            f'letter-spacing:.05em">Month-by-month · projected cumulative vs pro-rated cap</div>'
            f'{mrows}</div>')


def _program_pacing_html(s: dict) -> str:
    """Real-time pacing strip: actual cumulative spend vs the budget's expected pace to
    date, the projected end spend, and — if trending over — the projected breach DATE.
    Honest by construction: shows 'gathering baseline' until there's enough signal."""
    pc = s.get("pacing") or {}
    if not pc:
        return ""
    if not pc.get("ready"):
        return ('<div style="margin-top:10px;border-top:1px solid var(--line);padding-top:10px;'
                'font-size:12px;color:var(--muted)">Gathering baseline — real-time pacing flags '
                'appear once more of the program has elapsed.</div>')
    labels = {"ahead": ("ahead of plan", "var(--grn-d)"), "on_track": ("on track", "var(--grn-d)"),
              "over_pace": ("over plan pace", "var(--amber)"),
              "projected_breach": ("projected to exceed budget", "var(--red)"),
              "over_budget": ("over budget", "var(--red)")}
    lbl, col = labels.get(pc.get("pace"), ("on track", "var(--grn-d)"))
    pv, ac = pc.get("planned_to_date_usd", 0), pc.get("actual_to_date_usd", 0)
    vpct = pc.get("variance_pct", 0)
    arrow = "&#9650;" if vpct > 0 else ("&#9660;" if vpct < 0 else "&#8226;")
    var_html = f'<span class=muted>{arrow} {abs(vpct) * 100:.0f}% vs plan</span>' if pv else ""
    breach = pc.get("projected_breach_date")
    breach_html = (f' · <span style="color:var(--red);font-weight:600">exceeds budget '
                   f'{"now" if breach == "now" else "on " + _e(breach)}</span>') if breach else ""
    mx = max(ac, pv, 1)
    bar = ('display:inline-block;flex:1;height:7px;background:var(--paper2);border-radius:4px;'
           'position:relative;overflow:hidden')

    def row(name, val, pct, fill):
        return (f'<div style="display:flex;align-items:center;gap:8px;margin-top:3px">'
                f'<span class=muted style="width:48px;font-size:11.5px">{name}</span>'
                f'<span style="{bar}"><span style="display:block;height:100%;width:{pct:.0f}%;'
                f'background:{fill};border-radius:4px"></span></span>'
                f'<span style="font-size:11.5px;width:64px;text-align:right">{money(val)}</span></div>')
    return (f'<div style="margin-top:10px;border-top:1px solid var(--line);padding-top:10px">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;font-size:12.5px">'
            f'<span><b style="color:{col}">{lbl}</b> {var_html}</span>'
            f'<span class=muted>proj. end <b style="color:{col}">{money(pc.get("projected_end_usd", 0))}</b></span></div>'
            f'{row("actual", ac, ac / mx * 100, col)}'
            f'{row("planned", pv, pv / mx * 100, "var(--ink)")}'
            f'<div class=muted style="font-size:11.5px;margin-top:5px">to date{breach_html}</div></div>')


def _program_progress_html(s: dict) -> str:
    """Headline on-track rating from forecast-vs-actual on COMPLETED work (earned value).
    The most accurate read: are finished components costing what we forecast, and at this
    rate will the program land within budget?"""
    pr = s.get("progress")
    if not pr:
        return ""
    if not pr.get("ready"):
        return ('<div style="margin-top:10px;border-top:1px solid var(--line);padding-top:10px;'
                'font-size:12px;color:var(--muted)">On-track rating — gathering baseline '
                '(rates once a few components have completed).</div>')
    col = {"ok": "var(--grn-d)", "warn": "var(--amber)", "over": "var(--red)"}.get(pr["status"], "var(--grn-d)")
    icon = "&#10003;" if pr["status"] == "ok" else "&#9888;"
    cv = pr.get("cost_variance_pct", 0) * 100
    var_word = (f'completed work is <b>{abs(cv):.0f}% {"over" if cv > 0 else "under"} forecast</b>'
                if abs(cv) >= 1 else 'completed work is <b>on forecast</b>')
    over = pr.get("over_budget_by_usd", 0)
    proj_html = (f'projected <b style="color:{col}">{money(pr.get("projected_total_usd", 0))}</b>'
                 + (f' vs {money(s.get("limit_usd", 0))} budget (&#9650;{money(over)} over)'
                    if over > 0 else ' &mdash; within budget'))
    return (
        '<div style="margin-top:10px;border-top:1px solid var(--line);padding-top:10px">'
        '<div style="display:flex;justify-content:space-between;align-items:center">'
        f'<span style="font-weight:700;color:{col};font-size:13.5px">{icon} '
        f'{_e(pr.get("rating", "").title())}</span>'
        f'<span class=muted style="font-size:11.5px">{pr.get("components_done")}/'
        f'{pr.get("components_total")} components done</span></div>'
        f'<div style="font-size:12.5px;margin-top:4px">{pr.get("progress_pct", 0) * 100:.0f}% of '
        f'forecasted work complete &middot; {var_word}</div>'
        f'<div class=muted style="font-size:12px;margin-top:2px">{proj_html}</div></div>')


def _programs_section(account: dict, report: dict | None, statuses: list[dict]) -> str:
    """The programs management UI (status cards with timelines + define form), without
    the page chrome — composed by both the standalone Programs page and Governance."""
    tones = {"ok": ("var(--grn)", "var(--grn-d)"), "warn": ("var(--amber)", "var(--amber)"),
             "over": ("var(--red)", "var(--red)")}
    note = "" if report else ('<div class=ocard style="margin-bottom:16px"><p class=muted style="margin:0">'
                              'Connect data on the <a href="/app/outlay">Spend</a> tab to see live status.</p></div>')
    rows = ""
    for s in statuses:
        bar, txt = tones.get(s["status"], tones["ok"])
        w = min(max(s.get("pct_used", 0), 0), 1) * 100
        mem = ", ".join(f'{_e(m.get("scope_type"))}{(":" + _e(m.get("scope_id"))) if m.get("scope_id") else ""}'
                        for m in (s.get("members") or [])) or "—"
        if s.get("enforce_mode") == "hard":
            act = s.get("action") or "block"
            tip = f'gateway will {act}' + (f' → {_e(s.get("floor_model"))}' if act == "downgrade" and s.get("floor_model") else '')
            enf = f'<span class="otag over" title="{tip}">hard cap · {_e(act)}</span>'
        else:
            enf = '<span class="otag ex" title="detect &amp; notify; your automation enforces">alert only</span>'
        bit = ""
        spark_row = ""
        if s.get("enforce_mode") == "hard" and (s.get("enforced_count") or 0) > 0:
            n = int(s["enforced_count"])
            when = f' · last {_fmt_date(s["last_enforced_at"])}' if s.get("last_enforced_at") else ""
            bit = (f'<span style="color:var(--red);font-weight:600"> · enforced {n:,} '
                   f'time{"s" if n != 1 else ""}{when}</span>')
            hist = store.program_enforcement_history(account["id"], s["id"], days=14)
            sv = _sparkline([h["count"] for h in hist], w=140, h=24, color="var(--red)")
            if sv:
                tot = sum(h["count"] for h in hist)
                spark_row = (f'<div style="display:flex;align-items:center;gap:10px;margin-top:8px">{sv}'
                             f'<span class=muted style="font-size:11.5px">enforcement · last 14 days '
                             f'({tot:,} action{"s" if tot != 1 else ""})</span></div>')
        rows += (f'<div class=bcard id="prog-{s.get("id")}">'
                 f'<div style="display:flex;justify-content:space-between;align-items:center;gap:10px">'
                 f'<b style="font-size:14.5px">{_e(s.get("name"))}</b>'
                 f'<span style="display:flex;gap:6px;align-items:center">{enf}'
                 f'<span class="otag {s["status"]}">{_e(s["status"])}</span></span></div>'
                 f'<div class=muted style="font-size:12px;margin-top:3px">members: {mem}{bit}</div>'
                 f'<div class=dual style="margin-top:10px"><div class=track>'
                 f'<span style="width:{w:.0f}%;background:{bar}"></span></div></div>'
                 f'<div style="display:flex;justify-content:space-between;align-items:center;margin-top:8px">'
                 f'<span class=muted style="font-size:12.5px">{money(s.get("spent_usd",0))} of {money(s["limit_usd"])} · '
                 f'projected <b style="color:{txt}">{money(s.get("projected_usd",0))}</b> / {int(s.get("period_days") or 90)}d</span>'
                 f'<form method=post action="/app/outlay/programs/delete" style="margin:0">'
                 f'<input type=hidden name=id value="{s["id"]}">'
                 f'<button class="btn sec sm">Remove</button></form></div>'
                 f'{_program_progress_html(s)}'
                 f'{_program_pacing_html(s)}'
                 f'{spark_row}'
                 f'{_program_timeline_html(s)}'
                 # Reallocate inline: change the cap, or flip alert <-> hard, in place.
                 f'<form method=post action="/app/outlay/programs/update" '
                 f'style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;margin-top:10px;'
                 f'border-top:1px solid var(--line);padding-top:10px">'
                 f'<input type=hidden name=id value="{s["id"]}">'
                 f'<span class=muted style="font-size:12px">Reallocate budget</span>'
                 f'<input name=limit_usd type=number step=any placeholder="{int(s.get("limit_usd") or 0)}" '
                 f'style="width:110px;padding:6px 9px;border:1px solid var(--line);border-radius:8px">'
                 f'<select name=enforce_mode style="padding:6px 9px;border:1px solid var(--line);border-radius:8px">'
                 f'<option value="">enforcement…</option>'
                 f'<option value="alert"{" selected" if s.get("enforce_mode")!="hard" else ""}>alert only</option>'
                 f'<option value="hard"{" selected" if s.get("enforce_mode")=="hard" else ""}>hard cap</option></select>'
                 f'<button class="btn sec sm">Save</button></form></div>')
    rows = (f'<div class=ocard><div class=dh>Your programs</div>{rows}</div>' if statuses
            else '<div class=ocard><p class=muted style="margin:0">No programs yet — define one below.</p></div>')
    add = """<div class=ocard style="margin-top:16px"><div class=dh>Define a program</div>
      <form method=post action="/app/outlay/programs">
        <div style="display:grid;grid-template-columns:2fr 1fr;gap:12px;align-items:end">
          <label class=fld><span>Program name</span><input name=name placeholder="Platform" required></label>
          <label class=fld><span>Budget (USD)</span><input name=limit_usd type=number step=any placeholder="50000" required></label>
        </div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px;align-items:end;margin-top:12px">
          <label class=fld><span>Start date</span><input name=start_date type=date></label>
          <label class=fld><span>End date</span><input name=end_date type=date></label>
        </div>
        <p class=muted style="font-size:12px;margin:6px 0 0">Leave dates blank for a rolling 90-day window. Dates set the program timeline and month-by-month projection.</p>
        <label class=fld style="margin-top:12px"><span>Members — one per line: <code>team platform</code>, <code>project PLAT</code>, <code>class feature</code>, or <code>overall</code></span>
          <textarea name=members rows=3 placeholder="team platform&#10;team infra&#10;project PLAT" required></textarea></label>
        <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;align-items:end;margin-top:12px">
          <label class=fld><span>Enforcement</span><select name=enforce_mode>
            <option value=alert>Alert only (detect + notify)</option>
            <option value=hard>Hard cap (gateway enforces)</option></select></label>
          <label class=fld><span>When over (hard cap)</span><select name=action>
            <option value=block>Block new calls</option>
            <option value=downgrade>Route down to a cheaper model</option></select></label>
          <label class=fld><span>Floor model (for route-down)</span><select name=floor_model>
            <optgroup label="Claude (Anthropic)">
            <option value="claude-haiku-4-5">Claude Haiku 4.5 (cheapest)</option>
            <option value="claude-sonnet-4-6">Claude Sonnet 4.6</option>
            <option value="claude-opus-4-8">Claude Opus 4.8</option></optgroup>
            <optgroup label="OpenAI / Azure OpenAI">
            <option value="gpt-4o-mini">GPT-4o mini (cheapest)</option>
            <option value="o3-mini">o3-mini</option>
            <option value="gpt-4.1">GPT-4.1</option>
            <option value="gpt-4o">GPT-4o</option>
            <option value="gpt-4-turbo">GPT-4 Turbo</option>
            <option value="o1">o1</option></optgroup></select></label>
        </div>
        <button class="btn" style="margin-top:14px">Add program</button>
      </form>
      <p class=muted style="font-size:12.5px;margin:12px 0 0"><b>Hard cap</b> requires the opt-in
        <a href="/app/outlay/connect">Outlay gateway</a> in front of your calls — it consults Outlay and
        blocks or routes down once a program is over. <b>Alert only</b> works read-only: we fire a
        <code>program.over</code> webhook so your own automation enforces.</p></div>"""
    return note + rows + add


def programs_page(account: dict, report: dict | None, statuses: list[dict]) -> str:
    """Program budgets — a named budget across several teams/projects/work types, with
    optional hard-cap enforcement handed to the opt-in gateway."""
    head = ('<div class=ohead><h1>Program budgets</h1>'
            '<p>Budget a <b>program</b> — a body of work spanning several teams, projects, or work types — '
            'as one number. Alert on it, or hand a <b>hard cap</b> to the gateway to enforce.</p></div>')
    return page("Programs", head + _programs_section(account, report, statuses),
                account, active="/app/outlay/programs")


def _variance_section(program_statuses: list[dict]) -> str:
    """Finance's quarterly plan-vs-actual roll-up across programs (one table + totals)."""
    from . import outlay_app
    rep = outlay_app.variance_report(program_statuses or [])
    if not rep["rows"]:
        return ""
    tone = {"on track": "var(--grn-d)", "watch": "var(--amber)", "off track": "var(--red)",
            "gathering baseline": "var(--muted)"}
    rws = ""
    for r in rep["rows"]:
        planned = money(r["planned_to_date_usd"]) if r["planned_to_date_usd"] is not None else "—"
        if r["variance_usd"] is None:
            var = "—"
        else:
            vcol = "var(--red)" if r["variance_usd"] > 0 else "var(--grn-d)"
            pct = (f' ({"+" if r["variance_pct"] > 0 else ""}{r["variance_pct"] * 100:.0f}%)'
                   if r["variance_pct"] is not None else "")
            var = (f'<span style="color:{vcol}">{"+" if r["variance_usd"] > 0 else ""}'
                   f'{money(r["variance_usd"])}{pct}</span>')
        over = f' <span class=muted style="font-size:12px">({money(r["over_budget_usd"])} over)</span>' \
            if r["over_budget_usd"] > 0 else ""
        rws += (f'<tr><td><b>{_e(r["name"])}</b></td><td>{money(r["budget_usd"])}</td>'
                f'<td>{money(r["actual_to_date_usd"])}</td><td>{planned}</td><td>{var}</td>'
                f'<td style="color:{tone.get(r["rating"], "var(--muted)")};font-weight:600">'
                f'{_e(r["rating"].title())}</td>'
                f'<td>{money(r["projected_total_usd"])}{over}</td></tr>')
    t = rep["totals"]
    chips = " · ".join(f"{n} {k}" for k, n in rep["counts"].items() if n)
    total = (f'<tr style="border-top:2px solid var(--ink)"><td><b>Total ({rep["n"]})</b></td>'
             f'<td><b>{money(t["budget_usd"])}</b></td><td><b>{money(t["actual_to_date_usd"])}</b></td>'
             f'<td><b>{money(t["planned_to_date_usd"])}</b></td><td><b>{money(t["variance_usd"])}</b></td>'
             f'<td></td><td><b>{money(t["projected_total_usd"])}</b></td></tr>')
    return (
        f'<div class=ocard style="margin-top:16px"><div class=dh>Quarterly variance — {_e(rep["quarter"])}'
        f'<a class=sub href="/app/outlay/variance.csv">Export CSV →</a></div>'
        f'<p class=muted style="font-size:12.5px;margin:2px 0 10px">Plan vs. actual across programs this '
        f'quarter{(" · " + _e(chips)) if chips else ""}.</p>'
        '<table><thead><tr><th>Program</th><th>Budget</th><th>Actual</th><th>Planned</th>'
        '<th>Variance</th><th>Rating</th><th>Projected</th></tr></thead>'
        f'<tbody>{rws}{total}</tbody></table></div>')


def _worktype_enforce_section(teams: list | None, enforce: dict | None) -> str:
    """Per-team opt-in enforcement controls — customers pick what each team blocks
    (non-work and/or unknown). In-path enforcement runs in the customer's gateway."""
    teams = [t for t in (teams or []) if t]
    if not teams:
        return ""
    enforce = enforce or {}
    rows = ""
    for team in teams:
        e = enforce.get(team, {})
        bnw, bun = bool(e.get("block_non_work")), bool(e.get("block_unknown"))
        def toggle(field, on, other_field, other_on, label):
            # posting flips `field`; carries the other field's current state
            new = "0" if on else "1"
            style = ("background:var(--red-l);border-color:#f0cfca;color:var(--red)" if on
                     else "background:var(--bg);color:var(--mut)")
            carry = f'<input type=hidden name="{other_field}" value="{"1" if other_on else "0"}">'
            return (f'<form method=post action="/app/outlay/worktype/enforce" style="display:inline;margin:0">'
                    f'<input type=hidden name=team value="{_e(team)}">'
                    f'<input type=hidden name="{field}" value="{new}">{carry}'
                    f'<button class="btn sm" style="padding:3px 9px;font-size:12px;{style}" type=submit>'
                    f'{"✓ " if on else ""}{label}</button></form>')
        status = ("blocks non-work" + (" + unknown" if bun else "")) if bnw or bun else "read-only"
        rows += (f'<tr><td><b>{_e(team)}</b></td>'
                 f'<td>{toggle("block_non_work", bnw, "block_unknown", bun, "Block non-work")} '
                 f'{toggle("block_unknown", bun, "block_non_work", bnw, "Block unknown")}</td>'
                 f'<td class=muted style="font-size:12px">{status}</td></tr>')
    return (
        '<div class=ocard style="margin-top:14px"><div class=dh>Stop non-work usage — per team '
        '<span class=muted style="font-weight:400;font-size:12px">(opt-in, in-path)</span></div>'
        '<p class=muted style="font-size:12.5px;margin:2px 0 10px">Pick what each team blocks. '
        'Enforcement runs in <b>your</b> opt-in gateway — Outlay records the rule and never blocks on its '
        'own. "Block unknown" is stricter: it also stops untracked usage (can catch real work).</p>'
        '<table><thead><tr><th>Team</th><th>Block policy</th><th>Status</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>')


def worktype_card(view: dict | None, teams: list | None = None, enforce: dict | None = None) -> str:
    """Work vs non-work spend split + per-key tagging + per-team opt-in enforcement.
    Metadata-only: a key flagged personal makes its spend non-work without ever
    reading a prompt."""
    if not view:
        return ""
    bar = ""
    for label, pct, col in (("work", view["work_pct"], "var(--grn)"),
                            ("non-work", view["non_work_pct"], "var(--red)"),
                            ("unknown", view["unknown_pct"], "#cfcabb")):
        if pct > 0:
            bar += f'<span title="{label} {pct:.0f}%" style="width:{pct}%;background:{col}"></span>'
    rows = ""
    for k in view["by_key"][:12]:
        cur = k["tag"]
        who = f' · {_e(k["user"])}' if k.get("user") else ""
        def b(val, lbl):
            on = (cur == val) or (val == "" and cur == "unflagged")
            style = ("background:var(--grn-l);border-color:#bfe3d4;color:var(--grn-d)" if on
                     else "background:var(--bg);color:var(--mut)")
            return (f'<form method=post action="/app/outlay/worktype/key-class" style="display:inline;margin:0">'
                    f'<input type=hidden name=key value="{_e(k["key"])}">'
                    f'<input type=hidden name=cls value="{val}">'
                    f'<button class="btn sm" style="padding:3px 9px;font-size:12px;{style}" type=submit>{lbl}</button></form>')
        rows += (f'<tr><td><b>{_e(k["key"])}</b><span class=muted style="font-size:12px">{who}</span></td>'
                 f'<td>{money(k["total_usd"])}</td>'
                 f'<td style="white-space:nowrap">{b("work","Work")} {b("non_work","Personal")} {b("","Clear")}</td></tr>')
    nonwork_banner = ""
    if view["non_work_usd"] > 0:
        nonwork_banner = (
            f'<div class=okbox style="background:var(--red-l);border-color:#f0cfca;margin-top:10px">'
            f'<b>{money(view["non_work_usd"])} ({view["non_work_pct"]:.0f}%) flagged non-work.</b> '
            f'To <b>stop</b> non-work usage, turn on the opt-in gateway (in-path enforcement) — '
            f'Outlay stays read-only and never blocks on its own.</div>')
    note = ('<p class=muted style="font-size:12px;margin-top:8px">Metadata-only — we never read prompts. '
            'Work = joined to a ticket/branch or a key you mark Work; flag a key <b>Personal</b> to count '
            'its spend as non-work. Unflagged, unjoined spend stays <b>unknown</b> (not guessed as non-work). '
            'For prompt-level labels, run the client-side classifier — it emits labels only, on your box.')
    return (
        '<div class=ocard style="margin-top:16px"><div class=dh>Work vs non-work AI spend</div>'
        f'<div style="display:flex;gap:18px;flex-wrap:wrap;margin:2px 0 10px">'
        f'<span><b style="color:var(--grn-d);font-size:18px">{money(view["work_usd"])}</b> '
        f'<span class=muted style="font-size:12.5px">work ({view["work_pct"]:.0f}%)</span></span>'
        f'<span><b style="color:var(--red);font-size:18px">{money(view["non_work_usd"])}</b> '
        f'<span class=muted style="font-size:12.5px">non-work ({view["non_work_pct"]:.0f}%)</span></span>'
        f'<span><b style="color:#8a8270;font-size:18px">{money(view["unknown_usd"])}</b> '
        f'<span class=muted style="font-size:12.5px">unknown ({view["unknown_pct"]:.0f}%)</span></span></div>'
        f'<div class=ebar style="height:10px;margin-bottom:6px">{bar}</div>'
        f'{nonwork_banner}'
        '<table style="margin-top:12px"><thead><tr><th>API key</th><th>Spend</th><th>Classify</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>{note}</div>'
        + _worktype_enforce_section(teams, enforce))


def governance_page(account: dict, report: dict | None, budget_statuses: list[dict],
                    program_statuses: list[dict], projects: list[dict] | None = None,
                    worktype: dict | None = None, teams: list | None = None,
                    enforce: dict | None = None) -> str:
    """The consolidated business governance deep-view — budgets + programs + the
    work-vs-non-work split in one place. Programs lead (cross-team caps with
    timelines), then single-scope budgets, then work-relatedness."""
    head = ('<div class=ohead><h1>Governance</h1>'
            '<p>Hold spend to budget. <b>Programs</b> cap a body of work across several teams or '
            'projects with a timeline; <b>budgets</b> cap a single scope. Both project your pace and '
            'flag a breach <b>before</b> month-end.</p></div>')
    attention = _finance_attention(report, budget_statuses, program_statuses)
    variance = _variance_section(program_statuses)
    programs = (f'<h2 style="font-size:16px;margin:18px 0 6px">Programs</h2>'
                f'{_programs_section(account, report, program_statuses)}')
    budgets = (f'<h2 style="font-size:16px;margin:24px 0 6px">Budgets</h2>'
               f'{_budgets_section(account, report, budget_statuses, projects)}')
    wt = (f'<h2 style="font-size:16px;margin:24px 0 6px">Work vs non-work</h2>'
          f'{worktype_card(worktype, teams, enforce)}') if worktype else ""
    return page("Governance", head + attention + variance + programs + budgets + wt,
                account, active="/app/outlay/governance")


def _chip(label: str, value: str) -> str:
    return (f'<span style="border:1px solid var(--line);border-radius:999px;padding:5px 12px;'
            f'font-size:12.5px"><span class=muted>{_e(label)}</span> <b>{value}</b></span>')


def _opportunities_html(opps: dict | None) -> str:
    """Advisory caching + batch candidate card (spec §3e)."""
    if not opps:
        return ""
    rows = ""
    for o in opps.get("caching", []):
        rows += (f'<tr><td>Prompt caching · <b>{_e(o["model"])}</b></td>'
                 f'<td>{money(o["uncached_input_usd"])} full-price input · '
                 f'{o["cache_utilization"] * 100:.0f}% cached</td>'
                 f'<td>up to {money(o["potential_savings_usd"])}</td></tr>')
    for o in opps.get("batch", []):
        rows += (f'<tr><td>Batch API · <b>{_e(o["task_class"])}</b></td>'
                 f'<td>{money(o["spend_usd"])} in a latency-tolerant class · '
                 f'{o["batch_discount"] * 100:.0f}% off</td>'
                 f'<td>up to {money(o["potential_savings_usd"])}</td></tr>')
    return (
        '<div class=ocard style="margin-top:16px"><div class=dh>Optimization opportunities '
        '<span class=muted style="font-weight:400;font-size:12px">(advisory — candidates to review)</span></div>'
        '<table><thead><tr><th>Opportunity</th><th>Why</th><th>Potential</th></tr></thead>'
        f'<tbody>{rows}</tbody></table>'
        '<p class=muted style="font-size:12px;margin-top:8px">Upper-bound potential, not realized '
        'savings. Caching only helps the <i>repeated-context</i> portion of input; batch only suits '
        'work that can tolerate latency — confirm both before acting.</p></div>')


def _commitment_pacing_html(pacing: list[dict] | None) -> str:
    """Active-commitment pacing (forfeit/overage) + an add form."""
    tone = {"on_track": "var(--grn-d)", "forfeit_risk": "var(--amber)", "overage_risk": "var(--red)"}
    label = {"on_track": "On track", "forfeit_risk": "Forfeit risk", "overage_risk": "Overage risk"}
    rows = ""
    for p in (pacing or []):
        col = tone.get(p["status"], "var(--muted)")
        rows += (
            f'<tr><td><b>{_e(p["provider"])}</b> · {money(p["amount_usd"])}'
            f'<div class=muted style="font-size:12px">{_e(p["kind"].replace("_", " "))}</div></td>'
            f'<td>{p["elapsed_pct"]:.0f}% elapsed · {money(p["used_to_date_usd"])} used</td>'
            f'<td>{p["utilization_at_end"]:.0f}%</td>'
            f'<td style="color:{col};font-weight:600">{_e(label.get(p["status"], p["status"]))}</td>'
            f'<td><form method=post action="/app/outlay/commitment/delete" style="margin:0">'
            f'<input type=hidden name=id value="{p["id"]}">'
            f'<button class="btn sec sm" type=submit>Remove</button></form></td></tr>')
    table = (f'<table><thead><tr><th>Commitment</th><th>Pace</th><th>Proj. use</th>'
             f'<th>Status</th><th></th></tr></thead><tbody>{rows}</tbody></table>') if rows else \
        '<p class=muted>No active commitments tracked yet. Add one to project forfeit / overage risk.</p>'
    form = (
        '<form method=post action="/app/outlay/commitment/add" '
        'style="display:flex;gap:8px;flex-wrap:wrap;align-items:end;margin-top:12px">'
        '<label style="font-size:12px;color:var(--muted)">Provider<br>'
        '<input name=provider placeholder="anthropic" style="padding:6px 8px"></label>'
        '<label style="font-size:12px;color:var(--muted)">Commit $<br>'
        '<input name=amount_usd type=number step=1000 required style="padding:6px 8px;width:120px"></label>'
        '<label style="font-size:12px;color:var(--muted)">Used to date $<br>'
        '<input name=used_to_date_usd type=number step=1000 value=0 style="padding:6px 8px;width:120px"></label>'
        '<label style="font-size:12px;color:var(--muted)">Start<br>'
        '<input name=start type=date required style="padding:6px 8px"></label>'
        '<label style="font-size:12px;color:var(--muted)">End<br>'
        '<input name=end type=date required style="padding:6px 8px"></label>'
        '<button class="btn primary sm" type=submit>Track</button></form>')
    return (f'<div class=ocard style="margin-top:16px"><div class=dh>Active commitments — pacing</div>'
            f'<p class=muted style="font-size:12.5px;margin:2px 0 10px">Track a vendor commitment '
            f'(metadata only — the numbers, not the contract) to project end-of-term forfeit or '
            f'overage before it bites.</p>{table}{form}</div>')


def _planmix_card(pm: dict | None) -> str:
    """Procurement-mix card (seat plans vs. API credits) for the Commitments page.

    Compute is uneven across people, so the cheapest buy is a mix: seats for the
    heavy users, API for the light ones. Advisory, metadata-only — from per-person
    attributed spend; the customer buys the seats with the vendor."""
    if not pm:
        return ""
    head = ('<div class=dh>Seat plans vs. API credits '
            '<span class=muted style="font-weight:400;font-size:12px">(per employee)</span></div>')
    if pm.get("total_savings_usd", 0) <= 0 or not pm.get("seats_by_plan"):
        return (
            '<div class=ocard style="margin-top:16px">' + head +
            '<p class=muted style="margin:2px 0 0">At current per-person usage, flat-fee seat plans '
            'don\'t beat buying API credits for everyone — your users are below the seat breakeven. '
            'We\'ll flag it the moment a heavier-usage cohort makes a seat cheaper.</p></div>')

    seatbits = ", ".join(f"<b>{n}× {_e(name)}</b>" for name, n in pm["seats_by_plan"].items())
    band = ""
    if pm.get("capacity_sensitivity"):
        band = (f' If a seat\'s effective capacity is ±{pm["capacity_sensitivity"] * 100:.0f}%, '
                f'savings range <b>{money(pm["savings_low_usd"])}</b>–<b>{money(pm["savings_high_usd"])}</b>/mo.')
    movers = [r for r in pm.get("people", []) if r.get("plan_name")][:8]
    rws = ""
    for r in movers:
        sat = (' <span class=muted style="font-size:11px">(saturated → overflow on API)</span>'
               if r.get("saturated") else "")
        rws += (
            f'<tr><td>{_e(r["user"])}</td>'
            f'<td>{money(r["usage_usd"])}</td>'
            f'<td>{_e(r["plan_name"])}{sat}</td>'
            f'<td>{money(r["cost_usd"])}</td>'
            f'<td style="color:var(--grn-d);font-weight:600">{money(r["savings_usd"])}</td></tr>')
    table = (
        '<table style="margin-top:10px"><thead><tr><th>Heaviest users</th><th>On API</th>'
        '<th>Best plan</th><th>On plan</th><th>Saves</th></tr></thead>'
        f'<tbody>{rws}</tbody></table>') if rws else ""
    unattr = ""
    if pm.get("unattributed_usd", 0) > 0:
        unattr = (f'<p class=muted style="font-size:12px;margin-top:8px">'
                  f'{money(pm["unattributed_usd"])}/mo isn\'t attributed to a person yet — it stays on '
                  'API. Improve attribution coverage to optimize it too.</p>')
    return (
        '<div class=ocard style="margin-top:16px;border-left:4px solid var(--grn-d)">' + head +
        f'<p style="margin:2px 0 10px">Buying API credits for everyone costs '
        f'<b>{money(pm["status_quo_usd"])}/mo</b>. The cheapest mix — {seatbits}, with the other '
        f'<b>{pm["n_on_api"]}</b> on API — costs <b>{money(pm["optimized_usd"])}/mo</b>: '
        f'save <b style="color:var(--grn-d)">{money(pm["total_savings_usd"])}/mo</b> '
        f'(<b>{pm["savings_rate"] * 100:.0f}%</b>).{band}</p>'
        + table + unattr +
        '<p class=muted style="font-size:12px;margin-top:8px">Seat fees/capacities are illustrative — '
        'replace with your real plan terms. Advisory and metadata-only: we recommend the mix from '
        'per-person spend; you buy the seats with the vendor.</p></div>')


def commitment_page(account: dict, view: dict | None, opps: dict | None = None,
                    pacing: list[dict] | None = None, planmix: dict | None = None) -> str:
    """Commitment & procurement optimization recommender (advisory, read-only).

    From the customer's own spend run-rate: should they stay on-demand, or take a
    committed-spend discount — and at what level, given forfeit risk."""
    head = ('<div class=ohead><h1>Commitments</h1>'
            '<p>The cheapest <b>way to pay</b> for your AI compute. From your own spend '
            'run-rate we size an optional <b>committed-spend discount</b> and weigh it against '
            '<b>forfeit risk</b>. Advisory — you commit with the vendor; we never sit in the path.</p></div>')

    if not view:
        body = ('<div class=ocard><div class=dh>Not enough data yet</div>'
                '<p class=muted>Connect a usage source and sync so we can read your spend '
                'run-rate, then this page sizes a commitment for you.</p>'
                '<a class="btn sec sm" href="/app/outlay/connect">Connect a source →</a></div>')
        return page("Commitments",
                    head + body + _planmix_card(planmix) + _commitment_pacing_html(pacing),
                    account, active="/app/outlay/commitment")

    rate = (f' · blended <b>{money(view["blended_rate"])}/Mtok</b>'
            if view.get("blended_rate") else '')
    profile = (
        f'<div class=ocard><div class=dh>Your spend profile</div>'
        f'<p class=muted style="font-size:12.5px;margin:2px 0 10px">'
        f'Monthly run-rate <b>{money(view["monthly_on_demand_usd"])}</b>{rate}. '
        f'Steady floor <b>{money(view["floor_usd"])}/mo</b>, '
        f'steadiness <b>{view["steadiness"] * 100:.0f}%</b> '
        f'(higher ⇒ more of your bill is safely committable).</p>'
        f'<div style="display:flex;gap:10px;flex-wrap:wrap">'
        f'{_chip("floor", money(view["floor_usd"]))}'
        f'{_chip("median", money(view["median_usd"]))}'
        f'{_chip("peak", money(view["peak_usd"]))}</div></div>')

    tone = {"none": "var(--grn-d)", "low": "var(--amber)", "elevated": "var(--red)"}
    rws = ""
    for s in view["scenarios"]:
        risk = s["forfeit_risk"]
        rws += (
            f'<tr><td><b>{_e(s["label"].title())}</b></td>'
            f'<td>{money(s["commit_usd"])}</td>'
            f'<td>{s["discount"] * 100:.0f}%</td>'
            f'<td>{money(s["billed_usd"])}</td>'
            f'<td>{money(s["net_savings_usd"])}</td>'
            f'<td>{s["effective_savings_rate"] * 100:.1f}%</td>'
            f'<td style="color:{tone.get(risk, "var(--muted)")};font-weight:600">{_e(risk)}</td></tr>')
    table = (
        '<div class=ocard style="margin-top:16px"><div class=dh>Committed-spend options (per month)'
        '<a class=sub href="/app/outlay/commitment-pack.csv">Export negotiation pack →</a></div>'
        '<table><thead><tr><th>Scenario</th><th>Commit</th><th>Discount</th><th>Billed</th>'
        '<th>Net savings</th><th>Eff. rate</th><th>Forfeit risk</th></tr></thead>'
        f'<tbody>{rws}</tbody></table>'
        '<p class=muted style="font-size:12px;margin-top:8px">Discount tiers are illustrative — '
        'replace with your negotiated terms. Net savings is vs. paying on-demand; forfeit risk rises '
        'as the commit approaches your peak rather than your floor.</p></div>')

    prov = view.get("provisioned")
    prov_html = ""
    if prov:
        verdict = ("Worth pricing with your vendor" if prov.get("recommend")
                   else "Likely stay on-demand for now")
        vcol = "var(--grn-d)" if prov.get("recommend") else "var(--muted)"
        prov_html = (
            '<div class=ocard style="margin-top:16px"><div class=dh>Provisioned throughput '
            '<span class=muted style="font-weight:400;font-size:12px">(directional)</span></div>'
            f'<p style="margin:2px 0 10px">Your steady floor sustains about '
            f'<b>{prov["steady_tokens_per_sec"]:,.0f} tokens/sec</b> at '
            f'<b>{prov["steadiness"] * 100:.0f}%</b> steadiness. Dedicated capacity (Azure OpenAI PTUs, '
            f'Bedrock provisioned, reserved GPUs) is priced to beat on-demand once a unit stays busy — '
            f'a large, steady base is exactly that case. '
            f'<span style="color:{vcol};font-weight:600">{verdict}.</span></p>'
            '<p class=muted style="font-size:12px">Break-even = provisioned $/hr ÷ '
            '(on-demand $/token × tokens/sec × 3600). Bring your vendor\'s actual unit price and '
            'throughput to size how many units to reserve for the steady base; keep spikes on-demand.</p></div>')

    rec = view.get("recommended")
    if rec:
        banner = (
            f'<div class=ocard style="margin-top:16px;border-left:4px solid var(--grn-d)">'
            f'<div class=dh>Recommended</div>'
            f'<p>Commit <b>{money(rec["commit_usd"])}/mo</b> ({_e(rec["label"])}) → '
            f'~<b>{money(rec["net_savings_usd"])}/mo</b> net '
            f'(<b>{rec["effective_savings_rate"] * 100:.0f}%</b>), forfeit risk '
            f'<b>{_e(rec["forfeit_risk"])}</b>. Take this run-rate to your vendor as the basis '
            f'for the commit.</p></div>')
    else:
        banner = (
            '<div class=ocard style="margin-top:16px"><div class=dh>Stay on-demand</div>'
            '<p class=muted>At your current run-rate a committed-spend discount doesn\'t beat '
            'on-demand (spend is below the discount tiers, or too spiky to commit without forfeit). '
            'We\'ll flag it the moment that changes.</p></div>')

    note = ""
    if not view.get("enough_history"):
        note = ('<p class=muted style="font-size:12px;margin-top:14px">Based on your latest run-rate '
                f'({view["n_snapshots"]} sync snapshot(s)). The floor/steadiness estimate sharpens as '
                'more sync history accumulates.</p>')

    return page("Commitments",
                head + profile + table + prov_html + _planmix_card(planmix)
                + _opportunities_html(opps)
                + _commitment_pacing_html(pacing) + banner + note,
                account, active="/app/outlay/commitment")


def _quarter_label(ts: float | None = None) -> str:
    from datetime import datetime, timezone
    d = datetime.fromtimestamp(ts, timezone.utc) if ts else datetime.now(timezone.utc)
    return f"Q{(d.month - 1) // 3 + 1} {d.year}"


def pilot_request_page(error: str = "", values: dict | None = None) -> str:
    """Public, branded design-partner pilot request form (replaces the mailto CTA)."""
    v = values or {}
    err = f'<div class=ostrip style="background:var(--red-l);margin-bottom:14px"><span>{_e(error)}</span></div>' if error else ""
    body = (
        '<div class=ohead style="margin-top:30px"><h1>Become an Outlay customer</h1>'
        '<p>Tell us a bit about your team and we\'ll get back to you within a day. We start with a '
        'read-only, ~2-week pilot — we map your real AI spend to your roadmap and forecast the quarter — '
        'then onboard you as a customer.</p></div>'
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
        '<button class="btn" style="margin-top:16px">Become a customer →</button>'
        '<p class=muted style="font-size:12px;margin:12px 0 0">We\'ll only use this to follow up about '
        'getting you started. No spam.</p>'
        '</form>')
    return page("Become a customer", body, bare=True)


def audit_page(account: dict, entries: list[dict]) -> str:
    """Owner/admin audit trail — security-relevant activity, newest first."""
    head = ('<div class=ohead><h1>Activity &amp; audit log</h1>'
            '<p>Security-relevant events on your account — sign-ins, connection changes, and team '
            'changes. Newest first.</p></div>')
    siem = ('<div class=olinks style="margin:-6px 0 16px">'
            '<a href="/app/audit/export.csv">Export CSV</a>'
            '<span class=muted style="font-size:12.5px">· stream to your SIEM via '
            '<a href="/app/api">the audit API</a> (poll <code>/api/v1/audit?since=…</code>)</span></div>')
    if not entries:
        return page("Activity", head + siem + '<div class=ocard><p class=muted style="margin:0">'
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
    return page("Activity", head + siem + table, account, active="/app/audit")


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
            '<p>Your request is in. We read every one and typically reply within a day '
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


_LANDING_CSS = """<style>
  .lp{max-width:980px;margin:0 auto;padding:0 4px}
  .lp .hero{max-width:760px;margin:48px auto 8px;text-align:center}
  .lp .hero h1{font-size:46px;line-height:1.05;letter-spacing:-.02em;margin:10px 0 14px}
  .lp .hero p.sub{font-size:18px;line-height:1.55;color:var(--body);max-width:62ch;margin:0 auto}
  .lp .eyebrow{justify-content:center;text-align:center}
  .lp .cta{justify-content:center;margin-top:22px}
  .lp .trust{margin-top:18px;font-size:13px}
  .lp .wo{margin:44px auto 8px;text-align:center}
  .lp .wo .lab{font-size:11.5px;letter-spacing:.12em;text-transform:uppercase;color:var(--faint);margin-bottom:12px}
  .lp .pills{display:flex;flex-wrap:wrap;gap:8px;justify-content:center;max-width:760px;margin:0 auto}
  .lp .pill{border:1px solid var(--line);border-radius:999px;padding:6px 13px;font-size:13px;
    font-weight:500;color:var(--body);background:var(--bg)}
  .lp .sec{margin:52px auto}
  .lp .sec h2{font-size:13px;letter-spacing:.06em;text-transform:uppercase;color:var(--grn-d);
    text-align:center;margin:0 0 20px;font-weight:600}
  .lp .g3{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
  .lp .step .n{display:inline-flex;align-items:center;justify-content:center;width:26px;height:26px;
    border-radius:999px;background:var(--grn-l);color:var(--grn-d);font-weight:700;font-size:13px;margin-bottom:10px}
  .lp .step h3,.lp .why h3{font-size:15.5px;margin:0 0 6px}
  .lp .step p,.lp .why p{font-size:13.5px;line-height:1.55;color:var(--muted);margin:0}
  .lp .band{background:var(--navy);color:#dfe7f2;border-radius:14px;padding:22px 26px;text-align:center}
  .lp .band b{color:#fff}
  .lp .band .pills .pill{border-color:rgba(255,255,255,.18);background:transparent;color:#cdd7e6}
  .lp .close{text-align:center;margin:54px auto 30px;max-width:620px}
  .lp .close h2{font-size:30px;letter-spacing:-.01em;text-transform:none;color:var(--ink);margin:0 0 16px}
  @media(max-width:760px){.lp .g3{grid-template-columns:1fr}.lp .hero h1{font-size:34px}}
</style>"""


def landing() -> str:
    pill = lambda t: f'<span class=pill>{t}</span>'
    providers = ["Anthropic / Claude", "Claude Code", "Cursor", "OpenAI / Azure",
                 "Amazon Bedrock", "Google Vertex", "GitHub", "Jira", "Linear"]
    steps = [
        ("1", "Connect, read-only", "Bring your own keys to your AI provider and your tracker (Jira / Linear / "
         "GitHub). Outlay reads usage <b>metadata only</b> — token counts and dollar figures. Prompts, outputs, "
         "and keys never leave your environment."),
        ("2", "Attribute &amp; forecast", "Every dollar of LLM and coding-agent spend is mapped to the ticket, "
         "team, and person that drove it — then Outlay forecasts the quarter and prices your open backlog, with "
         "accuracy back-tested on your own closed work."),
        ("3", "Govern", "Set budgets and hard program caps across teams, get route-down recommendations to "
         "cheaper models where they're provably good enough, and enforce <b>before</b> you overspend — not at "
         "month-end."),
    ]
    why = [
        ("Cache-aware costing", "Outlay prices every token class separately — cache reads bill at ~1/10th. Naive "
         "trackers that count raw tokens overstate cache-heavy agentic spend several times over."),
        ("Accuracy you can check", "We don't ask you to trust a vendor benchmark. The forecast is back-tested "
         "leave-one-out on <b>your own</b> closed tickets, and we always show the measured error."),
        ("Reconciled to the invoice", "Every fidelity tier is shown so the total ties out to your provider's "
         "billed figure. A number business can take to the board."),
    ]
    steps_html = "".join(
        f'<div class="card step"><span class=n>{n}</span><h3>{h}</h3><p>{p}</p></div>' for n, h, p in steps)
    why_html = "".join(f'<div class="card why"><h3>{h}</h3><p>{p}</p></div>' for h, p in why)
    body = f"""{_LANDING_CSS}
    <div class=lp>
      <div class=hero>
        <div class=eyebrow>The control plane for AI compute spend</div>
        <h1>Put AI compute on a budget.</h1>
        <p class=sub>Outlay attributes every dollar of LLM and coding-agent spend to the work you already
        plan — tickets, epics, roadmap — forecasts the quarter, and lets you <b>enforce a budget per
        program</b>. Read-only to start; your prompts and keys never leave your environment.</p>
        <div class="row cta">
          <a class=btn href="/pilot-request">Become a customer →</a>
          <a class="btn sec" href="/login">Sign in</a>
        </div>
        <p class="trust muted">Read-only · metadata-only · BYOK · no app rewrite</p>
      </div>

      <div class=wo>
        <div class=lab>Works with your stack</div>
        <div class=pills>{"".join(pill(p) for p in providers)}</div>
      </div>

      <div class=sec>
        <h2>How it works</h2>
        <div class=g3>{steps_html}</div>
      </div>

      <div class=sec>
        <h2>Why the number is trustworthy</h2>
        <div class=g3>{why_html}</div>
      </div>

      <div class=sec>
        <div class=band>
          <p style="margin:0 0 12px;font-size:15px">Built metadata-only and read-only. <b>No prompts, outputs,
          or API keys ever leave your environment.</b></p>
          <div class=pills style="margin-top:2px">{"".join(pill(x) for x in
            ["Read-only", "Metadata-only", "BYOK", "SSO / OIDC", "SCIM", "2FA", "Audit log + SIEM export",
             "WCAG 2.1 AA"])}</div>
        </div>
      </div>

      <div class=close>
        <h2>See your AI spend mapped to your roadmap.</h2>
        <div class="row cta" style="margin-top:0">
          <a class=btn href="/pilot-request">Become a customer →</a>
          <a class="btn sec" href="/login">Sign in</a>
        </div>
      </div>
    </div>"""
    return page("Put AI compute on a budget", body)


def twofa_verify_form(error: str = "", note: str = "", has_code: bool = True,
                      has_passkey: bool = False) -> str:
    err = f'<div class="note bad">{_e(error)}</div>' if error else ""
    nt = f'<div class="note">{_e(note)}</div>' if note else ""
    # Passkey button first (strongest, one tap). Falls through to the code form below.
    passkey = ""
    if has_passkey:
        passkey = ('<button type=button class="btn" style="width:100%" onclick="loginPasskey()">'
                   '&#128273; Sign in with a passkey</button>'
                   + ('<div style="text-align:center;color:var(--muted);font-size:12px;margin:12px 0">'
                      'or use a code</div>' if has_code else ''))
    code_form = ""
    if has_code:
        code_form = (
            '<form method=post action="/login/verify">'
            '<div class=field><label>Verification code</label>'
            '<input name=code inputmode=numeric autocomplete=one-time-code pattern="[0-9]*" maxlength=6 '
            'required placeholder="123456" style="letter-spacing:4px;font-size:18px"></div>'
            '<button class="btn" style="width:100%">Verify &amp; sign in</button></form>'
            '<form method=post action="/login/verify/resend" style="margin-top:10px">'
            '<button class="btn sec sm" style="width:100%">Resend code</button></form>')
    sub = ("Use your authenticator app, a passkey, or the code we sent." if (has_passkey and has_code)
           else "Use your passkey to finish signing in." if has_passkey
           else "Enter the 6-digit code. It expires in 10 minutes.")
    body = f"""
    <div class=auth><div class=card>
      <h1>Verify it's you</h1>
      <p class=muted small>{sub}</p>
      {err}{nt}
      {passkey}
      {code_form}
    </div></div>{_WEBAUTHN_JS if has_passkey else ''}"""
    return page("Verify", body)


def _twofa_section(account: dict, state: str = "") -> str:
    tf = store.get_2fa(account["id"], member_id=account.get("member_id", 0) or 0)
    note = ""
    if state == "on":
        note = '<div class="note" role=status>Two-factor authentication is on.</div>'
    elif state == "off":
        note = '<div class="note" role=status>Two-factor authentication turned off.</div>'
    elif state == "bad":
        note = '<div class="note bad" role=status>That code was wrong or expired — start again.</div>'
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
    full_name = ('<div class=field><label>Your name <span class=muted>(optional)</span></label>'
                 '<input name=name aria-label="Your name" placeholder="Jane Doe"></div>') if is_signup else ""
    company = ('<div class=field><label>Company <span class=muted>(optional)</span></label>'
               '<input name=company aria-label="Company name" placeholder="Acme Inc."></div>') if is_signup else ""
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
           '<input name=email type=email aria-label="Email for SSO sign-in" required placeholder="you@company.com" '
           'style="flex:1">'
           '<button class="btn sec" type=submit style="white-space:nowrap">Use SSO</button>'
           '</form></div>')
    sub = "Create account" if is_signup else "Sign in"
    alt = ('Already have an account? <a href="/login">Sign in</a>' if is_signup
           else 'New here? <a href="/pilot-request">Become a customer</a> · '
                '<a href="/forgot">Forgot password?</a>')
    body = f"""
    <div class=auth><div class=card>
      <h1>{_e(title)}</h1>
      <p class=muted small>{'14 days free · full features · no card required to start.' if is_signup else 'Welcome back.'}</p>
      {err}
      <form method=post action="/{kind}">
        <div class=field><label>Work email</label>
          <input name=email type=email aria-label="Email address" required value="{_e(email)}" placeholder="you@company.com"></div>
        {full_name}
        {company}
        <div class=field><label>Password</label>
          <input name=password type=password aria-label="Password" required minlength=8 placeholder="At least 8 characters"></div>
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

def _trial_banner(plan: dict, trial: dict, persona: str = "") -> str:
    if plan.get("plan") == "paid":
        return ""
    if trial.get("not_started"):
        if persona == "business":
            # Business doesn't connect anything — engineering does. Point them at the
            # invite, not at the setup form.
            return (f'<div class="note">Your <b>{store.TRIAL_DAYS}-day free trial starts once your data is '
                    f'connected</b> — your engineering counterpart wires up the sources. '
                    f'<a href="/app/team">Invite engineering →</a></div>')
        return (f'<div class="note">Your <b>{store.TRIAL_DAYS}-day free trial starts once you connect your '
                f'data</b> — so the clock only runs while you\'re actually evaluating. '
                f'<a href="/app/outlay/connect">Connect your sources →</a></div>')
    if trial["active"]:
        d = trial["days_left"]
        if d <= 2:
            return (f'<div class="note warn">⏳ Only <b>{d} day{"" if d == 1 else "s"} left</b> in your free '
                    f'trial. Outlay is in early access — your first weeks are free. '
                    f'<a href="/app/billing">Manage your plan</a> to keep your account active.</div>')
        return (f'<div class="note">You\'re on the free trial — <b>{d} days left</b>. Your first weeks are '
                f'free; <a href="/app/billing">see your plan</a> for what happens after.</div>')
    return ('<div class="note bad">Your free trial has ended. <a href="/app/billing">Manage your plan</a> '
            'to keep using Outlay.</div>')


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
    persona = ((account or {}).get("persona") or "").lower()
    return _trial_banner(plan, trial, persona) if plan else ""


def _trial_pill(account: dict | None) -> str:
    plan, trial = _trial_meta(account)
    if not plan or plan.get("plan") == "paid":
        return ""
    persona = ((account or {}).get("persona") or "").lower()
    if trial.get("not_started"):
        # Business never visits Connect — its trial starts when engineering connects.
        href = "/app/team" if persona == "business" else "/app/outlay/connect"
        return f'<a class="trialpill" href="{href}">Trial · starts at setup</a>'
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


# PARKED (not wired to any route): the ModelPilot routing dashboard with savings
# telemetry. Hidden while Outlay leads with spend attribution/forecasting. Kept for
# reference / possible revival — do not link it from customer-facing nav.
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
    """PARKED (its /app/estimate route now redirects to the Outlay estimate).
    Logged-in savings view: MEASURED savings from the customer's own traffic +
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
                  delete_error: bool = False, twofa: str = "",
                  retention_days: int = 0, purged: bool = False, purge_error: bool = False) -> str:
    # Grouped IA: Account & team · Security · Notifications · Data & privacy ·
    # Danger zone. Each group hides itself when its cards are empty (role-gated), so
    # a member sees a shorter page than an owner. (Budgets live at /app/outlay/budgets;
    # the /app/settings POST still accepts the legacy routing fields.)
    saved_note = '<div class="note" role=status>Settings saved.</div>' if saved else ""
    body = (f"<h1>Settings</h1>{saved_note}"
            + _settings_group("Account &amp; team", _profile_section(account), _settings_links(account))
            + _settings_group("Security", _twofa_section(account, twofa))
            + _settings_group("Notifications", _digest_section(account))
            + _settings_group("Help us improve", _feedback_widget())
            + _settings_group("Data &amp; privacy",
                              _retention_section(account, retention_days, purged, purge_error))
            + _danger_zone(account, delete_error))
    return page("Settings", body, account, "/app/settings")


# Minimal WebAuthn browser glue (base64url + create/get + fetch). Embedded once on the
# Security page and the 2FA-verify page. Kept dependency-free and small on purpose.
_WEBAUTHN_JS = """
<script>
const b64uTo=b=>Uint8Array.from(atob(b.replace(/-/g,'+').replace(/_/g,'/').padEnd(b.length+(4-b.length%4)%4,'=')),c=>c.charCodeAt(0));
const toB64u=a=>btoa(String.fromCharCode(...new Uint8Array(a))).replace(/\\+/g,'-').replace(/\\//g,'_').replace(/=+$/,'');
function pkCreate(o){o.challenge=b64uTo(o.challenge);o.user.id=b64uTo(o.user.id);(o.excludeCredentials||[]).forEach(c=>c.id=b64uTo(c.id));return navigator.credentials.create({publicKey:o});}
function pkGet(o){o.challenge=b64uTo(o.challenge);(o.allowCredentials||[]).forEach(c=>c.id=b64uTo(c.id));return navigator.credentials.get({publicKey:o});}
function regCred(c){return {id:c.id,rawId:toB64u(c.rawId),type:c.type,clientExtensionResults:{},response:{clientDataJSON:toB64u(c.response.clientDataJSON),attestationObject:toB64u(c.response.attestationObject)}};}
function authCred(c){const r=c.response;return {id:c.id,rawId:toB64u(c.rawId),type:c.type,clientExtensionResults:{},response:{clientDataJSON:toB64u(r.clientDataJSON),authenticatorData:toB64u(r.authenticatorData),signature:toB64u(r.signature),userHandle:r.userHandle?toB64u(r.userHandle):null}};}
async function enrollPasskey(){
  try{
    const o=await (await fetch('/app/2fa/webauthn/options',{method:'POST'})).json();
    if(o.error){alert(o.error);return;}
    const cred=await pkCreate(o);
    const label=(navigator.userAgentData&&navigator.userAgentData.platform)||navigator.platform||'Passkey';
    const r=await (await fetch('/app/2fa/webauthn/verify',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({credential:regCred(cred),label})})).json();
    if(r.ok){location.href='/app/security?ok=passkey';}else{alert(r.error||'Could not add passkey.');}
  }catch(e){alert('Passkey setup was cancelled or failed.');}
}
async function loginPasskey(){
  try{
    const o=await (await fetch('/login/webauthn/options',{method:'POST'})).json();
    if(o.error){alert(o.error);return;}
    const cred=await pkGet(o);
    const r=await (await fetch('/login/webauthn/verify',{method:'POST',headers:{'content-type':'application/json'},body:JSON.stringify({credential:authCred(cred)})})).json();
    if(r.ok){location.href=r.redirect||'/app';}else{alert(r.error||'Could not verify passkey.');}
  }catch(e){alert('Passkey sign-in was cancelled or failed.');}
}
</script>"""


def _passkey_block(passkeys: list | None, webauthn_on: bool) -> str:
    """Passkey enrollment + management inside 'Your sign-in security'."""
    if not webauthn_on:
        return ""
    rows = ""
    for k in (passkeys or []):
        when = _fmt_date(k.get("created_at")) if k.get("created_at") else ""
        rows += (f'<div style="display:flex;justify-content:space-between;align-items:center;'
                 f'gap:10px;margin-top:6px;font-size:13px">'
                 f'<span>&#128273; <b>{_e(k.get("label") or "Passkey")}</b>'
                 f'<span class=muted style="font-size:11.5px"> · added {when}</span></span>'
                 f'<form method=post action="/app/2fa/webauthn/delete" style="margin:0">'
                 f'<input type=hidden name=id value="{k["id"]}">'
                 f'<button class="btn sec sm">Remove</button></form></div>')
    listing = rows or '<p class=muted style="font-size:12.5px;margin:6px 0 0">No passkeys yet.</p>'
    return (
        '<div style="margin-top:14px;border-top:1px solid var(--line);padding-top:10px">'
        '<div style="font-weight:600;font-size:13.5px">Passkeys '
        '<span class=muted style="font-weight:400">· phishing-resistant (FIDO2 / WebAuthn)</span></div>'
        '<p class=muted style="font-size:12.5px;margin:4px 0 8px">A passkey (Touch ID, Windows Hello, '
        'a security key) is the strongest second factor — it can\'t be phished or replayed.</p>'
        f'{listing}'
        '<button type=button class="btn sec sm" style="margin-top:10px" onclick="enrollPasskey()">'
        'Add a passkey →</button></div>')


def _trust_controls(account: dict, policy: dict, twofa: dict, enroll_secret: str = "",
                    flash: str = "", passkeys: list | None = None, webauthn_on: bool = False) -> str:
    """Interactive Trust Center controls — the org security policy (admin-enforced MFA,
    session timeouts, data residency, incident webhook), this person's sign-in security
    (2FA incl. TOTP + passkeys + log-out-everywhere), and the compliance artifacts."""
    is_admin = account.get("team_role") in ("owner", "admin")
    mfa_on = bool(twofa.get("enabled"))
    fl = {"mfa-required": ('<div class="note warn" role=alert>Your organization requires multi-factor '
                           'authentication — enroll below to continue.</div>'),
          "policy-saved": '<div class=note role=status>Security policy saved.</div>',
          "totp-on": '<div class=note role=status>Authenticator app enabled.</div>',
          "totp-bad": '<div class="note bad" role=alert>That code didn\'t match — try again.</div>',
          "logged-out-all": '<div class=note role=status>Signed out of all other sessions.</div>',
          "passkey-on": '<div class=note role=status>Passkey added.</div>',
          }.get(flash, "")

    # --- This person's sign-in security ---
    if mfa_on:
        ch = twofa.get("channel") or "email"
        label = {"totp": "Authenticator app (TOTP)", "email": "Email one-time codes",
                 "sms": "SMS one-time codes"}.get(ch, ch)
        twofa_block = (f'<p style="margin:6px 0 10px"><span class="otag ok">on</span> '
                       f'<b>{_e(label)}</b></p>'
                       '<form method=post action="/app/2fa/disable" style="display:inline">'
                       '<button class="btn sec sm">Turn off 2FA</button></form>')
    elif enroll_secret:
        uri = (f"otpauth://totp/Outlay:{quote(account.get('display_email') or account.get('email',''))}"
               f"?secret={enroll_secret}&issuer=Outlay")
        twofa_block = (
            '<p style="margin:6px 0 8px">Scan this in your authenticator app (or enter the key), then '
            'confirm a code:</p>'
            f'<div class=mono style="font-size:13px;word-break:break-all;background:var(--paper2);'
            f'border:1px solid var(--line);border-radius:8px;padding:10px;margin-bottom:8px">'
            f'Key: <b>{enroll_secret}</b><br><span class=muted style="font-size:11.5px">{_e(uri)}</span></div>'
            '<form method=post action="/app/2fa/totp/confirm" style="display:flex;gap:8px;flex-wrap:wrap">'
            f'<input type=hidden name=secret value="{enroll_secret}">'
            '<input name=code inputmode=numeric placeholder="123456" required '
            'style="width:120px;padding:7px 9px;border:1px solid var(--line);border-radius:8px;letter-spacing:2px">'
            '<button class=btn>Confirm &amp; enable</button></form>')
    else:
        # Owners can also choose email codes; invited members are authenticator-only (AAL2).
        email_opt = ('' if account.get("member_id") else
                     '<form method=post action="/app/2fa/start" style="margin:0">'
                     '<button class="btn sec">Use email codes</button></form>')
        rec = ('<b>authenticator app (TOTP)</b> is phishing-resistant-grade and recommended.'
               if account.get("member_id") else
               'An <b>authenticator app (TOTP)</b> is phishing-resistant-grade and recommended; '
               'email codes also work.')
        twofa_block = (
            f'<p class=muted style="margin:6px 0 10px;font-size:13.5px">Add a second factor. {rec}</p>'
            '<div class=row>'
            '<form method=post action="/app/2fa/totp/start" style="margin:0">'
            '<button class="btn">Set up authenticator app →</button></form>'
            f'{email_opt}</div>')
    signin = (f'<div class=ocard style="margin-top:16px"><div class=dh>Your sign-in security</div>'
              f'{twofa_block}'
              f'{_passkey_block(passkeys, webauthn_on)}'
              '<div style="margin-top:12px;border-top:1px solid var(--line);padding-top:10px">'
              '<form method=post action="/app/security/logout-all" style="margin:0">'
              '<button class="btn sec sm">Log out everywhere</button>'
              '<span class=muted style="font-size:12px;margin-left:8px">Ends every other active session '
              '(after a password change or a lost device).</span></form></div></div>')

    # --- Org security policy (admin only) ---
    pol = ""
    if is_admin:
        ck = "checked" if policy.get("require_mfa") else ""
        idle = policy.get("session_idle_min") or 0
        smax = policy.get("session_max_hours") or 0
        pol = (
            '<div class=ocard style="margin-top:16px"><div class=dh>Organization security policy '
            '<span class=sub>admin</span></div>'
            '<form method=post action="/app/security/policy">'
            f'<label style="display:flex;gap:8px;align-items:center;margin:6px 0 12px;font-size:14px">'
            f'<input type=checkbox name=require_mfa value=1 {ck}> <b>Require multi-factor authentication</b> '
            f'for everyone in this workspace (IA-2). <span class=muted>Owners, admins, and invited '
            f'members are each gated to enroll an authenticator before access.</span></label>'
            '<div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px;align-items:end">'
            '<label class=fld><span>Idle timeout (minutes, 0 = none)</span>'
            f'<input name=session_idle_min type=number min=0 max=1440 value="{idle}"></label>'
            '<label class=fld><span>Max session (hours, 0 = default)</span>'
            f'<input name=session_max_hours type=number min=0 max=720 value="{smax}"></label>'
            '<label class=fld><span>Data region</span>'
            f'<input name=data_region value="{_e(policy.get("data_region") or "")}" placeholder="US"></label>'
            '</div>'
            '<label class=fld style="margin-top:12px"><span>Incident / breach notification webhook '
            '(your SOC/SIEM)</span>'
            f'<input name=security_webhook type=url value="{_e(policy.get("security_webhook") or "")}" '
            'placeholder="https://your-soc.example.com/hooks/outlay"></label>'
            '<p class=muted style="font-size:12px;margin:6px 0 0">We post a signed alert here on a '
            'security event so you can meet your own reporting SLA (e.g. Maryland\'s 1-hour MD-SOC rule).</p>'
            '<button class="btn" style="margin-top:12px">Save policy</button></form></div>')

    # --- Compliance artifacts ---
    artifacts = (
        '<div class=ocard style="margin-top:16px"><div class=dh>Compliance &amp; artifacts</div>'
        '<a class=exrow href="/app/security/vpat" target=_blank><span class=nm>VPAT / ACR</span>'
        '<span class=exd>WCAG 2.1 AA · Section 508 · Maryland NTIAA nonvisual access.</span><span class=exarr>→</span></a>'
        '<a class=exrow href="/app/security/ai-card" target=_blank><span class=nm>AI model &amp; system card + Acceptable Use Policy</span>'
        '<span class=exd>Where AI is used, no-training guarantee, human oversight — NIST AI RMF / MD AI Act.</span><span class=exarr>→</span></a>'
        '<a class=exrow href="/app/audit/export.csv"><span class=nm>Audit log export (CSV → SIEM)</span>'
        '<span class=exd>Every privileged + auth event; kept for the life of the account (never auto-purged).</span><span class=exarr>→</span></a>'
        f'<div class=note style="margin-top:12px"><b>Status.</b> SOC 2 Type II — <b>in progress</b>. '
        f'Hosting — Fly.io (SOC 2 / ISO 27001 data centers); a FedRAMP-Moderate region is on the '
        f'roadmap for StateRAMP/GovRAMP-gated deals. Data region: <b>{_e(policy.get("data_region") or "US")}</b>.</div></div>')

    return fl + signin + pol + artifacts + (_WEBAUTHN_JS if webauthn_on else "")


def security_page(account: dict, policy: dict | None = None, twofa: dict | None = None,
                  enroll_secret: str = "", flash: str = "", passkeys: list | None = None,
                  webauthn_on: bool = False) -> str:
    """In-app security & compliance Trust Center — interactive controls (org policy,
    sign-in security, compliance artifacts) plus the reviewer-facing summary. Every
    claim maps to a shipped feature; certification status is stated honestly."""
    ck = '<span style="color:var(--grn);font-weight:800;flex:none">&#10003;</span>'

    def li(html: str) -> str:
        return f'<li style="display:flex;gap:10px;margin:9px 0;font-size:14.5px">{ck}<span>{html}</span></li>'

    def card(title: str, *items: str, note: str = "") -> str:
        lis = "".join(items)
        note_h = f'<div class=note style="margin-top:12px">{note}</div>' if note else ""
        return (f'<div class=ocard style="margin-top:16px"><div class=dh>{title}</div>'
                f'<ul style="list-style:none;padding:0;margin:8px 0 0">{lis}</ul>{note_h}</div>')

    controls = _trust_controls(account, policy or {}, twofa or {}, enroll_secret, flash,
                               passkeys=passkeys, webauthn_on=webauthn_on)
    body = f"""
    <h1>Security &amp; compliance</h1>
    <p class=muted style="max-width:72ch">Your Trust Center — manage your security policy and sign-in,
      and find the artifacts for a security review. Outlay is built so the sensitive data
      <b>physically can't reach us</b>: prompts, model outputs, and your API keys never leave your
      environment.</p>
    {controls}

    <div class=ocard style="margin-top:16px"><div class=dh>Architecture — read-only, never in your traffic path</div>
      <p class=muted style="margin:6px 0 0;font-size:14.5px">Outlay is <b>not a proxy or gateway</b>.
        Your AI calls go directly from your infrastructure to your model provider with your own key.
        Outlay connects <b>read-only</b> to your work tracker (Jira / Linear / GitHub) and your
        provider's usage/admin APIs, and reads usage metadata only. There is nothing for us to see in
        your traffic because we are not in it. (An optional, opt-in enforcement gateway exists for hard
        budget caps — it is the only component that ever sits in your request path, it is entirely
        opt-in, and it fails open.)</p></div>

    {card("What never leaves your environment",
          li("<b>Prompt text &amp; model outputs.</b> We never receive request or response bodies."),
          li("<b>Your API keys.</b> Your provider key stays on your side and calls the model directly."),
          li("<b>Customer / PII data.</b> Anything inside a prompt stays inside your boundary."),
          note="Our ingestion endpoints <b>reject any payload</b> that contains prompt text, model "
               "outputs, or secret-looking keys (HTTP 422) — the boundary is enforced, not just promised.")}

    {card("What Outlay sees — metadata only",
          li("A <b>task category</b> and numeric features (token counts, status flags)."),
          li("The <b>ticket / branch identifier</b> the work belongs to (e.g. <code>PROJ-123</code>)."),
          li("Per-request <b>cost</b> figures from your provider's usage data — dollars and counts, never content."))}

    {card("Access control &amp; auditability",
          li("<b>SSO (OIDC)</b>, email-domain routed, and <b>SCIM 2.0</b> provisioning/de-provisioning."),
          li("<b>Two-factor authentication</b> and <b>role-based access</b> (owner / admin / member)."),
          li("A full <b>audit log</b> of privileged actions, with <b>export to your SIEM</b> (CSV)."),
          li("Scoped, expiring, <b>one-time-revealed</b> API keys."))}

    {card("Data handling, isolation &amp; exit",
          li("<b>Per-deployment isolation</b> — your metadata is scoped to your deployment."),
          li("<b>Configurable retention</b> (keep, or auto-purge after 30 / 90 / 180 / 365 days) and "
             "<b>self-serve erasure</b> of ingested data or your entire account."),
          li("<b>Leave anytime</b> — removing Outlay changes nothing about how your calls are made; "
             "we were never in the path."))}

    {card("Accessibility (Section 508 / WCAG 2.1 AA)",
          li("The console is built to <b>WCAG 2.1 AA / Section 508</b>, with an <b>automated "
             "accessibility gate in CI</b> (programmatic names on every control, image alt text, "
             "page language + title) plus manual keyboard/screen-reader and axe-core spot-checks. "
             "A <b>VPAT / ACR</b> (self-assessment; independent validation on the roadmap) is "
             "available for your review (covering WCAG 2.1 AA, Section 508, and Maryland Nonvisual "
             "Access / NTIAA)."))}

    {card("AI transparency &amp; model use",
          li("<b>Where AI is used.</b> Outlay uses a model only to <b>classify work into task "
             "categories</b> (e.g. bug / feature / refactor) from ticket titles and labels you already "
             "have. It does <b>not</b> make consequential decisions about people."),
          li("<b>No training on your data.</b> Your metadata is never used to train or fine-tune any "
             "model, and is never shared with a model provider for training."),
          li("<b>Explainable &amp; overridable.</b> Every classification and cost figure is shown with "
             "the evidence behind it (the ticket, the token counts, the pricing) and can be "
             "<b>reviewed and corrected by a human</b> — no opaque automated scoring."),
          li("<b>Metadata only.</b> The model sees task categories and identifiers, never prompt "
             "content, model outputs, citizen/PII data, or your keys."),
          note="Aligned with the <b>NIST AI Risk Management Framework</b> and state responsible-AI "
               "guidance (e.g. Maryland's Executive Order on AI and DoIT's Responsible AI policy): "
               "transparency about where AI is used, no training on customer data, and human oversight "
               "of every output.")}

    <div class=note style="margin-top:16px"><b>Certifications — the honest part.</b> The data-flow
      guarantee above is a property of the <b>architecture</b> and is independently verifiable. We are
      <b>not yet SOC&nbsp;2 or HIPAA certified</b>, and we won't claim what we don't hold. For a
      <b>BAA</b>, a completed security questionnaire, or our compliance roadmap, email
      <a href="mailto:hello@outlay-ai.com?subject=Outlay%20security%20review">hello@outlay-ai.com</a> —
      we'll share exactly where we are and walk a reviewer through the data-flow boundary.</div>

    <p class=muted style="font-size:12.5px;margin-top:16px">Tip: use your browser's <b>Print</b>
      (⌘/Ctrl-P) to save this page as a PDF for your records.</p>
    """
    return page("Security &amp; compliance", body, account, "/app/security")


def vpat_page(account: dict) -> str:
    """A concise, printable VPAT/ACR summary (WCAG 2.1 AA · §508 · Maryland NTIAA).
    The full signed ACR is available on request; this is the in-product readout."""
    def row(criterion, level, conformance):
        return (f'<tr><td>{_e(criterion)}</td><td>{_e(level)}</td>'
                f'<td><b style="color:var(--grn-d)">{_e(conformance)}</b></td></tr>')
    rows = "".join([
        row("WCAG 2.1 Level A", "A", "Supports"),
        row("WCAG 2.1 Level AA", "AA", "Supports"),
        row("Section 508 (Revised 2017)", "—", "Supports"),
        row("Maryland Nonvisual Access (NTIAA / COMAR)", "—", "Supports"),
    ])
    body = f"""
    <h1>VPAT / Accessibility Conformance Report</h1>
    <p class=muted style="max-width:74ch">Outlay's console is built to <b>WCAG 2.1 AA</b> and
      <b>Section 508</b>, and supports Maryland's <b>Nonvisual Access (NTIAA)</b> requirements. An
      <b>automated accessibility gate in CI</b> checks programmatic naming, image alt text, and page
      language/title on every release; keyboard operability, focus order, contrast, and
      screen-reader labeling are verified with manual + axe-core spot-checks. This is the in-product
      summary (self-assessment; independent third-party validation on the roadmap) — the full ACR
      (VPAT 2.5 format) is available from
      <a href="mailto:hello@outlay-ai.com?subject=Outlay%20VPAT">hello@outlay-ai.com</a>.</p>
    <div class=card style="padding:0;margin-top:16px"><table>
      <thead><tr><th>Standard</th><th>Level</th><th>Conformance</th></tr></thead>
      <tbody>{rows}</tbody></table></div>
    <p class=muted style="font-size:12.5px;margin-top:14px">Print (⌘/Ctrl-P) to save as PDF.</p>"""
    return page("VPAT / ACR", body, account, "/app/security")


def ai_card_page(account: dict) -> str:
    """AI model & system card + Acceptable Use Policy — the transparency artifact
    procurement asks for under NIST AI RMF and Maryland's AI Governance Act / federal
    M-26-04 (model/system/data cards + AUP)."""
    def sect(title, *paras):
        ps = "".join(f"<p style='margin:6px 0;font-size:14px'>{p}</p>" for p in paras)
        return f'<div class=ocard style="margin-top:16px"><div class=dh>{title}</div>{ps}</div>'
    body = f"""
    <h1>AI model &amp; system card + Acceptable Use Policy</h1>
    <p class=muted style="max-width:74ch">How Outlay uses AI, what it does and doesn't do, and the
      acceptable-use terms — aligned to the <b>NIST AI Risk Management Framework</b>, Maryland's
      <b>AI Governance Act</b>, and federal <b>OMB M-26-04</b> (model/system/data cards + AUP).</p>
    {sect("Purpose &amp; scope",
          "Outlay uses a model only to <b>classify a unit of work into a task category</b> "
          "(e.g. bug / feature / refactor) from ticket titles and labels you already have, and to "
          "phrase short explanations. It does <b>not</b> make consequential decisions about people, "
          "benefits, eligibility, or rights.")}
    {sect("Data card — what the model sees",
          "<b>Inputs:</b> task categories, ticket/branch identifiers, token counts, dollar figures — "
          "<b>metadata only</b>. <b>Never:</b> prompt text, model outputs, PII/PHI/citizen data, or "
          "your API keys (these never leave your environment by architecture).",
          "<b>No training on your data:</b> your metadata is never used to train or fine-tune any "
          "model and is never shared with a provider for training.")}
    {sect("System card — model use &amp; oversight",
          "Outlay calls third-party foundation models via the customer's own keys; it does not host or "
          "fine-tune models. Every classification and cost figure is <b>explainable</b> (shown with the "
          "evidence behind it) and <b>human-reviewable and correctable</b> — no opaque automated scoring.",
          "Measured accuracy is reported in-product (leave-one-out back-test on your own data); the "
          "system fails safe and degrades to showing raw metadata if a model is unavailable.")}
    {sect("Acceptable Use Policy",
          "Outlay is for <b>cost attribution, forecasting, and budget governance of AI/LLM spend</b>. "
          "It must not be used to make automated decisions about individuals, to process regulated "
          "data it is not designed for, or to circumvent your own AI-use policies. Misuse, or feeding "
          "it prohibited data, is a breach of these terms.",
          "Feedback / concerns: <a href='mailto:hello@outlay-ai.com?subject=Outlay%20AI%20card'>"
          "hello@outlay-ai.com</a>.")}
    <p class=muted style="font-size:12.5px;margin-top:14px">Print (⌘/Ctrl-P) to save as PDF.</p>"""
    return page("AI model &amp; system card", body, account, "/app/security")


def _settings_group(title: str, *cards: str) -> str:
    """A labeled settings group; hides itself entirely when every card is empty
    (so role-gated sections don't leave a dangling header)."""
    inner = "".join(c for c in cards if c and c.strip())
    if not inner:
        return ""
    return (f'<div style="font-family:var(--mono,monospace);font-size:11.5px;font-weight:600;'
            f'letter-spacing:.1em;text-transform:uppercase;color:var(--mut);margin:30px 0 0">{title}</div>'
            f'{inner}')


def _retention_section(account: dict, retention_days: int = 0, purged: bool = False,
                       purge_error: bool = False) -> str:
    """Data retention window + on-demand erasure of ingested spend data — owner only.
    A standard enterprise procurement / DPA requirement (data minimization)."""
    if account.get("team_role") != "owner":
        return ""
    opts = [(0, "Keep forever"), (30, "30 days"), (90, "90 days"),
            (180, "180 days"), (365, "1 year")]
    sel = "".join(f'<option value="{d}"{" selected" if d == (retention_days or 0) else ""}>{label}</option>'
                  for d, label in opts)
    purged_note = ('<div class="note" role=status>Ingested spend data wiped.</div>' if purged else "")
    perr = ('<div class="note warn" role=status>Type <b>delete</b> to confirm.</div>' if purge_error else "")
    return f"""
    <div class=card style="margin-top:16px" id=retention>
      <div class=label>Data retention</div>
      <p class="small muted" style="margin:.2em 0 .8em">How long Outlay keeps your spend-history
        snapshots. Older snapshots are purged automatically; your current report and connection are
        unaffected. (Prompts and raw usage never leave your environment in the first place.)</p>
      {purged_note}
      <form method=post action="/app/retention" style="display:flex;gap:10px;align-items:center">
        <select name=retention_days aria-label="Data retention period" style="padding:7px 10px;border:1px solid var(--line);border-radius:8px">{sel}</select>
        <button class="btn sec sm">Save</button>
      </form>
      <hr style="border:0;border-top:1px solid var(--line);margin:16px 0">
      <div class=label>Erase ingested data</div>
      <p class="small muted" style="margin:.2em 0 .8em">Delete your current spend report and all history
        snapshots now. Your connection stays so you can re-sync. This cannot be undone.</p>
      {perr}
      <form method=post action="/app/outlay/purge" style="display:flex;gap:10px;align-items:center"
            onsubmit="return confirm('Erase all ingested spend data (report + history)? This cannot be undone.')">
        <input name=confirm aria-label="Type delete to confirm erasing data" autocomplete=off placeholder="type: delete"
               style="padding:7px 10px;border:1px solid var(--line);border-radius:8px">
        <button class="btn sec sm" style="color:#b00020;border-color:#e3b3b3">Erase data</button>
      </form>
    </div>"""


def _digest_section(account: dict) -> str:
    """Toggle the scheduled emails: the weekly spend digest (on by default) and the
    monthly business close pack (opt-in, with the FOCUS CSV attached)."""
    on = account.get("digest_weekly", 1) in (1, True, "1")
    cp = account.get("close_pack_monthly", 0) in (1, True, "1")
    checked = " checked" if on else ""
    cp_checked = " checked" if cp else ""
    return f"""
    <div class=card style="margin-top:16px" id=digest>
      <div class=label>Scheduled emails</div>
      <p class="small muted" style="margin:.2em 0 .8em">Sent to the account owner
        ({_e(account.get("email", ""))}).</p>
      <form method=post action="/app/digest">
        <label style="display:flex;gap:8px;align-items:flex-start;font-size:14px;cursor:pointer;margin-bottom:10px">
          <input type=checkbox name=weekly value=1{checked} style="margin-top:3px">
          <span><b>Weekly spend digest</b><br><span class="small muted">A short Monday email — total AI
          spend and the week-over-week trend, top team &amp; work type, budget status, runaway tickets.
          Also posted to <b>Slack/Teams</b> when a webhook is connected.</span></span></label>
        <label style="display:flex;gap:8px;align-items:flex-start;font-size:14px;cursor:pointer;margin-bottom:12px">
          <input type=checkbox name=close_pack value=1{cp_checked} style="margin-top:3px">
          <span><b>Monthly business close pack</b><br><span class="small muted">A month-end email with the
          period summary and the <b>FOCUS-aligned CSV attached</b> — the artifact you load into the books /
          your FinOps tool — plus a link to the printable close report.</span></span></label>
        <button class="btn sec sm">Save</button>
      </form>
    </div>"""


def _profile_section(account: dict) -> str:
    """Your display name — shown in the nav and across the product. Available to every
    signed-in principal (owner or member); blank falls back to the email alias."""
    # The member's own name when signed in as a member; otherwise the owner's.
    if account.get("member_id"):
        current = (account.get("member_name") or "").strip()
    else:
        current = (account.get("name") or "").strip()
    alias = (account.get("display_email") or account.get("email") or "").split("@")[0]
    return f"""
    <div class=card style="margin-top:16px" id=profile>
      <div class=label>Your name</div>
      <p class="small muted" style="margin:.2em 0 .8em">Shown in the top navigation and across Outlay.
        Leave blank to use your email alias (<b>{_e(alias)}</b>).</p>
      <form method=post action="/app/profile" style="display:flex;gap:10px;align-items:center">
        <input name=name value="{_e(current)}" aria-label="Your display name" maxlength=120
               placeholder="Jane Doe"
               style="flex:1;padding:7px 10px;border:1px solid var(--line);border-radius:8px">
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
          <input name=confirm_email type=email aria-label="Type your email to confirm account deletion" autocomplete=off placeholder="{email}" required></div>
        <div class=field><label>What made you leave? <span class="small muted">(optional, helps us a lot)</span></label>
          <textarea name=reason aria-label="Reason for leaving (optional)" rows=2 placeholder="e.g. savings weren't enough / too hard to set up / quality concern"></textarea></div>
        <button class=btn style="background:#b00020;border-color:#b00020">Delete my account</button>
      </form>
    </div>"""


def _api_keys_section(keys: list[dict], deployments: list[dict], new_key: str = "",
                      from_page: str = "") -> str:
    reveal = ""
    # Where the create/revoke POSTs should send the user back to (Configuration by
    # default; the API reference when the section is embedded there).
    ret = f'<input type=hidden name=from value="{_e(from_page)}">' if from_page else ""
    if new_key:
        reveal = (f'<div class="note"><b>Your new API key (shown once — copy it now):</b><br>'
                  f'<code style="word-break:break-all">{_e(new_key)}</code></div>')
    now = time.time()
    rows = ""
    for k in keys:
        revoked = bool(k.get("revoked_at"))
        exp = k.get("expires_at")
        expired = bool(exp) and exp <= now and not revoked
        if revoked:
            status = '<span class="badge suspended">revoked</span>'
        elif expired:
            status = '<span class="badge suspended">expired</span>'
        else:
            status = '<span class="badge paid">active</span>'
        last = _fmt_date(k["last_used_at"]) if k.get("last_used_at") else "never"
        expires = ("—" if not exp else
                   ('<span style="color:var(--red)">' + _fmt_date(exp) + '</span>' if expired
                    else _fmt_date(exp)))
        action = ("" if (revoked or expired) else
                  f'<form method=post action="/app/keys/revoke" style="margin:0">'
                  f'<input type=hidden name=key_id value="{k["id"]}">{ret}'
                  f'<button class="btn sec sm">Revoke</button></form>')
        rows += (f"<tr><td>{_e(k.get('name') or 'key')}</td>"
                 f"<td><code>{_e(k['prefix'])}…</code></td><td>{status}</td>"
                 f"<td class='small muted'>{last}</td><td class='small muted'>{expires}</td>"
                 f"<td>{action}</td></tr>")
    dep_opts = "".join(f'<option value="{_e(d["deployment_id"])}">{_e(d.get("label") or d["deployment_id"])}</option>'
                       for d in deployments)
    exp_opts = ('<option value="0">No expiry</option><option value="30">Expires in 30 days</option>'
                '<option value="90">90 days</option><option value="180">180 days</option>'
                '<option value="365">1 year</option>')
    table = (f'<div class=card style="padding:0"><table><thead><tr><th>Name</th><th>Key</th>'
             f'<th>Status</th><th>Last used</th><th>Expires</th><th></th></tr></thead>'
             f'<tbody>{rows}</tbody></table></div>'
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
        <input name=name aria-label="API key name" placeholder="key name (e.g. prod)" style="max-width:200px">
        <select name=deployment_id aria-label="Deployment for this key">{dep_opts}</select>
        <select name=expires_in_days aria-label="API key expiry" title="Set an expiry for rotating keys">{exp_opts}</select>{ret}
        <button class=btn>Create API key</button>
      </form>
    </div>"""


def _webhooks_section(webhooks: list[dict], deliveries: list[dict] | None = None) -> str:
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
    log = _webhook_delivery_log(deliveries)
    return f"""
    <h2>Webhooks</h2>
    <p class="small muted">Get notified of events (budget thresholds, tuning proposals, account
    changes). We POST JSON signed with <code>X-Outlay-Signature: sha256=…</code> (HMAC of the body
    with the webhook's signing secret). Failed deliveries are retried with backoff and logged below.</p>
    {table}
    <div class=card style="margin-top:12px">
      <form method=post action="/app/webhooks" class=row style="gap:8px">
        <input name=url aria-label="Webhook URL" placeholder="https://your-app.com/hooks/outlay" style="min-width:280px">
        <select name=events aria-label="Webhook events">
          <option value="all">all events</option>{opts}
        </select>
        <button class=btn>Add webhook</button>
      </form>
    </div>
    {log}"""


def _webhook_delivery_log(deliveries: list[dict] | None) -> str:
    """Recent delivery outcomes, so a dropped webhook is visible instead of silent."""
    if not deliveries:
        return ""
    rows = ""
    for d in deliveries:
        status = d.get("status")
        ok = status == "delivered"
        badge = {"delivered": '<span class="badge paid">delivered</span>',
                 "dead": '<span class="badge suspended">gave up</span>'}.get(
                     status, '<span class="badge suspended">retrying</span>')
        code = d.get("status_code")
        detail = (f"HTTP {code}" if code else "") + (
            f" · {_e(d.get('error') or '')}" if (not ok and d.get("error")) else "")
        att = d.get("attempts") or 1
        rows += (f"<tr><td class='small muted'>{_fmt_date(d.get('created_at'))}</td>"
                 f"<td><span class='otag ex'>{_e(d.get('event_type') or '')}</span></td>"
                 f"<td>{badge}</td><td class='small muted'>{att} attempt{'s' if att != 1 else ''}</td>"
                 f"<td class='small muted'>{detail}</td></tr>")
    return (f'<h3 style="margin-top:18px">Recent deliveries</h3>'
            f'<div class=card style="padding:0"><table><thead><tr><th>When</th><th>Event</th>'
            f'<th>Status</th><th>Tries</th><th>Detail</th></tr></thead><tbody>{rows}</tbody></table></div>')


_FOCUS_FIELD_DOCS = [
    ("BilledCost / EffectiveCost", "Attributed spend for the charge row (USD)."),
    ("BillingCurrency", "Always USD today."),
    ("ChargePeriodStart / End", "The window the charge covers (your report's lookback)."),
    ("ServiceCategory / ServiceName", '"AI and Machine Learning" / "LLM API".'),
    ("ChargeCategory", '"Usage".'),
    ("ResourceId / ResourceName", "The ticket / work item the spend is attributed to."),
    ("Tags", 'JSON: {"team": …, "work_type": …} — your cost-center + work-type allocation.'),
]


def api_page(account: dict, keys: list[dict], deployments: list[dict],
             base_url: str = "", new_key: str = "") -> str:
    """Developer reference for the read-only spend API + exports. Makes the BI/
    warehouse endpoint discoverable and copy-paste usable, with the customer's own
    key-management inline. Owner/admin only (keys are sensitive)."""
    base = (base_url or "https://app.outlay-ai.com").rstrip("/")
    sample_key = "mp_live_…"
    if keys:
        # Show their real prefix in the examples so copy-paste needs only the secret.
        sample_key = (keys[0].get("prefix") or "mp_live_") + "…"
    cols = "".join(f"<tr><td><code>{_e(name)}</code></td><td class='small muted'>{_e(desc)}</td></tr>"
                   for name, desc in _FOCUS_FIELD_DOCS)
    curl = (f"curl -s {base}/api/v1/spend \\\n"
            f"  -H 'Authorization: Bearer {sample_key}'")
    curl_audit = (f"curl -s '{base}/api/v1/audit?since=0&limit=1000' \\\n"
                  f"  -H 'Authorization: Bearer {sample_key}'")
    resp_audit = ('{\n'
                  '  "account_id": 42,\n'
                  '  "next_since": 1841,\n'
                  '  "count": 2,\n'
                  '  "events": [\n'
                  '    {"id": 1840, "ts": "2026-06-20T14:02:11+00:00", "actor": "cfo@acme.com",\n'
                  '     "action": "login", "detail": ""},\n'
                  '    {"id": 1841, "ts": "2026-06-20T14:05:39+00:00", "actor": "cfo@acme.com",\n'
                  '     "action": "connection.save", "detail": "tracker=github"}\n'
                  '  ]\n'
                  '}')
    resp = ('{\n'
            '  "account_id": 42,\n'
            '  "period": {"start": "2026-05-21T00:00:00+00:00",\n'
            '             "end":   "2026-06-20T00:00:00+00:00"},\n'
            '  "currency": "USD",\n'
            '  "total_usd": 4821.55,\n'
            '  "rows": [\n'
            '    {"BilledCost": 312.40, "EffectiveCost": 312.40, "BillingCurrency": "USD",\n'
            '     "ServiceCategory": "AI and Machine Learning", "ServiceName": "LLM API",\n'
            '     "ChargeCategory": "Usage", "ResourceId": "PLAT-1284",\n'
            '     "Tags": "{\\"team\\": \\"platform\\", \\"work_type\\": \\"feature\\"}"}\n'
            '  ]\n'
            '}')
    body = f"""
    <h1>API &amp; data export</h1>
    <p class=muted style="max-width:62ch">Pull your attributed AI spend into a data warehouse, BI tool, or a
    script — read-only, and the same numbers you see in the console. Rows use
    <a href="https://focus.finops.org/" target=_blank rel=noopener>FOCUS</a> (the FinOps Open Cost &amp;
    Usage Spec) column names, so they load into any FOCUS-aware tool.</p>

    <div class=card>
      <h2 style="margin-top:0">Authentication</h2>
      <p class="small muted">Create a key below, then send it as a bearer token on every request. Keys are
      shown once, hashed at rest, and revocable. The <code>x-modelpilot-key: &lt;key&gt;</code> header works too.</p>
      <p class="small muted">Requests are rate-limited per key; over the limit returns <code>429</code> with a
      <code>Retry-After</code> header. The data refreshes on your sync cadence, so polling faster than that
      adds nothing — once a day (or after a sync) is plenty.</p>
    </div>

    <div class=card style="margin-top:16px">
      <h2 style="margin-top:0"><code>GET /api/v1/spend</code></h2>
      <p class="small muted">The latest report as FOCUS-aligned charge rows (one per attributed ticket),
      plus the period and total.</p>
      <pre>{_e(curl)}</pre>
      <p class="small muted" style="margin-bottom:6px"><b>Response</b></p>
      <pre>{_e(resp)}</pre>
      <p class="small muted" style="margin-top:14px;margin-bottom:6px"><b>Row fields</b></p>
      <div class=card style="padding:0"><table><thead><tr><th>Field</th><th>Meaning</th></tr></thead>
        <tbody>{cols}</tbody></table></div>
      <p class="small muted" style="margin-top:12px">Returns <code>401</code> if the key is missing, invalid,
      or revoked. Before your first sync the response is a valid empty shape
      (<code>total_usd: 0, rows: []</code>).</p>
    </div>

    <div class=card style="margin-top:16px">
      <h2 style="margin-top:0"><code>GET /api/v1/audit</code></h2>
      <p class="small muted">Your security audit trail (sign-ins, connection &amp; team changes) for SIEM
      ingestion — Splunk, Datadog, etc. Events come in ascending <code>id</code> order; poll with
      <code>?since=&lt;next_since&gt;</code> to fetch only new events, gap-free. <code>?limit=</code> caps at 5000.</p>
      <pre>{_e(curl_audit)}</pre>
      <p class="small muted" style="margin-bottom:6px"><b>Response</b></p>
      <pre>{_e(resp_audit)}</pre>
    </div>

    <div class=card style="margin-top:16px">
      <h2 style="margin-top:0"><code>GET /api/v1/data-quality</code></h2>
      <p class="small muted">A lightweight trust verdict — ticket coverage, invoice reconciliation, pricing
      fidelity, and data freshness rolled into one <code>good</code> / <code>fair</code> / <code>poor</code>
      score (no rows). Gate a pipeline or alert a monitor on data confidence.</p>
      <pre>{{
  "account_id": 42,
  "score": "fair",
  "checks": [
    {{"key": "coverage",       "label": "Ticket coverage",      "status": "good", "detail": "…"}},
    {{"key": "reconciliation", "label": "Invoice reconciliation","status": "fair", "detail": "…"}},
    {{"key": "pricing",        "label": "Pricing fidelity",     "status": "good", "detail": "…"}},
    {{"key": "freshness",      "label": "Data freshness",       "status": "good", "detail": "…"}}
  ]
}}</pre>
      <p class="small muted">The same block is embedded in <code>/api/v1/spend</code> under
      <code>data_quality</code>.</p>
    </div>

    <div class=card style="margin-top:16px">
      <h2 style="margin-top:0"><code>GET /api/v1/enforcement</code></h2>
      <p class="small muted">The hard-cap decision the opt-in <b>gateway</b> consults for
      <a href="/app/outlay/programs">program budgets</a>. Returns the programs currently over their
      <code>hard</code> cap so the in-path client can cache it and match each call's attribution tags
      (team / project / work type) to a member scope locally. Pass <code>?ticket=&amp;team=&amp;work_type=</code>
      to also resolve a single call.</p>
      <pre>{{
  "account_id": 42,
  "enforced": [
    {{"name": "Platform", "action": "downgrade", "floor_model": "claude-haiku-4-5",
     "members": [{{"scope_type": "team", "scope_id": "platform"}}],
     "projected_usd": 61000, "limit_usd": 50000}}
  ],
  "decision": {{"decision": "downgrade", "program": "Platform", "floor_model": "claude-haiku-4-5"}}
}}</pre>
      <p class="small muted">Read-only: Outlay returns the verdict; the gateway enforces on the traffic.
      Programs set to <b>alert only</b> never appear here — they fire a <code>program.over</code> webhook instead.</p>
    </div>

    <div class=card style="margin-top:16px">
      <h2 style="margin-top:0">CSV exports</h2>
      <p class="small muted">Prefer a file? Download from the Spend page, or link directly (these need a
      signed-in session, not an API key):</p>
      <ul class="small">
        <li><a href="/app/outlay/export.focus.csv">/app/outlay/export.focus.csv</a> — FOCUS rows (same as the API).</li>
        <li><a href="/app/outlay/export.csv?view=tickets">/app/outlay/export.csv?view=tickets</a> — spend per ticket.</li>
        <li><code>?view=</code> also accepts <code>classes</code>, <code>people</code>, <code>models</code>, <code>savings</code>.</li>
      </ul>
    </div>

    {_api_keys_section(keys or [], deployments, new_key, from_page="api")}
    """
    return page("API", body, account, "/app/api")


def connect_page(account: dict, deployments: list[dict], brain_url: str, console_url: str,
                 keys: list[dict] | None = None, new_key: str = "",
                 webhooks: list[dict] | None = None,
                 deliveries: list[dict] | None = None) -> str:
    dep = deployments[0]["deployment_id"] if deployments else "—"
    dep_rows = ""
    for d in deployments:
        dep_rows += f"""<tr>
          <td><code>{_e(d['deployment_id'])}</code></td>
          <td><form method=post action="/app/deployments/rename" class=row style="gap:6px">
            <input type=hidden name=deployment_id value="{_e(d['deployment_id'])}">
            <input name=label aria-label="Deployment label" value="{_e(d.get('label') or '')}" style="padding:6px;max-width:200px">
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
        <input name=label aria-label="New deployment label" placeholder="e.g. production-api" style="max-width:240px">
        <button class=btn>Add deployment</button>
      </form>
    </div>
    {_api_keys_section(keys or [], deployments, new_key)}
    {_webhooks_section(webhooks or [], deliveries)}
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
        <div class=field><label>Email domain</label><input name=domain aria-label="Email domain" value="{v('domain')}" placeholder="yourdomain.com"></div>
        <div class=field><label>Default role for new users</label><select name=default_role aria-label="Default role for new users">{role_opts}</select></div>
        <div class=field><label>Client ID</label><input name=client_id aria-label="OIDC client ID" value="{v('client_id')}"></div>
        <div class=field><label>Client secret</label><input name=client_secret aria-label="OIDC client secret" type=password value="{v('client_secret')}"></div>
        <div class=field><label>Authorization URL</label><input name=auth_url aria-label="Authorization URL" value="{v('auth_url')}" placeholder="https://idp/authorize"></div>
        <div class=field><label>Token URL</label><input name=token_url aria-label="Token URL" value="{v('token_url')}" placeholder="https://idp/token"></div>
        <div class=field><label>Userinfo URL</label><input name=userinfo_url aria-label="Userinfo URL" value="{v('userinfo_url')}" placeholder="https://idp/userinfo"></div>
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
              sso: dict | None = None, scim_token: str = "", roster: str = "") -> str:
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
        <label class=fld style="flex:1;min-width:220px"><span>Work email</span>
          <input name=email type=email placeholder="teammate@company.com" required></label>
        <label class=fld style="min-width:140px"><span>Access</span>
          <select name=role>{role_opts}</select></label>
        <label class=fld style="min-width:150px"><span>Experience</span>
          <select name=persona><option value="">Let them choose</option>
            <option value="business">Business leader</option>
            <option value="eng">Engineering leader</option></select></label>
        <button class=btn>Send invite</button>
      </form>
      <div class=rolelegend>
        <span><b>admin</b> — full access, including team &amp; billing</span>
        <span><b>billing</b> — dashboards + billing</span>
        <span><b>member</b> — dashboards, logs &amp; connect (read-only)</span>
      </div>
      <p class=muted style="font-size:12.5px;margin-top:6px">They'll get a link to set a password and sign in.</p>
    </div>"""
    roster_note = (f'<div class=okbox style="margin-bottom:16px">{_e(roster)}</div>' if roster else "")
    directory = _org_directory(account, members) or members_card
    # Engineering manages direct reports (with job titles); business does not upload an org.
    upload = "" if (account.get("persona") or "").lower() == "business" else _org_upload_form(kind="title")
    body = (head + invite_note + roster_note + directory
            + upload + invite_card + _sso_section(sso or {}, scim_token))
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
          <input name=email type=email aria-label="Email address" required value="{_e(email)}" placeholder="you@company.com"></div>
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
          <input name=password type=password aria-label="Password" required minlength=8 placeholder="At least 8 characters"></div>
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
    # Not-started trials are entitled but not counting down — don't show a full
    # "Nd left" countdown (that contradicts the "starts at setup" copy below).
    if is_paid:
        status_badge = '<span class="badge paid">Active plan</span>'
    elif trial.get("not_started"):
        status_badge = '<span class="badge trial">Trial · starts at setup</span>'
    elif trial["active"]:
        status_badge = f'<span class="badge trial">Trial · {trial["days_left"]}d left</span>'
    else:
        status_badge = '<span class="badge suspended">Trial ended</span>'
    flash_html = ""
    if flash == "success":
        flash_html = '<div class="note" role=status>Your plan is active — thanks!</div>'
    elif flash == "cancel":
        flash_html = '<div class="note warn" role=status>No changes made.</div>'
    elif flash == "converted":
        flash_html = '<div class="note" role=status>Plan activated.</div>'
    if not is_paid and not trial["active"]:
        flash_html = ('<div class="note bad"><b>Your free trial has ended.</b> '
                      '<a href="mailto:hello@outlay-ai.com?subject=Outlay%20plan">Talk to us</a> to '
                      'continue on a plan.</div>' + flash_html)

    if is_paid:
        plan_line = ('<p>Your plan is <b>active</b>, on the terms set out in your Outlay order form '
                     'or agreement.</p>')
    elif trial.get("not_started"):
        plan_line = (f'<p>Your <b>{store.TRIAL_DAYS}-day free trial</b> starts when you connect your data and '
                     'run your first sync — the clock only runs while you\'re evaluating.</p>')
    elif trial["active"]:
        plan_line = (f'<p>You\'re on the free trial — <b>{trial["days_left"]} days left</b>. Your first '
                     'weeks are free; we\'ll scope ongoing pricing with you before anything is charged.</p>')
    else:
        plan_line = '<p>Your free trial has ended.</p>'
    body = f"""
    <div class=row><h1>Billing &amp; plan</h1><div class=spacer></div>{status_badge}</div>
    {flash_html}
    <div class=card>
      {plan_line}
      <p class="small muted">Outlay's pricing is scoped to your usage and set with you — there are no
      self-serve tiers here. Your plan and fees are governed by your Outlay order form or written
      agreement.</p>
      <p style="margin-top:14px"><a class=btn href="mailto:hello@outlay-ai.com?subject=Outlay%20pricing%20consultation">Book a pricing consultation →</a></p>
    </div>
    <div class=card style="margin-top:16px">
      <div class=label>How pricing works</div>
      <p class="small muted">We scope pricing to your AI spend, team size, and how much you want to
      govern — agreed in a short consultation before you're charged. No prompt content is ever used in
      billing; figures come from usage metadata only.</p>
    </div>"""
    return page("Billing", body, account, "/app/billing")


# --------------------------------------------------------------------------- #
# Admin
# --------------------------------------------------------------------------- #

def _feedback_widget() -> str:
    return ('<div class=card style="margin-top:16px"><div class=label>Feedback &amp; feature requests</div>'
            '<form method=post action="/app/feedback" class=row '
            'style="gap:8px;flex-wrap:wrap;align-items:center;margin-top:8px">'
            '<select name=kind aria-label="Type" '
            'style="padding:9px 10px;border:1px solid var(--line);border-radius:8px;background:#fff;font-size:14px">'
            '<option value=idea>&#128161; Feature request</option>'
            '<option value=problem>&#128030; Something&#39;s broken</option>'
            '<option value=praise>&#128077; What&#39;s working</option>'
            '<option value=other>&#128172; Other</option></select>'
            '<input name=comment aria-label="Your feedback" required placeholder="What would make Outlay better?" '
            'style="flex:1;min-width:220px;padding:8px 10px;border:1px solid var(--line);border-radius:8px">'
            '<button class="btn sm">Send</button></form>'
            '<p class="small muted" style="margin-top:6px">Goes straight to the founder — just your note, '
            'never any prompt content. We read every one.</p></div>')


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


def _value_funnel_panel(vf: dict | None) -> str:
    """Outlay time-to-value funnel: signed up → connected → synced → first attributed
    dollar. The metric that matters is the last gap — the target is 'first attributed
    dollar within 24h of signup'. Also lists stalled accounts so the founder knows who
    to nudge (this is the pilot-conversion instrument, not vanity analytics)."""
    if not vf:
        return ""
    import time as _time
    s = vf.get("summary") or {}
    su = s.get("signed_up") or 1
    stages = [("Signed up", s.get("signed_up", 0)), ("Connected a source", s.get("connected", 0)),
              ("Synced", s.get("synced", 0)), ("First attributed $", s.get("attributed", 0))]
    cells = "".join(
        f'<div style="text-align:center;min-width:96px"><div class=stat>{n}</div>'
        f'<div class="small muted">{_e(lbl)}<br>{round(100*n/su)}%</div></div>'
        for lbl, n in stages)
    med = s.get("median_ttv_hours")
    tgt = (f'<div style="text-align:center;min-width:120px"><div class=stat>'
           f'{s.get("within_24h", 0)}/{s.get("attributed", 0)}</div>'
           f'<div class="small muted">hit &lt;24h target'
           + (f'<br>median {med}h' if med is not None else '') + '</div></div>')

    # Who to nudge: signed up but never connected (>48h), or connected but no
    # attributed dollar yet (>24h). Demo accounts are badged, not hidden.
    now = _time.time()
    stalled = []
    for r in (vf.get("rows") or []):
        created = r.get("created_at") or now
        demo = ' <span class="badge trial">demo</span>' if r.get("demo_mode") else ""
        if not r.get("connected_at") and now - created > 48 * 3600:
            stalled.append(f'<li>{_e(r["email"])}{demo} — signed up '
                           f'{(now - created) / 86400:.0f}d ago, <b>never connected a source</b></li>')
        elif r.get("connected_at") and not r.get("attributed_at") \
                and now - r["connected_at"] > 24 * 3600:
            stalled.append(f'<li>{_e(r["email"])}{demo} — connected '
                           f'{(now - r["connected_at"]) / 86400:.0f}d ago, '
                           f'<b>no attributed dollar yet</b></li>')
    stalled_html = (f'<p class="small" style="margin-top:10px;margin-bottom:4px"><b>Stalled — '
                    f'worth a nudge:</b></p><ul class="small muted" style="margin:0 0 0 18px">'
                    + "".join(stalled[:8]) + '</ul>') if stalled else \
        '<p class="small muted" style="margin-top:10px">No stalled accounts right now.</p>'
    return ('<h2>Time to value (Outlay)</h2><div class=card>'
            f'<div class=row style="gap:24px;flex-wrap:wrap;align-items:flex-end">{cells}{tgt}</div>'
            f'{stalled_html}'
            '<p class="small muted" style="margin-top:10px">First-time milestones on the real '
            'customer path (demo/sample data never counts). The whole onboarding goal: '
            '<b>first attributed dollar &lt;24h</b> from signup.</p></div>')


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


def _fleet_ktlo_card(fc: dict | None) -> str:
    if not fc:
        return ""
    top = "".join(
        f'<tr><td><a href="/admin/accounts/{r["id"]}">{_e(r["email"])}</a></td>'
        f'<td>{money(r["loaded_monthly"])}/mo</td><td class="small muted">{_e(r["tier_signal"])} · '
        f'{_e(r["primary_driver"])}</td></tr>' for r in fc.get("top", []))
    return (
        '<div class=card style="margin-top:16px"><div class=label>Cost to serve (KTLO) · all customers</div>'
        '<p class="small muted" style="margin:4px 0 10px">What it costs US to run the product. Outlay makes '
        '<b>no LLM calls</b> — cost is infra only (storage + CPU/sync + egress + email), so marginal '
        'cost-to-serve is near-zero; the fixed always-on machine dominates.</p>'
        f'<div style="display:flex;gap:24px;flex-wrap:wrap">'
        f'<div><div class=stat>{money(fc["total_loaded_monthly"])}</div>'
        '<div class="small muted">total loaded / mo</div></div>'
        f'<div><div class=stat>{money(fc["total_marginal_monthly"])}</div>'
        '<div class="small muted">total marginal / mo</div></div>'
        f'<div><div class=stat>{money(fc["avg_loaded_per_account"])}</div>'
        '<div class="small muted">avg / account</div></div>'
        f'<div><div class=stat>{money(fc["fixed_monthly"])}</div>'
        '<div class="small muted">fixed base (machine)</div></div></div>'
        + (f'<table style="margin-top:12px"><thead><tr><th>Most expensive to serve</th><th>Loaded</th>'
           f'<th>Tier · driver</th></tr></thead><tbody>{top}</tbody></table>' if top else '')
        + '</div>')


def admin_overview(account: dict, rev: dict, rows: list[dict], pending: int = 0,
                   funnel: dict | None = None, feedback: list[dict] | None = None,
                   fleet_cost: dict | None = None, value_funnel: dict | None = None) -> str:
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
    {_value_funnel_panel(value_funnel)}
    {_funnel_panel(funnel)}
    {_fleet_ktlo_card(fleet_cost)}
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


def _ago(age_seconds) -> str:
    if age_seconds is None:
        return "never"
    h = age_seconds / 3600
    if h < 1:
        return f"{int(age_seconds // 60)}m ago"
    if h < 48:
        return f"{h:.0f}h ago"
    return f"{h / 24:.0f}d ago"


_CRON_JOB_INFO = {
    "sync-due": ("Auto-sync + staleness alerts", "POST /internal/outlay/sync-due",
                 "Re-syncs connected sources and fires stale-data / repeated-failure alerts."),
    "digest-due": ("Digest · close pack · retention · webhook redelivery",
                   "POST /internal/outlay/digest-due",
                   "Weekly digest, monthly close pack, data-retention purge, durable webhook redelivery."),
}


def _fmt_bytes(n: int) -> str:
    n = float(n or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if n < 1024 or unit == "GB":
            return f"{n:.0f} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} GB"


def _report_storage_card(storage: dict | None) -> str:
    """Surface the JSON-blob scale ceiling: per-account report blobs grow with the
    ticket tail; this makes the largest blob + fleet total visible so we act on the
    real fix (aggregate storage / pagination) before it bites, not after."""
    if not storage:
        return ""
    over = storage.get("over_soft_limit")
    badge = ('<span class="badge suspended">large</span>' if over
             else '<span class="badge paid">ok</span>')
    soft = _fmt_bytes(storage.get("soft_limit_bytes"))
    mx = _fmt_bytes(storage.get("max_bytes"))
    acct_id = storage.get("max_account_id")
    biggest = (f'<a href="/admin/accounts/{acct_id}">account {acct_id}</a>'
               if acct_id is not None else "—")
    note = ('' if not over else
            f'<div class="small muted" style="margin-top:3px">Largest blob is over the '
            f'{soft} soft limit — time to plan aggregate storage / pagination '
            f'(<code>OUTLAY_REPORT_SOFT_LIMIT_BYTES</code> to tune the alert).</div>')
    return (
        '<h2 style="margin-top:26px">Report storage</h2>'
        '<p class=muted style="margin-top:-4px">Each account\'s current report is one JSON blob in '
        'SQLite. Fine today; a ceiling at millions of events/month. Watched here so the fix lands '
        'before it\'s urgent.</p>'
        '<div class=card style="padding:0"><table>'
        '<thead><tr><th>Metric</th><th>Status</th><th>Value</th></tr></thead><tbody>'
        f'<tr><td><b>Largest report blob</b><div class="small muted">soft limit {soft}</div></td>'
        f'<td>{badge}</td><td class="small">{mx} · {biggest}{note}</td></tr>'
        f'<tr><td><b>Stored reports</b></td><td><span class="badge paid">—</span></td>'
        f'<td class="small">{storage.get("count", 0)} reports · {_fmt_bytes(storage.get("total_bytes"))} total</td></tr>'
        '</tbody></table></div>')


def admin_health_page(account: dict, cron: dict, runs: dict, storage: dict | None = None) -> str:
    """Operator view of scheduled-job freshness — a missing/broken cron scheduler is
    the silent failure mode for the digest / close-pack / retention / redelivery
    sweeps, so make 'last run' visible with a clear stale flag. Also surfaces the
    report-blob storage ceiling."""
    any_stale = any(c["stale"] for c in cron.values())
    banner = ("" if not any_stale else
              '<div class=ostrip style="background:var(--red-l)"><span>'
              '<span class="otag over">action</span> '
              '<b style="color:var(--red)">A scheduled job is overdue.</b> '
              'If the scheduler isn\'t hitting these endpoints daily (with <code>OUTLAY_CRON_TOKEN</code>), '
              'digests, the monthly close pack, retention purges, and webhook redelivery silently never run.'
              '</span></div>')
    rows = ""
    for job, c in cron.items():
        label, endpoint, what = _CRON_JOB_INFO.get(job, (job, "", ""))
        badge = ('<span class="badge suspended">stale</span>' if c["stale"]
                 else '<span class="badge paid">ok</span>')
        last = _fmt_date(c["last_run_at"]) if c["last_run_at"] else "—"
        detail = _e((runs.get(job) or {}).get("detail") or "")
        detail = f'<div class="small muted" style="margin-top:3px;word-break:break-all">{detail}</div>' if detail else ""
        rows += (f'<tr><td><b>{_e(label)}</b><br><code class=small>{_e(endpoint)}</code>'
                 f'<div class="small muted">{_e(what)}</div></td>'
                 f'<td>{badge}</td>'
                 f'<td class="small muted">{last}</td>'
                 f'<td class="small muted">{_ago(c["age_seconds"])}{detail}</td></tr>')
    body = (
        '<div class=row><h1>Scheduler health</h1><div class=spacer></div>'
        '<a class="small" href="/admin">← overview</a></div>'
        '<p class=muted>The daily cron drives every background sweep. If a job goes stale, '
        'the scheduler (Fly scheduled machine / external cron) likely stopped hitting it.</p>'
        f'{banner}'
        '<div class=card style="padding:0"><table>'
        '<thead><tr><th>Job</th><th>Status</th><th>Last run</th><th>Age / last result</th></tr></thead>'
        f'<tbody>{rows}</tbody></table></div>'
        '<p class="small muted" style="margin-top:12px">External monitors can poll '
        '<code>GET /api/health</code> — it returns <code>cron_ok</code> and per-job freshness.</p>'
        f'{_report_storage_card(storage)}')
    return page("Scheduler health", body, account, "/admin/health")


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


def _cost_to_serve_card(cost: dict | None, bill: dict | None) -> str:
    """Admin KTLO panel — what it costs US to serve this account, and the cost drivers."""
    if not cost:
        return ""
    d = cost.get("drivers", {})
    tier_col = {"light": "var(--grn-d)", "standard": "var(--amber)", "heavy": "var(--red)"}.get(
        cost.get("tier_signal"), "var(--muted)")

    def line(label, val):
        return (f'<div style="display:flex;justify-content:space-between;font-size:12.5px;margin:2px 0">'
                f'<span class=muted>{label}</span><span>{val}</span></div>')
    rev = (bill or {}).get("would_bill", 0) or 0
    margin = rev - cost["loaded_monthly"] if rev else None
    margin_html = (f'<div style="margin-top:8px;font-size:12.5px">Revenue {money(rev)}/mo · '
                   f'<b style="color:{"var(--grn-d)" if margin and margin >= 0 else "var(--red)"}">'
                   f'margin {money(margin)}</b></div>') if rev else (
                   '<div class=muted style="margin-top:8px;font-size:12px">Free pilot — no revenue yet.</div>')
    return (
        '<div class=ocard style="margin-top:16px"><div class=dh>Cost to serve (KTLO) '
        f'<span class=sub style="color:{tier_col}">{_e(cost.get("tier_signal","?"))} · admin</span></div>'
        '<p class=muted style="font-size:12px;margin:4px 0 10px">No LLM cost — Outlay is deterministic '
        'metadata analytics on BYOK data. Cost = infra (storage + CPU/sync + egress + email).</p>'
        f'<div style="font-size:20px;font-weight:700">{money(cost["loaded_monthly"])}'
        '<span class=muted style="font-size:12px;font-weight:400"> / mo loaded '
        f'({money(cost["marginal_monthly"])} marginal + {money(cost["allocated_fixed_monthly"])} '
        'fixed share)</span></div>'
        f'{line("storage · " + str(cost["storage_mb"]) + " MB", money(cost["cost_storage"]))}'
        f'{line("compute · " + str(cost["syncs_per_month"]) + " syncs/mo", money(cost["cost_compute"]))}'
        f'{line("egress", money(cost["cost_egress"]))}'
        f'{line("email", money(cost["cost_email"]))}'
        '<div style="margin-top:8px;border-top:1px solid var(--line);padding-top:8px">'
        f'{line("drivers", "")}'
        f'<div class=muted style="font-size:11.5px">{d.get("tickets",0):,} tickets · '
        f'{d.get("history_rows",0):,} snapshots · sync {("every " + str(d.get("sync_hours")) + "h") if d.get("sync_hours") else "manual"} · '
        f'retention {d.get("retention_days") or "∞"}d · {d.get("connectors",0)} connectors · '
        f'biggest line: <b>{_e(cost.get("primary_driver","?"))}</b></div></div>'
        f'{margin_html}</div>')


def admin_account_detail(account: dict, target: dict, plan: dict, trial: dict,
                         settings: dict, bill: dict, cats: list[dict],
                         suggestions: list[str], reset_link: str = "",
                         proposals: list[dict] | None = None,
                         history: list[dict] | None = None, cost: dict | None = None) -> str:
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
    <div class=card><ul style="margin:0;padding-left:20px">{sugg}</ul></div>
    {_cost_to_serve_card(cost, bill)}"""
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
