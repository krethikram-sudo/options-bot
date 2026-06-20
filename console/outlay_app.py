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
from outlay.ingest import parse_anthropic_usage, parse_bedrock_log_text, parse_github_issues
from outlay.recommend import recommend
from outlay.serialize import to_dict
from outlay.size import fit_size_models
from outlay.estimate import estimate_plan, parse_planned


def _tmp(text) -> str:
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    f.write(text if isinstance(text, str) else json.dumps(text))
    f.close()
    return f.name


def _looks_like_bedrock(usage) -> bool:
    """Heuristic: AWS Bedrock invocation logs carry `modelId` / a ModelInvocationLog
    schema tag, which the Anthropic per-call usage shape never does."""
    text = usage if isinstance(usage, str) else json.dumps(usage)
    head = (text or "").strip()[:2000]
    return "ModelInvocationLog" in head or '"modelId"' in head


def _parse_usage(usage):
    """Parse pasted/uploaded AI usage, auto-detecting the source: AWS Bedrock
    invocation logs (JSON or JSONL export) or Anthropic per-call usage JSON."""
    if _looks_like_bedrock(usage):
        try:
            return parse_bedrock_log_text(usage if isinstance(usage, str) else json.dumps(usage))
        except Exception as e:  # noqa: BLE001 — clean message for the UI
            raise ValueError(f"Couldn't read the Bedrock invocation logs: {e}") from e
    up = _tmp(usage)
    try:
        return parse_anthropic_usage(up)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Couldn't read the AI-usage data: {e}") from e
    finally:
        os.unlink(up)


def _parse(issues, usage):
    """Parse uploaded JSON into work items + usage events. Raises ValueError."""
    ip = _tmp(issues)
    try:
        work = parse_github_issues(ip)
    except Exception as e:  # noqa: BLE001 — clean message for the UI
        raise ValueError(f"Couldn't read the tracker data: {e}") from e
    finally:
        os.unlink(ip)
    return work, _parse_usage(usage)


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


def _people_spend(result) -> list[dict]:
    """Spend per engineer from costed events (user→cost), biggest first. Honest
    about coverage: events without a resolved user roll up under '(unattributed)'.
    Each engineer's top model is shown to surface premium-model-on-cheap-work."""
    total = result.total_cost or 0.0
    agg: dict[str, dict] = {}
    for r in result.rows:
        key = r.user or "(unattributed)"
        a = agg.setdefault(key, {"user": key, "spent_usd": 0.0, "events": 0, "by_model": {}})
        a["spent_usd"] += r.cost_usd
        a["events"] += 1
        a["by_model"][r.model] = a["by_model"].get(r.model, 0.0) + r.cost_usd
    out = []
    for a in sorted(agg.values(), key=lambda x: x["spent_usd"], reverse=True):
        top_model = max(a["by_model"], key=a["by_model"].get) if a["by_model"] else "—"
        out.append({"user": a["user"], "spent_usd": round(a["spent_usd"], 2),
                    "events": a["events"], "top_model": top_model,
                    "share": round(a["spent_usd"] / total, 4) if total else 0.0})
    return out


def _team_spend(result) -> list[dict]:
    """Spend per team / cost-center (user→team from the identity graph), biggest
    first. Honest about coverage: events with no resolved team roll up under
    '(unassigned)'. This is the finance/FinOps allocation view."""
    total = result.total_cost or 0.0
    agg: dict[str, dict] = {}
    for r in result.rows:
        key = getattr(r, "team_id", None) or "(unassigned)"
        a = agg.setdefault(key, {"team": key, "spent_usd": 0.0, "events": 0})
        a["spent_usd"] += r.cost_usd
        a["events"] += 1
    out = []
    for a in sorted(agg.values(), key=lambda x: x["spent_usd"], reverse=True):
        out.append({"team": a["team"], "spent_usd": round(a["spent_usd"], 2),
                    "events": a["events"],
                    "share": round(a["spent_usd"] / total, 4) if total else 0.0})
    return out


