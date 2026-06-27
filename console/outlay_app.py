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
from outlay.ingest import (parse_anthropic_usage, parse_bedrock_cost_text,
                            parse_bedrock_log_text, parse_github_issues,
                            parse_openai_costs_text, parse_openai_usage_text,
                            parse_vertex_cost_text, parse_vertex_log_text)
from outlay.proof import cost_fidelity
from outlay.recommend import recommend
from outlay.serialize import to_dict
from outlay.size import fit_size_models
from outlay.estimate import estimate_plan, parse_planned


# Live-sync lookback. We pull a 90-day (rolling quarter) window so the very first
# sync backfills a rich dashboard on day one — enough history for per-team/model
# breakdowns, unit economics, anomaly detection, and forecast calibration — instead
# of a sparse 30-day slice. Every sync uses the same window, so snapshot-to-snapshot
# trends stay apples-to-apples, and a 90-day rolling view lines up with the quarterly
# budget/forecast framing the product already speaks in.
SYNC_WINDOW_DAYS = 90


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


def _looks_like_vertex(usage) -> bool:
    """Google Vertex (Anthropic) request-response logs carry a publishers/anthropic
    path or a Cloud Logging `jsonPayload`/`resource.labels.model_id` shape."""
    text = usage if isinstance(usage, str) else json.dumps(usage)
    head = (text or "").strip()[:2000]
    return "publishers/anthropic" in head or ('"jsonPayload"' in head and '"model_id"' in head)


def _looks_like_openai(usage) -> bool:
    """OpenAI/Azure usage carries gpt-* / o1 / o3 model ids or an input_cached_tokens field."""
    text = usage if isinstance(usage, str) else json.dumps(usage)
    head = (text or "").strip()[:2000]
    return ('"gpt-' in head or '"o1' in head or '"o3' in head
            or "input_cached_tokens" in head)


def _parse_usage(usage):
    """Parse pasted/uploaded AI usage, auto-detecting the source: AWS Bedrock
    invocation logs, Google Vertex (Claude) logs, or Anthropic per-call usage JSON."""
    text = usage if isinstance(usage, str) else json.dumps(usage)
    if _looks_like_vertex(usage):
        try:
            return parse_vertex_log_text(text)
        except Exception as e:  # noqa: BLE001 — clean message for the UI
            raise ValueError(f"Couldn't read the Vertex logs: {e}") from e
    if _looks_like_bedrock(usage):
        try:
            return parse_bedrock_log_text(text)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"Couldn't read the Bedrock invocation logs: {e}") from e
    if _looks_like_openai(usage):
        try:
            return parse_openai_usage_text(text)
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"Couldn't read the OpenAI usage data: {e}") from e
    up = _tmp(usage)
    try:
        return parse_anthropic_usage(up)
    except Exception as e:  # noqa: BLE001
        raise ValueError(f"Couldn't read the AI-usage data: {e}") from e
    finally:
        os.unlink(up)


def _pricing_fidelity(events) -> Optional[dict]:
    """Spend that was priced by *nearest-tier fallback* because the model id wasn't
    in our price book — e.g. a model that launched after our last rate update. We
    surface it so an unrecognized model never silently mis-costs the bill (and the
    customer knows which rates to ask us to add). None when everything was priced
    from an exact rate."""
    from outlay.pricing import cost_usd, model_is_known
    fb: dict[str, float] = {}
    fb_usd = total = 0.0
    for e in events:
        c = cost_usd(e)
        total += c
        if not model_is_known(e.model):
            fb_usd += c
            fb[e.model] = fb.get(e.model, 0.0) + c
    if fb_usd <= 0:
        return None
    return {
        "fallback_usd": round(fb_usd, 2),
        "fallback_share": round(fb_usd / total, 4) if total else 0.0,
        "models": sorted(fb, key=fb.get, reverse=True)[:8],
    }


def reconcile(report: dict, invoice_usd, source: str, window_days: int = 30) -> dict:
    """Attach a reconciliation block: our token-normalized total vs the provider's
    own *billed* figure. The same shape for every provider, so business sees one
    'computed vs billed · within N%' line regardless of where the spend ran. A
    non-positive/absent invoice is a no-op (we never show a bogus 0% reconciliation)."""
    try:
        invoice_usd = float(invoice_usd)
    except (TypeError, ValueError):
        return report
    if invoice_usd <= 0:
        return report
    computed = (report.get("spend") or {}).get("total_usd", 0.0)
    report["reconciliation"] = {
        "source": source,
        "invoice_usd": round(invoice_usd, 2),
        "computed_usd": round(computed, 2),
        "delta_usd": round(computed - invoice_usd, 2),
        "delta_pct": round((computed - invoice_usd) / invoice_usd * 100, 1),
        "window_days": window_days,
    }
    return report


_DQ_RANK = {"good": 0, "fair": 1, "poor": 2, "na": -1}


