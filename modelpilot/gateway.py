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

import hashlib
import json
import os
import uuid
from dataclasses import dataclass

import httpx
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse

from . import router as mp_router
from .continuation import ContinuationModel
from .ledger import Ledger
from .pricing import Usage, request_cost
from .router import Recommendation

MODE = os.environ.get("MODELPILOT_MODE", "shadow")
UPSTREAM = os.environ.get("MODELPILOT_UPSTREAM", "https://api.anthropic.com").rstrip("/")
CONFIDENCE_GATE = float(os.environ.get("MODELPILOT_CONFIDENCE", "0.8"))
HOLDOUT_PCT = float(os.environ.get("MODELPILOT_HOLDOUT_PCT", "0.10"))
# Opt-in prompt capture for golden-set building. 0 (default) = no prompt text
# is ever stored. Set e.g. 0.25 to sample a quarter of requests into the
# captures table; export with `python -m modelpilot.goldenset.export_corpus`.
CAPTURE_PCT = float(os.environ.get("MODELPILOT_CAPTURE_PCT", "0"))
CAPTURE_MAX_CHARS = 20_000

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
    app.state.continuation = ContinuationModel(app.state.ledger)
    yield
    await app.state.http.aclose()
    app.state.ledger.close()


app = FastAPI(title="ModelPilot gateway", lifespan=_lifespan)


@dataclass
class Decision:
    recommendation: Recommendation
    routed_model: str
    applied: bool
    arm: str = "observe"  # treatment | control | observe


