"""Telemetry must carry aggregates only — never prompt text/outputs/keys."""

import json

from modelpilot.ledger import Ledger
from modelpilot.pricing import Usage
from modelpilot.router import Recommendation
from modelpilot.telemetry import build_payload

SECRET_PROMPT = "Reconcile invoice INV-99 for ACME-SECRET-CLIENT and email bob@secret.com"


def _seed(path):
    L = Ledger(path)
    for i in range(6):
        rec = Recommendation("switch", "claude-opus-4-8", "claude-haiku-4-5",
                             0.85, "extraction", "simple-task signal")
        rid = L.record(mode="autopilot", recommendation=rec, routed_model="claude-haiku-4-5",
                       applied=True, status_code=200,
                       usage=Usage(input_tokens=500, output_tokens=200), session_key=f"s{i}")
        # captured prompts carry the SECRET text + a recurring catch-all phrase
        L.record_capture(f"c{i}", "conversation", 0.5,
                         f"draft a reply to support ticket {SECRET_PROMPT} number {i}")
    L.close()


def test_payload_has_no_prompt_text(tmp_path):
    db = str(tmp_path / "t.db")
    _seed(db)
    payload = build_payload(db, days=0)
    blob = json.dumps(payload)
    assert "ACME-SECRET-CLIENT" not in blob and "bob@secret.com" not in blob
    assert "INV-99" not in blob
    # but the useful aggregates are present
    assert payload["n_requests"] == 6
    assert payload["by_category"] and payload["deployment_id"]
    assert payload["_privacy"].startswith("aggregates only")
    assert "catchall_phrase_signals" not in payload  # off unless --with-phrases


def test_phrase_signals_are_k_anonymous_and_textless(tmp_path):
    db = str(tmp_path / "t.db")
    _seed(db)
    payload = build_payload(db, days=0, with_phrases=True, min_docs=3)
    blob = json.dumps(payload)
    # the recurring phrase signal may appear, but never the secret/unique content
    assert "ACME-SECRET-CLIENT" not in blob and "bob@secret.com" not in blob
    sigs = payload.get("catchall_phrase_signals", [])
    for s in sigs:
        assert s["docs"] >= 3                 # k-anonymity floor enforced
        assert "example" not in s             # no example snippet shipped


def test_deployment_id_is_stable(tmp_path):
    db = str(tmp_path / "t.db")
    _seed(db)
    assert build_payload(db, days=0)["deployment_id"] == build_payload(db, days=0)["deployment_id"]