def data_quality(report: dict, conn: dict | None = None, now: float | None = None) -> dict:
    """A single 'can business trust these numbers?' verdict, rolled up from the signals
    that are otherwise scattered across the UI (coverage, reconciliation, pricing
    fidelity, sync freshness). Returns {score, checks:[{key,label,status,detail}]}.
    `status` is good|fair|poor, or 'na' when a check doesn't apply (it never drags
    the overall score down). Overall score = the worst applicable check."""
    import time as _time
    report = report or {}
    conn = conn or {}
    sp = report.get("spend") or {}
    checks: list[dict] = []

    # 1. Ticket coverage — how much spend mapped to a specific work item.
    total = sp.get("total_usd", 0.0)
    cov = sp.get("ticket_coverage", 0.0)
    if total <= 0:
        checks.append({"key": "coverage", "label": "Ticket coverage", "status": "na",
                       "detail": "No spend in the window yet."})
    else:
        cstat = "good" if cov >= 0.8 else "fair" if cov >= 0.5 else "poor"
        checks.append({"key": "coverage", "label": "Ticket coverage", "status": cstat,
                       "detail": f"{cov*100:.0f}% of spend is attributed to a specific ticket."})

    # 2. Reconciliation — computed vs the provider's billed figure.
    rec = report.get("reconciliation")
    if not rec:
        checks.append({"key": "reconciliation", "label": "Invoice reconciliation", "status": "na",
                       "detail": "No provider invoice/export to reconcile against yet."})
    else:
        dp = abs(rec.get("delta_pct", 0.0))
        rstat = "good" if dp <= 5 else "fair" if dp <= 15 else "poor"
        checks.append({"key": "reconciliation", "label": "Invoice reconciliation", "status": rstat,
                       "detail": f"Computed total is within {dp:.1f}% of the {rec.get('source','provider')} invoice."})

    # 3. Pricing fidelity — was any spend priced by nearest-tier fallback?
    pf = report.get("pricing_fidelity") or {}
    fshare = pf.get("fallback_share", 0.0)
    if not pf or fshare <= 0:
        checks.append({"key": "pricing", "label": "Pricing fidelity", "status": "good",
                       "detail": "Every model was priced from an exact rate."})
    else:
        pstat = "fair" if fshare < 0.05 else "poor"
        checks.append({"key": "pricing", "label": "Pricing fidelity", "status": pstat,
                       "detail": f"{fshare*100:.0f}% was priced at the nearest tier (unrecognized model id)."})

    # 4. Freshness — is the data current?
    synced_at = conn.get("synced_at")
    asy = conn.get("auto_sync_hours") or 0
    fails = conn.get("sync_fail_count") or 0
    if not synced_at:
        checks.append({"key": "freshness", "label": "Data freshness", "status": "na",
                       "detail": "No successful sync recorded yet."})
    else:
        age_h = ((now or _time.time()) - synced_at) / 3600
        if asy and fails >= 2:
            fstat, det = "poor", f"Auto-sync has failed {fails}× — showing the last good data."
        elif asy:
            fstat = "good" if age_h <= asy else "fair" if age_h <= 2 * asy else "poor"
            det = f"Last refreshed {age_h/24:.0f} day(s) ago (auto-sync every {asy}h)."
        else:  # manual sync
            fstat = "good" if age_h <= 168 else "fair" if age_h <= 720 else "poor"
            det = f"Last refreshed {age_h/24:.0f} day(s) ago (manual sync)."
        checks.append({"key": "freshness", "label": "Data freshness", "status": fstat, "detail": det})

    worst = max((_DQ_RANK[c["status"]] for c in checks), default=-1)
    score = {0: "good", 1: "fair", 2: "poor"}.get(worst, "na")
    return {"score": score, "checks": checks}


_CLOSED_STATUSES = {"closed", "done", "resolved", "merged", "completed", "closed/done"}


def unit_economics(report: dict) -> Optional[dict]:
    """Reframe raw spend as efficiency — cost *per ticket* and per *closed* ticket,
    the rework tax, and the priciest work types per unit. The differentiated FinOps
    metric (unit cost), computed from the attributed tickets we already have. Returns
    None when there's nothing attributed to divide by (the number would be noise)."""
    tickets = [t for t in ((report or {}).get("tickets") or []) if (t.get("cost_usd") or 0) > 0]
    n = len(tickets)
    if n == 0:
        return None
    total = sum(t.get("cost_usd", 0.0) for t in tickets)
    closed = [t for t in tickets if str(t.get("status") or "").lower() in _CLOSED_STATUSES]
    closed_cost = sum(t.get("cost_usd", 0.0) for t in closed)
    reworked = [t for t in tickets if (t.get("rework_iterations") or 0) > 0]
    rework_cost = sum(t.get("cost_usd", 0.0) for t in reworked)
    # Priciest work types per unit (avg cost per ticket within the class).
    by_class = []
    for c in (report.get("class_spend") or []):
        ntix = c.get("tickets") or 0
        if ntix:
            by_class.append({"task_class": c.get("task_class"),
                             "per_ticket_usd": round((c.get("spent_usd", 0.0)) / ntix, 2),
                             "tickets": ntix})
    by_class.sort(key=lambda x: x["per_ticket_usd"], reverse=True)
    return {
        "tickets": n,
        "cost_per_ticket_usd": round(total / n, 2),
        "closed_tickets": len(closed),
        "cost_per_closed_usd": round(closed_cost / len(closed), 2) if closed else None,
        "rework_share": round(rework_cost / total, 4) if total else 0.0,
        "reworked_tickets": len(reworked),
        "by_class": by_class[:5],
    }


def parse_cost_export(text):
    """Auto-detect and sum a pasted *provider cost/billing export* into (usd, source).

    Lets a customer reconcile any provider by pasting the cost export they can
    already pull from their console — AWS Cost Explorer, GCP Cloud Billing (BigQuery
    export), or the OpenAI Costs API — no extra keys. Returns (0.0, "") when the
    text is empty or unrecognized."""
    text = (text if isinstance(text, str) else json.dumps(text or "")).strip()
    if not text:
        return 0.0, ""
    # We don't do FX. If the export declares a non-USD currency, refuse rather than
    # silently compare a EUR/GBP invoice against a USD-computed total.
    import re as _re
    codes = {c.lower() for c in _re.findall(r'"(?:currency|Unit)"\s*:\s*"([A-Za-z]{3})"', text)}
    if codes and not codes <= {"usd"}:
        return 0.0, "non_usd"
    head = text[:2000]
    if "ResultsByTime" in head or "UnblendedCost" in head:
        return parse_bedrock_cost_text(text), "aws_cost_explorer"
    if '"credits"' in head or "BigQuery" in head or ('"cost"' in head and '"service"' in head):
        return parse_vertex_cost_text(text), "gcp_cloud_billing"
    if "organization.costs" in head or ('"amount"' in head and '"value"' in head):
        return parse_openai_costs_text(text), "openai_costs"
    return 0.0, ""


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


