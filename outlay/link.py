"""Cross-source linkage — recover the branch→ticket link customers don't encode.

The make-or-break number is ticket coverage, and it hinges on resolving each
usage event's git branch to a ticket. But most teams *don't* put ticket ids in
branch names (`alice/quick-fix`, `feat/new-billing`, trunk-based) — so branch
regex alone leaves coverage low.

The fix doesn't ask anyone to rename branches. It harvests the link from data the
team already produces: a **pull request** almost always references the issue it
closes ("Closes #123", "Fixes PROJ-45"), and **commit messages** often carry the
key too. This module parses those closing references and stamps the PR's head
branch onto the work item it closes — so the join engine's existing branch path
(`_by_branch`) resolves every event on that branch to the right ticket, at BRANCH
fidelity, with zero behavior change.
"""

from __future__ import annotations

import re
from typing import Iterable, Optional

from .models import WorkItem

# GitHub-style closing keywords (close/closes/closed/fix/fixes/fixed/resolve/...)
# followed by an issue reference: `#123`, a Jira/Linear key `PROJ-45`, or `GH-7`.
_CLOSING_RE = re.compile(
    r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\b\s*:?\s+"
    r"(#\d+|[A-Za-z][A-Za-z0-9]+-\d+)",
    re.IGNORECASE,
)
# A standalone ticket key anywhere in text (commit-message style: "PROJ-12: ...").
_KEY_RE = re.compile(r"\b([A-Z][A-Z0-9]+-\d+)\b")


def _canon(ref: str, source: str = "github") -> Optional[str]:
    """Canonicalize a raw reference to the same key space the resolver/ingest use:
    `#123` → `GH-123` (or LIN/PROJ per source), `proj-45` → `PROJ-45`."""
    ref = ref.strip()
    if not ref:
        return None
    if ref.startswith("#"):
        n = ref[1:]
        if not n.isdigit():
            return None
        prefix = {"github": "GH", "linear": "LIN", "jira": "PROJ"}.get(source, "GH")
        return f"{prefix}-{n}"
    return ref.upper()


def parse_closing_refs(text: Optional[str], source: str = "github",
                       include_bare_keys: bool = True) -> list[str]:
    """Ticket ids referenced as closed/fixed in `text` (a PR body/title or commit
    message). With `include_bare_keys`, also picks up a standalone `PROJ-12` key
    (common in commit subjects) — but never a bare `#123`, which is too noisy
    without a closing keyword. Order-preserving, de-duplicated."""
    if not text:
        return []
    out: list[str] = []
    seen: set[str] = set()

    def _add(raw: str) -> None:
        tid = _canon(raw, source)
        if tid and tid not in seen:
            seen.add(tid)
            out.append(tid)

    for m in _CLOSING_RE.finditer(text):
        _add(m.group(1))
    if include_bare_keys:
        for m in _KEY_RE.finditer(text):
            _add(m.group(1))
    return out


def link_branches(work_items: list[WorkItem], prs: Iterable[dict],
                  source: str = "github") -> list[WorkItem]:
    """Stamp each PR's head branch onto the work item(s) it closes, so a usage
    event on that branch resolves to the ticket even though the branch name never
    mentions it.

    `prs`: dicts with a head branch (`head_ref`/`branch`), an optional explicit
    `closes` list of ticket ids, and `title`/`body`/`message` text to scan. Only
    fills a work item that doesn't already have a branch (an explicitly-recorded
    branch wins). Mutates and returns `work_items`."""
    by_ticket = {wi.ticket_id: wi for wi in work_items}
    for pr in prs:
        if not isinstance(pr, dict):
            continue
        branch = pr.get("head_ref") or pr.get("branch") or pr.get("head")
        if not branch:
            continue
        refs: list[str] = []
        for c in (pr.get("closes") or []):
            t = _canon(str(c), source)
            if t:
                refs.append(t)
        text = "\n".join(str(pr.get(k, "")) for k in ("title", "body", "message"))
        refs += parse_closing_refs(text, source)
        number = pr.get("number") or pr.get("pr_number")
        for tid in refs:
            wi = by_ticket.get(tid)
            if wi and not wi.branch:
                wi.branch = branch
                if number is not None and wi.pr_number is None:
                    try:
                        wi.pr_number = int(number)
                    except (TypeError, ValueError):
                        pass
    return work_items
