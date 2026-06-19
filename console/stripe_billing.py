"""Stripe billing for the Outlay console — usage-based: the customer's bill
is 20% of the realized savings we deliver.

Model: a Stripe **Meter** (event name e.g. `modelpilot_savings`, aggregation = sum)
with a metered recurring Price linked to it set to **$0.01 per unit (1 cent)**. We
compute the customer's bill in code — `tier rate × realized savings` (PAYG 20% /
Self-optimize & Managed 15%) — and report it **in cents** as meter events; Stripe
sums the cents and the $0.01/unit price invoices that exact amount. Applying the rate
in code means ONE Price bills every tier correctly. Subscription tiers also add a
flat monthly Price ($99 Self-optimize, etc.) as a second line item. Convert-to-paid
runs Stripe Checkout (subscription mode) to collect a card and create the subscription.

Configuration (env):
  STRIPE_SECRET_KEY      sk_live_... / sk_test_...   (required to enable Stripe)
  STRIPE_PRICE_ID        price_...  metered recurring price linked to the meter, **$0.01/unit**
                                    (we report the bill in cents; tier rate applied in code)
  STRIPE_SELFOPT_PRICE_ID price_... flat $99/mo recurring price for the Self-optimize tier
  STRIPE_MANAGED_PRICE_ID price_... flat recurring price for the Managed tier
  STRIPE_METER_EVENT     the meter's event name (default "modelpilot_savings")
  STRIPE_WEBHOOK_SECRET  whsec_...  (optional, for webhook verification)
  CONSOLE_BASE_URL       https://...  (Checkout redirect base)

If STRIPE_SECRET_KEY is unset the console still runs end-to-end: convert-to-paid
records the plan change directly (manual/again-later billing) and the UI shows a
"connect Stripe to auto-bill" notice. This keeps the product demoable without a
payment account while making the live path real.
"""

import os

from . import store


def enabled() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY"))


def _client():
    import stripe  # imported lazily so the console runs without the dep installed
    stripe.api_key = os.environ["STRIPE_SECRET_KEY"]
    return stripe


def _base_url() -> str:
    return os.environ.get("CONSOLE_BASE_URL", "http://127.0.0.1:8700").rstrip("/")


def tier_sub_price(tier: str) -> str | None:
    """The flat monthly subscription price id for a tier (None for payg or until set)."""
    if tier == "self_optimize":
        return os.environ.get("STRIPE_SELFOPT_PRICE_ID")
    if tier == "managed":
        return os.environ.get("STRIPE_MANAGED_PRICE_ID")
    return None


def create_checkout_session(account: dict, tier: str = "payg") -> str | None:
    """Start a Stripe Checkout session for the chosen tier. Returns the hosted
    Checkout URL, or None if Stripe is not configured. Subscription tiers add the
    flat monthly price (when its STRIPE_*_PRICE_ID is set) alongside the metered
    20%/15%-of-savings price."""
    if not enabled():
        return None
    price = os.environ.get("STRIPE_PRICE_ID")
    if not price:
        raise RuntimeError("STRIPE_PRICE_ID is not set")
    stripe = _client()
    plan = store.get_plan(account["id"])
    customer = plan.get("stripe_customer_id")
    if not customer:
        customer = stripe.Customer.create(
            email=account["email"], name=account.get("company") or account["email"],
            metadata={"account_id": account["id"]}).id
        _save_customer(account["id"], customer)
    line_items = [{"price": price}]  # metered savings price -> no quantity
    sub_price = tier_sub_price(tier)
    if sub_price:  # flat monthly subscription for the optimization tier
        line_items.append({"price": sub_price, "quantity": 1})
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer,
        line_items=line_items,
        success_url=f"{_base_url()}/app/billing?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{_base_url()}/app/billing?checkout=cancel",
        metadata={"account_id": account["id"], "tier": tier},
    )
    return session.url


def _save_customer(account_id: int, customer_id: str) -> None:
    conn = store.connect()
    try:
        conn.execute("UPDATE plans SET stripe_customer_id=? WHERE account_id=?",
                     (customer_id, account_id))
        conn.commit()
    finally:
        conn.close()


