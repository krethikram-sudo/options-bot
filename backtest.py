"""Replay signals over historical bars and estimate option P&L via Black-Scholes.

Same-day exit only: enter on signal, exit on profit target / stop / N min before
close (whichever first). Skips entries with no time to exit before close.
"""
from dataclasses import dataclass
from datetime import time

import pandas as pd
from tabulate import tabulate

import config
from black_scholes import atm_strike, bs_price
from data_fetcher import fetch_intraday
from signals import compute_signals
from strategy import Strategy


@dataclass
class Trade:
    ticker: str
    kind: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    entry_price: float
    exit_price: float
    spot_entry: float
    spot_exit: float
    strike: float
    exit_reason: str

    @property
    def pnl_pct(self) -> float:
        return (self.exit_price - self.entry_price) / self.entry_price


def _years_to_close(dte_days: float) -> float:
    return max(dte_days / 365.0, 1 / 365.0 / 6)


def _simulate_trade(
    ticker: str, kind: str, entry_idx: int, day_bars: pd.DataFrame, s: Strategy
) -> Trade | None:
    entry_bar = day_bars.iloc[entry_idx]
    entry_ts = day_bars.index[entry_idx]

    market_close = entry_ts.replace(hour=16, minute=0, second=0)
    exit_cutoff = market_close - pd.Timedelta(minutes=s.exit_minutes_before_close)
    if entry_ts >= exit_cutoff:
        return None

    spot_entry = float(entry_bar["close"])
    strike = atm_strike(spot_entry)
    t_entry = _years_to_close(s.dte_days)
    entry_price = bs_price(spot_entry, strike, t_entry, s.risk_free_rate, s.iv, kind)
    if entry_price <= 0.05:
        return None

    for j in range(entry_idx + 1, len(day_bars)):
        ts = day_bars.index[j]
        spot = float(day_bars.iloc[j]["close"])
        elapsed_days = (ts - entry_ts).total_seconds() / 86400.0
        t_now = max(t_entry - elapsed_days, 1 / 365.0 / 24)
        price_now = bs_price(spot, strike, t_now, s.risk_free_rate, s.iv, kind)
        pnl = (price_now - entry_price) / entry_price

        if pnl >= s.profit_target:
            return Trade(ticker, kind, entry_ts, ts, entry_price, price_now,
                         spot_entry, spot, strike, "profit_target")
        if pnl <= s.stop_loss:
            return Trade(ticker, kind, entry_ts, ts, entry_price, price_now,
                         spot_entry, spot, strike, "stop_loss")
        if ts >= exit_cutoff:
            return Trade(ticker, kind, entry_ts, ts, entry_price, price_now,
                         spot_entry, spot, strike, "time_exit")

    last_ts = day_bars.index[-1]
    spot_last = float(day_bars.iloc[-1]["close"])
    elapsed_days = (last_ts - entry_ts).total_seconds() / 86400.0
    t_last = max(t_entry - elapsed_days, 1 / 365.0 / 24)
    last_price = bs_price(spot_last, strike, t_last, s.risk_free_rate, s.iv, kind)
    return Trade(ticker, kind, entry_ts, last_ts, entry_price, last_price,
                 spot_entry, spot_last, strike, "eod")


def simulate_signals(ticker: str, sig: pd.DataFrame, s: Strategy) -> list[Trade]:
    """Run the per-bar simulation given a signals frame. Used by tuner and CLI."""
    trades: list[Trade] = []
    for _, day_bars in sig.groupby(sig.index.date):
        day_bars = day_bars.between_time(time(9, 30), time(16, 0))
        if len(day_bars) < 30:
            continue
        open_position = False
        for i in range(len(day_bars)):
            if open_position:
                continue
            row = day_bars.iloc[i]
            kind = "call" if bool(row["call_signal"]) else "put" if bool(row["put_signal"]) else None
            if kind is None:
                continue
            t = _simulate_trade(ticker, kind, i, day_bars, s)
            if t:
                trades.append(t)
                open_position = True
    return trades


def backtest_ticker(ticker: str, s: Strategy | None = None) -> list[Trade]:
    s = s or Strategy()
    bars = fetch_intraday(ticker, config.BACKTEST_BAR_INTERVAL, config.BACKTEST_LOOKBACK_DAYS)
    if bars.empty:
        return []
    sig = compute_signals(bars, s)
    return simulate_signals(ticker, sig, s)


def summarize(trades: list[Trade]) -> None:
    if not trades:
        print("No trades generated.")
        return

    df = pd.DataFrame([{
        "ticker": t.ticker, "kind": t.kind, "entry": t.entry_time,
        "exit": t.exit_time, "entry$": round(t.entry_price, 2),
        "exit$": round(t.exit_price, 2), "pnl%": round(t.pnl_pct * 100, 1),
        "reason": t.exit_reason,
    } for t in trades])

    wins = (df["pnl%"] > 0).sum()
    print(tabulate(df.tail(20), headers="keys", tablefmt="simple", showindex=False))
    print(f"\nTrades: {len(df)}  Wins: {wins}  Win rate: {wins/len(df)*100:.1f}%")
    print(f"Avg P&L: {df['pnl%'].mean():.2f}%   Median: {df['pnl%'].median():.2f}%")
    print(f"Total P&L (sum %): {df['pnl%'].sum():.2f}%")
    print("\nBy ticker:")
    by_ticker = df.groupby("ticker").agg(
        n=("pnl%", "count"), win_rate=("pnl%", lambda s: (s > 0).mean() * 100),
        avg_pnl=("pnl%", "mean"),
    ).round(2)
    print(tabulate(by_ticker, headers="keys", tablefmt="simple"))


def run() -> None:
    all_trades: list[Trade] = []
    s = Strategy()
    for ticker in config.TICKERS:
        print(f"Backtesting {ticker}...")
        try:
            all_trades.extend(backtest_ticker(ticker, s))
        except Exception as e:
            print(f"  {ticker} failed: {e}")
    summarize(all_trades)


if __name__ == "__main__":
    run()
