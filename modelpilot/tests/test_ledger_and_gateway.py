import json

from modelpilot.gateway import _SSEUsage, decide
from modelpilot.ledger import Ledger
from modelpilot.pricing import Usage
from modelpilot.router import recommend


def _body(prompt, model="claude-opus-4-8"):
    return {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}


CLASSIFY = "Classify this review as positive or negative: 'terrible, broke in a day'"


def test_shadow_and_advise_never_alter_request():
    for mode in ("shadow", "advise"):
        d = decide(_body(CLASSIFY), mode)
        assert d.routed_model == "claude-opus-4-8"
        assert not d.applied
        assert d.recommendation.action == "switch"  # advice exists, just not applied


def test_autopilot_switches_above_gate():
    d = decide(_body(CLASSIFY), "autopilot", confidence_gate=0.7)
    assert d.applied
    assert d.routed_model == "claude-haiku-4-5"


def test_autopilot_respects_confidence_gate():
    d = decide(_body("Help me plan my week."), "autopilot", confidence_gate=0.99)
    assert not d.applied
    assert d.routed_model == "claude-opus-4-8"


def test_ledger_realized_vs_potential(tmp_path):
    ledger = Ledger(str(tmp_path / "test.db"))
    usage = Usage(input_tokens=10_000, output_tokens=2_000)
    rec = recommend(_body(CLASSIFY))

    # Shadow: nothing applied -> realized 0, potential > 0
    ledger.record(mode="shadow", recommendation=rec, routed_model=rec.original_model,
                  applied=False, status_code=200, usage=usage)
    # Autopilot: applied -> realized == potential
    ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                  applied=True, status_code=200, usage=usage)

    s = ledger.summary()
    assert s["n"] == 2
    assert s["realized"] > 0
    assert s["potential"] > s["realized"]  # both rows contribute potential
    assert s["n_applied"] == 1

    cats = ledger.by_category()
    assert cats[0]["category"] == rec.category
    ledger.close()


def test_ledger_records_and_sums_opportunity(tmp_path):
    ledger = Ledger(str(tmp_path / "opp.db"))
    usage = Usage(input_tokens=10_000, output_tokens=2_000)
    rec = recommend(_body(CLASSIFY))
    ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                  applied=True, status_code=200, usage=usage, opportunity_saved=0.0123)
    ledger.record(mode="autopilot", recommendation=rec, routed_model=rec.recommended_model,
                  applied=True, status_code=200, usage=usage, opportunity_saved=0.0077)
    s = ledger.summary()
    assert abs(s["opportunity_saved"] - 0.02) < 1e-9
    ledger.close()


def test_advice_headers_surface_opportunities():
    from modelpilot.gateway import Decision, _advice_headers
    rec = recommend(_body(CLASSIFY))
    d = Decision(recommendation=rec, routed_model=rec.original_model, applied=False,
                 opportunities=[{"type": "prompt_cache", "est_savings": 0.0021},
                                {"type": "batch_api", "est_savings": 0.0009}])
    h = _advice_headers(d)
    assert h["x-modelpilot-opportunity-prompt-cache-usd"] == "0.002100"
    assert h["x-modelpilot-opportunity-batch-api-usd"] == "0.000900"
    assert abs(d.opportunity_saved() - 0.003) < 1e-9


def test_sse_usage_extraction_across_chunks():
    events = [
        {"type": "message_start", "message": {"usage": {"input_tokens": 1200, "cache_read_input_tokens": 800}}},
        {"type": "content_block_delta", "delta": {"type": "text_delta", "text": "hi"}},
        {"type": "message_delta", "usage": {"output_tokens": 345}},
    ]
    raw = b"".join(f"event: x\ndata: {json.dumps(e)}\n\n".encode() for e in events)
    sse = _SSEUsage()
    # Feed in awkward chunk sizes to exercise partial-line buffering.
    for i in range(0, len(raw), 17):
        sse.feed(raw[i:i + 17])
    assert sse.usage.input_tokens == 1200
    assert sse.usage.cache_read_input_tokens == 800
    assert sse.usage.output_tokens == 345
