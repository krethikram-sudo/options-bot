"""JSON serialization of the report."""

import json

from outlay.cli import run
from outlay.dogfood import build_report
from outlay.ingest import parse_anthropic_usage, parse_github_issues
from outlay.tests.test_pipeline import FIX


def _fixture_json():
    out = run(FIX / "anthropic_usage.json", FIX / "github_issues.json",
              window_days=9, as_json=True)
    return json.loads(out)  # must be valid JSON


def test_json_schema_and_core_numbers():
    d = _fixture_json()
    assert d["schema_version"] == "1.0"
    assert d["window_days"] == 9
    sp = d["spend"]
    assert sp["total_usd"] > 0
    assert 0 < sp["ticket_coverage"] <= 1
    # fidelity tiers all present
    assert set(sp["by_fidelity_usd"]) == {"call", "branch", "team", "invoice"}


def test_json_forecast_and_items():
    fc = _fixture_json()["forecast"]
    assert fc["low_usd"] <= fc["expected_usd"] <= fc["high_usd"]
    assert fc["high_usd"] <= fc["conservative_p90_usd"]
    assert fc["items"]  # per-item bands serialized
    it = fc["items"][0]
    assert {"ticket_id", "task_class", "expected_usd", "low_usd",
            "high_usd", "basis", "costable"} <= set(it)


def test_json_calibration_with_size_verdict():
    cal = _fixture_json()["calibration"]
    assert cal["n_evaluated"] >= 0
    assert "mdape" in cal and "accuracy" in cal
    # fixtures carry diff-size signals → size comparison present
    assert cal["size"] is not None
    assert isinstance(cal["size"]["improves"], bool)


def test_json_savings_and_recommendations():
    d = _fixture_json()
    assert "enforce_now_usd" in d["savings"]
    assert d["recommendations"]  # at least one rec on the fixtures
    assert d["recommendations"][0]["confidence"] in ("validated", "needs_validation")


def test_dogfood_json_matches_schema():
    events = parse_anthropic_usage(FIX / "anthropic_usage.json")
    work = parse_github_issues(FIX / "github_issues.json")
    d = json.loads(build_report(events, work, window_days=9, as_json=True))
    assert d["schema_version"] == "1.0"
    assert "calibration" in d and "forecast" in d


def test_json_implies_calibration_even_without_flag():
    # --json computes calibration regardless of the calibrate flag.
    d = json.loads(run(FIX / "anthropic_usage.json", FIX / "github_issues.json",
                       as_json=True, calibrate=False))
    assert "calibration" in d
