"""Canary harness: the quality gate, and the two-gate graduation with shadow."""

from scopepilot.canary import (
    CanaryDecision,
    offline_judge_fn,
    offline_run_fn,
    ready_classes,
    run_canary,
)
from scopepilot.models import TaskClass
from scopepilot.policy import PolicyMode, build_policy
from scopepilot.recommend import recommend
from scopepilot.shadow import ClassGraduation
from scopepilot.attribute import attribute
from scopepilot.ingest import parse_anthropic_usage, parse_github_issues
from scopepilot.join import JoinEngine
from pathlib import Path

FIX = Path(__file__).parent.parent / "fixtures"
PROMPTS = [f"fix bug number {i}" for i in range(30)]


def test_canary_promotes_when_non_inferior():
    trial = run_canary(TaskClass.BUGFIX, "claude-opus-4-8", "claude-sonnet-4-6",
                       PROMPTS, offline_run_fn, offline_judge_fn(1.0),
                       min_samples=20, min_pass_rate=0.95)
    assert trial.decision == CanaryDecision.PROMOTE
    assert trial.n == 30 and trial.non_inferior_rate == 1.0
    assert trial.realized_savings_usd > 0   # cheaper candidate, savings realized


def test_canary_rejects_clear_regression():
    trial = run_canary(TaskClass.BUGFIX, "claude-opus-4-8", "claude-haiku-4-5",
                       PROMPTS, offline_run_fn, offline_judge_fn(0.3))
    assert trial.decision == CanaryDecision.REJECT


def test_canary_holds_when_too_few_samples():
    trial = run_canary(TaskClass.FEATURE, "claude-opus-4-8", "claude-sonnet-4-6",
                       PROMPTS[:5], offline_run_fn, offline_judge_fn(1.0),
                       min_samples=20)
    assert trial.decision == CanaryDecision.HOLD


def test_two_gate_requires_both_cost_and_quality():
    # bugfix: cost-ready AND canary-promote -> graduates.
    # refactor: canary-promote but NOT cost-ready -> withheld.
    # test:    cost-ready but canary-reject -> withheld.
    shadow_readiness = {
        TaskClass.BUGFIX: ClassGraduation(TaskClass.BUGFIX, 40, 12.0, True),
        TaskClass.TEST: ClassGraduation(TaskClass.TEST, 35, 3.0, True),
        TaskClass.REFACTOR: ClassGraduation(TaskClass.REFACTOR, 4, 0.5, False),
    }
    trials = [
        run_canary(TaskClass.BUGFIX, "claude-opus-4-8", "claude-sonnet-4-6",
                   PROMPTS, offline_run_fn, offline_judge_fn(1.0)),
        run_canary(TaskClass.REFACTOR, "claude-opus-4-8", "claude-sonnet-4-6",
                   PROMPTS, offline_run_fn, offline_judge_fn(1.0)),
        run_canary(TaskClass.TEST, "claude-sonnet-4-6", "claude-haiku-4-5",
                   PROMPTS, offline_run_fn, offline_judge_fn(0.2)),
    ]
    promote = ready_classes(shadow_readiness, trials)
    assert promote == {TaskClass.BUGFIX}


def test_graduation_flips_policy_to_enforce():
    # Build the real default policy (bugfix starts SHADOW), then graduate it via
    # the two-gate result + policy.promote.
    from scopepilot.shadow import promote as promote_policy
    work = parse_github_issues(FIX / "github_issues.json")
    res = attribute(parse_anthropic_usage(FIX / "anthropic_usage.json"), work,
                    engine=JoinEngine(work))
    policy = build_policy(recommend(res))
    assert policy.entries[TaskClass.BUGFIX].mode == PolicyMode.SHADOW

    shadow_readiness = {TaskClass.BUGFIX: ClassGraduation(TaskClass.BUGFIX, 50, 9.0, True)}
    trials = [run_canary(TaskClass.BUGFIX, "claude-opus-4-8", "claude-sonnet-4-6",
                         PROMPTS, offline_run_fn, offline_judge_fn(1.0))]
    promote_policy(policy, ready_classes(shadow_readiness, trials))
    assert policy.entries[TaskClass.BUGFIX].mode == PolicyMode.ENFORCE
