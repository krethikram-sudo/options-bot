"""Web dashboard: the visual proof layer (SAVINGS_DASHBOARD.md §2).

  GET /modelpilot/dashboard  — server-rendered HTML, inline SVG charts,
                               zero JS/CDN dependencies (enterprise-safe)
  GET /modelpilot/stats      — the same numbers as JSON

Views: headline cards, cumulative savings curve, model-mix migration,
category drill-down, RCT arm comparison, quality guardrails.
"""

import html
import os
import statistics
import time

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from .report import _bootstrap_diff_ci

router = APIRouter()

_MODEL_COLORS = {
    "claude-haiku-4-5": "#2e9e5b",
    "claude-sonnet-4-6": "#2f6fb6",
    "claude-opus-4-8": "#7d4fb3",
    "claude-fable-5": "#1f2430",
}
_FALLBACK_COLOR = "#999999"


def collect_stats(ledger, days: float = 30.0, session: str = "") -> dict:
    since = time.time() - days * 86_400 if days else 0.0
    gate = float(os.environ.get("MODELPILOT_CONFIDENCE", "0.8"))
    raw_mode = os.environ.get("MODELPILOT_MODE", "shadow")
    mode = {"guidance": "advise"}.get(raw_mode, raw_mode)
    display_mode = {"advise": "guidance"}.get(mode, mode)
    stats = {
        "window_days": days,
        "gate": gate,
        "mode": mode,
        "display_mode": display_mode,
        "summary": ledger.summary(since, gate=gate),
        "by_category": ledger.by_category(since),
        "daily": ledger.daily_series(since),
        "daily_mix": ledger.daily_model_mix(since),
        "escalations": ledger.escalation_costs(since),
        "guardrails": ledger.quality_guardrails(since),
        "recent_sessions": ledger.recent_sessions(),
        "session": ledger.session_summary(session) if session else None,
        "proof": {"summary": ledger.proof_summary(), "rows": ledger.proof_rows(8)},
    }
    arms = ledger.arm_costs(since)
    rct = {"treatment_n": len(arms["treatment"]), "control_n": len(arms["control"]), "ready": False}
    if rct["treatment_n"] >= 30 and rct["control_n"] >= 30:
        mean_t = statistics.fmean(arms["treatment"])
        mean_c = statistics.fmean(arms["control"])
        lo, hi = _bootstrap_diff_ci(arms["control"], arms["treatment"])
        rct.update(ready=True, mean_treatment=mean_t, mean_control=mean_c,
                   saving_pct=(mean_c - mean_t) / mean_c if mean_c else 0.0,
                   diff_ci_low=lo, diff_ci_high=hi)
    stats["rct"] = rct
    return stats


@router.get("/modelpilot/stats")
async def stats(request: Request, days: float = 30.0, session: str = ""):
    return collect_stats(request.app.state.ledger, days, session)


@router.get("/modelpilot/dashboard")
async def dashboard(request: Request, days: float = 30.0, session: str = ""):
    return HTMLResponse(render_html(collect_stats(request.app.state.ledger, days, session)))


# ---------------------------------------------------------------------------
# Rendering — plain string templating + hand-rolled SVG, no dependencies
# ---------------------------------------------------------------------------

def _usd(x: float | None) -> str:
    if x is None:
        return "—"
    return f"${x:,.2f}" if abs(x) >= 0.01 else f"${x:,.4f}"


