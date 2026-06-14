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
from modelpilot.pricing import CAPABILITY_LADDER, ladder_tier, net_switch_benefit
from modelpilot.taxonomy import floor_tier

GATE_DEFAULT = float(os.environ.get("BRAIN_GATE", "0.7"))
TRIAL_DAYS = 7
_SONNET_TIER = CAPABILITY_LADDER.index("claude-sonnet-4-6")
_DB = os.environ.get("BRAIN_DB", "brain.db")

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


def entitlement(deployment_id: str, license_token: str | None, now: float | None = None) -> dict:
    """Server-authoritative: a valid license, else a server-tracked 7-day trial
    keyed by deployment id (first-seen recorded here, not on the client)."""
    now = now if now is not None else time.time()
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


def _decision(req: dict) -> dict:
    """The routing policy (IP): floors, structured-output guard, economics, gate."""
    category = req.get("category", "unknown")
    confidence = float(req.get("confidence", 0.0))
    original = req.get("original_model", "")
    f = req.get("features", {}) or {}
    # per-deployment learned floors could be looked up here; v1 uses global.
    target = floor_tier(category)
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
    d = _decision(body)
    return {"entitled": True, **d, "entitlement": ent}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("brain.server:app", host="127.0.0.1",
                port=int(os.environ.get("PORT", "8600")), log_level="warning")
