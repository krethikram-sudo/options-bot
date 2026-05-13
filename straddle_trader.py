"""Live execution for selective earnings straddles (AVGO + MRVL only).

Backtest showed only tickers with >10% avg earnings move are profitable; we
restrict to AVGO and MRVL where the data showed clear edge.

Daily scan:
  - For each STRADDLE_TICKERS, look up next earnings date.
  - If earnings is exactly 1 trading day away and no open position: open ATM
    straddle on the nearest weekly expiry after earnings.
  - If we have an open position past earnings + 1: close it.

Open = market multi-leg debit order (buy call + buy put).
Close = market multi-leg credit order (sell call + sell put).
"""
from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

import config
from alerts import PRIORITY_HIGH, Notifier, ScanSummary, dispatch
from validate_chains import find_target_expiry_chain, get_chain_snapshots, get_spot

load_dotenv()


# ---------- state ----------

@dataclass
class StraddlePosition:
    ticker: str
    earnings_date: str         # ISO date the earnings was/are scheduled
    open_date: str             # ISO datetime
    call_symbol: str
    put_symbol: str
    strike: float
    expiry: str                # ISO date
    qty: int
    entry_premium: float       # debit per share (call+put)
    entry_cost_total: float    # entry_premium * 100 * qty
    status: str = "open"       # open | closed
    close_date: str | None = None
    exit_premium: float | None = None
    realized_pnl: float | None = None
    open_order_id: str | None = None
    close_order_id: str | None = None


def _append_state(pos: StraddlePosition) -> None:
    Path(config.STRADDLE_STATE_PATH).parent.mkdir(parents=True, exist_ok=True)
    with Path(config.STRADDLE_STATE_PATH).open("a") as f:
        f.write(json.dumps(asdict(pos)) + "\n")


def _load_state() -> list[StraddlePosition]:
    p = Path(config.STRADDLE_STATE_PATH)
    if not p.exists():
        return []
    by_key: dict[tuple, StraddlePosition] = {}
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (d["ticker"], d["call_symbol"], d["put_symbol"])
            by_key[key] = StraddlePosition(**d)
    return list(by_key.values())


def open_positions() -> list[StraddlePosition]:
    return [p for p in _load_state() if p.status == "open"]


# ---------- earnings ----------

def get_next_earnings_date(ticker: str) -> date | None:
    """Returns the ticker's next upcoming earnings date, or None if not scheduled within 14 days."""
    try:
        ed = yf.Ticker(ticker).earnings_dates
    except Exception:
        return None
    if ed is None or ed.empty:
        return None
    today = pd.Timestamp.now()
    if "Reported EPS" in ed.columns:
        future = ed[ed["Reported EPS"].isna()]
    else:
        future = ed
    if future.empty:
        return None
    future_idx = future.index.tz_localize(None) if future.index.tz is not None else future.index
    upcoming = future_idx[(future_idx > today) & (future_idx <= today + pd.Timedelta(days=14))]
    if len(upcoming) == 0:
        return None
    return min(upcoming).date()


# ---------- order submission ----------

def _trading_client():
    from alpaca.trading.client import TradingClient
    return TradingClient(
        os.environ["ALPACA_API_KEY"], os.environ["ALPACA_API_SECRET"], paper=True,
    )


def _build_straddle_legs(call_symbol: str, put_symbol: str, action: str):
    """action='open' -> BUY both. action='close' -> SELL both."""
    from alpaca.trading.enums import OrderSide, PositionIntent
    from alpaca.trading.requests import OptionLegRequest

    if action == "open":
        side = OrderSide.BUY
        intent = PositionIntent.BUY_TO_OPEN
    else:
        side = OrderSide.SELL
        intent = PositionIntent.SELL_TO_CLOSE

    return [
        OptionLegRequest(symbol=call_symbol, ratio_qty=1, side=side, position_intent=intent),
        OptionLegRequest(symbol=put_symbol, ratio_qty=1, side=side, position_intent=intent),
    ]


def submit_open_straddle(call_sym: str, put_sym: str, qty: int, limit_debit: float) -> str:
    from alpaca.trading.enums import OrderClass, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest

    legs = _build_straddle_legs(call_sym, put_sym, "open")
    req = LimitOrderRequest(
        order_class=OrderClass.MLEG,
        legs=legs, qty=qty,
        time_in_force=TimeInForce.DAY,
        limit_price=round(limit_debit, 2),  # we PAY this; positive number
    )
    client = _trading_client()
    order = client.submit_order(req)
    return str(order.id)


