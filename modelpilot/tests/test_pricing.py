from modelpilot.pricing import (
    BATCH_DISCOUNT,
    MIN_CACHEABLE_TOKENS,
    Usage,
    baseline_cost,
    batch_savings,
    cache_request_overpay,
    cache_savings,
    realized_cache_savings,
    ladder_tier,
    net_switch_benefit,
    request_cost,
    resolve_price,
)


def test_cache_savings_grows_with_turns():
    # A 10k-token prefix reused across turns saves more the more it's reused.
    s2 = cache_savings("claude-opus-4-8", 10_000, 2)
    s10 = cache_savings("claude-opus-4-8", 10_000, 10)
    assert s2 > 0 and s10 > s2
    # 10k tokens * $5/MTok input over 2 turns: uncached 2.0x vs cached 1.35x = 0.65x.
    per_tok = 5.0 / 1_000_000
    assert abs(s2 - 10_000 * per_tok * (2.0 - 1.35)) < 1e-9


def test_cache_savings_zero_when_not_worthwhile():
    assert cache_savings("claude-opus-4-8", MIN_CACHEABLE_TOKENS - 1, 10) == 0.0  # below cache min
    assert cache_savings("claude-opus-4-8", 50_000, 1) == 0.0                     # single turn
    assert cache_savings("nope", 50_000, 10) == 0.0                               # unknown model


def test_cache_request_overpay_is_per_request_marginal():
    # 10k-token prefix at opus $5/MTok input, billed full vs ~10% cache read = 0.9x.
    per_tok = 5.0 / 1_000_000
    assert abs(cache_request_overpay("claude-opus-4-8", 10_000) - 10_000 * per_tok * 0.9) < 1e-12
    assert cache_request_overpay("claude-opus-4-8", 500) == 0.0  # below cache minimum


def test_realized_cache_savings_nets_write_penalty():
    per_tok = 5.0 / 1_000_000  # opus input
    # reads save 0.90x, writes cost 0.25x extra
    assert abs(realized_cache_savings("claude-opus-4-8", 10_000, 0) - 10_000 * per_tok * 0.9) < 1e-12
    assert abs(realized_cache_savings("claude-opus-4-8", 0, 10_000) - (-10_000 * per_tok * 0.25)) < 1e-12
    # mixed: a write turn plus later reads nets positive
    mixed = realized_cache_savings("claude-opus-4-8", 30_000, 10_000)
    assert abs(mixed - (30_000 * per_tok * 0.9 - 10_000 * per_tok * 0.25)) < 1e-12 and mixed > 0


def test_batch_savings_is_half_of_request_cost():
    cost = request_cost("claude-haiku-4-5", Usage(input_tokens=20_000, output_tokens=2_000))
    assert abs(batch_savings("claude-haiku-4-5", 20_000, 2_000) - cost * BATCH_DISCOUNT) < 1e-12


def test_request_cost_basic():
    usage = Usage(input_tokens=1_000_000, output_tokens=1_000_000)
    assert request_cost("claude-opus-4-8", usage) == 5.00 + 25.00
    assert request_cost("claude-haiku-4-5", usage) == 1.00 + 5.00


def test_cache_tokens_priced_with_multipliers():
    usage = Usage(cache_read_input_tokens=1_000_000, cache_creation_input_tokens=1_000_000)
    # opus input $5/MTok: read at 0.1x = $0.50, write at 1.25x = $6.25
    assert abs(request_cost("claude-opus-4-8", usage) - (0.50 + 6.25)) < 1e-9


def test_date_suffixed_model_resolves():
    assert resolve_price("claude-haiku-4-5-20251001") is not None
    assert ladder_tier("claude-haiku-4-5-20251001") == 0


def test_unknown_model_returns_none():
    assert request_cost("gpt-5", Usage(input_tokens=100)) is None
    assert ladder_tier("gpt-5") is None


def test_opus_to_haiku_saves_80_percent():
    usage = Usage(input_tokens=10_000, output_tokens=2_000)
    base = baseline_cost("claude-opus-4-8", usage)
    actual = request_cost("claude-haiku-4-5", usage)
    assert abs(1 - actual / base) - 0.80 < 0.01


def test_cache_trap_blocks_mid_conversation_switch():
    """The worked example from PRODUCT_DESIGN.md: 100K cached prefix on Opus,
    one expected remaining short turn — switching to Sonnet loses money."""
    benefit = net_switch_benefit(
        "claude-opus-4-8",
        "claude-sonnet-4-6",
        cached_prefix_tokens=100_000,
        expected_remaining_input_tokens=2_000,
        expected_remaining_output_tokens=1_000,
    )
    assert benefit < 0


def test_fresh_conversation_switch_pays():
    benefit = net_switch_benefit(
        "claude-opus-4-8",
        "claude-haiku-4-5",
        cached_prefix_tokens=0,
        expected_remaining_input_tokens=10_000,
        expected_remaining_output_tokens=5_000,
    )
    assert benefit > 0


def test_long_continuation_amortizes_cache_rewrite():
    # Same 100K prefix, but many large remaining turns: the switch pays.
    benefit = net_switch_benefit(
        "claude-opus-4-8",
        "claude-sonnet-4-6",
        cached_prefix_tokens=100_000,
        expected_remaining_input_tokens=500_000,
        expected_remaining_output_tokens=100_000,
    )
    assert benefit > 0
