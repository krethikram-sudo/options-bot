"""Demo mode — one toggle that makes a *gated* account look like a fully set-up,
actively-running customer, so the team can walk a prospect through every surface
(both personas) without entering real data.

Access is gated to accounts whose email is in the `DEMO_ACCOUNT_EMAILS` env var
(comma-separated; `*` allows any account — used in tests). Entering demo mode
seeds the worked sample report + history, a mix of budgets, a couple of program
budgets (one enforcing a hard cap), and a "connected, just synced" source, then
drops into the Finance persona. Exiting wipes all of that back to a clean
standard-customer state. Nothing here ever touches real customer data.
"""
from __future__ import annotations

import os
import time

from . import outlay_app, store


def demo_account_emails() -> set[str]:
    raw = os.environ.get("DEMO_ACCOUNT_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}


def is_demo_account(email: str | None) -> bool:
    """True iff this account is allowed to access demo mode at all."""
    if not email:
        return False
    allow = demo_account_emails()
    return "*" in allow or email.strip().lower() in allow


# The talk-track a presenter follows, per persona — also rendered as the in-app
# "Demo guide". Kept here so the script and the UI never drift.
SCRIPT = {
    "finance": [
        ("Overview", "/app/outlay", "Lead with the finance KPIs: total attributed spend, "
         "how much is allocated to teams, invoice reconciliation."),
        ("Spend", "/app/outlay", "Drill into the per-team / cost-center allocation — the chargeback view."),
        ("Budgets", "/app/outlay/budgets", "Show guardrails: one team over, one warning, one healthy."),
        ("Programs", "/app/outlay/programs", "A program budget spanning teams with a hard cap the gateway enforces."),
        ("Security", "/app/security", "Close on the compliance posture: metadata-only, BYOK, AI transparency, VPAT."),
    ],
    "eng": [
        ("Overview", "/app/outlay", "Lead with the engineering KPIs: forecast coverage + runaway tickets."),
        ("Accuracy", "/app/outlay/accuracy", "Forecast back-tested on the team's own closed tickets."),
        ("Estimate", "/app/outlay/estimate", "Price a backlog before building it, from the learned cost model."),
        ("Spend", "/app/outlay", "Spend by ticket / work type, with the anomaly flags for runaway tickets."),
    ],
}


def _seed_budgets(account_id: int, report: dict) -> None:
    """Create team + work-type budgets tuned to show one over, one warning, one
    healthy — so the Budgets page demonstrates the full guardrail story.

    Pace status (outlay_app): over when spent ≥ limit, warn at ≥80%. We set the
    period to the report window so projection ≈ spent and the statuses are stable.
    """
    window = int(report.get("window_days") or 30)
    teams = [t for t in (report.get("team_spend") or []) if t.get("team") and t["team"] != "(unassigned)"]
    teams = sorted(teams, key=lambda t: t.get("spent_usd", 0.0), reverse=True)
    # over / warn / ok limits as multiples of realized spend.
    for team, mult in zip(teams[:3], (0.8, 1.15, 2.0)):
        spent = team.get("spent_usd", 0.0)
        if spent <= 0:
            continue
        store.add_outlay_budget(account_id, "team", team["team"],
                                round(spent * mult, 2), period_days=window)
    # One work-type budget for variety (healthy).
    classes = sorted((report.get("class_spend") or []), key=lambda c: c.get("spent_usd", 0.0), reverse=True)
    if classes:
        c = classes[0]
        store.add_outlay_budget(account_id, "class", c["task_class"],
                                round(c.get("spent_usd", 0.0) * 1.6, 2), period_days=window)


def _seed_programs(account_id: int, report: dict) -> None:
    """Two program budgets: a multi-team 'Platform stability' over its cap with a
    hard-cap route-down (shows enforcement), and a healthy 'Billing v2' on alert."""
    teams = [t["team"] for t in (report.get("team_spend") or [])
             if t.get("team") and t["team"] != "(unassigned)"]
    by_team = {t["team"]: t.get("spent_usd", 0.0) for t in (report.get("team_spend") or [])}
    if not teams:
        return
    # Program 1 — spans the two biggest teams, set OVER its cap, hard route-down.
    top = sorted(teams, key=lambda t: by_team.get(t, 0.0), reverse=True)
    members = [{"scope_type": "team", "scope_id": t} for t in top[:2]]
    cap = round(sum(by_team.get(t, 0.0) for t in top[:2]) * 0.85, 2)  # under realized → over
    store.add_outlay_program(account_id, "Platform stability", members, cap or 1000.0,
                             period_days=90, enforce_mode="hard", action="downgrade",
                             floor_model="claude-haiku-4-5")
    # Program 2 — a single team, comfortably under cap, alert-only. The 90-day period
    # straight-lines 30-day spend ~3x, so a healthy cap must clear that projection.
    if len(top) > 2:
        t = top[2]
        store.add_outlay_program(account_id, "Billing v2", [{"scope_type": "team", "scope_id": t}],
                                 round(by_team.get(t, 0.0) * 5.0, 2) or 5000.0,
                                 period_days=90, enforce_mode="alert", action="block")


def _seed_report(account_id: int, now: float | None = None) -> dict:
    """Load the worked sample report + a short backdated history (so the trend and
    movers render). Mirrors the legacy /app/outlay/sample seeding."""
    now = now or time.time()
    report = outlay_app.sample_report()
    store.save_outlay_report(account_id, report)
    for i, f in enumerate((0.78, 0.86, 0.93)):
        snap = {
            "spend": {"total_usd": (report.get("spend") or {}).get("total_usd", 0.0) * f},
            "forecast": {"expected_usd": (report.get("forecast") or {}).get("expected_usd", 0.0) * f},
            "team_spend": [{"team": t["team"], "spent_usd": t.get("spent_usd", 0.0) * f}
                           for t in (report.get("team_spend") or [])],
            "class_spend": [{"task_class": c["task_class"], "spent_usd": c.get("spent_usd", 0.0) * f}
                            for c in (report.get("class_spend") or [])],
        }
        store.record_outlay_snapshot(account_id, snap, now=now - (3 - i) * 86400)
    store.record_outlay_snapshot(account_id, report, now=now)
    return report


def clear(account_id: int) -> None:
    """Reset to a clean standard-customer state: drop the report/history, every
    budget and program, and the connector config."""
    store.delete_outlay_report(account_id)
    for b in store.list_outlay_budgets(account_id):
        store.delete_outlay_budget(account_id, b["id"])
    for p in store.list_outlay_programs(account_id):
        store.delete_outlay_program(account_id, p["id"])
    store.delete_outlay_connection(account_id)


def enter(account_id: int, member_id: int = 0, now: float | None = None) -> None:
    """Turn demo mode ON: clear any prior state, seed a full worked account, mark
    a freshly-synced GitHub connection, default to the Finance persona."""
    now = now or time.time()
    clear(account_id)
    report = _seed_report(account_id, now=now)
    _seed_budgets(account_id, report)
    _seed_programs(account_id, report)
    # A connected, just-synced source so Connect reads "✓ synced" and the setup
    # checklist is complete.
    store.save_outlay_connection(account_id, tracker="github",
                                 github_owner="acme", github_repo="platform")
    store.mark_outlay_synced(account_id, now=now)
    store.set_persona(account_id, "finance", member_id=member_id)
    store.set_demo_mode(account_id, True)


def exit(account_id: int) -> None:
    """Turn demo mode OFF and wipe the seeded data back to a clean account."""
    clear(account_id)
    store.set_demo_mode(account_id, False)
