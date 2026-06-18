"""Budget-vs-actual burndown — the original value prop made concrete.

The founding pitch: *build budgets from the scope of work, then hold spend within
guardrails.* Forecasting (`forecast.py`) gives the budget; attribution
(`attribute.py`) gives the actuals. This module is the third side: track spend
against a budget over a period, project the end-of-period total at the current
pace, and flag scopes trending over **before** they blow through — the guardrail.

Guardrails here are pace-based, not hard caps. A hard per-scope cap that binds
mid-period just stops work; a *projection* that says "at this burn rate this epic
lands 40% over by quarter-end" is what lets a lead act while there's still time.
Status:
  ok   — on pace to finish within budget
  warn — already spent, on pace to exceed (projected_end > limit)
  over — already past the limit
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from .attribute import AttributionResult
from .forecast import RoadmapForecast
from .models import WorkItem


@dataclass
class Budget:
    scope_type: str            # "epic" | "team" | "sprint" | "total"
    scope_id: str              # epic/team/sprint id, or "ALL" for total
    limit_usd: float
    period_start: datetime
    period_end: datetime
    label: str = ""


@dataclass
class BudgetStatus:
    budget: Budget
    spent_usd: float
    limit_usd: float
    pct_used: float
    fraction_elapsed: float
    projected_end_usd: float
    remaining_usd: float
    status: str                # "ok" | "warn" | "over"


def _scope_key(scope_type: str, ticket_scope: dict, team_id: Optional[str]) -> Optional[str]:
    if scope_type == "team":
        return team_id
    return ticket_scope.get(scope_type)


def track_budgets(
    result: AttributionResult,
    work_items: list[WorkItem],
    budgets: list[Budget],
    as_of: Optional[datetime] = None,
) -> list[BudgetStatus]:
    """Compute spend-vs-budget with a pace projection for each budget."""
    # ticket -> {epic, sprint} mapping for scoped rollups.
    tmap = {wi.ticket_id: {"epic": wi.epic_id, "sprint": wi.sprint_id}
            for wi in work_items}

    as_of = as_of or (max((r.ts for r in result.rows), default=datetime.utcnow()))

    out: list[BudgetStatus] = []
    for b in budgets:
        if b.scope_type == "total":
            spent = sum(r.cost_usd for r in result.rows)
        elif b.scope_type == "team":
            spent = sum(r.cost_usd for r in result.rows if r.team_id == b.scope_id)
        else:  # epic | sprint — derive from ticketed rollups
            spent = sum(
                ru.cost_usd for tid, ru in result.rollups.items()
                if _scope_key(b.scope_type, tmap.get(tid, {}), None) == b.scope_id
            )

        span = (b.period_end - b.period_start).total_seconds()
        elapsed = (as_of - b.period_start).total_seconds()
        frac = 0.0 if span <= 0 else max(0.0, min(1.0, elapsed / span))
        # Pace projection: extrapolate the run rate across the whole period.
        projected = spent / frac if frac > 0 else spent

        if spent > b.limit_usd:
            status = "over"
        elif projected > b.limit_usd:
            status = "warn"
        else:
            status = "ok"

        out.append(BudgetStatus(
            budget=b,
            spent_usd=round(spent, 4),
            limit_usd=b.limit_usd,
            pct_used=(spent / b.limit_usd) if b.limit_usd else 0.0,
            fraction_elapsed=round(frac, 4),
            projected_end_usd=round(projected, 4),
            remaining_usd=round(b.limit_usd - spent, 4),
            status=status,
        ))
    return out


def budget_from_forecast(
    forecast: RoadmapForecast,
    period_start: datetime,
    period_end: datetime,
    *,
    use_p90: bool = False,
    label: str = "Roadmap (auto)",
) -> Budget:
    """Derive a single total budget straight from the roadmap forecast, so you can
    track actuals against the scoped plan with no manual number. `use_p90` sets a
    conservative ceiling (the upper band) instead of the expected value."""
    limit = forecast.p90_usd if use_p90 else forecast.expected_usd
    return Budget(scope_type="total", scope_id="ALL", limit_usd=limit,
                  period_start=period_start, period_end=period_end, label=label)


def parse_budgets(records: list[dict]) -> list[Budget]:
    """Parse a budgets JSON file: list of
    {scope_type, scope_id, limit_usd, period_start, period_end, label?}."""
    def _ts(v):
        return datetime.fromisoformat(str(v).replace("Z", "+00:00")).replace(tzinfo=None)
    return [
        Budget(
            scope_type=r["scope_type"],
            scope_id=r.get("scope_id", "ALL"),
            limit_usd=float(r["limit_usd"]),
            period_start=_ts(r["period_start"]),
            period_end=_ts(r["period_end"]),
            label=r.get("label", ""),
        )
        for r in records
    ]
