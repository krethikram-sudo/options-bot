"""Strategy 5: AI full-chain equal-weight basket.

The simplest, highest-Sharpe candidate from the strategy lab. ~50 tickers
across the AI value chain held at equal weight, rebalanced monthly. Uses
notional (fractional-share) orders so high-priced names (SNDK, AVGO) get
the same dollar exposure as low-priced ones.

State stored as a single JSON snapshot in `logs/chain_positions.json`:
    {
      "last_rebalance_date": "2026-05-04",
      "positions": {
         "NVDA": {"shares": 2.515, "avg_cost": 198.72, "total_invested": 500.00},
         ...
      }
    }
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone
from pathlib import Path

import yfinance as yf
from dotenv import load_dotenv

import config
from alerts import PRIORITY_HIGH, Notifier, ScanSummary, dispatch

load_dotenv()


# ---------- state ----------

def _load_state() -> dict:
    p = Path(config.CHAIN_STATE_PATH)
    if not p.exists():
        return {"last_rebalance_date": None, "positions": {}}
    try:
        with p.open() as f:
            return json.load(f)
    except Exception:
        return {"last_rebalance_date": None, "positions": {}}


def _save_state(state: dict) -> None:
    p = Path(config.CHAIN_STATE_PATH)
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w") as f:
        json.dump(state, f, indent=2, default=str)


# ---------- pricing ----------

def _trading_client():
    from alpaca.trading.client import TradingClient
    return TradingClient(os.environ["ALPACA_API_KEY"],
                         os.environ["ALPACA_API_SECRET"], paper=True)


def _stock_data_client():
    from alpaca.data.historical.stock import StockHistoricalDataClient
    return StockHistoricalDataClient(
        os.environ["ALPACA_API_KEY"], os.environ["ALPACA_API_SECRET"],
    )


def fetch_current_price(ticker: str) -> float | None:
    """Get latest price via Alpaca; fallback to yfinance close."""
    try:
        from alpaca.data.requests import StockLatestQuoteRequest
        client = _stock_data_client()
        q = client.get_stock_latest_quote(
            StockLatestQuoteRequest(symbol_or_symbols=ticker))[ticker]
        bid = float(q.bid_price or 0)
        ask = float(q.ask_price or 0)
        if bid > 0 and ask > 0:
            return (bid + ask) / 2
        if ask > 0:
            return ask
        if bid > 0:
            return bid
    except Exception:
        pass
    try:
        df = yf.download(ticker, period="5d", interval="1d",
                         auto_adjust=False, progress=False)
        if df.empty:
            return None
        if hasattr(df.columns, "get_level_values"):
            df.columns = df.columns.get_level_values(0)
        return float(df["Close"].iloc[-1])
    except Exception:
        return None


# ---------- order submission ----------

def submit_buy_notional(ticker: str, dollars: float) -> str | None:
    """Submit a notional-dollar buy order (fractional shares allowed)."""
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    if dollars < 1:
        return None
    client = _trading_client()
    req = MarketOrderRequest(
        symbol=ticker,
        notional=round(dollars, 2),
        side=OrderSide.BUY,
        time_in_force=TimeInForce.DAY,
    )
    order = client.submit_order(req)
    return str(order.id)


def submit_sell_shares(ticker: str, shares: float) -> str | None:
    """Submit a market sell of `shares` (fractional allowed)."""
    from alpaca.trading.enums import OrderSide, TimeInForce
    from alpaca.trading.requests import MarketOrderRequest

    if shares <= 0:
        return None
    client = _trading_client()
    req = MarketOrderRequest(
        symbol=ticker,
        qty=round(shares, 6),
        side=OrderSide.SELL,
        time_in_force=TimeInForce.DAY,
    )
    order = client.submit_order(req)
    return str(order.id)


# ---------- daily scan ----------

def daily_chain_scan(
    notifiers: list[Notifier],
    dry_run: bool = False,
    push_individual: bool = True,
) -> ScanSummary:
    """Once per CHAIN_REBALANCE_DAYS, target equal-weight across all CHAIN_TICKERS."""
    summary = ScanSummary(strategy="ai_full_chain", opens=[], closes=[],
                          notes=[], dry_run=dry_run)
    state = _load_state()
    today = datetime.now(timezone.utc).date()
    last_rebal_str = state.get("last_rebalance_date")

    if last_rebal_str:
        try:
            last_rebal = date.fromisoformat(last_rebal_str)
            days_since = (today - last_rebal).days
            if days_since < config.CHAIN_REBALANCE_DAYS:
                summary.notes.append(f"not rebalance day ({days_since}/{config.CHAIN_REBALANCE_DAYS}d since last)")
                return summary
        except Exception:
            pass

    target_per = config.CHAIN_SLEEVE_CAPITAL / len(config.CHAIN_TICKERS)
    print(f"  [chain] rebalance day. target ${target_per:.0f} per ticker × {len(config.CHAIN_TICKERS)} tickers")

    actions = 0
    for ticker in config.CHAIN_TICKERS:
        try:
            price = fetch_current_price(ticker)
            if price is None or price <= 0:
                print(f"  [chain/{ticker}] no price; skipping")
                continue
            cur = state["positions"].get(ticker, {"shares": 0.0, "avg_cost": 0.0, "total_invested": 0.0})
            cur_shares = float(cur.get("shares", 0))
            cur_value = cur_shares * price
            delta = target_per - cur_value
            drift = abs(delta) / target_per

            if drift < config.CHAIN_DRIFT_THRESHOLD:
                continue  # within tolerance; no order

            order_id: str | None = None
            if delta > 0:
                # buy
                if not dry_run and config.CHAIN_AUTO_SUBMIT:
                    try:
                        order_id = submit_buy_notional(ticker, delta)
                    except Exception as e:
                        print(f"  [chain/{ticker}] buy failed: {e}")
                        continue
                est_shares_added = delta / price
                new_shares = cur_shares + est_shares_added
                new_invested = float(cur.get("total_invested", 0)) + delta
                new_avg_cost = new_invested / new_shares if new_shares > 0 else price
                state["positions"][ticker] = {
                    "shares": round(new_shares, 6),
                    "avg_cost": round(new_avg_cost, 4),
                    "total_invested": round(new_invested, 2),
                    "last_price": round(price, 4),
                }
                summary.opens.append({
                    "ticker": ticker, "label": ticker,
                    "cost": round(delta, 2),
                    "price": round(price, 2),
                })
                actions += 1
            else:
                # sell partial (drift means we're overweight)
                shares_to_sell = abs(delta) / price
                if shares_to_sell > cur_shares:
                    shares_to_sell = cur_shares
                if not dry_run and config.CHAIN_AUTO_SUBMIT:
                    try:
                        order_id = submit_sell_shares(ticker, shares_to_sell)
                    except Exception as e:
                        print(f"  [chain/{ticker}] sell failed: {e}")
                        continue
                proceeds = shares_to_sell * price
                new_shares = cur_shares - shares_to_sell
                pnl = proceeds - (shares_to_sell * float(cur.get("avg_cost", price)))
                new_invested = float(cur.get("total_invested", 0)) - proceeds
                state["positions"][ticker] = {
                    "shares": round(new_shares, 6),
                    "avg_cost": float(cur.get("avg_cost", price)),
                    "total_invested": round(max(new_invested, 0), 2),
                    "last_price": round(price, 4),
                }
                summary.closes.append({
                    "ticker": ticker, "label": ticker,
                    "pnl": round(pnl, 2),
                    "pct": (pnl / (shares_to_sell * float(cur.get("avg_cost", price))) * 100)
                           if shares_to_sell * float(cur.get("avg_cost", price)) > 0 else 0,
                    "reason": "rebalance_trim",
                })
                actions += 1

            # Per-trade push (when not consolidating)
            if push_individual:
                if delta > 0:
                    title = f"📊 CHAIN Bought {ticker} · {delta:+.0f}"
                    body = (f"Notional: ${delta:.0f}\n"
                            f"Approx shares: {(delta/price):.4f} @ ${price:.2f}\n"
                            f"Order: {order_id or '(dry-run)'}")
                    dispatch(notifiers, title, body, priority=PRIORITY_HIGH, tags="bar_chart")
                else:
                    title = f"📊 CHAIN Trimmed {ticker} · -${abs(delta):.0f}"
                    body = (f"Sold {shares_to_sell:.4f} shares @ ${price:.2f}\n"
                            f"Order: {order_id or '(dry-run)'}")
                    dispatch(notifiers, title, body, priority=PRIORITY_HIGH, tags="bar_chart")
        except Exception as e:
            print(f"  [chain/{ticker}] error: {e}")

    # update last_rebalance_date if anything happened (or if first run)
    if actions > 0 or not last_rebal_str:
        state["last_rebalance_date"] = today.isoformat()
        if not dry_run:
            _save_state(state)

    print(f"  [chain] {actions} orders submitted")
    return summary


# ---------- helpers for debrief ----------

def chain_open_positions() -> dict:
    """Return current positions dict."""
    return _load_state().get("positions", {})


def chain_total_value(use_last_price: bool = True) -> float:
    """Estimate current total $ value of chain positions."""
    state = _load_state()
    total = 0.0
    for ticker, pos in state.get("positions", {}).items():
        shares = float(pos.get("shares", 0))
        if shares <= 0:
            continue
        if use_last_price:
            price = float(pos.get("last_price", pos.get("avg_cost", 0)))
        else:
            price = float(pos.get("avg_cost", 0))
        total += shares * price
    return total


def chain_realized_pnl_today(today: date) -> float:
    """Realized P&L for chain isn't tracked per-event yet; return 0 (or compute from orders later)."""
    return 0.0
