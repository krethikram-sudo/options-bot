"""Live shadow-mode delta logging — the loop that makes enforcement *earn* itself.

The enforcement policy (`policy.py`) marks `needs_validation` classes as SHADOW:
the proxy keeps serving them on the incumbent model but should *record what it
would have done* on the cheaper candidate. This module is what the ModelPilot
gateway calls (via its generic request-observer seam) to write that record on
live traffic. Over time the shadow log accumulates the evidence that graduates a
class from `shadow` to `enforce` — instead of trusting a one-shot projection.

Integration (no gateway dependency on Outlay):

    export MODELPILOT_REQUEST_OBSERVER=outlay.shadow:make_observer
    export SCOPEPILOT_POLICY=policy.json        # from `outlay ... --emit-policy`
    export SCOPEPILOT_ISSUES=issues.json        # planner export
    export SCOPEPILOT_PLANNER=github            # github|jira|linear
    export SCOPEPILOT_SHADOW_LOG=shadow.jsonl   # append-only delta log

The gateway imports `make_observer`, calls it once at startup, and hands every
ledgered request to the returned callable. A misbehaving observer can never
affect the response — the gateway wraps the call — and an unset/!misconfigured
policy yields a safe no-op.

**Honesty boundary.** Shadow logs *cost* deltas, not *quality*. A class becomes
`ready_for_canary` once it has enough shadow samples, but promotion to ENFORCE
still requires a quality signal (run the candidate on a canary, confirm
non-inferiority). `graduation_report` surfaces readiness; `promote` only flips
classes the caller has actually validated — it never auto-enforces on cost alone.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional, Union

from .ingest import PLANNERS
from .join import TicketResolver
from .models import TaskClass, UsageEvent
from .policy import PolicyMode, PolicyResolver, RoutingPolicy
from .pricing import cost_usd, rate_for


@dataclass
class ShadowObservation:
    request_id: str
    ts: str
    task_class: str
    mode: str
    model_used: str
    candidate_model: str
    would_downgrade: bool
    cost_usd: float
    candidate_cost_usd: float
    est_savings_usd: float
    status_code: int


class ShadowLedger:
    """Append-only JSONL store of shadow observations."""

    def __init__(self, path: Union[str, Path]) -> None:
        self.path = Path(path)

    def record(self, obs: ShadowObservation) -> None:
        with self.path.open("a") as f:
            f.write(json.dumps(asdict(obs)) + "\n")

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line.strip()]


def _event_from_payload(payload: dict, model: str) -> UsageEvent:
    return UsageEvent(
        id=payload.get("request_id", ""),
        provider="anthropic",
        model=model,
        ts=datetime.utcnow(),
        input_tokens=int(payload.get("input_tokens", 0) or 0),
        output_tokens=int(payload.get("output_tokens", 0) or 0),
        cache_read_tokens=int(payload.get("cache_read_tokens", 0) or 0),
        cache_write_tokens=int(payload.get("cache_write_tokens", 0) or 0),
    )


class ShadowObserver:
    """Callable handed to the gateway: payload → maybe a shadow observation."""

    def __init__(self, resolver: PolicyResolver, ledger: ShadowLedger) -> None:
        self.resolver = resolver
        self.ledger = ledger

    def __call__(self, payload: dict) -> Optional[ShadowObservation]:
        work = payload.get("work") or {}
        entry = (self.resolver.for_branch(work.get("branch"))
                 or self.resolver.for_ticket(work.get("ticket")))
        if entry is None:
            return None  # request isn't on a policy-governed task class

        model_used = payload.get("routed_model") or payload.get("original_model") or ""
        cost = cost_usd(_event_from_payload(payload, model_used)) if model_used else 0.0
        cand_cost = cost_usd(_event_from_payload(payload, entry.model))
        would_downgrade = rate_for(entry.model).tier < rate_for(model_used).tier if model_used else False
        savings = (cost - cand_cost) if would_downgrade else 0.0

        obs = ShadowObservation(
            request_id=payload.get("request_id", ""),
            ts=datetime.utcnow().isoformat(timespec="seconds"),
            task_class=entry.task_class.value,
            mode=entry.mode.value,
            model_used=model_used,
            candidate_model=entry.model,
            would_downgrade=would_downgrade,
            cost_usd=round(cost, 6),
            candidate_cost_usd=round(cand_cost, 6),
            est_savings_usd=round(savings, 6),
            status_code=int(payload.get("status_code", 0) or 0),
        )
        self.ledger.record(obs)
        return obs


def _noop_observer(payload: dict) -> None:
    return None


def make_observer() -> Callable[[dict], object]:
    """Zero-arg factory the gateway's observer seam constructs at startup.

    Reads SCOPEPILOT_* env. With no `SCOPEPILOT_POLICY` configured it returns a
    safe no-op so an enabled-but-unconfigured deployment never errors.
    """
    policy_path = os.environ.get("SCOPEPILOT_POLICY")
    issues_path = os.environ.get("SCOPEPILOT_ISSUES")
    if not policy_path or not issues_path:
        return _noop_observer

    planner = os.environ.get("SCOPEPILOT_PLANNER", "github")
    parse_work, resolver_source = PLANNERS[planner]
    work_items = parse_work(issues_path)
    policy = RoutingPolicy.from_dict(json.loads(Path(policy_path).read_text()))
    resolver = PolicyResolver(work_items, policy,
                              resolver=TicketResolver(source=resolver_source))
    ledger = ShadowLedger(os.environ.get("SCOPEPILOT_SHADOW_LOG", "outlay_shadow.jsonl"))
    return ShadowObserver(resolver, ledger)


# ---------------------------------------------------------------------------
# Graduation loop
# ---------------------------------------------------------------------------

@dataclass
class ClassGraduation:
    task_class: TaskClass
    samples: int
    total_est_savings_usd: float
    ready_for_canary: bool


def graduation_report(
    ledger: Union[ShadowLedger, list[dict]],
    min_samples: int = 30,
) -> dict[TaskClass, ClassGraduation]:
    """Aggregate SHADOW observations per class → readiness to validate.

    Readiness is a *sample-count* gate, not a promotion: it says "this class has
    accumulated enough live counterfactuals to justify a quality canary." The
    promotion itself is `promote()`, which requires a validated set.
    """
    rows = ledger.read() if isinstance(ledger, ShadowLedger) else ledger
    agg: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        if r.get("mode") == PolicyMode.SHADOW.value:
            agg[r["task_class"]].append(r)

    out: dict[TaskClass, ClassGraduation] = {}
    for tc_value, items in agg.items():
        savings = sum(float(i.get("est_savings_usd", 0.0)) for i in items)
        out[TaskClass(tc_value)] = ClassGraduation(
            task_class=TaskClass(tc_value),
            samples=len(items),
            total_est_savings_usd=round(savings, 4),
            ready_for_canary=len(items) >= min_samples,
        )
    return out


def promote(policy: RoutingPolicy, validated_classes: set[TaskClass]) -> RoutingPolicy:
    """Flip the given (independently quality-validated) classes from SHADOW to
    ENFORCE. Only classes whose non-inferiority you've actually confirmed belong
    here — this function does not infer quality from the shadow log."""
    for tc in validated_classes:
        entry = policy.entries.get(tc)
        if entry and entry.mode == PolicyMode.SHADOW:
            entry.mode = PolicyMode.ENFORCE
            entry.confidence = "validated"
    return policy
