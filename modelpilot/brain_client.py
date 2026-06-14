"""Client side of the split architecture: ask the hosted routing brain for the
decision, sending ONLY non-sensitive features — never prompt text, outputs, or
API keys. Fail-open: if the brain is unreachable or errors, return None so the
gateway falls back to local routing / passthrough and the customer's traffic is
never blocked by our infrastructure.

This is the seam that lets the local client be published safely: the valuable
routing policy + license/trial enforcement live in the brain (brain/server.py),
not here.
"""

import os

# Import from the commodity classifier, NOT router.py: the published thin client
# ships router_classify (lexical only) and never the floor/economics IP in
# router.py / pricing.py / taxonomy.py.
from .router_classify import Recommendation, classify, extract_features

# The only features sent upstream — all numeric/boolean, none reversible to text.
_SEND_FEATURES = (
    "approx_context_tokens", "has_cache_control", "requested_max_tokens",
    "has_tools", "has_structured_output", "n_turns", "prompt_chars", "has_code",
)


def build_request(body: dict, deployment_id: str, license_token: str | None = None,
                  expected_remaining_turns: float = 5.0) -> dict:
    """Build the decision request. Classification happens locally (commodity);
    only the category label + numeric features leave the box — no prompt text."""
    feats = extract_features(body)
    category, _tier, confidence, _rat = classify(feats)
    return {
        "deployment_id": deployment_id,
        "license": (license_token or None),
        "category": category,
        "confidence": confidence,
        "original_model": body.get("model", ""),
        "features": {k: feats.get(k) for k in _SEND_FEATURES},
        "expected_remaining_turns": expected_remaining_turns,
    }


def remote_decide(body: dict, brain_url: str, deployment_id: str,
                  license_token: str | None = None, expected_remaining_turns: float = 5.0,
                  timeout: float = 3.0):
    """Ask the brain. Returns (Recommendation, entitlement_dict) or None (fail-open)."""
    import httpx

    req = build_request(body, deployment_id, license_token, expected_remaining_turns)
    try:
        r = httpx.post(f"{brain_url.rstrip('/')}/route", json=req, timeout=timeout)
        r.raise_for_status()
        d = r.json()
    except Exception:  # noqa: BLE001 — any failure => fail open
        return None
    rec = Recommendation(
        action=d.get("action", "stay"),
        original_model=req["original_model"],
        recommended_model=d.get("recommended_model") or req["original_model"],
        confidence=req["confidence"],
        category=req["category"],
        rationale=d.get("rationale", ""),
        est_net_benefit=d.get("est_net_benefit"),
    )
    entitlement = {"entitled": d.get("entitled", True), "apply": d.get("apply", False),
                   **(d.get("entitlement") or {})}
    return rec, entitlement


def deployment_id(db_path: str = "modelpilot.db") -> str:
    """Stable anonymous id for this deployment (reuses the telemetry sidecar)."""
    import uuid
    side = (db_path or "modelpilot.db") + ".deployment"
    try:
        with open(side) as f:
            return f.read().strip()
    except OSError:
        did = uuid.uuid4().hex
        try:
            with open(side, "w") as f:
                f.write(did)
        except OSError:
            pass
        return did
