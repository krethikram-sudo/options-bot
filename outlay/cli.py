"""Outlay Phase 0 CLI.

Runs the full pipeline — ingest → cost-normalize → join → classify → attribute
→ forecast → recommend → report — over any combination of usage sources joined
to a planning system (GitHub Issues in P0).

With no arguments it runs the bundled fixtures so you can see the deliverable:

    python -m outlay.cli

Mix real sources (each is additive; branch-bearing sources reach ticket-level
fidelity, aggregated ones reconcile totals):

    python -m outlay.cli \
        --claude-code ~/.claude/projects \
        --anthropic-admin admin_report.json \
        --cursor cursor_events.json \
        --issues issues.json --window-days 30

Live admin pulls (need ANTHROPIC_ADMIN_KEY / CURSOR_ADMIN_KEY) are exposed via
the `AnthropicAdminClient` / `CursorAdminClient` classes in `outlay.ingest`;
the CLI consumes their JSON output so it stays offline-friendly.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from .attribute import attribute
from .backtest import backtest, format_calibration
from .budget import parse_budgets, track_budgets
from .forecast import class_stats, find_anomalies, forecast_roadmap
from .ingest import (
    PLANNERS,
    parse_admin_usage_report,
    parse_anthropic_usage,
    parse_claude_code_dir,
    parse_claude_code_transcript,
    parse_cursor_events,
)
from .join import IdentityGraph, JoinEngine, TicketResolver
from .models import UsageEvent
from .policy import build_policy
from .recommend import recommend
from .report import render
from .size import fit_size_models

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
    planner: str = "github",
    anthropic_admin: Path | None = None,
    cursor: Path | None = None,
    claude_code: Path | None = None,
    claude_code_user: str | None = None,
    emit_policy: Path | None = None,
    budgets_path: Path | None = None,
    calibrate: bool = False,
    as_json: bool = False,
    as_html: bool = False,
    company: str | None = None,
    commitment: bool = False,
    opportunities: bool = False,
) -> str:
    events = gather_events(
        usage=usage_path,
        anthropic_admin=anthropic_admin,
        cursor=cursor,
        claude_code=claude_code,
        claude_code_user=claude_code_user,
    )
    parse_work, resolver_source = PLANNERS[planner]
    work_items = parse_work(issues_path)

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
    engine = JoinEngine(work_items, identity=identity,
                        resolver=TicketResolver(source=resolver_source))

    result = attribute(events, work_items, engine=engine)
    stats = class_stats(result)
    size_models = fit_size_models(result, work_items)

    open_items = [wi for wi in work_items if wi.is_open]
    fc = forecast_roadmap(open_items, stats, size_models)
    anomalies = find_anomalies(result, stats, threshold=3.0)

    horizon = (30.0 / window_days) if window_days else 1.0
    recs = recommend(result, horizon_scale=horizon)
    policy = build_policy(recs)

    if emit_policy:
        Path(emit_policy).write_text(json.dumps(policy.to_dict(), indent=2))

    budgets = None
    if budgets_path:
        budgets = track_budgets(result, work_items,
                                parse_budgets(_load_json(budgets_path)))

    # Calibration is computed whenever it's requested, or always for JSON/HTML output.
    calibration = backtest(result, work_items) if (calibrate or as_json or as_html) else None

    if as_json or as_html:
        from .serialize import to_dict
        data = to_dict(result, stats, fc, anomalies, recs,
                       calibration=calibration, policy=policy,
                       budgets=budgets, window_days=window_days)
        if as_html:
            from .readout import render_html
            return render_html(data, company=company)
        import json as _json
        return _json.dumps(data, indent=2)

    out = render(result, stats, fc, anomalies, recs, policy=policy,
                 budgets=budgets, window_days=window_days)

    if calibration is not None:
        out += "\n" + format_calibration(calibration)

    if commitment:
        from .commitment import (
            daily_spend_series,
            decompose,
            default_ratecard,
            format_commitment,
            recommend_commitment,
        )

        series = daily_spend_series(events)
        profile = decompose(series)
        # Blended realized $/Mtok from the customer's own spend, so the rate card
        # reflects their actual mix rather than a list price.
        total_cost = sum(series)
        total_mtok = sum(e.total_tokens for e in events) / 1_000_000.0
        blended = (total_cost / total_mtok) if total_mtok > 0 else 9.0
        card = default_ratecard(on_demand_usd_per_mtok=blended)
        forecast_month = profile.mean_usd * 30.0
        scenarios = recommend_commitment(profile, forecast_month, card, floor_periods=30)
        out += "\n\n" + format_commitment(profile, scenarios, card)

    if opportunities:
        from .opportunities import (
            batch_opportunities,
            caching_opportunities,
            format_opportunities,
        )

        caching = caching_opportunities(events)
        batch = batch_opportunities(result)
        out += "\n\n" + format_opportunities(caching, batch)

    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Outlay Phase 0 attribution report")
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
    p.add_argument("--planner", choices=sorted(PLANNERS), default="github",
                   help="planning system the --issues export came from")
    p.add_argument("--emit-policy", type=Path, default=None,
                   help="write the proxy-consumable routing policy JSON to this path")
    p.add_argument("--budgets", type=Path, default=None,
                   help="budgets JSON (scope_type/scope_id/limit_usd/period_*) for burndown")
    p.add_argument("--window-days", type=int, default=None,
                   help="observed window length, used to project a monthly figure")
    p.add_argument("--calibrate", action="store_true",
                   help="append a leave-one-out backtest of forecast accuracy on realized spend")
    p.add_argument("--json", action="store_true", dest="as_json",
                   help="emit the full report as machine-readable JSON (implies --calibrate)")
    p.add_argument("--html", action="store_true", dest="as_html",
                   help="emit a VP-ready printable HTML audit readout")
    p.add_argument("--company", default=None,
                   help="company/team name for the HTML readout header")
    p.add_argument("--commitment", action="store_true",
                   help="append a commitment & procurement optimization recommendation "
                        "(on-demand vs committed-spend discount) from the usage series")
    p.add_argument("--opportunities", action="store_true",
                   help="append advisory optimization opportunities (prompt-caching + "
                        "batch-API candidates) — upper-bound potential, not realized savings")
    args = p.parse_args(argv)

    # Default to the bundled demo when no usage source is given.
    if not any([args.usage, args.anthropic_admin, args.cursor, args.claude_code]):
        args.usage = _FIXTURES / "anthropic_usage.json"

    print(run(
        args.usage, args.issues, args.window_days,
        planner=args.planner,
        anthropic_admin=args.anthropic_admin,
        cursor=args.cursor,
        claude_code=args.claude_code,
        claude_code_user=args.claude_code_user,
        emit_policy=args.emit_policy,
        budgets_path=args.budgets,
        calibrate=args.calibrate,
        as_json=args.as_json,
        as_html=args.as_html,
        company=args.company,
        commitment=args.commitment,
        opportunities=args.opportunities,
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
