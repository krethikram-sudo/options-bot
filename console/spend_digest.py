"""Customer-facing weekly spend digest.

The proactive-retention surface: a short email that keeps Outlay in front of the
buyer every week — total AI spend, the week-over-week trend, where it's going,
budget status, runaway tickets, and reconciliation. (Distinct from
`console/digest.py`, which is the vendor-admin proposal-review digest.)

Pure builder (`build_account_digest`) so it's testable without SMTP; `send_*`
wraps it with delivery + the weekly cadence guard.
"""

from __future__ import annotations

import time
from typing import Optional

from . import notify, outlay_app, store

WEEK_SECONDS = 7 * 24 * 3600


def _money(x) -> str:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "$0"
    return f"${x:,.0f}" if abs(x) >= 1000 else f"${x:,.2f}"


def _trend(history: list[dict]) -> str:
    if not history or len(history) < 2:
        return ""
    cur, prev = history[-1].get("total_usd", 0), history[-2].get("total_usd", 0)
    if prev <= 0:
        return ""
    pct = (cur - prev) / prev * 100
    if abs(pct) < 0.5:
        return " (flat vs the prior refresh)"
    return f" ({'up' if pct > 0 else 'down'} {abs(pct):.0f}% vs the prior refresh)"


def build_account_digest(account_id: int, path: Optional[str] = None) -> Optional[dict]:
    """Assemble the weekly digest for an account, or None when there's nothing
    worth sending (no report / no spend)."""
    report = store.get_outlay_report(account_id, path)
    if not report:
        return None
    spend = report.get("spend") or {}
    total = spend.get("total_usd", 0.0)
    if total <= 0:
        return None

    history = store.outlay_history(account_id, path=path)
    budgets = store.list_outlay_budgets(account_id, path)
    statuses = outlay_app.budget_statuses(report, budgets) if budgets else []
    over = sum(1 for s in statuses if s["status"] == "over")
    warn = sum(1 for s in statuses if s["status"] == "warn")
    anomalies = report.get("anomalies") or []
    teams = [t for t in (report.get("team_spend") or []) if t.get("team") != "(unassigned)"]
    classes = report.get("class_spend") or []
    rec = report.get("reconciliation") or {}

    lines: list[str] = []
    lines.append(f"Your AI spend this window: {_money(total)}{_trend(history)}.")
    lines.append("")
    lines.append("Where it's going:")
    if teams:
        t = teams[0]
        lines.append(f"  Top team:       {t['team']} — {_money(t.get('spent_usd', 0))} "
                     f"({t.get('share', 0) * 100:.0f}%)")
    if classes:
        c = classes[0]
        lines.append(f"  Top work type:  {c['task_class']} — {_money(c.get('spent_usd', 0))} "
                     f"({c.get('share', 0) * 100:.0f}%)")
    lines.append(f"  Mapped to a ticket: {spend.get('ticket_coverage', 0) * 100:.0f}%")
    lines.append("")

    if statuses:
        if over or warn:
            parts = ([f"{over} over budget"] if over else []) + ([f"{warn} at warn"] if warn else [])
            lines.append(f"Budgets: {', '.join(parts)} — review before month-end.")
        else:
            lines.append(f"Budgets: all {len(statuses)} on track.")
    # Programs off track — the earned-value / pacing signal (forecast vs actual on
    # completed work, plus run-rate vs cap). The headline of the program-budget work,
    # so a leader sees a slipping program in the Monday email, not just in-app.
    programs = store.list_outlay_programs(account_id, path)
    if programs:
        histories = store.program_histories(account_id, path=path)
        prog_statuses = outlay_app.program_statuses(report, programs, histories)
        off = [s for s in prog_statuses if s["status"] == "over"]
        watch = [s for s in prog_statuses if s["status"] == "warn"]
        if off or watch:
            parts = ([f"{len(off)} off track"] if off else []) + \
                    ([f"{len(watch)} to watch"] if watch else [])
            lines.append(f"Programs: {', '.join(parts)}.")
            # Name the worst one with its earned-value read, when there's enough
            # completed work for an honest rating.
            worst = (off or watch)[0]
            prog = worst.get("progress") or {}
            if prog.get("ready"):
                var = prog.get("cost_variance_pct", 0) * 100
                lines.append(f"  {worst.get('name', 'program')}: {prog.get('rating', 'off track')} — "
                             f"completed work is {abs(var):.0f}% "
                             f"{'over' if var >= 0 else 'under'} forecast.")
            else:
                lines.append(f"  {worst.get('name', 'program')}: on pace to exceed its budget.")
        else:
            lines.append(f"Programs: all {len(prog_statuses)} on track.")

    if anomalies:
        worst = anomalies[0]
        lines.append(f"Runaway tickets: {len(anomalies)} — worst {worst.get('ticket_id')} "
                     f"at {worst.get('ratio', 0):.0f}x its class median.")
    if rec.get("invoice_usd"):
        dp = abs(rec.get("delta_pct", 0))
        lines.append(f"Reconciled: within {dp:.0f}% of your provider invoice.")

    lines.append("")
    lines.append(f"See the full picture:\n{notify.base_url()}/app")
    lines.append("\n— Outlay")

    subject = f"Outlay weekly: {_money(total)} AI spend{_trend(history)}"
    return {"account_id": account_id, "subject": subject, "body": "\n".join(lines)}


def send_account_digest(account_id: int, path: Optional[str] = None,
                        now: Optional[float] = None) -> bool:
    """Build the digest, email the owner, and also post it to Slack/Teams when an
    incoming webhook is configured (eng + business live there). Stamps the send time.
    Returns True iff at least one channel actually dispatched."""
    d = build_account_digest(account_id, path)
    if not d:
        return False
    acct = store.get_account(account_id, path)
    email = (acct or {}).get("email")
    sent = False
    if email:
        try:
            sent = notify.send_email(email, d["subject"], d["body"])
        except Exception:  # noqa: BLE001 — a digest must never crash the cron sweep
            sent = False
    try:
        webhook = store.get_slack_webhook(account_id, path)
        if webhook:
            text = f":bar_chart: *{d['subject']}*\n\n{d['body']}"
            sent = notify.send_slack(webhook, text) or sent
    except Exception:  # noqa: BLE001 — alerting must never break the sweep
        pass
    store.mark_digest_sent(account_id, now=now, path=path)
    return bool(sent)


def run_due_digests(now: Optional[float] = None, path: Optional[str] = None) -> dict:
    """Send the weekly digest to every account whose cadence has elapsed. Resilient:
    one account's failure never blocks the rest. Returns a summary for the cron hook."""
    now = now or time.time()
    due = store.accounts_due_for_digest(now=now, path=path)
    sent = 0
    for account_id in due:
        # send_account_digest only stamps the cadence when there was real spend to
        # report. If it returns False (no spend yet / no owner email) we deliberately
        # do NOT stamp, so the first genuine digest goes out as soon as spend lands —
        # the account is just re-checked cheaply on the next sweep.
        try:
            if send_account_digest(account_id, path=path, now=now):
                sent += 1
        except Exception:  # noqa: BLE001 — one account never blocks the rest
            pass
    return {"due": len(due), "sent": sent}
