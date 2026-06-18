"""Classify, attribute, forecast, recommend — and the full fixture run."""

from datetime import datetime
from pathlib import Path

from outlay.attribute import attribute
from outlay.classify import classify
from outlay.cli import run
from outlay.forecast import class_stats, find_anomalies, forecast_roadmap
from outlay.ingest import parse_anthropic_usage, parse_github_issues
from outlay.models import FidelityTier, TaskClass, UsageEvent, WorkItem
from outlay.recommend import recommend

FIX = Path(__file__).parent.parent / "fixtures"


# ---- classify ----

def test_classify_label_beats_diff():
    wi = WorkItem("GH-1", "github", labels=["bug"], diff_added=900)
    assert classify(wi) == TaskClass.BUGFIX  # label wins over big diff


def test_classify_branch_verb_fallback():
    wi = WorkItem("GH-2", "github", branch="feat/2-new-thing")
    assert classify(wi) == TaskClass.FEATURE


def test_classify_diff_size_fallback():
    assert classify(WorkItem("GH-3", "github", diff_added=500)) == TaskClass.FEATURE
    assert classify(WorkItem("GH-4", "github", diff_added=5)) == TaskClass.BUGFIX
    assert classify(WorkItem("GH-5", "github")) == TaskClass.UNKNOWN


# ---- attribute ----

def _ev(eid, model, branch=None, session=None, **tok):
    return UsageEvent(id=eid, provider="anthropic", model=model,
                      ts=datetime(2026, 6, 1), branch=branch, session_id=session, **tok)


def test_attribute_coverage_and_rework():
    work = [WorkItem("GH-10", "github", labels=["bug"], branch="fix/10-x", status="done")]
    events = [
        _ev("a", "claude-opus-4-8", branch="fix/10-x", session="s1", input_tokens=100_000),
        _ev("b", "claude-opus-4-8", branch="fix/10-x", session="s2", input_tokens=100_000),
        _ev("c", "claude-haiku-4-5", input_tokens=10_000),  # INVOICE, no ticket
    ]
    res = attribute(events, work)
    assert 0 < res.ticket_coverage < 1            # some attributed, some not
    assert res.rollups["GH-10"].rework_iterations == 2  # two distinct sessions
    # Unattributed invoice spend is retained, not dropped.
    assert any(r.fidelity == FidelityTier.INVOICE for r in res.rows)


# ---- forecast ----

def test_forecast_costs_open_items_and_flags_uncosted():
    work = [
        WorkItem("GH-20", "github", labels=["bug"], branch="fix/20", status="done"),
        WorkItem("GH-21", "github", labels=["bug"], status="open"),     # costable
        WorkItem("GH-22", "github", labels=["chore"], status="open"),   # no history
    ]
    events = [_ev("a", "claude-opus-4-8", branch="fix/20", session="s", input_tokens=200_000)]
    res = attribute(events, work)
    stats = class_stats(res)
    fc = forecast_roadmap([w for w in work if w.is_open], stats)
    assert fc.items_costed == 1          # GH-21 bugfix
    assert fc.items_unclassified == 1    # GH-22 chore has no history
    assert fc.expected_usd > 0


def test_forecast_per_item_intervals_and_pooled_band():
    # History: 4 bugfixes with spread-out costs so the class has real variance.
    work = [WorkItem(f"GH-{n}", "github", labels=["bug"], branch=f"fix/{n}", status="done")
            for n in (50, 51, 52, 53)]
    events = [
        _ev("a", "claude-opus-4-8", branch="fix/50", session="s50", input_tokens=100_000),
        _ev("b", "claude-opus-4-8", branch="fix/51", session="s51", input_tokens=200_000),
        _ev("c", "claude-opus-4-8", branch="fix/52", session="s52", input_tokens=300_000),
        _ev("d", "claude-opus-4-8", branch="fix/53", session="s53", input_tokens=400_000),
    ]
    res = attribute(events, work)
    stats = class_stats(res)
    # Six open bugfixes — enough that pooled sqrt(N) growth clearly beats the
    # linear Σp90 growth, so the independence band is strictly tighter.
    open_items = [WorkItem(f"GH-{n}", "github", labels=["bug"], status="open")
                  for n in range(60, 66)]
    fc = forecast_roadmap(open_items, stats)

    assert fc.items_costed == 6
    # Each item carries a p10..p90 band around its class mean.
    assert len(fc.items) == 6
    it = fc.items[0]
    assert it.costable and it.low_usd <= it.expected_usd <= it.high_usd
    # The variance-pooled aggregate band brackets the expected total...
    assert fc.low_usd < fc.expected_usd < fc.high_usd
    # ...stays nested inside the fully-correlated [Σp10, Σp90] envelope...
    assert fc.high_usd <= fc.p90_usd
    # ...and is strictly tighter than naively summing per-item p90s, because
    # independent per-item errors partially cancel.
    assert fc.high_usd < fc.p90_usd


