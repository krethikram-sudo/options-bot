"""Closed-loop per-customer floor learning (Track A) — the deepest savings lever.

Auto-tuning (tune.py) adjusts the per-category *gate*; rules (rules.py) fix
*classification*. Both work within a category's globally fixed floor — the
cheapest tier we'll route it to. But a customer's "summarization_long" may be
trivial *for their documents*, and the global floor (Sonnet) leaves money on the
table forever.

This closes the loop between our PROOF and our CONTROL: for each category it
takes a sample of the customer's OWN captured prompts, runs them on the
next-cheaper tier and on the baseline, judges non-inferiority, and lowers the
floor only when the cheaper tier holds up on their data. Re-run as captures
accumulate and the floor walks down one safe step at a time; any category that
fails the bar keeps its floor.

    modelpilot learn-floors --judge --out policy.json     # uses your API key
    modelpilot learn-floors --offline --out policy.json   # report shape, no spend
    # then: MODELPILOT_FLOORS=policy.json modelpilot gateway --mode autopilot

Active testing costs API calls, so this is a periodic command — never the hot
request path. The gateway just loads the resulting `category_floors`.
"""

import argparse
import json
import random
import time
from collections import defaultdict

from .pricing import CAPABILITY_LADDER
from .taxonomy import CATEGORIES, floor_tier

NON_INFERIOR_TARGET = 0.95   # cheaper tier must hold up on >= this share to lower
MIN_SAMPLES = 8              # need at least this many judged prompts to trust it
SAMPLE = 12                 # prompts judged per category per run


def learn_floors(captures_by_category: dict[str, list[str]], run_fn, judge_fn,
                 baseline: str, current_floors: dict | None = None,
                 min_samples: int = MIN_SAMPLES, sample: int = SAMPLE,
                 non_inferior_target: float = NON_INFERIOR_TARGET,
                 rng: random.Random | None = None) -> dict:
    """Test the next-cheaper tier per category on the customer's prompts.

    `run_fn(model, prompt) -> (text, usage)` and
    `judge_fn(prompt, baseline_text, routed_text) -> bool` come from compare.py
    (offline or API-backed). `current_floors` lets repeated runs continue walking
    a floor down from where the last run left it.
    """
    rng = rng or random.Random(7)
    learned = dict(current_floors or {})
    notes = []
    for category, prompts in sorted(captures_by_category.items()):
        cur = floor_tier(category, learned)
        if cur <= 0:
            continue  # already at the cheapest tier
        if len(prompts) < min_samples:
            notes.append(f"{category}: only {len(prompts)} captured prompts "
                         f"(need {min_samples}) — floor held at {CAPABILITY_LADDER[cur]}")
            continue
        candidate = cur - 1
        cand_model = CAPABILITY_LADDER[candidate]
        chosen = rng.sample(prompts, min(sample, len(prompts)))
        ni = n = 0
        for p in chosen:
            routed_text, _ = run_fn(cand_model, p)
            base_text, _ = run_fn(baseline, p)
            n += 1
            ni += int(bool(judge_fn(p, base_text, routed_text)))
        rate = ni / n if n else 0.0
        if n >= min_samples and rate >= non_inferior_target:
            learned[category] = candidate
            notes.append(f"{category}: {ni}/{n} non-inferior at {cand_model} "
                         f"-> floor lowered to {cand_model}")
        else:
            notes.append(f"{category}: {ni}/{n} non-inferior at {cand_model} "
                         f"(< {non_inferior_target:.0%}) -> floor held at {CAPABILITY_LADDER[cur]}")
    return {"category_floors": learned, "notes": notes}


def captures_by_category(captures: list[dict]) -> dict[str, list[str]]:
    by_cat = defaultdict(list)
    for c in captures:
        by_cat[c["category"]].append(c["prompt"])
    return dict(by_cat)


def _merge_into_policy(out_path: str, floors: dict) -> dict:
    """Write category_floors into the policy file, preserving gates/rules."""
    policy = {}
    try:
        with open(out_path) as f:
            policy = json.load(f) or {}
    except (OSError, ValueError):
        policy = {}
    policy["category_floors"] = floors
    policy["floors_generated_at"] = time.strftime("%Y-%m-%d %H:%M")
    with open(out_path, "w") as f:
        json.dump(policy, f, indent=2)
    return policy


def main():
    parser = argparse.ArgumentParser(description="Closed-loop per-customer floor learning")
    parser.add_argument("--db", default="modelpilot.db")
    parser.add_argument("--days", type=float, default=30.0, help="capture window (0 = all)")
    parser.add_argument("--baseline", default="claude-fable-5")
    parser.add_argument("--judge", action="store_true",
                        help="run real API calls + non-inferiority judging (costs money)")
    parser.add_argument("--offline", action="store_true",
                        help="synthetic run/judge — report shape only, no spend")
    parser.add_argument("--sample", type=int, default=SAMPLE)
    parser.add_argument("--min-samples", type=int, default=MIN_SAMPLES)
    parser.add_argument("--target", type=float, default=NON_INFERIOR_TARGET)
    parser.add_argument("--out", default="policy.json",
                        help="policy file to update with category_floors (gates/rules preserved)")
    args = parser.parse_args()

    from .ledger import Ledger
    ledger = Ledger(args.db)
    since = time.time() - args.days * 86_400 if args.days else 0.0
    caps = ledger.captures(since)
    ledger.close()
    if not caps:
        raise SystemExit("No captured prompts. Run the gateway with "
                         "MODELPILOT_CAPTURE_PCT>0 for a while, then retry.")

    from .compare import (
        api_judge_fn,
        api_run_fn,
        offline_judge_fn,
        offline_run_fn,
    )
    if args.offline:
        run_fn, judge_fn = offline_run_fn, offline_judge_fn
    else:
        import os
        key = os.environ.get("ANTHROPIC_API_KEY", "")
        if not key:
            raise SystemExit("ANTHROPIC_API_KEY is not set. Set it, or use --offline.")
        run_fn, judge_fn = api_run_fn(key), api_judge_fn()

    # Continue from any floors already learned in the policy file.
    current = _load_existing_floors(args.out)
    result = learn_floors(
        captures_by_category(caps), run_fn, judge_fn, args.baseline,
        current_floors=current, min_samples=args.min_samples,
        sample=args.sample, non_inferior_target=args.target)

    print("Floor learning (on your own captured prompts):")
    for note in result["notes"]:
        print(f"  - {note}")
    if result["category_floors"]:
        _merge_into_policy(args.out, result["category_floors"])
        print(f"\nLearned floors written to {args.out}. Apply them:")
        print(f"  MODELPILOT_FLOORS={args.out} modelpilot gateway --mode autopilot")
    else:
        print("\nNo category cleared the bar to lower its floor yet — keep capturing "
              "and re-run.")


def _load_existing_floors(path: str) -> dict:
    try:
        with open(path) as f:
            return (json.load(f) or {}).get("category_floors", {}) or {}
    except (OSError, ValueError):
        return {}


if __name__ == "__main__":
    main()
