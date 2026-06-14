"""Router v0: the server-side economics + floor layer on top of the commodity
classifier (router_classify).

Split rationale (IP protection / publishable thin client):
  - router_classify.py   — lexical classification only (category, confidence,
    features). Stdlib-only, no pricing/taxonomy. Safe to ship in the client.
  - router.py (here)     — binds the per-category capability *floors*
    (taxonomy), the price table + cache-aware switch *economics* (pricing), and
    the universal structured-output/tool guard. This is the valuable policy and
    stays server-side (also runs locally as the fail-open path).

Design rules (see ROUTER_TUNING_PLAN.md):
  - Only ever recommend a model at or below the one the caller requested.
  - When unsure, recommend nothing (action="stay"). Do-no-harm is the default.
  - Capability (can the cheap model do it?) and economics (does switching pay,
    given cache state and expected continuation?) are separate, auditable steps.
  - No turn is an independent decision: classification reconciles the prompt
    with the whole session (follow-ups inherit session difficulty; mechanical
    tasks over existing content keep their cheap tier). Stateless — the full
    conversation arrives with every request.
"""

import json
import os

from . import router_classify as _rc
from .pricing import CAPABILITY_LADDER, ladder_tier, net_switch_benefit
from .taxonomy import CATEGORIES, floor_tier

# Keep the commodity module's ladder-position literals honest against pricing.
assert _rc._SONNET_TIER == CAPABILITY_LADDER.index("claude-sonnet-4-6"), "router_classify._SONNET_TIER drifted"
assert _rc._TOP_TIER == len(CAPABILITY_LADDER) - 1, "router_classify._TOP_TIER drifted"

# Re-export the commodity classifier surface so existing imports keep working
# unchanged (gateway, rules, compare, tests all `from .router import ...`).
Recommendation = _rc.Recommendation
extract_features = _rc.extract_features
_message_text = _rc._message_text
_last_user_text = _rc._last_user_text
_session_signals = _rc._session_signals
CHARS_PER_TOKEN = _rc.CHARS_PER_TOKEN
_SONNET_TIER = _rc._SONNET_TIER  # quality floor for brittle calls (recommend guard)


def classify(features: dict, floors: dict | None = None) -> tuple[str, int, float, str]:
    """Session-context-aware classification with this deployment's floors applied.

    Thin wrapper that binds the taxonomy floor map (`floor_tier`) into the
    commodity classifier, so the floor IP lives here, not in router_classify.
    `floors` is the per-customer learned floor policy (taxonomy.floor_tier).
    """
    return _rc.classify(features, floor_tier=floor_tier, floors=floors)


def reconcile_followup(features: dict, category: str, tier: int,
                       confidence: float, rationale: str) -> tuple[str, int, float, str]:
    """Reconcile a standalone classification with the session (tier-aware).

    Binds the global floor map so the per-customer rule layer (rules.py) gets
    the same follow-up/session-difficulty protection as the global classifier.
    """
    return _rc.reconcile_followup(features, category, tier, confidence, rationale,
                                  floor_tier=floor_tier)


