"""Outlay product surface for the console — run the engine on a customer's data.

The `outlay` package is the engine; this thin module wraps it for the web app:
take a customer's tracker export + AI-usage export (the same JSON the CLI eats),
run attribute → forecast → estimate → backtest, and return the serialized report
the dashboard renders. Stdlib + the in-repo `outlay` engine only.
"""

from __future__ import annotations

import json
import os
import tempfile
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
    """The engine's parsers read files; write the uploaded JSON to a temp file."""
    f = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False)
    f.write(text if isinstance(text, str) else json.dumps(text))
    f.close()
    return f.name


def _model(issues, usage):
    """Parse the uploads and fit the cost model. Raises ValueError on bad input."""
    ip, up = _tmp(issues), _tmp(usage)
    try:
        try:
            work = parse_github_issues(ip)
            events = parse_anthropic_usage(up)
        except Exception as e:  # noqa: BLE001 — surface a clean message to the UI
            raise ValueError(f"Couldn't read the uploaded data: {e}") from e
    finally:
        os.unlink(ip)
        os.unlink(up)
    result = attribute(events, work)
    stats = class_stats(result)
    size_models = fit_size_models(result, work)
    return work, result, stats, size_models


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


def build_report(issues, usage, planned: Optional[object] = None,
                 window_days: int = 30) -> dict:
    """Run the full pipeline on uploaded data and return the serialized report."""
    work, result, stats, size_models = _model(issues, usage)
    recs = recommend(result, horizon_scale=30.0 / max(window_days, 1))
    cal = backtest(result, work)
    fc = forecast_roadmap([w for w in work if w.is_open], stats, size_models)
    data = to_dict(result, stats, fc, find_anomalies(result, stats), recs,
                   calibration=cal, window_days=window_days)
    if planned:
        pp = _tmp(planned)
        try:
            data["estimate"] = _serialize_plan(estimate_plan(parse_planned(pp), stats, size_models))
        finally:
            os.unlink(pp)
    return data


def estimate_backlog(issues, usage, planned) -> dict:
    """Estimate a planned backlog against the cost model learned from history."""
    _work, _result, stats, size_models = _model(issues, usage)
    pp = _tmp(planned)
    try:
        return _serialize_plan(estimate_plan(parse_planned(pp), stats, size_models))
    finally:
        os.unlink(pp)
