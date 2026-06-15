"""Maven/ModelPilot hosted routing brain (split architecture, v1).

VENDOR-SIDE, INTERNAL: runs on our infrastructure. NOT shipped to customers and
NOT migrated to the customer repo. This is where the defensible IP lives so the
local client can be published safely:

  - the calibrated confidence gate, per-category floors, and switch economics
    (the routing *policy*, which keeps improving without client updates);
  - server-authoritative license + 7-day-trial ENFORCEMENT keyed by deployment
    id (unforgeable — editing the client can't grant entitlement);
  - per-customer learned policy can be applied here later, keyed by deployment.

The thin client sends ONLY a non-sensitive decision request — a category label,
a confidence, the requested model, and numeric features (token estimates, flags).
It NEVER sends prompt text, outputs, or API keys; `/route` refuses any payload
that contains them (defense in depth). The brain returns the decision; the client
applies it locally and forwards to Anthropic with the customer's own key.

Run:  pip install fastapi uvicorn && python -m brain.server   (env BRAIN_DB, PORT)
"""

import os
import sqlite3
import time

from fastapi import FastAPI, HTTPException, Request

from modelpilot.license import LicenseError, verify_token
from modelpilot.pricing import (CAPABILITY_LADDER, batch_savings, cache_request_overpay,
                                cache_savings, ladder_tier, net_switch_benefit)
from modelpilot.taxonomy import floor_tier

GATE_DEFAULT = float(os.environ.get("BRAIN_GATE", "0.7"))
TRIAL_DAYS = 7
_SONNET_TIER = CAPABILITY_LADDER.index("claude-sonnet-4-6")
_DB = os.environ.get("BRAIN_DB", "brain.db")
# If a console is configured, it is the authority for entitlement + routing mode
# (accounts, trial/paid state, guidance vs autopilot). The brain's own license/
# trial path below is the fallback when no console is wired.
_CONSOLE_URL = os.environ.get("CONSOLE_URL", "").rstrip("/")

# Sensitive keys that must never appear in a decision request.
_FORBIDDEN = {"messages", "prompt", "prompts", "content", "text", "output",
              "outputs", "completion", "api_key", "apikey", "x-api-key", "authorization"}

_SCHEMA = """
CREATE TABLE IF NOT EXISTS deployments (
    deployment_id TEXT PRIMARY KEY,
    first_seen REAL NOT NULL
);
"""


def _conn():
    c = sqlite3.connect(_DB)
    c.row_factory = sqlite3.Row
    c.executescript(_SCHEMA)
    return c


def _forbidden_key(obj, path=""):
    if isinstance(obj, dict):
        for k, v in obj.items():
            if str(k).lower() in _FORBIDDEN:
                return f"{path}.{k}".lstrip(".")
            hit = _forbidden_key(v, f"{path}.{k}")
            if hit:
                return hit
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hit = _forbidden_key(v, f"{path}[{i}]")
            if hit:
                return hit
    return None


def _console_entitlement(deployment_id: str) -> dict | None:
    """Ask the console for entitlement + routing mode. Returns None on any failure
    (caller falls back to the brain's own license/trial path)."""
    if not _CONSOLE_URL or not deployment_id:
        return None
    try:
        import httpx
        r = httpx.get(f"{_CONSOLE_URL}/api/entitlement",
                      params={"deployment_id": deployment_id}, timeout=3.0)
        r.raise_for_status()
        d = r.json()
    except Exception:  # noqa: BLE001
        return None
    return {"entitled": bool(d.get("entitled")), "via": "console",
            "mode": d.get("mode"), "apply_mode": bool(d.get("apply")),
            "apply_pct": int(d.get("apply_pct", 100)),
            "reason": d.get("reason"), "plan": d.get("plan")}


_POLICY_CACHE: dict = {}
_POLICY_TTL = 30  # seconds — approved-policy lookups are cached to stay off the hot path


