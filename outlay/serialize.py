"""JSON serialization of the pipeline outputs.

The text report (`report.py`) is for a human reading it in 30 seconds. This is
the same content as a machine-readable dict — for a console dashboard, a CI gate,
or piping the coverage/accuracy/savings numbers somewhere. One schema, versioned,
so downstream consumers can rely on it.
"""

from __future__ import annotations

import json
from typing import Optional

from .attribute import AttributionResult
from .backtest import CalibrationReport
from .budget import BudgetStatus
from .forecast import Anomaly, ClassStats, RoadmapForecast
from .models import FidelityTier, TaskClass
from .policy import RoutingPolicy
from .recommend import Recommendation

SCHEMA_VERSION = "1.0"


def _r(x: float, places: int = 6) -> float:
    """Round to kill float noise in the emitted JSON."""
    return round(float(x), places)


def to_dict(
    result: AttributionResult,
    stats: dict[TaskClass, ClassStats],
    forecast: RoadmapForecast,
    anomalies: list[Anomaly],
    recs: list[Recommendation],
    *,
    calibration: Optional[CalibrationReport] = None,
    policy: Optional[RoutingPolicy] = None,
    budgets: Optional[list[BudgetStatus]] = None,
    window_days: Optional[int] = None,
) -> dict:
    """Assemble the full report as a JSON-serializable dict."""
    total = result.total_cost
    fid = result.cost_by_fidelity()

    out: dict = {
        "schema_version": SCHEMA_VERSION,
        "window_days": window_days,
        "spend": {
            "total_usd": _r(total),
            "attributed_to_ticket_usd": _r(result.attributed_to_ticket),
            "ticket_coverage": _r(result.ticket_coverage, 4),
            "by_fidelity_usd": {
                t.value: _r(fid.get(t, 0.0))
                for t in (FidelityTier.CALL, FidelityTier.BRANCH,
                          FidelityTier.TEAM, FidelityTier.INVOICE)
            },
        },
        "tickets": [
            {
                "ticket_id": ru.ticket_id,
                "task_class": ru.task_class.value,
                "status": ru.status,
                "cost_usd": _r(ru.cost_usd),
                "rework_iterations": ru.rework_iterations,
                "team_id": ru.team_id,
            }
            for ru in sorted(result.rollups.values(), key=lambda r: r.cost_usd, reverse=True)
        ],
        "class_stats": [
            {
                "task_class": st.task_class.value,
                "n": st.n,
                "mean_usd": _r(st.mean),
                "median_usd": _r(st.median),
                "p10_usd": _r(st.p10),
                "p90_usd": _r(st.p90),
                "std_usd": _r(st.std),
                "mean_rework": _r(st.mean_rework, 3),
            }
            for st in sorted(stats.values(), key=lambda s: s.mean, reverse=True)
        ],
        "forecast": {
            "expected_usd": _r(forecast.expected_usd),
            "low_usd": _r(forecast.low_usd),
            "high_usd": _r(forecast.high_usd),
            "conservative_p90_usd": _r(forecast.p90_usd),
            "items_costed": forecast.items_costed,
            "items_unclassified": forecast.items_unclassified,
            "by_class_usd": {tc.value: _r(v) for tc, v in forecast.by_class.items()},
            "items": [
                {
                    "ticket_id": it.ticket_id,
                    "task_class": it.task_class.value,
                    "expected_usd": _r(it.expected_usd),
                    "low_usd": _r(it.low_usd),
                    "high_usd": _r(it.high_usd),
                    "basis": it.basis,
                    "costable": it.costable,
                }
                for it in forecast.items
            ],
        },
        "anomalies": [
            {
                "ticket_id": a.ticket_id,
                "task_class": a.task_class.value,
                "cost_usd": _r(a.cost_usd),
                "class_median_usd": _r(a.class_median),
                "ratio": _r(a.ratio, 3),
            }
            for a in anomalies
        ],
        "recommendations": [
            {
                "task_class": r.task_class.value,
                "incumbent_model": r.incumbent_model,
                "candidate_model": r.candidate_model,
                "observed_usd": _r(r.observed_monthly_usd),
                "projected_usd": _r(r.projected_monthly_usd),
                "projected_savings_usd": _r(r.projected_savings_usd),
                "confidence": r.confidence,
                "rationale": r.rationale,
            }
            for r in recs
        ],
    }

    if calibration is not None:
        c = calibration
        cal: dict = {
            "n_evaluated": c.n_evaluated,
            "n_skipped": c.n_skipped,
            "coverage": _r(c.coverage, 4),
            "mdape": _r(c.overall_mdape, 4),
            "mape": _r(c.overall_mape, 4),
            "within_p90": _r(c.overall_within_p90, 4),
            "accuracy": _r(c.accuracy, 4),
            "by_class": [
                {
                    "task_class": cc.task_class.value,
                    "n": cc.n,
                    "mdape": _r(cc.mdape, 4),
                    "mape": _r(cc.mape, 4),
                    "bias": _r(cc.bias, 4),
                    "within_p90": _r(cc.within_p90, 4),
                }
                for cc in sorted(c.by_class.values(), key=lambda x: x.n, reverse=True)
            ],
            "size": None,
        }
        if c.size is not None:
            s = c.size
            cal["size"] = {
                "n": s.n,
                "mdape_class": _r(s.mdape_class, 4),
                "mdape_size": _r(s.mdape_size, 4),
                "mape_class": _r(s.mape_class, 4),
                "mape_size": _r(s.mape_size, 4),
                "improves": s.improves,
                "error_reduction": _r(s.error_reduction, 4),
            }
        out["calibration"] = cal

    if policy is not None:
        out["savings"] = {
            "enforce_now_usd": _r(policy.enforced_savings_usd),
            "shadow_usd": _r(policy.shadow_savings_usd),
        }
        out["policy"] = policy.to_dict()

    if budgets:
        out["budgets"] = [
            {
                "label": s.budget.label or f"{s.budget.scope_type}:{s.budget.scope_id}",
                "scope_type": s.budget.scope_type,
                "scope_id": s.budget.scope_id,
                "status": s.status,
                "spent_usd": _r(s.spent_usd),
                "limit_usd": _r(s.limit_usd),
                "pct_used": _r(s.pct_used, 4),
                "fraction_elapsed": _r(s.fraction_elapsed, 4),
                "projected_end_usd": _r(s.projected_end_usd),
                "remaining_usd": _r(s.remaining_usd),
            }
            for s in budgets
        ]

    return out


def to_json(*args, indent: int = 2, **kwargs) -> str:
    """`to_dict` rendered as a JSON string."""
    return json.dumps(to_dict(*args, **kwargs), indent=indent)
