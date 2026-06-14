"""Gateway decide() with a hosted brain: entitlement + fail-open."""

import modelpilot.brain_client as bc
from modelpilot.gateway import decide
from modelpilot.router import Recommendation

BODY = {"model": "claude-opus-4-8", "max_tokens": 512,
        "messages": [{"role": "user", "content": "Classify: good or bad — 'broke fast'"}]}


def _rec(action="switch", model="claude-haiku-4-5"):
    return Recommendation(action=action, original_model="claude-opus-4-8",
                          recommended_model=model, confidence=0.85,
                          category="classification", rationale="brain")


def test_brain_entitled_and_apply_routes(monkeypatch):
    monkeypatch.setattr(bc, "remote_decide",
                        lambda *a, **k: (_rec(), {"entitled": True, "apply": True}))
    d = decide(BODY, "autopilot", holdout_pct=0.0, brain_url="http://brain", deployment_id="d")
    assert d.applied and d.routed_model == "claude-haiku-4-5" and d.entitled


def test_brain_not_entitled_passes_through(monkeypatch):
    # trial/license lapsed -> brain says not entitled -> no routing, but traffic flows
    monkeypatch.setattr(bc, "remote_decide",
                        lambda *a, **k: (_rec(), {"entitled": False, "apply": False}))
    d = decide(BODY, "autopilot", holdout_pct=0.0, brain_url="http://brain", deployment_id="d")
    assert not d.applied and d.routed_model == "claude-opus-4-8" and d.entitled is False


def test_brain_entitled_but_below_gate_not_applied(monkeypatch):
    monkeypatch.setattr(bc, "remote_decide",
                        lambda *a, **k: (_rec(), {"entitled": True, "apply": False}))
    d = decide(BODY, "autopilot", holdout_pct=0.0, brain_url="http://brain", deployment_id="d")
    assert not d.applied and d.routed_model == "claude-opus-4-8"


def test_brain_unreachable_fails_open_to_local(monkeypatch):
    monkeypatch.setattr(bc, "remote_decide", lambda *a, **k: None)
    # local routing still classifies + applies (classification -> haiku, conf 0.85 >= 0.7)
    d = decide(BODY, "autopilot", holdout_pct=0.0, brain_url="http://brain", deployment_id="d")
    assert d.applied and d.routed_model == "claude-haiku-4-5"


def test_no_brain_is_pure_local(monkeypatch):
    # brain_url None -> never calls remote_decide
    monkeypatch.setattr(bc, "remote_decide",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not call brain")))
    d = decide(BODY, "autopilot", holdout_pct=0.0)
    assert d.applied and d.routed_model == "claude-haiku-4-5"
