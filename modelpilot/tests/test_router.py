from modelpilot.router import extract_features, recommend


def _body(prompt, model="claude-opus-4-8", **kwargs):
    return {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}], **kwargs}


def test_classification_prompt_routes_to_haiku():
    rec = recommend(_body("Classify this review as positive or negative: 'Great product, fast shipping!'"))
    assert rec.action == "switch"
    assert rec.recommended_model == "claude-haiku-4-5"
    assert rec.confidence >= 0.7


def test_structured_output_contract_floors_to_sonnet():
    prompt = "Classify this review as positive or negative: 'Great product, fast shipping!'"
    # Without a schema, classification routes to Haiku...
    assert recommend(_body(prompt)).recommended_model == "claude-haiku-4-5"
    # ...but a machine-enforced output contract must not be downgraded below Sonnet,
    # since a cheaper model could break brittle downstream parsing.
    schema_body = _body(prompt, output_config={"format": {"type": "json_schema", "schema": {}}})
    rec = recommend(schema_body)
    assert rec.recommended_model == "claude-sonnet-4-6"
    assert extract_features(schema_body)["has_structured_output"] is True


def test_response_format_also_floors_to_sonnet():
    rec = recommend(_body("Extract the order id from: 'order #A-1 shipped'.",
                          response_format={"type": "json_object"}))
    assert rec.recommended_model != "claude-haiku-4-5"


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
    # Simple task, but a huge cached conversation behind it. (Use a classification
    # task: a *summary* of this much context now correctly floors higher, so it's no
    # longer a "simple task" — classification stays cheap-tier and still exercises
    # the cache-economics veto.)
    big_turn = {"role": "user", "content": [{"type": "text", "text": "x" * 400_000, "cache_control": {"type": "ephemeral"}}]}
    body = {
        "model": "claude-opus-4-8",
        "max_tokens": 512,
        "messages": [big_turn, {"role": "assistant", "content": "ok"},
                     {"role": "user", "content": "Classify the sentiment of the message above as positive or negative."}],
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


# --- session-context-aware routing -----------------------------------------

DEBUG_Q = "Debug why my nightly job intermittently fails with a deadlock under load."
DEBUG_A = ("The deadlock comes from two workers acquiring the row locks in opposite "
           "order. Serialize the lock acquisition or use SELECT ... FOR UPDATE SKIP LOCKED.")


def _session(*texts, model="claude-opus-4-8"):
    roles = ["user", "assistant"]
    return {"model": model, "max_tokens": 1024,
            "messages": [{"role": roles[i % 2], "content": t} for i, t in enumerate(texts)]}


def test_followup_inherits_session_difficulty():
    body = _session(DEBUG_Q, DEBUG_A, "why?")
    rec = recommend(body)
    assert rec.category == "followup_in_context"
    assert "inheriting session difficulty" in rec.rationale
    assert rec.action == "stay"  # opus baseline, inherited tier == opus
    assert rec.recommended_model == "claude-opus-4-8"


def test_followup_inheritance_from_fable_rightsizes_to_opus():
    body = _session(DEBUG_Q, DEBUG_A, "ok now fix it", model="claude-fable-5")
    rec = recommend(body)
    assert rec.action == "switch"
    assert rec.recommended_model == "claude-opus-4-8"  # not haiku/sonnet
    assert rec.confidence >= 0.8


def test_mechanical_task_keeps_cheap_tier_in_hard_session():
    # "leverage existing contents": extraction over the hard transcript is
    # still mechanical work — haiku-safe per calibration.
    body = _session(DEBUG_Q, DEBUG_A,
                    "Extract the two suggested fixes from the above as a JSON list.")
    rec = recommend(body)
    assert rec.action == "switch"
    assert rec.recommended_model == "claude-haiku-4-5"


def test_independent_fresh_task_in_hard_session_routes_cheap():
    # Carries its own content, references nothing — no inheritance.
    body = _session(DEBUG_Q, DEBUG_A,
                    "Classify the sentiment of this unrelated review as positive or negative: 'lovely product'")
    rec = recommend(body)
    assert rec.action == "switch"
    assert rec.recommended_model == "claude-haiku-4-5"


def test_followup_in_easy_session_not_escalated():
    body = _session("Translate to French: Good morning.", "Bonjour.",
                    "now do it in Spanish instead")
    rec = recommend(body)
    # Easy session: nothing to inherit; the follow-up must not jump tiers.
    assert rec.recommended_model in ("claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8")
    assert rec.category != "followup_in_context" or rec.recommended_model != "claude-opus-4-8"


def test_single_turn_unaffected_by_context_layer():
    rec = recommend(_body("Classify this review as positive or negative: 'great!'"))
    assert rec.recommended_model == "claude-haiku-4-5"
    assert rec.confidence >= 0.8


# --- content-difficulty features (calibration v0 -> v0.1) -------------------

INCIDENT = ("09:02 deploy of build 4811. 09:14 p95 latency on /checkout rises to 2.4s. "
            "09:21 errors hit 11% (pool exhaustion). 09:31 rollback complete but errors persist.")


def test_audience_constraint_floors_summarization_at_sonnet():
    # The seed-027 false downgrade: public-facing rewrite of incident content.
    rec = recommend(_body(f"Summarize this incident in two sentences for a status page "
                          f"(no internal details):\n\n{INCIDENT}"))
    assert rec.recommended_model == "claude-sonnet-4-6"
    assert rec.confidence >= 0.8  # clears the shipped autopilot gate
    assert "audience-constrained" in rec.rationale


def test_hard_content_reduces_confidence_not_tier():
    # Postmortem summary of the same material was haiku-fine per the judge:
    # keep the haiku recommendation but drop below the autopilot gate.
    rec = recommend(_body(f"Summarize this incident for the postmortem doc:\n\n{INCIDENT}"))
    assert rec.recommended_model == "claude-haiku-4-5"
    assert 0.7 <= rec.confidence < 0.8
    assert "dense operational/legal content" in rec.rationale


def test_plain_summarization_unaffected_by_content_features():
    rec = recommend(_body("TL;DR this support ticket in one sentence: customer was charged "
                          "twice for the Pro plan and wants a refund."))
    assert rec.recommended_model == "claude-haiku-4-5"
    assert rec.confidence >= 0.85


# --- long-document summarization: must floor at Sonnet, never Haiku ---
_LONG_THREAD = "\n".join(
    f"[{i:03d}] " + msg for i, msg in enumerate(
        ["Customer: hi, I'd like to switch my plan from monthly to annual.",
         "Agent: happy to help — annual saves you about 15% versus monthly.",
         "Customer: nice. does the new price apply now or on my next renewal?",
         "Agent: it applies on your next renewal date, the 14th.",
         "Customer: can I also update the card you have on file?",
         "Agent: of course — it's under Settings, then Payment methods.",
         "Customer: the page just keeps spinning on my phone though.",
         "Agent: try the desktop site for now, or I can update it for you.",
         "Customer: please go ahead and move me to the annual plan.",
         "Agent: all set — you'll see the annual plan on your next invoice.",
         "Customer: thanks. when does the receipt arrive?",
         "Agent: the receipt emails right after the renewal goes through."] * 40))


def test_long_document_summary_floors_sonnet():
    body = _body("Summarize the key issue and the resolution in this support thread "
                 "in 3 bullets.\n\n" + _LONG_THREAD)
    assert extract_features(body)["approx_context_tokens"] >= 6000
    rec = recommend(body)
    assert rec.category == "summarization_long"
    assert rec.recommended_model == "claude-sonnet-4-6"  # floored at sonnet, not haiku
    assert rec.recommended_model != "claude-haiku-4-5"


def test_short_summary_still_routes_to_haiku():
    rec = recommend(_body("Summarize this in one line: 'The meeting was moved to 3pm Friday.'"))
    assert rec.category == "summarization_short"
    assert rec.recommended_model == "claude-haiku-4-5"
