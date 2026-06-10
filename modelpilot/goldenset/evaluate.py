"""Evaluate the router against golden labels and tune the confidence gate.

  python -m modelpilot.goldenset.evaluate --labels gs/labels.jsonl

For each confidence threshold, reports:
  coverage         — % of traffic where a switch would be applied
  accuracy         — applied decision lands exactly on the label tier
  false_downgrade  — applied decision lands BELOW the label tier (the metric;
                     ROUTER_TUNING_PLAN.md targets <= 1-2%)
  missed           — stayed above the label tier (savings left on the table)

The recommended gate is the lowest threshold whose false-downgrade rate meets
the target — maximizing savings subject to the safety constraint.
"""

import argparse

from ..pricing import ladder_tier
from ..router import recommend
from .fanout import load_jsonl

FDR_TARGET = 0.02
THRESHOLDS = [0.0, 0.3, 0.5, 0.6, 0.7, 0.8, 0.9]


def evaluate(labels: list[dict], baseline: str = "claude-opus-4-8",
             thresholds: list[float] = THRESHOLDS) -> dict:
    decisions = []
    for row in labels:
        body = {"model": baseline, "max_tokens": 1024,
                "messages": [{"role": "user", "content": row["prompt"]}]}
        rec = recommend(body)
        decisions.append((rec, ladder_tier(row["label_model"])))

    baseline_tier = ladder_tier(baseline)
    results = []
    for thr in thresholds:
        n = len(decisions)
        applied = correct = false_down = missed = 0
        for rec, label_tier in decisions:
            act = rec.action == "switch" and rec.confidence >= thr
            chosen_tier = ladder_tier(rec.recommended_model) if act else baseline_tier
            applied += act
            if chosen_tier == label_tier:
                correct += 1
            elif chosen_tier < label_tier:
                false_down += 1
            else:
                missed += 1
        results.append({
            "threshold": thr,
            "coverage": applied / n if n else 0.0,
            "accuracy": correct / n if n else 0.0,
            "false_downgrade": false_down / n if n else 0.0,
            "missed": missed / n if n else 0.0,
        })

    safe = [r for r in results if r["false_downgrade"] <= FDR_TARGET]
    recommended = min(safe, key=lambda r: r["threshold"]) if safe else None
    return {"n": len(decisions), "by_threshold": results, "recommended": recommended}


def render(report: dict) -> str:
    lines = [
        f"Router evaluation on {report['n']} golden-labeled prompts",
        "=" * 64,
        f"{'gate':>6} {'coverage':>9} {'accuracy':>9} {'false-dg':>9} {'missed':>9}",
    ]
    for r in report["by_threshold"]:
        flag = " <-- recommended" if report["recommended"] and r["threshold"] == report["recommended"]["threshold"] else ""
        lines.append(
            f"{r['threshold']:>6.2f} {r['coverage']:>9.1%} {r['accuracy']:>9.1%} "
            f"{r['false_downgrade']:>9.1%} {r['missed']:>9.1%}{flag}"
        )
    if report["recommended"] is None:
        lines.append(f"\nNo threshold meets the {FDR_TARGET:.0%} false-downgrade target — do not enable autopilot.")
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--labels", default="goldenset_data/labels.jsonl")
    parser.add_argument("--baseline", default="claude-opus-4-8")
    args = parser.parse_args()
    print(render(evaluate(load_jsonl(args.labels), baseline=args.baseline)))


if __name__ == "__main__":
    main()
