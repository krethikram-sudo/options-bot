"""Commodity classifier: turn a /v1/messages request into a task *category*,
*confidence*, and pre-flight *features* — with NO pricing, taxonomy, floors, or
economics. This is the only part of the router that is safe to publish in the
thin client: it reveals lexical heuristics (regexes), not the per-category
capability floors, price table, or switch economics that decide what actually
gets routed. Those stay server-side (router.py / brain/server.py).

Stdlib-only by design (json, re, dataclasses) so the published client carries no
ModelPilot internals beyond category detection.

Tier handling is *injected*, not imported. Callers that own the floor policy
(router.py) pass a `floor_tier(category, floors)` callable and get a full
`(category, tier, confidence, rationale)` decision; the thin client calls with
no `floor_tier` (commodity mode) and gets `(category, None, confidence,
rationale)` — it only ever needs the category label and confidence to hand to
the brain, never the tier.
"""

import json
import re
from dataclasses import dataclass, field

CHARS_PER_TOKEN = 4  # coarse pre-flight estimate; exact counts come from the response

# Capability-ladder positions, mirrored here as plain literals so this commodity
# module needs no pricing import. The pricing module asserts they stay in sync
# (0=haiku, 1=sonnet, 2=opus, 3=fable). These are just ladder *positions* —
# public model ordering, not the category->floor IP.
_SONNET_TIER = 1  # claude-sonnet-4-6 — quality floor for brittle calls
_TOP_TIER = 3     # highest ladder index (claude-fable-5)

# Phrases that mark a request as simple enough for the floor tier. Matched on
# the final user message, lowercased.
_SIMPLE_PATTERNS = {
    # Fixed-answer markers (one label / binary / single word) are cheap-tier-safe.
    "classification": r"\b(classif(y|ied)|categori[sz]e|label|sentiment|spam|which of the following|yes or no|yes/no|pass/fail|pass or fail|one[- ]word|true or false|intent)\b",
    # Data-shaping markers: pull fields out, or reshape into a table/rows/columns.
    "extraction": r"\b(extract|pull out|parse|list (all|the) (names|dates|emails|entities|fields)|into json|as json|into (rows|columns|a table|a spreadsheet)|csv of)\b",
    "translation": r"\b(translate|translation|in (french|spanish|german|japanese|chinese|korean|italian|portuguese|hindi))\b",
    # Code-WRITING intent (no actual code need be present): "write a SQL query",
    # "implement a function", "generate a regex". Narrow nouns keep complex work
    # (rate limiters, caches, algorithms) out — those fall through to the
    # has_code/complex paths and stay on the top model.
    "codegen_simple": (
        r"\b(write|create|implement|generate|code|give me) (a |an |the )?"
        r"(simple |small |basic |quick )?"
        r"(python |sql |javascript |js |typescript |ts |bash |shell |java |go(lang)? |rust |regex )?"
        r"(function|method|query|script|snippet|regex|one[- ]liner|command|helper|loop|utility)\b"
    ),
    "rewrite_format": (
        r"\b(rephrase|reword|rewrite this|fix (the )?grammar|proofread|reformat|"
        r"convert (this|to)|bullet points?|bulleted list|numbered list|"
        r"(turn|format) (this|these|it) (in)?to|(as|into) an? .{0,12}list|title case|"
        r"make (this|it)\b.{0,30}\b(concise|professional|formal|polished|clearer|shorter|simpler)|"
        r"more concise|tighten (this|it|up)|past tense|present tense|plural of|"
        r"conjugat\w*|opposite of|synonyms?|antonyms?|"
        # Short transactional drafting (reply/email/status update). Audience
        # constraints ("customer-facing") then floor it to sonnet via the
        # _CONTENT_SENSITIVE block; operational drafting ("runbook") has no
        # matching noun here and stays on the top model.
        r"(draft|compose|write)\b.{0,40}?\b(status[- ]?page|reply|response|email|update|memo|message|note))\b"
    ),
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

# Content-difficulty signals (calibration v0, seed-027): the judge found the
# status-page rewrite of an incident needed sonnet while the postmortem and
# legal summaries of the SAME material were haiku-fine. The hard part is the
# audience constraint (public-facing wording under filtering rules), not the
# content domain — so audience constraints floor the tier, while dense
# operational/legal content only reduces confidence (below the autopilot
# gate -> runs baseline; never forces a tier the labels don't support).
_AUDIENCE_CONSTRAINT = re.compile(
    r"\b(status page|customer[- ]facing|public[- ]facing|press release|"
    r"for (customers|the public|the press|investors|executives|leadership|"
    r"the board)|external (announcement|comms))\b"
)
_HARD_CONTENT = re.compile(
    r"\b(indemnif\w+|liabilit\w+|notwithstanding|pursuant|herein|warrant\w+|"
    r"aggregate liability|rollback|error rate|p9[59]|deadlock|outage|"
    r"postmortem|stack trace|root[- ]cause)\b"
)
_CONTENT_SENSITIVE = frozenset({"summarization_short", "summarization_long", "rewrite_format"})

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
# A "summarize…" instruction reads as simple, but summarizing a long/dense source
# is not cheap-tier-safe — the work scales with the source. Above this context size
# we treat it as summarization_long (floor sonnet), not summarization_short.
_LONG_SUMMARY_TOKENS = 6_000


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
    """What the conversation so far says about difficulty (tier-free).

    Scans prior turns (user AND assistant — code the assistant wrote is session
    content too) for the same hard-work signals used on the current prompt, and
    reports *which* hard categories appeared (`session_hard`) plus whether the
    current prompt is a back-referencing follow-up. The session's tier is
    derived from `session_hard` by whoever owns the floor policy — never here.
    """
    prior = "\n".join(_message_text(m) for m in messages[:-1])[-_SESSION_SIGNAL_WINDOW:].lower()
    session_hard = []
    if prior:
        for category, pattern in _COMPLEX_PATTERNS.items():
            if re.search(pattern, prior):
                session_hard.append(category)
    is_followup = (bool(prior)
                   and len(prompt) < _FOLLOWUP_MAX_CHARS
                   and bool(_REFERENCE_HINTS.search(prompt.lower())))
    return {"session_hard": session_hard, "is_followup": is_followup}


def extract_features(body: dict) -> dict:
    """Pre-flight features from a /v1/messages request body. All numeric/boolean
    plus the (server-discardable) prompt text — no pricing or floor lookups."""
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
        # A machine-enforced output contract (structured outputs / JSON schema /
        # response_format). A cheaper model can be semantically non-inferior yet
        # emit a structurally different shape that breaks brittle downstream
        # parsing — so these are routed conservatively (floor sonnet).
        "has_structured_output": bool(body.get("output_config") or body.get("response_format")),
        "has_images": '"type": "image"' in json.dumps(messages) or '"type":"image"' in json.dumps(messages),
        "has_code": bool(_CODE_HINT.search(prompt)),
        "has_cache_control": has_cache_control,
        "requested_max_tokens": body.get("max_tokens") or 0,
        **_session_signals(messages, prompt),
    }


