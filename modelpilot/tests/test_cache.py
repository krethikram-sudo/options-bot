"""Exact-match response cache + proxy cache integration (MISS then HIT at $0)."""

import asyncio
import json

import pytest

from modelpilot import cache


def test_request_key_stable_and_order_independent():
    a = {"model": "claude-opus-4-8", "max_tokens": 8, "messages": [{"role": "user", "content": "hi"}]}
    b = {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 8, "model": "claude-opus-4-8"}
    assert cache.request_key(a) == cache.request_key(b)
    c = {**a, "max_tokens": 9}
    assert cache.request_key(a) != cache.request_key(c)


def test_cache_get_put_ttl_and_evict():
    c = cache.ResponseCache(ttl=10, maxsize=2)
    c.put("k1", b"one", now=100)
    assert c.get("k1", now=105) == (b"one", "application/json")
    assert c.get("k1", now=120) is None        # expired
    c.put("a", b"A", now=200); c.put("b", b"B", now=201); c.put("d", b"D", now=202)
    assert len(c) == 2 and c.get("a", now=203) is None  # 'a' evicted (oldest)


# --- proxy integration ----------------------------------------------------- #

class _Resp:
    def __init__(self, status, content=b'{"ok":1}', headers=None):
        self.status_code = status; self.content = content
        self.headers = headers or {"content-type": "application/json"}
    async def aread(self): return self.content
    async def aclose(self): pass


class _FakeClient:
    def __init__(self, responses): self._r = list(responses); self.calls = 0
    async def post(self, url, content=None, headers=None):
        self.calls += 1
        return self._r.pop(0)


class _Req:
    def __init__(self, raw):
        self._raw = raw; self.headers = {"x-api-key": "sk"}
    async def body(self): return self._raw


@pytest.fixture()
def proxy(monkeypatch):
    import modelpilot.client_proxy as cp
    monkeypatch.setattr(cp, "CACHE_ON", True)
    monkeypatch.setattr(cp, "CACHE", cache.ResponseCache(ttl=60, maxsize=10))
    monkeypatch.setattr(cp, "MAX_RETRIES", 0)
    monkeypatch.setattr(cp, "_decide", lambda body: ("claude-haiku-4-5", "switch"))
    monkeypatch.setattr(cp, "_fwd_headers", lambda r: {"x-api-key": "sk"})
    return cp


def test_proxy_caches_then_serves_hit(proxy, monkeypatch):
    fake = _FakeClient([_Resp(200, b'{"answer":42}')])  # only ONE upstream response available
    monkeypatch.setattr(proxy, "_client", lambda: fake)
    raw = json.dumps({"model": "claude-opus-4-8", "max_tokens": 8,
                      "messages": [{"role": "user", "content": "same"}]}).encode()
    r1 = asyncio.run(proxy.messages(_Req(raw)))
    assert r1.status_code == 200 and r1.headers["x-modelpilot-cache"] == "MISS"
    # identical request -> served from cache, NO second upstream call
    r2 = asyncio.run(proxy.messages(_Req(raw)))
    assert r2.headers["x-modelpilot-cache"] == "HIT" and r2.body == b'{"answer":42}'
    assert fake.calls == 1


def test_proxy_does_not_cache_streaming(proxy, monkeypatch):
    fake = _FakeClient([_Resp(200), _Resp(200)])

    class _SC(_FakeClient):
        def build_request(self, *a, **k): return ("req",)
        async def send(self, *a, **k): self.calls += 1; return _Resp(200)
    sc = _SC([])
    monkeypatch.setattr(proxy, "_client", lambda: sc)
    raw = json.dumps({"model": "claude-opus-4-8", "stream": True, "max_tokens": 8,
                      "messages": [{"role": "user", "content": "x"}]}).encode()
    asyncio.run(proxy.messages(_Req(raw)))
    asyncio.run(proxy.messages(_Req(raw)))
    assert sc.calls == 2  # streaming never cached -> both hit upstream
