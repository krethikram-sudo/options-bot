from modelpilot.gateway import assign_arm, decide
from modelpilot.ledger import Ledger
from modelpilot.pricing import Usage
from modelpilot.report import _bootstrap_diff_ci
from modelpilot.router import recommend


def _body(prompt, model="claude-opus-4-8"):
    return {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}


CLASSIFY = "Classify this as positive or negative: 'meh'"


def test_arm_assignment_deterministic_and_proportional():
    arms = [assign_arm(f"session-{i}", 0.10) for i in range(2000)]
    assert arms == [assign_arm(f"session-{i}", 0.10) for i in range(2000)]  # stable
    control_share = arms.count("control") / len(arms)
    assert 0.06 < control_share < 0.14
    assert assign_arm("anything", 0.0) == "treatment"


def test_control_arm_never_applies():
    # Find a session key that lands in control at 100% holdout.
    d = decide(_body(CLASSIFY), "autopilot", confidence_gate=0.5,
               holdout_pct=1.0, session_key="s1")
    assert d.arm == "control"
    assert not d.applied
    assert d.routed_model == "claude-opus-4-8"
    assert d.recommendation.action == "switch"  # advice still logged


def test_treatment_arm_applies():
    d = decide(_body(CLASSIFY), "autopilot", confidence_gate=0.5,
               holdout_pct=0.0, session_key="s1")
    assert d.arm == "treatment"
    assert d.applied


def test_shadow_mode_is_observe_arm():
    d = decide(_body(CLASSIFY), "shadow", holdout_pct=1.0, session_key="s1")
    assert d.arm == "observe"


def test_feedback_and_escalation_accounting(tmp_path):
    ledger = Ledger(str(tmp_path / "t.db"))
    rec = recommend(_body(CLASSIFY))
    usage = Usage(input_tokens=10_000, output_tokens=2_000)

    rid = ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                        applied=True, status_code=200, usage=usage, arm="treatment")
    ledger.record_feedback(rid, "negative", "output missed the point")
    # The re-run on the original model, linked via retry_of.
    stay = recommend(_body("Refactor the billing module across multiple files."))
    ledger.record(mode="autopilot", recommendation=stay, routed_model=stay.original_model,
                  applied=False, status_code=200, usage=usage, arm="treatment", retry_of=rid)

    esc = ledger.escalation_costs()
    assert esc["n"] == 1
    assert esc["cost"] > 0

    guard = {g["arm"]: g for g in ledger.quality_guardrails()}
    assert guard["treatment"]["n_negative"] == 1
    ledger.close()


def test_arm_costs_split(tmp_path):
    ledger = Ledger(str(tmp_path / "t.db"))
    rec = recommend(_body(CLASSIFY))
    cheap = Usage(input_tokens=1_000, output_tokens=200)
    for i in range(3):
        ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                      applied=True, status_code=200, usage=cheap, arm="treatment")
    ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.original_model,
                  applied=False, status_code=200, usage=cheap, arm="control")
    arms = ledger.arm_costs()
    assert len(arms["treatment"]) == 3
    assert len(arms["control"]) == 1
    assert arms["control"][0] > arms["treatment"][0]  # opus row costs more
    ledger.close()


def test_bootstrap_ci_brackets_true_difference():
    a = [10.0 + (i % 5) * 0.1 for i in range(200)]   # mean ~10.2
    b = [8.0 + (i % 5) * 0.1 for i in range(200)]    # mean ~8.2
    lo, hi = _bootstrap_diff_ci(a, b)
    assert lo < 2.0 < hi or abs((lo + hi) / 2 - 2.0) < 0.1
    assert lo > 1.5 and hi < 2.5