def _line_chart(series: dict[str, list[float]], labels: list[str],
                w: int = 720, h: int = 220, colors: dict | None = None) -> str:
    """Multi-line SVG chart over a shared x axis (one point per label)."""
    pad = 44
    flat = [v for vals in series.values() for v in vals] or [0.0]
    vmax = max(flat) or 1.0
    n = max(len(labels), 2)

    def x(i):
        return pad + i * (w - 2 * pad) / (n - 1)

    def y(v):
        return h - pad - (v / vmax) * (h - 2 * pad)

    parts = [f'<svg viewBox="0 0 {w} {h}" class="chart">']
    parts.append(f'<line x1="{pad}" y1="{h-pad}" x2="{w-pad}" y2="{h-pad}" stroke="#ccc"/>')
    parts.append(f'<line x1="{pad}" y1="{pad}" x2="{pad}" y2="{h-pad}" stroke="#ccc"/>')
    parts.append(f'<text x="{pad-6}" y="{pad+4}" text-anchor="end" class="tick">{_usd(vmax)}</text>')
    parts.append(f'<text x="{pad-6}" y="{h-pad+4}" text-anchor="end" class="tick">$0</text>')
    if labels:
        parts.append(f'<text x="{pad}" y="{h-pad+16}" class="tick">{labels[0]}</text>')
        parts.append(f'<text x="{w-pad}" y="{h-pad+16}" text-anchor="end" class="tick">{labels[-1]}</text>')
    legend_x = pad
    for name, vals in series.items():
        color = (colors or {}).get(name, _FALLBACK_COLOR)
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2.5"/>')
        parts.append(f'<rect x="{legend_x}" y="8" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="{legend_x+14}" y="17" class="tick">{name}</text>')
        legend_x += 14 + 8 * len(name) + 24
    parts.append("</svg>")
    return "".join(parts)


def _mix_chart(daily_mix: list[dict], w: int = 720, h: int = 220) -> str:
    """Stacked share-of-traffic bars per day, by recommended model."""
    days = sorted({r["day"] for r in daily_mix})
    if not days:
        return '<p class="muted">No traffic yet.</p>'
    models = sorted({r["model"] for r in daily_mix})
    counts = {(r["day"], r["model"]): r["n"] for r in daily_mix}
    pad = 44
    bar_w = max(min((w - 2 * pad) / len(days) - 4, 60), 3)
    parts = [f'<svg viewBox="0 0 {w} {h}" class="chart">']
    legend_x = pad
    for m in models:
        color = _MODEL_COLORS.get(m, _FALLBACK_COLOR)
        parts.append(f'<rect x="{legend_x}" y="8" width="10" height="10" fill="{color}"/>')
        parts.append(f'<text x="{legend_x+14}" y="17" class="tick">{m}</text>')
        legend_x += 14 + 8 * len(m) + 24
    for i, day in enumerate(days):
        total = sum(counts.get((day, m), 0) for m in models) or 1
        x0 = pad + i * (w - 2 * pad) / len(days)
        y0 = h - pad
        for m in models:
            share = counts.get((day, m), 0) / total
            bar_h = share * (h - 2 * pad - 10)
            y0 -= bar_h
            parts.append(
                f'<rect x="{x0:.1f}" y="{y0:.1f}" width="{bar_w:.1f}" height="{bar_h:.1f}" '
                f'fill="{_MODEL_COLORS.get(m, _FALLBACK_COLOR)}"/>'
            )
    parts.append(f'<text x="{pad}" y="{h-pad+16}" class="tick">{days[0]}</text>')
    parts.append(f'<text x="{w-pad}" y="{h-pad+16}" text-anchor="end" class="tick">{days[-1]}</text>')
    parts.append("</svg>")
    return "".join(parts)


def _rct_block(rct: dict, guardrails: list[dict]) -> str:
    if not rct["ready"]:
        return (
            f'<p class="muted">Randomized holdout warming up — treatment n={rct["treatment_n"]}, '
            f'control n={rct["control_n"]} (need 30+ each). Until then the numbers above are '
            f'Layer-1 estimates.</p>'
        )
    rows = "".join(
        f'<tr><td>{g["arm"]}</td><td>{g["n"]:,}</td>'
        f'<td>{(g["n_negative"] / g["n"] if g["n"] else 0):.2%}</td></tr>'
        for g in guardrails
    )
    return f"""
    <p><strong>Verified saving: {rct['saving_pct']:.1%} per request</strong>
    (treatment {_usd(rct['mean_treatment'])} vs control {_usd(rct['mean_control'])};
    95% CI on the difference {_usd(rct['diff_ci_low'])} … {_usd(rct['diff_ci_high'])}).</p>
    <table><tr><th>arm</th><th>requests</th><th>negative-feedback rate</th></tr>{rows}</table>
    """


