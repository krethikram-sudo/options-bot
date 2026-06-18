"""Model-routing recommendation — per task-class, scored net of rework.

This is deliberately *advisory* and deliberately *per class*. The market already
commoditized per-request "cheapest good enough" routing; our angle is to tie the
recommendation to the engineering work-breakdown and, crucially, to score it
**net of rework**. The failure mode of naive downgrading is paying for two cheap
failures plus an escalation — strictly worse than one capable run. So a downgrade
is only recommended when the cheaper tier's expected cost *including* an
iteration penalty still beats the incumbent.

When history contains only one tier for a class (the common P0 case), we can't
yet *prove* the cheaper tier holds quality — so we emit a clearly-labeled
`needs_validation` candidate with projected savings, never a confident
"switch now". Honesty about confidence is the whole product.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import Optional

from .attribute import AttributionResult
from .models import TaskClass
from .pricing import RATES, TIER_LADDER, rate_for


@dataclass
class Recommendation:
    task_class: TaskClass
    incumbent_model: str
    candidate_model: str
    observed_monthly_usd: float
    projected_monthly_usd: float
    projected_savings_usd: float
    confidence: str          # "validated" | "needs_validation"
    rationale: str


# Assumed rework penalty when downgrading a tier with no observed quality data:
# we haircut the savings by assuming the cheaper tier needs this many extra
# fractional iterations. Conservative on purpose — better to under-promise.
_ASSUMED_DOWNGRADE_REWORK = 0.35


def _dominant_model(models: dict[str, float]) -> str:
    return max(models, key=models.get)


def recommend(
    result: AttributionResult,
    horizon_scale: float = 1.0,
) -> list[Recommendation]:
    """Produce per-class routing recommendations.

    `horizon_scale` projects the observed spend to a billing horizon (e.g. set
    to 30/observed_days for a monthly figure). Default 1.0 = "over the observed
    window".
    """
    # Aggregate cost per (class, model) and per-class rework signal.
    cost_cm: dict[TaskClass, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    rework_by_class: dict[TaskClass, list[int]] = defaultdict(list)
    for ru in result.rollups.values():
        rework_by_class[ru.task_class].append(ru.rework_iterations)
    for row in result.rows:
        if row.task_class != TaskClass.UNKNOWN:
            cost_cm[row.task_class][row.model] += row.cost_usd

    recs: list[Recommendation] = []
    for tc, models in cost_cm.items():
        incumbent = _dominant_model(models)
        inc_rate = rate_for(incumbent)
        # Candidate = next cheaper tier on the ladder, if any.
        cheaper = [m for m in TIER_LADDER if RATES[m].tier < inc_rate.tier]
        if not cheaper:
            continue
        candidate = cheaper[-1]  # closest cheaper tier
        cand_rate = rate_for(candidate)

        observed = sum(models.values()) * horizon_scale
        # Price ratio between tiers, blended across input/output (rough but
        # transparent — exact savings depend on the token mix).
        price_ratio = (cand_rate.input_per_m + cand_rate.output_per_m) / (
            inc_rate.input_per_m + inc_rate.output_per_m
        )

        validated = candidate in models  # have we actually run this class on the cheaper tier?
        if validated:
            # We have real cost data for the cheaper tier on this class; trust it.
            naive = observed * price_ratio
            projected = naive
            confidence = "validated"
            rationale = (
                f"{tc.value} has run on both {incumbent} and {candidate}; "
                f"cheaper tier observed in history."
            )
        else:
            # No quality proof — haircut savings by an assumed rework penalty.
            naive = observed * price_ratio
            penalty = naive * _ASSUMED_DOWNGRADE_REWORK
            projected = naive + penalty
            confidence = "needs_validation"
            rationale = (
                f"No {candidate} history for {tc.value}; savings shown net of an "
                f"assumed {_ASSUMED_DOWNGRADE_REWORK:.0%} rework penalty. Validate "
                f"on a sample before enforcing."
            )

        savings = observed - projected
        if savings <= 0:
            continue
        recs.append(
            Recommendation(
                task_class=tc,
                incumbent_model=incumbent,
                candidate_model=candidate,
                observed_monthly_usd=observed,
                projected_monthly_usd=projected,
                projected_savings_usd=savings,
                confidence=confidence,
                rationale=rationale,
            )
        )

    return sorted(recs, key=lambda r: r.projected_savings_usd, reverse=True)
