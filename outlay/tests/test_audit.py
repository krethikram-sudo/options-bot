"""Join-convention auditor: PR signal scoring + per-repo/aggregate rates."""

from outlay.audit import GitHubAudit, pr_signals
from outlay.join import TicketResolver

R = TicketResolver(source="github")


def test_pr_signal_closing_keyword():
    ref, br = pr_signals({"title": "Fix crash", "body": "Closes #123"}, R)
    assert ref is True


def test_pr_signal_bare_reference():
    ref, _ = pr_signals({"title": "Improve logging (#42)", "body": ""}, R)
    assert ref is True


def test_pr_signal_no_reference():
    ref, br = pr_signals({"title": "tidy", "body": "no ticket here"}, R)
    assert ref is False and br is False


def test_pr_signal_branch_resolves():
    _, br = pr_signals({"title": "x", "body": "", "head": {"ref": "feature/123-add"}}, R)
    assert br is True


def test_audit_repo_rates_with_canned_transport():
    prs = [
        {"merged_at": "2026-06-01", "title": "a", "body": "Fixes #1", "head": {"ref": "fix/1"}},
        {"merged_at": "2026-06-02", "title": "b (#2)", "body": "", "head": {"ref": "patchwork"}},
        {"merged_at": "2026-06-03", "title": "c", "body": "no ref", "head": {"ref": "scratch"}},
        {"title": "unmerged", "body": "Closes #9", "head": {"ref": "x"}},  # not merged -> ignored
    ]

    def transport(method, url, headers, body):
        assert headers["authorization"] == "Bearer tok"
        return prs  # single page

    a = GitHubAudit(token="tok", transport=transport).audit_repo("o", "r")
    assert a.merged_prs == 3                     # unmerged PR excluded
    assert abs(a.pr_issue_link_rate - 2/3) < 1e-9   # PRs 1 and 2 reference issues
    assert abs(a.branch_resolve_rate - 1/3) < 1e-9  # only fix/1 resolves cleanly
    assert abs(a.joinable_rate - 2/3) < 1e-9        # union of the two signals


def test_audit_query_aggregates():
    search_page = {"items": [{"full_name": "o/r1"}, {"full_name": "o/r2"}]}
    prs = [{"merged_at": "x", "title": "t", "body": "Closes #1", "head": {"ref": "fix/1"}}]

    def transport(method, url, headers, body):
        return search_page if "search/repositories" in url else prs

    audits, agg = GitHubAudit(token="tok", transport=transport).audit_query("q", max_repos=2)
    assert agg["repos_scored"] == 2
    assert agg["total_merged_prs"] == 2
    assert agg["joinable_rate"] == 1.0