def _console_policy(deployment_id: str) -> dict:
    """Approved per-customer policy (floors + rules) from the console. Cached;
    returns empty policy on any failure. Floors are applied here (Track A); rules
    are surfaced to the gateway via the console (Track C)."""
    if not _CONSOLE_URL or not deployment_id:
        return {"floors": {}, "rules": []}
    hit = _POLICY_CACHE.get(deployment_id)
    if hit and (time.time() - hit[0]) < _POLICY_TTL:
        return hit[1]
    try:
        import httpx
        r = httpx.get(f"{_CONSOLE_URL}/api/policy",
                      params={"deployment_id": deployment_id}, timeout=3.0)
        r.raise_for_status()
        pol = r.json()
    except Exception:  # noqa: BLE001
        return hit[1] if hit else {"floors": {}, "rules": []}
    _POLICY_CACHE[deployment_id] = (time.time(), pol)
    return pol


def entitlement(deployment_id: str, license_token: str | None, now: float | None = None) -> dict:
    """Server-authoritative: console (accounts) if configured, else a valid
    license, else a server-tracked 7-day trial keyed by deployment id."""
    now = now if now is not None else time.time()
    console = _console_entitlement(deployment_id)
    if console is not None:
        return console
    if license_token:
        try:
            claims = verify_token(license_token.strip())
            return {"entitled": True, "via": "license",
                    "licensee": claims.get("licensee"), "exp": claims.get("exp")}
        except LicenseError as e:
            # fall through to trial; report why the license didn't take
            lic_err = str(e)
    else:
        lic_err = None

    conn = _conn()
    try:
        row = conn.execute("SELECT first_seen FROM deployments WHERE deployment_id=?",
                           (deployment_id,)).fetchone()
        if row is None:
            conn.execute("INSERT INTO deployments (deployment_id, first_seen) VALUES (?,?)",
                         (deployment_id, now))
            conn.commit()
            first_seen = now
        else:
            first_seen = row["first_seen"]
    finally:
        conn.close()
    remaining = TRIAL_DAYS * 86_400 - (now - first_seen)
    import math
    return {"entitled": remaining > 0, "via": "trial",
            "trial_days_left": max(0, math.ceil(remaining / 86_400)) if remaining > 0 else 0,
            "license_error": lic_err}


