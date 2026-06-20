"""Cost normalization — token counts → USD.

The single most common way naive spend trackers are wrong: they multiply *all*
input tokens by the base input rate. Cache reads cost ~0.1× and cache writes
~1.25× of base input. On an agentic coding workload that re-sends a large repo
prefix every turn, cache reads dominate the token count — so collapsing them
into base-rate input inflates the bill 5–10×. We cost each token *class*
separately.

Rates are USD per 1,000,000 tokens, current Anthropic tier as used elsewhere in
this repo. `cache_read` = 0.1× input, `cache_write` (5-min TTL) = 1.25× input —
the standard Anthropic prompt-cache economics.
"""

from __future__ import annotations

from dataclasses import dataclass

from .models import UsageEvent


@dataclass(frozen=True)
class ModelRate:
    """Per-1M-token rates. `tier` is the capability-ladder position used by the
    routing recommender (0=cheapest .. 3=most capable). Cache multipliers are
    per-provider: Anthropic caches read at 0.1x / write at 1.25x of base input;
    OpenAI caches read at 0.5x with no separate write charge."""

    model: str
    input_per_m: float
    output_per_m: float
    tier: int
    cache_read_mult: float = 0.1
    cache_write_mult: float = 1.25

    @property
    def cache_read_per_m(self) -> float:
        return self.input_per_m * self.cache_read_mult

    @property
    def cache_write_per_m(self) -> float:
        return self.input_per_m * self.cache_write_mult


# Canonical model → rate. Keep ids in sync with the rest of the repo's model
# catalog. Unknown models fall back to the Sonnet-tier rate with a flag so the
# pipeline degrades loudly rather than silently mis-costing.
RATES: dict[str, ModelRate] = {
    "claude-haiku-4-5": ModelRate("claude-haiku-4-5", 1.0, 5.0, tier=0),
    "claude-sonnet-4-6": ModelRate("claude-sonnet-4-6", 3.0, 15.0, tier=1),
    "claude-opus-4-8": ModelRate("claude-opus-4-8", 5.0, 25.0, tier=2),
    "claude-fable-5": ModelRate("claude-fable-5", 10.0, 50.0, tier=3),
}

# Ordered cheapest → most capable; used to find a downgrade candidate. Built from
# the Claude RATES only — the routing recommender is Claude-tier-aware and must not
# see other providers' models.
TIER_LADDER: list[str] = sorted(RATES, key=lambda m: RATES[m].tier)

# OpenAI / Azure OpenAI rates — kept SEPARATE from the Claude tier ladder above,
# with OpenAI's own cache economics (cached input ~0.5x, no cache-write charge).
# Approximate USD/1M; update as OpenAI reprices. Used only to cost ingested
# OpenAI spend, never for routing.
OPENAI_RATES: dict[str, ModelRate] = {
    "gpt-4o-mini": ModelRate("gpt-4o-mini", 0.15, 0.60, tier=0, cache_read_mult=0.5, cache_write_mult=0.0),
    "o3-mini":     ModelRate("o3-mini", 1.10, 4.40, tier=1, cache_read_mult=0.5, cache_write_mult=0.0),
    "gpt-4.1":     ModelRate("gpt-4.1", 2.00, 8.00, tier=1, cache_read_mult=0.5, cache_write_mult=0.0),
    "gpt-4o":      ModelRate("gpt-4o", 2.50, 10.00, tier=2, cache_read_mult=0.5, cache_write_mult=0.0),
    "gpt-4-turbo": ModelRate("gpt-4-turbo", 10.0, 30.0, tier=2, cache_read_mult=0.5, cache_write_mult=0.0),
    "o1":          ModelRate("o1", 15.0, 60.0, tier=3, cache_read_mult=0.5, cache_write_mult=0.0),
}

_FALLBACK = RATES["claude-sonnet-4-6"]
_OPENAI_FALLBACK = OPENAI_RATES["gpt-4o"]


def _resolve(model: str) -> tuple[ModelRate, bool]:
    """Resolve a model id to (rate, known). `known=False` means no exact rate was
    found and we fell back to a nearest-tier estimate — the caller should surface
    that so an unrecognized model never silently mis-costs the bill."""
    if model in RATES:
        return RATES[model], True
    if model in OPENAI_RATES:
        return OPENAI_RATES[model], True
    norm = (model or "").replace("anthropic.", "")
    # Strip a trailing -YYYYMMDD date snapshot if present.
    for known in RATES:
        if norm == known or norm.startswith(known + "-"):
            return RATES[known], True
    for known in OPENAI_RATES:
        if norm == known or norm.startswith(known + "-"):
            return OPENAI_RATES[known], True
    # An OpenAI-family id we don't have an exact rate for → OpenAI fallback, not Claude.
    if norm.startswith(("gpt", "o1", "o3", "o4", "chatgpt")):
        return _OPENAI_FALLBACK, False
    return _FALLBACK, False


def rate_for(model: str) -> ModelRate:
    """Resolve a model id to its rate, tolerating minor id drift (date suffixes,
    `anthropic.` provider prefixes from Bedrock-style ids). OpenAI ids resolve to
    the separate OpenAI table. Unknown ids fall back to a nearest-tier rate — use
    `model_is_known` to detect that case and surface it."""
    return _resolve(model)[0]


def model_is_known(model: str) -> bool:
    """True iff `model` resolves to an exact rate (not a nearest-tier fallback)."""
    return _resolve(model)[1]


def cost_usd(event: UsageEvent) -> float:
    """Normalized cost of a single usage event, in USD. Token counts are clamped at
    zero — a negative count is nonsensical data and must never *reduce* the bill."""
    r = rate_for(event.model)
    it = max(0, event.input_tokens)
    ot = max(0, event.output_tokens)
    cr = max(0, event.cache_read_tokens)
    cw = max(0, event.cache_write_tokens)
    return (
        it * r.input_per_m
        + ot * r.output_per_m
        + cr * r.cache_read_per_m
        + cw * r.cache_write_per_m
    ) / 1_000_000.0
