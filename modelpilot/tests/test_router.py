from modelpilot.router import extract_features, recommend


def _body(prompt, model="claude-opus-4-8", **kwargs):
    return {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}], **kwargs}


def test_classification_prompt_routes_to_haiku():
    rec = recommend(_body("Classify this review as positive or negative: 'Great product, fast shipping!'"))
    assert rec.action == "switch"
    assert rec.recommended_model == "claude-haiku-4-5"
    assert rec.confidence >= 0.7


def test_complex_refactor_stays_on_opus():
    rec = recommend(_body("Refactor the billing module across multiple files to use the new event-driven architecture."))
    assert rec.action == "stay"
    assert rec.recommended_model == "claude-opus-4-8"


def test_never_recommends_above_requested_model():
    rec = recommend(_body("Prove that this scheduling problem is NP-hard.", model="claude-haiku-4-5"))
    assert rec.action == "stay"
    assert rec.recommended_model == "claude-haiku-4-5"


def test_unknown_model_passes_through():
    rec = recommend(_body("Classify this as spam or not.", model="some-custom-model"))
    assert rec.action == "stay"
    assert rec.confidence == 1.0


def test_ambiguous_prompt_does_nothing():
    rec = recommend(_body("Help me think about my career options over the next five years."))
    # Conversation/unknown floors at sonnet or opus; from opus this may switch
    # to sonnet but never below, and never with high confidence.
    assert rec.recommended_model != "claude-haiku-4-5"
    assert rec.confidence < 0.8


def test_cache_trap_vetoes_switch():
    # Simple task, but a huge cached conversation behind it.
    big_turn = {"role": "user", "content": [{"type": "text", "text": "x" * 400_000, "cache_control": {"type": "ephemeral"}}]}
    body = {
        "model": "claude-opus-4-8",
        "max_tokens": 512,
        "messages": [big_turn, {"role": "assistant", "content": "ok"},
                     {"role": "user", "content": "Summarize the key points of the above."}],
    }
    rec = recommend(body, expected_remaining_turns=1)
    assert rec.action == "stay"
    assert "cache-rewrite penalty" in rec.rationale


def test_tool_use_treated_as_agentic():
    body = _body("Find the cheapest flight and book it.", tools=[{"name": "search_flights", "input_schema": {"type": "object"}}])
    rec = recommend(body)
    assert rec.category == "agentic"
    assert rec.action == "stay"


def test_features_do_not_leak_prompt_text():
    rec = recommend(_body("Translate to French: secret internal memo contents"))
    assert "secret" not in str(rec.features)


def test_extract_features_counts_context():
    body = _body("Extract all email addresses from this text as JSON.")
    f = extract_features(body)
    assert f["n_turns"] == 1
    assert f["approx_context_tokens"] > 0
    assert not f["has_tools"]
