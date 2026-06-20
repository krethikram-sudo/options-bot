"""Google Vertex AI (Anthropic models) usage adapter.

Vertex AI is the third major way teams run Claude — alongside the Anthropic
direct API and AWS Bedrock. When request-response logging is enabled, Vertex
writes a log entry per call (to Cloud Logging / BigQuery) carrying the model,
timestamp, the calling principal, and — because these *are* Anthropic models —
the standard Anthropic `usage` block (input/output + cache tokens).

This adapter parses those log entries into `UsageEvent`s. Because the models are
Claude, the existing pricing table prices them directly (no new rates). Like the
Bedrock / Anthropic-Admin sources it carries no git branch, so its **fidelity
ceiling is `team`** (via principal→user→team); ticket-level attribution still
needs a branch-bearing source.

v1 ingests a **log export** (JSON array or JSONL) — the realistic enterprise
path. A live Cloud Logging / BigQuery puller is the planned follow-up.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Union

from ..models import UsageEvent
from .bedrock import normalize_model as _normalize_family


def _ts(value) -> datetime:
    if value is None:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return datetime.utcnow()


def normalize_vertex_model(model_id: Optional[str]) -> str:
    """'publishers/anthropic/models/claude-sonnet-4@20250514' -> 'claude-sonnet-4-6'.

    Strips the Vertex publisher path and the '@version' snapshot, then maps the
    family to the priced model (reusing the Bedrock family normalizer)."""
    if not model_id:
        return "claude-sonnet-4-6"
    m = str(model_id).lower()
    if "publishers/" in m:           # publishers/anthropic/models/<id>
        m = m.rsplit("/", 1)[-1]
    m = m.split("@")[0]              # drop @YYYYMMDD snapshot
    return _normalize_family(m)


def _dig(rec: dict, *paths):
    """Return the first present value among dotted paths into the record."""
    for path in paths:
        cur = rec
        ok = True
        for key in path.split("."):
            if isinstance(cur, dict) and key in cur:
                cur = cur[key]
            else:
                ok = False
                break
        if ok and cur is not None:
            return cur
    return None


def _usage_block(rec: dict) -> dict:
    return (_dig(rec, "jsonPayload.response.usage", "response.usage", "usage") or {})


def actor_from_vertex(rec: dict) -> Optional[str]:
    """The calling principal — service-account or user email — for team mapping."""
    return _dig(rec, "labels.principal", "authenticationInfo.principalEmail",
                "protoPayload.authenticationInfo.principalEmail", "principalEmail", "principal")


def parse_vertex_logs(records: Iterable[dict],
                      user_map: Optional[dict] = None) -> list[UsageEvent]:
    """Parse Vertex request-response log records into `UsageEvent`s."""
    user_map = user_map or {}
    events: list[UsageEvent] = []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        u = _usage_block(rec)
        it = int(u.get("input_tokens", u.get("inputTokens", 0)) or 0)
        ot = int(u.get("output_tokens", u.get("outputTokens", 0)) or 0)
        cr = int(u.get("cache_read_input_tokens", u.get("cacheReadInputTokens", 0)) or 0)
        cw = int(u.get("cache_creation_input_tokens", u.get("cacheCreationInputTokens", 0)) or 0)
        if it == 0 and ot == 0 and cr == 0 and cw == 0:
            continue
        model = _dig(rec, "resource.labels.model_id", "jsonPayload.request.model",
                     "request.model", "model", "modelId")
        actor = actor_from_vertex(rec)
        user = user_map.get(actor, actor) if actor else None
        events.append(
            UsageEvent(
                id=str(_dig(rec, "insertId", "logName") or f"vertex-{i}"),
                provider="vertex",
                model=normalize_vertex_model(model),
                ts=_ts(_dig(rec, "timestamp", "receiveTimestamp")),
                input_tokens=it,
                output_tokens=ot,
                cache_read_tokens=cr,
                cache_write_tokens=cw,
                user=user,
            )
        )
    return events


def parse_vertex_log_text(text: str, user_map: Optional[dict] = None) -> list[UsageEvent]:
    """Parse a Vertex log export — a JSON array of entries or JSONL (one per line)."""
    text = (text or "").strip()
    if not text:
        return []
    records: list = []
    if text[0] == "[":
        try:
            records = json.loads(text)
        except json.JSONDecodeError:
            records = []
    else:
        for line in text.splitlines():
            line = line.strip()
            if line:
                try:
                    records.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return parse_vertex_logs(records, user_map=user_map)


def parse_vertex_log_file(path: Union[str, Path],
                          user_map: Optional[dict] = None) -> list[UsageEvent]:
    return parse_vertex_log_text(Path(path).read_text(), user_map=user_map)
