"""Live shadow-mode delta logging + the graduation loop, and the gateway seam."""

import json
import os
import tempfile
from datetime import datetime
from pathlib import Path

from outlay.attribute import attribute
from outlay.ingest import parse_anthropic_usage, parse_github_issues
from outlay.join import JoinEngine, TicketResolver
from outlay.models import TaskClass
from outlay.policy import PolicyMode, PolicyResolver, build_policy
from outlay.recommend import recommend
from outlay.shadow import (
    ShadowLedger,
    ShadowObserver,
    graduation_report,
    make_observer,
    promote,
)

FIX = Path(__file__).parent.parent / "fixtures"


def _default_policy():
    events = parse_anthropic_usage(FIX / "anthropic_usage.json")
    work = parse_github_issues(FIX / "github_issues.json")
    res = attribute(events, work, engine=JoinEngine(work))
    return build_policy(recommend(res)), work


def _payload(branch, model="claude-opus-4-8", **tok):
    base = {"request_id": "r1", "status_code": 200, "routed_model": model,
            "original_model": model, "input_tokens": 20000, "output_tokens": 8000,
            "cache_read_tokens": 150000, "cache_write_tokens": 20000,
            "work": {"branch": branch, "ticket": None}}
    base.update(tok)
    return base


def _observer(tmp):
    policy, work = _default_policy()
    resolver = PolicyResolver(work, policy, resolver=TicketResolver(source="github"))
    return ShadowObserver(resolver, ShadowLedger(tmp)), policy


def test_shadow_records_counterfactual_for_shadow_class():
    with tempfile.TemporaryDirectory() as d:
        obs, policy = _observer(Path(d) / "s.jsonl")
        assert policy.entries[TaskClass.BUGFIX].mode == PolicyMode.SHADOW
        # GH-101 is a bugfix (shadow). Used Opus; candidate Sonnet -> would downgrade.
        o = obs(_payload("fix/101-null-pointer"))
        assert o is not None
        assert o.task_class == "bugfix" and o.mode == "shadow"
        assert o.would_downgrade is True
        assert o.est_savings_usd > 0 and o.candidate_cost_usd < o.cost_usd


def test_shadow_skips_ungoverned_requests():
    with tempfile.TemporaryDirectory() as d:
        obs, _ = _observer(Path(d) / "s.jsonl")
        assert obs(_payload("scratch/experiment")) is None   # branch -> no ticket
        assert obs(_payload(None)) is None                    # no work context


def test_shadow_ledger_roundtrip():
    with tempfile.TemporaryDirectory() as d:
        obs, _ = _observer(Path(d) / "s.jsonl")
        obs(_payload("fix/101-null-pointer"))
        obs(_payload("fix/113-off-by-one"))
        rows = obs.ledger.read()
        assert len(rows) == 2 and all(r["mode"] == "shadow" for r in rows)


def test_graduation_report_and_promote():
    # Synthesize 40 shadow rows for bugfix.
    rows = [{"task_class": "bugfix", "mode": "shadow", "est_savings_usd": 0.5}
            for _ in range(40)]
    rows += [{"task_class": "refactor", "mode": "shadow", "est_savings_usd": 0.1}
             for _ in range(5)]
    grad = graduation_report(rows, min_samples=30)
    assert grad[TaskClass.BUGFIX].samples == 40
    assert grad[TaskClass.BUGFIX].ready_for_canary is True
    assert grad[TaskClass.REFACTOR].ready_for_canary is False  # too few

    policy, _ = _default_policy()
    promote(policy, {TaskClass.BUGFIX})   # only after independent quality validation
    assert policy.entries[TaskClass.BUGFIX].mode == PolicyMode.ENFORCE
    # untouched class stays shadow
    assert policy.entries[TaskClass.REFACTOR].mode == PolicyMode.SHADOW


def test_make_observer_noop_when_unconfigured():
    saved = {k: os.environ.pop(k, None) for k in ("SCOPEPILOT_POLICY", "SCOPEPILOT_ISSUES")}
    try:
        obs = make_observer()
        assert obs(_payload("fix/101-null-pointer")) is None  # safe no-op
    finally:
        for k, v in saved.items():
            if v is not None:
                os.environ[k] = v


def test_make_observer_from_env():
    policy, _ = _default_policy()
    with tempfile.TemporaryDirectory() as d:
        pol_path = Path(d) / "policy.json"
        pol_path.write_text(json.dumps(policy.to_dict()))
        log_path = Path(d) / "shadow.jsonl"
        env = {
            "SCOPEPILOT_POLICY": str(pol_path),
            "SCOPEPILOT_ISSUES": str(FIX / "github_issues.json"),
            "SCOPEPILOT_PLANNER": "github",
            "SCOPEPILOT_SHADOW_LOG": str(log_path),
        }
        saved = {k: os.environ.get(k) for k in env}
        os.environ.update(env)
        try:
            obs = make_observer()
            o = obs(_payload("fix/106-flaky-retry"))
            assert o is not None and o.task_class == "bugfix"
            assert log_path.exists() and len(ShadowLedger(log_path).read()) == 1
        finally:
            for k, v in saved.items():
                if v is None:
                    os.environ.pop(k, None)
                else:
                    os.environ[k] = v


def test_gateway_observer_seam():
    # The gateway must load our factory through its product-agnostic seam.
    try:
        from modelpilot import gateway
    except Exception:
        return  # gateway deps (fastapi/httpx) absent in this env — seam tested elsewhere
    assert gateway._load_observer(None) is None
    assert gateway._load_observer("nonexistent.module:nope") is None  # fail-open
    loaded = gateway._load_observer("outlay.shadow:make_observer")
    assert callable(loaded)
