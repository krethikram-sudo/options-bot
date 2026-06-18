"""The join engine — spend → unit of planned work. This is the IP.

Every existing gateway/observability/FinOps tool stops at an infra tag (API
key, span, model). ScopePilot reaches the ticket by resolving the git context a
coding agent runs in. The high-fidelity path is **branch name → ticket id**;
everything else degrades gracefully, and every result is stamped with the
fidelity tier it was established at so reports never over-claim.

Join precedence (best → worst):
  1. CALL    — the event was tagged with a ticket at call time (proxy metadata).
  2. BRANCH  — the event's branch parses to a ticket key, or matches a work
               item's recorded branch / PR.
  3. TEAM    — no ticket, but key→user→team is known.
  4. INVOICE — only the raw provider event; no team, no ticket.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Optional

from .models import FidelityTier, UsageEvent, WorkItem


@dataclass
class IdentityGraph:
    """Resolves the technical identifiers on a usage event to a human/team.

    In production this is fed by SSO/SCIM + provider key metadata; here it's a
    couple of plain dicts. Kept separate from the join so the fidelity logic
    doesn't care *how* identity was resolved.
    """

    key_to_user: dict[str, str] = field(default_factory=dict)
    user_to_team: dict[str, str] = field(default_factory=dict)

    def user_for(self, event: UsageEvent) -> Optional[str]:
        if event.user:
            return event.user
        if event.api_key_id and event.api_key_id in self.key_to_user:
            return self.key_to_user[event.api_key_id]
        return None

    def team_for(self, event: UsageEvent) -> Optional[str]:
        user = self.user_for(event)
        if user and user in self.user_to_team:
            return self.user_to_team[user]
        return None


# Default branch→ticket patterns. Order matters; first match wins. Designed for
# GitHub Issues (numeric) plus generic Jira/Linear-style project keys, since
# teams frequently mix conventions. All case-insensitive.
DEFAULT_BRANCH_PATTERNS: list[str] = [
    r"\b([A-Z][A-Z0-9]+-\d+)\b",          # PROJ-1234  (Jira/Linear style)
    r"(?:^|[/_-])gh[-_]?(\d+)\b",          # gh-123 / gh_123
    r"(?:^|[/_-])issue[-_]?(\d+)\b",       # issue-123
    r"(?:^|[/_-])#?(\d+)(?:[-_/]|$)",      # feature/123-... or fix/#123
]


@dataclass
class TicketResolver:
    """Parses ticket ids out of branch names.

    `source` controls how a bare number is canonicalized. For GitHub a branch
    `feature/123-add-auth` resolves to ticket id `GH-123`, matching how work
    items are keyed in `ingest.github_issues`.
    """

    source: str = "github"
    patterns: list[str] = field(default_factory=lambda: list(DEFAULT_BRANCH_PATTERNS))

    def __post_init__(self) -> None:
        self._compiled = [re.compile(p, re.IGNORECASE) for p in self.patterns]

    def _canonicalize(self, raw: str) -> str:
        if raw.isdigit():  # bare number from a numeric planner
            prefix = {"github": "GH", "linear": "LIN", "jira": "PROJ"}.get(
                self.source, "GH"
            )
            return f"{prefix}-{int(raw)}"
        return raw.upper()

    def from_branch(self, branch: Optional[str]) -> Optional[str]:
        if not branch:
            return None
        for rx in self._compiled:
            m = rx.search(branch)
            if m:
                return self._canonicalize(m.group(1))
        return None


@dataclass
class JoinResult:
    ticket_id: Optional[str]
    team_id: Optional[str]
    user: Optional[str]
    fidelity: FidelityTier


class JoinEngine:
    """Joins usage events to work items, producing a fidelity-tiered result."""

    def __init__(
        self,
        work_items: list[WorkItem],
        identity: Optional[IdentityGraph] = None,
        resolver: Optional[TicketResolver] = None,
    ) -> None:
        self.identity = identity or IdentityGraph()
        self.resolver = resolver or TicketResolver()
        self._by_ticket = {wi.ticket_id: wi for wi in work_items}
        # Reverse indexes for the BRANCH path.
        self._by_branch = {
            wi.branch: wi for wi in work_items if wi.branch
        }

    def _team_from_ticket(self, ticket_id: str) -> Optional[str]:
        wi = self._by_ticket.get(ticket_id)
        return wi.team_id if wi else None

    def join(self, event: UsageEvent) -> JoinResult:
        user = self.identity.user_for(event)
        team = self.identity.team_for(event)

        # 1. CALL — explicit ticket tag wins outright (only trust it if the
        #    ticket actually exists in the planning system).
        if event.explicit_ticket and event.explicit_ticket in self._by_ticket:
            return JoinResult(
                ticket_id=event.explicit_ticket,
                team_id=team or self._team_from_ticket(event.explicit_ticket),
                user=user,
                fidelity=FidelityTier.CALL,
            )

        # 2. BRANCH — resolve via branch→ticket parse, or a work item that
        #    recorded this exact branch.
        if event.branch:
            ticket = self.resolver.from_branch(event.branch)
            if ticket and ticket in self._by_ticket:
                return JoinResult(
                    ticket, team or self._team_from_ticket(ticket), user,
                    FidelityTier.BRANCH,
                )
            wi = self._by_branch.get(event.branch)
            if wi:
                return JoinResult(
                    wi.ticket_id, team or wi.team_id, user, FidelityTier.BRANCH
                )

        # 3. TEAM — no ticket, but we know who/what team.
        if team or user:
            return JoinResult(None, team, user, FidelityTier.TEAM)

        # 4. INVOICE — raw provider event only.
        return JoinResult(None, None, None, FidelityTier.INVOICE)
