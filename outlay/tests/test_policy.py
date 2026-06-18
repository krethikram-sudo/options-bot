"""Enforcement tier: the validated→enforce / needs_validation→shadow gate,
the ModelPilot-shaped floor export, and proxy-side resolution."""

from datetime import datetime

from outlay.attribute import attribute
from outlay.join import JoinEngine, TicketResolver
from outlay.models import TaskClass, UsageEvent, WorkItem
from outlay.policy import PolicyMode, PolicyResolver, build_policy
from outlay.recommend import recommend


def _ev(eid, model, branch, session):
    return UsageEvent(id=eid, provider="anthropic", model=model,
                      ts=datetime(2026, 6, 1), branch=branch, session_id=session,
                      input_tokens=400_000)


WORK = [
    WorkItem("GH-40", "github", labels=["feature"], branch="feat/40", status="done"),
    WorkItem("GH-41", "github", labels=["bug"], branch="fix/41", status="done"),
]
EVENTS = [
    _ev("f1", "claude-opus-4-8", "feat/40", "s1"),
    _ev("f2", "claude-sonnet-4-6", "feat/40", "s2"),   # feature seen cheaper -> validated
    _ev("b1", "claude-opus-4-8", "fix/41", "s3"),       # bugfix opus-only -> needs validation
]


def _policy():
    res = attribute(EVENTS, WORK, engine=JoinEngine(WORK))
    return build_policy(recommend(res)), res


def test_gate_enforce_vs_shadow():
    policy, _ = _policy()
    assert policy.entries[TaskClass.FEATURE].mode == PolicyMode.ENFORCE
    assert policy.entries[TaskClass.BUGFIX].mode == PolicyMode.SHADOW


def test_modelpilot_floor_export_only_enforced():
    policy, _ = _policy()
    floors = policy.to_modelpilot_floors()
    assert "feature" in floors                 # validated → exported
    assert "bugfix" not in floors              # shadow → withheld
    # candidate is the next cheaper tier (sonnet, tier 1)
    assert floors["feature"] == 1


def test_policy_savings_split():
    policy, _ = _policy()
    assert policy.enforced_savings_usd > 0
    assert policy.shadow_savings_usd > 0


def test_policy_resolver_for_branch():
    policy, _ = _policy()
    resolver = PolicyResolver(WORK, policy, resolver=TicketResolver(source="github"))
    entry = resolver.for_branch("feat/40")
    assert entry is not None and entry.mode == PolicyMode.ENFORCE
    # An unmapped branch yields no policy (proxy leaves the request untouched).
    assert resolver.for_branch("scratch/play") is None


def test_policy_to_dict_shape():
    policy, _ = _policy()
    d = policy.to_dict()
    assert d["version"] == 1 and d["entries"]
    assert d["compose"].startswith("binding_floor")
    assert d["ladder"][0] == "claude-haiku-4-5"
