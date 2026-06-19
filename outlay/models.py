"""Core data model for Outlay's attribution pipeline.

Three record types and two enums. The whole design hinges on one idea the rest
of the market doesn't capture: every attributed cost carries a **fidelity tier**
that states *how confident* the spend→work join is. A finance owner will trust
"team-level, ±15%"; they will never forgive a confident per-ticket number that
turns out to be a silent guess. So fidelity is a first-class field, not a
footnote.

Fields marked ★ in the build plan (cache token split, branch, session,
fidelity) are exactly the ones competitors either don't record or can't join
on — they are why this attribution can reach the ticket and they can't.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Optional


class FidelityTier(str, Enum):
    """How the spend→work join was established, best → worst.

    The number on a report is only as trustworthy as its weakest contributing
    tier, so we surface a per-row tier and let reports aggregate honestly.
    """

    CALL = "call"        # event carried an explicit ticket tag (e.g. proxy metadata)
    BRANCH = "branch"    # event's git branch resolved to a ticket
    TEAM = "team"        # only key→user→team known; no ticket
    INVOICE = "invoice"  # only provider-level total; no team/ticket

    @property
    def rank(self) -> int:
        return {"call": 0, "branch": 1, "team": 2, "invoice": 3}[self.value]

    @property
    def has_ticket(self) -> bool:
        return self in (FidelityTier.CALL, FidelityTier.BRANCH)


class TaskClass(str, Enum):
    """Engineering work buckets. Cost distributions are learned per class, and
    routing policy is recommended per class — never per individual ticket,
    which is as unpredictable to cost as it is to estimate in hours."""

    BUGFIX = "bugfix"
    FEATURE = "feature"
    REFACTOR = "refactor"
    TEST = "test"
    CHORE = "chore"        # docs, deps, config, formatting
    UNKNOWN = "unknown"


@dataclass
class UsageEvent:
    """One billable LLM/coding-agent interaction.

    Token fields are kept *split* — cache reads bill at ~0.1× and cache writes
    at ~1.25× of base input, so collapsing them into one `input_tokens` number
    (as naive trackers do) overstates cached workloads by 5–10×.
    """

    id: str
    provider: str            # "anthropic"
    model: str               # canonical model id, e.g. "claude-sonnet-4-6"
    ts: datetime
    input_tokens: int = 0    # uncached input only
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    # Attribution signals (any may be absent — that's what drives fidelity).
    api_key_id: Optional[str] = None
    user: Optional[str] = None         # resolved actor (email/handle)
    branch: Optional[str] = None       # git branch the agent ran on
    session_id: Optional[str] = None   # agent session / run id
    explicit_ticket: Optional[str] = None  # ticket tagged at call time (proxy)

    @property
    def total_tokens(self) -> int:
        return (
            self.input_tokens
            + self.output_tokens
            + self.cache_read_tokens
            + self.cache_write_tokens
        )


@dataclass
class WorkItem:
    """A unit of planned work from the planning system (GitHub Issue in P0)."""

    ticket_id: str           # canonical key, e.g. "GH-1234" or "PROJ-12"
    source: str              # "github" | "jira" | "linear" | "plan"
    title: str = ""
    description: str = ""     # body text — used to classify planned work pre-build
    status: str = "open"     # "open" | "in_progress" | "done"
    labels: list[str] = field(default_factory=list)
    epic_id: Optional[str] = None
    sprint_id: Optional[str] = None
    est_points: Optional[float] = None
    team_id: Optional[str] = None
    branch: Optional[str] = None     # linked branch, if the planner records it
    pr_number: Optional[int] = None
    diff_added: int = 0
    diff_removed: int = 0
    opened_at: Optional[datetime] = None
    merged_at: Optional[datetime] = None

    @property
    def is_open(self) -> bool:
        return self.status != "done"

    @property
    def diff_size(self) -> int:
        return self.diff_added + self.diff_removed


@dataclass
class Attribution:
    """The join output: one usage event costed and tied to work (or not)."""

    usage_event_id: str
    cost_usd: float
    fidelity: FidelityTier
    model: str
    ts: datetime
    ticket_id: Optional[str] = None
    team_id: Optional[str] = None
    user: Optional[str] = None
    task_class: TaskClass = TaskClass.UNKNOWN
