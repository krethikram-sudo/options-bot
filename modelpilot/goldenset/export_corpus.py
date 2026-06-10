"""Export captured shadow-traffic prompts into a golden-set corpus.

  python -m modelpilot.goldenset.export_corpus --db modelpilot.db \\
      --out gs2/prompts.jsonl --per-category 40 [--days 30]

Requires prompt capture to have been enabled on the gateway
(MODELPILOT_CAPTURE_PCT > 0) — by default the ledger stores no prompt text.

Stratified sampling: up to --per-category prompts per router category,
newest-first, deduplicated on normalized text. Output rows carry only
{"id", "prompt", "category"} — live prompts have no `expected`, so they all
go to the pairwise judge.

⚠ REVIEW BEFORE SUBMITTING: captured prompts are real traffic and may
contain PII, secrets, or confidential material. A human must skim the file
before it is fanned out to the Batch API or shared anywhere.
"""

import argparse
import hashlib
import json
import os
import re
import time
from collections import defaultdict

from .fanout import dump_jsonl

MIN_PROMPT_CHARS = 15


def _norm_hash(text: str) -> str:
    normalized = re.sub(r"\s+", " ", text.strip().lower())
    return hashlib.sha256(normalized.encode()).hexdigest()[:12]


def export(captures: list[dict], per_category: int) -> list[dict]:
    """Newest-first, deduped, stratified sample over captured prompts."""
    by_category: dict[str, list[dict]] = defaultdict(list)
    seen: set[str] = set()
    for row in sorted(captures, key=lambda r: -r["ts"]):
        prompt = row["prompt"].strip()
        if len(prompt) < MIN_PROMPT_CHARS:
            continue
        h = _norm_hash(prompt)
        if h in seen:
            continue
        seen.add(h)
        if len(by_category[row["category"]]) < per_category:
            by_category[row["category"]].append(
                {"id": f"live-{h}", "prompt": prompt, "category": row["category"]}
            )
    rows = [r for bucket in by_category.values() for r in bucket]
    rows.sort(key=lambda r: (r["category"], r["id"]))
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--db", default="modelpilot.db")
    # The filename must be prompts.jsonl — build.py reads it from the workdir.
    parser.add_argument("--out", default="goldenset_data/live/prompts.jsonl")
    parser.add_argument("--per-category", type=int, default=40)
    parser.add_argument("--days", type=float, default=0, help="lookback window (0 = all time)")
    args = parser.parse_args()

    from ..ledger import Ledger

    since = time.time() - args.days * 86_400 if args.days else 0.0
    ledger = Ledger(args.db)
    captures = ledger.captures(since)
    ledger.close()
    if not captures:
        print("No captured prompts found. Enable capture on the gateway first:\n"
              "  MODELPILOT_CAPTURE_PCT=0.25 (or similar) — capture is off by default.")
        return

    rows = export(captures, args.per_category)
    os.makedirs(os.path.dirname(args.out) or ".", exist_ok=True)
    dump_jsonl(rows, args.out)

    counts = defaultdict(int)
    for r in rows:
        counts[r["category"]] += 1
    print(f"exported {len(rows)} prompts (from {len(captures)} captures) -> {args.out}")
    print("by category: " + ", ".join(f"{c}={n}" for c, n in sorted(counts.items())))
    print("\n⚠ Review the file for PII/secrets BEFORE running the pipeline on it.")
    print(json.dumps({"next": f"python -m modelpilot.goldenset.build submit --workdir {os.path.dirname(args.out) or '.'}"}))


if __name__ == "__main__":
    main()
