"""The hero metric — realized AI cost per *delivered* unit of work.

A single, intuitive number the whole product can ladder to: not "we spent $X" but
"each shipped feature/bugfix cost $Y." Computed from completed (status == 'done')
tickets so it's cost per *shipped* item, overall and per work class.

Operates on the serialized report dict (`outlay.serialize.to_dict` / the console's
report), so the engine, the MCP server, and the console all share one definition.
"""

from __future__ import annotations

from collections import defaultdict


def cost_per_unit(report: dict) -> dict:
    """Cost per delivered unit of work, overall and per task class.

    Returns ``cost_per_unit_usd`` (overall), ``units_shipped``,
    ``total_attributed_usd``, and a ``by_class`` breakdown sorted most→least
    expensive per unit. Empty/zero when there are no completed tickets yet.
    """
    tickets = report.get("tickets", []) or []
    done = [t for t in tickets if (t.get("status") == "done")]
    total = sum(t.get("cost_usd", 0.0) for t in done)
    overall = (total / len(done)) if done else 0.0
    per_class: dict[str, dict] = defaultdict(lambda: {"cost_usd": 0.0, "count": 0})
    for t in done:
        c = per_class[t.get("task_class") or "unknown"]
        c["cost_usd"] += t.get("cost_usd", 0.0)
        c["count"] += 1
    by_class = [{"task_class": k, "cost_per_unit_usd": round(v["cost_usd"] / v["count"], 4),
                 "units": v["count"]}
                for k, v in per_class.items() if v["count"]]
    by_class.sort(key=lambda r: r["cost_per_unit_usd"], reverse=True)
    return {
        "cost_per_unit_usd": round(overall, 4),
        "units_shipped": len(done),
        "total_attributed_usd": round(total, 4),
        "by_class": by_class,
    }
