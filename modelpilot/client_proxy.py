"""Thin-client proxy — the publishable half of the split architecture.

A minimal drop-in gateway for the Claude Messages API that asks a hosted
ModelPilot *brain* for every routing decision and rewrites the request model
when the brain says it's both entitled and worth it. It carries NONE of the
routing IP: no price table, no per-category floors, no switch economics, no
ledger/dashboard. Those live in the brain (brain/server.py); this file only
classifies locally (commodity) and forwards.

What leaves the box: a task *category* + numeric features (see brain_client) —
never prompt text, model outputs, or API keys. If the brain is unreachable or
errors, the proxy **fails open**: the request is forwarded unchanged to the
upstream API, so customer traffic is never blocked by our infrastructure.

Run:
    export MODELPILOT_BRAIN_URL=https://your-brain.example.com
    export MODELPILOT_LICENSE=...            # optional; trial is server-tracked
    python -m modelpilot.client_proxy        # listens on :8400, proxies to api.anthropic.com

This module depends only on the publishable commodity modules (router_classify,
brain_client) plus fastapi/httpx/uvicorn — nothing IP-bearing.
"""

import json
import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

from . import brain_client, cache as _cache, retry

UPSTREAM = os.environ.get("MODELPILOT_UPSTREAM", "https://api.anthropic.com").rstrip("/")
BRAIN_URL = os.environ.get("MODELPILOT_BRAIN_URL", "").rstrip("/")
CONSOLE_URL = os.environ.get("MODELPILOT_CONSOLE_URL", "").rstrip("/")
LICENSE = os.environ.get("MODELPILOT_LICENSE") or None
DB_PATH = os.environ.get("MODELPILOT_DB", "modelpilot.db")
# autopilot rewrites the model; advise/shadow only annotate (do-no-harm default).
MODE = os.environ.get("MODELPILOT_MODE", "autopilot")
# Reliability: retry transient upstream errors, and on a routed (cheaper) model's
# failure fall back to the model the caller asked for.
MAX_RETRIES = int(os.environ.get("MODELPILOT_MAX_RETRIES", str(retry.DEFAULT_MAX_RETRIES)))
FALLBACK = os.environ.get("MODELPILOT_FALLBACK", "1") not in ("0", "false", "no", "")
# Exact-match response cache (opt-in). Identical requests return instantly at $0.
CACHE_ON = os.environ.get("MODELPILOT_CACHE", "") in ("1", "true", "yes", "on")
CACHE = _cache.ResponseCache(
    ttl=float(os.environ.get("MODELPILOT_CACHE_TTL", str(_cache.DEFAULT_TTL))),
    maxsize=int(os.environ.get("MODELPILOT_CACHE_MAX", str(_cache.DEFAULT_MAX))))
# Semantic cache (opt-in): near-duplicate requests hit too. Needs an embeddings
# endpoint you choose (OpenAI-compatible); cached responses stay local.
SEMANTIC_ON = os.environ.get("MODELPILOT_SEMANTIC_CACHE", "") in ("1", "true", "yes", "on")
EMBED_URL = os.environ.get("MODELPILOT_EMBED_URL", "").rstrip("/")
EMBED_KEY = os.environ.get("MODELPILOT_EMBED_KEY") or os.environ.get("ANTHROPIC_API_KEY")
EMBED_MODEL = os.environ.get("MODELPILOT_EMBED_MODEL", "text-embedding-3-small")
SEM_CACHE = _cache.SemanticCache(
    ttl=float(os.environ.get("MODELPILOT_CACHE_TTL", str(_cache.DEFAULT_TTL))),
    maxsize=int(os.environ.get("MODELPILOT_SEMANTIC_MAX", "200")),
    threshold=float(os.environ.get("MODELPILOT_SEMANTIC_THRESHOLD", str(_cache.DEFAULT_SIM))))


def _embed_text(body: dict) -> str:
    """Text we embed for semantic matching — the last user message."""
    for m in reversed(body.get("messages") or []):
        if m.get("role") == "user":
            c = m.get("content")
            if isinstance(c, str):
                return c
            if isinstance(c, list):
                return "\n".join(b.get("text", "") for b in c
                                 if isinstance(b, dict) and b.get("type") == "text")
    return ""


