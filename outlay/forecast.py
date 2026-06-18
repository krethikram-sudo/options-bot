"""Forecasting and guardrails.

The product leadership actually buys is *predictability tied to the plan they
already build* — not another reactive dashboard. So from historical per-class
cost distributions we forecast the cost of the **open roadmap** (open work items
× their class's observed cost), and we guard with **run-rate / anomaly** flags
(a ticket far above its class median), NOT per-task hard caps. A hard cap that
binds one iteration before success is the worst outcome: you pay and get
nothing. Anomaly flags bind on outliers, which is where the real waste is.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field

from .attribute import AttributionResult, TicketRollup
from .models import TaskClass, WorkItem


@dataclass
class ClassStats:
    task_class: TaskClass
    n: int
    mean: float
    median: float
    p90: float
    mean_rework: float


def class_stats(result: AttributionResult) -> dict[TaskClass, ClassStats]:
    """Per-class cost distribution, computed from *closed-or-touched* tickets in
    history (every ticket we've seen spend for)."""
    by_class: dict[TaskClass, list[TicketRollup]] = defaultdict(list)
    for ru in result.rollups.values():
        by_class[ru.task_class].append(ru)

    stats: dict[TaskClass, ClassStats] = {}
    for tc, rus in by_class.items():
        costs = sorted(r.cost_usd for r in rus)
        rework = [r.rework_iterations for r in rus]
        stats[tc] = ClassStats(
            task_class=tc,
            n=len(costs),
            mean=statistics.fmean(costs),
            median=statistics.median(costs),
            p90=_percentile(costs, 0.90),
            mean_rework=statistics.fmean(rework),
        )
    return stats


def _percentile(sorted_vals: list[float], q: float) -> float:
    if not sorted_vals:
        return 0.0
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    idx = q * (len(sorted_vals) - 1)
    lo = int(idx)
    hi = min(lo + 1, len(sorted_vals) - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1 - frac) + sorted_vals[hi] * frac


@dataclass
class RoadmapForecast:
    expected_usd: float
    p90_usd: float
    items_costed: int
    items_unclassified: int
    by_class: dict[TaskClass, float] = field(default_factory=dict)


def forecast_roadmap(
    open_items: list[WorkItem],
    stats: dict[TaskClass, ClassStats],
) -> RoadmapForecast:
    """Bottom-up forecast: each open work item costed at its class's mean (and
    p90 for the upper band). Items whose class has no history can't be costed —
    we count them rather than guessing, so the forecast states its own coverage.
    """
    from .classify import classify

    expected = 0.0
    p90 = 0.0
    costed = 0
    unclassified = 0
    by_class: dict[TaskClass, float] = defaultdict(float)

    for item in open_items:
        tc = classify(item)
        st = stats.get(tc)
        if st is None or st.n == 0:
            unclassified += 1
            continue
        expected += st.mean
        p90 += st.p90
        by_class[tc] += st.mean
        costed += 1

    return RoadmapForecast(
        expected_usd=expected,
        p90_usd=p90,
        items_costed=costed,
        items_unclassified=unclassified,
        by_class=dict(by_class),
    )


@dataclass
class Anomaly:
    ticket_id: str
    task_class: TaskClass
    cost_usd: float
    class_median: float
    ratio: float


def find_anomalies(
    result: AttributionResult,
    stats: dict[TaskClass, ClassStats],
    threshold: float = 3.0,
) -> list[Anomaly]:
    """Flag tickets whose cost exceeds `threshold`× their class median. This is
    the guardrail that binds — on outliers, not on every task."""
    out: list[Anomaly] = []
    for ru in result.rollups.values():
        st = stats.get(ru.task_class)
        if not st or st.median <= 0:
            continue
        ratio = ru.cost_usd / st.median
        if ratio >= threshold:
            out.append(
                Anomaly(
                    ticket_id=ru.ticket_id,
                    task_class=ru.task_class,
                    cost_usd=ru.cost_usd,
                    class_median=st.median,
                    ratio=ratio,
                )
            )
    return sorted(out, key=lambda a: a.ratio, reverse=True)
