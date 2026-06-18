"""The join engine — the IP. Cover every fidelity tier and the branch parser."""

from datetime import datetime

from scopepilot.join import IdentityGraph, JoinEngine, TicketResolver
from scopepilot.models import FidelityTier, UsageEvent, WorkItem


def _wi(tid, **kw):
    return WorkItem(ticket_id=tid, source="github", **kw)


def _ev(**kw):
    return UsageEvent(id="e", provider="anthropic", model="claude-opus-4-8",
                      ts=datetime(2026, 6, 1), **kw)


WORK = [
    _wi("GH-101", branch="fix/101-x", team_id="platform"),
    _wi("PROJ-7", team_id="growth"),
]


def test_branch_resolver_numeric_github():
    r = TicketResolver(source="github")
    assert r.from_branch("feature/123-add-auth") == "GH-123"
    assert r.from_branch("fix/#456-thing") == "GH-456"
    assert r.from_branch("kr/gh-789-thing") == "GH-789"


def test_branch_resolver_jira_style_key():
    r = TicketResolver(source="github")
    assert r.from_branch("bugfix/PROJ-7-crash") == "PROJ-7"


def test_call_fidelity_wins_with_valid_ticket():
    eng = JoinEngine(WORK)
    res = eng.join(_ev(explicit_ticket="PROJ-7", branch="fix/101-x"))
    assert res.fidelity == FidelityTier.CALL
    assert res.ticket_id == "PROJ-7"


def test_call_ignored_if_ticket_unknown():
    # An explicit tag for a non-existent ticket must not be trusted blindly;
    # falls through to the branch path.
    eng = JoinEngine(WORK)
    res = eng.join(_ev(explicit_ticket="GH-999", branch="fix/101-x"))
    assert res.fidelity == FidelityTier.BRANCH
    assert res.ticket_id == "GH-101"


def test_branch_fidelity():
    eng = JoinEngine(WORK)
    res = eng.join(_ev(branch="fix/101-x"))
    assert res.fidelity == FidelityTier.BRANCH
    assert res.ticket_id == "GH-101"
    assert res.team_id == "platform"


def test_team_fidelity_when_no_branch():
    ident = IdentityGraph(key_to_user={"k1": "bob@acme.dev"},
                          user_to_team={"bob@acme.dev": "growth"})
    eng = JoinEngine(WORK, identity=ident)
    res = eng.join(_ev(api_key_id="k1"))
    assert res.fidelity == FidelityTier.TEAM
    assert res.ticket_id is None
    assert res.team_id == "growth"


def test_invoice_fidelity_when_nothing_known():
    eng = JoinEngine(WORK)
    res = eng.join(_ev())
    assert res.fidelity == FidelityTier.INVOICE
    assert res.ticket_id is None and res.team_id is None


def test_unresolvable_branch_degrades_not_crashes():
    eng = JoinEngine(WORK)
    res = eng.join(_ev(branch="scratch/experiment"))
    assert res.fidelity == FidelityTier.INVOICE
