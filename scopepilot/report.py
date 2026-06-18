"""Plain-text report renderer — the P0 deliverable a VP reads in 30 seconds.

Leads with the headline (total + ticket coverage), then the fidelity breakdown
(the honesty layer), per-epic/ticket spend, the roadmap forecast, anomaly flags,
and advisory routing recommendations. Stdlib-only; no table deps.
"""

from __future__ import annotations

from .attribute import AttributionResult
from .forecast import Anomaly, ClassStats, RoadmapForecast
from .models import FidelityTier, TaskClass
from .recommend import Recommendation


def _usd(x: float) -> str:
    if x >= 100:
        return f"${x:,.0f}"
    if x >= 1:
        return f"${x:,.2f}"
    return f"${x:.4f}"


def _bar(frac: float, width: int = 24) -> str:
    filled = round(frac * width)
    return "█" * filled + "·" * (width - filled)


def render(
    result: AttributionResult,
    stats: dict[TaskClass, ClassStats],
    forecast: RoadmapForecast,
    anomalies: list[Anomaly],
    recs: list[Recommendation],
    *,
    window_days: int | None = None,
) -> str:
    L: list[str] = []
    add = L.append

    add("=" * 64)
    add("  ScopePilot — AI spend, mapped to your roadmap   (Phase 0)")
    add("=" * 64)

    total = result.total_cost
    add("")
    add(f"  Total AI spend{f' (last {window_days}d)' if window_days else ''}: "
        f"{_usd(total)}")
    add(f"  Reached a ticket:   {_usd(result.attributed_to_ticket)}  "
        f"({result.ticket_coverage:.0%} coverage)")

    # --- Fidelity (the trust layer) ---
    add("")
    add("  Attribution fidelity (how confident each dollar's join is)")
    add("  " + "-" * 56)
    fid = result.cost_by_fidelity()
    for tier in (FidelityTier.CALL, FidelityTier.BRANCH, FidelityTier.TEAM, FidelityTier.INVOICE):
        amt = fid.get(tier, 0.0)
        frac = (amt / total) if total else 0.0
        add(f"   {tier.value:<8} {_bar(frac)} {frac:>4.0%}  {_usd(amt)}")

    # --- Per-ticket spend ---
    add("")
    add("  Spend by ticket")
    add("  " + "-" * 56)
    rollups = sorted(result.rollups.values(), key=lambda r: r.cost_usd, reverse=True)
    add(f"   {'ticket':<9}{'class':<10}{'status':<13}{'iters':>5}  {'cost':>10}")
    for ru in rollups:
        add(f"   {ru.ticket_id:<9}{ru.task_class.value:<10}{ru.status:<13}"
            f"{ru.rework_iterations:>5}  {_usd(ru.cost_usd):>10}")

    # --- Per-class distribution ---
    add("")
    add("  Cost distribution by task class (learned from history)")
    add("  " + "-" * 56)
    add(f"   {'class':<10}{'n':>3}  {'mean':>9}{'median':>9}{'p90':>9}  {'rework':>7}")
    for tc, st in sorted(stats.items(), key=lambda kv: kv[1].mean, reverse=True):
        add(f"   {tc.value:<10}{st.n:>3}  {_usd(st.mean):>9}{_usd(st.median):>9}"
            f"{_usd(st.p90):>9}  {st.mean_rework:>6.1f}x")

    # --- Forecast ---
    add("")
    add("  Roadmap forecast (open work items × class cost)")
    add("  " + "-" * 56)
    add(f"   Expected: {_usd(forecast.expected_usd)}    "
        f"Upper (p90): {_usd(forecast.p90_usd)}")
    add(f"   Costed {forecast.items_costed} open items; "
        f"{forecast.items_unclassified} had no class history (not costed).")
    for tc, amt in sorted(forecast.by_class.items(), key=lambda kv: kv[1], reverse=True):
        add(f"     {tc.value:<10} {_usd(amt)}")

    # --- Anomalies ---
    add("")
    add("  Anomaly guardrails (tickets ≥3× their class median)")
    add("  " + "-" * 56)
    if not anomalies:
        add("   none — no outlier tickets this window.")
    for a in anomalies:
        add(f"   ⚠ {a.ticket_id:<9} {a.task_class.value:<10} {_usd(a.cost_usd)}  "
            f"({a.ratio:.1f}× median {_usd(a.class_median)})")

    # --- Recommendations ---
    add("")
    add("  Advisory model routing (per class, net of rework)")
    add("  " + "-" * 56)
    if not recs:
        add("   no downgrade opportunities found.")
    for r in recs:
        flag = "✓ validated" if r.confidence == "validated" else "? needs validation"
        add(f"   {r.task_class.value:<10} {r.incumbent_model} → {r.candidate_model}")
        add(f"      save ~{_usd(r.projected_savings_usd)}  [{flag}]")
        add(f"      {r.rationale}")
    add("")
    add("=" * 64)
    return "\n".join(L)
