"""Forward estimator — what will *planned* work cost in AI compute?

`forecast.py` costs open work items that already exist in the tracker. This goes
one step earlier: take a backlog of **planned** Jira/Linear features — a title, a
description, optionally a story-point estimate — that haven't been built yet, and
estimate their AI compute cost so a team can **budget against work that needs to
get done**.

It works by learning a cost model from the customer's realized history (per-class
cost distributions + a cost-per-point size model) and applying it to each planned
item, classified from its text. Every estimate carries a **confidence** and a
**p10–p90 band**, and items we can't ground are counted, never guessed:

  * **high**   — has story points and its class has a fitted size model → cost
                 scales with the estimate.
  * **medium** — class has solid history but no points → class-mean estimate.
  * **low**    — thin/no history for the class → wide band, flagged to collect more.

The honest message to a customer: a single feature is a range, but a quarter's
backlog pools to a budget — and the band is measured on their own data.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .classify import classify
from .complexity import scope_of
from .forecast import ClassStats, _Z_P90
from .models import TaskClass, WorkItem
from .size import size_feature

_MIN_CONFIDENT_HISTORY = 5   # class tickets needed before a class-mean estimate is "medium"


@dataclass
class ItemEstimate:
    item_id: str
    title: str
    task_class: TaskClass
    est_points: Optional[float]
    expected_usd: float
    low_usd: float
    high_usd: float
    basis: str          # "points" | "scope" | "class" | "none"
    confidence: str     # "high" | "medium" | "low"
    costable: bool
    complexity_tier: Optional[str] = None   # S | M | L | XL when sized by requirements/design
    needs: list[str] = field(default_factory=list)  # inputs that would raise confidence


def _tier_band(st: ClassStats, tier: str) -> tuple[float, float, float]:
    """Place an item within its class's *own* cost distribution by complexity tier.

    Stays inside the observed range (XL gets a modest stretch beyond p90), so a
    complexity read never invents a number the team has never actually hit."""
    if tier == "S":
        return (st.p10 + st.median) / 2, st.p10, st.median
    if tier == "L":
        return (st.median + st.p90) / 2, st.median, st.p90
    if tier == "XL":
        return st.p90, st.median, st.p90 * 1.25
    return st.mean, st.p10, st.p90   # "M" — the class-typical case


@dataclass
class PlanEstimate:
    expected_usd: float
    low_usd: float
    high_usd: float
    items: list[ItemEstimate] = field(default_factory=list)
    items_costed: int = 0
    items_unknown: int = 0
    by_class: dict[TaskClass, float] = field(default_factory=dict)
    by_confidence: dict[str, int] = field(default_factory=dict)


def estimate_item(
    item: WorkItem,
    stats: dict[TaskClass, ClassStats],
    size_models: "dict[TaskClass, object] | None" = None,
) -> ItemEstimate:
    """Estimate one planned item from the learned cost model."""
    size_models = size_models or {}
    tc = classify(item)   # reads title + description (which carries requirements + design)
    points = item.est_points
    st = stats.get(tc)

    if st is None or st.n == 0:
        # No history to ground a number — say so, don't invent one.
        return ItemEstimate(item.ticket_id, item.title, tc, points,
                            0.0, 0.0, 0.0, basis="none", confidence="low", costable=False,
                            needs=["realized history for this work type"])

    tier = None
    needs: list[str] = []
    sm = size_models.get(tc)
    sf = size_feature(item) if sm is not None else None
    scope = scope_of(item.description)

    if sm is not None and sf is not None and sf[0] == sm.feature:
        # Best: story points + a fitted, history-calibrated size model.
        exp = sm.predict(sf[1])
        lo, hi = exp * sm.lo_mult, exp * sm.hi_mult
        basis, confidence = "points", "high"
    elif scope is not None:
        # Size from the requirements/design read, within the class's own distribution.
        exp, lo, hi = _tier_band(st, scope.tier)
        basis, confidence, tier = "scope", "medium", scope.tier
        if points is None:
            needs.append("story points (→ point-calibrated, higher confidence)")
    else:
        # Only a thin title — flat class mean.
        exp, lo, hi = st.mean, st.p10, st.p90
        basis = "class"
        confidence = "medium" if st.n >= _MIN_CONFIDENT_HISTORY else "low"
        needs.append("business requirements + a design doc (→ complexity-sized)")
        if points is None:
            needs.append("story points")

    return ItemEstimate(item.ticket_id, item.title, tc, points,
                        exp, lo, hi, basis=basis, confidence=confidence, costable=True,
                        complexity_tier=tier, needs=needs)


def estimate_plan(
    items: list[WorkItem],
    stats: dict[TaskClass, ClassStats],
    size_models: "dict[TaskClass, object] | None" = None,
) -> PlanEstimate:
    """Estimate a backlog/epic of planned items into a budget with a confidence band.

    The aggregate band is variance-pooled (per-item errors partially cancel) and
    kept nested inside the fully-correlated [Σp10, Σp90] envelope — same honest
    interval math as the roadmap forecast.
    """
    ests = [estimate_item(it, stats, size_models) for it in items]
    costed = [e for e in ests if e.costable]

    expected = sum(e.expected_usd for e in costed)
    p10 = sum(e.low_usd for e in costed)
    p90 = sum(e.high_usd for e in costed)
    var_sum = sum(((e.high_usd - e.low_usd) / (2 * _Z_P90)) ** 2 for e in costed)
    agg = var_sum ** 0.5
    low = max(p10, expected - _Z_P90 * agg)
    high = min(p90, expected + _Z_P90 * agg)
    low = max(0.0, low)

    by_class: dict[TaskClass, float] = {}
    for e in costed:
        by_class[e.task_class] = by_class.get(e.task_class, 0.0) + e.expected_usd
    by_conf: dict[str, int] = {}
    for e in ests:
        by_conf[e.confidence] = by_conf.get(e.confidence, 0) + 1

    return PlanEstimate(
        expected_usd=expected, low_usd=low, high_usd=high, items=ests,
        items_costed=len(costed), items_unknown=len(ests) - len(costed),
        by_class=by_class, by_confidence=by_conf,
    )


def _join_docs(v) -> str:
    """Flatten design_docs / requirements that may be a string, a list of strings,
    or a list of {title, body|text|content} dicts, into one text blob."""
    if not v:
        return ""
    if isinstance(v, str):
        return v
    parts = []
    for d in v:
        if isinstance(d, str):
            parts.append(d)
        elif isinstance(d, dict):
            parts.append(" ".join(str(d.get(k, "")) for k in ("title", "body", "text", "content")))
    return "\n".join(p for p in parts if p)


def parse_planned(path: Path | str) -> list[WorkItem]:
    """Load planned items from a simple JSON list.

    Each entry: {"id", "title", "description"?, "requirements"?, "design_docs"?,
    "points"?, "labels"?}. `requirements` and `design_docs` may be strings or
    lists; they're folded into the item text so it classifies and sizes on the
    full scope, not just a title.
    """
    data = json.loads(Path(path).read_text())
    rows = data.get("items", data) if isinstance(data, dict) else data
    out: list[WorkItem] = []
    for r in rows:
        text = "\n".join(p for p in (
            r.get("description", "") or r.get("body", ""),
            _join_docs(r.get("requirements")),
            _join_docs(r.get("design_docs") or r.get("design")),
        ) if p).strip()
        out.append(WorkItem(
            ticket_id=str(r.get("id") or r.get("key") or r.get("ticket_id") or "?"),
            source="plan",
            title=r.get("title", "") or r.get("summary", ""),
            description=text,
            labels=list(r.get("labels", []) or []),
            est_points=r.get("points", r.get("est_points")),
            status="open",
        ))
    return out


def _usd(x: float) -> str:
    if abs(x) >= 1000:
        return f"${x:,.0f}"
    if abs(x) >= 1:
        return f"${x:,.2f}"
    return f"${x:.4f}"


def format_estimate(plan: PlanEstimate) -> str:
    """Render a plan estimate as a legible text block."""
    L = [
        "Compute budget estimate · planned work",
        "  " + "-" * 56,
        f"   Expected: {_usd(plan.expected_usd)}    "
        f"Likely range (p10–p90): {_usd(plan.low_usd)}–{_usd(plan.high_usd)}",
        f"   {plan.items_costed} of {plan.items_costed + plan.items_unknown} items estimated; "
        f"{plan.items_unknown} had no class history (collect more before trusting).",
    ]
    conf = plan.by_confidence
    L.append(f"   Confidence: {conf.get('high',0)} high · {conf.get('medium',0)} medium · {conf.get('low',0)} low")
    if plan.by_class:
        L.append("   By work type:")
        for tc, amt in sorted(plan.by_class.items(), key=lambda kv: kv[1], reverse=True):
            L.append(f"     {tc.value:<10} {_usd(amt)}")
    L.append("")
    L.append("   Top items (expected · band · basis · confidence):")
    top = sorted([e for e in plan.items if e.costable],
                 key=lambda e: e.expected_usd, reverse=True)[:12]
    for e in top:
        pts = f"{e.est_points:g}pt" if e.est_points else "—"
        basis = e.basis + (f"·{e.complexity_tier}" if e.complexity_tier else "")
        L.append(f"     {e.item_id:<10}{e.task_class.value:<9}{pts:>5}  "
                 f"{_usd(e.expected_usd):>9}  [{_usd(e.low_usd)}–{_usd(e.high_usd)}]  "
                 f"{basis:<10} {e.confidence}")
    # What would tighten the weakest estimates.
    hints = sorted({n for e in plan.items for n in e.needs})
    if hints:
        L.append("")
        L.append("   To tighten the estimate, add: " + "; ".join(hints))
    unk = [e for e in plan.items if not e.costable]
    if unk:
        L.append(f"   Not estimated (no history): {', '.join(e.item_id for e in unk[:8])}"
                 + (" …" if len(unk) > 8 else ""))
    return "\n".join(L) + "\n"


def main(argv: list[str] | None = None) -> int:
    """`python -m outlay.estimate` — learn from history, estimate a planned backlog."""
    import argparse

    from .attribute import attribute
    from .cli import gather_events
    from .forecast import class_stats
    from .ingest import PLANNERS
    from .join import JoinEngine, TicketResolver
    from .size import fit_size_models

    p = argparse.ArgumentParser(description="Outlay forward compute-budget estimator")
    p.add_argument("--plan", type=Path, required=True,
                   help="planned items JSON (id/title/description/points/labels)")
    p.add_argument("--usage", type=Path, default=None, help="Anthropic per-call usage JSON (history)")
    p.add_argument("--anthropic-admin", type=Path, default=None)
    p.add_argument("--cursor", type=Path, default=None)
    p.add_argument("--claude-code", type=Path, default=None)
    p.add_argument("--issues", type=Path, required=True, help="historical tracker export (to learn from)")
    p.add_argument("--planner", choices=sorted(PLANNERS), default="github")
    p.add_argument("--json", action="store_true", dest="as_json")
    args = p.parse_args(argv)

    events = gather_events(usage=args.usage, anthropic_admin=args.anthropic_admin,
                           cursor=args.cursor, claude_code=args.claude_code)
    parse_work, resolver_source = PLANNERS[args.planner]
    history = parse_work(args.issues)
    result = attribute(events, history,
                       engine=JoinEngine(history, resolver=TicketResolver(source=resolver_source)))
    stats = class_stats(result)
    size_models = fit_size_models(result, history)

    plan = estimate_plan(parse_planned(args.plan), stats, size_models)
    if args.as_json:
        print(json.dumps({
            "expected_usd": round(plan.expected_usd, 4),
            "low_usd": round(plan.low_usd, 4),
            "high_usd": round(plan.high_usd, 4),
            "items_costed": plan.items_costed,
            "items_unknown": plan.items_unknown,
            "by_confidence": plan.by_confidence,
            "items": [{
                "id": e.item_id, "title": e.title, "task_class": e.task_class.value,
                "est_points": e.est_points, "expected_usd": round(e.expected_usd, 4),
                "low_usd": round(e.low_usd, 4), "high_usd": round(e.high_usd, 4),
                "basis": e.basis, "complexity_tier": e.complexity_tier,
                "confidence": e.confidence, "costable": e.costable, "needs": e.needs,
            } for e in plan.items],
        }, indent=2))
    else:
        print(format_estimate(plan))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
