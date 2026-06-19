"""One-command real-data validation.

    GITHUB_TOKEN=… python -m outlay.dogfood --repo owner/name \
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
from .backtest import backtest, format_calibration
from .forecast import class_stats, find_anomalies, forecast_roadmap
from .ingest import GitHubIssuesClient, parse_claude_code_dir
from .join import JoinEngine
from .policy import build_policy
from .recommend import recommend
from .report import render
from .size import fit_size_models


def build_report(events, work, window_days: int = 30, *, as_json: bool = False,
                 as_html: bool = False, company: str | None = None) -> str:
    """Assemble the full dogfood report from already-ingested events + work items.

    Pure (no network) so it's unit-testable: runs attribution, the size-aware
    forecast, the recommendations, and appends the measured calibration backtest
    plus the make-or-break ticket-coverage line. With `as_json`, returns the same
    content as a machine-readable JSON string instead of the text report.
    """
    result = attribute(events, work, engine=JoinEngine(work))
    stats = class_stats(result)
    size_models = fit_size_models(result, work)
    fc = forecast_roadmap([w for w in work if w.is_open], stats, size_models)
    recs = recommend(result, horizon_scale=30.0 / max(window_days, 1))
    calibration = backtest(result, work)

    if as_json or as_html:
        from .serialize import to_dict
        data = to_dict(result, stats, fc, find_anomalies(result, stats), recs,
                       calibration=calibration, policy=build_policy(recs),
                       window_days=window_days)
        if as_html:
            from .readout import render_html
            return render_html(data, company=company)
        import json as _json
        return _json.dumps(data, indent=2)

    parts = [
        render(result, stats, fc, find_anomalies(result, stats), recs,
               policy=build_policy(recs), window_days=window_days),
        # Measured forecast accuracy on *your* history — class-mean vs size-conditioned.
        "\n" + format_calibration(calibration),
        f">>> TICKET COVERAGE: {result.ticket_coverage:.0%}   "
        f"(events={len(result.rows)}, tickets touched={len(result.rollups)}, "
        f"issues={len(work)})",
        ">>> This is the make-or-break number. High = the join works on real data.",
    ]
    return "\n".join(parts)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Outlay real-data dogfood")
    p.add_argument("--repo", required=True, help="owner/name of the GitHub repo")
    p.add_argument("--claude-code", default=os.path.expanduser("~/.claude/projects"),
                   help="path to Claude Code transcripts (default ~/.claude/projects)")
    p.add_argument("--state", default="all", choices=["all", "open", "closed"])
    p.add_argument("--window-days", type=int, default=30)
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="emit the report as machine-readable JSON")
    p.add_argument("--html", action="store_true", dest="as_html",
                   help="emit a VP-ready printable HTML audit readout")
    p.add_argument("--company", default=None, help="company/team name for the HTML readout")
    args = p.parse_args(argv)

    owner, _, repo = args.repo.partition("/")
    if not owner or not repo:
        p.error("--repo must be 'owner/name'")

    work = GitHubIssuesClient().pull(owner, repo, state=args.state)
    events = parse_claude_code_dir(args.claude_code)
    # On JSON output keep stdout clean (parseable); send diagnostics to stderr.
    import sys
    diag = sys.stderr if (args.as_json or args.as_html) else sys.stdout
    if not events:
        print(f"(no Claude Code transcripts found under {args.claude_code})", file=diag)
    if not work:
        print(f"(no issues returned for {args.repo} — check GITHUB_TOKEN/scope)", file=diag)

    print(build_report(events, work, window_days=args.window_days,
                       as_json=args.as_json, as_html=args.as_html,
                       company=args.company or args.repo))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
