"""Stripe billing for the ModelPilot console — usage-based: the customer's bill
is 20% of the realized savings we deliver.

Model: a Stripe **Meter** (event name e.g. `modelpilot_savings`, aggregation = sum)
with a metered recurring Price linked to it where 1 unit = $1 of realized savings
and the per-unit amount is the rate (default $0.20). We report **meter events**
equal to the dollars of savings delivered, keyed to the customer; Stripe aggregates
them and invoices rate * savings each cycle. Convert-to-paid runs Stripe Checkout
(subscription mode) to collect a card and create the subscription.

Configuration (env):
  STRIPE_SECRET_KEY      sk_live_... / sk_test_...   (required to enable Stripe)
  STRIPE_PRICE_ID        price_...  metered recurring price linked to the meter, $0.20/unit
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


def create_checkout_session(account: dict) -> str | None:
    """Start a Stripe Checkout session for the subscription. Returns the hosted
    Checkout URL, or None if Stripe is not configured."""
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
        store.convert_to_paid  # noqa: B018 — keep import warm; convert happens on success
        _save_customer(account["id"], customer)
    session = stripe.checkout.Session.create(
        mode="subscription",
        customer=customer,
        line_items=[{"price": price}],  # metered price -> no quantity
        success_url=f"{_base_url()}/app/billing?checkout=success&session_id={{CHECKOUT_SESSION_ID}}",
        cancel_url=f"{_base_url()}/app/billing?checkout=cancel",
        metadata={"account_id": account["id"]},
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
    return True


def _meter_event_name() -> str:
    """The Stripe Meter's event name (set when you create the Meter in Stripe)."""
    return os.environ.get("STRIPE_METER_EVENT", "modelpilot_savings")


def report_usage(account_id: int, savings_dollars: float) -> bool:
    """Report a meter event (= dollars of savings) for the account's customer.
    Stripe's meter aggregates these and the linked price invoices rate * total
    each cycle. No-op if not paid/configured."""
    if not enabled() or savings_dollars <= 0:
        return False
    plan = store.get_plan(account_id)
    customer = plan.get("stripe_customer_id")
    if plan.get("plan") != "paid" or not customer:
        return False
    import time
    stripe = _client()
    stripe.billing.MeterEvent.create(
        event_name=_meter_event_name(),
        payload={"stripe_customer_id": customer,
                 "value": str(int(round(savings_dollars)))},
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
        rows = conn.execute(
            "SELECT m.id, m.realized_savings, d.account_id FROM meter m"
            " JOIN deployments d ON d.deployment_id=m.deployment_id"
            " WHERE m.stripe_reported=0 AND m.realized_savings>0").fetchall()
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
