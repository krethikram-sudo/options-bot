"""Retry/fallback decision logic + proxy integration (fall back to original model)."""

import asyncio

import pytest

from modelpilot import retry


def test_retriable_and_plan_basics():
    # non-retriable status -> stop
    assert retry.plan(200, 0, 2, "claude-haiku-4-5", "claude-opus-4-8") is None
    assert retry.plan(400, 0, 2, "claude-haiku-4-5", "claude-opus-4-8") is None
    # out of attempts -> stop
    assert retry.plan(529, 2, 2, "claude-haiku-4-5", "claude-opus-4-8") is None


def test_first_retry_falls_back_to_original():
    p = retry.plan(529, 0, 2, "claude-haiku-4-5", "claude-opus-4-8", fallback=True)
    assert p["model"] == "claude-opus-4-8" and p["attempt"] == 1 and p["reason"] == "fallback-to-original"


def test_retry_same_model_when_no_fallback_or_same_model():
    assert retry.plan(503, 0, 2, "claude-opus-4-8", "claude-opus-4-8")["model"] == "claude-opus-4-8"
    p = retry.plan(503, 0, 2, "claude-haiku-4-5", "claude-opus-4-8", fallback=False)
    assert p["model"] == "claude-haiku-4-5" and p["reason"] == "retry"


def test_backoff_honors_retry_after_and_caps():
    assert retry.backoff_seconds(0, retry_after="2") == 2.0
    assert retry.backoff_seconds(0) == 0.5
    assert retry.backoff_seconds(1) == 1.0
    assert retry.backoff_seconds(10) == retry.DEFAULT_CAP  # capped
    assert retry.backoff_seconds(0, retry_after="bogus") == 0.5  # bad header ignored


# --- proxy integration: a fake async client that fails then succeeds --------

class _Resp:
    def __init__(self, status, content=b"ok", headers=None):
        self.status_code = status
        self.content = content
        self.headers = headers or {}
        self.closed = False

    async def aread(self):
        return self.content

    async def aclose(self):
        self.closed = True


class _FakeClient:
    """Records the model in each POST body; returns queued responses in order."""
    def __init__(self, responses):
        self._responses = list(responses)
        self.sent_models = []

    async def post(self, url, content=None, headers=None):
        import json
        self.sent_models.append(json.loads(content)["model"])
        return self._responses.pop(0)


@pytest.fixture()
def proxy(monkeypatch):
    import modelpilot.client_proxy as cp
    monkeypatch.setattr(cp, "MAX_RETRIES", 2)
    monkeypatch.setattr(cp, "FALLBACK", True)
    return cp


def _run(coro):
    return asyncio.run(coro)


class _Req:
    def __init__(self, raw):
        self._raw = raw
        self.headers = {"x-api-key": "sk", "content-type": "application/json"}

    async def body(self):
        return self._raw


def test_proxy_retries_then_falls_back(proxy, monkeypatch):
    import json
    # routed to haiku; first attempt 529, retry succeeds on the original opus
    fake = _FakeClient([_Resp(529, b"overloaded", {"retry-after": "0"}), _Resp(200, b"done")])
    monkeypatch.setattr(proxy, "_client", lambda: fake)
    monkeypatch.setattr(proxy, "_decide", lambda body: ("claude-haiku-4-5", "switch:cls:haiku"))
    monkeypatch.setattr(proxy, "_fwd_headers", lambda r: {"x-api-key": "sk"})
    raw = json.dumps({"model": "claude-opus-4-8", "max_tokens": 8,
                      "messages": [{"role": "user", "content": "hi"}]}).encode()
    resp = _run(proxy.messages(_Req(raw)))
    assert resp.status_code == 200
    # first send used the routed haiku, retry fell back to the original opus
    assert fake.sent_models == ["claude-haiku-4-5", "claude-opus-4-8"]
    assert "fallback-to-original" in resp.headers["x-modelpilot-decision"]


def test_proxy_no_retry_on_success(proxy, monkeypatch):
    import json
    fake = _FakeClient([_Resp(200, b"done")])
    monkeypatch.setattr(proxy, "_client", lambda: fake)
    monkeypatch.setattr(proxy, "_decide", lambda body: ("claude-haiku-4-5", "switch"))
    monkeypatch.setattr(proxy, "_fwd_headers", lambda r: {"x-api-key": "sk"})
    raw = json.dumps({"model": "claude-opus-4-8", "max_tokens": 8,
                      "messages": [{"role": "user", "content": "hi"}]}).encode()
    resp = _run(proxy.messages(_Req(raw)))
    assert resp.status_code == 200 and fake.sent_models == ["claude-haiku-4-5"]
