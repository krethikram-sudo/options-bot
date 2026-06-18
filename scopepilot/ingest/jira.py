"""Jira planner adapter.

Normalizes the Jira REST search shape (`{"issues": [{"key", "fields": {...}}]}`)
into `WorkItem`s keyed by the issue key (`OPS-123`). The key embeds the project
prefix, so a branch like `fix/OPS-123-crash` resolves straight to it via the
default ticket resolver — no per-shop config needed for the common case.

Jira's basic search doesn't return the dev-panel branch or diff stats, so those
stay empty; classification leans on labels/issuetype, and the branch join works
off the key embedded in the agent's git branch. Story-point custom-field id is
configurable (defaults to the common `customfield_10016`).
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from ..models import WorkItem

# Jira status categories → our status vocabulary.
_STATUS_CATEGORY = {"new": "open", "indeterminate": "in_progress", "done": "done"}


def _ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def _status(fields: dict) -> str:
    status = fields.get("status") or {}
    cat = (status.get("statusCategory") or {}).get("key")
    if cat in _STATUS_CATEGORY:
        return _STATUS_CATEGORY[cat]
    # Fall back to the status name if no category present.
    name = (status.get("name") or "open").lower()
    if "done" in name or "closed" in name or "resolved" in name:
        return "done"
    if "progress" in name:
        return "in_progress"
    return "open"


def parse_jira_issues(
    data: Union[str, Path, list, dict],
    points_field: str = "customfield_10016",
) -> list[WorkItem]:
    if isinstance(data, (str, Path)) and not str(data).lstrip().startswith(("{", "[")):
        data = json.loads(Path(data).read_text())
    elif isinstance(data, str):
        data = json.loads(data)
    records = data.get("issues", data) if isinstance(data, dict) else data

    items: list[WorkItem] = []
    for rec in records:
        key = rec.get("key")
        if not key:
            continue
        f = rec.get("fields", {}) or {}
        labels = list(f.get("labels", []) or [])
        issuetype = (f.get("issuetype") or {}).get("name")
        if issuetype:
            labels = labels + [issuetype]  # issuetype is a strong class signal
        parent = (f.get("parent") or {}).get("key")
        assignee = (f.get("assignee") or {})
        items.append(
            WorkItem(
                ticket_id=key,
                source="jira",
                title=f.get("summary", ""),
                status=_status(f),
                labels=labels,
                epic_id=parent or f.get("epic"),
                sprint_id=_sprint(f),
                est_points=f.get(points_field),
                team_id=(f.get("project") or {}).get("key") or assignee.get("emailAddress"),
                opened_at=_ts(f.get("created")),
                merged_at=_ts(f.get("resolutiondate")),
            )
        )
    return items


def _sprint(fields: dict) -> Optional[str]:
    sprint = fields.get("sprint") or fields.get("customfield_10020")
    if isinstance(sprint, list) and sprint:
        first = sprint[0]
        return first.get("name") if isinstance(first, dict) else str(first)
    if isinstance(sprint, dict):
        return sprint.get("name")
    return sprint if isinstance(sprint, str) else None