def _decision(req: dict, floors: dict | None = None) -> dict:
    """The routing policy (IP): floors, structured-output guard, economics, gate.

    `floors` is this deployment's admin-approved per-category floor overrides
    (Track A); when present they lower the floor for proven-safe categories."""
    category = req.get("category", "unknown")
    confidence = float(req.get("confidence", 0.0))
    original = req.get("original_model", "")
    f = req.get("features", {}) or {}
    target = floor_tier(category, floors)
    if f.get("has_structured_output") or f.get("has_tools"):
        target = max(target, _SONNET_TIER)
    if f.get("approx_context_tokens", 0) > 50_000:
        target += 1
    target = min(target, len(CAPABILITY_LADDER) - 1)

    orig_tier = ladder_tier(original)
    stay = {"action": "stay", "recommended_model": original, "apply": False,
            "gate": GATE_DEFAULT, "rationale": "no cheaper tier / passthrough"}
    if orig_tier is None or target >= orig_tier:
        return stay
    candidate = CAPABILITY_LADDER[target]

    cached = f.get("approx_context_tokens", 0) if f.get("has_cache_control") else 0
    per_in = max(f.get("approx_context_tokens", 0), 500)
    per_out = max(int(f.get("requested_max_tokens", 0)) // 4, 300)
    turns = float(req.get("expected_remaining_turns", 5.0))
    benefit = net_switch_benefit(original, candidate, cached, int(per_in * turns), int(per_out * turns))
    if benefit is not None and benefit <= 0:
        return {**stay, "rationale": f"switch to {candidate} doesn't pay (net ${benefit:.4f})"}

    return {"action": "switch", "recommended_model": candidate,
            "apply": confidence >= GATE_DEFAULT, "gate": GATE_DEFAULT,
            "est_net_benefit": benefit,
            "rationale": f"route {category} -> {candidate} (conf {confidence:.2f} vs gate {GATE_DEFAULT})"}


def _opportunities(req: dict) -> list[dict]:
    """Savings levers *beyond* model choice — orthogonal to the switch decision.
    Each entry is advisory: a type, an estimated dollar saving, and a human detail.
    Computed server-side (pricing economics stay here); the client only surfaces
    them. Never includes prompt content — only the numeric features we were given."""
    f = req.get("features", {}) or {}
    model = req.get("original_model", "")
    ctx = int(f.get("approx_context_tokens", 0) or 0)
    turns = float(req.get("expected_remaining_turns", 1.0) or 1.0)
    out: list[dict] = []
    # 1) Prompt caching: a large reusable prefix that isn't cached yet, reused across turns.
    #    est_savings is the PER-REQUEST overpay (so it sums honestly across traffic);
    #    the detail quotes the conversation-level figure as the motivating number.
    if not f.get("has_cache_control") and turns >= 2:
        per_req = cache_request_overpay(model, ctx)
        if per_req > 0:
            convo = cache_savings(model, ctx, turns)
            out.append({"type": "prompt_cache", "est_savings": round(per_req, 6),
                        "detail": (f"Cache your ~{ctx:,}-token reusable prefix — cached reads "
                                   f"bill at ~10% of input price (~${convo:.4f} over "
                                   f"{turns:.0f} expected turns).")})
    # 2) Batch API: traffic the customer has flagged latency-tolerant -> 50% off.
    if f.get("latency_tolerant"):
        est_out = max(int(f.get("requested_max_tokens", 0)) // 4, 300)
        saved = batch_savings(model, max(ctx, 500), est_out)
        if saved > 0:
            out.append({"type": "batch_api", "est_savings": round(saved, 6),
                        "detail": "Route this latency-tolerant request through the Batch API for 50% off."})
    return out


def _passes_ramp(apply_pct: int) -> bool:
    """Gradual-rollout canary gate. In autopilot the customer can ramp what share
    of eligible switches is actually applied (build trust, then expand to 100%).
    A switch decision still stands as a *recommendation* when it doesn't pass —
    we just don't auto-apply it. Boundaries are deterministic (0 = never auto-apply,
    100 = always); in between we sample uniformly per request."""
    if apply_pct >= 100:
        return True
    if apply_pct <= 0:
        return False
    import random
    return random.random() < (apply_pct / 100.0)


app = FastAPI(title="ModelPilot routing brain")


@app.get("/health")
async def health():
    return {"ok": True}


@app.post("/route")
async def route(request: Request):
    body = await request.json()
    if not isinstance(body, dict):
        raise HTTPException(400, "payload must be a JSON object")
    bad = _forbidden_key(body)
    if bad is not None:
        raise HTTPException(422, f"rejected: decision requests must not contain '{bad}' "
                                 "(prompts/outputs/keys stay on the client)")
    ent = entitlement(str(body.get("deployment_id") or ""), body.get("license"))
    if not ent["entitled"]:
        # No entitlement -> no routing decision (the client passes traffic through
        # unoptimized). This is the monetization gate, enforced server-side.
        return {"entitled": False, "apply": False, "recommended_model": body.get("original_model"),
                "action": "stay", "entitlement": ent}
    floors = _console_policy(str(body.get("deployment_id") or "")).get("floors") if _CONSOLE_URL else None
    d = _decision(body, floors)
    # Console owns the routing mode: only apply (auto-route) in autopilot. In
    # guidance/shadow the brain still returns the recommendation, but apply=False.
    if ent.get("via") == "console":
        apply_pct = int(ent.get("apply_pct", 100))
        applied = bool(d.get("apply")) and bool(ent.get("apply_mode")) and _passes_ramp(apply_pct)
        # If a switch was held back purely by the rollout ramp, surface it so the
        # client/dashboard can distinguish "recommended but not yet ramped" from "stay".
        if d.get("action") == "switch" and bool(d.get("apply")) and bool(ent.get("apply_mode")) and not applied:
            d["ramp_held"] = True
        d["apply"] = applied
        d["mode"] = ent.get("mode")
        d["apply_pct"] = apply_pct
    opps = _opportunities(body)
    if opps:
        d["opportunities"] = opps
    return {"entitled": True, **d, "entitlement": ent}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("brain.server:app", host="127.0.0.1",
                port=int(os.environ.get("PORT", "8600")), log_level="warning")
