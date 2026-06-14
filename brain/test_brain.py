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