_DOMAIN_RE = __import__("re").compile(r"^[\w.-]+\.[a-z]{2,}$", __import__("re").I)


def identity_graph(text):
    """Parse a customer's identity map (one `identifier, team` / `identifier -> team`
    per line) into an `IdentityGraph`. An identifier with a leading `@` or a bare
    `acme.com` maps a whole email **domain**; anything else is an exact user/email
    or API-key id. Powers team / cost-center allocation when tickets don't carry a
    team — the business lead view and the low-coverage fallback."""
    from outlay.join import IdentityGraph
    u2t: dict[str, str] = {}
    d2t: dict[str, str] = {}
    k2u: dict[str, str] = {}
    for raw in (text or "").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if "->" in line:
            ident, team = line.split("->", 1)
        elif "," in line:
            ident, team = line.split(",", 1)
        elif "\t" in line:
            ident, team = line.split("\t", 1)
        else:
            continue
        ident, team = ident.strip(), team.strip()
        if not ident or not team:
            continue
        if ident.startswith("@"):
            d2t[ident[1:].lower()] = team
        elif "@" not in ident and _DOMAIN_RE.match(ident):
            d2t[ident.lower()] = team
        else:
            u2t[ident] = team
            k2u[ident] = ident  # so a key-identified event (no email) also resolves
    return IdentityGraph(key_to_user=k2u, user_to_team=u2t, domain_to_team=d2t)


def _fit(work, events, identity=None):
    from outlay.join import JoinEngine
    result = attribute(events, work, engine=JoinEngine(work, identity=identity))
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
    '(unassigned)'. This is the business/FinOps allocation view."""
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


def _report(work, result, stats, size_models, planned_items=None, window_days: int = 30,
            events=None) -> dict:
    recs = recommend(result, horizon_scale=30.0 / max(window_days, 1))
    cal = backtest(result, work)
    fc = forecast_roadmap([w for w in work if w.is_open], stats, size_models)
    data = to_dict(result, stats, fc, find_anomalies(result, stats), recs,
                   calibration=cal, window_days=window_days)
    data["people"] = _people_spend(result)  # per-engineer spend rollup
    data["team_spend"] = _team_spend(result)  # per-team / cost-center rollup (business view)
    data["class_spend"] = class_spend(data)  # spend by work type (FinOps view)
    data["_model"] = _serialize_model(stats, size_models)  # for the backlog estimator
    # Cache-aware vs naive costing gap on the customer's own usage — the proof that
    # the headline spend number is the correct one, surfaced in-product (Overview).
    if events:
        data["cost_fidelity"] = cost_fidelity(events).as_dict()
        pf = _pricing_fidelity(events)
        if pf:
            data["pricing_fidelity"] = pf  # unrecognized models priced by nearest tier
    if planned_items:
        data["estimate"] = _serialize_plan(estimate_plan(planned_items, stats, size_models))
    else:
        # Default: price the open backlog from the tracker you already connected, so
        # the Estimate page works out of the box — no JSON paste required. Flagged so
        # the UI can label it "your open backlog" vs a hand-pasted what-if plan.
        open_items = [w for w in work if w.is_open]
        if open_items:
            est = _serialize_plan(estimate_plan(open_items, stats, size_models))
            est["from_backlog"] = True
            data["estimate"] = est
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


def build_report(issues, usage, planned: Optional[object] = None, window_days: int = 30,
                 identity_text: Optional[str] = None) -> dict:
    """Run the pipeline on uploaded JSON and return the serialized report.

    `identity_text` (optional) maps identifiers/domains → teams so spend allocates
    by cost-center even when the tracker doesn't tag tickets with a team."""
    work, events = _parse(issues, usage)
    result, stats, size_models = _fit(work, events, identity=identity_graph(identity_text))
    planned_items = None
    if planned:
        pp = _tmp(planned)
        try:
            planned_items = parse_planned(pp)
        finally:
            os.unlink(pp)
    return _report(work, result, stats, size_models, planned_items, window_days, events=events)


def sample_report() -> dict:
    """Build a fully-populated report from the bundled fixtures so a prospect can
    see the product live before connecting any keys. Flagged `_sample` so the UI
    can label it honestly and let them clear it."""
    from pathlib import Path
    fix = Path(__file__).resolve().parent.parent / "outlay" / "fixtures"
    # Rich demo dataset (dozens of tickets across teams) so the dashboard a
    # prospect sees is realistic — believable coverage + a measured accuracy
    # number, not a 6-ticket toy. Regenerate with `python -m outlay.fixtures.gen_demo`.
    # No `planned=`: the Estimate page prices the connected *open* backlog by default
    # (what a real customer sees), so the demo matches reality. window_days matches the
    # live sync (SYNC_WINDOW_DAYS) so pace projections over program/budget periods are
    # realistic, not 3x inflated by a stale 30-day window.
    report = build_report((fix / "demo_github_issues.json").read_text(),
                          (fix / "demo_anthropic_usage.json").read_text(),
                          window_days=SYNC_WINDOW_DAYS)
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


def _scope_match(ticket: dict, scope_type: str, scope_id) -> bool:
    if scope_type == "team":
        return (ticket.get("team_id") or "") == scope_id
    if scope_type == "class":
        return ticket.get("task_class") == scope_id
    if scope_type == "project":
        return _project_key(ticket.get("ticket_id")) == scope_id
    return True  # 'overall' matches everything


def _scope_spent(tickets: list, total: float, scope_type: str, scope_id) -> float:
    if scope_type == "overall":
        return total
    return sum(t.get("cost_usd", 0) for t in tickets if _scope_match(t, scope_type, scope_id))


