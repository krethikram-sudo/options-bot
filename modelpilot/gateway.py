"""Drop-in gateway in front of the Claude API.

Point your SDK at it (base_url) and traffic flows through unchanged except:

  shadow    — passthrough; every request is scored and ledgered, nothing altered
  advise    — passthrough + x-modelpilot-* recommendation headers
  autopilot — model field rewritten when confidence >= threshold

Run:  uvicorn modelpilot.gateway:app --port 8400
Env:  MODELPILOT_MODE=shadow|advise|autopilot   (default shadow)
      MODELPILOT_UPSTREAM=https://api.anthropic.com
      MODELPILOT_DB=modelpilot.db
      MODELPILOT_CONFIDENCE=0.8                 (autopilot gate)
"""

import json
import os
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from . import router as mp_router
from .ledger import Ledger
from .pricing import Usage
from .router import Recommendation

MODE = os.environ.get("MODELPILOT_MODE", "shadow")
UPSTREAM = os.environ.get("MODELPILOT_UPSTREAM", "https://api.anthropic.com").rstrip("/")
CONFIDENCE_GATE = float(os.environ.get("MODELPILOT_CONFIDENCE", "0.8"))

_FORWARD_HEADERS = {
    "x-api-key", "authorization", "anthropic-version", "anthropic-beta",
    "content-type", "accept", "user-agent",
}
_RETURN_HEADERS = {"content-type", "request-id", "anthropic-ratelimit-requests-remaining", "retry-after"}

from contextlib import asynccontextmanager


@asynccontextmanager
async def _lifespan(app):
    app.state.http = httpx.AsyncClient(timeout=httpx.Timeout(600.0, connect=10.0))
    app.state.ledger = Ledger(os.environ.get("MODELPILOT_DB", "modelpilot.db"))
    yield
    await app.state.http.aclose()
    app.state.ledger.close()


app = FastAPI(title="ModelPilot gateway", lifespan=_lifespan)


@dataclass
class Decision:
    recommendation: Recommendation
    routed_model: str
    applied: bool


def decide(body: dict, mode: str, confidence_gate: float = CONFIDENCE_GATE) -> Decision:
    """Pure routing decision — what runs, given the mode. Shadow and advise
    never alter the request; autopilot switches only above the confidence gate.
    """
    rec = mp_router.recommend(body)
    applied = (
        mode == "autopilot"
        and rec.action == "switch"
        and rec.confidence >= confidence_gate
    )
    routed = rec.recommended_model if applied else rec.original_model
    return Decision(recommendation=rec, routed_model=routed, applied=applied)


def _advice_headers(decision: Decision) -> dict:
    rec = decision.recommendation
    headers = {
        "x-modelpilot-mode": MODE,
        "x-modelpilot-recommended-model": rec.recommended_model,
        "x-modelpilot-action": rec.action,
        "x-modelpilot-confidence": f"{rec.confidence:.2f}",
        "x-modelpilot-category": rec.category,
    }
    if rec.est_net_benefit is not None:
        headers["x-modelpilot-est-net-benefit-usd"] = f"{rec.est_net_benefit:.6f}"
    if decision.applied:
        headers["x-modelpilot-routed-model"] = decision.routed_model
    return headers


class _SSEUsage:
    """Extracts the usage block from a pass-through SSE stream.

    input/cache tokens arrive on message_start; output_tokens on message_delta.
    """

    def __init__(self):
        self._buf = b""
        self.usage = Usage()

    def feed(self, chunk: bytes):
        self._buf += chunk
        while b"\n" in self._buf:
            line, self._buf = self._buf.split(b"\n", 1)
            if not line.startswith(b"data: "):
                continue
            try:
                event = json.loads(line[6:])
            except json.JSONDecodeError:
                continue
            usage = None
            if event.get("type") == "message_start":
                usage = (event.get("message") or {}).get("usage")
            elif event.get("type") == "message_delta":
                usage = event.get("usage")
            if not usage:
                continue
            for src, attr in (
                ("input_tokens", "input_tokens"),
                ("output_tokens", "output_tokens"),
                ("cache_read_input_tokens", "cache_read_input_tokens"),
                ("cache_creation_input_tokens", "cache_creation_input_tokens"),
            ):
                if usage.get(src) is not None:
                    setattr(self.usage, attr, usage[src])


def _record(decision: Decision, status_code: int, usage: Usage):
    app.state.ledger.record(
        mode=MODE,
        recommendation=decision.recommendation,
        routed_model=decision.routed_model,
        applied=decision.applied,
        status_code=status_code,
        usage=usage,
    )


@app.post("/v1/messages")
async def messages(request: Request):
    raw = await request.body()
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return await _passthrough(request, raw)

    decision = decide(body, MODE)
    if decision.applied:
        body["model"] = decision.routed_model
        raw = json.dumps(body).encode()

    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() in _FORWARD_HEADERS}
    fwd_headers["content-length"] = str(len(raw))
    url = f"{UPSTREAM}/v1/messages"
    extra = _advice_headers(decision) if MODE in ("advise", "autopilot") else {"x-modelpilot-mode": MODE}

    if body.get("stream"):
        upstream = await app.state.http.send(
            app.state.http.build_request("POST", url, content=raw, headers=fwd_headers),
            stream=True,
        )
        sse = _SSEUsage()

        async def relay():
            try:
                async for chunk in upstream.aiter_bytes():
                    sse.feed(chunk)
                    yield chunk
            finally:
                await upstream.aclose()
                _record(decision, upstream.status_code, sse.usage)

        resp_headers = {k: v for k, v in upstream.headers.items() if k.lower() in _RETURN_HEADERS}
        return StreamingResponse(relay(), status_code=upstream.status_code, headers={**resp_headers, **extra})

    upstream = await app.state.http.post(url, content=raw, headers=fwd_headers)
    usage = Usage()
    if upstream.status_code == 200:
        try:
            usage = Usage.from_api(upstream.json().get("usage") or {})
        except (json.JSONDecodeError, AttributeError):
            pass
    _record(decision, upstream.status_code, usage)
    resp_headers = {k: v for k, v in upstream.headers.items() if k.lower() in _RETURN_HEADERS}
    return Response(content=upstream.content, status_code=upstream.status_code, headers={**resp_headers, **extra})


@app.api_route("/{path:path}", methods=["GET", "POST", "DELETE", "PATCH"])
async def fallthrough(request: Request, path: str):
    """Everything that isn't /v1/messages (count_tokens, models, batches, ...)
    passes through untouched so the gateway is a true drop-in base_url.
    """
    return await _passthrough(request, await request.body())


async def _passthrough(request: Request, raw: bytes) -> Response:
    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() in _FORWARD_HEADERS}
    url = f"{UPSTREAM}{request.url.path}"
    if request.url.query:
        url += f"?{request.url.query}"
    upstream = await app.state.http.request(request.method, url, content=raw or None, headers=fwd_headers)
    resp_headers = {k: v for k, v in upstream.headers.items() if k.lower() in _RETURN_HEADERS}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=resp_headers)
