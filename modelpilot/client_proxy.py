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

import os

import httpx
from fastapi import FastAPI, Request
from fastapi.responses import Response, StreamingResponse

from . import brain_client

UPSTREAM = os.environ.get("MODELPILOT_UPSTREAM", "https://api.anthropic.com").rstrip("/")
BRAIN_URL = os.environ.get("MODELPILOT_BRAIN_URL", "").rstrip("/")
CONSOLE_URL = os.environ.get("MODELPILOT_CONSOLE_URL", "").rstrip("/")
LICENSE = os.environ.get("MODELPILOT_LICENSE") or None
DB_PATH = os.environ.get("MODELPILOT_DB", "modelpilot.db")
# autopilot rewrites the model; advise/shadow only annotate (do-no-harm default).
MODE = os.environ.get("MODELPILOT_MODE", "autopilot")

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


@app.post("/v1/messages")
async def messages(request: Request):
    raw = await request.body()
    try:
        import json
        body = json.loads(raw)
    except ValueError:
        body = {}

    routed_model, annotation = (body.get("model", ""), "bad-body")
    if body:
        routed_model, annotation = _decide(body)
        if routed_model and routed_model != body.get("model"):
            body["model"] = routed_model
            import json
            raw = json.dumps(body).encode()

    url = f"{UPSTREAM}/v1/messages"
    headers = _fwd_headers(request)
    headers["content-length"] = str(len(raw))
    extra = {"x-modelpilot-decision": annotation, "x-modelpilot-routed": routed_model or ""}

    if body.get("stream"):
        upstream = await _client().send(
            _client().build_request("POST", url, content=raw, headers=headers),
            stream=True)

        async def relay():
            try:
                async for chunk in upstream.aiter_bytes():
                    yield chunk
            finally:
                await upstream.aclose()

        return StreamingResponse(relay(), status_code=upstream.status_code,
                                 headers={**_resp_headers(upstream), **extra})

    upstream = await _client().post(url, content=raw, headers=headers)
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
