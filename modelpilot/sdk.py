"""Thin SDK helpers — one line to point a Claude client at your local ModelPilot
proxy. Pure convenience; carries no routing IP (safe to ship in the client).

    from modelpilot import anthropic_client
    client = anthropic_client()          # base_url -> the local proxy on :8400
    msg = client.messages.create(model="claude-opus-4-8", max_tokens=512,
                                 messages=[{"role": "user", "content": "hi"}])

Your Anthropic API key is read from ANTHROPIC_API_KEY (or passed in) and used by
the proxy to call Anthropic directly — it stays on your machine. The proxy URL
defaults to http://127.0.0.1:8400 and can be overridden with MODELPILOT_PROXY_URL.
"""

import os

DEFAULT_PROXY = "http://127.0.0.1:8400"


def proxy_url(url: str | None = None) -> str:
    """Resolve the local proxy base URL (arg > MODELPILOT_PROXY_URL > default)."""
    return (url or os.environ.get("MODELPILOT_PROXY_URL") or DEFAULT_PROXY).rstrip("/")


def anthropic_client(api_key: str | None = None, proxy: str | None = None, **kwargs):
    """A configured `anthropic.Anthropic` that sends requests through the local
    ModelPilot proxy. Extra kwargs pass through to the SDK constructor."""
    import anthropic
    return anthropic.Anthropic(
        api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
        base_url=proxy_url(proxy), **kwargs)


def async_anthropic_client(api_key: str | None = None, proxy: str | None = None, **kwargs):
    """Async variant — a configured `anthropic.AsyncAnthropic`."""
    import anthropic
    return anthropic.AsyncAnthropic(
        api_key=api_key or os.environ.get("ANTHROPIC_API_KEY"),
        base_url=proxy_url(proxy), **kwargs)
