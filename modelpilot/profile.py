"""Per-customer deployment profile (Track B) — route to *their* utility.

A cost router that ignores a customer's constraints is unusable in an
enterprise. The profile makes routing fit the customer:

  - allowed_models / blocked_models — compliance: never route to a model the
    customer hasn't approved (data-residency, vendor, or policy reasons);
  - min_model — a quality floor the customer sets: never route below this tier,
    regardless of what the heuristics or learned floors say. (A hard latency or
    quality SLA is expressed by pinning to fast/strong models here.)
  - price_overrides — negotiated/enterprise/committed-use rates, so the economics
    and every savings number reflect the customer's ACTUAL bill, not list price;
  - risk_tolerance — conservative / balanced / aggressive, mapped to the
    autopilot confidence gate (or an explicit `gate`).

Single-tenant by design: one local gateway = one customer = one profile. Loaded
from MODELPILOT_PROFILE (a path) or a `profile` object inside MODELPILOT_POLICY.

Example profile.json:

    {
      "allowed_models": ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"],
      "blocked_models": ["claude-fable-5"],
      "min_model": "claude-haiku-4-5",
      "risk_tolerance": "balanced",
      "price_overrides": {"claude-sonnet-4-6": {"input": 2.4, "output": 12.0}}
    }
"""

import json
from dataclasses import dataclass, field

from .pricing import CAPABILITY_LADDER, ModelPrice, ladder_tier

# risk_tolerance -> autopilot confidence gate. Higher gate = more cautious.
RISK_GATES = {"conservative": 0.9, "balanced": 0.8, "aggressive": 0.65}


class ProfileError(ValueError):
    pass


@dataclass
class Profile:
    allowed_models: set[str] | None = None      # whitelist (None = all allowed)
    blocked_models: set[str] = field(default_factory=set)
    min_model: str | None = None
    risk_tolerance: str = "balanced"
    gate: float | None = None                    # explicit override of risk_tolerance
    price_overrides: dict[str, ModelPrice] = field(default_factory=dict)

    def allows(self, model: str) -> bool:
        if any(model.startswith(b) for b in self.blocked_models):
            return False
        if self.allowed_models is None:
            return True
        return any(model.startswith(a) for a in self.allowed_models)

    def min_tier(self) -> int:
        t = ladder_tier(self.min_model) if self.min_model else None
        return t or 0

    def confidence_gate(self, default: float = 0.8) -> float:
        if self.gate is not None:
            return self.gate
        return RISK_GATES.get(self.risk_tolerance, default)

    def is_active(self) -> bool:
        return bool(self.allowed_models or self.blocked_models or self.min_model
                    or self.price_overrides or self.gate is not None
                    or self.risk_tolerance != "balanced")


def _parse_price(model: str, raw) -> ModelPrice:
    if isinstance(raw, dict):
        return ModelPrice(float(raw["input"]), float(raw["output"]))
    if isinstance(raw, (list, tuple)) and len(raw) == 2:
        return ModelPrice(float(raw[0]), float(raw[1]))
    raise ProfileError(f"price_overrides[{model!r}] must be {{'input':x,'output':y}} or [in,out]")


def compile_profile(raw: dict) -> Profile:
    allowed = raw.get("allowed_models")
    blocked = raw.get("blocked_models") or []
    min_model = raw.get("min_model")
    risk = raw.get("risk_tolerance", "balanced")
    if risk not in RISK_GATES:
        raise ProfileError(f"risk_tolerance must be one of {sorted(RISK_GATES)} (got {risk!r})")
    if min_model and ladder_tier(min_model) is None:
        raise ProfileError(f"min_model {min_model!r} is not a known model")
    overrides = {m: _parse_price(m, v) for m, v in (raw.get("price_overrides") or {}).items()}
    return Profile(
        allowed_models=set(allowed) if allowed else None,
        blocked_models=set(blocked),
        min_model=min_model,
        risk_tolerance=risk,
        gate=float(raw["gate"]) if raw.get("gate") is not None else None,
        price_overrides=overrides,
    )


def load_profile(source) -> Profile:
    """Load from a path, a dict (policy.json with a `profile` key, or a raw
    profile dict), or None. Missing/unreadable -> an empty (inactive) profile."""
    if not source:
        return Profile()
    data = source
    if isinstance(source, str):
        try:
            with open(source) as f:
                data = json.load(f)
        except (OSError, ValueError):
            return Profile()
    if isinstance(data, dict) and "profile" in data:
        data = data["profile"]
    if not isinstance(data, dict):
        return Profile()
    return compile_profile(data)


def choose_allowed(target_tier: int, original_tier: int, profile: Profile | None):
    """Cheapest profile-permitted model strictly below the requested model, at or
    above the target floor. Returns (model, tier) or (None, None) to stay.

    Walks up from the cheapest acceptable tier so a blocked cheap model falls
    back to the next-cheapest permitted one rather than forfeiting the switch.
    """
    lo = target_tier if profile is None else max(target_tier, profile.min_tier())
    for t in range(lo, original_tier):
        model = CAPABILITY_LADDER[t]
        if profile is None or profile.allows(model):
            return model, t
    return None, None


def main():
    import argparse
    import os

    parser = argparse.ArgumentParser(description="Validate/print the active deployment profile")
    parser.add_argument("--profile", default=os.environ.get("MODELPILOT_PROFILE", ""),
                        help="profile path (default: MODELPILOT_PROFILE, then MODELPILOT_POLICY)")
    args = parser.parse_args()

    src = args.profile or os.environ.get("MODELPILOT_POLICY", "")
    if not src:
        raise SystemExit("No profile configured (set MODELPILOT_PROFILE or pass --profile).")
    try:
        p = load_profile(src)
    except ProfileError as e:
        raise SystemExit(f"Invalid profile: {e}")
    if not p.is_active():
        print(f"Profile at {src} is empty/inactive — global defaults apply.")
        return
    print("Active deployment profile:")
    print(f"  allowed models : {sorted(p.allowed_models) if p.allowed_models else 'all'}")
    print(f"  blocked models : {sorted(p.blocked_models) or 'none'}")
    print(f"  min model      : {p.min_model or '(cheapest)'}")
    print(f"  risk tolerance : {p.risk_tolerance}  -> autopilot gate {p.confidence_gate():.2f}")
    if p.price_overrides:
        print("  price overrides ($/MTok in/out):")
        for m, pr in sorted(p.price_overrides.items()):
            print(f"    {m}: {pr.input_per_mtok}/{pr.output_per_mtok}")


if __name__ == "__main__":
    main()
