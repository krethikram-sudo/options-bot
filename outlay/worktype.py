"""Work vs. non-work classification — which AI compute is doing the company's work,
and which isn't — plus an opt-in policy to stop the non-work usage.

**Posture (non-negotiable):** metadata-only. We classify from signals Outlay
already has — the attribution join, the work key/repo registry — and never need
the prompt. When prompt-level judgement *is* wanted, an optional classifier runs
**on the customer's box** (like `router_classify`), reads the prompt locally, and
emits only a one-word **label** (`work` / `non_work`). The label is metadata; the
prompt never leaves the customer's environment. We consume the label, not the text.

Classification is **fidelity-honest** (mirrors the attribution fidelity tiers): we
only call something `non_work` when there's evidence (a client-side label or an
explicit non-work key). Absence of a work join is `unknown`, not `non_work` — most
unjoined spend is just *untracked* work, and guessing would burn trust.

**Enforcement** is advisory here: `gateway_decision()` returns allow/block for the
**opt-in gateway** the customer runs in their own request path. Outlay stays
read-only; the customer who wants to *stop* non-work usage turns the gateway on.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import TYPE_CHECKING, Optional

from .pricing import cost_usd

if TYPE_CHECKING:
    from .models import UsageEvent


class WorkType(str, Enum):
    WORK = "work"            # joined to a work item / on a work key, or labeled work
    NON_WORK = "non_work"    # labeled non-work, or on a key flagged non-work
    UNKNOWN = "unknown"      # no work join and no label — untracked, don't guess


@dataclass(frozen=True)
class WorkPolicy:
    """Customer-defined rules: what counts as work, and whether to stop the rest."""

    work_api_keys: frozenset = frozenset()      # keys provisioned for the company's work
    non_work_api_keys: frozenset = frozenset()  # keys known to be personal / non-work
    treat_unknown_as_non_work: bool = False     # strict mode: unjoined+unlabeled → non-work
    block_non_work: bool = False                # OPT-IN: the gateway blocks non-work requests
    block_unknown: bool = False                 # OPT-IN, stricter: also block unjoined+unlabeled


def classify_event(event: "UsageEvent", *, joined_to_work: bool = False,
                   work_label: Optional[str] = None,
                   policy: Optional[WorkPolicy] = None) -> WorkType:
    """Classify one event. `joined_to_work` comes from the attribution join (a
    ticket/branch/session resolved). `work_label` is the optional client-side
    prompt label ('work'/'non_work') — metadata only, the prompt never left the box."""
    policy = policy or WorkPolicy()
    key = event.api_key_id
    # 1. Explicit non-work key wins (the customer told us this key is personal).
    if key and key in policy.non_work_api_keys:
        return WorkType.NON_WORK
    # 2. Joined to a work item, or on a registered work key → work (metadata only).
    if joined_to_work or event.explicit_ticket or event.branch or (key and key in policy.work_api_keys):
        return WorkType.WORK
    # 3. Client-side prompt label, if the customer runs the local classifier.
    if work_label == "work":
        return WorkType.WORK
    if work_label == "non_work":
        return WorkType.NON_WORK
    # 4. No work join, no label — untracked. Strict mode treats it as non-work.
    return WorkType.NON_WORK if policy.treat_unknown_as_non_work else WorkType.UNKNOWN


@dataclass
class WorkSplit:
    """Spend split by work-relatedness, with per-actor rollups for governance."""

    work_usd: float = 0.0
    non_work_usd: float = 0.0
    unknown_usd: float = 0.0
    work_events: int = 0
    non_work_events: int = 0
    unknown_events: int = 0
    by_user: dict[str, dict] = field(default_factory=dict)     # user -> {work,non_work,unknown}_usd
    by_key: dict[str, dict] = field(default_factory=dict)      # api_key_id -> same

    @property
    def total_usd(self) -> float:
        return self.work_usd + self.non_work_usd + self.unknown_usd

    @property
    def non_work_share(self) -> float:
        return (self.non_work_usd / self.total_usd) if self.total_usd > 0 else 0.0


def classify_usage(events: "list[UsageEvent]", *,
                   joined_ids: Optional[set] = None,
                   labels: Optional[dict] = None,
                   policy: Optional[WorkPolicy] = None) -> WorkSplit:
    """Classify a batch and aggregate the spend split.

    `joined_ids` = event ids the attribution join tied to a work item.
    `labels` = {event_id: 'work'|'non_work'} from the optional client-side classifier.
    """
    joined_ids = joined_ids or set()
    labels = labels or {}
    policy = policy or WorkPolicy()
    split = WorkSplit()
    for e in events:
        wt = classify_event(e, joined_to_work=(e.id in joined_ids),
                            work_label=labels.get(e.id), policy=policy)
        usd = cost_usd(e)
        bucket = wt.value  # "work" / "non_work" / "unknown"
        setattr(split, f"{bucket}_usd", getattr(split, f"{bucket}_usd") + usd)
        setattr(split, f"{bucket}_events", getattr(split, f"{bucket}_events") + 1)
        for dim, dim_key in (("by_user", e.user), ("by_key", e.api_key_id)):
            if not dim_key:
                continue
            d = getattr(split, dim).setdefault(dim_key, {"work_usd": 0.0, "non_work_usd": 0.0, "unknown_usd": 0.0})
            d[f"{bucket}_usd"] += usd
    # round for presentation
    for attr in ("work_usd", "non_work_usd", "unknown_usd"):
        setattr(split, attr, round(getattr(split, attr), 4))
    for dim in ("by_user", "by_key"):
        for d in getattr(split, dim).values():
            for k in d:
                d[k] = round(d[k], 4)
    return split


def format_worktype(split: WorkSplit, *, policy: Optional[WorkPolicy] = None) -> str:
    """Human-readable work / non-work split for the CLI report."""
    policy = policy or WorkPolicy()
    t = split.total_usd or 1.0
    lines = [
        "Work vs non-work AI spend  (metadata-only — prompts never leave your box)",
        "=" * 74,
        f"  Work:      ${split.work_usd:>10,.2f}  ({split.work_usd / t * 100:4.0f}%)  "
        f"· {split.work_events} events  — joined to a ticket/branch or a work key",
        f"  Non-work:  ${split.non_work_usd:>10,.2f}  ({split.non_work_usd / t * 100:4.0f}%)  "
        f"· {split.non_work_events} events  — labeled non-work or on a personal key",
        f"  Unknown:   ${split.unknown_usd:>10,.2f}  ({split.unknown_usd / t * 100:4.0f}%)  "
        f"· {split.unknown_events} events  — untracked (not guessed as non-work)",
    ]
    if split.non_work_usd > 0:
        top = sorted(split.by_user.items(), key=lambda kv: kv[1].get("non_work_usd", 0), reverse=True)
        top = [(u, d) for u, d in top if d.get("non_work_usd", 0) > 0][:5]
        if top:
            lines.append("")
            lines.append("  Top non-work spenders:")
            for u, d in top:
                lines.append(f"    {u:<28} ${d['non_work_usd']:>9,.2f}")
    lines.append("")
    if policy.block_non_work:
        lines.append("  ▶ Enforcement ON (opt-in gateway): non-work requests are blocked in-path."
                     + (" Unknown also blocked (strict)." if policy.block_unknown else ""))
    else:
        lines.append("  Enforcement OFF — read-only. Turn on the opt-in gateway to stop non-work usage.")
    return "\n".join(lines)


@dataclass
class GatewayDecision:
    allow: bool
    work_type: WorkType
    reason: str


def gateway_decision(event: "UsageEvent", *, joined_to_work: bool = False,
                     work_label: Optional[str] = None,
                     policy: Optional[WorkPolicy] = None) -> GatewayDecision:
    """Allow/deny verdict for the **opt-in** gateway the customer runs in-path.

    Outlay itself never blocks anything — this is the rule the customer's gateway
    applies if they turn on `block_non_work` (and optionally `block_unknown`)."""
    policy = policy or WorkPolicy()
    wt = classify_event(event, joined_to_work=joined_to_work, work_label=work_label, policy=policy)
    if wt is WorkType.NON_WORK and policy.block_non_work:
        return GatewayDecision(False, wt, "blocked: classified non-work")
    if wt is WorkType.UNKNOWN and policy.block_unknown:
        return GatewayDecision(False, wt, "blocked: no work context (strict mode)")
    return GatewayDecision(True, wt, "allowed")