def _pace_status(spent: float, limit: float, window: int, period: int) -> tuple:
    """(projected_usd, status) — straight-line the window's spend to the budget
    period; over if already past or projected past, warn at ≥80%, else ok."""
    projected = spent / window * period if window else spent
    if limit and (spent >= limit or projected > limit):
        status = "over"
    elif limit and projected >= 0.8 * limit:
        status = "warn"
    else:
        status = "ok"
    return round(projected, 2), status


_STATUS_RANK = {"ok": 0, "warn": 1, "over": 2}


def _worse(a: str, b: str) -> str:
    return a if _STATUS_RANK.get(a, 0) >= _STATUS_RANK.get(b, 0) else b


def program_spend(report: dict, program: dict) -> float:
    """Cumulative spend attributed to one program from a report (a ticket matching ANY
    of the program's members counts once — no double-count across overlapping scopes)."""
    members = program.get("members") or []
    if not members:
        return 0.0
    total = (report.get("spend", {}) or {}).get("total_usd", 0.0) if report else 0.0
    if any(m.get("scope_type") == "overall" for m in members):
        return total
    tickets = report.get("tickets", []) if report else []
    return sum(t.get("cost_usd", 0) for t in tickets
               if any(_scope_match(t, m.get("scope_type"), m.get("scope_id")) for m in members))


def program_spends(report: dict, programs: list[dict]) -> dict:
    """{program_id: spent_usd} — the per-program snapshot persisted on each sync."""
    return {p["id"]: round(program_spend(report, p), 4) for p in programs if p.get("id") is not None}


def commitment_view(report: dict | None, history: list[dict] | None = None) -> dict | None:
    """Commitment & procurement optimization read for the console (advisory).

    Uses the per-sync spend snapshots (`outlay_history`) as a monthly run-rate
    series: each snapshot's window total is normalized to a month, decomposed into
    a steady floor vs spike, and run through the committed-spend recommender. With
    too few snapshots we fall back to the latest report's run-rate as a single
    point and say so — the estimate sharpens as sync history accumulates.
    """
    from outlay.commitment import (decompose, default_ratecard, recommend_commitment)

    if not report:
        return None
    spend = report.get("spend", {}) or {}
    total = float(spend.get("total_usd", 0.0) or 0.0)
    window = report.get("window_days") or 30
    if total <= 0:
        return None
    to_month = 30.0 / float(window)

    # Monthly run-rate series from the snapshots (oldest→newest), normalized to a month.
    hist = history or []
    series = [float(h.get("total_usd", 0.0) or 0.0) * to_month for h in hist if (h.get("total_usd") or 0) > 0]
    enough = len(series) >= 4
    if enough:
        profile = decompose(series)
        forecast_month = profile.median_usd
    else:
        # Single-point fallback: treat the current run-rate as the floor with a
        # conservative steadiness so we never over-recommend on thin data.
        run_rate = total * to_month
        profile = decompose([run_rate])
        forecast_month = run_rate

    # Blended realized $/Mtok from the report when token counts are present; else
    # leave the rate-card default and flag tiers as illustrative either way.
    blended = None
    toks = spend.get("total_tokens") or report.get("total_tokens")
    if toks:
        blended = total / (float(toks) / 1_000_000.0)
    card = default_ratecard(on_demand_usd_per_mtok=blended or 9.0)

    scenarios = recommend_commitment(profile, forecast_month, card, floor_periods=1)
    best = max(scenarios, key=lambda s: s.net_savings_usd) if scenarios else None
    return {
        "monthly_on_demand_usd": round(forecast_month, 2),
        "floor_usd": round(profile.floor_usd, 2),
        "median_usd": round(profile.median_usd, 2),
        "peak_usd": round(profile.peak_usd, 2),
        "steadiness": round(profile.steadiness, 4),
        "cov": round(profile.cov, 4),
        "n_snapshots": len(series),
        "enough_history": enough,
        "blended_rate": round(blended, 2) if blended else None,
        "tiers": [{"threshold_usd": t.threshold_usd, "discount": t.discount} for t in card.tiers],
        "scenarios": [
            {"label": s.label, "commit_usd": s.commit_usd, "discount": s.discount,
             "billed_usd": s.billed_usd, "forfeited_usd": s.forfeited_usd,
             "net_savings_usd": s.net_savings_usd, "effective_savings_rate": s.effective_savings_rate,
             "forfeit_risk": s.forfeit_risk}
            for s in scenarios
        ],
        "recommended": (
            {"label": best.label, "commit_usd": best.commit_usd,
             "net_savings_usd": best.net_savings_usd,
             "effective_savings_rate": best.effective_savings_rate,
             "forfeit_risk": best.forfeit_risk}
            if best and best.net_savings_usd > 0 else None
        ),
    }


def program_statuses(report: dict, programs: list[dict], histories: dict | None = None) -> list[dict]:
    """Spend-vs-budget for *programs* — named budgets spanning several teams /
    projects / work types. Attaches real-time **pacing** (actual-to-date vs the budget's
    expected pace) when a per-program spend history is supplied."""
    window = (report.get("window_days") if report else None) or 30
    histories = histories or {}
    out = []
    for p in programs:
        spent = program_spend(report, p)
        limit = p.get("limit_usd", 0) or 0
        period = p.get("period_days") or 90
        projected, status = _pace_status(spent, limit, window, period)
        row = {**p, "spent_usd": round(spent, 2), "projected_usd": projected,
               "pct_used": round(spent / limit, 3) if limit else 0.0, "status": status}
        row["timeline"] = _program_timeline(p, spent, projected, limit, period)
        row["pacing"] = program_pacing(p, histories.get(p.get("id"), []), spent)
        row["progress"] = program_earned_value(report, p)
        # Budget headroom (spent/run-rate vs cap) — prefer the time-based pacing read.
        budget_status = row["pacing"]["status"] if row["pacing"].get("ready") else status
        # Execution quality (forecast vs actual on completed work) — a separate axis.
        exec_status = row["progress"]["status"] if (row["progress"] and row["progress"].get("ready")) else "ok"
        # A program needs attention if EITHER is bad → take the worse.
        row["status"] = _worse(budget_status, exec_status)
        out.append(row)
    return out


