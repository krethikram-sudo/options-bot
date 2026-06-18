"""Task-class classification.

Cost is learned and routing is recommended per *class*, not per ticket — a
single unseen ticket is as unpredictable to cost as it is to estimate in hours,
but the distribution over "bugfix tickets in this repo" is stable and useful.

P0 uses cheap, legible heuristics: planner labels first (highest signal),
then branch-name verbs, then diff size as a fallback. Deliberately a pure
function of the work item so it's trivially testable and explainable to a
skeptical eng lead. A learned classifier is a Phase-2 upgrade, not a P0 need.
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
    """Best-effort task class for a work item."""
    labels = " ".join(item.labels).lower()
    for cls, needles in _LABEL_RULES:
        if any(n in labels for n in needles):
            return cls

    branch = (item.branch or "").lower()
    for cls, rx in _BRANCH_VERBS:
        if re.search(rx, branch):
            return cls

    # Diff-size fallback: a big change is most likely a feature; a tiny one a fix.
    if item.diff_size:
        return TaskClass.FEATURE if item.diff_size >= _LARGE_DIFF else TaskClass.BUGFIX

    return TaskClass.UNKNOWN
