"""Cross-source linkage — recover ticket attribution from PR/commit closing refs,
so teams that don't put ticket ids in branch names still get a high coverage."""

from datetime import datetime

from outlay.ingest import parse_github_issues
from outlay.join import JoinEngine
from outlay.link import link_branches, parse_closing_refs
from outlay.models import FidelityTier, UsageEvent, WorkItem


def _ev(branch):
    return UsageEvent(id="e", provider="anthropic", model="claude-opus-4-8",
                      ts=datetime(2026, 6, 20), branch=branch, input_tokens=1000)


def test_parse_closing_refs():
    assert parse_closing_refs("Closes #123") == ["GH-123"]
    assert parse_closing_refs("fixes PROJ-45 and resolves #7") == ["PROJ-45", "GH-7"]
    # bare key in a commit subject is picked up; a bare #n without a keyword is not
    assert parse_closing_refs("PROJ-12: refactor") == ["PROJ-12"]
    assert parse_closing_refs("see #99 for context") == []
    assert parse_closing_refs("") == []
    # de-duplicated, order-preserving
    assert parse_closing_refs("fixes #1, closes #1, PROJ-2") == ["GH-1", "PROJ-2"]


def test_link_branches_stamps_branch_from_pr():
    work = [WorkItem(ticket_id="GH-123", source="github", status="done"),
            WorkItem(ticket_id="PROJ-45", source="github", status="done")]
    prs = [{"number": 10, "head_ref": "alice/quick-fix", "body": "Closes #123"},
           {"number": 11, "branch": "feat/new-billing", "title": "fixes PROJ-45"}]
    link_branches(work, prs)
    by = {w.ticket_id: w for w in work}
    assert by["GH-123"].branch == "alice/quick-fix" and by["GH-123"].pr_number == 10
    assert by["PROJ-45"].branch == "feat/new-billing"


def test_link_does_not_overwrite_explicit_branch():
    work = [WorkItem(ticket_id="GH-1", source="github", branch="real/branch")]
    link_branches(work, [{"head_ref": "other", "body": "closes #1"}])
    assert work[0].branch == "real/branch"   # explicit branch wins


def test_recovers_attribution_end_to_end():
    """A branch with no ticket id resolves once the PR link is harvested."""
    work = [WorkItem(ticket_id="GH-123", source="github", status="done")]
    # before linkage: event on a non-ticket branch can't resolve
    assert JoinEngine(work).join(_ev("alice/quick-fix")).fidelity == FidelityTier.INVOICE
    link_branches(work, [{"number": 10, "head_ref": "alice/quick-fix", "body": "Closes #123"}])
    res = JoinEngine(work).join(_ev("alice/quick-fix"))
    assert res.ticket_id == "GH-123" and res.fidelity == FidelityTier.BRANCH


def test_combined_export_links_through_parse_github_issues():
    payload = {
        "issues": [{"number": 123, "title": "Add SSO", "state": "closed"}],
        "pulls": [{"number": 9, "head_ref": "kr/sso-stuff", "body": "Closes #123"}],
    }
    items = parse_github_issues(payload)
    assert items[0].ticket_id == "GH-123" and items[0].branch == "kr/sso-stuff"
    # and a plain issues export (no pulls) is unaffected
    plain = parse_github_issues({"issues": [{"number": 5, "title": "x"}]})
    assert plain[0].branch is None
