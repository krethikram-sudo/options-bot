"""Outlay product surface for the console — run the engine on a customer's data.

The `outlay` package is the engine; this thin module wraps it for the web app.
Two ways in:
  * upload — paste tracker + AI-usage JSON (`build_report` / `estimate_backlog`).
  * connect — pull live from GitHub Issues + the Anthropic Admin API with the
    customer's read-only tokens (`sync`), via the engine's transport seam.
Stdlib + the in-repo `outlay` engine only.
"""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Optional

from outlay.attribute import attribute
from outlay.backtest import backtest
from outlay.forecast import class_stats, find_anomalies, forecast_roadmap
from outlay.ingest import parse_anthropic_usage, parse_github_issues
from outlay.recommend import recommend
from outlay.serialize import to_dict
from outlay.size import fit_size_models
from outlay.estimate import estimate_plan, parse_planned


def _tmp(text) -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    f.write(text if isinstance(text, str) else json.dumps(text))
    f.close()
    return f.name


def _parse(issues, usage):
    """Parse uploaded JSON into work items + usage events. Raises ValueError."""
    ip, up = _tmp(issues), _tmp(usage)
    try:
        try:
            work = parse_github_issues(ip)
            events = parse_anthropic_usage(up)
        except Exception as e:  # noqa: BLE001 — clean message for the UI
            raise ValueError(f"Couldn't read the uploaded data: {e}") from e
    finally:
        os.unlink(ip)
        os.unlink(up)
    return work, events


def _fit(work, events):
    result = attribute(events, work)
    return result, class_stats(result), fit_size_models(result, work)


def _serialize_plan(plan) -> dict:
    return {
        "expected_usd": round(plan.expected_usd, 2),
        "low_usd": round(plan.low_usd, 2),
        "high_usd": round(plan.high_usd, 2),
        "items_costed": plan.items_costed,
        "items_unknown": plan.items_unknown,
        "by_confidence": plan.by_confidence,
        "tighten": sorted({n for e in plan.items for n in e.needs}),
        "items": [{
            "id": e.item_id, "title": e.title, "task_class": e.task_class.value,
            "expected_usd": round(e.expected_usd, 2), "low_usd": round(e.low_usd, 2),
            "high_usd": round(e.high_usd, 2), "basis": e.basis,
            "complexity_tier": e.complexity_tier, "confidence": e.confidence,
            "costable": e.costable, "needs": e.needs,
        } for e in plan.items],
    }


def _serialize_model(stats, size_models) -> dict:
    """The minimal learned model the backlog estimator needs (so it works after
    either an upload or a live sync, without re-storing raw data)."""
    return {
        "stats": [{"task_class": s.task_class.value, "n": s.n, "mean": s.mean,
                   "median": s.median, "p10": s.p10, "p90": s.p90, "std": s.std,
                   "mean_rework": s.mean_rework} for s in stats.values()],
        "size": [{"task_class": m.task_class.value, "feature": m.feature,
                  "cost_per_unit": m.cost_per_unit, "n": m.n,
                  "lo_mult": m.lo_mult, "hi_mult": m.hi_mult} for m in size_models.values()],
    }


def _deserialize_model(d: dict):
    from outlay.forecast import ClassStats
    from outlay.models import TaskClass
    from outlay.size import SizeModel
    stats, size = {}, {}
    for s in (d or {}).get("stats", []):
        tc = TaskClass(s["task_class"])
        stats[tc] = ClassStats(task_class=tc, n=s["n"], mean=s["mean"], median=s["median"],
                               p10=s["p10"], p90=s["p90"], std=s["std"], mean_rework=s["mean_rework"])
    for m in (d or {}).get("size", []):
        tc = TaskClass(m["task_class"])
        size[tc] = SizeModel(task_class=tc, feature=m["feature"], cost_per_unit=m["cost_per_unit"],
                             n=m["n"], lo_mult=m["lo_mult"], hi_mult=m["hi_mult"])
    return stats, size


def _report(work, result, stats, size_models, planned_items=None, window_days: int = 30) -> dict:
    recs = recommend(result, horizon_scale=30.0 / max(window_days, 1))
    cal = backtest(result, work)
    fc = forecast_roadmap([w for w in work if w.is_open], stats, size_models)
    data = to_dict(result, stats, fc, find_anomalies(result, stats), recs,
                   calibration=cal, window_days=window_days)
    data["_model"] = _serialize_model(stats, size_models)  # for the backlog estimator
    if planned_items:
        data["estimate"] = _serialize_plan(estimate_plan(planned_items, stats, size_models))
    return data


def estimate_with_model(model: dict, planned) -> dict:
    """Estimate a backlog against a previously-learned, serialized model."""
    stats, size_models = _deserialize_model(model)
    if not stats:
        raise ValueError("No cost model yet — connect or upload data first.")
    pp = _tmp(planned)
    try:
        return _serialize_plan(estimate_plan(parse_planned(pp), stats, size_models))
    finally:
        os.unlink(pp)


def build_report(issues, usage, planned: Optional[object] = None, window_days: int = 30) -> dict:
    """Run the pipeline on uploaded JSON and return the serialized report."""
    work, events = _parse(issues, usage)
    result, stats, size_models = _fit(work, events)
    planned_items = None
    if planned:
        pp = _tmp(planned)
        try:
            planned_items = parse_planned(pp)
        finally:
            os.unlink(pp)
    return _report(work, result, stats, size_models, planned_items, window_days)


