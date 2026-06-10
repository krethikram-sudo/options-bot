from modelpilot.pricing import (
    Usage,
    baseline_cost,
    ladder_tier,
    net_switch_benefit,
    request_cost,
    resolve_price,
)


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
