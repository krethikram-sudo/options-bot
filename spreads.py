"""Multi-leg credit spread strategies + backtester.

Currently implemented:
  - bull_put_spread : sell OTM put + buy further-OTM put (defined-risk, neutral-to-bullish)

Backtest model:
  - Daily bars (yfinance).
  - IV is rolling 30-day realized volatility of daily log returns (annualized).
  - Open one position at a time, sequentially. Hold until profit target hit
    or expiry (whichever first).
  - At expiry, intrinsic value is used.

This is a Black-Scholes synthesis, not real chain data. Treat results as
directional, not precise.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date as _date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from tabulate import tabulate

from black_scholes import bs_price, find_strike_at_delta

RATE = 0.045


@dataclass
class BullPutSpread:
    underlying: str
    open_date: _date
    expiry_date: _date
    short_strike: float
    long_strike: float
    spot_at_open: float
    iv_at_open: float
    credit_received: float   # per spread (1 contract = $100 notional per $1)

    @property
    def width(self) -> float:
        return self.short_strike - self.long_strike

    @property
    def max_profit(self) -> float:
        return self.credit_received

    @property
    def max_loss(self) -> float:
        return self.width - self.credit_received


def _daily_bars(ticker: str, days: int = 365) -> pd.DataFrame:
    df = yf.download(ticker, period=f"{days}d", interval="1d",
                     auto_adjust=False, progress=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def _realized_vol(close: pd.Series, window: int = 30) -> pd.Series:
    """Annualized realized vol from daily log returns."""
    log_ret = np.log(close / close.shift(1))
    return log_ret.rolling(window).std() * math.sqrt(252)


def open_bull_put(
    ticker: str, spot: float, today: _date, iv: float,
    dte: int = 30, target_short_delta: float = 0.16, width_pct: float = 0.05,
) -> BullPutSpread | None:
    if iv <= 0 or math.isnan(iv):
        return None
    expiry = today + timedelta(days=dte)
    t = dte / 365.0

    short_strike = find_strike_at_delta(spot, target_short_delta, t, RATE, iv, "put")
    short_strike = round(short_strike)
    long_strike = round(short_strike - max(spot * width_pct, 1.0))
    if long_strike >= short_strike:
        long_strike = short_strike - 1
    if long_strike <= 0:
        return None

    short_premium = bs_price(spot, short_strike, t, RATE, iv, "put")
    long_premium = bs_price(spot, long_strike, t, RATE, iv, "put")
    credit = short_premium - long_premium
    if credit <= 0.05:
        return None

    return BullPutSpread(
        underlying=ticker, open_date=today, expiry_date=expiry,
        short_strike=short_strike, long_strike=long_strike,
        spot_at_open=spot, iv_at_open=iv, credit_received=credit,
    )


def value_spread(spread: BullPutSpread, spot_now: float, today_now: _date, iv_now: float) -> float:
    """Returns the current LIABILITY (cost to buy back / close) of the spread."""
    days_left = (spread.expiry_date - today_now).days
    if days_left <= 0:
        # intrinsic at expiry (short put liability minus long put value)
        short_int = max(spread.short_strike - spot_now, 0.0)
        long_int = max(spread.long_strike - spot_now, 0.0)
        return short_int - long_int
    t = days_left / 365.0
    short_p = bs_price(spot_now, spread.short_strike, t, RATE, iv_now, "put")
    long_p = bs_price(spot_now, spread.long_strike, t, RATE, iv_now, "put")
    return short_p - long_p


def spread_pnl(spread: BullPutSpread, spot_now: float, today_now: _date, iv_now: float) -> float:
    return spread.credit_received - value_spread(spread, spot_now, today_now, iv_now)


# ---------- backtest ----------

@dataclass
class TradeResult:
    underlying: str
    open_date: _date
    exit_date: _date
    days_held: int
    spot_open: float
    spot_exit: float
    short_strike: float
    long_strike: float
    width: float
    credit: float
    pnl: float
    exit_reason: str

    @property
    def max_loss(self) -> float:
        return self.width - self.credit

    @property
    def roi_on_max_loss(self) -> float:
        return self.pnl / self.max_loss if self.max_loss > 0 else 0.0


def backtest_bull_put(
    ticker: str, days: int = 365, dte: int = 30,
    target_delta: float = 0.16, width_pct: float = 0.05,
    profit_target_frac: float = 0.50,
    iv_floor: float = 0.30, iv_ceiling: float = 1.50,
    iv_haircut: float = 1.0,
    bars: pd.DataFrame | None = None,
) -> list[TradeResult]:
    df = bars if bars is not None else _daily_bars(ticker, days=days)
    if df.empty or len(df) < 60:
        return []

    df["rv"] = _realized_vol(df["close"], window=30).clip(iv_floor, iv_ceiling) * iv_haircut
    closes = df["close"]
    rv = df["rv"]
    dates = [d.date() for d in df.index]

    trades: list[TradeResult] = []
    open_pos: BullPutSpread | None = None

    for i, today in enumerate(dates):
        spot = float(closes.iloc[i])
        iv = float(rv.iloc[i])

        if open_pos is not None:
            pnl = spread_pnl(open_pos, spot, today, iv)
            if pnl >= profit_target_frac * open_pos.max_profit or today >= open_pos.expiry_date:
                reason = "profit_target" if pnl >= profit_target_frac * open_pos.max_profit else "expiry"
                # at expiry exactly, lock in intrinsic (already handled by value_spread when days_left<=0)
                if today >= open_pos.expiry_date:
                    pnl = spread_pnl(open_pos, spot, today, iv)
                trades.append(TradeResult(
                    underlying=ticker, open_date=open_pos.open_date, exit_date=today,
                    days_held=(today - open_pos.open_date).days,
                    spot_open=open_pos.spot_at_open, spot_exit=spot,
                    short_strike=open_pos.short_strike, long_strike=open_pos.long_strike,
                    width=open_pos.width, credit=open_pos.credit_received,
                    pnl=pnl, exit_reason=reason,
                ))
                open_pos = None

        if open_pos is None and i + dte < len(dates) and not math.isnan(iv):
            open_pos = open_bull_put(ticker, spot, today, iv,
                                     dte=dte, target_short_delta=target_delta,
                                     width_pct=width_pct)
    return trades


# ---------- reporting ----------

def summarize(trades: list[TradeResult]) -> None:
    if not trades:
        print("No trades.")
        return

    df = pd.DataFrame([{
        "ticker": t.underlying,
        "open": t.open_date,
        "exit": t.exit_date,
        "days": t.days_held,
        "spot_o": round(t.spot_open, 2),
        "spot_x": round(t.spot_exit, 2),
        "short": t.short_strike,
        "long": t.long_strike,
        "width": round(t.width, 1),
        "credit": round(t.credit, 2),
        "max_loss": round(t.max_loss, 2),
        "pnl": round(t.pnl, 2),
        "roi%": round(t.roi_on_max_loss * 100, 1),
        "reason": t.exit_reason,
    } for t in trades])

    wins = (df["pnl"] > 0).sum()
    print(tabulate(df, headers="keys", tablefmt="simple", showindex=False))
    print()
    print(f"Trades: {len(df)}  Wins: {wins}  Win rate: {wins/len(df)*100:.1f}%")
    print(f"Avg PnL/trade: ${df['pnl'].mean():.2f}  "
          f"Median: ${df['pnl'].median():.2f}  "
          f"Sum: ${df['pnl'].sum():.2f}")
    print(f"Avg ROI on max-loss: {df['roi%'].mean():.2f}%  "
          f"Median: {df['roi%'].median():.2f}%")
    print(f"Best trade: ${df['pnl'].max():.2f}   Worst trade: ${df['pnl'].min():.2f}")
    print(f"Exit reasons: {df['reason'].value_counts().to_dict()}")


def run(tickers: list[str] | None = None) -> None:
    import config as _config
    tickers = tickers or _config.SPREAD_TICKERS

    all_trades: list[TradeResult] = []
    per_ticker_summary = []
    for ticker in tickers:
        print(f"\n--- {ticker} ---")
        trades = backtest_bull_put(ticker)
        if not trades:
            print("(no trades)")
            continue
        # show compact table per ticker
        wins = sum(1 for t in trades if t.pnl > 0)
        total_pnl = sum(t.pnl for t in trades)
        avg_roi = sum(t.roi_on_max_loss for t in trades) / len(trades) * 100
        print(f"{len(trades)} trades, {wins} wins ({wins/len(trades)*100:.1f}%), "
              f"total pnl=${total_pnl:.2f}, avg ROI on max-loss={avg_roi:.2f}%")
        per_ticker_summary.append({
            "ticker": ticker, "n": len(trades),
            "win_rate": round(wins/len(trades)*100, 1),
            "total_pnl": round(total_pnl, 2),
            "avg_roi%": round(avg_roi, 2),
        })
        all_trades.extend(trades)

    print("\n" + "=" * 60)
    print("PER-TICKER SUMMARY")
    print("=" * 60)
    if per_ticker_summary:
        print(tabulate(per_ticker_summary, headers="keys", tablefmt="simple", showindex=False))

    print("\n" + "=" * 60)
    print("ALL TRADES")
    print("=" * 60)
    summarize(all_trades)


if __name__ == "__main__":
    import sys
    run(sys.argv[1:] if len(sys.argv) > 1 else None)
