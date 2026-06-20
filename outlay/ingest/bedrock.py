"""AWS Bedrock model-invocation-log adapter.

Enterprises overwhelmingly run Claude through **Amazon Bedrock**, not the
Anthropic direct API — so this is the connector that makes Outlay usable at
enterprise scale. Bedrock can be configured to emit a *model invocation log*
for every call (Console → Bedrock → Settings → Model invocation logging), which
it writes to CloudWatch Logs and/or S3. Each record carries the per-call token
counts, the `modelId`, the timestamp, and the IAM `identity` that made the call.

This adapter parses those records into `UsageEvent`s. **Fidelity ceiling is
`team`** (via identity→user→team): Bedrock has no idea what git branch the work
happened on, so — like the Anthropic Admin and Cursor sources — it reconciles
totals and supports per-team / cost-center allocation, but the ticket-level
join still needs a branch-bearing source (Claude Code transcripts or a proxy).

v1 ingests an **export** of the logs (the realistic enterprise path: the
customer points us at the JSON/JSONL they already ship to S3/CloudWatch, or
hands us a dump). A live CloudWatch Logs / S3 puller (AWS SigV4) is the planned
follow-up; the parser below is the part that has to be right.

Cache-token note: when Bedrock prompt caching is in play the records carry
`cacheReadInputTokenCount` / `cacheWriteInputTokenCount`; we keep them split so
cached workloads aren't overstated.

Model-id note: Bedrock ids look like `us.anthropic.claude-sonnet-4-6-v1:0`
(optionally with a region prefix and a version suffix). We normalize them to the
canonical family names the pricing table knows; an unrecognized id is passed
through and priced via the engine's documented fallback.
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
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return datetime.utcnow()


def normalize_model(model_id: Optional[str]) -> str:
    """Map a Bedrock modelId to a canonical family name the pricing table knows.

    e.g. 'us.anthropic.claude-sonnet-4-6-v1:0' -> 'claude-sonnet-4-6'.
    Unknown ids are returned cleaned (region/provider/version stripped) so the
    engine's pricing fallback applies rather than crashing.
    """
    if not model_id:
        return "claude-sonnet-4-6"
    m = model_id.lower()
    # strip cross-region inference prefixes (us. / eu. / apac. / global.)
    for pre in ("us.", "eu.", "apac.", "global."):
        if m.startswith(pre):
            m = m[len(pre):]
            break
    if m.startswith("anthropic."):
        m = m[len("anthropic."):]
    # strip a trailing version tag like '-v1:0' / ':0'
    m = m.split(":")[0]
    if m.endswith("-v1") or m.endswith("-v2"):
        m = m[:-3]
    # map by family to the current priced models
    if "haiku" in m:
        return "claude-haiku-4-5"
    if "opus" in m:
        return "claude-opus-4-8"
    if "sonnet" in m:
        return "claude-sonnet-4-6"
    if "fable" in m:
        return "claude-fable-5"
    return m


def actor_from_identity(identity) -> Optional[str]:
    """Best-effort actor from the IAM `identity` block of an invocation record.

    'arn:aws:sts::123:assumed-role/PaymentsSvcRole/payments-pod-7' -> 'PaymentsSvcRole'
    'arn:aws:iam::123:user/alice'                                  -> 'alice'
    The role (not the ephemeral session) is the stable handle to map to a team.
    """
    if isinstance(identity, dict):
        arn = identity.get("arn") or identity.get("Arn")
    else:
        arn = identity
    if not arn or "/" not in str(arn):
        return None
    parts = str(arn).split("/")
    head = parts[0]  # 'arn:aws:sts::123:assumed-role' or 'arn:aws:iam::123:user'
    if head.endswith("assumed-role"):
        return parts[1] if len(parts) > 1 else None     # the role name
    if head.endswith("user"):
        return parts[-1]                                  # the IAM user name
    return parts[-1]


def _toks(rec: dict) -> tuple[int, int, int, int]:
    """Dig token counts out of a record, tolerating the shapes Bedrock has used
    (top-level, nested under input/output, or under a `usage` block)."""
    inp = rec.get("input") or {}
    out = rec.get("output") or {}
    usage = rec.get("usage") or {}

    def pick(*candidates) -> int:
        for src, key in candidates:
            v = (src or {}).get(key)
            if v is not None:
                try:
                    return int(v)
                except (ValueError, TypeError):
                    return 0
        return 0

    input_tokens = pick((inp, "inputTokenCount"), (usage, "inputTokens"), (rec, "inputTokenCount"))
    output_tokens = pick((out, "outputTokenCount"), (usage, "outputTokens"), (rec, "outputTokenCount"))
    cache_read = pick((inp, "cacheReadInputTokenCount"), (usage, "cacheReadInputTokens"),
                      (rec, "cacheReadInputTokenCount"))
    cache_write = pick((inp, "cacheWriteInputTokenCount"), (usage, "cacheWriteInputTokens"),
                       (rec, "cacheWriteInputTokenCount"))
    return input_tokens, output_tokens, cache_read, cache_write


def parse_bedrock_invocation_logs(records: Iterable[dict],
                                  user_map: Optional[dict] = None) -> list[UsageEvent]:
    """Parse Bedrock model-invocation-log records into `UsageEvent`s.

    `user_map` optionally maps the resolved actor (IAM role / user name) to a
    stable identity (e.g. an email), which the identity graph then maps to a team.
    """
    user_map = user_map or {}
    events: list[UsageEvent] = []
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            continue
        it, ot, cr, cw = _toks(rec)
        if it == 0 and ot == 0 and cr == 0 and cw == 0:
            continue  # not a billable invocation record (e.g. a control line)
        actor = actor_from_identity(rec.get("identity"))
        user = user_map.get(actor, actor) if actor else None
        events.append(
            UsageEvent(
                id=str(rec.get("requestId") or rec.get("request_id") or f"bedrock-{i}"),
                provider="bedrock",
                model=normalize_model(rec.get("modelId") or rec.get("model")),
                ts=_ts(rec.get("timestamp")),
                input_tokens=it,
                output_tokens=ot,
                cache_read_tokens=cr,
                cache_write_tokens=cw,
                user=user,
                # No git branch in Bedrock logs -> team-fidelity, not ticket-level.
            )
        )
    return events


def parse_bedrock_log_text(text: str, user_map: Optional[dict] = None) -> list[UsageEvent]:
    """Parse an export that's either a JSON array of records or JSONL (one per line)."""
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
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return parse_bedrock_invocation_logs(records, user_map=user_map)


def parse_bedrock_log_file(path: Union[str, Path],
                           user_map: Optional[dict] = None) -> list[UsageEvent]:
    """Read a Bedrock invocation-log export (.json or .jsonl) and parse it."""
    return parse_bedrock_log_text(Path(path).read_text(), user_map=user_map)
