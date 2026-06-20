"""Monthly finance close pack.

Month-end close is a recurring finance workflow: pull the period's AI spend,
load it into the books / FinOps tool, file the audit readout. This emails that
artifact on a monthly cadence — a short summary, the FOCUS-aligned CSV attached
(the thing finance loads), and a link to the printable close report.

Opt-in (off by default); finance turns it on from Settings. Pure builder
(`build_close_pack`) so it's testable without SMTP; `send_*` wraps it with
delivery + the monthly cadence guard. Mirrors `spend_digest.py`.
"""

from __future__ import annotations

import time
from typing import Optional

from . import notify, outlay_app, store

MONTH_SECONDS = 30 * 24 * 3600


def _money(x) -> str:
    try:
        x = float(x)
    except (TypeError, ValueError):
        return "$0"
    return f"${x:,.0f}" if abs(x) >= 1000 else f"${x:,.2f}"


def build_close_pack(account_id: int, path: Optional[str] = None) -> Optional[dict]:
    """Assemble the monthly close pack, or None when there's nothing to send (no
    report / no spend). Returns subject, body, and the FOCUS CSV to attach."""
    report = store.get_outlay_report(account_id, path)
    if not report:
        return None
    spend = report.get("spend") or {}
    total = spend.get("total_usd", 0.0)
    if total <= 0:
        return None

    budgets = store.list_outlay_budgets(account_id, path)
    statuses = outlay_app.budget_statuses(report, budgets) if budgets else []
    over = sum(1 for s in statuses if s["status"] == "over")
    teams = [t for t in (report.get("team_spend") or []) if t.get("team") != "(unassigned)"]
    classes = report.get("class_spend") or []
    rec = report.get("reconciliation") or {}
    dq = outlay_app.data_quality(report, store.get_outlay_connection(account_id, path))

    lines: list[str] = []
    lines.append(f"AI spend for the period: {_money(total)}.")
    lines.append(f"Mapped to a specific ticket: {spend.get('ticket_coverage', 0) * 100:.0f}%.")
    lines.append("")
    if teams:
        lines.append("Top cost centers:")
        for t in teams[:5]:
            lines.append(f"  {t['team']:<24} {_money(t.get('spent_usd', 0))} "
                         f"({t.get('share', 0) * 100:.0f}%)")
        lines.append("")
    if classes:
        lines.append("By work type:")
        for c in classes[:5]:
            lines.append(f"  {c['task_class']:<24} {_money(c.get('spent_usd', 0))} "
                         f"({c.get('share', 0) * 100:.0f}%)")
        lines.append("")
    if statuses:
        lines.append(f"Budgets: {over} over, {len(statuses) - over} on track.")
    if rec.get("invoice_usd"):
        lines.append(f"Reconciled: within {abs(rec.get('delta_pct', 0)):.0f}% of your provider invoice.")
    lines.append(f"Data confidence: {dq.get('score', 'n/a').title()}.")
    lines.append("")
    lines.append("Attached: outlay-focus.csv — FOCUS-aligned charge rows for your books / FinOps tool.")
    lines.append(f"Printable close report:\n{notify.base_url()}/app/outlay/close-report.html")
    lines.append("\n— Outlay")

    return {
        "account_id": account_id,
        "subject": f"Outlay close pack: {_money(total)} AI spend",
        "body": "\n".join(lines),
        "csv": outlay_app.report_focus_csv(report),
    }


def send_close_pack(account_id: int, path: Optional[str] = None,
                    now: Optional[float] = None) -> bool:
    """Build + email the close pack (with the FOCUS CSV attached) to the owner, and
    stamp the send time. Returns True iff an email was actually dispatched."""
    pack = build_close_pack(account_id, path)
    if not pack:
        return False
    acct = store.get_account(account_id, path)
    email = (acct or {}).get("email")
    if not email:
        return False
    sent = False
    try:
        sent = notify.send_email(email, pack["subject"], pack["body"],
                                 attachments=[("outlay-focus.csv", pack["csv"], "csv")])
    except Exception:  # noqa: BLE001 — a close pack must never crash the cron sweep
        sent = False
    store.mark_close_pack_sent(account_id, now=now, path=path)
    return bool(sent)


def run_due_close_packs(now: Optional[float] = None, path: Optional[str] = None) -> dict:
    """Send the monthly close pack to every account whose cadence has elapsed.
    Resilient: one account's failure never blocks the rest."""
    now = now or time.time()
    due = store.accounts_due_for_close_pack(now=now, path=path)
    sent = 0
    for account_id in due:
        try:
            if send_close_pack(account_id, path=path, now=now):
                sent += 1
            else:
                store.mark_close_pack_sent(account_id, now=now, path=path)
        except Exception:  # noqa: BLE001
            store.mark_close_pack_sent(account_id, now=now, path=path)
    return {"due": len(due), "sent": sent}
