"""Enforcement tier — turn advisory recommendations into a routing policy the
ModelPilot proxy can act on.

The advisory report tells a human "feature work is over-served on Opus." This
module turns that into a machine-applicable policy and, crucially, gates it:

  - `validated` recommendations  → ENFORCE  (actually lower the floor)
  - `needs_validation` recs      → SHADOW   (log the delta, change no traffic)

You never enforce a downgrade you haven't proven. Shadow mode is how a candidate
*earns* enforcement: run it alongside production, accumulate cheaper-tier
outcomes, and it graduates to `validated` on its own data.

### How it composes with ModelPilot (the contract)

ModelPilot routes by *request category* with a capability-ladder floor
(0=haiku … 3=fable; `modelpilot/taxonomy.py`) and only ever moves a request
*down* to the floor, never above the caller's model, with a brittle-call guard
that can veto. ScopePilot adds a second, orthogonal floor keyed by *engineering
task-class* (resolved from the request's branch/ticket metadata the proxy
already stamps):

    binding_floor = min(category_floor, scopepilot_class_floor)   # for ENFORCE
                    category_floor                                # for SHADOW/none

i.e. an enforced class floor *lowers* the binding floor to permit the downgrade,
while ModelPilot's structured-output/tool guard still applies on top — so a
lowered floor can never break a brittle call. Shadow entries don't touch the
floor; they only record what they *would* have done.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from .classify import classify
from .join import TicketResolver
from .models import TaskClass, WorkItem
from .pricing import rate_for
from .recommend import Recommendation


class PolicyMode(str, Enum):
    ENFORCE = "enforce"   # lower the floor; traffic actually moves
    SHADOW = "shadow"     # compute + log the delta; traffic unchanged
    ADVISORY = "advisory"  # report only


# confidence → mode mapping (the safety gate).
_DEFAULT_GATE = {"validated": PolicyMode.ENFORCE, "needs_validation": PolicyMode.SHADOW}


@dataclass
class PolicyEntry:
    task_class: TaskClass
    model: str           # the candidate (downgrade) model
    floor_tier: int      # its capability-ladder tier (0=haiku … 3=fable)
    mode: PolicyMode
    confidence: str
    projected_savings_usd: float
    rationale: str

    def to_dict(self) -> dict:
        return {
            "task_class": self.task_class.value,
            "model": self.model,
            "floor_tier": self.floor_tier,
            "mode": self.mode.value,
            "confidence": self.confidence,
            "projected_savings_usd": round(self.projected_savings_usd, 4),
            "rationale": self.rationale,
        }


@dataclass
class RoutingPolicy:
    entries: dict[TaskClass, PolicyEntry] = field(default_factory=dict)

    def decide(self, task_class: TaskClass) -> Optional[PolicyEntry]:
        return self.entries.get(task_class)

    @property
    def enforced_savings_usd(self) -> float:
        return sum(e.projected_savings_usd for e in self.entries.values()
                   if e.mode == PolicyMode.ENFORCE)

    @property
    def shadow_savings_usd(self) -> float:
        return sum(e.projected_savings_usd for e in self.entries.values()
                   if e.mode == PolicyMode.SHADOW)

    def to_dict(self) -> dict:
        """Proxy-consumable policy document."""
        return {
            "version": 1,
            "ladder": ["claude-haiku-4-5", "claude-sonnet-4-6",
                       "claude-opus-4-8", "claude-fable-5"],
            "compose": "binding_floor = min(category_floor, class_floor) for enforce",
            "entries": [e.to_dict() for e in sorted(
                self.entries.values(), key=lambda x: x.projected_savings_usd, reverse=True)],
        }

    # ModelPilot-shaped export: per-task-class floor, ENFORCE entries only —
    # mirrors the learned-floor structure `floor_tier()` consumes.
    def to_modelpilot_floors(self) -> dict[str, int]:
        return {e.task_class.value: e.floor_tier
                for e in self.entries.values() if e.mode == PolicyMode.ENFORCE}

    @classmethod
    def from_dict(cls, doc: dict) -> "RoutingPolicy":
        """Rehydrate a policy emitted by `to_dict()` (e.g. read back by the
        live shadow observer from `--emit-policy` output)."""
        entries: dict[TaskClass, PolicyEntry] = {}
        for e in doc.get("entries", []):
            tc = TaskClass(e["task_class"])
            entries[tc] = PolicyEntry(
                task_class=tc,
                model=e["model"],
                floor_tier=int(e["floor_tier"]),
                mode=PolicyMode(e["mode"]),
                confidence=e.get("confidence", ""),
                projected_savings_usd=float(e.get("projected_savings_usd", 0.0)),
                rationale=e.get("rationale", ""),
            )
        return cls(entries=entries)


def build_policy(
    recommendations: list[Recommendation],
    gate: Optional[dict[str, PolicyMode]] = None,
) -> RoutingPolicy:
    """Compile recommendations into a gated routing policy."""
    gate = gate or _DEFAULT_GATE
    entries: dict[TaskClass, PolicyEntry] = {}
    for rec in recommendations:
        mode = gate.get(rec.confidence, PolicyMode.ADVISORY)
        entries[rec.task_class] = PolicyEntry(
            task_class=rec.task_class,
            model=rec.candidate_model,
            floor_tier=rate_for(rec.candidate_model).tier,
            mode=mode,
            confidence=rec.confidence,
            projected_savings_usd=rec.projected_savings_usd,
            rationale=rec.rationale,
        )
    return RoutingPolicy(entries=entries)


class PolicyResolver:
    """Proxy-side helper: resolve a live request's git context → policy entry.

    The proxy stamps each request with the branch (or ticket) it's running on;
    this maps that to the engineering task-class and returns the policy decision,
    so the gateway can apply the floor (ENFORCE) or just log it (SHADOW).
    """

    def __init__(
        self,
        work_items: list[WorkItem],
        policy: RoutingPolicy,
        resolver: Optional[TicketResolver] = None,
    ) -> None:
        self.policy = policy
        self.resolver = resolver or TicketResolver()
        self._class_by_ticket = {wi.ticket_id: classify(wi) for wi in work_items}

    def for_ticket(self, ticket_id: Optional[str]) -> Optional[PolicyEntry]:
        tc = self._class_by_ticket.get(ticket_id) if ticket_id else None
        return self.policy.decide(tc) if tc else None

    def for_branch(self, branch: Optional[str]) -> Optional[PolicyEntry]:
        return self.for_ticket(self.resolver.from_branch(branch))
