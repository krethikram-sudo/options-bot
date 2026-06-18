"""Anthropic usage adapter.

Accepts the shape teams actually have: a list of per-call usage records (the
`usage` object returned on every `/v1/messages` response, or rows from the
admin/usage export), each carrying the four token counts plus whatever
attribution metadata the caller stamped.

Token field naming follows Anthropic's own response object:
  - `input_tokens`               → uncached input
  - `output_tokens`              → output
  - `cache_read_input_tokens`    → served from cache (~0.1× input)
  - `cache_creation_input_tokens`→ written to cache (~1.25× input)

Attribution signals live under an optional `metadata` object — this is exactly
the channel a Outlay proxy (or a disciplined Claude Code / Cursor wrapper)
would populate (`branch`, `user`, `session_id`, `ticket`, `api_key_id`). When
absent, the join simply degrades to a lower fidelity tier.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Union

from ..models import UsageEvent


def _ts(value: Union[str, int, float, None]) -> datetime:
    if value is None:
        return datetime.utcnow()
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    # ISO-8601, tolerate trailing Z.
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def parse_anthropic_usage(data: Union[str, Path, list, dict]) -> list[UsageEvent]:
    """Parse Anthropic usage JSON into `UsageEvent`s.

    `data` may be a path, a JSON string, an already-loaded list, or a dict with
    a top-level `records`/`data` list.
    """
    if isinstance(data, (str, Path)) and not _looks_like_json(data):
        data = json.loads(Path(data).read_text())
    elif isinstance(data, str):
        data = json.loads(data)

    if isinstance(data, dict):
        records = data.get("records") or data.get("data") or []
    else:
        records = data

    events: list[UsageEvent] = []
    for i, rec in enumerate(records):
        usage = rec.get("usage", rec)  # support flat or nested usage
        meta = rec.get("metadata", {}) or {}
        events.append(
            UsageEvent(
                id=str(rec.get("id", f"evt-{i}")),
                provider="anthropic",
                model=rec.get("model", "claude-sonnet-4-6"),
                ts=_ts(rec.get("timestamp") or rec.get("ts")),
                input_tokens=int(usage.get("input_tokens", 0) or 0),
                output_tokens=int(usage.get("output_tokens", 0) or 0),
                cache_read_tokens=int(usage.get("cache_read_input_tokens", 0) or 0),
                cache_write_tokens=int(
                    usage.get("cache_creation_input_tokens", 0) or 0
                ),
                api_key_id=meta.get("api_key_id") or rec.get("api_key_id"),
                user=meta.get("user"),
                branch=meta.get("branch"),
                session_id=meta.get("session_id"),
                explicit_ticket=meta.get("ticket"),
            )
        )
    return events


def _looks_like_json(s: Union[str, Path]) -> bool:
    text = str(s).lstrip()
    return text.startswith("{") or text.startswith("[")
