"""One-command real-data validation.

    GITHUB_TOKEN=… python -m scopepilot.dogfood --repo owner/name \
        --claude-code ~/.claude/projects [--window-days 30]

Pulls your repo's live GitHub issues and your local Claude Code transcripts
(which carry `gitBranch`), runs the full attribution pipeline, and prints the
report — plus the one number that decides whether the whole bet holds:
**ticket coverage**, the fraction of real spend that resolved to a real ticket.

No exports, no proxy, no admin keys. If coverage is high, real branches resolve
to real tickets and the product works; if it's low, that's the thing to fix
before anything else.
"""

from __future__ import annotations

import argparse
import os

from .attribute import attribute
from .forecast import class_stats, find_anomalies, forecast_roadmap
from .ingest import GitHubIssuesClient, parse_claude_code_dir
from .join import JoinEngine
from .policy import build_policy
from .recommend import recommend
from .report import render


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="ScopePilot real-data dogfood")
    p.add_argument("--repo", required=True, help="owner/name of the GitHub repo")
    p.add_argument("--claude-code", default=os.path.expanduser("~/.claude/projects"),
                   help="path to Claude Code transcripts (default ~/.claude/projects)")
    p.add_argument("--state", default="all", choices=["all", "open", "closed"])
    p.add_argument("--window-days", type=int, default=30)
    args = p.parse_args(argv)

    owner, _, repo = args.repo.partition("/")
    if not owner or not repo:
        p.error("--repo must be 'owner/name'")

    work = GitHubIssuesClient().pull(owner, repo, state=args.state)
    events = parse_claude_code_dir(args.claude_code)
    if not events:
        print(f"(no Claude Code transcripts found under {args.claude_code})")
    if not work:
        print(f"(no issues returned for {args.repo} — check GITHUB_TOKEN/scope)")

    result = attribute(events, work, engine=JoinEngine(work))
    stats = class_stats(result)
    fc = forecast_roadmap([w for w in work if w.is_open], stats)
    recs = recommend(result, horizon_scale=30.0 / max(args.window_days, 1))

    print(render(result, stats, fc, find_anomalies(result, stats), recs,
                 policy=build_policy(recs), window_days=args.window_days))
    print(f"\n>>> TICKET COVERAGE: {result.ticket_coverage:.0%}   "
          f"(events={len(result.rows)}, tickets touched={len(result.rollups)}, "
          f"issues={len(work)})")
    print(">>> This is the make-or-break number. High = the join works on real data.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
