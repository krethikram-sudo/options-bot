"""Hosted routing brain: decisions, server-side entitlement, no-sensitive-data."""

import importlib
import os

from fastapi.testclient import TestClient


def _client(tmp_path):
    os.environ["BRAIN_DB"] = str(tmp_path / "brain.db")
    import brain.server as srv
    importlib.reload(srv)
    return TestClient(srv.app), srv


def _req(**over):
    r = {"deployment_id": "dep-A", "category": "classification", "confidence": 0.85,
         "original_model": "claude-opus-4-8",
         "features": {"approx_context_tokens": 600, "requested_max_tokens": 512,
                      "has_tools": False, "has_structured_output": False,
                      "has_cache_control": False, "n_turns": 1},
         "expected_remaining_turns": 5.0}
    r.update(over)
    return r


def test_routes_simple_category_down(tmp_path):
    c, _ = _client(tmp_path)
    d = c.post("/route", json=_req()).json()
    assert d["entitled"] and d["action"] == "switch"
    assert d["recommended_model"] == "claude-haiku-4-5" and d["apply"] is True


def test_structured_output_floored_to_sonnet(tmp_path):
    c, _ = _client(tmp_path)
    d = c.post("/route", json=_req(features={**_req()["features"], "has_structured_output": True})).json()
    assert d["recommended_model"] == "claude-sonnet-4-6"


def test_low_confidence_does_not_apply(tmp_path):
    c, _ = _client(tmp_path)
    d = c.post("/route", json=_req(confidence=0.5)).json()
    assert d["recommended_model"] == "claude-haiku-4-5" and d["apply"] is False  # below 0.7 gate


def test_rejects_sensitive_payload(tmp_path):
    c, _ = _client(tmp_path)
    for bad in ({**_req(), "messages": [{"role": "user", "content": "secret"}]},
                {**_req(), "prompt": "raw text"},
                {**_req(), "features": {"api_key": "sk-ant-leak"}}):
        assert c.post("/route", json=bad).status_code == 422


def test_opportunity_prompt_cache(tmp_path):
    c, _ = _client(tmp_path)
    # Large uncached reusable prefix over several turns -> a caching opportunity.
    feats = {**_req()["features"], "approx_context_tokens": 20_000, "has_cache_control": False}
    d = c.post("/route", json=_req(features=feats, expected_remaining_turns=8.0)).json()
    opps = {o["type"]: o for o in d.get("opportunities", [])}
    assert "prompt_cache" in opps and opps["prompt_cache"]["est_savings"] > 0


def test_opportunity_none_when_already_cached(tmp_path):
    c, _ = _client(tmp_path)
    feats = {**_req()["features"], "approx_context_tokens": 20_000, "has_cache_control": True}
    d = c.post("/route", json=_req(features=feats, expected_remaining_turns=8.0)).json()
    assert not any(o["type"] == "prompt_cache" for o in d.get("opportunities", []))


def test_opportunity_batch_when_latency_tolerant(tmp_path):
    c, _ = _client(tmp_path)
    feats = {**_req()["features"], "latency_tolerant": True}
    d = c.post("/route", json=_req(features=feats)).json()
    assert any(o["type"] == "batch_api" and o["est_savings"] > 0
               for o in d.get("opportunities", []))


def test_passes_ramp_boundaries(tmp_path):
    _, srv = _client(tmp_path)
    # deterministic boundaries
    assert all(srv._passes_ramp(100) for _ in range(50))
    assert not any(srv._passes_ramp(0) for _ in range(50))
    # a mid ramp samples both outcomes over many draws
    draws = [srv._passes_ramp(50) for _ in range(400)]
    assert any(draws) and not all(draws)


def test_ramp_holds_back_switch_when_pct_zero(tmp_path, monkeypatch):
    c, srv = _client(tmp_path)
    # Simulate a console saying autopilot is on but ramped to 0%.
    monkeypatch.setattr(srv, "_CONSOLE_URL", "http://console.test")
    monkeypatch.setattr(srv, "_console_entitlement", lambda dep: {
        "entitled": True, "via": "console", "mode": "autopilot",
        "apply_mode": True, "apply_pct": 0, "reason": "paid", "plan": "paid"})
    monkeypatch.setattr(srv, "_console_policy", lambda dep: {})
    d = c.post("/route", json=_req()).json()
    # Still a recommendation, but not auto-applied — flagged as held by the ramp.
    assert d["action"] == "switch" and d["apply"] is False
    assert d.get("ramp_held") is True and d["apply_pct"] == 0


def test_ramp_full_applies_switch(tmp_path, monkeypatch):
    c, srv = _client(tmp_path)
    monkeypatch.setattr(srv, "_CONSOLE_URL", "http://console.test")
    monkeypatch.setattr(srv, "_console_entitlement", lambda dep: {
        "entitled": True, "via": "console", "mode": "autopilot",
        "apply_mode": True, "apply_pct": 100, "reason": "paid", "plan": "paid"})
    monkeypatch.setattr(srv, "_console_policy", lambda dep: {})
    d = c.post("/route", json=_req()).json()
    assert d["action"] == "switch" and d["apply"] is True and not d.get("ramp_held")


def test_trial_entitlement_expires_server_side(tmp_path):
    _, srv = _client(tmp_path)
    now = 1_000_000.0
    e1 = srv.entitlement("dep-X", None, now=now)
    assert e1["entitled"] and e1["via"] == "trial" and e1["trial_days_left"] == 7
    e2 = srv.entitlement("dep-X", None, now=now + 8 * 86_400)
    assert not e2["entitled"] and e2["trial_days_left"] == 0


def test_expired_trial_yields_no_decision(tmp_path):
    c, srv = _client(tmp_path)
    # seed an old first_seen so the trial is expired
    conn = srv._conn()
    conn.execute("INSERT INTO deployments (deployment_id, first_seen) VALUES (?,?)",
                 ("dep-old", 1.0))
    conn.commit(); conn.close()
    d = c.post("/route", json=_req(deployment_id="dep-old")).json()
    assert d["entitled"] is False and d["apply"] is False
    assert d["recommended_model"] == "claude-opus-4-8"  # passthrough, unoptimized
