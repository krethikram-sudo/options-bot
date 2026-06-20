"""Cost normalization: the cache-token split is the thing naive trackers get
wrong, so it gets the most coverage."""

from datetime import datetime

from outlay.models import UsageEvent
from outlay.pricing import cost_usd, model_is_known, rate_for


def _ev(model="claude-sonnet-4-6", **tok):
    return UsageEvent(id="x", provider="anthropic", model=model, ts=datetime(2026, 6, 1), **tok)


def test_base_input_output_cost():
    # 1M input @ $3 + 1M output @ $15 on Sonnet = $18.
    c = cost_usd(_ev(input_tokens=1_000_000, output_tokens=1_000_000))
    assert abs(c - 18.0) < 1e-9


def test_cache_read_is_one_tenth_input():
    # 1M cache-read tokens on Sonnet ($3 input) = $0.30, not $3.
    c = cost_usd(_ev(cache_read_tokens=1_000_000))
    assert abs(c - 0.30) < 1e-9


def test_cache_write_is_1_25x_input():
    c = cost_usd(_ev(cache_write_tokens=1_000_000))
    assert abs(c - 3.75) < 1e-9


def test_collapsing_cache_into_input_overstates_5x_plus():
    # A cache-heavy turn: tiny fresh input, huge cache read.
    ev = _ev(input_tokens=10_000, cache_read_tokens=1_000_000)
    correct = cost_usd(ev)
    naive = (10_000 + 1_000_000) * 3.0 / 1_000_000  # all-as-input
    assert naive / correct > 5.0


def test_rate_fallback_and_normalization():
    assert rate_for("claude-opus-4-8").tier == 2
    # Bedrock-style prefix + unknown date suffix still resolve.
    assert rate_for("anthropic.claude-opus-4-8").tier == 2
    assert rate_for("totally-unknown-model").model == "claude-sonnet-4-6"


def test_model_is_known_flags_fallback_pricing():
    # exact / drift-tolerant ids are known...
    assert model_is_known("claude-opus-4-8")
    assert model_is_known("anthropic.claude-opus-4-8-20260101")
    assert model_is_known("gpt-4o")
    # ...future/foreign ids are NOT — so the report can surface estimated pricing
    assert not model_is_known("claude-opus-5-1")
    assert not model_is_known("gpt-5")
    assert not model_is_known("gemini-2.5-pro")
    assert not model_is_known("")


def test_negative_token_counts_clamp_to_zero():
    # nonsensical negative data must never *reduce* the bill
    assert cost_usd(_ev(model="claude-opus-4-8", input_tokens=-1_000_000, output_tokens=1_000_000)) == 25.0
    assert cost_usd(_ev(model="claude-opus-4-8", input_tokens=-5, output_tokens=-5)) == 0.0
