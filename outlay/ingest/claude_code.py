"""Claude Code transcript adapter — the high-fidelity source.

Claude Code writes a JSONL transcript per session under
`~/.claude/projects/<slug>/<session-id>.jsonl`. Crucially, **every entry carries
`gitBranch`, `cwd`, and `sessionId`**, and assistant entries carry
`message.model` + `message.usage`. That branch field is exactly what the join
engine needs to reach a ticket — so unlike the aggregated Admin/Cursor sources,
Claude Code data lands at `branch` fidelity (ticket-level).

This is why the architecture treats per-call coding-tool telemetry as the
primary attribution source and provider invoices as the reconciliation backstop:
only the former sees the git context the work actually happened in.

Engineer identity isn't reliably in the transcript, so `user` is supplied by the
caller (e.g. mapped from the machine/seat, or the directory owner).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Union

from ..models import UsageEvent


def _ts(value) -> datetime:
    if value is None:
        return datetime.utcnow()
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def _iter_lines(source: Union[str, Path]) -> Iterable[str]:
    text = source if (isinstance(source, str) and "\n" in source) else Path(source).read_text()
    for line in text.splitlines():
        line = line.strip()
        if line:
            yield line


def parse_claude_code_transcript(
    source: Union[str, Path],
    user: Optional[str] = None,
) -> list[UsageEvent]:
    """Parse one Claude Code JSONL transcript (path or raw text) into events.

    Only assistant entries that carry a `message.usage` block are billable; user
    turns and tool results are skipped.
    """
    events: list[UsageEvent] = []
    for i, raw in enumerate(_iter_lines(source)):
        try:
            entry = json.loads(raw)
        except json.JSONDecodeError:
            continue
        msg = entry.get("message") or {}
        usage = msg.get("usage")
        if entry.get("type") != "assistant" or not usage:
            continue
        events.append(
            UsageEvent(
                id=str(msg.get("id") or entry.get("uuid") or f"cc-{i}"),
                provider="anthropic",
                model=msg.get("model", "claude-sonnet-4-6"),
                ts=_ts(entry.get("timestamp")),
                input_tokens=int(usage.get("input_tokens", 0) or 0),
                output_tokens=int(usage.get("output_tokens", 0) or 0),
                cache_read_tokens=int(usage.get("cache_read_input_tokens", 0) or 0),
                cache_write_tokens=int(usage.get("cache_creation_input_tokens", 0) or 0),
                user=user,
                branch=entry.get("gitBranch") or None,
                session_id=entry.get("sessionId"),
            )
        )
    return events


def parse_claude_code_dir(
    root: Union[str, Path],
    user_for_path: Optional[dict[str, str]] = None,
) -> list[UsageEvent]:
    """Walk a `~/.claude/projects` tree and parse every `*.jsonl` transcript.

    `user_for_path` optionally maps a project-slug substring → engineer email so
    multi-developer log collections attribute to the right person.
    """
    root = Path(root)
    out: list[UsageEvent] = []
    for jsonl in sorted(root.rglob("*.jsonl")):
        user = None
        if user_for_path:
            for needle, email in user_for_path.items():
                if needle in str(jsonl):
                    user = email
                    break
        out.extend(parse_claude_code_transcript(jsonl, user=user))
    return out
