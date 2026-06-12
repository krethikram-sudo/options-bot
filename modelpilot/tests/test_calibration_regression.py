"""Router-accuracy regression gate: every change to the router is measured
against the committed golden labels, automatically, in the same suite as the
plumbing tests. Thresholds pin the calibrated v0.1 results (CALIBRATION.md);
loosening them is an explicit, reviewed decision, never an accident.

Skips in the published beta layout (golden labels are internal data).
"""

from pathlib import Path

import pytest

LABELS = Path(__file__).parent.parent / "goldenset_data" / "labels.jsonl"


@pytest.fixture(scope="module")
def report():
    if not LABELS.exists():
        pytest.skip("golden labels not present (published layout)")
    import json

    from modelpilot.goldenset.evaluate import evaluate

    labels = [json.loads(line) for line in LABELS.read_text().splitlines() if line.strip()]
    return evaluate(labels, baseline="claude-opus-4-8")


def test_zero_false_downgrades_at_calibrated_gates(report):
    for row in report["by_threshold"]:
        if row["threshold"] >= 0.6:
            assert row["false_downgrade"] == 0.0, (
                f"false-downgrade regression at gate {row['threshold']}: "
                f"{row['false_downgrade']:.1%} (calibrated v0.1 = 0.0%)")


def test_coverage_not_regressed(report):
    at_calibrated = next(r for r in report["by_threshold"] if r["threshold"] == 0.6)
    assert at_calibrated["coverage"] >= 0.45, (
        f"coverage at calibrated gate fell to {at_calibrated['coverage']:.1%} "
        f"(v0.1 baseline 49.3%) — savings capture regressed")
    assert at_calibrated["accuracy"] >= 0.60


def test_a_safe_gate_still_exists(report):
    assert report["recommended"] is not None, (
        "no gate meets the <=2% false-downgrade target — autopilot would be unsafe")
