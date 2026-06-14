"""Measure ONE checked-out version's router against a fixed golden-label set.

Self-contained on purpose: it uses only `router.recommend(body)` and
`pricing.ladder_tier` (stable since the first router commit), so it runs
unchanged inside an old git worktree. Holding the LABELS fixed and varying only
the router code isolates "did this iteration's routing get better".

Emits one JSON line: coverage / accuracy / false-downgrade at the calibrated
gate (0.6) and at the safe gate (lowest gate meeting the FDR target).

    python scripts/router_progress.py --labels /abs/path/labels.jsonl
"""

import argparse
import json
import sys

from modelpilot.pricing import ladder_tier
from modelpilot.router import recommend

FDR_TARGET = 0.02
GATES = [0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9]


def evaluate(labels, baseline="claude-opus-4-8"):
    base_tier = ladder_tier(baseline)
    decisions = []
    for row in labels:
        body = {"model": baseline, "max_tokens": 1024,
                "messages": [{"role": "user", "content": row["prompt"]}]}
        rec = recommend(body)
        decisions.append((rec, ladder_tier(row["label_model"])))

    rows = []
    n = len(decisions)
    for thr in GATES:
        applied = correct = false_down = 0
        for rec, label_tier in decisions:
            act = rec.action == "switch" and rec.confidence >= thr
            chosen = ladder_tier(rec.recommended_model) if act else base_tier
            applied += act
            if chosen == label_tier:
                correct += 1
            elif chosen is not None and label_tier is not None and chosen < label_tier:
                false_down += 1
        rows.append({"gate": thr, "coverage": applied / n, "accuracy": correct / n,
                     "fdr": false_down / n})
    safe = [r for r in rows if r["fdr"] <= FDR_TARGET]
    safe_gate = min(safe, key=lambda r: r["gate"]) if safe else None
    at_06 = next(r for r in rows if r["gate"] == 0.6)
    return {"n": n, "at_0.6": at_06, "safe_gate": safe_gate}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--labels", required=True)
    ap.add_argument("--baseline", default="claude-opus-4-8")
    args = ap.parse_args()
    with open(args.labels) as f:
        labels = [json.loads(line) for line in f if line.strip()]
    try:
        print(json.dumps(evaluate(labels, args.baseline)))
    except Exception as e:  # noqa: BLE001 — report, don't crash the sweep
        print(json.dumps({"error": f"{type(e).__name__}: {e}"}))
        sys.exit(1)


if __name__ == "__main__":
    main()
