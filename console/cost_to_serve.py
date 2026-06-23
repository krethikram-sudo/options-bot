"""Cost-to-serve / KTLO estimator (vendor-internal, admin-only).

Answers: *what does it cost US to run a customer's Outlay experience, and how does
that scale per customer* — so pricing can be set against real cost drivers.

Key fact about Outlay's economics: the product makes **no server-side LLM calls**.
Classification, forecasting, attribution, and the cost model are deterministic
heuristics + statistics (`outlay/classify.py` etc.). Sync pulls use the *customer's*
own tracker + provider tokens (BYOK). So our marginal cost-to-serve is **infra only**
— CPU to rebuild the report on each sync, storage of the report + history snapshots,
a little egress + email — on top of a small fixed always-on machine. No per-token COGS.

Cost driver per customer ≈ **data volume × sync frequency × retention**. A large
enterprise (many tickets/usage-events, hourly sync, 365-day retention, many connectors)
costs materially more than a small team (few tickets, weekly sync, 90-day retention) —
but in absolute terms it's cents-to-low-dollars/month until the single-SQLite-machine
scale ceiling forces a step change (add machines / move to a real DB).

All unit costs are tunable (env `CTS_*`) — they're transparent assumptions, not gospel.
"""

from __future__ import annotations

import os

# --- Unit-cost assumptions (USD; override via env) ------------------------- #
FLY_BASE_MONTHLY = float(os.environ.get("CTS_FLY_BASE_MONTHLY", "2.00"))   # always-on shared-cpu-1x/512mb
STORAGE_GB_MONTH = float(os.environ.get("CTS_STORAGE_GB_MONTH", "0.15"))   # Fly volume $/GB-mo
EGRESS_GB = float(os.environ.get("CTS_EGRESS_GB", "0.02"))                 # outbound $/GB
EMAIL_SEND = float(os.environ.get("CTS_EMAIL_SEND", "0.0004"))            # transactional email $/send
CPU_SEC = float(os.environ.get("CTS_CPU_SEC", "0.0000008"))               # shared vCPU $/second

# Rough on-disk bytes per stored row (SQLite, incl. overhead).
_B_HISTORY = 320       # outlay_history snapshot (total + small breakdown JSON)
_B_PROG_HISTORY = 56   # outlay_program_history row
_B_AUDIT = 170         # audit_log row
_B_DELIVERY = 440      # webhook_deliveries row
_GB = 1_000_000_000


def syncs_per_month(sync_hours: int) -> float:
    """Auto-sync cadence → syncs/month; manual (0) ≈ ~weekly hand-runs."""
    if sync_hours and sync_hours > 0:
        return 730.0 / sync_hours
    return 4.0


def estimate(drivers: dict, active_accounts: int = 1) -> dict:
    """`drivers` = the raw per-account counts (see store.account_cost_drivers).
    Returns the monthly cost-to-serve breakdown + the dominant driver + a tier signal."""
    events = int(drivers.get("events", 0) or 0)
    tickets = int(drivers.get("tickets", 0) or 0)
    report_bytes = int(drivers.get("report_bytes", 0) or 0)
    hist = int(drivers.get("history_rows", 0) or 0)
    phist = int(drivers.get("prog_history_rows", 0) or 0)
    audit = int(drivers.get("audit_rows", 0) or 0)
    deliveries = int(drivers.get("delivery_rows", 0) or 0)
    sync_hours = int(drivers.get("sync_hours", 0) or 0)
    retention = int(drivers.get("retention_days", 0) or 0)
    connectors = int(drivers.get("connectors", 0) or 0)
    webhooks = int(drivers.get("webhooks", 0) or 0)
    emails_month = float(drivers.get("emails_month", 5))   # ~weekly digest + monthly pack + a few alerts

    syncs = syncs_per_month(sync_hours)

    # Storage = the live report blob + accumulated history/audit/delivery rows.
    storage_bytes = (report_bytes + hist * _B_HISTORY + phist * _B_PROG_HISTORY
                     + audit * _B_AUDIT + deliveries * _B_DELIVERY)
    storage_cost = storage_bytes / _GB * STORAGE_GB_MONTH

    # Compute = rebuild the report on each sync; CPU scales ~linearly with volume
    # (report byte-size is the directly-measured volume signal; no event count is stored).
    cpu_sec_per_sync = 0.15 + tickets * 0.00002 + (report_bytes / 1_000_000) * 0.05
    compute_cost = syncs * cpu_sec_per_sync * CPU_SEC

    # Egress = sync pulls + webhook posts + the report API; small, volume-scaled.
    egress_bytes = syncs * report_bytes * 0.3 + deliveries * 2000 + webhooks * syncs * 1500
    egress_cost = egress_bytes / _GB * EGRESS_GB

    email_cost = emails_month * EMAIL_SEND
    marginal = storage_cost + compute_cost + egress_cost + email_cost
    allocated_fixed = FLY_BASE_MONTHLY / max(1, active_accounts)
    loaded = marginal + allocated_fixed

    lines = {"storage": storage_cost, "compute": compute_cost,
             "egress": egress_cost, "email": email_cost}
    primary = max(lines, key=lines.get) if marginal > 0 else "fixed"

    # Tier signal — the same axes drive cost AND value (volume / freshness / retention / breadth).
    score = ((report_bytes >= 2_000_000) + bool(sync_hours and sync_hours <= 6)
             + (retention >= 365) + (connectors >= 3) + (webhooks >= 1))
    tier = "heavy" if score >= 3 else ("standard" if score >= 1 else "light")

    return {
        "syncs_per_month": round(syncs, 1),
        "storage_mb": round(storage_bytes / 1_000_000, 2),
        "cost_storage": round(storage_cost, 4),
        "cost_compute": round(compute_cost, 4),
        "cost_egress": round(egress_cost, 4),
        "cost_email": round(email_cost, 4),
        "marginal_monthly": round(marginal, 4),
        "allocated_fixed_monthly": round(allocated_fixed, 4),
        "loaded_monthly": round(loaded, 4),
        "primary_driver": primary,
        "tier_signal": tier,
        "drivers": {"events": events, "tickets": tickets, "history_rows": hist + phist,
                    "sync_hours": sync_hours, "retention_days": retention,
                    "connectors": connectors, "webhooks": webhooks},
    }
