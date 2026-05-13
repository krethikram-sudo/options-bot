"""Earnings-driven long straddle backtest.

For each historical earnings date:
  - Buy ATM call + ATM put 1 trading day before earnings (close of T-1)
  - Sell both 1 trading day after earnings (close of T+1)

We don't have historical option chain data, so we synthesize prices via
Black-Scholes with regime-aware IV:
  - Pre-earnings IV  ≈ 1.6 × 30-day realized vol  (typical pre-event spike)
  - Post-earnings IV ≈ 0.75 × 30-day realized vol (post-crush)

This understates the IV crush in extreme cases and overstates it in mild
cases, but produces reasonable expectations for whether the strategy has
edge in aggregate.

The strategy wins when realized post-earnings move > implied move + IV
crush penalty. Loses otherwise.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf
from tabulate import tabulate

import config
from black_scholes import bs_price

RATE = 0.045


@dataclass
class StraddleTrade:
    ticker: str
    earnings_date: date
    entry_date: date
    exit_date: date
    spot_entry: float
    spot_exit: float
    move_pct: float
    strike: float
    iv_entry: float
    iv_exit: float
    premium_paid: float
    premium_received: float
    pnl: float
    pnl_pct: float
    days_held: int


def _fetch_daily(ticker: str, days: int = 730) -> pd.DataFrame:
    df = yf.download(ticker, period=f"{days}d", interval="1d",
                     auto_adjust=False, progress=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


def get_earnings_dates(ticker: str, lookback_years: int = 2) -> list[date]:
    try:
        ed = yf.Ticker(ticker).earnings_dates
    except Exception:
        return []
    if ed is None or ed.empty:
        return []
    cutoff = pd.Timestamp.now() - pd.Timedelta(days=365 * lookback_years)
    if "Reported EPS" in ed.columns:
        past = ed[ed["Reported EPS"].notna()]
    else:
        past = ed
    if past.empty:
        return []
    past_index = past.index.tz_localize(None) if past.index.tz is not None else past.index
    past = past[past_index >= cutoff]
    return sorted({d.date() for d in past.index})


def _realized_vol(closes: pd.Series, window: int = 30) -> float:
    log_ret = np.log(closes / closes.shift(1)).dropna()
    if len(log_ret) < window:
        return 0.0
    return float(log_ret.tail(window).std() * math.sqrt(252))


def backtest_earnings_straddle(
    ticker: str,
    contracts_per_trade: int = 1,
    days_to_expiry: int = 7,
    iv_pre_mult: float = 1.6,
    iv_post_mult: float = 0.75,
    bars: pd.DataFrame | None = None,
    earnings_dates: list[date] | None = None,
) -> list[StraddleTrade]:
    df = bars if bars is not None else _fetch_daily(ticker)
    if df.empty:
        return []
    if earnings_dates is None:
        earnings_dates = get_earnings_dates(ticker)
    if not earnings_dates:
        return []

    df_dates = [d.date() for d in df.index]

    trades: list[StraddleTrade] = []
    for ed in earnings_dates:
        # find entry idx: largest trading day strictly before ed
        before = [i for i, d in enumerate(df_dates) if d < ed]
        if not before:
            continue
        entry_idx = before[-1]

        # find exit idx: smallest trading day strictly after ed
        after = [i for i, d in enumerate(df_dates) if d > ed]
        if not after:
            continue
        exit_idx = after[0]

        if exit_idx <= entry_idx:
            continue

        entry_date = df_dates[entry_idx]
        exit_date = df_dates[exit_idx]
        spot_entry = float(df["close"].iloc[entry_idx])
        spot_exit = float(df["close"].iloc[exit_idx])

        if entry_idx < 30:
            continue
        rv = _realized_vol(df["close"].iloc[max(0, entry_idx - 30):entry_idx + 1])
        if rv <= 0 or rv > 2.5:
            continue

        iv_entry = rv * iv_pre_mult
        iv_exit = rv * iv_post_mult
        strike = round(spot_entry)

        t_entry = days_to_expiry / 365.0
        days_elapsed = (exit_date - entry_date).days
        t_exit = max((days_to_expiry - days_elapsed) / 365.0, 1 / 365.0 / 24)

        call_e = bs_price(spot_entry, strike, t_entry, RATE, iv_entry, "call")
        put_e = bs_price(spot_entry, strike, t_entry, RATE, iv_entry, "put")
        call_x = bs_price(spot_exit, strike, t_exit, RATE, iv_exit, "call")
        put_x = bs_price(spot_exit, strike, t_exit, RATE, iv_exit, "put")

        premium_paid = (call_e + put_e) * 100 * contracts_per_trade
        premium_received = (call_x + put_x) * 100 * contracts_per_trade
        if premium_paid <= 5.0:
            continue

        pnl = premium_received - premium_paid
        pnl_pct = pnl / premium_paid

        trades.append(StraddleTrade(
            ticker=ticker, earnings_date=ed,
            entry_date=entry_date, exit_date=exit_date,
            spot_entry=spot_entry, spot_exit=spot_exit,
            move_pct=(spot_exit - spot_entry) / spot_entry * 100,
            strike=strike, iv_entry=iv_entry, iv_exit=iv_exit,
            premium_paid=premium_paid, premium_received=premium_received,
            pnl=pnl, pnl_pct=pnl_pct,
            days_held=days_elapsed,
        ))

    return trades


def _summarize(trades: list[StraddleTrade]) -> None:
    if not trades:
        print("No trades."); return
    df = pd.DataFrame([{
        "ticker": t.ticker, "earnings": t.earnings_date,
        "spot_entry": round(t.spot_entry, 2),
        "spot_exit": round(t.spot_exit, 2),
        "move%": round(t.move_pct, 1),
        "iv_entry%": round(t.iv_entry * 100, 0),
        "iv_exit%": round(t.iv_exit * 100, 0),
        "paid$": round(t.premium_paid, 2),
        "got$": round(t.premium_received, 2),
        "pnl$": round(t.pnl, 2),
        "pnl%": round(t.pnl_pct * 100, 1),
    } for t in trades])

    wins = (df["pnl$"] > 0).sum()
    print(tabulate(df.tail(20), headers="keys", tablefmt="simple", showindex=False))
    print(f"\nTrades: {len(df)}  Wins: {wins} ({wins/len(df)*100:.1f}%)")
    print(f"Total PnL: ${df['pnl$'].sum():,.2f}  Avg per trade: ${df['pnl$'].mean():,.2f}")
    print(f"Avg pnl%: {df['pnl%'].mean():.1f}%  Median: {df['pnl%'].median():.1f}%")
    print(f"Best: ${df['pnl$'].max():,.2f}  Worst: ${df['pnl$'].min():,.2f}")
    print(f"Avg move on earnings day: {df['move%'].abs().mean():.2f}%")
    print()
    print("By ticker:")
    by = df.groupby("ticker").agg(n=("pnl$", "count"), wins=("pnl$", lambda s: (s > 0).sum()),
                                  total=("pnl$", "sum"), avg=("pnl$", "mean"),
                                  avg_move=("move%", lambda s: s.abs().mean())).round(2)
    print(tabulate(by, headers="keys", tablefmt="simple"))


def run(tickers: list[str] | None = None) -> None:
    tickers = tickers or config.TICKERS
    print(f"Earnings straddle backtest")
    print(f"  Universe: {tickers}")
    print(f"  Entry T-1, exit T+1, ATM, weekly expiry, IV: 1.6x pre / 0.75x post realized\n")

    all_trades: list[StraddleTrade] = []
    for t in tickers:
        print(f"  fetching {t}...")
        try:
            df = _fetch_daily(t, days=730)
            ed = get_earnings_dates(t, lookback_years=2)
            trades = backtest_earnings_straddle(t, bars=df, earnings_dates=ed)
            all_trades.extend(trades)
            if trades:
                wins = sum(1 for x in trades if x.pnl > 0)
                pnl = sum(x.pnl for x in trades)
                print(f"    {len(trades)} trades, {wins} wins, total ${pnl:,.2f}")
        except Exception as e:
            print(f"    error: {e}")

    print()
    _summarize(all_trades)


if __name__ == "__main__":
    run()
