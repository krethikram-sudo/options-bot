"""Anthropic Admin Usage API puller — live ingestion to replace the fixture.

Hits the organization Usage Report for Messages:

    GET https://api.anthropic.com/v1/organizations/usage_report/messages

Auth is an **Admin** API key (`sk-ant-admin...`), distinct from a normal
inference key, sent as `x-api-key` with `anthropic-version`. The report returns
time buckets, each holding one or more `results` rows grouped by the requested
dimensions (api_key_id / workspace_id / model). Pagination is cursor-style via
`has_more` + `next_page`.

⚠️ **Fidelity ceiling.** This endpoint is *aggregated* — a result row is a
sum over a time bucket for a (key, model) pair. It carries **no git branch or
session**, so events from this source can only reach `team` fidelity (via the
key→user→team identity graph) or `invoice` fidelity. Branch/ticket-level
attribution requires per-call telemetry — see `claude_code.py` (which does carry
`gitBranch`) or a ScopePilot proxy. This puller is the reconciliation backstop
that makes totals match the bill; it is not the ticket-level join.

The org **Cost Report** (`/v1/organizations/cost_report`) returns Anthropic's
own USD figures and is the truth source to reconcile our normalized costs
against; we keep cost computation in `pricing.py` so the same logic spans every
provider, and use the Cost Report only to sanity-check magnitude.
"""

from __future__ import annotations

import os
from datetime import datetime
from typing import Optional

from ..models import UsageEvent
from ._http import Transport, get_json

USAGE_URL = "https://api.anthropic.com/v1/organizations/usage_report/messages"
ANTHROPIC_VERSION = "2023-06-01"


def _ts(value) -> datetime:
    if value is None:
        return datetime.utcnow()
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def parse_admin_usage_report(report: dict) -> list[UsageEvent]:
    """Flatten an admin usage report (one or more pages already merged into a
    single `{"data": [...buckets...]}`) into aggregated `UsageEvent`s.

    Tolerates the cache-token field-name variants Anthropic has shipped over
    time (flat `cache_creation_input_tokens`, or a `cache_creation` breakdown of
    ephemeral 5m/1h buckets).
    """
    events: list[UsageEvent] = []
    for bucket in report.get("data", []):
        start = bucket.get("starting_at")
        for i, row in enumerate(bucket.get("results", [])):
            events.append(
                UsageEvent(
                    id=f"adm-{start}-{row.get('api_key_id','')}-{row.get('model','')}-{i}",
                    provider="anthropic",
                    model=row.get("model", "claude-sonnet-4-6"),
                    ts=_ts(start),
                    input_tokens=int(row.get("uncached_input_tokens",
                                             row.get("input_tokens", 0)) or 0),
                    output_tokens=int(row.get("output_tokens", 0) or 0),
                    cache_read_tokens=int(row.get("cache_read_input_tokens", 0) or 0),
                    cache_write_tokens=_cache_creation(row),
                    api_key_id=row.get("api_key_id"),
                    # No branch/session/user available at this aggregation level.
                )
            )
    return events


def _cache_creation(row: dict) -> int:
    if "cache_creation_input_tokens" in row:
        return int(row.get("cache_creation_input_tokens") or 0)
    cc = row.get("cache_creation") or {}
    if isinstance(cc, dict):
        return int(
            (cc.get("ephemeral_5m_input_tokens", 0) or 0)
            + (cc.get("ephemeral_1h_input_tokens", 0) or 0)
        )
    return 0


class AnthropicAdminClient:
    """Paginating client for the org usage report."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = USAGE_URL,
        transport: Optional[Transport] = None,
    ) -> None:
        self.api_key = api_key or os.environ.get("ANTHROPIC_ADMIN_KEY", "")
        self.base_url = base_url
        self._transport = transport

    def _headers(self) -> dict:
        return {"x-api-key": self.api_key, "anthropic-version": ANTHROPIC_VERSION}

    def fetch(
        self,
        starting_at: str,
        ending_at: Optional[str] = None,
        bucket_width: str = "1d",
        group_by: tuple[str, ...] = ("api_key_id", "model"),
        limit: int = 1000,
    ) -> dict:
        """Fetch all pages, merging buckets into one `{"data": [...]}` report."""
        from urllib.parse import urlencode

        params = [
            ("starting_at", starting_at),
            ("bucket_width", bucket_width),
            ("limit", str(limit)),
        ]
        if ending_at:
            params.append(("ending_at", ending_at))
        for g in group_by:
            params.append(("group_by[]", g))

        merged: list[dict] = []
        page: Optional[str] = None
        while True:
            q = list(params)
            if page:
                q.append(("page", page))
            url = f"{self.base_url}?{urlencode(q)}"
            resp = get_json(url, self._headers(), self._transport)
            merged.extend(resp.get("data", []))
            if resp.get("has_more") and resp.get("next_page"):
                page = resp["next_page"]
                continue
            break
        return {"data": merged}

    def pull(self, starting_at: str, **kw) -> list[UsageEvent]:
        return parse_admin_usage_report(self.fetch(starting_at, **kw))
