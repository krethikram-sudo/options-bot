"""Per-customer classification rules — adapt routing to a customer's own domain.

The global heuristic classifier (`router.classify`) is general-purpose. Every
customer's traffic has its own shape: a contracts SaaS sees "redline this
clause", a support tool sees "draft a reply to this ticket". Left to the global
classifier, domain-specific phrasing often lands in the conservative
`conversation` / `unknown` catch-alls and never gets optimized — savings leak.

A rule maps a lexical signal in the prompt to a category (and an optional tier
floor), so a customer's traffic is classified by patterns drawn from THEIR
domain. Rules come from two places:

  - hand-authored during onboarding ("anything mentioning 'invoice' is
    extraction → haiku"), the most direct form of customization; and
  - proposed by `modelpilot learn-rules`, which mines catch-all captures for
    recurring topics and writes a rules scaffold.

Safety: a rule only sets the *category* and an optional floor tier. The
economics veto, the never-route-above-the-requested-model rule, the
follow-up/session-difficulty reconciliation, and the structured-output / tool
guard in `router.recommend` all still apply. A rule can make routing more
precise; it cannot bypass the quality guards.

Rule file format (JSON) — a list, or an object with a "category_rules" list:

    [
      {"name": "invoices", "any": ["invoice", "po number"],
       "category": "extraction", "max_tier": 0},
      {"name": "ticket-replies", "regex": ["draft (a )?(reply|response) to"],
       "category": "rewrite_format"}
    ]
"""

import json
import re
from dataclasses import dataclass, field

from .router import classify as _global_classify
from .router import reconcile_followup
from .taxonomy import CATEGORIES, floor_tier


@dataclass
class Rule:
    name: str
    category: str
    any: list[str] = field(default_factory=list)       # substrings (case-insensitive)
    regex: list[str] = field(default_factory=list)      # regex patterns (case-insensitive)
    max_tier: int | None = None                         # explicit floor; default floor_tier(category)
    confidence: float = 0.85
    _compiled: list = field(default_factory=list, repr=False)

    def matches(self, prompt: str) -> bool:
        low = prompt.lower()
        if any(s.lower() in low for s in self.any):
            return True
        return any(p.search(prompt) for p in self._compiled)


class RuleError(ValueError):
    pass


def compile_rules(raw: list[dict]) -> list[Rule]:
    """Validate and compile raw rule dicts into Rule objects."""
    rules = []
    for i, r in enumerate(raw):
        name = r.get("name") or f"rule-{i}"
        category = r.get("category")
        if category not in CATEGORIES:
            raise RuleError(
                f"rule '{name}': category {category!r} is not a known category "
                f"({', '.join(sorted(CATEGORIES))})")
        if not r.get("any") and not r.get("regex"):
            raise RuleError(f"rule '{name}': needs at least one 'any' or 'regex' signal")
        rule = Rule(
            name=name,
            category=category,
            any=list(r.get("any") or []),
            regex=list(r.get("regex") or []),
            max_tier=r.get("max_tier"),
            confidence=float(r.get("confidence", 0.85)),
        )
        rule._compiled = [re.compile(p, re.IGNORECASE) for p in rule.regex]
        rules.append(rule)
    return rules


def load_rules(source) -> list[Rule]:
    """Load rules from a path, a dict (policy.json), or a list. None/missing -> []."""
    if not source:
        return []
    if isinstance(source, str):
        try:
            with open(source) as f:
                data = json.load(f)
        except (OSError, ValueError):
            return []
    else:
        data = source
    if isinstance(data, dict):
        data = data.get("category_rules") or []
    if not isinstance(data, list):
        return []
    return compile_rules(data)


def match(prompt: str, rules: list[Rule]) -> Rule | None:
    """First rule whose signals match the prompt, or None."""
    for rule in rules:
        if rule.matches(prompt):
            return rule
    return None


def rule_classifier(rules: list[Rule], base=_global_classify):
    """A classifier(features) that applies customer rules first, then falls back
    to the global classifier. Rule hits still go through follow-up/session
    reconciliation so a cheap rule can't strand a hard follow-up on a weak model.
    """
    def classify_with_rules(features: dict):
        prompt = features.get("prompt", "")
        rule = match(prompt, rules) if prompt else None
        if rule is None:
            return base(features)
        tier = rule.max_tier if rule.max_tier is not None else floor_tier(rule.category)
        return reconcile_followup(
            features, rule.category, tier, rule.confidence,
            f"customer rule '{rule.name}' -> {rule.category}")
    return classify_with_rules
