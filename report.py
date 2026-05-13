"""Daily account reports — open, hourly check-in, and close summaries.

Pulls equity, cash, open positions, and today's filled orders from Alpaca's
paper trading API. `account.last_equity` is yesterday's closing equity, so
day P&L = equity - last_equity.

Formatters return (title, body, priority, tags). The hourly formatter may
return None to indicate "skip — nothing happened".
"""
import os
from datetime import datetime, time as _dt_time, timedelta, timezone
from zoneinfo import ZoneInfo

import config
from alerts import (PRIORITY_DEFAULT, PRIORITY_LOW, dispatch)

ET = ZoneInfo("America/New_York")


def _client():
    from alpaca.trading.client import TradingClient
    return TradingClient(
        os.environ["ALPACA_API_KEY"],
        os.environ["ALPACA_API_SECRET"],
        paper=True,
    )


def get_summary() -> dict:
    from alpaca.trading.enums import QueryOrderStatus
    from alpaca.trading.requests import GetOrdersRequest

    client = _client()
    acct = client.get_account()
    positions = client.get_all_positions()

    equity = float(acct.equity)
    last_equity = float(acct.last_equity) if acct.last_equity else equity
    day_change = equity - last_equity
    day_pct = (day_change / last_equity * 100) if last_equity else 0.0

    starting_capital = float(getattr(config, "STARTING_CAPITAL", 100000.0))
    lifetime_change = equity - starting_capital
    lifetime_pct = (lifetime_change / starting_capital * 100) if starting_capital else 0.0

    today_start_et = datetime.now(ET).replace(hour=0, minute=0, second=0, microsecond=0)
    after = today_start_et.astimezone(timezone.utc)
    req = GetOrdersRequest(status=QueryOrderStatus.CLOSED, after=after, limit=500)
    orders = client.get_orders(filter=req)
    fills = [o for o in orders if o.filled_at is not None]

    unrealized = sum(float(p.unrealized_pl or 0) for p in positions)

    return {
        "equity": equity,
        "cash": float(acct.cash),
        "buying_power": float(acct.buying_power),
        "last_equity": last_equity,
        "day_change": day_change,
        "day_pct": day_pct,
        "starting_capital": starting_capital,
        "lifetime_change": lifetime_change,
        "lifetime_pct": lifetime_pct,
        "positions": positions,
        "fills_today": fills,
        "unrealized": unrealized,
    }


def _money(x: float) -> str:
    """Compact money format: $1,234 (no decimals for >=$10), $12.34 for less."""
    if abs(x) >= 10:
        return f"${x:,.0f}"
    return f"${x:.2f}"


def _signed_money(x: float) -> str:
    if x >= 0:
        return f"+{_money(x)}"
    return f"-{_money(abs(x))}"


def _pct(x: float) -> str:
    return f"{x:+.2f}%"


def format_open(s: dict) -> tuple[str, str, str, str]:
    """Returns (title, body, priority, tags)."""
    title = f"📊 Open · {_money(s['equity'])} · life {_pct(s['lifetime_pct'])}"
    parts = [
        f"Day: {_signed_money(s['day_change'])} ({_pct(s['day_pct'])})  "
        f"·  Life: {_signed_money(s['lifetime_change'])} ({_pct(s['lifetime_pct'])})",
        f"Cash: {_money(s['cash'])} · Buying power: {_money(s['buying_power'])}",
        f"Open positions: {len(s['positions'])}",
    ]
    if s["positions"]:
        parts.append("")
        for p in s["positions"]:
            unrl = float(p.unrealized_pl or 0)
            parts.append(f"  {p.symbol} {_signed_money(unrl)}")
    return title, "\n".join(parts), PRIORITY_DEFAULT, "bar_chart"


def format_intraday(s: dict) -> tuple[str, str, str, str] | None:
    """Returns (title, body, priority, tags), or None if nothing's changed
    enough to be worth a push (no positions, no fills, day P&L within $1)."""
    if (not s["positions"] and not s["fills_today"]
            and abs(s["day_change"]) < 1.0):
        return None  # caller will skip the push

    now_et = datetime.now(ET).strftime("%H:%M")
    title = (f"⏰ {now_et} · {_money(s['equity'])} · "
             f"day {_pct(s['day_pct'])} · life {_pct(s['lifetime_pct'])}")

    parts = [
        f"Day: {_signed_money(s['day_change'])} ({_pct(s['day_pct'])})  "
        f"·  Life: {_signed_money(s['lifetime_change'])} ({_pct(s['lifetime_pct'])})",
    ]
    if s["positions"]:
        parts.append(f"Open: {len(s['positions'])} (unrealized {_signed_money(s['unrealized'])})")
    if s["fills_today"]:
        parts.append(f"Fills today: {len(s['fills_today'])}")
    if s["positions"]:
        parts.append("")
        for p in s["positions"]:
            unrl = float(p.unrealized_pl or 0)
            parts.append(f"  {p.symbol} {_signed_money(unrl)}")
    return title, "\n".join(parts), PRIORITY_DEFAULT, "clock1"


def format_close(s: dict) -> tuple[str, str, str, str]:
    emoji = "📈" if s["day_change"] >= 0 else "📉"
    title = (f"{emoji} Close · {_money(s['equity'])} · "
             f"day {_pct(s['day_pct'])} · life {_pct(s['lifetime_pct'])}")
    parts = [
        f"Day: {_signed_money(s['day_change'])} ({_pct(s['day_pct'])})  "
        f"·  Life: {_signed_money(s['lifetime_change'])} ({_pct(s['lifetime_pct'])})",
        f"Open: {len(s['positions'])} · Fills today: {len(s['fills_today'])}",
    ]
    if s["positions"]:
        parts.append("")
        parts.append("Positions:")
        for p in s["positions"]:
            unrl = float(p.unrealized_pl or 0)
            parts.append(f"  {p.symbol} {_signed_money(unrl)}")
    if s["fills_today"]:
        parts.append("")
        parts.append("Today's fills:")
        for o in s["fills_today"]:
            t = o.filled_at.astimezone(ET).strftime("%H:%M")
            px = float(o.filled_avg_price) if o.filled_avg_price else 0.0
            side = o.side.value if o.side else "mleg"
            sym = o.symbol or "(multi-leg)"
            parts.append(f"  {t} {side} {sym} x{o.filled_qty} @ ${px:.2f}")
    tags = "chart_with_upwards_trend" if s["day_change"] >= 0 else "chart_with_downwards_trend"
    return title, "\n".join(parts), PRIORITY_DEFAULT, tags


def send_report(notifiers: list, when: str) -> bool:
    """Send open/intraday/close report. Returns True if sent, False if skipped."""
    s = get_summary()
    if when == "open":
        title, body, priority, tags = format_open(s)
    elif when == "intraday":
        result = format_intraday(s)
        if result is None:
            print(f"  [intraday] skipping push — no activity yet")
            return False
        title, body, priority, tags = result
    else:
        title, body, priority, tags = format_close(s)
    dispatch(notifiers, title, body, priority=priority, tags=tags)
    return True


if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()
    s = get_summary()
    print("=== OPEN ===")
    t, b, _, _ = format_open(s); print(t); print(b)
    print("\n=== INTRADAY ===")
    r = format_intraday(s)
    if r:
        t, b, _, _ = r; print(t); print(b)
    else:
        print("(skipped — no activity)")
    print("\n=== CLOSE ===")
    t, b, _, _ = format_close(s); print(t); print(b)