def match_rule(prompt: str, rules: list | None):
    """First customer rule whose lexical signals match the prompt, or None.

    Commodity: a rule is `{name, any:[substrings], regex:[patterns], category}` —
    pure signal→category mapping, no tiers/floors (those stay server-side). Lets
    the published thin client apply admin-approved Track-C rules locally."""
    if not rules:
        return None
    low = prompt.lower()
    for r in rules:
        if any(str(s).lower() in low for s in (r.get("any") or [])):
            return r
        for pat in (r.get("regex") or []):
            try:
                if re.search(pat, prompt, re.IGNORECASE):
                    return r
            except re.error:
                continue
    return None


def classify(features: dict, floor_tier=None, floors: dict | None = None,
             rules: list | None = None):
    """Session-context-aware classification.

    Each prompt is first classified on its own, then reconciled with the
    conversation: a short follow-up referencing earlier hard work inherits the
    session's difficulty (a cheap model can't reason over Opus-grade context),
    while mechanical tasks keep their own cheap tier even in hard sessions —
    that's where existing content gets leveraged for savings.

    `rules` (optional) are admin-approved per-customer classification rules
    (Track C): a matching rule sets the category, still passing through follow-up
    reconciliation so a cheap rule can't strand a hard follow-up.

    `floor_tier` is an injected `floor_tier(category, floors)` callable owned by
    the caller (router.py). With it, returns `(category, tier, confidence,
    rationale)`. Without it (commodity / thin-client mode), `tier` is None and
    follow-up detection falls back to "any hard category in the session" — the
    thin client only needs the category + confidence to send to the brain.
    """
    rule = match_rule(features.get("prompt", ""), rules)
    if rule is not None:
        cat = rule.get("category")
        conf = float(rule.get("confidence", 0.85))
        tier = floor_tier(cat, floors) if floor_tier is not None else None
        return reconcile_followup(features, cat, tier, conf,
                                  f"customer rule '{rule.get('name') or cat}' -> {cat}", floor_tier)
    category, tier, confidence, rationale = _classify_standalone(features, floor_tier, floors)
    return reconcile_followup(features, category, tier, confidence, rationale, floor_tier)


