"""Joinability audit — does the ScopePilot join *convention* hold in the wild?

We can't see other teams' agent spend, so we can't measure end-to-end ticket
coverage on someone else's public repo. What we *can* measure at scale is the
**precondition** the whole product rests on: in real repositories, do engineers
tie their work to tickets in a way the resolver catches?

For public/OSS repos the meaningful signal is the **PR→issue link**, not the
branch name: contributors branch inside their own forks (invisible to us) and
land work as pull requests, and a disciplined team writes "Fixes #123" / links a
closing issue. That same PR→issue path is also what survives **detached-HEAD /
remote-agent** sessions (where `gitBranch` is just `HEAD`), so this audit
validates exactly the join path the real-world `HEAD` failure mode demands.

What this proves and doesn't:
  - HIGH PR→issue rate across many repos  → the join *can* fire in the wild; the
    moat mechanism is sound. (A necessary precondition.)
  - It does NOT prove ScopePilot works end-to-end — that still needs a real
    team's agent telemetry joined to their tracker. Public data gets us the
    precondition cheaply and at scale; it is not a substitute for a design
    partner's real spend.

Run locally (needs GITHUB_TOKEN):

    python -m scopepilot.audit --query "language:python stars:>200 pushed:>2026-05-01" \
        --max-repos 100 --prs-per-repo 50
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from statistics import fmean
from typing import Optional
from urllib.parse import urlencode

from .ingest._http import Transport, get_json
from .join import TicketResolver

# "Closes #123" / "fixes #45" / "resolved #7" — the explicit closing keywords.
_CLOSES = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b[\s:]+#(\d+)", re.IGNORECASE)
# A bare "#123" issue reference anywhere in the PR title/body.
_BARE = re.compile(r"#(\d+)\b")


@dataclass
class RepoAudit:
    full_name: str
    merged_prs: int
    pr_issue_link_rate: float    # merged PRs that close/reference an issue
    branch_resolve_rate: float   # merged PRs whose head branch resolves to a key
    joinable_rate: float         # either signal present


def pr_signals(pr: dict, resolver: TicketResolver) -> tuple[bool, bool]:
    """(references_issue, branch_resolves) for one PR."""
    text = f"{pr.get('title') or ''}\n{pr.get('body') or ''}"
    references = bool(_CLOSES.search(text)) or bool(_BARE.search(text))
    head_ref = (pr.get("head") or {}).get("ref")
    branch_ok = resolver.from_branch(head_ref) is not None
    return references, branch_ok


class GitHubAudit:
    """Pulls merged PRs per repo and scores joinability. Network behind the
    transport seam so the scoring is unit-tested offline."""

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = "https://api.github.com",
        transport: Optional[Transport] = None,
        resolver: Optional[TicketResolver] = None,
    ) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.base_url = base_url.rstrip("/")
        self._transport = transport
        self.resolver = resolver or TicketResolver()

    def _headers(self) -> dict:
        h = {"accept": "application/vnd.github+json", "user-agent": "scopepilot-audit"}
        if self.token:
            h["authorization"] = f"Bearer {self.token}"
        return h

    def list_merged_prs(self, owner: str, repo: str, limit: int = 50) -> list[dict]:
        out: list[dict] = []
        page = 1
        while len(out) < limit:
            params = {"state": "closed", "per_page": 100, "page": page,
                      "sort": "updated", "direction": "desc"}
            url = f"{self.base_url}/repos/{owner}/{repo}/pulls?{urlencode(params)}"
            rows = get_json(url, self._headers(), self._transport)
            if not isinstance(rows, list) or not rows:
                break
            out.extend(r for r in rows if r.get("merged_at"))
            if len(rows) < 100:
                break
            page += 1
        return out[:limit]

    def audit_repo(self, owner: str, repo: str, limit: int = 50) -> RepoAudit:
        prs = self.list_merged_prs(owner, repo, limit)
        if not prs:
            return RepoAudit(f"{owner}/{repo}", 0, 0.0, 0.0, 0.0)
        refs = brs = joins = 0
        for pr in prs:
            r, b = pr_signals(pr, self.resolver)
            refs += r
            brs += b
            joins += (r or b)
        n = len(prs)
        return RepoAudit(f"{owner}/{repo}", n, refs / n, brs / n, joins / n)

    def search_repos(self, query: str, max_repos: int = 50) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        page = 1
        while len(out) < max_repos:
            params = {"q": query, "per_page": 100, "page": page}
            url = f"{self.base_url}/search/repositories?{urlencode(params)}"
            resp = get_json(url, self._headers(), self._transport)
            items = resp.get("items", []) if isinstance(resp, dict) else []
            if not items:
                break
            for it in items:
                full = it.get("full_name", "")
                if "/" in full:
                    o, _, r = full.partition("/")
                    out.append((o, r))
            if len(items) < 100:
                break
            page += 1
        return out[:max_repos]

    def audit_query(self, query: str, max_repos: int = 50,
                    prs_per_repo: int = 50) -> tuple[list[RepoAudit], dict]:
        repos = self.search_repos(query, max_repos)
        audits = [self.audit_repo(o, r, prs_per_repo) for o, r in repos]
        scored = [a for a in audits if a.merged_prs > 0]
        agg = {
            "repos_scored": len(scored),
            "total_merged_prs": sum(a.merged_prs for a in scored),
            "pr_issue_link_rate": fmean([a.pr_issue_link_rate for a in scored]) if scored else 0.0,
            "branch_resolve_rate": fmean([a.branch_resolve_rate for a in scored]) if scored else 0.0,
            "joinable_rate": fmean([a.joinable_rate for a in scored]) if scored else 0.0,
        }
        return audits, agg


def main(argv: list[str] | None = None) -> int:
    import argparse

    p = argparse.ArgumentParser(description="ScopePilot join-convention audit (public repos)")
    p.add_argument("--query", required=True, help="GitHub repo search query")
    p.add_argument("--max-repos", type=int, default=50)
    p.add_argument("--prs-per-repo", type=int, default=50)
    args = p.parse_args(argv)

    audits, agg = GitHubAudit().audit_query(args.query, args.max_repos, args.prs_per_repo)
    print(f"{'repo':<45}{'PRs':>5}{'issue-link':>12}{'branch':>9}{'joinable':>10}")
    for a in sorted(audits, key=lambda x: x.joinable_rate, reverse=True):
        if a.merged_prs:
            print(f"{a.full_name[:44]:<45}{a.merged_prs:>5}"
                  f"{a.pr_issue_link_rate:>11.0%}{a.branch_resolve_rate:>9.0%}"
                  f"{a.joinable_rate:>10.0%}")
    print("-" * 81)
    print(f"{'AGGREGATE ('+str(agg['repos_scored'])+' repos, '+str(agg['total_merged_prs'])+' merged PRs)':<45}"
          f"{'':>5}{agg['pr_issue_link_rate']:>11.0%}{agg['branch_resolve_rate']:>9.0%}"
          f"{agg['joinable_rate']:>10.0%}")
    print("\nPR→issue link rate is the headline: the fraction of real merged work that "
          "ties to a ticket — i.e., would be attributable. This is the join precondition, "
          "not end-to-end spend coverage (that needs a real team's agent telemetry).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
