"""OpenAI / Azure OpenAI usage adapter (multi-model coverage).

Many enterprises run Claude *and* OpenAI (often via Azure OpenAI). To attribute
and forecast their whole AI bill, Outlay ingests OpenAI usage too. This parses
an OpenAI usage export — either the Usage API's bucketed results
(`/v1/organization/usage/completions`) or a flat list of per-call rows — into
`UsageEvent`s, priced on the separate OpenAI rate table (`pricing.OPENAI_RATES`),
which is kept out of the Claude routing ladder.

Azure OpenAI uses the same model families via *deployment names*; pass a
`deployment_map` (deployment → base model) if your export reports deployments,
otherwise the normalizer maps any id containing a known family.

Fidelity ceiling is `team` (no git branch), via user→team — consistent with the
Bedrock / Vertex / Anthropic-Admin sources.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Optional, Union

from ..models import UsageEvent

_FAMILIES = ("gpt-4o-mini", "o3-mini", "gpt-4.1", "gpt-4o", "gpt-4-turbo", "o1")


def _ts(value) -> datetime:
    if value is None:
        return datetime.utcnow()
    if isinstance(value, (int, float)):
        return datetime.utcfromtimestamp(value)
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)
    except (ValueError, TypeError):
        return datetime.utcnow()


def normalize_openai_model(model_id: Optional[str], deployment_map: Optional[dict] = None) -> str:
    """Map an OpenAI/Azure model or deployment id to a canonical priced family.

    'gpt-4o-2024-08-06' -> 'gpt-4o'; an Azure deployment -> its base via the map."""
    if not model_id:
        return "gpt-4o"
    m = str(model_id).lower()
    if deployment_map and model_id in deployment_map:
        m = str(deployment_map[model_id]).lower()
    # longest family first so 'gpt-4o-mini' wins over 'gpt-4o'
    for fam in sorted(_FAMILIES, key=len, reverse=True):
        if fam in m:
            return fam
    return m


def _rows(payload) -> list[dict]:
    """Flatten either a Usage-API bucketed report or a flat list into rows."""
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if not isinstance(payload, dict):
        return []
    if "data" in payload and isinstance(payload["data"], list):
        out: list[dict] = []
        for bucket in payload["data"]:
            results = bucket.get("results") if isinstance(bucket, dict) else None
            if isinstance(results, list):
                out.extend(r for r in results if isinstance(r, dict))
            elif isinstance(bucket, dict):
                out.append(bucket)
        return out
    if "results" in payload and isinstance(payload["results"], list):
        return [r for r in payload["results"] if isinstance(r, dict)]
    return [payload]


def parse_openai_usage(payload, user_map: Optional[dict] = None,
                       deployment_map: Optional[dict] = None) -> list[UsageEvent]:
    """Parse an OpenAI/Azure usage export into `UsageEvent`s.

    OpenAI reports total `input_tokens` *including* cached input plus a separate
    `input_cached_tokens`; we split them so cached input is billed at OpenAI's
    discounted rate rather than full price."""
    user_map = user_map or {}
    events: list[UsageEvent] = []
    for i, row in enumerate(_rows(payload)):
        total_in = int(row.get("input_tokens", row.get("n_input_tokens", 0)) or 0)
        out_tok = int(row.get("output_tokens", row.get("n_output_tokens", 0)) or 0)
        cached = int(row.get("input_cached_tokens", row.get("cached_tokens", 0)) or 0)
        cached = min(cached, total_in)
        uncached_in = max(0, total_in - cached)
        if total_in == 0 and out_tok == 0:
            continue
        actor = (row.get("user") or row.get("user_id") or row.get("api_key_id")
                 or row.get("project_id"))
        user = user_map.get(actor, actor) if actor else None
        events.append(
            UsageEvent(
                id=str(row.get("id") or row.get("request_id") or f"openai-{i}"),
                provider="openai",
                model=normalize_openai_model(row.get("model") or row.get("deployment"), deployment_map),
                ts=_ts(row.get("start_time") or row.get("timestamp") or row.get("ts")),
                input_tokens=uncached_in,
                output_tokens=out_tok,
                cache_read_tokens=cached,
                cache_write_tokens=0,            # OpenAI has no separate cache-write charge
                user=user,
            )
        )
    return events


def parse_openai_usage_text(text: str, user_map: Optional[dict] = None,
                            deployment_map: Optional[dict] = None) -> list[UsageEvent]:
    text = (text or "").strip()
    if not text:
        return []
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        payload = [json.loads(ln) for ln in text.splitlines() if ln.strip()]
    return parse_openai_usage(payload, user_map=user_map, deployment_map=deployment_map)


def parse_openai_usage_file(path: Union[str, Path], user_map: Optional[dict] = None,
                            deployment_map: Optional[dict] = None) -> list[UsageEvent]:
    return parse_openai_usage_text(Path(path).read_text(), user_map=user_map,
                                   deployment_map=deployment_map)
