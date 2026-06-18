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
    p10: float
    p90: float
    std: float          # sample stdev of class cost; 0 when n < 2
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
            p10=_percentile(costs, 0.10),
            p90=_percentile(costs, 0.90),
            std=statistics.stdev(costs) if len(costs) >= 2 else 0.0,
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


# 80% central interval ≈ ±1.2816σ (the z-score of the 10th/90th percentile),
# so the aggregate band lines up with the per-item p10..p90 framing.
_Z_P90 = 1.2815515594


@dataclass
class ItemForecast:
    """Per-item point estimate with a confidence band, costed at its class."""

    ticket_id: str
    task_class: TaskClass
    expected_usd: float
    low_usd: float      # class p10 (empirical, robust to skew)
    high_usd: float     # class p90
    costable: bool


@dataclass
class RoadmapForecast:
    expected_usd: float
    p90_usd: float          # naive upper bound: Σ per-item p90 (assumes perfect correlation)
    items_costed: int
    items_unclassified: int
    by_class: dict[TaskClass, float] = field(default_factory=dict)
    low_usd: float = 0.0    # aggregate lower band, variance-pooled (errors de-correlate)
    high_usd: float = 0.0   # aggregate upper band, variance-pooled — tighter & more honest than p90_usd
    items: list[ItemForecast] = field(default_factory=list)


def forecast_roadmap(
    open_items: list[WorkItem],
    stats: dict[TaskClass, ClassStats],
) -> RoadmapForecast:
    """Bottom-up forecast: each open work item costed at its class's mean, with a
    per-item p10..p90 band. Items whose class has no history can't be costed — we
    count them rather than guessing, so the forecast states its own coverage.

    The aggregate band is **variance-pooled**, not a sum of per-item p90s: across
    many items the over- and under-shoots partially cancel (Var of a sum = Σ of
    variances for independent items), so the honest total band is tighter than
    the perfectly-correlated `p90_usd`. The realistic interval is always kept
    *nested inside* the conservative `[Σp10, Σp90]` envelope — perfect positive
    correlation is the genuine worst case, so the independence band can never sit
    outside it (and won't overshoot it on small, heavy-tailed samples). We keep
    `p90_usd` as the conservative upper bound and add `low_usd`/`high_usd` as the
    realistic interval.
    """
    from .classify import classify

    expected = 0.0
    p10 = 0.0
    p90 = 0.0
    var_sum = 0.0
    costed = 0
    unclassified = 0
    by_class: dict[TaskClass, float] = defaultdict(float)
    items: list[ItemForecast] = []

    for item in open_items:
        tc = classify(item)
        st = stats.get(tc)
        if st is None or st.n == 0:
            unclassified += 1
            items.append(ItemForecast(item.ticket_id, tc, 0.0, 0.0, 0.0, costable=False))
            continue
        expected += st.mean
        p10 += st.p10
        p90 += st.p90
        var_sum += st.std ** 2
        by_class[tc] += st.mean
        costed += 1
        items.append(ItemForecast(item.ticket_id, tc, st.mean, st.p10, st.p90, costable=True))

    agg_std = var_sum ** 0.5
    # Nest the independence band inside the fully-correlated [Σp10, Σp90] envelope.
    high = min(p90, expected + _Z_P90 * agg_std)
    low = max(p10, expected - _Z_P90 * agg_std)
    low = max(0.0, low)

    return RoadmapForecast(
        expected_usd=expected,
        p90_usd=p90,
        items_costed=costed,
        items_unclassified=unclassified,
        by_class=dict(by_class),
        low_usd=low,
        high_usd=high,
        items=items,
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