def _report(work, result, stats, size_models, planned_items=None, window_days: int = 30) -> dict:
    recs = recommend(result, horizon_scale=30.0 / max(window_days, 1))
    cal = backtest(result, work)
    fc = forecast_roadmap([w for w in work if w.is_open], stats, size_models)
    data = to_dict(result, stats, fc, find_anomalies(result, stats), recs,
                   calibration=cal, window_days=window_days)
    data["people"] = _people_spend(result)  # per-engineer spend rollup
    data["team_spend"] = _team_spend(result)  # per-team / cost-center rollup (finance view)
    data["class_spend"] = class_spend(data)  # spend by work type (FinOps view)
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


_SAMPLE_PLAN = ('{"items":[{"id":"PROJ-201","title":"Add SSO (SAML + SCIM)",'
                '"requirements":"Multi-tenant SAML, SCIM provisioning, audit log","points":8},'
                '{"id":"PROJ-202","title":"Fix flaky checkout test","points":2},'
                '{"id":"PROJ-203","title":"Migrate billing to new pricing engine",'
                '"requirements":"Backfill historical invoices, dual-write window","points":13}]}')


def sample_report() -> dict:
    """Build a fully-populated report from the bundled fixtures so a prospect can
    see the product live before connecting any keys. Flagged `_sample` so the UI
    can label it honestly and let them clear it."""
    from pathlib import Path
    fix = Path(__file__).resolve().parent.parent / "outlay" / "fixtures"
    report = build_report((fix / "github_issues.json").read_text(),
                          (fix / "anthropic_usage.json").read_text(),
                          planned=_SAMPLE_PLAN)
    report["_sample"] = True
    return report


def _project_key(ticket_id) -> str:
    """The project/epic prefix of a ticket key: PROJ-123 → PROJ, #42 → '' (none).
    GitHub issue numbers have no prefix, so they roll up under the empty key."""
    s = str(ticket_id or "")
    return s.rsplit("-", 1)[0] if "-" in s else ""


def class_spend(report: dict) -> list[dict]:
    """Spend grouped by work type (feature / bugfix / refactor / …), biggest first
    — the core FinOps view, and the same axis the savings recs act on."""
    if not report:
        return []
    total = (report.get("spend", {}) or {}).get("total_usd", 0.0)
    agg: dict[str, dict] = {}
    for t in report.get("tickets", []):
        tc = t.get("task_class") or "unknown"
        a = agg.setdefault(tc, {"task_class": tc, "spent_usd": 0.0, "tickets": 0})
        a["spent_usd"] += t.get("cost_usd", 0.0)
        a["tickets"] += 1
    out = []
    for a in sorted(agg.values(), key=lambda x: x["spent_usd"], reverse=True):
        out.append({"task_class": a["task_class"], "spent_usd": round(a["spent_usd"], 2),
                    "tickets": a["tickets"],
                    "share": round(a["spent_usd"] / total, 4) if total else 0.0})
    return out


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


def report_csv(report: dict, view: str = "tickets") -> str:
    """Serialize a slice of the report to CSV for finance/sheets export.
    view: tickets (spend per ticket) | people (spend per engineer) | savings."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    report = report or {}
    if view == "people":
        w.writerow(["engineer", "spend_usd", "share_pct", "top_model", "events"])
        for p in report.get("people", []):
            w.writerow([p.get("user"), p.get("spent_usd"), round(p.get("share", 0) * 100, 1),
                        p.get("top_model"), p.get("events")])
    elif view == "classes":
        w.writerow(["work_type", "tickets", "spend_usd", "share_pct"])
        for c in report.get("class_spend", []):
            w.writerow([c.get("task_class"), c.get("tickets"), c.get("spent_usd"),
                        round(c.get("share", 0) * 100, 1)])
    elif view == "savings":
        w.writerow(["work_type", "from_model", "to_model", "projected_savings_usd", "confidence"])
        for r in report.get("recommendations", []):
            w.writerow([r.get("task_class"), r.get("incumbent_model"), r.get("candidate_model"),
                        r.get("projected_savings_usd"), r.get("confidence")])
    else:  # tickets
        w.writerow(["ticket_id", "task_class", "status", "cost_usd", "rework_iterations", "team_id"])
        for t in report.get("tickets", []):
            w.writerow([t.get("ticket_id"), t.get("task_class"), t.get("status"),
                        t.get("cost_usd"), t.get("rework_iterations"), t.get("team_id")])
    return buf.getvalue()


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
