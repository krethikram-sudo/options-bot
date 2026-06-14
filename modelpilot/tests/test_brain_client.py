"""Client seam: build_request leaks no prompt text; remote_decide fails open."""

import json

from modelpilot.brain_client import build_request, remote_decide

SECRET = "Reconcile invoice for ACME-SECRET and email bob@secret.com"


def _body(prompt, model="claude-opus-4-8"):
    return {"model": model, "max_tokens": 512, "messages": [{"role": "user", "content": prompt}]}


def test_build_request_has_no_prompt_text():
    req = build_request(_body(SECRET), deployment_id="dep-1")
    blob = json.dumps(req)
    assert "ACME-SECRET" not in blob and "bob@secret.com" not in blob and "invoice" not in blob
    # but the useful, non-sensitive signal is present
    assert req["category"] and req["original_model"] == "claude-opus-4-8"
    assert set(req["features"]) and "prompt" not in req["features"]
    assert req["deployment_id"] == "dep-1"


def test_remote_decide_fails_open_when_brain_unreachable():
    # nothing listening on this port -> None (gateway then falls back locally)
    out = remote_decide(_body("classify this"), "http://127.0.0.1:9", deployment_id="dep-1")
    assert out is None


def test_license_token_passed_but_no_prompt():
    req = build_request(_body(SECRET), deployment_id="d", license_token="tok-123")
    assert req["license"] == "tok-123"
    assert SECRET not in json.dumps(req)