def _program_timeline(program: dict, spent: float, projected: float, limit: float,
                      period_days: int) -> dict:
    """Calendar timeline + month-by-month projection for a program. Straight-lines the
    current run-rate (spend so far → projected end-of-period) across the program's
    months, and compares each month's cumulative projection to a pro-rated slice of
    the cap so business can see *when* a program is set to breach, not just whether."""
    import calendar
    from datetime import datetime, timezone

    now = datetime.now(timezone.utc)
    start_ts = program.get("start_ts")
    end_ts = program.get("end_ts")
    start = (datetime.fromtimestamp(start_ts, timezone.utc) if start_ts
             else now - timedelta(days=period_days))
    end = (datetime.fromtimestamp(end_ts, timezone.utc) if end_ts
           else start + timedelta(days=period_days))
    total_days = max(1.0, (end - start).total_seconds() / 86400)
    elapsed_days = min(total_days, max(0.0, (now - start).total_seconds() / 86400))
    frac_elapsed = elapsed_days / total_days
    # End-of-program projection: what we've spent plus the run-rate over the remaining
    # time. `projected` from _pace_status is the period-normalized run-rate total.
    run_rate_total = max(projected, spent)
    per_day = run_rate_total / total_days

    # Walk month buckets from start to end; cumulative projected vs pro-rated cap.
    months = []
    cur = datetime(start.year, start.month, 1, tzinfo=timezone.utc)
    while cur <= end:
        last_day = calendar.monthrange(cur.year, cur.month)[1]
        m_end = datetime(cur.year, cur.month, last_day, 23, 59, 59, tzinfo=timezone.utc)
        seg_start = max(start, cur)
        seg_end = min(end, m_end)
        cum_days = max(0.0, (seg_end - start).total_seconds() / 86400)
        cum_proj = round(min(run_rate_total, per_day * cum_days), 2)
        cap_slice = round(limit * (cum_days / total_days), 2) if limit else 0.0
        is_past = m_end < now
        months.append({
            "label": cur.strftime("%b %Y"),
            "cum_projected_usd": cum_proj,
            "cap_to_date_usd": cap_slice,
            "over": bool(limit and cum_proj > limit),
            "past": is_past,
        })
        # advance one month
        cur = datetime(cur.year + (cur.month // 12), (cur.month % 12) + 1, 1, tzinfo=timezone.utc)

    breach = next((m["label"] for m in months if m["over"]), None)
    return {
        "start": start.strftime("%b %-d, %Y"),
        "end": end.strftime("%b %-d, %Y"),
        "frac_elapsed": round(frac_elapsed, 4),
        "days_left": max(0, round(total_days - elapsed_days)),
        "projected_end_usd": round(run_rate_total, 2),
        "months": months,
        "breach_month": breach,
    }


# Pacing tolerances + minimum signal before we flag confidently (honesty guardrail:
# projections are unstable when little has elapsed / few measurements exist).
PACE_OVER_PCT = 0.10          # >10% above the budget's expected pace ⇒ at-risk
PACE_UNDER_PCT = -0.10        # >10% below ⇒ ahead of plan
PACE_MIN_ELAPSED = 0.15       # need ≥15% of the program elapsed, OR…
PACE_MIN_SNAPSHOTS = 2        # …≥2 measured snapshots, before a confident flag
BURN_WINDOW_DAYS = 14.0       # smoothing window for the recent burn rate


def program_pacing(program: dict, history: list[dict], current_spent: float,
                   now: float | None = None) -> dict:
    """Real-time budget pacing for an in-flight program: actual cumulative spend to
    date vs. the budget's *expected* pace (linear over the program's life), a smoothed
    burn rate, a projected end spend, and — if it's trending over — the projected
    breach **date**. Honest by construction: until enough has elapsed / been measured,
    `ready=False` and we say "gathering baseline" rather than cry wolf.

    `history` is this program's ascending [{ts, spent_usd}] snapshots; `current_spent`
    is the freshest actual (latest report)."""
    from datetime import datetime, timezone, timedelta

    nowt = now if now is not None else _now_ts()
    limit = program.get("limit_usd", 0) or 0
    period = program.get("period_days") or 90
    start_ts = program.get("start_ts") or (nowt - period * 86400)
    end_ts = program.get("end_ts") or (start_ts + period * 86400)
    total_days = max(1.0, (end_ts - start_ts) / 86400)
    elapsed_days = min(total_days, max(0.0, (nowt - start_ts) / 86400))
    remaining_days = max(0.0, total_days - elapsed_days)
    frac_elapsed = elapsed_days / total_days

    ac = float(current_spent or 0.0)                 # actual-to-date (freshest)
    pv = limit * frac_elapsed                         # planned-to-date (linear plan)
    variance_usd = ac - pv
    variance_pct = (ac / pv - 1.0) if pv > 0 else 0.0

    # Smoothed recent burn rate from history: latest vs. the earliest point within the
    # burn window. Falls back to the simple proportional rate (AC / elapsed) if we don't
    # have two usable snapshots yet.
    burn_per_day = (ac / elapsed_days) if elapsed_days > 0 else 0.0
    pts = sorted([h for h in history if h.get("ts")], key=lambda h: h["ts"])
    if len(pts) >= 2:
        latest = pts[-1]
        cutoff = latest["ts"] - BURN_WINDOW_DAYS * 86400
        earlier = next((p for p in pts if p["ts"] >= cutoff), pts[0])
        dt_days = (latest["ts"] - earlier["ts"]) / 86400
        if dt_days >= 0.5:
            burn_per_day = max(0.0, (latest["spent_usd"] - earlier["spent_usd"]) / dt_days)

    # Estimate-at-completion: blend the recent-burn extrapolation with the simple
    # proportional estimate so neither a spike nor a lull dominates.
    eac_runrate = ac + burn_per_day * remaining_days
    eac_prop = (ac / frac_elapsed) if frac_elapsed > 0 else ac
    eac = round((eac_runrate + eac_prop) / 2.0, 2) if len(pts) >= 2 else round(eac_prop, 2)

    # Projected breach date: when the extrapolated actual crosses the cap.
    breach_date = None
    if limit:
        if ac >= limit:
            breach_date = "now"
        elif burn_per_day > 0 and (ac + burn_per_day * remaining_days) > limit:
            days_to = (limit - ac) / burn_per_day
            breach_date = (datetime.fromtimestamp(nowt, timezone.utc)
                           + timedelta(days=days_to)).strftime("%b %-d, %Y")

    ready = bool(limit) and frac_elapsed > 0 and (len(pts) >= PACE_MIN_SNAPSHOTS
                                                  or frac_elapsed >= PACE_MIN_ELAPSED)
    if not ready:
        pace, status = "baseline", "ok"
    elif ac >= limit or (limit and eac > limit):
        pace = "projected_breach" if ac < limit else "over_budget"
        status = "over"
    elif (limit and eac >= 0.95 * limit) or variance_pct > PACE_OVER_PCT:
        pace, status = "over_pace", "warn"
    elif variance_pct < PACE_UNDER_PCT:
        pace, status = "ahead", "ok"
    else:
        pace, status = "on_track", "ok"

    return {
        "ready": ready,
        "status": status,                      # ok | warn | over (drives the existing colour)
        "pace": pace,                          # baseline|ahead|on_track|over_pace|projected_breach|over_budget
        "planned_to_date_usd": round(pv, 2),
        "actual_to_date_usd": round(ac, 2),
        "variance_usd": round(variance_usd, 2),
        "variance_pct": round(variance_pct, 4),
        "burn_per_day_usd": round(burn_per_day, 2),
        "projected_end_usd": eac,
        "over_budget_by_usd": round(max(0.0, eac - limit), 2) if limit else 0.0,
        "projected_breach_date": breach_date,
        "frac_elapsed": round(frac_elapsed, 4),
        "days_left": int(round(remaining_days)),
        "snapshots": len(pts),
    }


def _now_ts() -> float:
    import time as _t
    return _t.time()


# --- Progress / earned-value pacing (forecast vs actual on COMPLETED work) --- #
# This is the more accurate read the founder asked for: instead of pacing against
# calendar time, pace against *work actually completed*. For each completed component
# (ticket) we have its actual cost and a per-component forecast (its class's typical
# cost — the same robust class figure the anomaly detector uses). Comparing forecasted
# vs actual over completed work gives an on-track / not rating and a "how far off" %.
EV_MIN_DONE = 3            # need at least this many completed components before we rate
EV_OK_CPI = 0.92          # completed work within ~8% of forecast → on track
EV_WARN_CPI = 0.80        # 8–20% over forecast → watch; worse → off track


def program_earned_value(report: dict, program: dict) -> Optional[dict]:
    """On-track rating from forecast-vs-actual on a program's COMPLETED tickets.

    CPI = Σforecast(done) / Σactual(done) — ≥1 means completed components came in at or
    under their forecast; <1 means they ran hot. Progress = forecasted share of work done.
    Projected total = budget / CPI. Honest: returns ready=False ('gathering baseline')
    until enough components have completed."""
    if not report:
        return None
    tickets = report.get("tickets") or []
    members = program.get("members") or []
    if not tickets or not members:
        return None
    if any(m.get("scope_type") == "overall" for m in members):
        scoped = tickets
    else:
        scoped = [t for t in tickets
                  if any(_scope_match(t, m.get("scope_type"), m.get("scope_id")) for m in members)]
    if not scoped:
        return None
    # Per-component forecast = the class's typical (median) cost.
    cfc = {cs.get("task_class"): (cs.get("median_usd") or cs.get("mean_usd") or 0.0)
           for cs in (report.get("class_stats") or [])}

    def fc(t):
        return cfc.get(t.get("task_class")) or (t.get("cost_usd", 0.0) or 0.0)

    done = [t for t in scoped if str(t.get("status") or "").lower() in _CLOSED_STATUSES]
    forecast_done = sum(fc(t) for t in done)
    actual_done = sum(t.get("cost_usd", 0.0) or 0.0 for t in done)
    forecast_all = sum(fc(t) for t in scoped)
    n_done = len(done)
    ready = n_done >= EV_MIN_DONE and forecast_done > 0 and actual_done > 0

    cpi = (forecast_done / actual_done) if actual_done > 0 else 0.0
    progress = (forecast_done / forecast_all) if forecast_all > 0 else 0.0
    cost_variance_pct = ((actual_done - forecast_done) / forecast_done) if forecast_done > 0 else 0.0
    budget = program.get("limit_usd", 0) or 0
    # EVM estimate-at-completion: the total forecasted work, adjusted by how efficiently
    # completed work has tracked its forecast (BAC / CPI, with BAC = Σforecast over scoped work).
    projected_total = (forecast_all / cpi) if cpi > 0 else forecast_all
    over_budget_by = max(0.0, projected_total - budget) if budget else 0.0

    # Status is the *execution* read (are completed components costing what we forecast),
    # a separate axis from budget headroom — the caller combines the two.
    if not ready:
        pace, status = "baseline", "ok"
    elif cpi < EV_WARN_CPI:
        pace, status = "over_forecast", "over"          # completed work >25% over forecast
    elif cpi < EV_OK_CPI:
        pace, status = "over_pace", "warn"
    elif cpi > 1.08:
        pace, status = "under_forecast", "ok"
    else:
        pace, status = "on_track", "ok"

    return {
        "ready": ready,
        "status": status,                          # ok | warn | over
        "pace": pace,
        "rating": "on track" if status == "ok" else ("watch" if status == "warn" else "off track"),
        "cpi": round(cpi, 3),
        "progress_pct": round(progress, 4),        # forecasted share of work completed
        "forecast_done_usd": round(forecast_done, 2),
        "actual_done_usd": round(actual_done, 2),
        "cost_variance_pct": round(cost_variance_pct, 4),   # + = completed work over forecast
        "projected_total_usd": round(projected_total, 2),
        "over_budget_by_usd": round(over_budget_by, 2),
        "components_done": n_done,
        "components_total": len(scoped),
    }


def variance_report(statuses: list[dict], now: float | None = None) -> dict:
    """Finance-facing quarterly plan-vs-actual roll-up across programs. Consolidates the
    per-program pacing + earned-value reads into one table + totals + an on-track tally —
    the artifact finance pulls each quarter to see which programs are tracking to budget."""
    import datetime as _dt
    d = (_dt.datetime.fromtimestamp(now, _dt.timezone.utc) if now
         else _dt.datetime.now(_dt.timezone.utc))
    quarter = f"Q{(d.month - 1) // 3 + 1} {d.year}"

    rows, counts = [], {"on track": 0, "watch": 0, "off track": 0, "gathering baseline": 0}
    tb = ta = tp = tproj = tover = 0.0
    for s in statuses:
        budget = s.get("limit_usd", 0) or 0
        if not budget:
            continue
        actual = s.get("spent_usd", 0) or 0
        pc, pr = s.get("pacing") or {}, s.get("progress") or {}
        planned = pc.get("planned_to_date_usd") if pc.get("ready") else None
        if pr.get("ready"):                              # earned-value is the most accurate read
            projected, rating = pr.get("projected_total_usd", 0), pr.get("rating", "on track")
        elif pc.get("ready"):                            # else the time-based pacing
            projected = pc.get("projected_end_usd", 0)
            rating = {"ok": "on track", "warn": "watch", "over": "off track"}.get(pc.get("status"), "on track")
        else:
            projected, rating = s.get("projected_usd", 0) or 0, "gathering baseline"
        var_usd = (actual - planned) if planned is not None else None
        var_pct = (var_usd / planned) if (planned and var_usd is not None) else None
        over = max(0.0, (projected or 0) - budget)
        rows.append({
            "name": s.get("name"), "budget_usd": round(budget, 2),
            "actual_to_date_usd": round(actual, 2),
            "planned_to_date_usd": round(planned, 2) if planned is not None else None,
            "variance_usd": round(var_usd, 2) if var_usd is not None else None,
            "variance_pct": round(var_pct, 4) if var_pct is not None else None,
            "progress_pct": pr.get("progress_pct") if pr.get("ready") else None,
            "cost_variance_pct": pr.get("cost_variance_pct") if pr.get("ready") else None,
            "rating": rating, "projected_total_usd": round(projected or 0, 2),
            "over_budget_usd": round(over, 2),
        })
        tb += budget; ta += actual; tproj += (projected or 0); tover += over
        if planned is not None:
            tp += planned
        counts[rating] = counts.get(rating, 0) + 1
    return {
        "quarter": quarter, "rows": rows, "n": len(rows), "counts": counts,
        "totals": {"budget_usd": round(tb, 2), "actual_to_date_usd": round(ta, 2),
                   "planned_to_date_usd": round(tp, 2), "projected_total_usd": round(tproj, 2),
                   "over_budget_usd": round(tover, 2), "variance_usd": round(ta - tp, 2)},
    }


def variance_report_csv(rep: dict) -> str:
    """The quarterly variance report as CSV (for finance to load into a sheet)."""
    import csv
    import io
    buf = io.StringIO()
    w = csv.writer(buf)
    w.writerow(["program", "budget_usd", "actual_to_date_usd", "planned_to_date_usd",
                "variance_usd", "variance_pct", "progress_pct", "cost_variance_pct",
                "rating", "projected_total_usd", "over_budget_usd"])
    for r in rep.get("rows", []):
        w.writerow([r["name"], r["budget_usd"], r["actual_to_date_usd"], r["planned_to_date_usd"],
                    r["variance_usd"], r["variance_pct"], r["progress_pct"], r["cost_variance_pct"],
                    r["rating"], r["projected_total_usd"], r["over_budget_usd"]])
    return buf.getvalue()


def enforced_programs(report: dict, programs: list[dict]) -> list[dict]:
    """Programs the gateway should currently ENFORCE — i.e. enforce_mode='hard' and
    over their cap. Returns the action + members + numbers so the in-path client can
    cache this and decide per request by matching the call's attribution tags to a
    member scope. Read-only by design; this is just the verdict, never the traffic."""
    out = []
    for s in program_statuses(report, programs):
        if s.get("enforce_mode") == "hard" and s.get("status") == "over":
            out.append({
                "id": s.get("id"), "name": s.get("name"),
                "action": s.get("action") or "block",
                "floor_model": s.get("floor_model"),
                "members": s.get("members") or [],
                "spent_usd": s.get("spent_usd"), "limit_usd": s.get("limit_usd"),
                "projected_usd": s.get("projected_usd"), "period_days": s.get("period_days"),
            })
    return out


def program_decision(enforced: list[dict], ticket_id=None, team=None, task_class=None) -> dict:
    """Given the enforced-programs list, decide what to do with one request described
    by its attribution tags. 'block' wins over 'downgrade'; 'allow' when nothing
    matches. Lets the gateway (or a test) resolve a per-call verdict locally."""
    ticket_id = ticket_id or ""
    proj = _project_key(ticket_id) if ticket_id else ""
    matched = []
    for p in enforced:
        for m in p.get("members") or []:
            st, sid = m.get("scope_type"), m.get("scope_id")
            if (st == "overall"
                    or (st == "team" and team and team == sid)
                    or (st == "class" and task_class and task_class == sid)
                    or (st == "project" and proj and proj == sid)):
                matched.append(p)
                break
    if not matched:
        return {"decision": "allow"}
    block = next((p for p in matched if (p.get("action") or "block") == "block"), None)
    chosen = block or matched[0]
    return {"decision": chosen.get("action") or "block",
            "program": chosen.get("name"), "program_id": chosen.get("id"),
            "floor_model": chosen.get("floor_model")}


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
        spent = _scope_spent(tickets, total, b["scope_type"], b.get("scope_id"))
        limit = b.get("limit_usd", 0) or 0
        projected, status = _pace_status(spent, limit, window, b.get("period_days") or 30)
        out.append({**b, "spent_usd": round(spent, 2), "projected_usd": projected,
                    "pct_used": round(spent / limit, 3) if limit else 0.0, "status": status})
    return out


# FOCUS (FinOps Open Cost & Usage Specification) — the neutral, community standard
# for normalized cost+usage data. We emit FOCUS-aligned rows (standard column names)
# at the ticket grain with team/work-type Tags, so business can load Outlay's spend
# into any FOCUS-aware FinOps/BI tool. (Aligned, not formally certified-conformant.)
FOCUS_COLUMNS = [
    "BilledCost", "EffectiveCost", "BillingCurrency",
    "BillingPeriodStart", "BillingPeriodEnd", "ChargePeriodStart", "ChargePeriodEnd",
    "ProviderName", "ServiceCategory", "ServiceName", "ChargeCategory",
    "ChargeDescription", "ResourceId", "ResourceName", "Tags",
]


def focus_rows(report: dict, window_days: int = 30) -> list[dict]:
    """Per-ticket spend as FOCUS-aligned charge rows."""
    from datetime import datetime, timedelta, timezone
    report = report or {}
    wd = report.get("window_days") or window_days or 30
    end = datetime.now(timezone.utc).replace(microsecond=0)
    start = end - timedelta(days=wd)
    si, ei = start.isoformat(), end.isoformat()
    out: list[dict] = []
    for t in report.get("tickets", []):
        cost = round(t.get("cost_usd", 0.0), 6)
        out.append({
            "BilledCost": cost, "EffectiveCost": cost, "BillingCurrency": "USD",
            "BillingPeriodStart": si, "BillingPeriodEnd": ei,
            "ChargePeriodStart": si, "ChargePeriodEnd": ei,
            "ProviderName": "", "ServiceCategory": "AI and Machine Learning",
            "ServiceName": "LLM API", "ChargeCategory": "Usage",
            "ChargeDescription": f"{t.get('task_class') or 'unknown'} · {t.get('status') or ''}".strip(" ·"),
            "ResourceId": t.get("ticket_id"), "ResourceName": t.get("ticket_id"),
            "Tags": json.dumps({"team": t.get("team_id") or "unassigned",
                                "work_type": t.get("task_class") or "unknown"}),
        })
    return out


def report_focus_csv(report: dict, window_days: int = 30) -> str:
    import csv
    import io
    buf = io.StringIO()
    w = csv.DictWriter(buf, fieldnames=FOCUS_COLUMNS)
    w.writeheader()
    for r in focus_rows(report, window_days):
        w.writerow(r)
    return buf.getvalue()


def report_csv(report: dict, view: str = "tickets") -> str:
    """Serialize a slice of the report to CSV for business/sheets export.
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
    elif view == "teams":
        # Per-team / cost-center allocation for business showback / chargeback.
        w.writerow(["team", "spend_usd", "share_pct", "events"])
        for t in report.get("team_spend", []):
            w.writerow([t.get("team"), t.get("spent_usd"), round(t.get("share", 0) * 100, 1),
                        t.get("events")])
    elif view == "savings":
        w.writerow(["work_type", "from_model", "to_model", "projected_savings_usd", "confidence"])
        for r in report.get("recommendations", []):
            w.writerow([r.get("task_class"), r.get("incumbent_model"), r.get("candidate_model"),
                        r.get("projected_savings_usd"), r.get("confidence")])
    elif view == "models":
        w.writerow(["model", "calls", "spend_usd", "input_tokens", "output_tokens",
                    "cache_read_tokens", "cache_write_tokens"])
        for name, m in ((report.get("cost_fidelity") or {}).get("by_model") or {}).items():
            tok = m.get("tokens") or {}
            w.writerow([name, m.get("events"), m.get("outlay_usd"), tok.get("input"),
                        tok.get("output"), tok.get("cache_read"), tok.get("cache_write")])
    else:  # tickets
        w.writerow(["ticket_id", "task_class", "status", "cost_usd", "rework_iterations", "team_id"])
        for t in report.get("tickets", []):
            w.writerow([t.get("ticket_id"), t.get("task_class"), t.get("status"),
                        t.get("cost_usd"), t.get("rework_iterations"), t.get("team_id")])
    return buf.getvalue()


def sync(conn: dict, window_days: int = SYNC_WINDOW_DAYS, transport=None) -> dict:
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
        invoice_usd = None
        if ak:
            client = AnthropicAdminClient(api_key=ak, transport=transport)
            events += client.pull(starting_at)
            # Reconcile against Anthropic's own billed figure — but only when
            # Anthropic is the sole usage source, so the comparison is apples-to-apples.
            if not ck:
                try:
                    invoice_usd = client.pull_cost(starting_at)
                except Exception:  # noqa: BLE001 — reconciliation is best-effort, never fail the sync
                    invoice_usd = None
        if ck:
            start_ms, end_ms = int(since.timestamp() * 1000), int(now.timestamp() * 1000)
            events += CursorAdminClient(api_key=ck, transport=transport).pull(start_ms, end_ms)
    except ValueError:
        raise
    except Exception as e:  # noqa: BLE001 — network / auth → clean message
        raise ValueError(f"Couldn't sync from your sources: {e}") from e

    result, stats, size_models = _fit(work, events, identity=identity_graph(conn.get("identity_map")))
    report = _report(work, result, stats, size_models, None, window_days, events=events)
    return reconcile(report, invoice_usd, "anthropic_cost_report", window_days)
