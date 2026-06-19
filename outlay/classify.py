"""Task-class classification.

Cost is learned and routing is recommended per *class*, not per ticket — a
single unseen ticket is as unpredictable to cost as it is to estimate in hours,
but the distribution over "bugfix tickets in this repo" is stable and useful.

P0 uses cheap, legible heuristics: planner labels first (highest signal), then
the title/description **text** (so planned work classifies before any branch or
diff exists — the basis for estimating future Jira features), then branch-name
verbs, then diff size as a fallback. Deliberately a pure function of the work
item so it's trivially testable and explainable to a skeptical eng lead.
"""

from __future__ import annotations

import re

from .models import TaskClass, WorkItem

# Label substrings → class. First matching class in this order wins.
_LABEL_RULES: list[tuple[TaskClass, tuple[str, ...]]] = [
    (TaskClass.BUGFIX, ("bug", "fix", "defect", "regression", "hotfix")),
    (TaskClass.TEST, ("test", "qa", "coverage", "e2e")),
    (TaskClass.REFACTOR, ("refactor", "cleanup", "tech-debt", "techdebt", "debt")),
    (TaskClass.CHORE, ("chore", "docs", "documentation", "deps", "dependencies",
                       "ci", "build", "config", "style", "formatting")),
    (TaskClass.FEATURE, ("feature", "enhancement", "feat", "story", "epic")),
]

# Title/description keyword → class, word-boundary matched. Order matters:
# narrower intents (bug/test/refactor/chore) win over the broad feature verbs.
_TEXT_RULES: list[tuple[TaskClass, str]] = [
    (TaskClass.BUGFIX, r"\b(fix|fixes|bug|bugs|crash|crashes|error|errors|broken|"
                       r"regression|hotfix|defect|patch|incorrect|fails?|failing)\b"),
    (TaskClass.TEST, r"\b(test|tests|testing|coverage|e2e|qa|fixture|fixtures)\b"),
    (TaskClass.REFACTOR, r"\b(refactor|refactors|cleanup|clean[- ]up|rewrite|"
                         r"restructure|migrate|migration|tech[- ]debt|deprecate)\b"),
    (TaskClass.CHORE, r"\b(docs?|documentation|deps|dependency|dependencies|upgrade|"
                      r"bump|ci|cd|config|configure|lint|format|formatting|chore|readme)\b"),
    (TaskClass.FEATURE, r"\b(add|adds|build|implement|implements|create|creates|support|"
                        r"introduce|enable|new|feature|integrate|integration)\b"),
]
_TEXT_PATTERNS = [(cls, re.compile(rx, re.IGNORECASE)) for cls, rx in _TEXT_RULES]

_BRANCH_VERBS: list[tuple[TaskClass, str]] = [
    (TaskClass.BUGFIX, r"(?:^|[/_-])(fix|bug|hotfix)(?:[/_-]|$)"),
    (TaskClass.FEATURE, r"(?:^|[/_-])(feat|feature)(?:[/_-]|$)"),
    (TaskClass.REFACTOR, r"(?:^|[/_-])(refactor|cleanup|chore-refactor)(?:[/_-]|$)"),
    (TaskClass.TEST, r"(?:^|[/_-])(test|tests)(?:[/_-]|$)"),
    (TaskClass.CHORE, r"(?:^|[/_-])(chore|docs|deps|ci)(?:[/_-]|$)"),
]

# Diff-size fallback thresholds (added+removed lines).
_LARGE_DIFF = 400


def classify(item: WorkItem) -> TaskClass:
    """Best-effort task class for a work item.

    Labels (highest signal) → title/description text → branch verbs → diff size.
    The text tier is what lets a *planned* item — a Jira feature with only a
    title and a description, no branch or diff yet — still be classified, which
    is the foundation for estimating future work (see `estimate.py`).
    """
    labels = " ".join(item.labels).lower()
    for cls, needles in _LABEL_RULES:
        if any(n in labels for n in needles):
            return cls

    text = f"{item.title} {item.description}".strip()
    if text:
        for cls, pat in _TEXT_PATTERNS:
            if pat.search(text):
                return cls

    branch = (item.branch or "").lower()
    for cls, rx in _BRANCH_VERBS:
        if re.search(rx, branch):
            return cls

    # Diff-size fallback: a big change is most likely a feature; a tiny one a fix.
    if item.diff_size:
        return TaskClass.FEATURE if item.diff_size >= _LARGE_DIFF else TaskClass.BUGFIX

    return TaskClass.UNKNOWN
