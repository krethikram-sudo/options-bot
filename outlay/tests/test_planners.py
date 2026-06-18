"""Jira + Linear planner adapters, and that the branch join reaches their keys."""

from datetime import datetime
from pathlib import Path

from outlay.attribute import attribute
from outlay.ingest import parse_jira_issues, parse_linear_issues
from outlay.join import JoinEngine, TicketResolver
from outlay.models import FidelityTier, TaskClass, UsageEvent
from outlay.classify import classify

FIX = Path(__file__).parent.parent / "fixtures"


def _ev(branch):
    return UsageEvent(id="e", provider="anthropic", model="claude-opus-4-8",
                      ts=datetime(2026, 6, 1), branch=branch, session_id="s",
                      input_tokens=100_000)


# ---- Linear ----

def test_linear_parse_status_branch_estimate():
    items = {w.ticket_id: w for w in parse_linear_issues(FIX / "linear_issues.json")}
    assert items["ENG-201"].status == "done"
    assert items["ENG-202"].status == "in_progress"
    assert items["ENG-203"].status == "open"          # backlog
    assert items["ENG-201"].branch == "alice/eng-201-usage-export"
    assert items["ENG-201"].est_points == 5
    assert classify(items["ENG-201"]) == TaskClass.FEATURE


def test_linear_branch_join():
    work = parse_linear_issues(FIX / "linear_issues.json")
    eng = JoinEngine(work, resolver=TicketResolver(source="linear"))
    res = eng.join(_ev("alice/eng-201-usage-export"))
    assert res.ticket_id == "ENG-201" and res.fidelity == FidelityTier.BRANCH


# ---- Jira ----

def test_jira_parse_status_category_and_issuetype_label():
    items = {w.ticket_id: w for w in parse_jira_issues(FIX / "jira_issues.json")}
    assert items["OPS-301"].status == "done"
    assert items["OPS-302"].status == "in_progress"
    assert items["OPS-303"].status == "open"
    # issuetype folds into labels so classify can use it
    assert classify(items["OPS-301"]) == TaskClass.BUGFIX        # "Bug" issuetype
    assert items["OPS-302"].epic_id == "OPS-300"
    assert items["OPS-301"].est_points == 3


def test_jira_branch_join_uses_embedded_key():
    work = parse_jira_issues(FIX / "jira_issues.json")
    eng = JoinEngine(work, resolver=TicketResolver(source="jira"))
    res = eng.join(_ev("fix/OPS-301-crash"))
    assert res.ticket_id == "OPS-301" and res.fidelity == FidelityTier.BRANCH


def test_planner_attribution_end_to_end():
    work = parse_linear_issues(FIX / "linear_issues.json")
    events = [_ev("alice/eng-201-usage-export"), _ev("alice/eng-202-webhook-sig")]
    res = attribute(events, work, engine=JoinEngine(
        work, resolver=TicketResolver(source="linear")))
    assert {"ENG-201", "ENG-202"} <= set(res.rollups)
    assert res.ticket_coverage == 1.0