def submit_close_straddle(call_sym: str, put_sym: str, qty: int, limit_credit: float) -> str:
    from alpaca.trading.enums import OrderClass, TimeInForce
    from alpaca.trading.requests import LimitOrderRequest

    legs = _build_straddle_legs(call_sym, put_sym, "close")
    req = LimitOrderRequest(
        order_class=OrderClass.MLEG,
        legs=legs, qty=qty,
        time_in_force=TimeInForce.DAY,
        limit_price=round(limit_credit, 2),
    )
    client = _trading_client()
    order = client.submit_order(req)
    return str(order.id)


# ---------- candidate finding ----------

def find_atm_straddle_contracts(ticker: str, target_dte: int) -> tuple[str, str, float, date] | None:
    """Returns (call_symbol, put_symbol, atm_strike, expiry) for nearest weekly post-earnings."""
    from alpaca.trading.enums import AssetStatus, ContractType
    from alpaca.trading.requests import GetOptionContractsRequest

    spot = get_spot(ticker)
    today = date.today()
    target = today + timedelta(days=target_dte)

    client = _trading_client()
    # Pull both calls and puts
    call_req = GetOptionContractsRequest(
        underlying_symbols=[ticker], type=ContractType.CALL,
        status=AssetStatus.ACTIVE,
        expiration_date_gte=today + timedelta(days=max(target_dte - 5, 1)),
        expiration_date_lte=today + timedelta(days=target_dte + 14),
        limit=500,
    )
    put_req = GetOptionContractsRequest(
        underlying_symbols=[ticker], type=ContractType.PUT,
        status=AssetStatus.ACTIVE,
        expiration_date_gte=today + timedelta(days=max(target_dte - 5, 1)),
        expiration_date_lte=today + timedelta(days=target_dte + 14),
        limit=500,
    )
    calls = client.get_option_contracts(call_req).option_contracts
    puts = client.get_option_contracts(put_req).option_contracts
    if not calls or not puts:
        return None

    # Pick expiry closest to target
    call_expirations = {c.expiration_date for c in calls}
    put_expirations = {p.expiration_date for p in puts}
    common = call_expirations & put_expirations
    if not common:
        return None
    expiry = min(common, key=lambda e: abs((e - target).days))

    # Filter to that expiry, find closest-to-spot strike
    expiry_calls = [c for c in calls if c.expiration_date == expiry]
    expiry_puts = [p for p in puts if p.expiration_date == expiry]

    atm_call = min(expiry_calls, key=lambda c: abs(float(c.strike_price) - spot))
    # Find put with same strike if available, else closest to ATM call's strike
    target_strike = float(atm_call.strike_price)
    same_strike_puts = [p for p in expiry_puts if float(p.strike_price) == target_strike]
    atm_put = same_strike_puts[0] if same_strike_puts else min(
        expiry_puts, key=lambda p: abs(float(p.strike_price) - target_strike)
    )
    if float(atm_put.strike_price) != target_strike:
        return None  # require matched strikes for true straddle

    return atm_call.symbol, atm_put.symbol, target_strike, expiry


def get_straddle_quote(call_sym: str, put_sym: str) -> tuple[float, float] | None:
    """Returns (mid_debit, conservative_debit) per share for the straddle."""
    quotes = get_chain_snapshots([call_sym, put_sym])
    cq = quotes.get(call_sym)
    pq = quotes.get(put_sym)
    if not cq or not pq:
        return None
    cb, ca = float(cq.bid_price or 0), float(cq.ask_price or 0)
    pb, pa = float(pq.bid_price or 0), float(pq.ask_price or 0)
    if ca == 0 or pa == 0:
        return None
    mid = (cb + ca) / 2 + (pb + pa) / 2
    conservative = ca + pa  # buy both at ask = pay full spread
    return mid, conservative


# ---------- daily scan ----------

