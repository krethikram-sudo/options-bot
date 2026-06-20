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
    own *billed* figure. The same shape for every provider, so finance sees one
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
    """A single 'can finance trust these numbers?' verdict, rolled up from the signals
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
    team — the finance lead view and the low-coverage fallback."""
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


def _report(work, result, stats, size_models, planned_items=None, window_days: int = 30,
            events=None) -> dict:
    recs = recommend(result, horizon_scale=30.0 / max(window_days, 1))
    cal = backtest(result, work)
    fc = forecast_roadmap([w for w in work if w.is_open], stats, size_models)
    data = to_dict(result, stats, fc, find_anomalies(result, stats), recs,
                   calibration=cal, window_days=window_days)
    data["people"] = _people_spend(result)  # per-engineer spend rollup
    data["team_spend"] = _team_spend(result)  # per-team / cost-center rollup (finance view)
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


# FOCUS (FinOps Open Cost & Usage Specification) — the neutral, community standard
# for normalized cost+usage data. We emit FOCUS-aligned rows (standard column names)
# at the ticket grain with team/work-type Tags, so finance can load Outlay's spend
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
