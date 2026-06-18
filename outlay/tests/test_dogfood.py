"""Dogfood report assembly (pure, no network)."""

from outlay.dogfood import build_report
from outlay.ingest import parse_anthropic_usage, parse_github_issues
from outlay.tests.test_pipeline import FIX


def test_build_report_includes_calibration_and_coverage():
    events = parse_anthropic_usage(FIX / "anthropic_usage.json")
    work = parse_github_issues(FIX / "github_issues.json")
    out = build_report(events, work, window_days=9)

    # Core report still present.
    assert "Outlay" in out
    assert "Roadmap forecast" in out
    # Measured accuracy block is appended...
    assert "Forecast calibration" in out
    # ...including the size-vs-class verdict (fixtures carry diff-size signals).
    assert "Size conditioning" in out
    # ...and the make-or-break coverage line.
    assert ">>> TICKET COVERAGE:" in out


def test_build_report_handles_no_events():
    work = parse_github_issues(FIX / "github_issues.json")
    out = build_report([], work, window_days=30)
    assert ">>> TICKET COVERAGE: 0%" in out
    # With no spend there is nothing to calibrate — say so, don't crash.
    assert "Forecast calibration" in out
