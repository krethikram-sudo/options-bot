"""Cursor Admin API adapter.

Pulls token-level usage events from the Cursor Admin API:

    POST https://api.cursor.com/teams/filtered-usage-events

Auth is the team Admin API key sent via HTTP Basic (key as username, empty
password). The response carries per-event `userEmail`, `model`, and a
`tokenUsage` block (input/output/cache-read/cache-write).

⚠️ **Fidelity ceiling.** Cursor's events identify the *user* and *model* but not
the git branch, so this source reaches `team` fidelity (via user→team), not
ticket-level. It's valuable for per-engineer/per-team rollups and for catching
seats running premium models on trivial work — but the ticket join needs a
branch-bearing source (Claude Code transcripts, or a proxy).
"""

from __future__ import annotations

import base64
import os
from datetime import datetime
from typing import Optional

from ..models import UsageEvent
from ._http import Transport, post_json

EVENTS_URL = "https://api.cursor.com/teams/filtered-usage-events"


def _ts(value) -> datetime:
    if value is None:
        return datetime.utcnow()
    # Cursor timestamps are epoch milliseconds (often as strings).
    try:
        return datetime.utcfromtimestamp(int(value) / 1000.0)
    except (ValueError, TypeError):
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def parse_cursor_events(payload: dict) -> list[UsageEvent]:
    """Parse a Cursor filtered-usage-events response into `UsageEvent`s."""
    events: list[UsageEvent] = []
    rows = payload.get("usageEvents") or payload.get("data") or []
    for i, row in enumerate(rows):
        tok = row.get("tokenUsage") or {}
        events.append(
            UsageEvent(
                id=str(row.get("id") or f"cur-{i}"),
                provider="cursor",
                model=row.get("model") or row.get("modelIntent") or "claude-sonnet-4-6",
                ts=_ts(row.get("timestamp")),
                input_tokens=int(tok.get("inputTokens", 0) or 0),
                output_tokens=int(tok.get("outputTokens", 0) or 0),
                cache_read_tokens=int(tok.get("cacheReadTokens", 0) or 0),
                cache_write_tokens=int(tok.get("cacheWriteTokens", 0) or 0),
                user=row.get("userEmail"),
                # No branch/session/ticket exposed by Cursor's admin events.
            )
        )
    return events


class CursorAdminClient:
    """Paginating client for Cursor's filtered usage events."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = EVENTS_URL,
        transport: Optional[Transport] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("CURSOR_ADMIN_KEY", "")
        self.base_url = base_url
        self._transport = transport

    def _headers(self) -> dict:
        token = base64.b64encode(f"{self.api_key}:".encode()).decode()
        return {"authorization": f"Basic {token}"}

    def fetch(self, start_ms: int, end_ms: int, page_size: int = 1000) -> dict:
        """Fetch all pages, merging events into one payload."""
        merged: list[dict] = []
        page = 1
        while True:
            body = {
                "startDate": start_ms,
                "endDate": end_ms,
                "page": page,
                "pageSize": page_size,
            }
            resp = post_json(self.base_url, self._headers(), body, self._transport)
            rows = resp.get("usageEvents") or resp.get("data") or []
            merged.extend(rows)
            pagination = resp.get("pagination") or {}
            if pagination.get("hasNextPage") or (len(rows) == page_size):
                page += 1
                continue
            break
        return {"usageEvents": merged}

    def pull(self, start_ms: int, end_ms: int, **kw) -> list[UsageEvent]:
        return parse_cursor_events(self.fetch(start_ms, end_ms, **kw))
