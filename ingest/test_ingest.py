"""Ingest server: accepts aggregate payloads, rejects sensitive ones, rolls up.

Run: pip install fastapi uvicorn httpx && python -m pytest ingest/ -q
(Vendor-side internal tool — not part of the shipped modelpilot package.)
"""

import importlib
import os

from fastapi.testclient import TestClient


def _client(tmp_path):
    os.environ["INGEST_DB"] = str(tmp_path / "ingest.db")
    import ingest.server as srv
    importlib.reload(srv)
    return TestClient(srv.app)


CLEAN = {
    "schema": 3, "deployment_id": "dep-A", "modelpilot_version": "0.16.0",
    "n_requests": 100, "catch_all_rate": 0.30,
    "by_category": [{"category": "extraction", "n": 40, "n_applied": 30, "incident_rate": 0.0}],
    "catchall_phrase_signals": [{"phrase": "parse table", "docs": 12}],
    "_privacy": "aggregates only — no prompt text, outputs, or keys",
}


def test_clean_payload_accepted_and_aggregated(tmp_path):
    c = _client(tmp_path)
    assert c.post("/ingest", json=CLEAN).status_code == 200
    second = {**CLEAN, "deployment_id": "dep-B", "n_requests": 60, "catch_all_rate": 0.10,
              "by_category": [{"category": "extraction", "n": 60, "n_applied": 50, "incident_rate": 0.02}]}
    assert c.post("/ingest", json=second).status_code == 200
    agg = c.get("/agg").json()
    assert agg["n_deployments"] == 2
    assert agg["total_requests"] == 160
    assert agg["mean_catch_all_rate"] == 0.20
    assert agg["per_category"][0]["category"] == "extraction"
    assert any(p["phrase"] == "parse table" for p in agg["top_catchall_phrases"])


def test_sensitive_payload_is_rejected(tmp_path):
    c = _client(tmp_path)
    for bad in (
        {"deployment_id": "x", "messages": [{"role": "user", "content": "secret"}]},
        {"deployment_id": "x", "by_category": [{"category": "c", "example": "raw prompt text"}]},
        {"deployment_id": "x", "api_key": "sk-ant-leak"},
    ):
        r = c.post("/ingest", json=bad)
        assert r.status_code == 422, f"should reject {list(bad)}"


def test_latest_payload_per_deployment_wins(tmp_path):
    c = _client(tmp_path)
    c.post("/ingest", json={**CLEAN, "n_requests": 1})
    c.post("/ingest", json={**CLEAN, "n_requests": 999})  # same deployment_id, newer
    agg = c.get("/agg").json()
    assert agg["n_deployments"] == 1 and agg["total_requests"] == 999