def test_forecast_uncostable_item_recorded():
    work = [WorkItem("GH-70", "github", labels=["bug"], branch="fix/70", status="done")]
    events = [_ev("a", "claude-opus-4-8", branch="fix/70", session="s", input_tokens=100_000)]
    stats = class_stats(attribute(events, work))
    fc = forecast_roadmap([WorkItem("GH-71", "github", labels=["chore"], status="open")], stats)
    assert fc.items_costed == 0 and fc.items_unclassified == 1
    assert fc.items[0].costable is False and fc.items[0].expected_usd == 0.0


def test_anomaly_flags_outlier():
    work = [WorkItem(f"GH-{n}", "github", labels=["bug"], branch=f"fix/{n}", status="done")
            for n in (30, 31, 32, 33)]
    events = [
        _ev("a", "claude-opus-4-8", branch="fix/30", session="s30", input_tokens=20_000),
        _ev("b", "claude-opus-4-8", branch="fix/31", session="s31", input_tokens=22_000),
        _ev("c", "claude-opus-4-8", branch="fix/32", session="s32", input_tokens=21_000),
        _ev("big", "claude-opus-4-8", branch="fix/33", session="s33", input_tokens=2_000_000),
    ]
    res = attribute(events, work)
    stats = class_stats(res)
    anomalies = find_anomalies(res, stats, threshold=3.0)
    assert [a.ticket_id for a in anomalies] == ["GH-33"]


# ---- recommend ----

def test_recommend_validated_vs_needs_validation():
    work = [
        WorkItem("GH-40", "github", labels=["feature"], branch="feat/40", status="done"),
        WorkItem("GH-41", "github", labels=["bug"], branch="fix/41", status="done"),
    ]
    events = [
        # feature seen on BOTH opus and sonnet -> validated downgrade.
        _ev("f1", "claude-opus-4-8", branch="feat/40", session="s1", input_tokens=500_000),
        _ev("f2", "claude-sonnet-4-6", branch="feat/40", session="s2", input_tokens=100_000),
        # bugfix only on opus -> needs validation.
        _ev("b1", "claude-opus-4-8", branch="fix/41", session="s3", input_tokens=300_000),
    ]
    res = attribute(events, work)
    recs = {r.task_class: r for r in recommend(res)}
    assert recs[TaskClass.FEATURE].confidence == "validated"
    assert recs[TaskClass.BUGFIX].confidence == "needs_validation"
    assert recs[TaskClass.FEATURE].projected_savings_usd > 0


# ---- ingest + end-to-end ----

def test_ingest_shapes():
    events = parse_anthropic_usage(FIX / "anthropic_usage.json")
    work = parse_github_issues(FIX / "github_issues.json")
    assert len(events) > 10 and len(work) == 12
    # cache token split survives ingestion
    e101 = next(e for e in events if e.id == "e101")
    assert e101.cache_read_tokens == 150_000 and e101.cache_write_tokens == 20_000
    # closed+merged issue -> done; open issue -> open
    by_id = {w.ticket_id: w for w in work}
    assert by_id["GH-101"].status == "done"
    assert by_id["GH-107"].status == "open"


def test_end_to_end_fixture_report():
    out = run(FIX / "anthropic_usage.json", FIX / "github_issues.json", window_days=9)
    assert "Outlay" in out
    assert "GH-106" in out          # the anomaly ticket appears
    assert "needs validation" in out
    assert "validated" in out
    # Forecast surfaces the realistic interval and the per-item bands.
    assert "Likely range (p10–p90)" in out
    assert "Top open items" in out
    assert "p10–p90 range" in out