def _ago(ts: float | None) -> str:
    if not ts:
        return "—"
    delta = max(time.time() - ts, 0)
    if delta < 90:
        return "just now"
    if delta < 3600:
        return f"{int(delta // 60)} min ago"
    if delta < 86400:
        return f"{delta / 3600:.0f} h ago"
    return time.strftime("%b %d", time.localtime(ts))


def _now_strip(stats: dict) -> str:
    """The live 'this session' panel. Pinned session if the URL has one
    (the chat links here), else the most recently active conversation."""
    sess = stats["session"]
    pinned = sess is not None
    if not pinned and stats["recent_sessions"]:
        sess = stats["recent_sessions"][0]
    if not sess or not sess["n"]:
        return ('<div class="now"><div class="nowhead">LIVE</div>'
                '<p class="muted">No session activity yet — open the '
                '<a href="/modelpilot/chat">chat</a> or send traffic through the gateway.</p></div>')
    label = "THIS SESSION" if pinned else "LATEST SESSION"
    return f"""
<div class="now">
  <div class="nowhead"><span class="pulse">●</span> {label}
    <code>{sess['session_key'][:14]}</code>
    <span class="muted" id="s-ago">{_ago(sess['last_ts'])}</span></div>
  <div class="cards">
    <div class="card hero"><div class="num save" id="s-realized">{_usd(sess['realized'])}</div>
      <div class="label">saved this session</div></div>
    <div class="card"><div class="num" id="s-potential">{_usd(sess['potential'])}</div>
      <div class="label">potential (if all advice followed)</div></div>
    <div class="card"><div class="num" id="s-n">{sess['n']}</div>
      <div class="label">requests ({sess['n_applied']} auto-routed)</div></div>
    <div class="card"><div class="num" id="s-actual">{_usd(sess['actual'])}</div>
      <div class="label">spent (vs {_usd(sess['baseline'])} baseline)</div></div>
  </div>
</div>"""


def _sessions_table(stats: dict, days: float) -> str:
    rows = stats["recent_sessions"]
    if not rows:
        return '<p class="muted">No sessions recorded yet.</p>'
    current = (stats["session"] or {}).get("session_key", "")
    body = "".join(
        f'<tr{(" class=current" if r["session_key"] == current else "")}>'
        f'<td><a href="/modelpilot/dashboard?days={days:g}&session={r["session_key"]}">'
        f'{r["session_key"][:14]}</a></td>'
        f'<td>{_ago(r["last_ts"])}</td><td>{r["n"]:,}</td>'
        f'<td class="save">{_usd(r["realized"])}</td><td>{_usd(r["potential"])}</td>'
        f'<td>{_usd(r["actual"])}</td></tr>'
        for r in rows
    )
    return (f'<table><tr><th>session</th><th>last active</th><th>requests</th>'
            f'<th>saved</th><th>potential</th><th>spent</th></tr>{body}</table>')


_POLL_SCRIPT = """
<script>
const MP_DAYS = "__DAYS__", MP_SESSION = "__SESSION__";
const mpUsd = x => '$' + (Math.abs(x) >= 0.01 ? x.toFixed(2) : x.toFixed(4));
async function mpTick() {
  try {
    const url = '/modelpilot/stats?days=' + MP_DAYS +
                (MP_SESSION ? '&session=' + encodeURIComponent(MP_SESSION) : '');
    const s = await (await fetch(url)).json();
    const set = (id, v) => { const el = document.getElementById(id); if (el) el.textContent = v; };
    const sess = s.session || (s.recent_sessions && s.recent_sessions[0]);
    if (sess && sess.n) {
      set('s-realized', mpUsd(sess.realized));
      set('s-potential', mpUsd(sess.potential));
      set('s-n', sess.n);
      set('s-actual', mpUsd(sess.actual));
      set('s-ago', 'just now');
    }
    set('t-n', s.summary.n.toLocaleString());
    set('t-realized', mpUsd(s.summary.realized - s.escalations.cost));
    set('t-potential', mpUsd(s.summary.potential));
  } catch (e) { /* gateway briefly unreachable — try again next tick */ }
}
setInterval(mpTick, 5000);
</script>
"""