def recommend(
    body: dict,
    expected_remaining_turns: float = 5.0,
    classifier=classify,
    profile=None,
) -> Recommendation:
    """Full routing decision for one request body.

    `profile` is the per-customer deployment profile (Track B): it enforces a
    `min_model` quality floor and allowed/blocked-model compliance on the
    candidate, and its price overrides (applied to the global price table at
    startup) flow through the economics automatically."""
    original_model = body.get("model", "")
    original_tier = ladder_tier(original_model)
    features = extract_features(body)
    category, target_tier, confidence, rationale = classifier(features)
    # Universal quality guard (applies whatever the classifier was — global
    # heuristic OR a per-customer rule): a machine-enforced output contract or
    # tool definitions are never routed below Sonnet, so a custom rule can make
    # routing more precise but can't downgrade a structurally brittle call.
    if features.get("has_structured_output") or features.get("has_tools"):
        guarded = max(target_tier, _SONNET_TIER)
        if guarded != target_tier:
            target_tier = guarded
            rationale += "; tool/structured-output contract (floor sonnet)"
    log_features = {k: v for k, v in features.items() if k != "prompt"}

    def stay(reason: str, conf: float = confidence) -> Recommendation:
        return Recommendation(
            action="stay",
            original_model=original_model,
            recommended_model=original_model,
            confidence=conf,
            category=category,
            rationale=reason,
            features=log_features,
        )

    if original_tier is None:
        return stay("unknown model — passthrough", conf=1.0)
    if target_tier >= original_tier:
        return stay(f"{rationale}; requested model already at or below floor")

    # Profile constraints (Track B): a customer-set quality floor (min_model) and
    # allowed/blocked-model compliance. choose_allowed walks up from the cheapest
    # acceptable tier to the nearest permitted model below the requested one.
    if profile is not None:
        from .profile import choose_allowed
        candidate, cand_tier = choose_allowed(target_tier, original_tier, profile)
        if candidate is None:
            return stay(f"{rationale}; no profile-permitted model below "
                        f"{original_model} (min_model/allow-list constraints)")
        if cand_tier != target_tier:
            rationale += f"; profile raised floor to {candidate}"
    else:
        candidate = CAPABILITY_LADDER[target_tier]

    # Economics layer: does the switch pay, given cache state and the expected
    # remainder of the conversation? Pre-flight we approximate the cached
    # prefix by the current context size when cache_control is present; the
    # per-route remaining-length model replaces the flat turn count in Phase 1.
    cached_prefix = features["approx_context_tokens"] if features["has_cache_control"] else 0
    per_turn_in = max(features["approx_context_tokens"], 500)
    per_turn_out = max(features["requested_max_tokens"] // 4, 300)
    benefit = net_switch_benefit(
        original_model,
        candidate,
        cached_prefix_tokens=cached_prefix,
        expected_remaining_input_tokens=int(per_turn_in * expected_remaining_turns),
        expected_remaining_output_tokens=int(per_turn_out * expected_remaining_turns),
    )
    if benefit is not None and benefit <= 0:
        return stay(
            f"{rationale}; capability fits {candidate} but cache-rewrite penalty "
            f"outweighs savings (net ${benefit:.4f})"
        )

    return Recommendation(
        action="switch",
        original_model=original_model,
        recommended_model=candidate,
        confidence=confidence,
        category=category,
        rationale=rationale,
        est_net_benefit=benefit,
        features=log_features,
    )


# ---------------------------------------------------------------------------
# Optional second opinion: Haiku 4.5 as classifier (shadow mode / ambiguous band)
# ---------------------------------------------------------------------------

_HAIKU_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string", "enum": sorted(CATEGORIES.keys())},
        "difficulty": {"type": "string", "enum": ["trivial", "easy", "moderate", "hard", "frontier"]},
        "rationale": {"type": "string"},
    },
    "required": ["category", "difficulty", "rationale"],
    "additionalProperties": False,
}

_DIFFICULTY_TIER_BUMP = {"trivial": 0, "easy": 0, "moderate": 1, "hard": 2, "frontier": 3}


class HaikuClassifier:
    """LLM classifier for the ambiguous band. Costs ~$0.0005/request, so it
    runs off the hot path (shadow scoring, advise mode) — never in autopilot's
    request path.
    """

    def __init__(self, client=None):
        if client is None:
            import anthropic

            client = anthropic.Anthropic(api_key=os.environ.get("MODELPILOT_ROUTER_API_KEY") or None)
        self._client = client

    def __call__(self, features: dict) -> tuple[str, int, float, str]:
        prompt = features["prompt"][:6_000]
        response = self._client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=300,
            system=(
                "You triage requests for an AI-cost router. Classify the user "
                "request into a task category and difficulty. Judge difficulty "
                "by the content, not the instruction verb: a 'summarize' over "
                "dense legal text is hard; a 'write code' for fizzbuzz is trivial."
            ),
            messages=[{"role": "user", "content": f"<request>\n{prompt}\n</request>"}],
            output_config={"format": {"type": "json_schema", "schema": _HAIKU_SCHEMA}},
        )
        text = next(b.text for b in response.content if b.type == "text")
        result = json.loads(text)
        tier = max(
            floor_tier(result["category"]),
            _DIFFICULTY_TIER_BUMP[result["difficulty"]],
        )
        return result["category"], tier, 0.75, f"haiku classifier: {result['rationale']}"
