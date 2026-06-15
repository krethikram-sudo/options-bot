"""Price table and cost math for Claude models.

Prices are USD per million tokens (June 2026 list). Keep this as data so a
price change is a config edit, not a code change. Cache multipliers per the
Claude API: reads ~0.1x input price, 5-minute-TTL writes 1.25x.
"""

from dataclasses import dataclass, field


CACHE_READ_MULT = 0.10
CACHE_WRITE_MULT = 1.25

# Anthropic minimum tokens for a prompt-cache breakpoint, and the Batch API discount.
MIN_CACHEABLE_TOKENS = 1024
BATCH_DISCOUNT = 0.50


@dataclass(frozen=True)
class ModelPrice:
    input_per_mtok: float
    output_per_mtok: float


PRICES = {
    "claude-fable-5": ModelPrice(10.00, 50.00),
    "claude-opus-4-8": ModelPrice(5.00, 25.00),
    "claude-opus-4-7": ModelPrice(5.00, 25.00),
    "claude-opus-4-6": ModelPrice(5.00, 25.00),
    "claude-opus-4-5": ModelPrice(5.00, 25.00),
    "claude-sonnet-4-6": ModelPrice(3.00, 15.00),
    "claude-sonnet-4-5": ModelPrice(3.00, 15.00),
    "claude-haiku-4-5": ModelPrice(1.00, 5.00),
}

# Cheapest to most capable. The router recommends moves down this ladder only.
CAPABILITY_LADDER = [
    "claude-haiku-4-5",
    "claude-sonnet-4-6",
    "claude-opus-4-8",
    "claude-fable-5",
]


def apply_overrides(overrides: dict) -> None:
    """Merge a customer's negotiated rates into the price table in place.

    Single-tenant by design (one local gateway = one customer), so updating the
    process-global table is correct and means every cost path — router economics,
    ledger, dashboard, digest, compare — reflects the customer's ACTUAL bill with
    no plumbing. Values may be ModelPrice or (input, output) tuples. Called once
    at gateway startup from the deployment profile."""
    for model, price in (overrides or {}).items():
        if not isinstance(price, ModelPrice):
            price = ModelPrice(float(price[0]), float(price[1]))
        PRICES[model] = price


def resolve_price(model: str) -> ModelPrice | None:
    """Look up a price, tolerating date-suffixed IDs like claude-haiku-4-5-20251001."""
    if model in PRICES:
        return PRICES[model]
    for known, price in PRICES.items():
        if model.startswith(known):
            return price
    return None


def ladder_tier(model: str) -> int | None:
    """Position on the capability ladder, or None for unknown models."""
    for i, known in enumerate(CAPABILITY_LADDER):
        if model == known or model.startswith(known):
            return i
    # Older opus/sonnet aliases share a tier with their current sibling.
    if model.startswith("claude-opus"):
        return CAPABILITY_LADDER.index("claude-opus-4-8")
    if model.startswith("claude-sonnet"):
        return CAPABILITY_LADDER.index("claude-sonnet-4-6")
    if model.startswith("claude-haiku"):
        return CAPABILITY_LADDER.index("claude-haiku-4-5")
    return None


@dataclass
class Usage:
    """Token usage as reported by the API's `usage` block."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_input_tokens: int = 0
    cache_creation_input_tokens: int = 0

    @classmethod
    def from_api(cls, usage: dict) -> "Usage":
        return cls(
            input_tokens=usage.get("input_tokens") or 0,
            output_tokens=usage.get("output_tokens") or 0,
            cache_read_input_tokens=usage.get("cache_read_input_tokens") or 0,
            cache_creation_input_tokens=usage.get("cache_creation_input_tokens") or 0,
        )


def request_cost(model: str, usage: Usage) -> float | None:
    """Dollar cost of a request at this model's list prices."""
    price = resolve_price(model)
    if price is None:
        return None
    per_tok_in = price.input_per_mtok / 1_000_000
    per_tok_out = price.output_per_mtok / 1_000_000
    return (
        usage.input_tokens * per_tok_in
        + usage.cache_read_input_tokens * per_tok_in * CACHE_READ_MULT
        + usage.cache_creation_input_tokens * per_tok_in * CACHE_WRITE_MULT
        + usage.output_tokens * per_tok_out
    )


def baseline_cost(baseline_model: str, usage: Usage) -> float | None:
    """Layer-1 counterfactual: re-price the same tokens at the baseline model.

    This is an estimate — output length and cache state would differ on the
    baseline model. The replay-sampling job (Phase 2) calibrates it.
    """
    return request_cost(baseline_model, usage)


def cache_switch_penalty(model_to: str, cached_prefix_tokens: int) -> float:
    """Extra input cost incurred on the first turn after a model switch.

    Caches are model-scoped: a switch turns a ~0.1x cached read into a
    ~1.25x fresh cache write on the new model.
    """
    price = resolve_price(model_to)
    if price is None or cached_prefix_tokens <= 0:
        return 0.0
    per_tok = price.input_per_mtok / 1_000_000
    return cached_prefix_tokens * per_tok * (CACHE_WRITE_MULT - 0.0)


def cache_savings(model: str, prefix_tokens: int, turns: float) -> float:
    """Estimated dollars saved over `turns` by caching a reusable prefix
    (system prompt / shared context) instead of re-sending it uncached each turn.

    Uncached: the prefix is billed at 1.0x input every turn. Cached: 1.25x once to
    write, then 0.10x to read on each subsequent turn. Returns 0 when caching isn't
    worthwhile (prefix below the cache minimum, or a single turn)."""
    price = resolve_price(model)
    if price is None or prefix_tokens < MIN_CACHEABLE_TOKENS or turns < 2:
        return 0.0
    per_tok = price.input_per_mtok / 1_000_000
    uncached = turns * 1.0
    cached = CACHE_WRITE_MULT + (turns - 1) * CACHE_READ_MULT
    return max(0.0, prefix_tokens * per_tok * (uncached - cached))


def batch_savings(model: str, input_tokens: int, output_tokens: int) -> float:
    """Dollars saved by sending a latency-tolerant request through the Batch API
    (50% off both input and output) instead of the synchronous endpoint."""
    cost = request_cost(model, Usage(input_tokens=int(input_tokens),
                                     output_tokens=int(output_tokens)))
    return 0.0 if cost is None else cost * BATCH_DISCOUNT


def net_switch_benefit(
    model_from: str,
    model_to: str,
    cached_prefix_tokens: int,
    expected_remaining_input_tokens: int,
    expected_remaining_output_tokens: int,
) -> float | None:
    """Expected dollars saved by switching, net of the cache-rewrite penalty.

    Positive means the switch pays off over the expected remainder of the
    conversation. The cached prefix is valued at what it would have cost to
    keep reading it on the old model vs. rewriting it on the new one.
    """
    p_from = resolve_price(model_from)
    p_to = resolve_price(model_to)
    if p_from is None or p_to is None:
        return None
    d_in = (p_from.input_per_mtok - p_to.input_per_mtok) / 1_000_000
    d_out = (p_from.output_per_mtok - p_to.output_per_mtok) / 1_000_000
    gross = (
        expected_remaining_input_tokens * d_in
        + expected_remaining_output_tokens * d_out
    )
    # Staying: prefix read at 0.1x old price. Switching: rewrite at 1.25x new price.
    stay_prefix = cached_prefix_tokens * (p_from.input_per_mtok / 1_000_000) * CACHE_READ_MULT
    switch_prefix = cached_prefix_tokens * (p_to.input_per_mtok / 1_000_000) * CACHE_WRITE_MULT
    return gross - (switch_prefix - stay_prefix)
