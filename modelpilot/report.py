"""Shadow-mode savings report.

Usage:  python -m modelpilot.report [--db modelpilot.db] [--days 14]

Prints the Layer-1 estimate of what routing would have saved (shadow/advise)
and what it did save (autopilot). Numbers are labeled estimates — replay
calibration and the randomized holdout (Phase 2) anchor them.
"""

import argparse
import time

from .ledger import Ledger


def _fmt_usd(x: float) -> str:
    return f"${x:,.2f}" if abs(x) >= 0.01 else f"${x:,.4f}"


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
    if s["baseline"]:
        lines.append(f"Potential as % of baseline:    {s['potential'] / s['baseline']:.1%}")
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
