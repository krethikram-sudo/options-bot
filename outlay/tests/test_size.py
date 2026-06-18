"""Size-conditioned forecasting and its backtest proof."""

from datetime import datetime

from outlay.attribute import attribute
from outlay.backtest import backtest
from outlay.forecast import class_stats, forecast_roadmap
from outlay.models import TaskClass, UsageEvent, WorkItem
from outlay.size import FEATURE_DIFF, FEATURE_POINTS, fit_size_models, size_feature


def _ev(eid, tokens, branch, session):
    # opus input rate is $5/1M, so cost == tokens * 5 / 1e6 (200k -> $1.00).
    return UsageEvent(id=eid, provider="anthropic", model="claude-opus-4-8",
                      ts=datetime(2026, 6, 1), branch=branch, session_id=session,
                      input_tokens=tokens)


def _linear_bug_history():
    """Four done bugfixes where cost scales exactly with story points (k=$1/pt)."""
    work, events = [], []
    for n, pts in ((1, 1), (2, 2), (3, 3), (4, 4)):
        work.append(WorkItem(f"GH-{n}", "github", labels=["bug"], branch=f"fix/{n}",
                             status="done", est_points=pts))
        events.append(_ev(f"e{n}", pts * 200_000, f"fix/{n}", f"s{n}"))
    return work, events


def test_size_feature_priority_and_none():
    assert size_feature(WorkItem("A", "github", est_points=3, diff_added=100)) == (FEATURE_POINTS, 3.0)
    assert size_feature(WorkItem("B", "github", diff_added=80, diff_removed=20)) == (FEATURE_DIFF, 100.0)
    assert size_feature(WorkItem("C", "github")) is None


def test_fit_requires_min_history():
    # Two sized bugfixes is below min_fit=3 → no model.
    work = [WorkItem("GH-1", "github", labels=["bug"], branch="fix/1", status="done", est_points=2),
            WorkItem("GH-2", "github", labels=["bug"], branch="fix/2", status="done", est_points=4)]
    events = [_ev("a", 400_000, "fix/1", "s1"), _ev("b", 800_000, "fix/2", "s2")]
    assert fit_size_models(attribute(events, work), work) == {}


def test_size_conditioned_forecast_scales_with_points():
    work, events = _linear_bug_history()
    res = attribute(events, work)
    stats = class_stats(res)
    models = fit_size_models(res, work)
    assert TaskClass.BUGFIX in models
    assert models[TaskClass.BUGFIX].feature == FEATURE_POINTS
    assert abs(models[TaskClass.BUGFIX].cost_per_unit - 1.0) < 1e-9  # $1 per point

    # A 5-point open bugfix should be costed at ~$5 (size), not the $2.50 class mean.
    big = WorkItem("GH-10", "github", labels=["bug"], status="open", est_points=5)
    fc = forecast_roadmap([big], stats, models)
    it = fc.items[0]
    assert it.basis == "size"
    assert abs(it.expected_usd - 5.0) < 1e-9
    assert it.low_usd <= it.expected_usd <= it.high_usd


def test_forecast_falls_back_to_class_without_size_signal():
    work, events = _linear_bug_history()
    res = attribute(events, work)
    models = fit_size_models(res, work)
    # Open bugfix with no points and no diff → class-mean basis.
    plain = WorkItem("GH-11", "github", labels=["bug"], status="open")
    fc = forecast_roadmap([plain], class_stats(res), models)
    assert fc.items[0].basis == "class"
    assert abs(fc.items[0].expected_usd - 2.5) < 1e-9  # class mean of 1,2,3,4


def test_backtest_proves_size_helps_on_linear_data():
    work, events = _linear_bug_history()
    rep = backtest(attribute(events, work), work)
    assert rep.size is not None
    assert rep.size.n == 4
    assert rep.size.improves
    assert rep.size.mdape_size < rep.size.mdape_class
    assert rep.size.error_reduction > 0.5  # near-perfect fit → big cut


def test_backtest_size_none_without_work_items():
    work, events = _linear_bug_history()
    assert backtest(attribute(events, work)).size is None