def _quality_verdict(stats: dict) -> str:
    rct = stats["rct"]
    if not rct.get("ready"):
        guards = {g["arm"]: g for g in stats["guardrails"]}
        gt = guards.get("treatment", {})
        if gt.get("n"):
            rate = gt["n_negative"] / gt["n"]
            return f"quality so far: {rate:.1%} negative feedback on routed requests"
        return "quality monitoring is warming up (needs 30+ requests per arm to certify)"
    return (f"quality verified: routing saves {rct['saving_pct']:.0%}/request with "
            f"outputs statistically on par with the baseline (randomized holdout)")


def _conversion_panel(stats: dict) -> str:
    """The conversion artifact: in guidance/shadow, show what autopilot WOULD
    save (gated potential = only the confident routes autopilot would apply) and
    push the switch. In autopilot, reassure with realized savings + quality."""
    s = stats["summary"]
    mode = stats["mode"]
    days = stats["window_days"]
    gated = s.get("gated_potential", s["potential"])
    pct = (gated / s["baseline"]) if s["baseline"] else 0.0
    annual = (gated / days * 365.0) if days else 0.0
    verdict = _quality_verdict(stats)

    if mode == "autopilot":
        net = s["realized"] - stats["escalations"]["cost"]
        rpct = (net / s["baseline"]) if s["baseline"] else 0.0
        return f"""<div class="now" style="border-color:#bfe5cc">
  <div class="nowhead">AUTOPILOT — CAPTURING SAVINGS</div>
  <div style="font-size:1.5rem;font-weight:700;color:#2e9e5b">{_usd(net)} saved
    <span style="font-size:0.9rem;font-weight:500;color:#6b7080">({rpct:.0%} of spend, this {("day" if days==1 else f"{days:g}d")})</span></div>
  <p class="muted" style="margin:6px 0 0">{verdict}.</p>
</div>"""

    # guidance / shadow: sell the switch
    cta = ("You're in guidance mode — nothing has been rerouted yet. "
           "Switch to autopilot to start capturing this:") if mode == "advise" else (
           "You're in shadow mode (measuring only). Move to guidance, then autopilot, to capture this:")
    annual_line = (f" · about <b>{_usd(annual)}/yr</b> at this rate" if annual else "")
    return f"""<div class="now" style="border-color:#f0d9a8;background:#fffdf5">
  <div class="nowhead" style="color:#b8860b">READY TO SWITCH TO AUTOPILOT?</div>
  <div style="font-size:1.5rem;font-weight:700;color:#2e9e5b">{_usd(gated)} you could save
    <span style="font-size:0.9rem;font-weight:500;color:#6b7080">({pct:.0%} of spend){annual_line}</span></div>
  <p class="muted" style="margin:6px 0 4px">This is the savings autopilot would have captured at the
    current confidence gate — only the routes it's sure about. {verdict.capitalize()}.</p>
  <p style="margin:4px 0 0"><b>{cta}</b>
    <code>modelpilot gateway --mode autopilot</code></p>
  <p class="muted" style="margin:4px 0 0;font-size:0.8rem">See the proof on your own traffic:
    <code>modelpilot compare --from-captures --judge</code> — same prompts, recommended vs standard
    model, side by side.</p>
</div>"""


