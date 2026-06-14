"""Every shipped starter pack must be valid and route as intended."""

import json
from pathlib import Path

import pytest

from modelpilot.profile import load_profile
from modelpilot.router import recommend
from modelpilot.rules import load_rules, rule_classifier

def _find_packs() -> Path:
    """Locate packs/ regardless of layout (source vs published/migrated repo)."""
    for parent in Path(__file__).resolve().parents:
        cand = parent / "packs"
        if cand.is_dir():
            return cand
    return Path("packs")


PACKS_DIR = _find_packs()
PACKS = sorted(PACKS_DIR.glob("*.json"))


def _body(prompt, model="claude-opus-4-8"):
    return {"model": model, "max_tokens": 1024, "messages": [{"role": "user", "content": prompt}]}


def test_packs_exist():
    assert PACKS, "no starter packs found"


@pytest.mark.parametrize("pack", PACKS, ids=lambda p: p.name)
def test_pack_is_valid(pack):
    data = json.loads(pack.read_text())
    rules = load_rules(data)              # compiles category_rules; raises on bad category
    assert rules, f"{pack.name} has no usable rules"
    load_profile(data)                    # validates any embedded profile (raises on bad values)
    for g in (data.get("category_gates") or {}).values():
        assert 0.0 <= float(g) <= 1.0


def test_doc_extraction_routes_invoice_to_haiku():
    data = json.loads((PACKS_DIR / "doc-extraction.json").read_text())
    clf = rule_classifier(load_rules(data))
    rec = recommend(_body("Pull the fields from this invoice and return them."), classifier=clf)
    assert rec.recommended_model == "claude-haiku-4-5"


def test_legal_pack_never_below_sonnet():
    # Conservative legal pack: a redline routes to Sonnet, never Haiku.
    data = json.loads((PACKS_DIR / "legal.json").read_text())
    clf = rule_classifier(load_rules(data))
    rec = recommend(_body("Redline this clause to make this mutual."), classifier=clf)
    assert rec.recommended_model == "claude-sonnet-4-6"
    # and the embedded profile enforces a Sonnet floor
    prof = load_profile(data)
    assert prof.min_model == "claude-sonnet-4-6" and prof.min_tier() == 1


def test_healthcare_pack_is_regulated():
    data = json.loads((PACKS_DIR / "healthcare.json").read_text())
    prof = load_profile(data)
    assert prof.min_tier() >= 1                      # never Haiku
    assert prof.confidence_gate() == 0.8             # conservative risk tolerance
