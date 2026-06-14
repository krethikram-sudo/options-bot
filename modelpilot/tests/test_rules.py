"""Per-customer classification rules (feature C)."""

import pytest

from modelpilot.learn_rules import build_scaffold, mine_clusters
from modelpilot.router import recommend
from modelpilot.rules import RuleError, compile_rules, load_rules, rule_classifier


def _body(prompt, model="claude-fable-5", **extra):
    b = {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}
    b.update(extra)
    return b


def test_compile_rejects_unknown_category():
    with pytest.raises(RuleError):
        compile_rules([{"name": "x", "any": ["foo"], "category": "not-a-category"}])


def test_compile_rejects_signal_less_rule():
    with pytest.raises(RuleError):
        compile_rules([{"name": "x", "category": "extraction"}])


def test_rule_overrides_catchall_and_routes_cheaper():
    # "pull the totals from this invoice" is domain phrasing the global router
    # drops into a catch-all; a customer rule makes it extraction -> haiku.
    rules = compile_rules([{"name": "invoices", "any": ["invoice"],
                            "category": "extraction", "max_tier": 0}])
    clf = rule_classifier(rules)
    rec = recommend(_body("Reconcile the line items on this invoice for me"), classifier=clf)
    assert rec.category == "extraction"
    assert rec.recommended_model == "claude-haiku-4-5"
    assert "customer rule 'invoices'" in rec.rationale


def test_rule_falls_back_to_global_when_no_match():
    rules = compile_rules([{"name": "invoices", "any": ["invoice"], "category": "extraction"}])
    clf = rule_classifier(rules)
    rec = recommend(_body("Prove that the sequence converges and derive its limit"),
                    classifier=clf)
    assert rec.category == "math_logic"  # global classifier still in charge


def test_rule_cannot_bypass_structured_output_guard():
    # A rule asking for haiku on a request with an output schema must still be
    # floored to sonnet by recommend's universal guard.
    rules = compile_rules([{"name": "invoices", "any": ["invoice"],
                            "category": "extraction", "max_tier": 0}])
    clf = rule_classifier(rules)
    body = _body("extract fields from this invoice",
                 output_config={"format": {"type": "json_schema", "schema": {}}})
    rec = recommend(body, classifier=clf)
    assert rec.recommended_model == "claude-sonnet-4-6"
    assert "floor sonnet" in rec.rationale


def test_load_rules_from_policy_dict():
    rules = load_rules({"category_rules": [{"name": "r", "any": ["foo"], "category": "short_qa"}]})
    assert len(rules) == 1 and rules[0].category == "short_qa"
    assert load_rules("") == []


# --- learner ---------------------------------------------------------------

def test_mine_clusters_surfaces_recurring_catchall_topic():
    caps = [{"category": "conversation", "prompt": f"draft a reply to this support ticket #{i}"}
            for i in range(6)]
    caps += [{"category": "unknown", "prompt": "something totally different and unique here"}]
    clusters = mine_clusters(caps, min_docs=3)
    phrases = {c["phrase"] for c in clusters}
    assert any("ticket" in p or "reply" in p or "support" in p for p in phrases)
    scaffold = build_scaffold(clusters)
    assert scaffold["category_rules"][0]["category"] == ""  # operator fills it in