async def _embed(text: str):
    """Vector for `text` via the configured embeddings endpoint, or None."""
    if not (EMBED_URL and text):
        return None
    try:
        headers = {"content-type": "application/json"}
        if EMBED_KEY:
            headers["authorization"] = f"Bearer {EMBED_KEY}"
        r = await _client().post(EMBED_URL, headers=headers,
                                 content=json.dumps({"model": EMBED_MODEL, "input": text[:8000]}).encode())
        r.raise_for_status()
        return r.json()["data"][0]["embedding"]
    except Exception:  # noqa: BLE001 — semantic cache is best-effort
        return None

# Headers we never echo back from upstream (hop-by-hop / length recomputed).
_DROP_RESP_HEADERS = {"content-length", "content-encoding", "transfer-encoding", "connection"}


def _client() -> httpx.AsyncClient:
    return app.state.http


app = FastAPI(title="ModelPilot thin client")


@app.on_event("startup")
async def _startup():
    import asyncio

    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0))
    app.state.deployment_id = brain_client.deployment_id(DB_PATH)
    # Admin-approved per-customer classification rules (Track C), applied locally
    # so the cheap-model routing reflects this customer's domain. Floors stay in
    # the brain. Refreshed in the background so newly-approved rules take effect
    # without a restart.
    app.state.rules = brain_client.fetch_policy(CONSOLE_URL, app.state.deployment_id)["rules"]
    app.state.policy_task = None
    if CONSOLE_URL and app.state.deployment_id:
        async def _refresh():
            interval = int(os.environ.get("MODELPILOT_POLICY_REFRESH", "300"))
            while True:
                await asyncio.sleep(interval)
                try:
                    pol = await asyncio.to_thread(
                        brain_client.fetch_policy, CONSOLE_URL, app.state.deployment_id)
                    app.state.rules = pol["rules"]
                except Exception:  # noqa: BLE001 — refresh must never break the proxy
                    pass
        app.state.policy_task = asyncio.create_task(_refresh())


@app.on_event("shutdown")
async def _shutdown():
    task = getattr(app.state, "policy_task", None)
    if task is not None:
        task.cancel()
    await app.state.http.aclose()


@app.get("/modelpilot/health")
async def health():
    return {"ok": True, "brain": bool(BRAIN_URL), "mode": MODE,
            "deployment_id": app.state.deployment_id}


def _fwd_headers(request: Request) -> dict:
    # Pass the caller's auth straight through; the key never touches the brain.
    return {k: v for k, v in request.headers.items()
            if k.lower() not in ("host", "content-length")}


def _resp_headers(upstream: httpx.Response) -> dict:
    return {k: v for k, v in upstream.headers.items()
            if k.lower() not in _DROP_RESP_HEADERS}


def _decide(body: dict):
    """Routing decision via the brain. Returns the model to send + an x-header
    annotation. Fails open to the original model on any brain trouble."""
    original = body.get("model", "")
    annotation = "passthrough"
    if not BRAIN_URL:
        return original, "no-brain"
    result = brain_client.remote_decide(
        body, BRAIN_URL, app.state.deployment_id, LICENSE,
        rules=getattr(app.state, "rules", None))
    if result is None:
        return original, "brain-unreachable-fail-open"
    rec, ent = result
    if not ent.get("entitled", True):
        return original, "not-entitled"
    annotation = f"{rec.action}:{rec.category}:{rec.recommended_model}"
    apply = MODE == "autopilot" and ent.get("apply") and rec.action == "switch"
    return (rec.recommended_model if apply else original), annotation


def _rebody(raw: bytes, body: dict, model: str) -> bytes:
    import json
    if not body or model == body.get("model"):
        return raw
    body = {**body, "model": model}
    return json.dumps(body).encode()


