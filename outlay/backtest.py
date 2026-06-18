"""Calibration backtest — put a measured accuracy number on the forecast.

`forecast_roadmap` costs each open work item at its task class's observed mean
(with p90 as the upper band). The honest question a skeptical eng lead asks is:
*how wrong is that, on our own data?* This module answers it with **leave-one-out
cross-validation** over the tickets we already have realized spend for.

For each closed/costed ticket we predict its cost from the *other* tickets in its
class (so the ticket under test never informs its own prediction), then compare
to what it actually cost. We report:

  * **MAPE / MdAPE** — mean and median absolute percentage error of the point
    estimate. MdAPE is the headline: "half of tickets land within X% of estimate".
  * **bias** — mean signed error; positive means we systematically over-forecast.
  * **within-p90** — share of actuals at or below the leave-one-out p90 band; a
    well-calibrated upper band sits near 0.90.

Tickets whose class has too little history to predict are *counted as skipped*,
never silently costed — same coverage-honesty rule as the forecast itself.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .attribute import AttributionResult, TicketRollup
from .forecast import _percentile
from .models import TaskClass, WorkItem
from .size import size_feature


@dataclass
class ClassCalibration:
    task_class: TaskClass
    n: int              # tickets evaluated in this class
    mape: float         # mean absolute percentage error
    mdape: float        # median absolute percentage error
    bias: float         # mean signed pct error; + = over-forecast, - = under
    within_p90: float   # fraction of actuals at or below the LOO p90 band


@dataclass
class SizeComparison:
    """Apples-to-apples LOO of size-conditioned vs class-mean estimates, on the
    subset of tickets that carry a size signal and share identical training folds."""

    n: int
    mdape_class: float   # class-mean baseline MdAPE on these tickets
    mdape_size: float    # size-conditioned MdAPE on the same tickets
    mape_class: float
    mape_size: float

    @property
    def improves(self) -> bool:
        return self.n > 0 and self.mdape_size < self.mdape_class

    @property
    def error_reduction(self) -> float:
        """Fractional MdAPE cut from conditioning on size (negative = it hurt)."""
        if self.mdape_class <= 0:
            return 0.0
        return (self.mdape_class - self.mdape_size) / self.mdape_class


@dataclass
class CalibrationReport:
    n_evaluated: int
    n_skipped: int      # tickets whose class had < min_history → not predictable
    overall_mape: float
    overall_mdape: float
    overall_within_p90: float
    by_class: dict[TaskClass, ClassCalibration] = field(default_factory=dict)
    size: Optional[SizeComparison] = None  # set when work items (size signals) supplied

    @property
    def coverage(self) -> float:
        """Share of costed tickets the backtest could actually evaluate."""
        denom = self.n_evaluated + self.n_skipped
        return (self.n_evaluated / denom) if denom else 0.0

    @property
    def accuracy(self) -> float:
        """Headline 'estimates land within ~X%' figure = 1 − MdAPE (floored)."""
        return max(0.0, 1.0 - self.overall_mdape)


def backtest(
    result: AttributionResult,
    work_items: Optional[list[WorkItem]] = None,
    *,
    min_history: int = 2,
) -> CalibrationReport:
    """Leave-one-out calibration of the class-mean forecast over realized spend.

    Only costed (cost > 0), classified (non-UNKNOWN) tickets are evaluated — those
    are the ones the forecast would actually estimate. A class needs at least
    `min_history` tickets to leave one out and still have something to predict
    from; tickets in thinner classes are reported as skipped, not guessed.

    When `work_items` are supplied, also runs an apples-to-apples comparison of
    size-conditioned vs class-mean estimates (see `_size_comparison`) so the
    "does size help?" question is answered with a measured number, not asserted.
    """
    by_class: dict[TaskClass, list[TicketRollup]] = defaultdict(list)
    for ru in result.rollups.values():
        if ru.cost_usd > 0 and ru.task_class != TaskClass.UNKNOWN:
            by_class[ru.task_class].append(ru)

    per_class: dict[TaskClass, ClassCalibration] = {}
    all_ape: list[float] = []
    all_hits: list[int] = []
    n_skipped = 0

    for tc, rus in by_class.items():
        if len(rus) < min_history:
            n_skipped += len(rus)
            continue

        costs = [r.cost_usd for r in rus]
        ape: list[float] = []
        signed: list[float] = []
        hits: list[int] = []
        for i, actual in enumerate(costs):
            others = costs[:i] + costs[i + 1:]
            pred = statistics.fmean(others)
            p90 = _percentile(sorted(others), 0.90)
            ape.append(abs(pred - actual) / actual)
            signed.append((pred - actual) / actual)
            hits.append(1 if actual <= p90 else 0)

        per_class[tc] = ClassCalibration(
            task_class=tc,
            n=len(costs),
            mape=statistics.fmean(ape),
            mdape=statistics.median(ape),
            bias=statistics.fmean(signed),
            within_p90=statistics.fmean(hits),
        )
        all_ape += ape
        all_hits += hits

    size_cmp = _size_comparison(result, work_items) if work_items else None

    if not all_ape:
        return CalibrationReport(0, n_skipped, 0.0, 0.0, 0.0, {}, size=size_cmp)

    return CalibrationReport(
        n_evaluated=len(all_ape),
        n_skipped=n_skipped,
        overall_mape=statistics.fmean(all_ape),
        overall_mdape=statistics.median(all_ape),
        overall_within_p90=statistics.fmean(all_hits),
        by_class=per_class,
        size=size_cmp,
    )


def _size_comparison(
    result: AttributionResult,
    work_items: list[WorkItem],
    *,
    min_fit: int = 3,
) -> Optional[SizeComparison]:
    """Leave-one-out: for each ticket with a size signal, predict it two ways from
    the *same* held-out training fold — the class mean, and a size ratio fit on
    the others — and compare errors. Holding the training set fixed isolates the
    effect of conditioning on size. Needs ≥ `min_fit` sized tickets in a class."""
    wi_by_id = {w.ticket_id: w for w in work_items}
    # class -> majority feature kind -> list[(size, cost)]
    by_class: dict[TaskClass, dict[str, list[tuple[float, float]]]] = defaultdict(
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
        by_class[ru.task_class][sf[0]].append((sf[1], ru.cost_usd))

    ape_class: list[float] = []
    ape_size: list[float] = []
    for _tc, by_kind in by_class.items():
        kind = max(by_kind, key=lambda k: len(by_kind[k]))
        pairs = by_kind[kind]
        if len(pairs) < min_fit:
            continue
        for i, (size_i, actual) in enumerate(pairs):
            others = pairs[:i] + pairs[i + 1:]
            costs = [c for _, c in others]
            size_sum = sum(s for s, _ in others)
            cost_sum = sum(costs)
            if size_i <= 0 or size_sum <= 0 or cost_sum <= 0:
                continue
            class_pred = statistics.fmean(costs)
            size_pred = size_i * (cost_sum / size_sum)
            ape_class.append(abs(class_pred - actual) / actual)
            ape_size.append(abs(size_pred - actual) / actual)

    if not ape_class:
        return None
    return SizeComparison(
        n=len(ape_class),
        mdape_class=statistics.median(ape_class),
        mdape_size=statistics.median(ape_size),
        mape_class=statistics.fmean(ape_class),
        mape_size=statistics.fmean(ape_size),
    )


def format_calibration(report: CalibrationReport) -> str:
    """Render a calibration report as a legible text block for the CLI."""
    if report.n_evaluated == 0:
        return (
            "Forecast calibration\n"
            "  Not enough realized history to backtest — every class has fewer than\n"
            f"  2 costed tickets ({report.n_skipped} skipped). Estimate accuracy is unproven on\n"
            "  this data; collect more spend before trusting the point estimate.\n"
        )

    lines = [
        "Forecast calibration (leave-one-out on realized spend)",
        f"  Evaluated {report.n_evaluated} tickets · {report.n_skipped} skipped "
        f"(too little class history) · coverage {report.coverage:.0%}",
        f"  Median estimate lands within ~{report.overall_mdape:.0%} of actual "
        f"(MAPE {report.overall_mape:.0%})",
        f"  Upper (p90) band held {report.overall_within_p90:.0%} of the time",
        "",
        "  By task class:",
    ]
    for tc in sorted(report.by_class, key=lambda c: report.by_class[c].n, reverse=True):
        c = report.by_class[tc]
        direction = "over" if c.bias > 0 else "under"
        lines.append(
            f"    {tc.value:<9} n={c.n:<3} MdAPE {c.mdape:>4.0%}  "
            f"MAPE {c.mape:>4.0%}  bias {abs(c.bias):>4.0%} {direction}  "
            f"p90-held {c.within_p90:>4.0%}"
        )

    s = report.size
    if s is not None:
        lines.append("")
        lines.append(f"  Size conditioning (on {s.n} tickets with a size signal):")
        verdict = (
            f"cuts median error {s.error_reduction:.0%} → use it"
            if s.improves else
            "no improvement on this data → stay on the class mean"
        )
        lines.append(
            f"    class-mean MdAPE {s.mdape_class:.0%} vs size-conditioned "
            f"{s.mdape_size:.0%} — {verdict}"
        )

    return "\n".join(lines) + "\n"
