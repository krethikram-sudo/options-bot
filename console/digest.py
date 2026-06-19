"""Pending-review digest: summarize tuning proposals awaiting admin approval and
(optionally) email it, so the queue doesn't pile up unnoticed.

Usage:
  python -m console.digest            # print the digest
  python -m console.digest --send     # email it to all admins (needs SMTP; see notify.py)
Run on a schedule (cron) or enable the in-process daily task with
CONSOLE_DIGEST_HOURS=24 on the server.
"""

import os

from . import notify, store


def _line(p: dict, email: str) -> str:
    payload = p.get("payload") or {}
    stats = p.get("stats") or {}
    if p["kind"] == "floor":
        what = (f"floor {p['category']} -> tier {payload.get('proposed_tier')} "
                f"({int(stats.get('samples', 0))} samples"
                + (f", {(100*stats['non_inferior_rate']):.0f}% non-inferior)"
                   if stats.get("non_inferior_rate") is not None else ")"))
    else:
        what = f"rule {payload.get('name') or p['category']} -> {p['category']}"
    return f"    - [{email}] {what}"


def build_digest(path: str | None = None, base_url: str | None = None) -> dict:
    """Summarize all pending proposals grouped by customer. Returns counts + text."""
    pending = store.list_proposals(status="pending", path=path)
    emails = {a["id"]: a["email"] for a in store.list_accounts(path)}
    by_customer: dict[int, list] = {}
    for p in pending:
        by_customer.setdefault(p["account_id"], []).append(p)
    base = (base_url or os.environ.get("CONSOLE_BASE_URL", "http://127.0.0.1:8700")).rstrip("/")
    lines = [f"{len(pending)} tuning proposal(s) awaiting review "
             f"across {len(by_customer)} customer(s).", ""]
    for account_id, items in by_customer.items():
        email = emails.get(account_id, "?")
        lines.append(f"  {email} — {len(items)} pending:")
        lines.extend(_line(p, email) for p in items)
    lines += ["", f"Review & bulk-approve: {base}/admin/proposals"]
    return {"n_pending": len(pending), "n_customers": len(by_customer),
            "text": "\n".join(lines)}


def send_digest(to: list[str] | None = None, path: str | None = None) -> dict:
    """Email the digest to admins (or `to`). Skips sending when nothing is pending."""
    d = build_digest(path)
    if d["n_pending"] == 0:
        return {"sent": 0, "n_pending": 0, "reason": "nothing pending"}
    recipients = to or [a["email"] for a in store.list_accounts(path)
                        if a["role"] == "admin" and a["status"] == "active"]
    sent = 0
    subject = f"Outlay: {d['n_pending']} tuning proposal(s) to review"
    for r in recipients:
        try:
            notify.send_email(r, subject, d["text"])
            sent += 1
        except Exception:  # noqa: BLE001 — one bad address shouldn't abort the rest
            pass
    return {"sent": sent, "n_pending": d["n_pending"], "recipients": recipients}


def main():
    import argparse
    p = argparse.ArgumentParser(prog="console.digest",
                                description="pending tuning-proposal review digest")
    p.add_argument("--send", action="store_true", help="email the digest to all admins")
    a = p.parse_args()
    store.init_db()
    print(build_digest()["text"])
    if a.send:
        res = send_digest()
        print(f"\nsent to {res['sent']} admin(s)" if res["sent"] else f"\n{res.get('reason','')}")


if __name__ == "__main__":
    main()