@app.post("/v1/messages")
async def messages(request: Request):
    import asyncio
    import json

    raw = await request.body()
    try:
        body = json.loads(raw)
    except ValueError:
        body = {}

    streaming = bool(body.get("stream"))

    # Exact-match cache: identical, non-streaming requests return instantly at $0.
    cache_key = _cache.request_key(body) if (CACHE_ON and body and not streaming) else None
    if cache_key:
        hit = CACHE.get(cache_key)
        if hit:
            content, ctype = hit
            return Response(content=content, status_code=200,
                            headers={"content-type": ctype, "x-modelpilot-cache": "HIT",
                                     "x-modelpilot-decision": "cache-hit"})

    original = body.get("model", "")

    # Semantic cache: a near-duplicate request (same model) serves a stored response.
    sem_vec = None
    if SEMANTIC_ON and body and not streaming and EMBED_URL:
        sem_vec = await _embed(_embed_text(body))
        if sem_vec:
            shit = SEM_CACHE.get(sem_vec, bucket=original)
            if shit:
                content, ctype = shit
                return Response(content=content, status_code=200,
                                headers={"content-type": ctype, "x-modelpilot-cache": "HIT-SEMANTIC",
                                         "x-modelpilot-decision": "cache-hit-semantic"})

    routed_model, annotation = (original, "bad-body")
    if body:
        routed_model, annotation = _decide(body)

    url = f"{UPSTREAM}/v1/messages"
    base_headers = _fwd_headers(request)

    # Retry transient failures; fall back to the original model if the routed
    # (cheaper) one errors, so routing never costs reliability.
    model = routed_model or original
    notes = [annotation]
    attempt = 0
    while True:
        payload = _rebody(raw, body, model)
        headers = {**base_headers, "content-length": str(len(payload))}
        if streaming:
            upstream = await _client().send(
                _client().build_request("POST", url, content=payload, headers=headers),
                stream=True)
        else:
            upstream = await _client().post(url, content=payload, headers=headers)

        nxt = retry.plan(upstream.status_code, attempt, MAX_RETRIES, routed_model,
                         original, FALLBACK) if body else None
        if nxt is None:
            break
        # retriable failure with attempts left -> close this response and retry
        if streaming:
            await upstream.aclose()
        else:
            await upstream.aread()
        wait = retry.backoff_seconds(attempt, upstream.headers.get("retry-after"))
        notes.append(f"retry{nxt['attempt']}:{upstream.status_code}:{nxt['reason']}")
        model = nxt["model"]
        attempt = nxt["attempt"]
        await asyncio.sleep(wait)

    extra = {"x-modelpilot-decision": ";".join(notes), "x-modelpilot-routed": model or ""}
    if streaming:
        async def relay():
            try:
                async for chunk in upstream.aiter_bytes():
                    yield chunk
            finally:
                await upstream.aclose()
        return StreamingResponse(relay(), status_code=upstream.status_code,
                                 headers={**_resp_headers(upstream), **extra})

    # Store successful non-streaming responses for exact + semantic reuse.
    if upstream.status_code == 200:
        ctype = upstream.headers.get("content-type", "application/json")
        if cache_key:
            CACHE.put(cache_key, upstream.content, ctype)
            extra["x-modelpilot-cache"] = "MISS"
        if sem_vec:
            SEM_CACHE.put(sem_vec, upstream.content, ctype, bucket=original)
    return Response(content=upstream.content, status_code=upstream.status_code,
                    headers={**_resp_headers(upstream), **extra})


@app.api_route("/{path:path}",
               methods=["GET", "POST", "PUT", "DELETE", "PATCH", "OPTIONS"])
async def passthrough(request: Request, path: str):
    raw = await request.body()
    headers = _fwd_headers(request)
    upstream = await _client().request(
        request.method, f"{UPSTREAM}/{path}", content=raw or None, headers=headers)
    return Response(content=upstream.content, status_code=upstream.status_code,
                    headers=_resp_headers(upstream))


def main():
    import uvicorn
    port = int(os.environ.get("MODELPILOT_PORT", "8400"))
    if not BRAIN_URL:
        print("warning: MODELPILOT_BRAIN_URL is not set — proxy will pass all "
              "traffic through unrouted. Set it to enable routing.")
    print(f"ModelPilot thin client — {MODE} mode on http://127.0.0.1:{port} "
          f"(brain: {BRAIN_URL or 'none'})")
    uvicorn.run("modelpilot.client_proxy:app", host="127.0.0.1", port=port,
                log_level="warning")


if __name__ == "__main__":
    main()
