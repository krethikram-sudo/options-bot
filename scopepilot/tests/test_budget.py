"""Budget-vs-actual burndown: scope rollups, pace projection, status gating."""

from datetime import datetime
from pathlib import Path

from scopepilot.attribute import attribute
from scopepilot.budget import (
    Budget,
    budget_from_forecast,
    parse_budgets,
    track_budgets,
)
from scopepilot.forecast import RoadmapForecast
from scopepilot.join import JoinEngine
from scopepilot.models import UsageEvent, WorkItem

FIX = Path(__file__).parent.parent / "fixtures"

WORK = [
    WorkItem("GH-1", "github", labels=["bug"], branch="fix/1", epic_id="E1",
             team_id="platform", status="done"),
    WorkItem("GH-2", "github", labels=["feature"], branch="feat/2", epic_id="E1",
             team_id="growth", status="done"),
]
# GH-1 -> $5.00 (1M input @ Opus $5); GH-2 -> $1.00 (200k input).
EVENTS = [
    UsageEvent("a", "anthropic", "claude-opus-4-8", datetime(2026, 6, 6),
               branch="fix/1", session_id="s1", input_tokens=1_000_000),
    UsageEvent("b", "anthropic", "claude-opus-4-8", datetime(2026, 6, 6),
               branch="feat/2", session_id="s2", input_tokens=200_000),
]
PERIOD = (datetime(2026, 6, 1), datetime(2026, 6, 11))   # 10-day period
AS_OF = datetime(2026, 6, 6)                              # 50% elapsed


def _result():
    return attribute(EVENTS, WORK, engine=JoinEngine(WORK))


def test_total_budget_warn_on_pace():
    b = Budget("total", "ALL", 10.0, *PERIOD)
    s = track_budgets(_result(), WORK, [b], as_of=AS_OF)[0]
    assert s.spent_usd == 6.0
    assert s.fraction_elapsed == 0.5
    assert s.projected_end_usd == 12.0      # 6.0 / 0.5
    assert s.status == "warn"               # spent < limit, but on pace to exceed


def test_epic_budget_over():
    b = Budget("epic", "E1", 4.0, *PERIOD)
    s = track_budgets(_result(), WORK, [b], as_of=AS_OF)[0]
    assert s.spent_usd == 6.0               # both tickets roll up to E1
    assert s.status == "over"               # already past the limit


def test_team_budget_ok():
    b = Budget("team", "platform", 20.0, *PERIOD)
    s = track_budgets(_result(), WORK, [b], as_of=AS_OF)[0]
    assert s.spent_usd == 5.0               # only GH-1 is platform
    assert s.projected_end_usd == 10.0      # under the limit even projected
    assert s.status == "ok"


def test_budget_from_forecast():
    fc = RoadmapForecast(expected_usd=7.0, p90_usd=9.0, items_costed=3,
                         items_unclassified=0)
    assert budget_from_forecast(fc, *PERIOD).limit_usd == 7.0
    assert budget_from_forecast(fc, *PERIOD, use_p90=True).limit_usd == 9.0


def test_parse_budgets_fixture():
    budgets = parse_budgets(__import__("json").loads((FIX / "budgets.json").read_text()))
    assert {b.scope_type for b in budgets} == {"total", "epic", "team"}
    assert any(b.scope_id == "Q3 stability" for b in budgets)
