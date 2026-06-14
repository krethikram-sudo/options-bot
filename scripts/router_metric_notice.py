"""Emit the calibrated-gate router metric as a GitHub Actions ::notice::.

Kept as a file (not an inline heredoc) so it doesn't fight YAML block-scalar
indentation. Run by the router-metrics CI job after the step-summary table.
"""

import json
import sys

from modelpilot.goldenset.evaluate import evaluate

LABELS = "modelpilot/goldenset_data/labels.jsonl"


def main():
    try:
        labels = [json.loads(line) for line in open(LABELS) if line.strip()]
    except OSError:
        print("no golden labels present — skipping metric")
        return
    row = next(r for r in evaluate(labels)["by_threshold"] if r["threshold"] == 0.6)
    print(f"::notice title=Router @gate 0.60::coverage={row['coverage']:.1%} "
          f"accuracy={row['accuracy']:.1%} false_downgrade={row['false_downgrade']:.1%}")


if __name__ == "__main__":
    sys.exit(main())
