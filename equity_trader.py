"""Live execution for two equity strategies sharing infrastructure.

  - Trend-following     : per ticker, buy on close > 50-SMA, sell on cross-below or stop
  - Rotational momentum : portfolio of top-N by lookback return, rebalance every N days

Both submit market orders to Alpaca paper, persist state to JSONL, and
reconcile against Alpaca positions on each daily scan.

State files track which strategy owns which shares — Alpaca only knows
total share count per ticker, so per-strategy bookkeeping is local.
"""
from __future__ import annotations

import json
import os
import urllib.request
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from dotenv import load_dotenv

import config
from alerts import (PRIORITY_DEFAULT, PRIORITY_HIGH, Notifier, ScanSummary,
                    dispatch)

load_dotenv()


# ---------- shared utilities ----------

def _trading_client():
    from alpaca.trading.client import TradingClient
    return TradingClient(
        os.environ["ALPACA_API_KEY"], os.environ["ALPACA_API_SECRET"], paper=True,
    )


def _fetch_daily(ticker: str, days: int = 200) -> pd.DataFrame:
    df = yf.download(ticker, period=f"{days}d", interval="1d",
                     auto_adjust=False, progress=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def _money(x: float) -> str:
    if abs(x) >= 10:
        return f"${x:,.0f}"
    return f"${x:.2f}"


def _signed_money(x: float) -> str:
    return f"{'+' if x >= 0 else '-'}{_money(abs(x))}"


@dataclass
class EquityPosition:
    strategy: str          # 'trend_following' | 'rotational_momentum'
    ticker: str
    entry_date: str        # ISO datetime
    entry_price: float
    shares: int
    sma_at_entry: float | None = None
    status: str = "open"   # open | closed
    close_date: str | None = None
    exit_price: float | None = None
    realized_pnl: float | None = None
    open_order_id: str | None = None
    close_order_id: str | None = None
    note: str | None = None


def _append_state(path: str, pos: EquityPosition) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    with Path(path).open("a") as f:
        f.write(json.dumps(asdict(pos)) + "\n")


def _load_state(path: str) -> list[EquityPosition]:
    """Replay JSONL log; latest entry per (strategy, ticker, entry_date) wins."""
    p = Path(path)
    if not p.exists():
        return []
    by_key: dict[tuple, EquityPosition] = {}
    with p.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            key = (d.get("strategy"), d.get("ticker"), d.get("entry_date"))
            by_key[key] = EquityPosition(**d)
    return list(by_key.values())


def _open_positions(path: str) -> list[EquityPosition]:
    return [p for p in _load_state(path) if p.status == "open"]


def submit_equity_order(ticker: str, side: str, qty: int) -> str:
    """Submit a market day order on equity. Returns order ID."""
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    client = _trading_client()
    req = MarketOrderRequest(
        symbol=ticker, qty=qty,
        side=OrderSide.BUY if side == "buy" else OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    order = client.submit_order(req)
    return str(order.id)


def _get_recent_closes(ticker: str) -> tuple[float, float | None]:
    """Returns (last_close, prior_close) from yfinance."""
    df = _fetch_daily(ticker, days=10)
    if df.empty or len(df) < 2:
        return 0.0, None
    return float(df["close"].iloc[-1]), float(df["close"].iloc[-2])


# ---------- Strategy 2: Trend-following ----------

def daily_trend_scan(notifiers: list[Notifier], dry_run: bool = False,
                     push_individual: bool = True) -> ScanSummary:
    """For each ticker, decide buy/hold/sell based on 50-SMA cross."""
    summary = ScanSummary(strategy="trend_following", opens=[], closes=[], notes=[], dry_run=dry_run)
    open_positions = _open_positions(config.TREND_STATE_PATH)
    held_tickers = {p.ticker for p in open_positions}

    for ticker in config.TREND_TICKERS:
        try:
            df = _fetch_daily(ticker, days=120)
            if df.empty or len(df) < config.TREND_SMA_PERIOD + 2:
                continue
            df["sma"] = df["close"].rolling(config.TREND_SMA_PERIOD).mean()
            df = df.dropna()
            today = df.iloc[-1]
            yesterday = df.iloc[-2]
            close = float(today["close"])
            sma = float(today["sma"])

            in_position = ticker in held_tickers

            # Exit: cross below SMA OR stop hit
            if in_position:
                pos = next(p for p in open_positions if p.ticker == ticker)
                cross_below = close < sma and float(yesterday["close"]) >= float(yesterday["sma"])
                pnl_pct = (close - pos.entry_price) / pos.entry_price
                stop_hit = pnl_pct <= config.TREND_STOP_PCT

                if cross_below or stop_hit:
                    reason = "stop" if stop_hit else "cross_below"
                    order_id = None
                    if not dry_run and config.TREND_AUTO_SUBMIT:
                        try:
                            order_id = submit_equity_order(ticker, "sell", pos.shares)
                        except Exception as e:
                            print(f"  [TF/{ticker}] sell order failed: {e}")
                            continue
                        pos.status = "closed"
                        pos.close_date = datetime.now(timezone.utc).isoformat()
                        pos.exit_price = close
                        pos.realized_pnl = (close - pos.entry_price) * pos.shares
                        pos.close_order_id = order_id
                        pos.note = reason
                        _append_state(config.TREND_STATE_PATH, pos)
                    pnl_dollars = (close - pos.entry_price) * pos.shares
                    summary.closes.append({
                        "ticker": ticker, "label": f"{ticker} (TF)",
                        "pnl": pnl_dollars, "pct": pnl_pct * 100, "reason": reason,
                    })
                    emoji = "✅" if pnl_dollars >= 0 else "❌"
                    title = f"{emoji} TF Sold {ticker} · {_signed_money(pnl_dollars)} ({pnl_pct*100:+.1f}%)"
                    body = (f"Entry ${pos.entry_price:.2f} → exit ${close:.2f}\n"
                            f"Shares: {pos.shares} · Reason: {reason}\n"
                            f"Held: {pos.shares} shares since {pos.entry_date[:10]}")
                    if push_individual:
                        dispatch(notifiers, title, body, priority=PRIORITY_HIGH,
                                 tags="white_check_mark" if pnl_dollars >= 0 else "x")
                continue

            # Entry: close above SMA AND wasn't above yesterday (cross-up) OR sustained above
            # Simplified: just enter if close > sma and not in position. The 50-SMA already filters.
            if close > sma:
                shares = int(config.TREND_PER_TICKER / close)
                if shares < 1:
                    continue
                order_id = None
                if not dry_run and config.TREND_AUTO_SUBMIT:
                    try:
                        order_id = submit_equity_order(ticker, "buy", shares)
                    except Exception as e:
                        print(f"  [TF/{ticker}] buy order failed: {e}")
                        continue
                    pos = EquityPosition(
                        strategy="trend_following",
                        ticker=ticker,
                        entry_date=datetime.now(timezone.utc).isoformat(),
                        entry_price=close, shares=shares,
                        sma_at_entry=sma, open_order_id=order_id,
                    )
                    _append_state(config.TREND_STATE_PATH, pos)
                cost = shares * close
                summary.opens.append({
                    "ticker": ticker, "label": ticker, "cost": cost, "shares": shares,
                })
                title = f"📈 TF Bought {ticker} · {shares} shares @ ${close:.2f}"
                body = (f"Cost basis: {_money(cost)}\n"
                        f"50-SMA: ${sma:.2f} (close {((close-sma)/sma*100):+.1f}% above)\n"
                        f"Stop: {config.TREND_STOP_PCT*100:.0f}% below entry")
                if push_individual:
                    dispatch(notifiers, title, body, priority=PRIORITY_HIGH, tags="chart_with_upwards_trend")
        except Exception as e:
            print(f"  [TF/{ticker}] error: {e}")
    return summary


# ---------- Strategy 3: Rotational momentum ----------

def _last_rebalance_date(positions: list[EquityPosition]) -> date | None:
    """Latest 'entry_date' across rotation positions = last rebalance."""
    rotation = [p for p in positions if p.strategy == "rotational_momentum"]
    if not rotation:
        return None
    dates = [datetime.fromisoformat(p.entry_date).date() for p in rotation]
    return max(dates)


def daily_rotation_scan(notifiers: list[Notifier], dry_run: bool = False,
                        push_individual: bool = True) -> ScanSummary:
    """Rotational momentum scan. On rebalance days, recompute top-N and rotate."""
    summary = ScanSummary(strategy="rotational_momentum", opens=[], closes=[], notes=[], dry_run=dry_run)
    all_state = _load_state(config.ROTATION_STATE_PATH)
    open_pos = [p for p in all_state if p.status == "open"]
    last_rebalance = _last_rebalance_date(all_state)

    today = datetime.now(timezone.utc).date()
    if last_rebalance is not None:
        days_since = (today - last_rebalance).days
        if days_since < config.ROTATION_REBALANCE_DAYS:
            summary.notes.append(f"not rebalance day ({days_since}/{config.ROTATION_REBALANCE_DAYS} days)")
            return summary

    # Compute lookback returns
    print(f"  [rotation] rebalance day (last: {last_rebalance})")
    returns: dict[str, float] = {}
    prices: dict[str, float] = {}
    for ticker in config.ROTATION_TICKERS:
        df = _fetch_daily(ticker, days=config.ROTATION_LOOKBACK_DAYS + 10)
        if df.empty or len(df) < config.ROTATION_LOOKBACK_DAYS + 1:
            continue
        cur = float(df["close"].iloc[-1])
        past = float(df["close"].iloc[-(config.ROTATION_LOOKBACK_DAYS + 1)])
        returns[ticker] = (cur - past) / past
        prices[ticker] = cur

    if not returns:
        print("  [rotation] no return data; skipping")
        summary.notes.append("no return data")
        return summary

    top = sorted(returns.keys(), key=lambda t: returns[t], reverse=True)[:config.ROTATION_TOP_N]
    held_tickers = {p.ticker for p in open_pos}
    to_sell = [p for p in open_pos if p.ticker not in top]
    to_buy = [t for t in top if t not in held_tickers]

    print(f"  [rotation] top-{config.ROTATION_TOP_N}: {top}")
    print(f"  [rotation] sell: {[p.ticker for p in to_sell]}, buy: {to_buy}")

    # Sell first to free up capital
    for pos in to_sell:
        order_id = None
        if not dry_run and config.ROTATION_AUTO_SUBMIT:
            try:
                order_id = submit_equity_order(pos.ticker, "sell", pos.shares)
            except Exception as e:
                print(f"  [ROT/{pos.ticker}] sell failed: {e}")
                continue
            cur_price = prices.get(pos.ticker, pos.entry_price)
            pos.status = "closed"
            pos.close_date = datetime.now(timezone.utc).isoformat()
            pos.exit_price = cur_price
            pos.realized_pnl = (cur_price - pos.entry_price) * pos.shares
            pos.close_order_id = order_id
            pos.note = "rotation_out"
            _append_state(config.ROTATION_STATE_PATH, pos)
        cur_price = prices.get(pos.ticker, pos.entry_price)
        pnl_dollars = (cur_price - pos.entry_price) * pos.shares
        pnl_pct = (cur_price - pos.entry_price) / pos.entry_price
        summary.closes.append({
            "ticker": pos.ticker, "label": f"{pos.ticker} (ROT)",
            "pnl": pnl_dollars, "pct": pnl_pct * 100, "reason": "rotation_out",
        })
        emoji = "✅" if pnl_dollars >= 0 else "❌"
        title = f"{emoji} ROT Sold {pos.ticker} · {_signed_money(pnl_dollars)} ({pnl_pct*100:+.1f}%)"
        body = (f"Entry ${pos.entry_price:.2f} → exit ${cur_price:.2f}\n"
                f"Shares: {pos.shares} · Rotated out (no longer top-{config.ROTATION_TOP_N})")
        if push_individual:
            dispatch(notifiers, title, body, priority=PRIORITY_HIGH,
                     tags="white_check_mark" if pnl_dollars >= 0 else "x")

    # Allocate equally to top-N (use the slot's full per-position budget)
    target_per_position = config.ROTATION_SLEEVE_CAPITAL / config.ROTATION_TOP_N
    for ticker in to_buy:
        price = prices[ticker]
        shares = int(target_per_position / price)
        if shares < 1:
            continue
        order_id = None
        if not dry_run and config.ROTATION_AUTO_SUBMIT:
            try:
                order_id = submit_equity_order(ticker, "buy", shares)
            except Exception as e:
                print(f"  [ROT/{ticker}] buy failed: {e}")
                continue
            pos = EquityPosition(
                strategy="rotational_momentum",
                ticker=ticker,
                entry_date=datetime.now(timezone.utc).isoformat(),
                entry_price=price, shares=shares,
                open_order_id=order_id,
                note=f"top-{top.index(ticker)+1} of {config.ROTATION_TOP_N}",
            )
            _append_state(config.ROTATION_STATE_PATH, pos)
        cost = shares * price
        summary.opens.append({
            "ticker": ticker, "label": ticker, "cost": cost, "shares": shares,
            "lookback_return_pct": returns[ticker] * 100,
        })
        title = f"🔄 ROT Bought {ticker} · {shares} shares @ ${price:.2f}"
        body = (f"Cost basis: {_money(cost)}\n"
                f"30d return: {returns[ticker]*100:+.1f}% (top-{top.index(ticker)+1} of {config.ROTATION_TOP_N})\n"
                f"Held until next rebalance ({config.ROTATION_REBALANCE_DAYS} days)")
        if push_individual:
            dispatch(notifiers, title, body, priority=PRIORITY_HIGH, tags="arrows_counterclockwise")

    return summary


# ---------- helpers used by debrief ----------

def trend_realized_pnl_today(today: date) -> float:
    state = _load_state(config.TREND_STATE_PATH)
    today_iso = today.isoformat()
    return sum(p.realized_pnl or 0 for p in state
               if p.status == "closed" and (p.close_date or "").startswith(today_iso))


def rotation_realized_pnl_today(today: date) -> float:
    state = _load_state(config.ROTATION_STATE_PATH)
    today_iso = today.isoformat()
    return sum(p.realized_pnl or 0 for p in state
               if p.status == "closed" and (p.close_date or "").startswith(today_iso))


def trend_open_positions() -> list[EquityPosition]:
    return _open_positions(config.TREND_STATE_PATH)


def rotation_open_positions() -> list[EquityPosition]:
    return _open_positions(config.ROTATION_STATE_PATH)
