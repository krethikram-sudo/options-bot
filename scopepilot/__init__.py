"""ScopePilot — roadmap-anchored AI spend governance (Phase 0 prototype).

Sibling product to ModelPilot. Where ModelPilot answers *"cheapest model that's
good enough per request"*, ScopePilot answers *"how much should this body of
planned engineering work cost in AI compute, and are we on track"* — by joining
LLM/coding-agent spend to the **work-breakdown units a team already plans
around** (Jira/Linear/GitHub tickets → epics → sprints → roadmap), not to
infrastructure tags (API keys, spans, model names) the way every existing
gateway / observability / FinOps tool does.

The moat is the join from a model call to a unit of *planned work*; the existing
market lives at the infra layer and structurally can't see the planning system.

Phase 0 scope (this package):
  - Provider:  Anthropic usage (admin export + per-call `usage` shape)
  - Planner:   GitHub Issues (issues/PRs + branch links)
  - Pipeline:  ingest → cost-normalize → branch→ticket join (fidelity-tiered)
               → task-class classify → attribute → forecast + anomaly guardrails
               → advisory model-routing recommendation
  - Read-only: no proxy/enforcement dependency (flat-SaaS-friendly land motion).

Everything is stdlib-only (json, re, dataclasses, statistics) so the prototype
runs with no new dependencies. Run `python -m scopepilot.cli` for the demo
report over bundled fixtures.
"""

from .models import (
    Attribution,
    FidelityTier,
    TaskClass,
    UsageEvent,
    WorkItem,
)

__all__ = [
    "Attribution",
    "FidelityTier",
    "TaskClass",
    "UsageEvent",
    "WorkItem",
]
