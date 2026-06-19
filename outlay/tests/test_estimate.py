"""Forward estimator for planned (not-yet-built) work."""

from datetime import datetime

from outlay.attribute import attribute
from outlay.classify import classify
from outlay.estimate import (estimate_item, estimate_plan, format_estimate,
                             parse_planned)
from outlay.forecast import class_stats
from outlay.models import TaskClass, UsageEvent, WorkItem
from outlay.size import fit_size_models
from outlay.ingest import parse_anthropic_usage, parse_github_issues
from outlay.tests.test_pipeline import FIX


# ---- text classification of planned work (no labels/branch/diff) ----

def test_classify_from_title_text():
    assert classify(WorkItem("P1", "plan", title="Add OAuth login")) == TaskClass.FEATURE
    assert classify(WorkItem("P2", "plan", title="Fix checkout crash")) == TaskClass.BUGFIX
    assert classify(WorkItem("P3", "plan", title="Refactor the auth module")) == TaskClass.REFACTOR
    assert classify(WorkItem("P4", "plan", title="Add unit tests for payments")) == TaskClass.TEST
    assert classify(WorkItem("P5", "plan", title="Upgrade dependencies and bump CI")) == TaskClass.CHORE
    # narrower intent beats the broad feature verbs
    assert classify(WorkItem("P6", "plan", title="Add tests for the new flow")) == TaskClass.TEST


def test_classify_label_still_wins_over_text():
    wi = WorkItem("P7", "plan", title="Add a new feature", labels=["bug"])
    assert classify(wi) == TaskClass.BUGFIX


# ---- per-item estimate confidence ----

def _ev(eid, tokens, branch, session):
    return UsageEvent(id=eid, provider="anthropic", model="claude-opus-4-8",
                      ts=datetime(2026, 6, 1), branch=branch, session_id=session,
                      input_tokens=tokens)


def _pointed_bug_history():
    work, events = [], []
    for n, pts in ((1, 1), (2, 2), (3, 3), (4, 4)):
        work.append(WorkItem(f"GH-{n}", "github", labels=["bug"], branch=f"fix/{n}",
                             status="done", est_points=pts))
        events.append(_ev(f"e{n}", pts * 200_000, f"fix/{n}", f"s{n}"))
    return attribute(events, work), work


def test_estimate_high_confidence_with_points_and_size_model():
    res, work = _pointed_bug_history()
    stats, models = class_stats(res), fit_size_models(res, work)
    planned = WorkItem("PROJ-1", "plan", title="Fix the login bug", est_points=5)
    e = estimate_item(planned, stats, models)
    assert e.task_class == TaskClass.BUGFIX
    assert e.confidence == "high" and e.basis == "points"
    assert abs(e.expected_usd - 5.0) < 1e-9   # cost-per-point = $1
    assert e.low_usd <= e.expected_usd <= e.high_usd


def test_estimate_low_confidence_when_no_history():
    res, work = _pointed_bug_history()
    stats, models = class_stats(res), fit_size_models(res, work)
    # A chore — no chore history exists, so we decline to cost it.
    planned = WorkItem("PROJ-2", "plan", title="Upgrade dependencies", est_points=2)
    e = estimate_item(planned, stats, models)
    assert e.task_class == TaskClass.CHORE
    assert e.costable is False and e.confidence == "low" and e.expected_usd == 0.0


# ---- plan aggregation ----

def test_estimate_plan_pools_and_counts():
    res, work = _pointed_bug_history()
    stats, models = class_stats(res), fit_size_models(res, work)
    items = [
        WorkItem("A", "plan", title="Fix bug A", est_points=2),
        WorkItem("B", "plan", title="Fix bug B", est_points=3),
        WorkItem("C", "plan", title="Fix bug C", est_points=4),
        WorkItem("D", "plan", title="Upgrade deps"),   # chore, no history
    ]
    plan = estimate_plan(items, stats, models)
    assert plan.items_costed == 3 and plan.items_unknown == 1
    assert plan.low_usd <= plan.expected_usd <= plan.high_usd
    assert plan.high_usd <= sum(e.high_usd for e in plan.items if e.costable) + 1e-9
    assert plan.by_confidence.get("high") == 3 and plan.by_confidence.get("low") == 1


# ---- ingest + end-to-end on fixtures ----

def test_parse_planned_fixture():
    items = parse_planned(FIX / "planned_features.json")
    assert len(items) == 6
    assert items[0].ticket_id == "PROJ-301" and items[0].est_points == 8
    assert all(it.source == "plan" and it.status == "open" for it in items)


def test_end_to_end_estimate_against_history():
    events = parse_anthropic_usage(FIX / "anthropic_usage.json")
    history = parse_github_issues(FIX / "github_issues.json")
    res = attribute(events, history)
    stats, models = class_stats(res), fit_size_models(res, history)
    plan = estimate_plan(parse_planned(FIX / "planned_features.json"), stats, models)
    out = format_estimate(plan)
    assert "Compute budget estimate" in out
    assert "Likely range" in out
    # the chore (no history in the fixture) is declined, not guessed
    assert plan.items_unknown >= 1
