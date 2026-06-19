"""Seed the console with an admin login + demo customers and metering, so the
dashboards/admin views are populated. Idempotent: skips accounts that exist.

Usage:
  CONSOLE_DB=console.db ADMIN_EMAIL=you@x.com ADMIN_PASSWORD=secret python -m console.seed
"""

import os
import random
import time

from . import store

CATS = ["classification", "extraction", "summarization_short", "rewrite_format",
        "codegen_simple", "conversation", "translation"]


def _meter_history(deployment_id: str, days: int, daily_savings: float, rng: random.Random):
    now = time.time()
    for d in range(days):
        ts = now - d * store.DAY - rng.uniform(0, store.DAY)
        for _ in range(rng.randint(2, 4)):
            cat = rng.choice(CATS)
            requests = rng.randint(40, 200)
            routed = int(requests * rng.uniform(0.4, 0.7))
            baseline = requests * rng.uniform(0.004, 0.012)
            savings = baseline * rng.uniform(0.25, 0.45)
            actual = baseline - savings
            escal = int(routed * rng.uniform(0, 0.04))
            store.record_meter(deployment_id, requests=requests, routed=routed,
                               escalations=escal, baseline_cost=baseline, actual_cost=actual,
                               realized_savings=savings * (daily_savings / 1.0), category=cat, ts=ts)


def main():
    store.init_db()
    rng = random.Random(7)

    admin_email = os.environ.get("ADMIN_EMAIL", "admin@outlay-ai.com")
    admin_pw = os.environ.get("ADMIN_PASSWORD", "changeme-admin-pw")
    if not store.get_account_by_email(admin_email):
        store.create_account(admin_email, admin_pw, company="Outlay", role="admin")
        print(f"admin: {admin_email} / {admin_pw}  (change this!)")
    else:
        print(f"admin exists: {admin_email}")

    demos = [
        ("founder@northwind.ai", "Northwind AI", "paid", "autopilot", 30, 1.2),
        ("eng@brightloop.io", "BrightLoop", "trial", "guidance", 5, 0.8),
        ("cto@taraplabs.com", "Tarap Labs", "trial_expired", "autopilot", 12, 1.0),
        ("ops@ferndesk.com", "FernDesk", "paid", "autopilot", 22, 0.6),
    ]
    for email, company, plan, mode, days, scale in demos:
        if store.get_account_by_email(email):
            print(f"exists: {email}")
            continue
        acct = store.create_account(email, "demo-password-123", company=company)
        store.update_settings(acct["id"], mode=mode)
        dep = store.deployments_for(acct["id"])[0]["deployment_id"]
        _meter_history(dep, days, scale, rng)
        if plan == "paid":
            store.convert_to_paid(acct["id"])
        elif plan == "trial_expired":
            store.extend_trial(acct["id"], -3)  # ended 3 days ago
        print(f"customer: {email} ({company}) plan={plan} mode={mode}")

    rev = store.revenue_overview()
    print(f"\nrevenue this cycle: ${rev['cycle_revenue']:.2f} · "
          f"savings delivered (cycle): ${rev['cycle_savings']:.2f} · "
          f"accounts: {rev['n_accounts']} ({rev['n_paid']} paid)")


if __name__ == "__main__":
    main()
