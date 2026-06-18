"""ScopePilot Phase 0 CLI.

Runs the full pipeline — ingest → cost-normalize → join → classify → attribute
→ forecast → recommend → report — over any combination of usage sources joined
to a planning system (GitHub Issues in P0).

With no arguments it runs the bundled fixtures so you can see the deliverable:

    python -m scopepilot.cli

Mix real sources (each is additive; branch-bearing sources reach ticket-level
fidelity, aggregated ones reconcile totals):

    python -m scopepilot.cli \
        --claude-code ~/.claude/projects \
        --anthropic-admin admin_report.json \
        --cursor cursor_events.json \
        --issues issues.json --window-days 30

Live admin pulls (need ANTHROPIC_ADMIN_KEY / CURSOR_ADMIN_KEY) are exposed via
the `AnthropicAdminClient` / `CursorAdminClient` classes in `scopepilot.ingest`;
the CLI consumes their JSON output so it stays offline-friendly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .attribute import attribute
from .forecast import class_stats, find_anomalies, forecast_roadmap
from .ingest import (
    parse_admin_usage_report,
    parse_anthropic_usage,
    parse_claude_code_dir,
    parse_claude_code_transcript,
    parse_cursor_events,
    parse_github_issues,
)
from .join import IdentityGraph, JoinEngine
from .models import UsageEvent
from .recommend import recommend
from .report import render

_FIXTURES = Path(__file__).parent / "fixtures"


def _load_json(path: Path) -> dict | list:
    return json.loads(Path(path).read_text())


def gather_events(
    usage: Path | None = None,
    anthropic_admin: Path | None = None,
    cursor: Path | None = None,
    claude_code: Path | None = None,
    claude_code_user: str | None = None,
) -> list[UsageEvent]:
    """Concatenate events from every supplied source."""
    events: list[UsageEvent] = []
    if usage:
        events += parse_anthropic_usage(usage)
    if anthropic_admin:
        events += parse_admin_usage_report(_load_json(anthropic_admin))
    if cursor:
        events += parse_cursor_events(_load_json(cursor))
    if claude_code:
        p = Path(claude_code)
        if p.is_dir():
            events += parse_claude_code_dir(p)
        else:
            events += parse_claude_code_transcript(p, user=claude_code_user)
    return events


def run(
    usage_path: Path | None = None,
    issues_path: Path = _FIXTURES / "github_issues.json",
    window_days: int | None = None,
    *,
    anthropic_admin: Path | None = None,
    cursor: Path | None = None,
    claude_code: Path | None = None,
    claude_code_user: str | None = None,
) -> str:
    events = gather_events(
        usage=usage_path,
        anthropic_admin=anthropic_admin,
        cursor=cursor,
        claude_code=claude_code,
        claude_code_user=claude_code_user,
    )
    work_items = parse_github_issues(issues_path)

    # Identity graph: seeds key→user→team so aggregated/no-branch spend (Admin
    # API, Cursor, CI keys) still rolls up to a team. Production feeds this from
    # SSO/SCIM + provider key metadata.
    identity = IdentityGraph(
        key_to_user={"key_ci": "ci-bot@acme.dev"},
        user_to_team={
            "ci-bot@acme.dev": "platform",
            "alice@acme.dev": "platform",
            "bob@acme.dev": "growth",
        },
    )
    engine = JoinEngine(work_items, identity=identity)

    result = attribute(events, work_items, engine=engine)
    stats = class_stats(result)

    open_items = [wi for wi in work_items if wi.is_open]
    fc = forecast_roadmap(open_items, stats)
    anomalies = find_anomalies(result, stats, threshold=3.0)

    horizon = (30.0 / window_days) if window_days else 1.0
    recs = recommend(result, horizon_scale=horizon)

    return render(result, stats, fc, anomalies, recs, window_days=window_days)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ScopePilot Phase 0 attribution report")
    p.add_argument("--usage", type=Path, default=None,
                   help="Anthropic per-call usage JSON (proxy/tool export)")
    p.add_argument("--anthropic-admin", type=Path, default=None,
                   help="Anthropic Admin usage report JSON")
    p.add_argument("--cursor", type=Path, default=None,
                   help="Cursor filtered-usage-events JSON")
    p.add_argument("--claude-code", type=Path, default=None,
                   help="Claude Code .jsonl transcript or ~/.claude/projects dir")
    p.add_argument("--claude-code-user", default=None,
                   help="engineer email to attribute a single Claude Code transcript to")
    p.add_argument("--issues", type=Path, default=_FIXTURES / "github_issues.json")
    p.add_argument("--window-days", type=int, default=None,
                   help="observed window length, used to project a monthly figure")
    args = p.parse_args(argv)

    # Default to the bundled demo when no usage source is given.
    if not any([args.usage, args.anthropic_admin, args.cursor, args.claude_code]):
        args.usage = _FIXTURES / "anthropic_usage.json"

    print(run(
        args.usage, args.issues, args.window_days,
        anthropic_admin=args.anthropic_admin,
        cursor=args.cursor,
        claude_code=args.claude_code,
        claude_code_user=args.claude_code_user,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
