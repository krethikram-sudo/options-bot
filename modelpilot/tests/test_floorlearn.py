"""Closed-loop per-customer floor learning (Track A)."""

import random

from modelpilot.floorlearn import captures_by_category, learn_floors
from modelpilot.pricing import Usage
from modelpilot.router import classify, recommend
from modelpilot.taxonomy import floor_tier


def _body(prompt, model="claude-fable-5"):
    return {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}


def _run(model, prompt):
    return f"out:{model}", Usage(input_tokens=50, output_tokens=100)


def test_floor_lowered_when_cheaper_tier_is_non_inferior():
    # summarization_long floors at sonnet (tier 1) globally.
    assert floor_tier("summarization_long") == 1
    caps = {"summarization_long": [f"summarize document {i}" for i in range(12)]}
    always_pass = lambda p, b, r: True
    out = learn_floors(caps, _run, always_pass, baseline="claude-fable-5",
                       rng=random.Random(1))
    assert out["category_floors"]["summarization_long"] == 0  # lowered to haiku


def test_floor_held_when_cheaper_tier_fails():
    caps = {"summarization_long": [f"summarize document {i}" for i in range(12)]}
    mostly_fail = lambda p, b, r: False
    out = learn_floors(caps, _run, mostly_fail, baseline="claude-fable-5",
                       rng=random.Random(1))
    assert "summarization_long" not in out["category_floors"]


def test_floor_held_without_enough_samples():
    caps = {"summarization_long": ["one prompt only"]}
    out = learn_floors(caps, _run, lambda *_: True, baseline="claude-fable-5",
                       min_samples=8)
    assert "summarization_long" not in out["category_floors"]


def test_already_cheapest_category_skipped():
    # classification already floors at haiku (0) — nothing to lower.
    caps = {"classification": [f"classify {i}" for i in range(12)]}
    out = learn_floors(caps, _run, lambda *_: True, baseline="claude-fable-5")
    assert "classification" not in out["category_floors"]


def test_learned_floor_changes_routing():
    # A short generic prompt classifies as `conversation` (global floor 1 -> sonnet).
    body = _body("Tell me a fun fact about sea otters")
    base = recommend(body)
    assert base.category == "conversation"
    assert base.recommended_model == "claude-sonnet-4-6"  # global floor
    # With a learned floor of 0 for conversation, it routes a tier cheaper.
    floors = {"conversation": 0}
    lowered = recommend(body, classifier=lambda f: classify(f, floors))
    assert lowered.recommended_model == "claude-haiku-4-5"


def test_captures_by_category_groups():
    caps = [{"category": "extraction", "prompt": "a"},
            {"category": "extraction", "prompt": "b"},
            {"category": "short_qa", "prompt": "c"}]
    grouped = captures_by_category(caps)
    assert grouped["extraction"] == ["a", "b"] and grouped["short_qa"] == ["c"]
