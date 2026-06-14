"""Full-gateway request-path parity: retry/fallback helper behavior."""

import asyncio
import json

from modelpilot import gateway


class _Resp:
    def __init__(self, status, content=b'{"ok":1}', headers=None):
        self.status_code = status; self.content = content
        self.headers = headers or {}
    async def aread(self): return self.content
    async def aclose(self): pass


class _FakeHTTP:
    def __init__(self, responses):
        self._r = list(responses); self.models = []
    async def post(self, url, content=None, headers=None):
        self.models.append(json.loads(content)["model"]); return self._r.pop(0)


def _set(monkeypatch, http, **cfg):
    monkeypatch.setattr(gateway.app.state, "http", http, raising=False)
    monkeypatch.setattr(gateway, "MAX_RETRIES", cfg.get("max", 2))
    monkeypatch.setattr(gateway, "FALLBACK", cfg.get("fallback", True))


def test_gateway_retry_falls_back_to_original(monkeypatch):
    http = _FakeHTTP([_Resp(529, headers={"retry-after": "0"}), _Resp(200, b'{"done":1}')])
    _set(monkeypatch, http)
    body = {"model": "claude-opus-4-8", "max_tokens": 8, "messages": [{"role": "user", "content": "hi"}]}
    resp, ran, notes = asyncio.run(gateway._send_with_retry(
        "http://up/v1/messages", body, {}, "claude-haiku-4-5", "claude-opus-4-8", False))
    assert resp.status_code == 200
    assert http.models == ["claude-haiku-4-5", "claude-opus-4-8"]  # routed then fallback
    assert ran == "claude-opus-4-8" and notes and "fallback-to-original" in notes[0]


def test_gateway_no_retry_on_success(monkeypatch):
    http = _FakeHTTP([_Resp(200, b'{"done":1}')])
    _set(monkeypatch, http)
    body = {"model": "claude-opus-4-8", "max_tokens": 8, "messages": [{"role": "user", "content": "hi"}]}
    resp, ran, notes = asyncio.run(gateway._send_with_retry(
        "http://up/v1/messages", body, {}, "claude-haiku-4-5", "claude-opus-4-8", False))
    assert resp.status_code == 200 and ran == "claude-haiku-4-5" and notes == []
