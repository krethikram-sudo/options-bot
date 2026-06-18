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

from .attribute import AttributionResult, TicketRollup
from .forecast import _percentile
from .models import TaskClass


@dataclass
class ClassCalibration:
    task_class: TaskClass
    n: int              # tickets evaluated in this class
    mape: float         # mean absolute percentage error
    mdape: float        # median absolute percentage error
    bias: float         # mean signed pct error; + = over-forecast, - = under
    within_p90: float   # fraction of actuals at or below the LOO p90 band


@dataclass
class CalibrationReport:
    n_evaluated: int
    n_skipped: int      # tickets whose class had < min_history → not predictable
    overall_mape: float
    overall_mdape: float
    overall_within_p90: float
    by_class: dict[TaskClass, ClassCalibration] = field(default_factory=dict)

    @property
    def coverage(self) -> float:
        """Share of costed tickets the backtest could actually evaluate."""
        denom = self.n_evaluated + self.n_skipped
        return (self.n_evaluated / denom) if denom else 0.0

    @property
    def accuracy(self) -> float:
        """Headline 'estimates land within ~X%' figure = 1 − MdAPE (floored)."""
        return max(0.0, 1.0 - self.overall_mdape)


def backtest(result: AttributionResult, *, min_history: int = 2) -> CalibrationReport:
    """Leave-one-out calibration of the class-mean forecast over realized spend.

    Only costed (cost > 0), classified (non-UNKNOWN) tickets are evaluated — those
    are the ones the forecast would actually estimate. A class needs at least
    `min_history` tickets to leave one out and still have something to predict
    from; tickets in thinner classes are reported as skipped, not guessed.
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

    if not all_ape:
        return CalibrationReport(0, n_skipped, 0.0, 0.0, 0.0, {})

    return CalibrationReport(
        n_evaluated=len(all_ape),
        n_skipped=n_skipped,
        overall_mape=statistics.fmean(all_ape),
        overall_mdape=statistics.median(all_ape),
        overall_within_p90=statistics.fmean(all_hits),
        by_class=per_class,
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
    return "\n".join(lines) + "\n"
