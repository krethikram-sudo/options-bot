"""GitHub Issues adapter.

Normalizes the GitHub issues/PR JSON shape into `WorkItem`s keyed `GH-<number>`
— the same canonical id the branch resolver produces, so the join lines up.

Pulls the signals the pipeline needs: labels (for task-class), state (open vs
done), the linked branch/PR head ref (for the BRANCH join), diff size
(classification fallback + a proxy for effort), and milestone→epic mapping.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path
from typing import Optional, Union
from urllib.parse import urlencode

from ..models import WorkItem
from ._http import Transport, get_json


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


class GitHubIssuesClient:
    """GitHub REST issues client (live puller).

    `GET /repos/{owner}/{repo}/issues?state=all` with token auth and page
    pagination. Pull requests (which the issues endpoint also returns) are
    filtered out. The issues endpoint doesn't carry a branch — that's fine: the
    branch comes from the coding-tool telemetry (Claude Code `gitBranch`), and
    the join resolves it to `GH-<number>`.
    """

    def __init__(
        self,
        token: Optional[str] = None,
        base_url: str = "https://api.github.com",
        transport: Optional[Transport] = None,
    ) -> None:
        self.token = token or os.environ.get("GITHUB_TOKEN", "")
        self.base_url = base_url.rstrip("/")
        self._transport = transport

    def _headers(self) -> dict:
        h = {"accept": "application/vnd.github+json",
             "user-agent": "scopepilot"}
        if self.token:
            h["authorization"] = f"Bearer {self.token}"
        return h

    def fetch(self, owner: str, repo: str, state: str = "all",
              page_size: int = 100) -> dict:
        merged: list[dict] = []
        page = 1
        while True:
            params = {"state": state, "per_page": page_size, "page": page}
            url = f"{self.base_url}/repos/{owner}/{repo}/issues?{urlencode(params)}"
            rows = get_json(url, self._headers(), self._transport)
            if isinstance(rows, dict):  # error envelope or wrapped
                rows = rows.get("issues") or rows.get("data") or []
            # Drop PRs; the issues endpoint returns them with a pull_request key.
            merged.extend(r for r in rows if "pull_request" not in r)
            if len(rows) < page_size:
                break
            page += 1
        return {"issues": merged}

    def pull(self, owner: str, repo: str, **kw) -> list[WorkItem]:
        return parse_github_issues(self.fetch(owner, repo, **kw))
