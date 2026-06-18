"""Calibration backtest: leave-one-out forecast accuracy on realized spend."""

from datetime import datetime

from outlay.attribute import attribute
from outlay.backtest import backtest, format_calibration
from outlay.cli import run
from outlay.models import TaskClass, UsageEvent, WorkItem
from outlay.tests.test_pipeline import FIX


def _ev(eid, model, branch=None, session=None, **tok):
    return UsageEvent(id=eid, provider="anthropic", model=model,
                      ts=datetime(2026, 6, 1), branch=branch, session_id=session, **tok)


def _closed_bug(n, tokens):
    """One done bugfix ticket whose single event costs `tokens` of opus input."""
    wi = WorkItem(f"GH-{n}", "github", labels=["bug"], branch=f"fix/{n}", status="done")
    ev = _ev(f"e{n}", "claude-opus-4-8", branch=f"fix/{n}", session=f"s{n}",
             input_tokens=tokens)
    return wi, ev


def test_perfect_class_has_zero_error():
    # Four identical-cost bugfixes: leave-one-out mean always equals the actual.
    work, events = [], []
    for n in (10, 11, 12, 13):
        wi, ev = _closed_bug(n, 100_000)
        work.append(wi)
        events.append(ev)
    rep = backtest(attribute(events, work))
    assert rep.n_evaluated == 4
    assert rep.n_skipped == 0
    assert rep.overall_mape == 0.0
    assert rep.overall_mdape == 0.0
    assert rep.accuracy == 1.0
    assert rep.by_class[TaskClass.BUGFIX].within_p90 == 1.0


def test_loo_error_is_computed_against_held_out_actual():
    # Costs 100k,100k,100k,200k (opus input). For the 200k ticket the LOO mean is
    # 100k → predicted cost is half of actual → APE 0.5. The three 100k tickets
    # predict (100k,100k,200k)->133k → APE 1/3. MdAPE = median(0.5,1/3,1/3,1/3)=1/3.
    work, events = [], []
    for n, tok in ((20, 100_000), (21, 100_000), (22, 100_000), (23, 200_000)):
        wi, ev = _closed_bug(n, tok)
        work.append(wi)
        events.append(ev)
    rep = backtest(attribute(events, work))
    c = rep.by_class[TaskClass.BUGFIX]
    assert c.n == 4
    assert abs(c.mdape - (1 / 3)) < 1e-9
    # Signed errors: -0.5 on the big ticket, +1/3 on each of the three small ones.
    # Mean = +0.125 — percentage bias is positive because under-shooting a large
    # ticket is capped at -100% while over-shooting small ones isn't bounded.
    assert rep.overall_mape > 0
    assert abs(c.bias - 0.125) < 1e-9


def test_thin_classes_are_skipped_not_guessed():
    # One bugfix (history of 1) cannot be left-one-out predicted → skipped.
    wi, ev = _closed_bug(30, 50_000)
    rep = backtest(attribute([ev], [wi]))
    assert rep.n_evaluated == 0
    assert rep.n_skipped == 1
    assert rep.coverage == 0.0
    assert "unproven" in format_calibration(rep)


def test_uncosted_and_unknown_excluded():
    # A done ticket with no spend and an unclassifiable one must not be evaluated.
    work = [
        WorkItem("GH-40", "github", labels=["bug"], branch="fix/40", status="done"),
        WorkItem("GH-41", "github", labels=["bug"], branch="fix/41", status="done"),
        WorkItem("GH-42", "github", status="done"),  # UNKNOWN class, no events
    ]
    events = [
        _ev("a", "claude-opus-4-8", branch="fix/40", session="s40", input_tokens=80_000),
        _ev("b", "claude-opus-4-8", branch="fix/41", session="s41", input_tokens=90_000),
    ]
    rep = backtest(attribute(events, work))
    assert set(rep.by_class) == {TaskClass.BUGFIX}
    assert rep.n_evaluated == 2


def test_format_block_has_headline_and_per_class():
    work, events = [], []
    for n in (50, 51, 52):
        wi, ev = _closed_bug(n, 100_000 + n * 1000)
        work.append(wi)
        events.append(ev)
    text = format_calibration(backtest(attribute(events, work)))
    assert "Forecast calibration" in text
    assert "Median estimate lands within" in text
    assert "bugfix" in text


def test_cli_calibrate_flag_appends_block():
    out = run(FIX / "anthropic_usage.json", FIX / "github_issues.json",
              window_days=9, calibrate=True)
    assert "Forecast calibration" in out
