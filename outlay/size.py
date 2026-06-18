"""Size-conditioned cost model — shrink the per-item band when size predicts cost.

The class-mean forecast treats every bugfix as costing the same. But within a
class, cost often scales with the *size* of the work: a 5-point story or a
600-line diff usually costs more than a 1-pointer. Conditioning the estimate on
size narrows the band — **when that correlation actually exists**. Whether it
does is an empirical question, so this model is opt-in and the backtest
(`backtest.py`) measures size-conditioned error against the class-mean baseline;
we only lean on it where it earns its keep.

Two size signals, in priority order:
  * **story points** (`est_points`) — known at *plan time*, so it forecasts
    unbuilt work. The real forecasting feature.
  * **diff size** (`diff_added + diff_removed`) — only known once the work ships,
    so it's a *retrospective* proxy: great for backtesting that the signal
    exists, not available for a not-yet-built item.

A model is fit per class on whichever feature that class's history consistently
carries (the majority), and only applied to items exposing that *same* feature —
points and diff are different units and must never be mixed in one fit.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from .attribute import AttributionResult
from .forecast import _percentile
from .models import TaskClass, WorkItem

FEATURE_POINTS = "points"
FEATURE_DIFF = "diff"


def size_feature(wi: WorkItem) -> Optional[tuple[str, float]]:
    """The work item's size signal as (kind, value), or None if it has neither.

    Story points win when present (plan-time, forecastable); diff size is the
    retrospective fallback.
    """
    if wi.est_points is not None and wi.est_points > 0:
        return (FEATURE_POINTS, float(wi.est_points))
    if wi.diff_size > 0:
        return (FEATURE_DIFF, float(wi.diff_size))
    return None


@dataclass
class SizeModel:
    """Per-class cost-per-unit-of-size ratio estimator, with a residual band."""

    task_class: TaskClass
    feature: str            # FEATURE_POINTS | FEATURE_DIFF
    cost_per_unit: float    # Σcost / Σsize over the fitted tickets
    n: int                  # tickets used to fit
    lo_mult: float          # p10 of actual/predicted residual ratio
    hi_mult: float          # p90 of actual/predicted residual ratio

    def predict(self, size: float) -> float:
        return size * self.cost_per_unit


def _fit_one(
    pairs: list[tuple[float, float]],  # (size, cost)
    task_class: TaskClass,
    feature: str,
) -> Optional[SizeModel]:
    """Ratio-estimator fit; None if the sizes carry no information."""
    size_sum = sum(s for s, _ in pairs)
    cost_sum = sum(c for _, c in pairs)
    if size_sum <= 0 or cost_sum <= 0:
        return None
    k = cost_sum / size_sum
    # Residual ratios: actual / predicted. 1.0 == on the line.
    ratios = sorted((c / (s * k)) for s, c in pairs if s > 0)
    if not ratios:
        return None
    return SizeModel(
        task_class=task_class,
        feature=feature,
        cost_per_unit=k,
        n=len(pairs),
        lo_mult=_percentile(ratios, 0.10),
        hi_mult=_percentile(ratios, 0.90),
    )


def fit_size_models(
    result: AttributionResult,
    work_items: list[WorkItem],
    *,
    min_fit: int = 3,
) -> dict[TaskClass, SizeModel]:
    """Fit one size model per class from costed history, using the class's
    majority size feature. Classes with fewer than `min_fit` sized tickets get
    no model (and fall back to the class mean) — same don't-guess rule as
    everywhere else.
    """
    wi_by_id = {w.ticket_id: w for w in work_items}
    # class -> feature_kind -> list[(size, cost)]
    grouped: dict[TaskClass, dict[str, list[tuple[float, float]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for ru in result.rollups.values():
        if ru.cost_usd <= 0 or ru.task_class == TaskClass.UNKNOWN:
            continue
        wi = wi_by_id.get(ru.ticket_id)
        if wi is None:
            continue
        sf = size_feature(wi)
        if sf is None:
            continue
        kind, value = sf
        grouped[ru.task_class][kind].append((value, ru.cost_usd))

    models: dict[TaskClass, SizeModel] = {}
    for tc, by_kind in grouped.items():
        # Use the feature the class carries most often.
        kind = max(by_kind, key=lambda k: len(by_kind[k]))
        pairs = by_kind[kind]
        if len(pairs) < min_fit:
            continue
        model = _fit_one(pairs, tc, kind)
        if model is not None:
            models[tc] = model
    return models
