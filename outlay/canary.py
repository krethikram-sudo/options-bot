"""Canary harness — the quality half of graduation.

Shadow mode (`shadow.py`) proves a downgrade would be *cheaper*. It cannot prove
it's *good enough* — cost is not quality. This module supplies the missing half:
run the candidate model on a sampled set of a class's real prompts, judge it
non-inferior to the incumbent, and only then let the class graduate to ENFORCE.

The honest gate is **both**: a class promotes only when it is
`ready_for_canary` (enough live cost evidence in the shadow log) **and** its
canary trial passed (enough quality evidence here). Cost evidence accrues
automatically; quality is measured, never assumed.

This is the "ModelPilot as a service within Outlay" seam in concrete form:
Outlay decides *which* classes to canary and adjudicates graduation;
the actual model runs + non-inferiority judging are pluggable `run_fn`/`judge_fn`
callables — in production, ModelPilot's `compare.api_run_fn` /
`compare.api_judge_fn` (same signatures), so the routing product executes the
test the governance product ordered.
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Callable, Optional

from .models import TaskClass, UsageEvent
from .pricing import cost_usd

# run_fn(model, prompt) -> (text, usage_like)   usage_like: obj/dict with token fields
RunFn = Callable[[str, str], tuple]
# judge_fn(prompt, incumbent_text, candidate_text) -> bool (True = non-inferior)
JudgeFn = Callable[[str, str, str], bool]


class CanaryDecision(str, Enum):
    PROMOTE = "promote"   # passed — safe to ENFORCE
    REJECT = "reject"     # candidate is materially worse — keep incumbent
    HOLD = "hold"         # not enough samples yet — keep collecting


@dataclass
class CanaryTrial:
    task_class: TaskClass
    incumbent_model: str
    candidate_model: str
    n: int
    non_inferior_rate: float
    realized_savings_usd: float
    decision: CanaryDecision


def _tok(u, *names) -> int:
    for n in names:
        v = getattr(u, n, None)
        if v is None and isinstance(u, dict):
            v = u.get(n)
        if v is not None:
            return int(v)
    return 0


def _cost(model: str, usage_like) -> float:
    ev = UsageEvent(
        id="", provider="anthropic", model=model, ts=datetime.utcnow(),
        input_tokens=_tok(usage_like, "input_tokens"),
        output_tokens=_tok(usage_like, "output_tokens"),
        cache_read_tokens=_tok(usage_like, "cache_read_tokens", "cache_read_input_tokens"),
        cache_write_tokens=_tok(usage_like, "cache_write_tokens", "cache_creation_input_tokens"),
    )
    return cost_usd(ev)


def run_canary(
    task_class: TaskClass,
    incumbent_model: str,
    candidate_model: str,
    prompts: list[str],
    run_fn: RunFn,
    judge_fn: JudgeFn,
    *,
    min_samples: int = 20,
    min_pass_rate: float = 0.95,
    reject_below: float = 0.85,
) -> CanaryTrial:
    """Run the candidate against the incumbent on `prompts`, judge each pair, and
    decide. PROMOTE needs both enough samples and a high pass rate; a pass rate
    below `reject_below` is REJECT even early (clear regression); otherwise HOLD.
    """
    passes = 0
    realized = 0.0
    n = 0
    for prompt in prompts:
        inc_text, inc_usage = run_fn(incumbent_model, prompt)
        cand_text, cand_usage = run_fn(candidate_model, prompt)
        non_inferior = bool(judge_fn(prompt, inc_text, cand_text))
        n += 1
        if non_inferior:
            passes += 1
            realized += max(0.0, _cost(incumbent_model, inc_usage)
                            - _cost(candidate_model, cand_usage))

    rate = (passes / n) if n else 0.0
    if n and rate < reject_below:
        decision = CanaryDecision.REJECT
    elif n >= min_samples and rate >= min_pass_rate:
        decision = CanaryDecision.PROMOTE
    else:
        decision = CanaryDecision.HOLD

    return CanaryTrial(
        task_class=task_class,
        incumbent_model=incumbent_model,
        candidate_model=candidate_model,
        n=n,
        non_inferior_rate=round(rate, 4),
        realized_savings_usd=round(realized, 6),
        decision=decision,
    )


def graduations_from_canary(trials: list[CanaryTrial]) -> set[TaskClass]:
    """Classes whose canary trial passed."""
    return {t.task_class for t in trials if t.decision == CanaryDecision.PROMOTE}


def ready_classes(shadow_readiness: dict, canary_trials: list[CanaryTrial]) -> set[TaskClass]:
    """The two-gate graduation set: a class promotes only if it is BOTH
    `ready_for_canary` in the shadow log AND PROMOTE in its canary trial.

    `shadow_readiness` is the output of `shadow.graduation_report` (task_class →
    ClassGraduation with `.ready_for_canary`).
    """
    cost_ready = {tc for tc, g in shadow_readiness.items() if getattr(g, "ready_for_canary", False)}
    quality_ready = graduations_from_canary(canary_trials)
    return cost_ready & quality_ready


# ---------------------------------------------------------------------------
# Deterministic offline run/judge — for the demo and tests (no API/keys).
# Production injects ModelPilot's compare.api_run_fn / api_judge_fn instead.
# ---------------------------------------------------------------------------

def offline_run_fn(model: str, prompt: str) -> tuple:
    rng = random.Random(hash((model, prompt)) & 0xFFFF)
    text = f"[{model}] {prompt[:60]}"
    # Cheaper tiers emit fewer tokens here so realized savings is visible.
    scale = {"claude-haiku-4-5": 0.6, "claude-sonnet-4-6": 0.8}.get(model, 1.0)
    usage = {
        "input_tokens": max(len(prompt) // 4, 30),
        "output_tokens": int(rng.randint(120, 400) * scale),
        "cache_read_input_tokens": 0,
        "cache_creation_input_tokens": 0,
    }
    return text, usage


def offline_judge_fn(pass_rate: float = 0.98) -> JudgeFn:
    """A deterministic judge that marks ~`pass_rate` of prompts non-inferior."""
    def judge(prompt: str, incumbent_text: str, candidate_text: str) -> bool:
        return (random.Random(hash(prompt) & 0xFFFF).random()) < pass_rate
    return judge
