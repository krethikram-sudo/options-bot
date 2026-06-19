"""Estimate enrichment from business requirements + design docs.

Story points are the cleanest size signal, but many teams don't point their
backlog — and a one-line ticket title under-determines compute cost. When a
planned item carries its **business requirements and design docs**, we read that
text for legible scope signals — acceptance criteria, external integrations,
hard/architectural work, overall breadth — and place the item within its class's
*own* historical cost distribution (S → lower, XL → upper).

This is a transparent heuristic, not a learned model, and it's honest about it:
the estimate stays inside the team's observed range for that work type, the band
widens versus a points-calibrated estimate, and confidence is capped at "medium"
until the customer's own backtest validates it. More input → tighter estimate.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Acceptance-criteria-ish lines: bullets, numbered items, Gherkin, modal verbs.
_AC = re.compile(
    r"(?mi)^\s*(?:[-*•]|\d+[.)]|ac\d|given\b|when\b|then\b|must\b|shall\b|should\b)")
# External integrations / surfaces — each distinct one adds scope.
_INTEG = re.compile(
    r"(?i)\b(integrat\w+|webhook|oauth|saml|sso|scim|stripe|s3|kafka|queue|"
    r"third[- ]party|external|provider|connector|sdk|graphql|grpc)\b")
# Hard / architectural work that reliably inflates effort.
_HARD = re.compile(
    r"(?i)\b(migrat\w+|backfill|re[- ]?architect|rewrite|new service|new system|"
    r"schema change|data model|breaking change|rollout|feature flag|"
    r"concurrency|distributed|idempoten\w+|encryption|multi[- ]tenant)\b")


@dataclass
class Scope:
    acceptance_criteria: int
    integrations: int
    hard_signals: int
    words: int
    tier: str          # "S" | "M" | "L" | "XL"


def scope_of(text: str | None) -> Scope | None:
    """Score requirements/design text into a complexity tier, or None if too thin.

    Returns None when there isn't enough text to say anything — the estimator then
    falls back to the flat class mean rather than pretending to size it.
    """
    text = (text or "").strip()
    words = len(text.split())
    ac = len(_AC.findall(text))
    integ = len(set(m.lower() for m in _INTEG.findall(text)))
    hard = len(set(m.lower() for m in _HARD.findall(text)))

    if words < 12 and ac == 0 and integ == 0 and hard == 0:
        return None  # nothing to ground a complexity read on

    # Transparent additive scope score.
    score = (
        min(ac, 8) * 0.06        # detailed acceptance criteria
        + min(integ, 5) * 0.12   # each external integration
        + min(hard, 5) * 0.16    # each hard/architectural signal
        + min(words // 120, 4) * 0.08  # overall breadth, length-bucketed
    )
    tier = "S" if score < 0.18 else "M" if score < 0.55 else "L" if score < 0.95 else "XL"
    return Scope(ac, integ, hard, words, tier)
