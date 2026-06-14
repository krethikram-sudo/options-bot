"""Per-customer deployment profile (Track B)."""

import pytest

from modelpilot import pricing
from modelpilot.profile import (
    Profile,
    ProfileError,
    choose_allowed,
    compile_profile,
    load_profile,
)
from modelpilot.router import recommend


def _body(prompt, model="claude-fable-5"):
    return {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}


CLASSIFY = "Classify this review as positive or negative: 'broke in a day'"


def test_compile_validates_risk_and_min_model():
    with pytest.raises(ProfileError):
        compile_profile({"risk_tolerance": "yolo"})
    with pytest.raises(ProfileError):
        compile_profile({"min_model": "gpt-9"})


def test_risk_tolerance_maps_to_gate():
    assert compile_profile({"risk_tolerance": "conservative"}).confidence_gate() == 0.9
    assert compile_profile({"risk_tolerance": "aggressive"}).confidence_gate() == 0.65
    assert compile_profile({"gate": 0.77}).confidence_gate() == 0.77  # explicit wins


def test_allows_blocklist_and_allowlist():
    p = compile_profile({"blocked_models": ["claude-haiku-4-5"]})
    assert not p.allows("claude-haiku-4-5") and p.allows("claude-sonnet-4-6")
    p2 = compile_profile({"allowed_models": ["claude-opus-4-8", "claude-sonnet-4-6"]})
    assert p2.allows("claude-sonnet-4-6") and not p2.allows("claude-haiku-4-5")


def test_blocked_model_falls_back_to_next_allowed_tier():
    # classification floors at haiku (0); blocking haiku should route sonnet, not stay.
    p = compile_profile({"blocked_models": ["claude-haiku-4-5"]})
    rec = recommend(_body(CLASSIFY), profile=p)
    assert rec.action == "switch"
    assert rec.recommended_model == "claude-sonnet-4-6"
    assert "profile raised floor" in rec.rationale


def test_min_model_enforces_quality_floor():
    p = compile_profile({"min_model": "claude-sonnet-4-6"})
    rec = recommend(_body(CLASSIFY), profile=p)
    assert rec.recommended_model == "claude-sonnet-4-6"  # not haiku


def test_no_permitted_model_stays():
    # allow only the baseline-tier model -> nothing cheaper is permitted -> stay.
    p = compile_profile({"allowed_models": ["claude-fable-5"]})
    rec = recommend(_body(CLASSIFY), profile=p)
    assert rec.action == "stay"
    assert "no profile-permitted model" in rec.rationale


def test_choose_allowed_walks_up():
    p = compile_profile({"blocked_models": ["claude-haiku-4-5"]})
    model, tier = choose_allowed(0, 3, p)  # cheapest is haiku(0) but blocked
    assert model == "claude-sonnet-4-6" and tier == 1


def test_price_overrides_apply_to_global_table():
    saved = dict(pricing.PRICES)
    try:
        p = compile_profile({"price_overrides": {"claude-sonnet-4-6": {"input": 1.0, "output": 2.0}}})
        pricing.apply_overrides(p.price_overrides)
        price = pricing.resolve_price("claude-sonnet-4-6")
        assert price.input_per_mtok == 1.0 and price.output_per_mtok == 2.0
    finally:
        pricing.PRICES.clear()
        pricing.PRICES.update(saved)


def test_load_profile_from_policy_object():
    p = load_profile({"profile": {"min_model": "claude-haiku-4-5", "risk_tolerance": "aggressive"}})
    assert p.min_model == "claude-haiku-4-5" and p.confidence_gate() == 0.65
    assert load_profile("").is_active() is False