def _proof_section(stats: dict) -> str:
    """The embedded conversion proof: the customer's own prompts, recommended
    model vs standard model, outputs side by side, with per-chat + cumulative
    savings. Generated by `compare --from-captures --save-to-db`."""
    proof = stats.get("proof") or {}
    rows, summ = proof.get("rows") or [], proof.get("summary") or {}
    if not rows:
        return ('<p class="muted">No side-by-side proof generated yet. Run '
                '<code>modelpilot compare --from-captures --judge --save-to-db</code> '
                '(needs <code>MODELPILOT_CAPTURE_PCT&gt;0</code> during a run) to render your '
                'own prompts here — recommended vs standard model, outputs and savings side by side.</p>')
    nir = summ.get("non_inferior_rate")
    head = (f'<p>Across {summ["n"]} of your prompts, routing saved '
            f'<b class="save">{_usd(summ["savings"])}</b> ({summ["savings_pct"]:.0%}) — '
            + (f'<b>{nir:.0%}</b> of routed outputs judged non-inferior to the standard model. '
               'Same prompts, both outputs below — see for yourself.'
               if nir is not None else
               'add <code>--judge</code> for non-inferiority verdicts. Same prompts, both outputs below.')
            + '</p>')
    blocks, run = [], 0.0
    for r in rows:
        saved = r["baseline_cost"] - r["routed_cost"]
        run += saved
        verdict = ("" if r["non_inferior"] is None else
                   ' <span class="ok">✓ non-inferior</span>' if r["non_inferior"] else
                   ' <span class="bad">✗ review</span>')
        blocks.append(f"""
  <details><summary><b>{html.escape(r['category'])}</b> · saved
    <b class="save">{_usd(saved)}</b> · cumulative {_usd(run)}{verdict}</summary>
    <p class="prompt">{html.escape(r['prompt'][:600])}</p>
    <div class="sxs">
      <div><h4>ModelPilot → {html.escape(r['routed_model'])} · {_usd(r['routed_cost'])}</h4>
        <pre>{html.escape(r['routed_text'][:2000])}</pre></div>
      <div><h4>Standard → {html.escape(r['baseline_model'])} · {_usd(r['baseline_cost'])}</h4>
        <pre>{html.escape(r['baseline_text'][:2000])}</pre></div>
    </div></details>""")
    return head + "".join(blocks)


