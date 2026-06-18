from modelpilot.continuation import ContinuationModel
from modelpilot.dashboard import collect_stats, render_html
from modelpilot.ledger import Ledger
from modelpilot.pricing import Usage
from modelpilot.router import recommend


def _body(prompt, model="claude-opus-4-8"):
    return {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}


CLASSIFY = "Classify this as positive or negative: 'fine'"


class FakeLedger:
    def __init__(self, lengths):
        self._lengths = lengths

    def session_lengths(self, *a, **k):
        return self._lengths


def test_continuation_falls_back_when_sparse():
    model = ContinuationModel(FakeLedger([3, 4, 5]), default_remaining=7.0)
    assert model.expected_remaining(1) == 7.0


def test_continuation_mean_residual_life():
    # 100 sessions: half end at 2 turns, half at 10.
    lengths = [2] * 50 + [10] * 50
    model = ContinuationModel(FakeLedger(lengths))
    # At turn 1 every session survives: E[L-1] = mean(L) - 1 = 5.
    assert abs(model.expected_remaining(1) - 5.0) < 1e-9
    # At turn 3 only the 10-turn sessions survive: E[10-3] = 7.
    assert abs(model.expected_remaining(3) - 7.0) < 1e-9
    # Deeper than anything observed: conversation is wrapping up.
    assert model.expected_remaining(11) == 1.0


def test_continuation_changes_routing_economics():
    # Simple task behind a large cached prefix: switching only pays if the
    # conversation is expected to keep going.
    big_turn = {"role": "user", "content": [
        {"type": "text", "text": "x" * 400_000, "cache_control": {"type": "ephemeral"}}]}
    # Classification stays a cheap-tier task even behind a huge cache (a *summary*
    # of this much context now correctly floors higher), so the turns-economics
    # flip (stay at 1 turn, switch at 40) is still demonstrable.
    body = {"model": "claude-opus-4-8", "max_tokens": 512,
            "messages": [big_turn, {"role": "assistant", "content": "ok"},
                         {"role": "user", "content": "Classify the sentiment of the message above as positive or negative."}]}
    short = recommend(body, expected_remaining_turns=1)
    long = recommend(body, expected_remaining_turns=40)
    assert short.action == "stay"
    assert long.action == "switch"


def test_ledger_session_tracking(tmp_path):
    ledger = Ledger(str(tmp_path / "t.db"))
    rec = recommend(_body(CLASSIFY))
    usage = Usage(input_tokens=100, output_tokens=10)
    for turn in range(3):
        ledger.record(mode="shadow", recommendation=rec, routed_model=rec.original_model,
                      applied=False, status_code=200, usage=usage, session_key="sess-a")
    ledger.record(mode="shadow", recommendation=rec, routed_model=rec.original_model,
                  applied=False, status_code=200, usage=usage, session_key="sess-b")
    assert ledger.turns_so_far("sess-a") == 3
    assert ledger.turns_so_far("sess-b") == 1
    assert ledger.turns_so_far("") == 0
    assert sorted(ledger.session_lengths()) == [1, 3]
    ledger.close()


def _seeded_ledger(tmp_path):
    ledger = Ledger(str(tmp_path / "d.db"))
    usage_cheap = Usage(input_tokens=1_000, output_tokens=200)
    rec = recommend(_body(CLASSIFY))
    for i in range(40):
        ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                      applied=True, status_code=200, usage=usage_cheap, arm="treatment",
                      session_key=f"s{i}")
    for i in range(35):
        ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.original_model,
                      applied=False, status_code=200, usage=usage_cheap, arm="control",
                      session_key=f"c{i}")
    return ledger


def test_collect_stats_and_rct(tmp_path):
    ledger = _seeded_ledger(tmp_path)
    stats = collect_stats(ledger, days=0)
    assert stats["summary"]["n"] == 75
    assert stats["rct"]["ready"]
    assert stats["rct"]["saving_pct"] > 0.5  # haiku vs opus on identical tokens
    assert stats["daily"]
    assert stats["daily_mix"]
    ledger.close()


def test_dashboard_html_renders(tmp_path):
    ledger = _seeded_ledger(tmp_path)
    html = render_html(collect_stats(ledger, days=0))
    for marker in ("ModelPilot", "Cumulative savings", "Verified saving",
                   "model mix", "<svg", "classification"):
        assert marker in html, marker
    ledger.close()


