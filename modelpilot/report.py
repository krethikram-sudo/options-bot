"""Shadow-mode savings report.

Usage:  python -m modelpilot.report [--db modelpilot.db] [--days 14]

Prints the Layer-1 estimate of what routing would have saved (shadow/advise)
and what it did save (autopilot). Numbers are labeled estimates — replay
calibration and the randomized holdout (Phase 2) anchor them.
"""

import argparse
import random
import statistics
import time

from .ledger import Ledger


def _fmt_usd(x: float) -> str:
    return f"${x:,.2f}" if abs(x) >= 0.01 else f"${x:,.4f}"


def _bootstrap_diff_ci(a: list[float], b: list[float], n_resamples: int = 2000,
                       seed: int = 7) -> tuple[float, float]:
    """95% CI for mean(a) - mean(b) by bootstrap resampling."""
    rng = random.Random(seed)
    diffs = sorted(
        statistics.fmean(rng.choices(a, k=len(a))) - statistics.fmean(rng.choices(b, k=len(b)))
        for _ in range(n_resamples)
    )
    return diffs[int(0.025 * n_resamples)], diffs[int(0.975 * n_resamples)]


def _rct_section(ledger: Ledger, since: float) -> list[str]:
    arms = ledger.arm_costs(since)
    control, treatment = arms["control"], arms["treatment"]
    if len(control) < 30 or len(treatment) < 30:
        return [
            "",
            "Randomized holdout (Layer 3): not enough data yet "
            f"(treatment n={len(treatment)}, control n={len(control)}; need 30+ each).",
        ]
    mean_t, mean_c = statistics.fmean(treatment), statistics.fmean(control)
    lo, hi = _bootstrap_diff_ci(control, treatment)
    pct = (mean_c - mean_t) / mean_c if mean_c else 0.0
    lines = [
        "",
        "Randomized holdout (Layer 3 — the verified number):",
        "-" * 60,
        f"  treatment (routed):  n={len(treatment):,}  mean cost/request {_fmt_usd(mean_t)}",
        f"  control (baseline):  n={len(control):,}  mean cost/request {_fmt_usd(mean_c)}",
        f"  measured saving:     {pct:.1%} per request "
        f"(95% CI on $ diff: {_fmt_usd(lo)} .. {_fmt_usd(hi)})",
    ]
    for row in ledger.quality_guardrails(since):
        rate = row["n_negative"] / row["n"] if row["n"] else 0.0
        lines.append(f"  {row['arm']:<20} negative-feedback rate {rate:.2%} ({row['n_negative']}/{row['n']})")
    return lines


def render(db_path: str, days: float) -> str:
    ledger = Ledger(db_path)
    since = time.time() - days * 86_400 if days else 0.0
    s = ledger.summary(since)
    lines = [
        f"ModelPilot savings report — last {days:g} days" if days else "ModelPilot savings report — all time",
        "=" * 60,
        f"Requests scored:            {s['n']:,}",
        f"Tokens (in/out):            {s['tok_in']:,} / {s['tok_out']:,}",
        f"Actual spend:               {_fmt_usd(s['actual'])}",
        f"Baseline (requested model): {_fmt_usd(s['baseline'])}",
        f"Switch recommendations:     {s['n_switch_recs']:,} ({s['n_switch_recs'] / s['n']:.0%} of traffic)" if s['n'] else "Switch recommendations:     0",
        "",
        f"REALIZED savings (applied):    {_fmt_usd(s['realized'])}   [{s['n_applied']:,} requests auto-routed]",
        f"POTENTIAL savings (estimated): {_fmt_usd(s['potential'])}   [if every recommendation were followed]",
    ]
    esc = ledger.escalation_costs(since)
    if esc["n"]:
        lines += [
            f"Escalation re-runs:            {esc['n']:,} costing {_fmt_usd(esc['cost'])} "
            "(charged against savings)",
            f"NET realized savings:          {_fmt_usd(s['realized'] - esc['cost'])}",
        ]
    if s["baseline"]:
        lines.append(f"Potential as % of baseline:    {s['potential'] / s['baseline']:.1%}")
    corr = ledger.corrected_potential(since)
    if corr["covered_categories"]:
        lines.append(
            f"Replay-calibrated potential:   {_fmt_usd(corr['corrected_potential'])} "
            f"(output-length corrected; {len(corr['covered_categories'])} categories)"
        )
    lines += _rct_section(ledger, since)
    lines += ["", "By category (top opportunities):", "-" * 60]
    for row in ledger.by_category(since)[:10]:
        lines.append(
            f"  {row['category']:<22} n={row['n']:<6,} "
            f"potential={_fmt_usd(row['potential']):<10} avg_conf={row['avg_confidence']:.2f}"
        )
    lines += ["", "Recommended model mix (requested -> recommended):", "-" * 60]
    for row in ledger.model_mix(since)[:10]:
        arrow = "->" if row["original_model"] != row["recommended_model"] else "= "
        lines.append(f"  {row['original_model']:<22} {arrow} {row['recommended_model']:<22} n={row['n']:,}")
    lines += [
        "",
        "NOTE: potential savings are Layer-1 estimates (same tokens re-priced).",
        "Replay sampling and the randomized holdout produce the verified number.",
    ]
    ledger.close()
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default="modelpilot.db")
    parser.add_argument("--days", type=float, default=0, help="lookback window (0 = all time)")
    args = parser.parse_args()
    print(render(args.db, args.days))


if __name__ == "__main__":
    main()
