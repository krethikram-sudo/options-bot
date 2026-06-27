"""Advisory optimization opportunities — caching + batch candidate flags."""

from datetime import datetime

from outlay.attribute import attribute
from outlay.models import TaskClass, UsageEvent, WorkItem
from outlay.opportunities import (
    batch_opportunities,
    caching_opportunities,
    format_opportunities,
)


def _ev(model, inp=0, out=0, cr=0, **kw):
    return UsageEvent(id=kw.pop("id", "e"), provider="anthropic", model=model,
                      ts=datetime(2026, 1, 1), input_tokens=inp, output_tokens=out,
                      cache_read_tokens=cr, **kw)


# --------------------------- caching -------------------------------------- #
def test_caching_flags_low_utilization_high_input():
    evs = [_ev("claude-sonnet-4-6", inp=5_000_000, out=100_000, cr=0, id=str(i)) for i in range(5)]
    ops = caching_opportunities(evs)
    assert len(ops) == 1
    o = ops[0]
    assert o.model == "claude-sonnet-4-6"
    assert o.cache_utilization == 0.0
    # Potential = uncached input cost × (1 − cache_read_mult).
    assert o.potential_savings_usd == round(o.uncached_input_usd * (1 - o.cache_read_mult), 2)


def test_caching_skips_well_cached_workloads():
    # Mostly cache reads → high utilization → not a candidate.
    evs = [_ev("claude-sonnet-4-6", inp=100_000, cr=5_000_000, id=str(i)) for i in range(5)]
    assert caching_opportunities(evs) == []


def test_caching_respects_min_usd():
    evs = [_ev("claude-haiku-4-5", inp=1000, cr=0)]
    assert caching_opportunities(evs, min_usd=1.0) == []


# --------------------------- batch ---------------------------------------- #
def _attributed(class_for_ticket):
    # Build a tiny attribution result: events tagged to tickets of known classes.
    work = [WorkItem(ticket_id=t, source="github", title=title, labels=[lbl])
            for t, (title, lbl) in class_for_ticket.items()]
    evs = []
    for i, t in enumerate(class_for_ticket):
        evs.append(_ev("claude-sonnet-4-6", inp=2_000_000, out=200_000,
                       id=str(i), explicit_ticket=t))
    return attribute(evs, work)


def test_batch_flags_async_classes():
    # A 'test' ticket (async-tolerant) and a 'feature' ticket (not in defaults).
    res = _attributed({"GH-1": ("add tests", "test"), "GH-2": ("build feature", "feature")})
    ops = batch_opportunities(res)
    classes = {o.task_class for o in ops}
    # test should be flagged; feature should not (not in default async set).
    assert "test" in classes
    assert "feature" not in classes
    for o in ops:
        assert o.potential_savings_usd == round(o.spend_usd * o.batch_discount, 2)


# --------------------------- formatting ----------------------------------- #
def test_format_handles_empty():
    txt = format_opportunities([], [])
    assert "No caching or batch candidates" in txt


def test_format_renders_both():
    evs = [_ev("claude-sonnet-4-6", inp=5_000_000, cr=0, id=str(i)) for i in range(5)]
    co = caching_opportunities(evs)
    res = _attributed({"GH-1": ("add tests", "test")})
    bo = batch_opportunities(res)
    txt = format_opportunities(co, bo)
    assert "Prompt-caching candidates" in txt
    assert "Batch-API candidates" in txt
    assert "not realized savings" in txt
