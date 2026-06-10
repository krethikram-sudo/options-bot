"""Web dashboard: the visual proof layer (SAVINGS_DASHBOARD.md §2).

  GET /modelpilot/dashboard  — server-rendered HTML, inline SVG charts,
                               zero JS/CDN dependencies (enterprise-safe)
  GET /modelpilot/stats      — the same numbers as JSON

Views: headline cards, cumulative savings curve, model-mix migration,
category drill-down, RCT arm comparison, quality guardrails.
"""

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


def collect_stats(ledger, days: float = 30.0) -> dict:
    since = time.time() - days * 86_400 if days else 0.0
    stats = {
        "window_days": days,
        "summary": ledger.summary(since),
        "by_category": ledger.by_category(since),
        "daily": ledger.daily_series(since),
        "daily_mix": ledger.daily_model_mix(since),
        "escalations": ledger.escalation_costs(since),
        "guardrails": ledger.quality_guardrails(since),
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
async def stats(request: Request, days: float = 30.0):
    return collect_stats(request.app.state.ledger, days)


@router.get("/modelpilot/dashboard")
async def dashboard(request: Request, days: float = 30.0):
    return HTMLResponse(render_html(collect_stats(request.app.state.ledger, days)))


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


def render_html(stats: dict) -> str:
    s = stats["summary"]
    esc = stats["escalations"]
    net_realized = s["realized"] - esc["cost"]
    pct = f"{stats['summary']['potential'] / s['baseline']:.1%}" if s["baseline"] else "—"

    days = [d["day"] for d in stats["daily"]]
    cum_potential, cum_realized, run_p, run_r = [], [], 0.0, 0.0
    for d in stats["daily"]:
        run_p += d["potential"]
        run_r += d["realized"]
        cum_potential.append(run_p)
        cum_realized.append(run_r)

    cards = "".join(
        f'<div class="card"><div class="num">{value}</div><div class="label">{label}</div></div>'
        for label, value in [
            ("requests scored", f"{s['n']:,}"),
            ("actual spend", _usd(s["actual"])),
            ("baseline spend", _usd(s["baseline"])),
            ("net realized savings", _usd(net_realized)),
            ("potential savings (est.)", _usd(s["potential"])),
            ("potential vs baseline", pct),
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

    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>ModelPilot</title>
<style>
  body {{ font: 14px/1.5 -apple-system, "Segoe UI", sans-serif; margin: 2rem auto; max-width: 800px;
         color: #1f2430; padding: 0 1rem; }}
  h1 {{ font-size: 1.4rem; }} h2 {{ font-size: 1.05rem; margin-top: 2rem; }}
  .cards {{ display: flex; flex-wrap: wrap; gap: 10px; }}
  .card {{ border: 1px solid #e3e3e8; border-radius: 8px; padding: 10px 14px; min-width: 140px; }}
  .num {{ font-size: 1.3rem; font-weight: 600; }} .label {{ color: #6b7080; font-size: 0.8rem; }}
  .chart {{ width: 100%; height: auto; }} .tick {{ font-size: 11px; fill: #6b7080; }}
  table {{ border-collapse: collapse; width: 100%; }} td, th {{ border-bottom: 1px solid #eee;
  padding: 5px 8px; text-align: left; }} th {{ color: #6b7080; font-weight: 600; }}
  .muted {{ color: #6b7080; }}
  .note {{ background: #f6f7f9; border-radius: 8px; padding: 10px 14px; font-size: 0.85rem; }}
</style></head><body>
<h1>ModelPilot — last {stats['window_days']:g} days</h1>
<div class="cards">{cards}</div>

<h2>Cumulative savings</h2>
{_line_chart({"potential (est.)": cum_potential, "realized": cum_realized}, days,
             colors={"potential (est.)": "#2f6fb6", "realized": "#2e9e5b"})}

<h2>Recommended model mix (the migration story)</h2>
{_mix_chart(stats["daily_mix"])}

<h2>Top opportunities by category</h2>
<table><tr><th>category</th><th>requests</th><th>potential</th><th>avg confidence</th></tr>{cat_rows}</table>

<h2>Quality assurance</h2>
{esc_line}
{_rct_block(stats["rct"], stats["guardrails"])}

<p class="note">Potential savings are Layer-1 estimates (same tokens re-priced at the requested
model). The verified number comes from the randomized holdout above; replay sampling further
calibrates output-length differences. Savings are reported net of escalation re-runs.</p>
</body></html>"""
