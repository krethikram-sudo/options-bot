"""Layer-2 replay calibration (SAVINGS_DASHBOARD.md §1).

  modelpilot replay --offline                 # exercise the pipeline, no spend
  modelpilot replay --days 7 --max 50         # nightly job, real API

The Layer-1 ledger estimates baseline cost by re-pricing the routed model's
actual tokens at baseline rates — but different models produce different
output lengths for the same prompt. This job samples switch-recommended
requests that have a captured prompt (replay only works on opt-in captures;
the ledger stores no prompt text otherwise), re-runs them on the baseline
model, and stores a per-(category, baseline) output-length ratio. The report
then shows a replay-calibrated potential alongside the raw estimate.

Cost: bounded by --max (default 50 short requests on the baseline model —
typically a few dollars; this is the price of honest numbers).
"""

import argparse
import os
import statistics
import sys
import time
from collections import defaultdict

MIN_SAMPLES_PER_GROUP = 3


def run_replay(ledger, run_fn, since_ts: float = 0.0, max_samples: int = 50,
               min_per_group: int = MIN_SAMPLES_PER_GROUP, progress=print) -> dict:
    rows = ledger.replayable_sample(since_ts, max_samples)
    if not rows:
        return {"sampled": 0, "written": [], "note":
                "no replayable rows — enable capture (MODELPILOT_CAPTURE_PCT) "
                "and accumulate switch-recommended traffic first"}

    ratios: dict[tuple, list[float]] = defaultdict(list)
    for i, row in enumerate(rows, 1):
        progress(f"[{i}/{len(rows)}] replaying {row['category']} on {row['original_model']}")
        _, usage = run_fn(row["original_model"], row["prompt"])
        if usage.output_tokens > 0:
            ratios[(row["category"], row["original_model"])].append(
                usage.output_tokens / row["output_tokens"])

    written = []
    for (category, baseline_model), values in ratios.items():
        if len(values) < min_per_group:
            continue
        ratio = statistics.median(values)  # median: robust to one runaway output
        ledger.set_replay_coefficient(category, baseline_model, ratio, len(values))
        written.append({"category": category, "baseline_model": baseline_model,
                        "output_ratio": ratio, "n": len(values)})
    return {"sampled": len(rows), "written": written}


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default="modelpilot.db")
    parser.add_argument("--days", type=float, default=7)
    parser.add_argument("--max", type=int, default=50)
    parser.add_argument("--offline", action="store_true", help="synthetic outputs, no spend")
    args = parser.parse_args()

    from .compare import api_run_fn, offline_run_fn
    from .ledger import Ledger

    if args.offline:
        run_fn = offline_run_fn
    else:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            sys.exit("ANTHROPIC_API_KEY is not set. Set it, or use --offline.")
        run_fn = api_run_fn(api_key)

    ledger = Ledger(args.db)
    since = time.time() - args.days * 86_400 if args.days else 0.0
    result = run_replay(ledger, run_fn, since_ts=since, max_samples=args.max)
    if not result["written"]:
        print(result.get("note") or
              f"sampled {result['sampled']} rows but no group reached "
              f"{MIN_SAMPLES_PER_GROUP} samples — raise --max or --days")
    for w in result["written"]:
        print(f"  {w['category']:<22} vs {w['baseline_model']:<18} "
              f"output ratio {w['output_ratio']:.2f}  (n={w['n']})")
    corr = ledger.corrected_potential(since)
    if corr["covered_categories"]:
        print(f"\nraw potential ${corr['raw_potential']:.2f} -> "
              f"replay-calibrated ${corr['corrected_potential']:.2f} "
              f"({len(corr['covered_categories'])} categories corrected)")
    ledger.close()


if __name__ == "__main__":
    main()
