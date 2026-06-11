"""Router v0: heuristic classifier with an optional Haiku-4.5 second opinion,
plus the cache-aware economics layer that decides whether acting on the
classification actually saves money.

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
import re
from dataclasses import dataclass, field

from .pricing import CAPABILITY_LADDER, ladder_tier, net_switch_benefit
from .taxonomy import CATEGORIES, floor_tier

CHARS_PER_TOKEN = 4  # coarse pre-flight estimate; exact counts come from the response

# Phrases that mark a request as simple enough for the floor tier. Matched on
# the final user message, lowercased.
_SIMPLE_PATTERNS = {
    "classification": r"\b(classif(y|ied)|categori[sz]e|label|sentiment|spam or not|which of the following|yes or no|true or false|intent)\b",
    "extraction": r"\b(extract|pull out|parse out|list (all|the) (names|dates|emails|entities|fields)|into json|as json|csv of)\b",
    "translation": r"\b(translate|translation|in (french|spanish|german|japanese|chinese|korean|italian|portuguese|hindi))\b",
    "rewrite_format": r"\b(rephrase|reword|rewrite this|fix (the )?grammar|proofread|reformat|convert (this|to)|bullet points|title case)\b",
    "summarization_short": r"\b(summari[sz]e|tl;?dr|key points|main takeaways)\b",
    "short_qa": r"^(what|who|when|where|which|how (many|much|long|old))\b",
}

# Phrases that mark genuinely hard work. Any hit forces tier >= opus.
_COMPLEX_PATTERNS = {
    "codegen_complex": r"\b(refactor|migrate|migration|architecture|design (a|the) (system|schema|api)|across (the|multiple) (files|modules|services)|end[- ]to[- ]end)\b",
    "debugging": r"\b(debug|root[- ]cause|race condition|intermittent|flak(y|e)|memory leak|segfault|deadlock|why (is|does|did).{0,40}(fail|crash|break|wrong))\b",
    "math_logic": r"\b(prove|proof|derive|theorem|optimi[sz]e under|np[- ]hard|closed[- ]form)\b",
    "analysis_strategy": r"\b(strategy|trade[- ]?offs?|pros and cons|business case|due diligence|investment (memo|thesis)|negotiat)\b",
}

_CODE_HINT = re.compile(r"```|\bdef |\bclass |\bfunction\b|\bimport |\bSELECT\b.+\bFROM\b|\btraceback\b", re.IGNORECASE)

# A short prompt that points back at earlier session content rather than
# carrying its own task ("why?", "expand on that", "now fix it"). Such a
# prompt inherits the session's difficulty — a cheap model can't answer
# "why?" about an Opus-grade debugging exchange.
_REFERENCE_HINTS = re.compile(
    r"\b(that|this|it|those|above|previous|earlier|again|why|how come|expand|"
    r"continue|go on|elaborate|instead|what about|and the|now (do|try|fix|make|"
    r"apply|update|change)|the (code|bug|fix|function|error|output|result|"
    r"analysis|plan|approach|answer|response))\b"
)
_FOLLOWUP_MAX_CHARS = 250  # longer prompts carry their own content/task
_SESSION_SIGNAL_WINDOW = 30_000  # chars of recent history scanned for signals

# Mechanical tasks operate on whatever content they're given — extraction over
# a hard debugging transcript is still extraction, and calibration v0 measured
# these categories near-perfect on haiku. They keep their own tier even when
# the session is hard ("leverage existing contents" savings).
_MECHANICAL = frozenset({"extraction", "rewrite_format", "translation", "classification"})


@dataclass
class Recommendation:
    action: str  # "switch" | "stay"
    original_model: str
    recommended_model: str
    confidence: float  # 0..1
    category: str
    rationale: str
    est_net_benefit: float | None = None  # $ over expected remainder, switch only
    features: dict = field(default_factory=dict)


def _message_text(msg: dict) -> str:
    content = msg.get("content")
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "\n".join(b.get("text", "") for b in content
                         if isinstance(b, dict) and b.get("type") == "text")
    return ""


def _last_user_text(messages: list) -> str:
    for msg in reversed(messages or []):
        if msg.get("role") == "user":
            text = _message_text(msg)
            if text:
                return text
    return ""


def _session_signals(messages: list, prompt: str) -> dict:
    """What the conversation so far says about difficulty.

    Scans prior turns (user AND assistant — code the assistant wrote is
    session content too) for the same hard-work signals used on the current
    prompt, so routing never treats a turn as an independent decision.
    """
    prior = "\n".join(_message_text(m) for m in messages[:-1])[-_SESSION_SIGNAL_WINDOW:].lower()
    session_max_tier, session_hard = 0, []
    if prior:
        for category, pattern in _COMPLEX_PATTERNS.items():
            if re.search(pattern, prior):
                session_hard.append(category)
                session_max_tier = max(session_max_tier, floor_tier(category))
        if _CODE_HINT.search(prior):
            session_max_tier = max(session_max_tier, floor_tier("codegen_simple"))
    is_followup = (bool(prior)
                   and len(prompt) < _FOLLOWUP_MAX_CHARS
                   and bool(_REFERENCE_HINTS.search(prompt.lower())))
    return {"session_max_tier": session_max_tier,
            "session_hard": session_hard,
            "is_followup": is_followup}


def extract_features(body: dict) -> dict:
    """Pre-flight features from a /v1/messages request body."""
    messages = body.get("messages") or []
    prompt = _last_user_text(messages)
    system = body.get("system") or ""
    if isinstance(system, list):
        system = "\n".join(b.get("text", "") for b in system if isinstance(b, dict))
    total_chars = len(json.dumps(messages)) + len(system)
    has_cache_control = "cache_control" in json.dumps(body)
    return {
        "prompt": prompt,
        "prompt_chars": len(prompt),
        "n_turns": len(messages),
        "approx_context_tokens": total_chars // CHARS_PER_TOKEN,
        "has_tools": bool(body.get("tools")),
        "has_images": '"type": "image"' in json.dumps(messages) or '"type":"image"' in json.dumps(messages),
        "has_code": bool(_CODE_HINT.search(prompt)),
        "has_cache_control": has_cache_control,
        "requested_max_tokens": body.get("max_tokens") or 0,
        **_session_signals(messages, prompt),
    }


def classify(features: dict) -> tuple[str, int, float, str]:
    """Session-context-aware classification.

    Each prompt is first classified on its own, then reconciled with the
    conversation: a short follow-up referencing earlier hard work inherits
    the session's difficulty (a cheap model can't reason over Opus-grade
    context), while mechanical tasks keep their own cheap tier even in hard
    sessions — that's where existing content gets leveraged for savings.
    """
    category, tier, confidence, rationale = _classify_standalone(features)
    session_tier = features.get("session_max_tier", 0)
    if (features.get("is_followup")
            and session_tier > tier
            and category not in _MECHANICAL):
        hard = "/".join(features.get("session_hard") or []) or "earlier work"
        return ("followup_in_context", session_tier, 0.8,
                f"short follow-up referencing {hard} in this session — "
                f"inheriting session difficulty (standalone read: {category})")
    return category, tier, confidence, rationale


def _classify_standalone(features: dict) -> tuple[str, int, float, str]:
    """Per-prompt heuristic -> (category, target_tier, confidence, rationale).

    Confidence reflects how unambiguous the signals are, not model quality.
    The golden-set-trained router replaces this in Phase 1; the interface stays.
    """
    prompt = features["prompt"].lower()

    for category, pattern in _COMPLEX_PATTERNS.items():
        if re.search(pattern, prompt):
            return category, floor_tier(category), 0.8, f"complex-work signal ({category})"

    simple_hits = [c for c, p in _SIMPLE_PATTERNS.items() if re.search(p, prompt)]
    if simple_hits:
        category = simple_hits[0]
        tier = floor_tier(category)
        confidence = 0.85
        rationale = f"simple-task signal ({category})"
        # Size and shape penalties: big context, tools, or heavy code lower
        # our certainty that the floor tier suffices.
        if features["approx_context_tokens"] > 50_000:
            tier += 1
            confidence -= 0.15
            rationale += "; large context (+1 tier)"
        if features["has_tools"]:
            tier = max(tier, 1)
            confidence -= 0.15
            rationale += "; tool use (floor sonnet)"
        if features["has_code"] and category not in ("extraction", "rewrite_format"):
            tier = max(tier, 1)
            confidence -= 0.10
            rationale += "; code present (floor sonnet)"
        if len(simple_hits) > 1:
            confidence -= 0.05  # mixed signals
        return category, min(tier, len(CAPABILITY_LADDER) - 1), max(confidence, 0.0), rationale

    if features["has_tools"] or features["n_turns"] > 12:
        return "agentic", floor_tier("agentic"), 0.6, "tool use / long multi-turn — treating as agentic"
    if features["has_code"]:
        category = "codegen_complex" if features["prompt_chars"] > 2_000 else "codegen_simple"
        return category, floor_tier(category), 0.55, f"code present, sized as {category}"
    if features["prompt_chars"] < 400 and features["approx_context_tokens"] < 4_000:
        return "conversation", floor_tier("conversation"), 0.5, "short generic prompt"
    return "unknown", floor_tier("unknown"), 0.3, "no clear signal — staying conservative"


def recommend(
    body: dict,
    expected_remaining_turns: float = 5.0,
    classifier=classify,
) -> Recommendation:
    """Full routing decision for one request body."""
    original_model = body.get("model", "")
    original_tier = ladder_tier(original_model)
    features = extract_features(body)
    category, target_tier, confidence, rationale = classifier(features)
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