def finalize_checkout(account: dict, session_id: str) -> bool:
    """After Checkout success, read the subscription back and mark the account
    paid (storing the subscription + metered item id for usage reporting)."""
    if not enabled():
        return False
    stripe = _client()
    session = stripe.checkout.Session.retrieve(session_id, expand=["subscription"])
    sub = session.subscription
    if not sub:
        return False
    sub_id = sub.id if hasattr(sub, "id") else sub
    sub_obj = stripe.Subscription.retrieve(sub_id)
    item_id = sub_obj["items"]["data"][0]["id"]
    store.convert_to_paid(account["id"], stripe_customer_id=session.customer,
                          stripe_subscription_id=sub_id, stripe_item_id=item_id)
    tier = (session.metadata or {}).get("tier", "payg")
    if tier in store.TIERS:
        store.set_tier(account["id"], tier)  # aligns the savings rate (20% vs 15%)
    return True


def _meter_event_name() -> str:
    """The Stripe Meter's event name (set when you create the Meter in Stripe)."""
    return os.environ.get("STRIPE_METER_EVENT", "modelpilot_savings")


def report_usage(account_id: int, savings_dollars: float) -> bool:
    """Report the customer's BILL (their tier rate × realized savings) as a Stripe
    meter event, in CENTS. The tier rate (PAYG 20% / Self-optimize & Managed 15%)
    is applied HERE, so a single metered Price set to **$0.01 per unit** invoices
    the correct percentage for every tier — Stripe sums the cents and the $0.01/unit
    price bills that exact dollar amount. No-op if not paid/configured."""
    if not enabled() or savings_dollars <= 0:
        return False
    plan = store.get_plan(account_id)
    customer = plan.get("stripe_customer_id")
    if plan.get("plan") != "paid" or not customer:
        return False
    rate = plan.get("rate", store.TIER_RATES["payg"])
    bill_cents = int(round(savings_dollars * rate * 100))
    if bill_cents <= 0:  # sub-cent bill this report — nothing to meter yet
        return False
    import time
    stripe = _client()
    stripe.billing.MeterEvent.create(
        event_name=_meter_event_name(),
        payload={"stripe_customer_id": customer, "value": str(bill_cents)},
        timestamp=int(time.time()))
    return True


def cancel_subscription(account_id: int) -> bool:
    """Best-effort cancel the account's Stripe subscription (e.g. on account
    deletion) so billing stops. No-op if Stripe isn't configured or there's no
    subscription; never raises."""
    if not enabled():
        return False
    plan = store.get_plan(account_id)
    sub = plan.get("stripe_subscription_id")
    if not sub:
        return False
    try:
        _client().Subscription.cancel(sub)
        return True
    except Exception:  # noqa: BLE001
        return False


def sync_unreported_usage(path: str | None = None) -> dict:
    """Report any metered savings not yet pushed to Stripe for paid accounts.
    Returns counts. Safe to call on a schedule."""
    if not enabled():
        return {"enabled": False, "reported": 0}
    conn = store.connect(path)
    reported = 0
    try:
        # Only bill PAID accounts' POST-conversion savings: never the free-trial
        # period, never a row the inline /api/meter push already marked reported.
        rows = conn.execute(
            "SELECT m.id, m.realized_savings, d.account_id FROM meter m"
            " JOIN deployments d ON d.deployment_id=m.deployment_id"
            " JOIN plans p ON p.account_id=d.account_id"
            " WHERE m.stripe_reported=0 AND m.realized_savings>0"
            " AND p.plan='paid' AND p.converted_at IS NOT NULL"
            " AND m.ts >= p.converted_at").fetchall()
        by_account: dict[int, list[int]] = {}
        sums: dict[int, float] = {}
        for r in rows:
            by_account.setdefault(r["account_id"], []).append(r["id"])
            sums[r["account_id"]] = sums.get(r["account_id"], 0.0) + r["realized_savings"]
        for account_id, ids in by_account.items():
            if report_usage(account_id, sums[account_id]):
                conn.executemany("UPDATE meter SET stripe_reported=1 WHERE id=?",
                                 [(i,) for i in ids])
                reported += len(ids)
        conn.commit()
    finally:
        conn.close()
    return {"enabled": True, "reported": reported}