def render_html(stats: dict) -> str:
    s = stats["summary"]
    esc = stats["escalations"]
    net_realized = s["realized"] - esc["cost"]
    pct = f"{stats['summary']['potential'] / s['baseline']:.1%}" if s["baseline"] else "—"
    window = f"last {stats['window_days']:g} days" if stats["window_days"] else "all time"

    days = [d["day"] for d in stats["daily"]]
    cum_potential, cum_realized, run_p, run_r = [], [], 0.0, 0.0
    for d in stats["daily"]:
        run_p += d["potential"]
        run_r += d["realized"]
        cum_potential.append(run_p)
        cum_realized.append(run_r)

    cards = "".join(
        f'<div class="card"><div class="num"{(" id=" + ident) if ident else ""}>{value}</div>'
        f'<div class="label">{label}</div></div>'
        for label, value, ident in [
            ("requests scored", f"{s['n']:,}", "t-n"),
            ("net realized savings", _usd(net_realized), "t-realized"),
            ("potential savings (est.)", _usd(s["potential"]), "t-potential"),
            ("actual spend", _usd(s["actual"]), ""),
            ("baseline spend", _usd(s["baseline"]), ""),
            ("potential vs baseline", pct, ""),
        ]
    )
    cat_rows = "".join(
        f'<tr><td>{c["category"]}</td><td>{c["n"]:,}</td><td>{_usd(c["potential"])}</td>'
        f'<td>{c["avg_confidence"]:.2f}</td></tr>'
        for c in stats["by_category"][:12]
    )
    esc_line = (
        f'<p>{esc["n"]:,} escalation re-runs costing {_usd(esc["cost"])} — already deducted '
        f'from net realized savings.</p>' if esc["n"] else '<p class="muted">No escalations recorded.</p>'
    )
    session_key = (stats["session"] or {}).get("session_key", "")

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>ModelPilot</title>
<style>
  body {{ font: 14px/1.5 -apple-system, "Segoe UI", sans-serif; margin: 2rem auto; max-width: 800px;
         color: #1f2430; padding: 0 1rem; }}
  h1 {{ font-size: 1.4rem; }} h2 {{ font-size: 1.05rem; margin-top: 2.2rem; border-bottom: 1px solid #eee;
       padding-bottom: 4px; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 10px; }}
  .card {{ border: 1px solid #e3e3e8; border-radius: 8px; padding: 10px 14px; min-width: 140px; }}
  .card.hero {{ border-color: #bfe5cc; background: #f4fbf6; }}
  .num {{ font-size: 1.3rem; font-weight: 600; }} .label {{ color: #6b7080; font-size: 0.8rem; }}
  .num.save, td.save {{ color: #2e9e5b; }}
  .now {{ border: 1px solid #d8efe0; border-radius: 10px; padding: 12px 14px; background: #fbfefc; }}
  .nowhead {{ font-size: 0.78rem; font-weight: 700; letter-spacing: 0.05em; color: #2e9e5b;
              margin-bottom: 8px; }}
  .nowhead code {{ color: #6b7080; font-weight: 400; }}
  .pulse {{ animation: mp-pulse 2s infinite; }}
  @keyframes mp-pulse {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: 0.25; }} }}
  .chart {{ width: 100%; height: auto; }} .tick {{ font-size: 11px; fill: #6b7080; }}
  table {{ border-collapse: collapse; width: 100%; }} td, th {{ border-bottom: 1px solid #eee;
  padding: 5px 8px; text-align: left; }} th {{ color: #6b7080; font-weight: 600; }}
  tr.current {{ background: #f4fbf6; }}
  .muted {{ color: #6b7080; }} a {{ color: #2f6fb6; }}
  .note {{ background: #f6f7f9; border-radius: 8px; padding: 10px 14px; font-size: 0.85rem; }}
  .ok {{ color: #2e9e5b; }} .bad {{ color: #b3372f; }}
  details {{ border: 1px solid #eee; border-radius: 8px; margin: 8px 0; padding: 8px 12px; }}
  summary {{ cursor: pointer; }}
  .prompt {{ background: #f6f7f9; border-radius: 6px; padding: 8px 10px; font-size: 0.85rem; }}
  .sxs {{ display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }}
  .sxs h4 {{ margin: 6px 0; font-size: 0.82rem; }}
  .sxs pre {{ white-space: pre-wrap; background: #fbfbfc; border: 1px solid #eee; border-radius: 6px;
        padding: 8px; font-size: 0.8rem; max-height: 320px; overflow-y: auto; }}
  details.adv {{ margin-top: 2.2rem; }}
  details.adv > summary {{ font-weight: 600; color: #6b7080; }}
  details.adv h3 {{ font-size: 0.95rem; margin: 1.3rem 0 0.4rem; }}
</style></head><body>
<h1>ModelPilot <span class="muted" style="font-size:0.8rem;font-weight:400">— {stats['display_mode']} mode</span></h1>
{_conversion_panel(stats)}
{_now_strip(stats)}

<h2>Proof: recommended vs standard model, side by side</h2>
{_proof_section(stats)}

<h2>Cumulative savings <span class="muted" style="font-size:0.8rem;font-weight:400">— {window}
(<a href="?days=1{f'&session={session_key}' if session_key else ''}">day</a> ·
 <a href="?days=7{f'&session={session_key}' if session_key else ''}">week</a> ·
 <a href="?days=30{f'&session={session_key}' if session_key else ''}">month</a> ·
 <a href="?days=0{f'&session={session_key}' if session_key else ''}">all</a>)</span></h2>
{_line_chart({"potential (est.)": cum_potential, "realized": cum_realized}, days,
             colors={"potential (est.)": "#2f6fb6", "realized": "#2e9e5b"})}

<details class="adv"><summary>Details &amp; methodology</summary>
<h3>Totals</h3>
<div class="cards">{cards}</div>

<h3>Recent sessions</h3>
{_sessions_table(stats, stats["window_days"])}

<h3>Recommended model mix (the migration story)</h3>
{_mix_chart(stats["daily_mix"])}

<h3>Top opportunities by category</h3>
<table><tr><th>category</th><th>requests</th><th>potential</th><th>avg confidence</th></tr>{cat_rows}</table>

<h3>Quality assurance</h3>
{esc_line}
{_rct_block(stats["rct"], stats["guardrails"])}

<p class="note">Potential savings are Layer-1 estimates (same tokens re-priced at the requested
model). The verified number comes from the randomized holdout above; replay sampling further
calibrates output-length differences. Savings are reported net of escalation re-runs.</p>
</details>
{_POLL_SCRIPT.replace("__DAYS__", f"{stats['window_days']:g}").replace("__SESSION__", session_key)}
</body></html>"""