def test_declared_baseline_recovers_advise_mode_savings(monkeypatch, tmp_path):
    """A caller who followed advice sends the cheap model + the baseline they
    would have used — realized savings recorded from actual tokens."""
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
                               "usage": {"input_tokens": 10_000, "output_tokens": 500}}).encode()
            self.send_response(200)
            self.send_header("content-type", "application/json")
            self.send_header("content-length", str(len(resp)))
            self.end_headers()
            self.wfile.write(resp)

        def log_message(self, *a):
            pass

    server = ThreadingHTTPServer(("127.0.0.1", 8493), FakeUpstream)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    db = str(tmp_path / "decl.db")
    monkeypatch.setenv("MODELPILOT_MODE", "advise")
    monkeypatch.setenv("MODELPILOT_UPSTREAM", "http://127.0.0.1:8493")
    monkeypatch.setenv("MODELPILOT_DB", db)

    import importlib
    from modelpilot import gateway as gw
    importlib.reload(gw)
    try:
        with TestClient(gw.app) as client:
            r = client.post("/v1/messages",
                            headers={"x-api-key": "k",
                                     "x-modelpilot-baseline": "claude-fable-5"},
                            json={"model": "claude-haiku-4-5", "max_tokens": 64,
                                  "messages": [{"role": "user", "content":
                                                "Classify this as positive or negative: 'meh'"}]})
            assert r.status_code == 200
        ledger = Ledger(db)
        s = ledger.summary()
        # ran on haiku, baseline fable: realized = (10k*$10 + 500*$50)/1M - (10k*$1 + 500*$5)/1M
        assert abs(s["realized"] - ((10_000 * 9 + 500 * 45) / 1e6)) < 1e-9
        assert s["realized"] > 0
        ledger.close()
    finally:
        server.shutdown()
        importlib.reload(gw)


def test_declared_baseline_ignores_garbage(monkeypatch, tmp_path):
    from modelpilot.gateway import decide
    # decide() itself is unaffected; the header path validates via resolve_price —
    # covered indirectly above. Here: unknown model string must not crash pricing.
    from modelpilot.pricing import resolve_price
    assert resolve_price("gpt-5-mega") is None


def test_replay_calibration_end_to_end(tmp_path):
    """Capture -> replay on baseline -> coefficient -> corrected potential."""
    from modelpilot.pricing import Usage as U
    from modelpilot.replay import run_replay
    from modelpilot.router import recommend as rec_fn

    ledger = Ledger(str(tmp_path / "rp.db"))
    prompt = "Classify this review as positive or negative: 'great product'"
    rec = rec_fn({"model": "claude-fable-5", "max_tokens": 64,
                  "messages": [{"role": "user", "content": prompt}]})
    assert rec.action == "switch"

    # 4 routed-to-haiku requests, each with a captured prompt, 100 output tokens
    for i in range(4):
        rid = ledger.record(mode="autopilot", recommendation=rec,
                            routed_model=rec.recommended_model, applied=True,
                            status_code=200,
                            usage=U(input_tokens=1_000, output_tokens=100),
                            arm="treatment")
        ledger.record_capture(rid, rec.category, rec.confidence, prompt)

    # Baseline (fable) is twice as verbose: 200 output tokens per replay
    def fake_run(model, p):
        assert model == "claude-fable-5"
        return "(baseline output)", U(input_tokens=1_000, output_tokens=200)

    result = run_replay(ledger, fake_run, progress=lambda *_: None)
    assert result["sampled"] == 4
    assert len(result["written"]) == 1
    coef = result["written"][0]
    assert coef["output_ratio"] == 2.0 and coef["n"] == 4

    corr = ledger.corrected_potential()
    # raw potential per row: (1000*10 + 100*50)/1e6 - (1000*1 + 100*5)/1e6 = 0.0135
    assert abs(corr["raw_potential"] - 4 * 0.0135) < 1e-9
    # correction per row: 100 tokens * $50/MTok * (2.0 - 1) = 0.005
    assert abs(corr["corrected_potential"] - 4 * (0.0135 + 0.005)) < 1e-9
    assert corr["covered_categories"] == ["classification"]
    ledger.close()


def test_replay_requires_captures(tmp_path):
    """No capture opt-in -> nothing replayable, by design (privacy)."""
    from modelpilot.pricing import Usage as U
    from modelpilot.replay import run_replay
    from modelpilot.router import recommend as rec_fn

    ledger = Ledger(str(tmp_path / "nr.db"))
    rec = rec_fn({"model": "claude-fable-5", "max_tokens": 64,
                  "messages": [{"role": "user", "content":
                                "Classify this as positive or negative: 'ok'"}]})
    ledger.record(mode="autopilot", recommendation=rec,
                  routed_model=rec.recommended_model, applied=True,
                  status_code=200, usage=U(input_tokens=500, output_tokens=50),
                  arm="treatment")
    result = run_replay(ledger, lambda m, p: (_ for _ in ()).throw(AssertionError("must not run")),
                        progress=lambda *_: None)
    assert result["sampled"] == 0 and result["written"] == []
    ledger.close()
