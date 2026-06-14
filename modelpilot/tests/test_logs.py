"""Opt-in request logs: metadata-only shipping, marker advance, OTLP shape."""

from modelpilot import logs
from modelpilot.ledger import Ledger
from modelpilot.pricing import Usage
from modelpilot.router import Recommendation


def _seed(path, n=3):
    led = Ledger(str(path))
    for i in range(n):
        rec = Recommendation(action="switch", original_model="claude-opus-4-8",
                             recommended_model="claude-haiku-4-5", confidence=0.9,
                             category="classification", rationale="secret reasoning text")
        led.record(mode="autopilot", recommendation=rec, routed_model="claude-haiku-4-5",
                   applied=True, status_code=200,
                   usage=Usage(input_tokens=100, output_tokens=50),
                   arm="treatment", retry_of=None, request_id=f"r{i}", session_key="s")
    led.close()


def test_ship_console_metadata_only_and_marker(tmp_path):
    db = tmp_path / "l.db"
    _seed(db, 3)
    sent = []
    res = logs.ship_once(str(db), "http://console", "dep_x", post_fn=sent.append)
    assert res["shipped"] == 3 and res["console"] is True
    payload = sent[0]
    assert payload["deployment_id"] == "dep_x" and len(payload["logs"]) == 3
    row = payload["logs"][0]
    # metadata only — no prompt/rationale/text anywhere
    assert "rationale" not in row and "prompt" not in row and "_rowid" not in row
    assert row["routed_model"] == "claude-haiku-4-5" and row["applied"] is True
    assert row["input_tokens"] == 100 and "actual_cost" in row
    # nothing new on a second run (marker advanced)
    assert logs.ship_once(str(db), "http://console", "dep_x", post_fn=sent.append)["shipped"] == 0


def test_otlp_payload_shape():
    rows = [{"ts": 1.0, "category": "extraction", "routed_model": "claude-haiku-4-5",
             "applied": True, "input_tokens": 10, "actual_cost": 0.001}]
    p = logs.otlp_payload(rows)
    span = p["resourceSpans"][0]["scopeSpans"][0]["spans"][0]
    assert span["name"] == "modelpilot.route:extraction"
    keys = {a["key"] for a in span["attributes"]}
    assert "modelpilot.category" in keys and "modelpilot.routed_model" in keys


def test_otel_export_only(tmp_path):
    db = tmp_path / "l2.db"
    _seed(db, 2)
    otel = []
    res = logs.ship_once(str(db), "", "", otel_endpoint="http://collector",
                         otel_post_fn=otel.append)
    assert res["shipped"] == 2 and res["otel"] is True and res["console"] is False
    assert otel[0]["resourceSpans"]


def test_ship_noop_without_sinks(tmp_path):
    db = tmp_path / "l3.db"
    _seed(db, 1)
    assert logs.ship_once(str(db), "", "")["shipped"] == 0