def daily_straddle_scan(notifiers: list[Notifier], dry_run: bool = False,
                        push_individual: bool = True) -> ScanSummary:
    """One pass: for each ticker, decide open/close based on earnings proximity."""
    summary = ScanSummary(strategy="earnings_straddle", opens=[], closes=[], notes=[], dry_run=dry_run)
    open_pos = open_positions()
    open_tickers = {p.ticker for p in open_pos}
    today = date.today()

    # 1) Close any positions where earnings has now passed
    for pos in open_pos:
        ed = date.fromisoformat(pos.earnings_date)
        days_since = (today - ed).days
        if days_since >= config.STRADDLE_DAYS_AFTER:
            quote = get_straddle_quote(pos.call_symbol, pos.put_symbol)
            if quote is None:
                print(f"  [STR/{pos.ticker}] no quote, skipping close")
                continue
            mid, _ = quote
            order_id = None
            if not dry_run and config.STRADDLE_AUTO_SUBMIT:
                try:
                    # accept fills slightly below mid for fast close
                    order_id = submit_close_straddle(
                        pos.call_symbol, pos.put_symbol, pos.qty,
                        limit_credit=mid * 0.95,
                    )
                except Exception as e:
                    print(f"  [STR/{pos.ticker}] close failed: {e}")
                    continue
                exit_dollars = mid * 100 * pos.qty
                realized = exit_dollars - pos.entry_cost_total
                pos.status = "closed"
                pos.close_date = datetime.now(timezone.utc).isoformat()
                pos.exit_premium = mid
                pos.realized_pnl = realized
                pos.close_order_id = order_id
                _append_state(pos)
            realized = mid * 100 * pos.qty - pos.entry_cost_total
            summary.closes.append({
                "ticker": pos.ticker, "label": f"{pos.ticker} ${pos.strike:g} STR",
                "pnl": realized, "pct": (realized / pos.entry_cost_total * 100) if pos.entry_cost_total else 0,
                "reason": "post_earnings_close",
            })
            emoji = "✅" if realized >= 0 else "❌"
            sign = "+" if realized >= 0 else "-"
            title = (f"{emoji} STR Closed {pos.ticker} ${pos.strike:g} straddle · "
                     f"{sign}${abs(realized):,.0f}")
            body = (f"Entry premium: ${pos.entry_premium:.2f}/sh\n"
                    f"Closed at:     ${mid:.2f}/sh\n"
                    f"Realized P&L:  {sign}${abs(realized):,.0f}\n"
                    f"Earnings was:  {pos.earnings_date}")
            tags = "white_check_mark" if realized >= 0 else "x"
            if push_individual:
                dispatch(notifiers, title, body, priority=PRIORITY_HIGH, tags=tags)

    # 2) Open new positions for tickers whose earnings is exactly DAYS_BEFORE away
    for ticker in config.STRADDLE_TICKERS:
        if ticker in open_tickers:
            continue
        ed = get_next_earnings_date(ticker)
        if ed is None:
            continue
        days_until = (ed - today).days
        if days_until != config.STRADDLE_DAYS_BEFORE:
            continue

        # earnings is tomorrow (or DAYS_BEFORE away) → open straddle
        contracts = find_atm_straddle_contracts(ticker, target_dte=config.STRADDLE_DTE_TARGET)
        if contracts is None:
            print(f"  [STR/{ticker}] no matching ATM straddle on weekly expiry")
            continue
        call_sym, put_sym, strike, expiry = contracts
        quote = get_straddle_quote(call_sym, put_sym)
        if quote is None:
            print(f"  [STR/{ticker}] no quote")
            continue
        mid, conservative = quote
        if mid <= 0:
            continue

        order_id = None
        if not dry_run and config.STRADDLE_AUTO_SUBMIT:
            try:
                order_id = submit_open_straddle(
                    call_sym, put_sym, qty=config.STRADDLE_QTY_PER_TRADE,
                    limit_debit=mid * 1.05,  # willing to pay slightly above mid
                )
            except Exception as e:
                print(f"  [STR/{ticker}] open failed: {e}")
                continue
            entry_cost = mid * 100 * config.STRADDLE_QTY_PER_TRADE
            pos = StraddlePosition(
                ticker=ticker, earnings_date=ed.isoformat(),
                open_date=datetime.now(timezone.utc).isoformat(),
                call_symbol=call_sym, put_symbol=put_sym,
                strike=strike, expiry=expiry.isoformat(),
                qty=config.STRADDLE_QTY_PER_TRADE,
                entry_premium=mid, entry_cost_total=entry_cost,
                open_order_id=order_id,
            )
            _append_state(pos)
        cost = mid * 100 * config.STRADDLE_QTY_PER_TRADE
        summary.opens.append({
            "ticker": ticker, "label": f"{ticker} ${strike:g} STR",
            "cost": cost, "earnings_date": ed.isoformat(),
        })
        title = f"💎 STR Opened {ticker} ${strike:g} straddle · cost ${cost:,.0f}"
        body = (f"Earnings: {ed} · Expiry: {expiry}\n"
                f"Entry premium: ${mid:.2f}/sh\n"
                f"Breakeven: ±${mid:.2f} from ${strike:g}\n"
                f"Qty {config.STRADDLE_QTY_PER_TRADE}")
        if push_individual:
            dispatch(notifiers, title, body, priority=PRIORITY_HIGH, tags="diamond_shape_with_a_dot_inside")

    return summary


# ---------- helpers for debrief ----------

def straddle_realized_pnl_today(today: date) -> float:
    today_iso = today.isoformat()
    return sum(p.realized_pnl or 0 for p in _load_state()
               if p.status == "closed" and (p.close_date or "").startswith(today_iso))


def straddle_open_positions() -> list[StraddlePosition]:
    return open_positions()
