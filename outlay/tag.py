"""Explicit task-tagging — the primary, reliable attribution path.

Validation (see `VALIDATION.md`) showed passive branch→ticket inference can't be
the foundation: in detached-HEAD / remote-agent sessions `gitBranch` is just
`HEAD` (0% on our own data), and teams whose tracker is Jira/Linear rather than
GitHub Issues are undercounted by GitHub-issue parsing (Sentry's flagship repo
scored 30% vs 80–90% for its GitHub-issue-managed SDKs). So the robust design is:
**whatever launches the agent declares the ticket**, and attribution prefers that
explicit signal — falling back to inference only when no explicit tag exists.

`resolve_ticket` tries the most reliable signal first:

  1. explicit argument            — the caller passed the ticket outright
  2. `SCOPEPILOT_TICKET` env       — set by a wrapper / CI step / `tagged()` block
  3. git branch                    — parsed to a key (skipped when it's `HEAD`)
  4. CI PR head-ref env            — `GITHUB_HEAD_REF` etc. *recovers the real
                                     branch in detached-HEAD CI/web sessions*
  5. commit-message trailer        — `Ticket: PROJ-123` / `Closes #123`

This is what makes Outlay work regardless of branch discipline or which
tracker a team uses. The resulting `work_headers()` are what the ModelPilot
gateway's request observer reads (`x-modelpilot-work-*`) to attribute live
traffic at `call` fidelity.
"""

from __future__ import annotations

import os
import re
import subprocess
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Optional

from .join import TicketResolver

TICKET_ENV = "SCOPEPILOT_TICKET"

# Commit-message trailer: "Ticket: PROJ-123", "Refs PROJ-1", "Closes #45".
_TRAILER = re.compile(
    r"\b(?:ticket|refs?|fix(?:e[sd])?|close[sd]?|resolve[sd]?)\b\s*[:#]?\s*"
    r"([A-Za-z][A-Za-z0-9]+-\d+|#?\d+)",
    re.IGNORECASE,
)


@dataclass
class TicketContext:
    ticket_id: Optional[str]
    source: str   # explicit_arg | explicit_env | branch | ci | commit_trailer | none


def _git(args: list[str]) -> Optional[str]:
    try:
        out = subprocess.run(["git", *args], capture_output=True, text=True,
                             timeout=3, check=True)
        return out.stdout.strip() or None
    except Exception:  # noqa: BLE001 — git absent / not a repo / detached: best-effort
        return None


def current_branch() -> Optional[str]:
    return _git(["rev-parse", "--abbrev-ref", "HEAD"])


def current_commit_message() -> Optional[str]:
    return _git(["log", "-1", "--pretty=%B"])


def resolve_ticket(
    explicit: Optional[str] = None,
    *,
    branch: Optional[str] = None,
    commit_message: Optional[str] = None,
    env: Optional[dict] = None,
    resolver: Optional[TicketResolver] = None,
) -> TicketContext:
    """Resolve the active ticket from the most reliable signal available.

    Pass `branch` / `commit_message` / `env` explicitly to avoid touching git or
    the process environment (the resolution is then pure and testable).
    """
    env = os.environ if env is None else env
    resolver = resolver or TicketResolver()

    if explicit:
        return TicketContext(explicit, "explicit_arg")

    tagged_env = env.get(TICKET_ENV)
    if tagged_env:
        return TicketContext(tagged_env, "explicit_env")

    b = current_branch() if branch is None else branch
    if b and b != "HEAD":
        tid = resolver.from_branch(b)
        if tid:
            return TicketContext(tid, "branch")

    # Detached-HEAD recovery: CI/web runners expose the real PR branch via env
    # even when the checkout is a detached merge ref.
    head_ref = env.get("GITHUB_HEAD_REF") or env.get("CHANGE_BRANCH")
    if head_ref:
        tid = resolver.from_branch(head_ref)
        if tid:
            return TicketContext(tid, "ci")

    msg = current_commit_message() if commit_message is None else commit_message
    if msg:
        m = _TRAILER.search(msg)
        if m:
            tid = resolver.from_branch(m.group(1))
            if tid:
                return TicketContext(tid, "commit_trailer")

    return TicketContext(None, "none")


def work_headers(ticket: Optional[str] = None, branch: Optional[str] = None) -> dict:
    """The headers the ModelPilot gateway observer reads to attribute a live
    request (never forwarded upstream). Accepts a ticket id and/or branch."""
    h: dict[str, str] = {}
    if ticket:
        h["x-modelpilot-work-ticket"] = ticket
    if branch:
        h["x-modelpilot-work-branch"] = branch
    return h


def headers_for(ctx: TicketContext, branch: Optional[str] = None) -> dict:
    return work_headers(ctx.ticket_id, branch)


@contextmanager
def tagged(ticket: str, env: Optional[dict] = None):
    """Set the ambient ticket for a block of agent work so downstream
    `resolve_ticket()` / wrappers pick it up. Restores the prior value on exit."""
    target = os.environ if env is None else env
    prev = target.get(TICKET_ENV)
    target[TICKET_ENV] = ticket
    try:
        yield
    finally:
        if prev is None:
            target.pop(TICKET_ENV, None)
        else:
            target[TICKET_ENV] = prev
