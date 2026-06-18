"""GitHub Issues adapter.

Normalizes the GitHub issues/PR JSON shape into `WorkItem`s keyed `GH-<number>`
— the same canonical id the branch resolver produces, so the join lines up.

Pulls the signals the pipeline needs: labels (for task-class), state (open vs
done), the linked branch/PR head ref (for the BRANCH join), diff size
(classification fallback + a proxy for effort), and milestone→epic mapping.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Optional, Union

from ..models import WorkItem


def _ts(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    return datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def _labels(rec: dict) -> list[str]:
    raw = rec.get("labels", []) or []
    out = []
    for l in raw:
        out.append(l["name"] if isinstance(l, dict) else str(l))
    return out


def _status(rec: dict) -> str:
    state = (rec.get("state") or "open").lower()
    if state == "closed":
        # Merged PR / closed-as-completed → done; closed-as-not-planned stays open-ish.
        if rec.get("merged_at") or rec.get("state_reason") in (None, "completed"):
            return "done"
    if rec.get("in_progress") or "in progress" in [l.lower() for l in _labels(rec)]:
        return "in_progress"
    return "open"


def parse_github_issues(data: Union[str, Path, list, dict]) -> list[WorkItem]:
    """Parse GitHub issues/PR JSON into `WorkItem`s."""
    if isinstance(data, (str, Path)) and not str(data).lstrip().startswith(("{", "[")):
        data = json.loads(Path(data).read_text())
    elif isinstance(data, str):
        data = json.loads(data)

    if isinstance(data, dict):
        records = data.get("issues") or data.get("data") or []
    else:
        records = data

    items: list[WorkItem] = []
    for rec in records:
        number = rec.get("number")
        if number is None:
            continue
        milestone = rec.get("milestone")
        epic = (milestone.get("title") if isinstance(milestone, dict) else milestone)
        items.append(
            WorkItem(
                ticket_id=f"GH-{int(number)}",
                source="github",
                title=rec.get("title", ""),
                status=_status(rec),
                labels=_labels(rec),
                epic_id=epic,
                sprint_id=rec.get("sprint"),
                est_points=rec.get("points"),
                team_id=rec.get("team"),
                branch=rec.get("head_ref") or rec.get("branch"),
                pr_number=rec.get("pr_number"),
                diff_added=int(rec.get("additions", 0) or 0),
                diff_removed=int(rec.get("deletions", 0) or 0),
                opened_at=_ts(rec.get("created_at")),
                merged_at=_ts(rec.get("merged_at")),
            )
        )
    return items
