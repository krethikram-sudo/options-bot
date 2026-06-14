"""Thin SDK helpers: proxy URL resolution + configured client construction."""

import sys
import types

from modelpilot import sdk


def test_proxy_url_resolution(monkeypatch):
    monkeypatch.delenv("MODELPILOT_PROXY_URL", raising=False)
    assert sdk.proxy_url() == "http://127.0.0.1:8400"
    assert sdk.proxy_url("http://host:9000/") == "http://host:9000"
    monkeypatch.setenv("MODELPILOT_PROXY_URL", "http://env:8400/")
    assert sdk.proxy_url() == "http://env:8400"          # env used
    assert sdk.proxy_url("http://arg:1") == "http://arg:1"  # arg beats env


def _fake_anthropic(monkeypatch):
    captured = {}

    class _Client:
        def __init__(self, **kw):
            captured.update(kw)

    mod = types.ModuleType("anthropic")
    mod.Anthropic = _Client
    mod.AsyncAnthropic = _Client
    monkeypatch.setitem(sys.modules, "anthropic", mod)
    return captured


def test_anthropic_client_points_at_proxy(monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
    monkeypatch.delenv("MODELPILOT_PROXY_URL", raising=False)
    captured = _fake_anthropic(monkeypatch)
    sdk.anthropic_client()
    assert captured["base_url"] == "http://127.0.0.1:8400"
    assert captured["api_key"] == "sk-test"


def test_anthropic_client_overrides_and_passthrough(monkeypatch):
    captured = _fake_anthropic(monkeypatch)
    sdk.anthropic_client(api_key="k2", proxy="http://p:1", timeout=30)
    assert captured["base_url"] == "http://p:1" and captured["api_key"] == "k2"
    assert captured["timeout"] == 30  # extra kwargs pass through


def test_async_client(monkeypatch):
    captured = _fake_anthropic(monkeypatch)
    sdk.async_anthropic_client(api_key="k", proxy="http://p:2")
    assert captured["base_url"] == "http://p:2"
