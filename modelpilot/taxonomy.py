"""Task taxonomy and the category -> minimum-capable-model policy table.

Tiers index into pricing.CAPABILITY_LADDER:
  0 = haiku, 1 = sonnet, 2 = opus, 3 = fable.

The policy table encodes the *floor* — the cheapest tier we believe is
non-inferior for a typical request in that category. The router only ever
moves a request down to its floor, never above the model the caller asked
for, and the economics layer can veto the move.
"""

CATEGORIES = {
    # category: (floor_tier, description)
    "classification": (0, "label/sentiment/intent/spam, fixed answer set"),
    "extraction": (0, "pull fields/entities into structured form"),
    "translation": (0, "language translation, short-to-medium text"),
    "short_qa": (0, "factual lookup-style question, short answer"),
    "summarization_short": (0, "summarize a short document or thread"),
    "summarization_long": (1, "summarize long/complex material"),
    "rewrite_format": (0, "rephrase, fix grammar, reformat, convert"),
    "codegen_simple": (1, "small function, snippet, regex, one-file edit"),
    "codegen_complex": (2, "multi-file feature, refactor, architecture"),
    "debugging": (2, "root-cause a failure, fix a non-obvious bug"),
    "math_logic": (2, "proofs, multi-step quantitative reasoning"),
    "agentic": (2, "tool-using, multi-step autonomous task"),
    "analysis_strategy": (2, "open-ended analysis, planning, judgment"),
    "creative_longform": (1, "essays, marketing copy, stories"),
    "conversation": (1, "general chat, advice, brainstorming"),
    "followup_in_context": (1, "short follow-up that depends on earlier session content; tier inherited from the session"),
    "unknown": (2, "could not classify — stay conservative"),
}


def floor_tier(category: str) -> int:
    return CATEGORIES.get(category, CATEGORIES["unknown"])[0]