def test_chat_send_roundtrip(monkeypatch, tmp_path):
    """Chat playground loops back through the gateway's own /v1/messages."""
    import json, os, threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from fastapi.testclient import TestClient

    class FakeUpstream(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            resp = json.dumps({
                "id": "m", "type": "message", "model": body["model"],
                "content": [{"type": "text", "text": "negative"}], "stop_reason": "end_turn",
                "usage": {"input_tokens": 500, "output_tokens": 20},
            }).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        def log_message(self, *a):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 8495), FakeUpstream)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("MODELPILOT_MODE", "autopilot")
    monkeypatch.setenv("MODELPILOT_UPSTREAM", "http://127.0.0.1:8495")
    monkeypatch.setenv("MODELPILOT_DB", str(tmp_path / "chat.db"))
    monkeypatch.setenv("MODELPILOT_HOLDOUT_PCT", "0")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")

    import importlib
    from modelpilot import gateway as gw
    importlib.reload(gw)
    try:
        with TestClient(gw.app) as client:
            page = client.get("/modelpilot/chat")
            assert page.status_code == 200 and "ModelPilot chat" in page.text

            r = client.post("/modelpilot/chat/send", json={
                "messages": [{"role": "user", "content":
                              "Classify this review as positive or negative: 'broke instantly'"}],
                "model": "claude-opus-4-8", "session_id": "t1",
            })
            assert r.status_code == 200, r.text
            data = r.json()
            assert data["text"] == "negative"
            assert data["applied"] is True
            assert data["ran_on"] == "claude-haiku-4-5"
            assert data["saved"] > 0
            assert abs(data["cost_baseline"] - (500 * 5 + 20 * 25) / 1e6) < 1e-9
    finally:
        server.shutdown()
        importlib.reload(gw)  # restore module-level config for other tests


def test_preview_matches_execution(monkeypatch, tmp_path):
    """The pre-execution preview must predict exactly what /v1/messages does."""
    import json, threading
    from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
    from fastapi.testclient import TestClient

    class FakeUpstream(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            resp = json.dumps({"id": "m", "type": "message", "model": body["model"],
                               "content": [{"type": "text", "text": "ok"}],
                               "stop_reason": "end_turn",
                               "usage": {"input_tokens": 100, "output_tokens": 10}}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        def log_message(self, *a):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 8494), FakeUpstream)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    monkeypatch.setenv("MODELPILOT_MODE", "autopilot")
    monkeypatch.setenv("MODELPILOT_UPSTREAM", "http://127.0.0.1:8494")
    monkeypatch.setenv("MODELPILOT_DB", str(tmp_path / "pv.db"))
    monkeypatch.setenv("MODELPILOT_HOLDOUT_PCT", "0")

    import importlib
    from modelpilot import gateway as gw
    importlib.reload(gw)
    try:
        with TestClient(gw.app) as client:
            req = {"model": "claude-opus-4-8", "max_tokens": 64, "session_id": "pv1",
                   "messages": [{"role": "user", "content":
                                 "Classify this as positive or negative: 'great'"}]}
            pv = client.post("/modelpilot/preview", json=req).json()
            assert pv["applied"] is True
            assert pv["will_run_on"] == "claude-haiku-4-5"
            assert pv["est_saved"] > 0

            run = client.post("/v1/messages", json=req,
                              headers={"x-api-key": "k", "x-session-id": "pv1"})
            assert run.json()["model"] == pv["will_run_on"]  # prediction == execution

            # A hard prompt previews as stay
            hard = dict(req, messages=[{"role": "user", "content":
                        "Debug why the nightly job intermittently deadlocks under load."}])
            pv2 = client.post("/modelpilot/preview", json=hard).json()
            assert pv2["applied"] is False
            assert pv2["will_run_on"] == "claude-opus-4-8"
    finally:
        server.shutdown()
        importlib.reload(gw)


def test_session_view_and_history(tmp_path):
    """Dashboard: live session strip + per-session history table."""
    ledger = _seeded_ledger(tmp_path)
    # one chat-style session with three turns, two routed
    rec = recommend(_body(CLASSIFY))
    u = Usage(input_tokens=2_000, output_tokens=300)
    for applied in (True, True, False):
        ledger.record(mode="autopilot", recommendation=rec,
                      routed_model=rec.recommended_model if applied else rec.original_model,
                      applied=applied, status_code=200, usage=u,
                      arm="treatment", session_key="chat-demo1234")

    sess = ledger.session_summary("chat-demo1234")
    assert sess["n"] == 3 and sess["n_applied"] == 2
    assert sess["realized"] > 0
    recent = ledger.recent_sessions()
    assert recent[0]["session_key"] == "chat-demo1234"  # most recently active first

    stats = collect_stats(ledger, days=0, session="chat-demo1234")
    assert stats["session"]["n"] == 3
    html = render_html(stats)
    assert "THIS SESSION" in html
    assert "chat-demo1234" in html
    assert "Recent sessions" in html
    assert "setInterval(mpTick" in html          # live updates
    assert 'id="s-realized"' in html

    # Without a pinned session, the strip falls back to the latest one
    html2 = render_html(collect_stats(ledger, days=0))
    assert "LATEST SESSION" in html2
    ledger.close()