def assign_arm(session_key: str, holdout_pct: float) -> str:
    """Deterministic session-level randomization for the RCT (Layer 3).

    Hashing the session key keeps a whole conversation in one arm, avoiding
    cache contamination between arms (SAVINGS_DASHBOARD.md §1).
    """
    if holdout_pct <= 0:
        return "treatment"
    h = int(hashlib.sha256(session_key.encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
    return "control" if h < holdout_pct else "treatment"


def decide(body: dict, mode: str, confidence_gate: float = CONFIDENCE_GATE,
           holdout_pct: float = 0.0, session_key: str = "",
           expected_remaining_turns: float | None = None) -> Decision:
    """Pure routing decision — what runs, given the mode. Shadow and advise
    never alter the request; autopilot switches only above the confidence gate
    and only in the treatment arm (control requests run the baseline so the
    two arms can be compared).
    """
    if expected_remaining_turns is None:
        rec = mp_router.recommend(body)
    else:
        rec = mp_router.recommend(body, expected_remaining_turns=expected_remaining_turns)
    arm = assign_arm(session_key, holdout_pct) if mode == "autopilot" else "observe"
    applied = (
        mode == "autopilot"
        and arm == "treatment"
        and rec.action == "switch"
        and rec.confidence >= confidence_gate
    )
    routed = rec.recommended_model if applied else rec.original_model
    return Decision(recommendation=rec, routed_model=routed, applied=applied, arm=arm)


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
    if decision.arm != "observe":
        headers["x-modelpilot-arm"] = decision.arm
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


def _record(decision: Decision, status_code: int, usage: Usage,
            request_id: str, retry_of: str | None, session_key: str = ""):
    app.state.ledger.record(
        mode=MODE,
        recommendation=decision.recommendation,
        routed_model=decision.routed_model,
        applied=decision.applied,
        status_code=status_code,
        usage=usage,
        arm=decision.arm,
        retry_of=retry_of,
        request_id=request_id,
        session_key=session_key,
    )


def maybe_capture(ledger, body: dict, decision: Decision, request_id: str,
                  capture_pct: float, rng=None) -> bool:
    """Sampled, opt-in prompt capture feeding the next golden-set round."""
    import random as _random

    if capture_pct <= 0 or (rng or _random).random() >= capture_pct:
        return False
    prompt = mp_router.extract_features(body)["prompt"][:CAPTURE_MAX_CHARS]
    if not prompt.strip():
        return False
    rec = decision.recommendation
    ledger.record_capture(request_id, rec.category, rec.confidence, prompt)
    return True


def _session_key(request: Request, body: dict) -> str:
    """Arm assignment key: explicit session header if the client sends one,
    else a hash of the first message — keeping a conversation in one arm."""
    explicit = request.headers.get("x-session-id")
    if explicit:
        return explicit
    messages = body.get("messages") or [{}]
    return hashlib.sha256(json.dumps(messages[0], sort_keys=True).encode()).hexdigest()


@app.post("/modelpilot/feedback")
async def feedback(request: Request):
    """Quality signal from the customer's app: the escalation valve's input.

    Body: {"request_id": "...", "signal": "negative"|"positive", "note": "..."}
    request_id comes from the x-modelpilot-request-id response header. To link
    a re-run after a failure, resend through the gateway with header
    x-modelpilot-retry-of: <request_id> — its cost is charged against savings.
    """
    body = await request.json()
    if body.get("signal") not in ("negative", "positive") or not body.get("request_id"):
        return Response(content='{"error": "request_id and signal=negative|positive required"}',
                        status_code=400, media_type="application/json")
    app.state.ledger.record_feedback(body["request_id"], body["signal"], body.get("note"))
    return {"ok": True}


# Dashboard/chat routes must register before the catch-all passthrough below.
from .chat import router as _chat_router  # noqa: E402
from .dashboard import router as _dashboard_router  # noqa: E402

app.include_router(_dashboard_router)
app.include_router(_chat_router)


@app.post("/modelpilot/preview")
async def preview(request: Request):
    """Pre-execution routing decision: which model WILL run this request,
    and the estimated saving — without executing anything. Free and instant;
    deterministic, so the answer matches what /v1/messages will then do.
    """
    body = await request.json()
    session_key = body.get("session_id") or _session_key(request, body)
    decision = decide(body, MODE, holdout_pct=HOLDOUT_PCT, session_key=session_key)
    rec = decision.recommendation

    # Pre-flight cost estimate: input from context size, nominal output.
    feats = mp_router.extract_features(body)
    est_usage = Usage(input_tokens=max(feats["approx_context_tokens"], 50), output_tokens=300)
    cost_baseline = request_cost(rec.original_model, est_usage) or 0.0
    cost_will_run = request_cost(decision.routed_model, est_usage) or cost_baseline
    cost_recommended = request_cost(rec.recommended_model, est_usage) or cost_baseline
    return {
        "mode": MODE,
        "action": rec.action,
        "applied": decision.applied,
        "arm": decision.arm,
        "will_run_on": decision.routed_model,
        "recommended_model": rec.recommended_model,
        "baseline_model": rec.original_model,
        "confidence": rec.confidence,
        "category": rec.category,
        "rationale": rec.rationale,
        "est_saved": max(cost_baseline - cost_will_run, 0.0),
        "est_potential": max(cost_baseline - cost_recommended, 0.0),
    }


@app.post("/v1/messages")
async def messages(request: Request):
    raw = await request.body()
    try:
        body = json.loads(raw)
    except json.JSONDecodeError:
        return await _passthrough(request, raw)

    retry_of = request.headers.get("x-modelpilot-retry-of")
    session_key = _session_key(request, body)
    turns = app.state.ledger.turns_so_far(session_key) + 1
    decision = decide(
        body, MODE, holdout_pct=HOLDOUT_PCT, session_key=session_key,
        expected_remaining_turns=app.state.continuation.expected_remaining(turns),
    )
    if retry_of and decision.applied:
        # An escalation retry after a quality failure must never be routed
        # down again — run it exactly as the caller asked.
        decision = Decision(recommendation=decision.recommendation,
                            routed_model=decision.recommendation.original_model,
                            applied=False, arm=decision.arm)
    if decision.applied:
        body["model"] = decision.routed_model
        raw = json.dumps(body).encode()

    request_id = uuid.uuid4().hex
    maybe_capture(app.state.ledger, body, decision, request_id, CAPTURE_PCT)
    fwd_headers = {k: v for k, v in request.headers.items() if k.lower() in _FORWARD_HEADERS}
    fwd_headers["content-length"] = str(len(raw))
    url = f"{UPSTREAM}/v1/messages"
    extra = _advice_headers(decision) if MODE in ("advise", "autopilot") else {"x-modelpilot-mode": MODE}
    extra["x-modelpilot-request-id"] = request_id

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
                _record(decision, upstream.status_code, sse.usage, request_id, retry_of, session_key)

        resp_headers = {k: v for k, v in upstream.headers.items() if k.lower() in _RETURN_HEADERS}
        return StreamingResponse(relay(), status_code=upstream.status_code, headers={**resp_headers, **extra})

    upstream = await app.state.http.post(url, content=raw, headers=fwd_headers)
    usage = Usage()
    if upstream.status_code == 200:
        try:
            usage = Usage.from_api(upstream.json().get("usage") or {})
        except (json.JSONDecodeError, AttributeError):
            pass
    _record(decision, upstream.status_code, usage, request_id, retry_of, session_key)
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