def reconcile_followup(features: dict, category: str, tier, confidence: float,
                       rationale: str, floor_tier=None):
    """Reconcile a standalone classification with the session.

    A short follow-up referencing earlier hard work inherits the session's
    difficulty (a cheap model can't reason over Opus-grade context); mechanical
    tasks keep their own cheap tier even in hard sessions. Shared by the global
    classifier and the per-customer rule layer so rules get the same protection.

    Session difficulty is assessed at the *global* floor (no per-customer floors)
    — the conservative choice. In commodity mode (`floor_tier` is None) we can't
    compare tiers, so any hard session category flips a non-mechanical follow-up;
    the brain resolves the actual tier.
    """
    if not (features.get("is_followup")
            and features.get("session_hard")
            and category not in _MECHANICAL):
        return category, tier, confidence, rationale
    hard = "/".join(features.get("session_hard") or []) or "earlier work"
    msg = (f"short follow-up referencing {hard} in this session — "
           f"inheriting session difficulty (standalone read: {category})")
    if floor_tier is None:
        return "followup_in_context", tier, 0.8, msg
    session_tier = max((floor_tier(c) for c in features["session_hard"]), default=0)
    if session_tier > tier:
        return "followup_in_context", session_tier, 0.8, msg
    return category, tier, confidence, rationale


def _classify_standalone(features: dict, floor_tier=None, floors: dict | None = None):
    """Per-prompt heuristic -> (category, target_tier, confidence, rationale).

    Confidence reflects how unambiguous the signals are, not model quality. When
    `floor_tier` is None (commodity mode) the tier is None and the tier-floor
    bumps are skipped; the confidence penalties (which are pure ambiguity
    signals) always apply.
    """
    prompt = features["prompt"].lower()
    tiered = floor_tier is not None

    def base_tier(category: str):
        return floor_tier(category, floors) if tiered else None

    for category, pattern in _COMPLEX_PATTERNS.items():
        if re.search(pattern, prompt):
            return category, base_tier(category), 0.8, f"complex-work signal ({category})"

    simple_hits = [c for c, p in _SIMPLE_PATTERNS.items() if re.search(p, prompt)]
    if simple_hits:
        category = simple_hits[0]
        # Promote short->long summarization by the actual source size: a summary of a
        # long/dense document needs more than the cheapest tier even though the
        # instruction looks simple. (The work scales with the source, not the prompt.)
        long_summary = (category == "summarization_short"
                        and features["approx_context_tokens"] >= _LONG_SUMMARY_TOKENS)
        if long_summary:
            category = "summarization_long"
        tier = base_tier(category)
        confidence = 0.85
        rationale = f"simple-task signal ({category})"
        if long_summary:
            rationale += "; long/dense source -> summarization_long (floor sonnet)"
        # Size and shape penalties: big context, tools, or heavy code lower
        # our certainty that the floor tier suffices.
        if features["approx_context_tokens"] > 50_000:
            if tiered:
                tier += 1
            confidence -= 0.15
            rationale += "; large context (+1 tier)"
        if features["has_tools"]:
            if tiered:
                tier = max(tier, _SONNET_TIER)
            confidence -= 0.15
            rationale += "; tool use (floor sonnet)"
        if features.get("has_structured_output"):
            if tiered:
                tier = max(tier, _SONNET_TIER)
            confidence -= 0.10
            rationale += "; structured-output contract (floor sonnet)"
        if features["has_code"] and category not in ("extraction", "rewrite_format"):
            if tiered:
                tier = max(tier, _SONNET_TIER)
            confidence -= 0.10
            rationale += "; code present (floor sonnet)"
        if category in _CONTENT_SENSITIVE:
            if _AUDIENCE_CONSTRAINT.search(prompt):
                if tiered:
                    tier = max(tier, _SONNET_TIER)
                confidence -= 0.05
                rationale += "; audience-constrained output (floor sonnet)"
            elif _HARD_CONTENT.search(prompt):
                confidence -= 0.10
                rationale += "; dense operational/legal content (confidence reduced)"
        if len(simple_hits) > 1:
            confidence -= 0.05  # mixed signals
        # Penalties accumulate in floating point (0.85 - 0.05 = 0.7999...);
        # round so confidence compares cleanly against the gate.
        if tiered:
            tier = min(tier, _TOP_TIER)
        return category, tier, round(max(confidence, 0.0), 2), rationale

    if features["has_tools"] or features["n_turns"] > 12:
        return "agentic", base_tier("agentic"), 0.6, "tool use / long multi-turn — treating as agentic"
    if features["has_code"]:
        category = "codegen_complex" if features["prompt_chars"] > 2_000 else "codegen_simple"
        return category, base_tier(category), 0.55, f"code present, sized as {category}"
    if features["prompt_chars"] < 400 and features["approx_context_tokens"] < 4_000:
        return "conversation", base_tier("conversation"), 0.5, "short generic prompt"
    return "unknown", base_tier("unknown"), 0.3, "no clear signal — staying conservative"
