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
    routing recommender (0=cheapest .. 3=most capable)."""

    model: str
    input_per_m: float
    output_per_m: float
    tier: int

    # Anthropic prompt-cache multipliers relative to base input price.
    CACHE_READ_MULT = 0.1
    CACHE_WRITE_MULT = 1.25

    @property
    def cache_read_per_m(self) -> float:
        return self.input_per_m * self.CACHE_READ_MULT

    @property
    def cache_write_per_m(self) -> float:
        return self.input_per_m * self.CACHE_WRITE_MULT


# Canonical model → rate. Keep ids in sync with the rest of the repo's model
# catalog. Unknown models fall back to the Sonnet-tier rate with a flag so the
# pipeline degrades loudly rather than silently mis-costing.
RATES: dict[str, ModelRate] = {
    "claude-haiku-4-5": ModelRate("claude-haiku-4-5", 1.0, 5.0, tier=0),
    "claude-sonnet-4-6": ModelRate("claude-sonnet-4-6", 3.0, 15.0, tier=1),
    "claude-opus-4-8": ModelRate("claude-opus-4-8", 5.0, 25.0, tier=2),
    "claude-fable-5": ModelRate("claude-fable-5", 10.0, 50.0, tier=3),
}

# Ordered cheapest → most capable; used to find a downgrade candidate.
TIER_LADDER: list[str] = sorted(RATES, key=lambda m: RATES[m].tier)

_FALLBACK = RATES["claude-sonnet-4-6"]


def rate_for(model: str) -> ModelRate:
    """Resolve a model id to its rate, tolerating minor id drift (date suffixes,
    `anthropic.` provider prefixes from Bedrock-style ids)."""
    if model in RATES:
        return RATES[model]
    norm = model.replace("anthropic.", "")
    # Strip a trailing -YYYYMMDD date snapshot if present.
    for known in RATES:
        if norm == known or norm.startswith(known + "-"):
            return RATES[known]
    return _FALLBACK


def cost_usd(event: UsageEvent) -> float:
    """Normalized cost of a single usage event, in USD."""
    r = rate_for(event.model)
    return (
        event.input_tokens * r.input_per_m
        + event.output_tokens * r.output_per_m
        + event.cache_read_tokens * r.cache_read_per_m
        + event.cache_write_tokens * r.cache_write_per_m
    ) / 1_000_000.0
