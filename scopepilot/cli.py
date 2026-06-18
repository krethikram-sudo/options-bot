"""ScopePilot Phase 0 CLI.

Runs the full pipeline — ingest → cost-normalize → join → classify → attribute
→ forecast → recommend → report — over the Anthropic-usage + GitHub-Issues pair.
With no arguments it runs the bundled fixtures so you can see the deliverable
immediately:

    python -m scopepilot.cli

Point it at real exports with:

    python -m scopepilot.cli --usage usage.json --issues issues.json [--window-days 30]
"""

from __future__ import annotations

import argparse
from pathlib import Path

from .attribute import attribute
from .forecast import class_stats, find_anomalies, forecast_roadmap
from .ingest import parse_anthropic_usage, parse_github_issues
from .join import IdentityGraph, JoinEngine
from .recommend import recommend
from .report import render

_FIXTURES = Path(__file__).parent / "fixtures"


def run(usage_path: Path, issues_path: Path, window_days: int | None = None) -> str:
    events = parse_anthropic_usage(usage_path)
    work_items = parse_github_issues(issues_path)

    # Identity graph: in P0 we seed a tiny key→user→team map so TEAM-fidelity
    # spend (no branch) still rolls up somewhere. Production feeds this from SSO.
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

    # Project observed spend to a monthly figure if a window was given.
    horizon = (30.0 / window_days) if window_days else 1.0
    recs = recommend(result, horizon_scale=horizon)

    return render(result, stats, fc, anomalies, recs, window_days=window_days)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ScopePilot Phase 0 attribution report")
    p.add_argument("--usage", type=Path, default=_FIXTURES / "anthropic_usage.json")
    p.add_argument("--issues", type=Path, default=_FIXTURES / "github_issues.json")
    p.add_argument("--window-days", type=int, default=None,
                   help="observed window length, used to project a monthly figure")
    args = p.parse_args(argv)
    print(run(args.usage, args.issues, args.window_days))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