def _project_key(ticket_id) -> str:
    """The project/epic prefix of a ticket key: PROJ-123 → PROJ, #42 → '' (none).
    GitHub issue numbers have no prefix, so they roll up under the empty key."""
    s = str(ticket_id or "")
    return s.rsplit("-", 1)[0] if "-" in s else ""


def project_spend(report: dict) -> list[dict]:
    """Spend grouped by project/epic prefix, biggest first — a pick-list so users
    know which keys they can budget against."""
    if not report:
        return []
    agg: dict[str, float] = {}
    for t in report.get("tickets", []):
        key = _project_key(t.get("ticket_id"))
        if key:
            agg[key] = agg.get(key, 0.0) + t.get("cost_usd", 0.0)
    return [{"project": k, "spent_usd": round(v, 2)}
            for k, v in sorted(agg.items(), key=lambda kv: kv[1], reverse=True)]


def budget_statuses(report: dict, budgets: list[dict]) -> list[dict]:
    """Compute spend-vs-budget with pace projection from the stored report.

    Pace projection: the report covers `window_days`; we straight-line the spend
    to the budget's period. Status: over (already past, or projected past),
    warn (projected ≥ 80%), else ok — guardrails that flag *before* overspend.
    """
    tickets = report.get("tickets", []) if report else []
    total = (report.get("spend", {}) or {}).get("total_usd", 0.0) if report else 0.0
    window = (report.get("window_days") if report else None) or 30
    out = []
    for b in budgets:
        st, sid = b["scope_type"], b.get("scope_id")
        if st == "team":
            spent = sum(t.get("cost_usd", 0) for t in tickets if (t.get("team_id") or "") == sid)
        elif st == "class":
            spent = sum(t.get("cost_usd", 0) for t in tickets if t.get("task_class") == sid)
        elif st == "project":  # group by ticket-key prefix (PROJ-123 → PROJ)
            spent = sum(t.get("cost_usd", 0) for t in tickets
                        if _project_key(t.get("ticket_id")) == sid)
        else:  # overall
            spent = total
        period = b.get("period_days") or 30
        projected = spent / window * period if window else spent
        limit = b.get("limit_usd", 0) or 0
        if limit and (spent >= limit or projected > limit):
            status = "over"
        elif limit and projected >= 0.8 * limit:
            status = "warn"
        else:
            status = "ok"
        out.append({**b, "spent_usd": round(spent, 2), "projected_usd": round(projected, 2),
                    "pct_used": round(spent / limit, 3) if limit else 0.0, "status": status})
    return out


def sync(conn: dict, window_days: int = 30, transport=None) -> dict:
    """Pull live from the customer's connected sources and run the pipeline.

    `conn`: tracker creds + at least one AI-usage key (`anthropic_key` and/or
    `cursor_key`); usage events from both are merged. `transport` is the engine's
    HTTP seam — left None in production, injected in tests.
    """
    from outlay.ingest import (AnthropicAdminClient, CursorAdminClient,
                               GitHubIssuesClient, JiraClient, LinearClient)

    tracker = (conn.get("tracker") or "github").strip()
    ak = (conn.get("anthropic_key") or "").strip()
    ck = (conn.get("cursor_key") or "").strip()
    if not ak and not ck:
        raise ValueError("Add an Anthropic admin key and/or a Cursor admin key first.")

    now = datetime.now(timezone.utc)
    since = now - timedelta(days=window_days)
    starting_at = since.strftime("%Y-%m-%dT00:00:00Z")
    try:
        if tracker == "jira":
            base = (conn.get("jira_base_url") or "").strip()
            email = (conn.get("jira_email") or "").strip()
            tok = (conn.get("jira_token") or "").strip()
            if not (base and email and tok):
                raise ValueError("Add your Jira URL, email, and API token.")
            jql = (conn.get("jira_jql") or "").strip() or "updated >= -90d ORDER BY updated DESC"
            work = JiraClient(base_url=base, email=email, api_token=tok, transport=transport).pull(jql)
        elif tracker == "linear":
            key = (conn.get("linear_key") or "").strip()
            if not key:
                raise ValueError("Add your Linear API key.")
            work = LinearClient(api_key=key, transport=transport).pull()
        else:
            owner = (conn.get("github_owner") or "").strip()
            repo = (conn.get("github_repo") or "").strip()
            gh = (conn.get("github_token") or "").strip()
            if not (owner and repo and gh):
                raise ValueError("Add a GitHub repo + read-only token.")
            work = GitHubIssuesClient(token=gh, transport=transport).pull(owner, repo)
        events = []
        if ak:
            events += AnthropicAdminClient(api_key=ak, transport=transport).pull(starting_at)
        if ck:
            start_ms, end_ms = int(since.timestamp() * 1000), int(now.timestamp() * 1000)
            events += CursorAdminClient(api_key=ck, transport=transport).pull(start_ms, end_ms)
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001 — network / auth → clean message
        raise ValueError(f"Couldn't sync from your sources: {e}") from e

    result, stats, size_models = _fit(work, events)
    return _report(work, result, stats, size_models, None, window_days)
