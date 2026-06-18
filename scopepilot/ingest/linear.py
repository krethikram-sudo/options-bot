"""Linear planner adapter.

Normalizes the Linear GraphQL issue shape (`{"issues": {"nodes": [...]}}`) into
`WorkItem`s keyed by `identifier` (`ENG-123`). Linear is the friendliest planner
for attribution because it exposes **`branchName`** directly — the suggested git
branch for the issue — so the BRANCH join lands even when the agent's branch
name doesn't embed the key verbatim.

Status maps from Linear's workflow state `type`
(backlog/unstarted/started/completed/canceled).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from ..models import WorkItem

_STATE_TYPE = {
    "backlog": "open",
    "unstarted": "open",
    "triage": "open",
    "started": "in_progress",
    "completed": "done",
    "canceled": "done",
}


def _ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def _labels(rec: dict) -> list[str]:
    labels = rec.get("labels") or {}
    nodes = labels.get("nodes", labels) if isinstance(labels, dict) else labels
    return [n["name"] if isinstance(n, dict) else str(n) for n in (nodes or [])]


def parse_linear_issues(data: Union[str, Path, list, dict]) -> list[WorkItem]:
    if isinstance(data, (str, Path)) and not str(data).lstrip().startswith(("{", "[")):
        data = json.loads(Path(data).read_text())
    elif isinstance(data, str):
        data = json.loads(data)

    if isinstance(data, dict):
        issues = data.get("issues", data)
        records = issues.get("nodes", issues) if isinstance(issues, dict) else issues
    else:
        records = data

    items: list[WorkItem] = []
    for rec in records:
        ident = rec.get("identifier")
        if not ident:
            continue
        state = rec.get("state") or {}
        items.append(
            WorkItem(
                ticket_id=ident,
                source="linear",
                title=rec.get("title", ""),
                status=_STATE_TYPE.get((state.get("type") or "").lower(), "open"),
                labels=_labels(rec),
                epic_id=(rec.get("project") or {}).get("name"),
                sprint_id=(rec.get("cycle") or {}).get("name"),
                est_points=rec.get("estimate"),
                team_id=(rec.get("team") or {}).get("key"),
                branch=rec.get("branchName"),
                opened_at=_ts(rec.get("createdAt")),
                merged_at=_ts(rec.get("completedAt")),
            )
        )
    return items
