"""Client-side tuning-proposal submission (Track A floors / Track C rules)."""

import random

from modelpilot import proposals
from modelpilot.floorlearn import learn_floors


def test_learn_floors_emits_review_details():
    caps = {"summarization_long": [f"summarize doc {i}" for i in range(12)]}
    out = learn_floors(caps, lambda m, p: ("x", None), lambda p, b, r: True,
                       baseline="claude-fable-5", rng=random.Random(1))
    d = out["details"]["summarization_long"]
    assert d["current_tier"] == 1 and d["proposed_tier"] == 0
    assert d["lowered"] is True and d["samples"] >= 8 and d["non_inferior_rate"] == 1.0


def test_submit_floor_details_only_lowered():
    sent = []
    details = {
        "summarization_long": {"current_tier": 1, "proposed_tier": 0, "samples": 12,
                               "non_inferior_rate": 0.95, "lowered": True},
        "debugging": {"current_tier": 2, "proposed_tier": 1, "samples": 9,
                      "non_inferior_rate": 0.4, "lowered": False},
    }
    n = proposals.submit_floor_details(details, console_url="http://c", deployment_id="dep_x",
                                       post_fn=sent.append)
    assert n == 1
    p = sent[0]
    assert p["kind"] == "floor" and p["category"] == "summarization_long"
    assert p["payload"]["proposed_tier"] == 0 and p["stats"]["samples"] == 12
    assert "prompt" not in p and "messages" not in p  # aggregate only


def test_submit_rules_requires_category():
    sent = []
    rules = [{"name": "invoices", "any": ["invoice"], "category": "extraction", "_seen_in_pct": 12},
             {"name": "blank", "any": ["x"], "category": ""}]  # skipped: no category
    n = proposals.submit_rules(rules, console_url="http://c", deployment_id="dep_x",
                               post_fn=sent.append)
    assert n == 1 and sent[0]["payload"]["name"] == "invoices"
    assert sent[0]["kind"] == "rule" and sent[0]["category"] == "extraction"


def test_submit_noop_without_config():
    assert proposals.submit_floor("c", 1, 0, 10, 0.9, console_url="", deployment_id="") is False
