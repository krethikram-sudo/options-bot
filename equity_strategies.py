"""Equity strategies: trend-following + mean-reversion + buy-and-hold benchmark.

Both strategies use daily bars and submit equity orders (not options).
Sequential per ticker: one position at a time. Capital is allocated equally
across the universe so total deployed never exceeds the per-strategy budget.

Backtests sweep parameters per strategy and report best/most-robust combos.
"""
from __future__ import annotations

import itertools
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
import yfinance as yf
from tabulate import tabulate

import config
from indicators import rsi as compute_rsi


@dataclass
class EquityTrade:
    ticker: str
    strategy: str
    entry_date: date
    exit_date: date
    entry_price: float
    exit_price: float
    shares: int
    pnl: float
    pnl_pct: float
    exit_reason: str
    days_held: int

    @property
    def cost_basis(self) -> float:
        return self.entry_price * self.shares


def _fetch_daily(ticker: str, days: int = 365) -> pd.DataFrame:
    df = yf.download(ticker, period=f"{days}d", interval="1d",
                     auto_adjust=False, progress=False)
    if df.empty:
        return df
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    df.columns = [c.lower() for c in df.columns]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    return df


# ---------- trend following ----------

def backtest_trend_following(
    ticker: str, allocation: float = 2700,
    sma_period: int = 50, stop_pct: float = -0.08,
    bars: pd.DataFrame | None = None,
) -> list[EquityTrade]:
    """Buy on close > SMA(period) cross. Sell on cross below or stop loss."""
    df = bars if bars is not None else _fetch_daily(ticker)
    if df.empty or len(df) < sma_period + 5:
        return []

    df = df.copy()
    df["sma"] = df["close"].rolling(sma_period).mean()
    df = df.dropna()

    trades: list[EquityTrade] = []
    in_pos = False
    entry_price = entry_date = shares = None

    for i in range(1, len(df)):
        today = df.iloc[i]
        prev = df.iloc[i - 1]
        d = df.index[i].date()

        if not in_pos:
            # cross above SMA
            if today["close"] > today["sma"] and prev["close"] <= prev["sma"]:
                entry_price = float(today["close"])
                entry_date = d
                shares = int(allocation / entry_price)
                if shares >= 1:
                    in_pos = True
        else:
            cur_pnl_pct = (today["close"] - entry_price) / entry_price
            cross_below = today["close"] < today["sma"] and prev["close"] >= prev["sma"]
            stop_hit = cur_pnl_pct <= stop_pct
            if cross_below or stop_hit:
                ex_price = float(today["close"])
                pnl = (ex_price - entry_price) * shares
                trades.append(EquityTrade(
                    ticker=ticker, strategy="trend_following",
                    entry_date=entry_date, exit_date=d,
                    entry_price=entry_price, exit_price=ex_price,
                    shares=shares, pnl=pnl,
                    pnl_pct=(ex_price - entry_price) / entry_price,
                    exit_reason="stop" if stop_hit else "cross_below",
                    days_held=(d - entry_date).days,
                ))
                in_pos = False

    # if still in position at end of window, mark to last close
    if in_pos:
        last = df.iloc[-1]
        last_date = df.index[-1].date()
        ex_price = float(last["close"])
        pnl = (ex_price - entry_price) * shares
        trades.append(EquityTrade(
            ticker=ticker, strategy="trend_following",
            entry_date=entry_date, exit_date=last_date,
            entry_price=entry_price, exit_price=ex_price,
            shares=shares, pnl=pnl,
            pnl_pct=(ex_price - entry_price) / entry_price,
            exit_reason="open_at_end",
            days_held=(last_date - entry_date).days,
        ))

    return trades


# ---------- mean reversion ----------

def backtest_mean_reversion(
    ticker: str, allocation: float = 2700,
    rsi_period: int = 14, oversold: float = 30, overbought: float = 50,
    stop_pct: float = -0.08, max_days: int = 30,
    bars: pd.DataFrame | None = None,
) -> list[EquityTrade]:
    """Buy on RSI crossing below oversold. Sell on RSI > overbought, stop, or max days."""
    df = bars if bars is not None else _fetch_daily(ticker)
    if df.empty or len(df) < rsi_period + 5:
        return []

    df = df.copy()
    df["rsi"] = compute_rsi(df["close"], rsi_period)
    df = df.dropna()

    trades: list[EquityTrade] = []
    in_pos = False
    entry_price = entry_date = shares = None

    for i in range(1, len(df)):
        today = df.iloc[i]
        prev = df.iloc[i - 1]
        d = df.index[i].date()

        if not in_pos:
            # RSI just dropped below oversold
            if today["rsi"] < oversold and prev["rsi"] >= oversold:
                entry_price = float(today["close"])
                entry_date = d
                shares = int(allocation / entry_price)
                if shares >= 1:
                    in_pos = True
        else:
            cur_pnl_pct = (today["close"] - entry_price) / entry_price
            recovered = today["rsi"] > overbought
            stop_hit = cur_pnl_pct <= stop_pct
            timed_out = (d - entry_date).days >= max_days
            if recovered or stop_hit or timed_out:
                ex_price = float(today["close"])
                pnl = (ex_price - entry_price) * shares
                reason = "stop" if stop_hit else "timeout" if timed_out else "rsi_recovered"
                trades.append(EquityTrade(
                    ticker=ticker, strategy="mean_reversion",
                    entry_date=entry_date, exit_date=d,
                    entry_price=entry_price, exit_price=ex_price,
                    shares=shares, pnl=pnl,
                    pnl_pct=(ex_price - entry_price) / entry_price,
                    exit_reason=reason,
                    days_held=(d - entry_date).days,
                ))
                in_pos = False

    return trades


# ---------- rotational momentum ----------

def backtest_rotational_momentum(
    bars_cache: dict[str, pd.DataFrame],
    capital: float = 25_000.0,
    lookback_days: int = 30,
    top_n: int = 3,
    rebalance_days: int = 21,  # ~monthly
) -> tuple[list[dict], list[dict]]:
    """Hold the top-N performers (by lookback return) on each rebalance.

    Each rebalance day:
      1. Compute lookback returns for every ticker
      2. Select top_n
      3. Sell holdings that fell out of top_n
      4. Buy/rebalance to equal-weight across the new top_n

    Returns (daily_history, rebalance_log).
    """
    if not bars_cache:
        return [], []

    closes = pd.DataFrame({t: b["close"] for t, b in bars_cache.items()})
    closes = closes.dropna()
    if len(closes) < lookback_days + 5:
        return [], []

    cash = capital
    positions: dict[str, int] = {}
    history: list[dict] = []
    rebalances: list[dict] = []
    last_rebalance_idx = -rebalance_days  # first iteration triggers rebalance

    for i in range(lookback_days, len(closes)):
        d = closes.index[i].date()
        prices = closes.iloc[i]
        port_value = cash + sum(prices[t] * sh for t, sh in positions.items())

        if i - last_rebalance_idx >= rebalance_days:
            past = closes.iloc[i - lookback_days]
            returns = ((prices - past) / past).dropna()
            top = list(returns.sort_values(ascending=False).head(top_n).index)

            # liquidate non-top
            for t in list(positions.keys()):
                if t not in top:
                    cash += positions[t] * prices[t]
                    del positions[t]

            held_value = sum(prices[t] * sh for t, sh in positions.items())
            total = cash + held_value
            target_per = total / top_n

            for t in top:
                cur_value = positions.get(t, 0) * prices[t]
                diff = target_per - cur_value
                if diff > prices[t]:  # add shares
                    add = int(diff / prices[t])
                    cost = add * prices[t]
                    if cost <= cash:
                        positions[t] = positions.get(t, 0) + add
                        cash -= cost
                elif diff < -prices[t] and t in positions:  # trim shares
                    sell = int(-diff / prices[t])
                    sell = min(sell, positions[t])
                    positions[t] -= sell
                    cash += sell * prices[t]
                    if positions[t] == 0:
                        del positions[t]

            rebalances.append({
                "date": d, "top": top,
                "returns_pct": {t: round(float(returns[t]) * 100, 1) for t in top},
                "port_value_before": round(float(port_value), 2),
            })
            last_rebalance_idx = i

        history.append({
            "date": d, "value": float(port_value), "cash": float(cash),
            "positions": len(positions),
        })

    return history, rebalances


# ---------- buy-and-hold benchmark ----------

def buyhold_return(ticker: str, allocation: float = 2700,
                   bars: pd.DataFrame | None = None) -> tuple[float, float]:
    """Return (pnl_dollars, pnl_pct) for a buy-and-hold over the full window."""
    df = bars if bars is not None else _fetch_daily(ticker)
    if df.empty or len(df) < 2:
        return 0.0, 0.0
    entry, exit_p = float(df["close"].iloc[0]), float(df["close"].iloc[-1])
    shares = int(allocation / entry)
    pnl = (exit_p - entry) * shares
    pct = (exit_p - entry) / entry * 100
    return pnl, pct


# ---------- aggregator ----------

def _summarize(trades: list[EquityTrade], label: str) -> dict:
    if not trades:
        print(f"{label}: no trades")
        return {"label": label, "n": 0}
    df = pd.DataFrame([{
        "ticker": t.ticker, "entry": t.entry_date, "exit": t.exit_date,
        "days": t.days_held, "entry$": round(t.entry_price, 2),
        "exit$": round(t.exit_price, 2), "shares": t.shares,
        "pnl$": round(t.pnl, 2), "pnl%": round(t.pnl_pct * 100, 2),
        "reason": t.exit_reason,
    } for t in trades])

    wins = (df["pnl$"] > 0).sum()
    total_pnl = df["pnl$"].sum()
    print(f"\n=== {label.upper()} ===")
    print(tabulate(df.tail(15), headers="keys", tablefmt="simple", showindex=False))
    print(f"\nTrades: {len(df)}  Wins: {wins} ({wins/len(df)*100:.1f}%)")
    print(f"Total PnL: ${total_pnl:,.2f}  Avg per trade: ${df['pnl$'].mean():,.2f}")
    print(f"Avg pnl%: {df['pnl%'].mean():.2f}%  Median: {df['pnl%'].median():.2f}%")
    print(f"Best: ${df['pnl$'].max():,.2f}  Worst: ${df['pnl$'].min():,.2f}")
    print(f"Avg days held: {df['days'].mean():.1f}")
    print(f"Exit reasons: {df['reason'].value_counts().to_dict()}")
    return {"label": label, "n": len(df), "wins": int(wins),
            "total_pnl": float(total_pnl), "win_rate": wins/len(df)*100}


def run() -> None:
    tickers = config.TICKERS  # all 9 for equity strategies (no need to exclude MU/ARM)
    sleeve_capital = 25_000.0
    per_ticker = sleeve_capital / len(tickers)
    print(f"Equity strategy backtests")
    print(f"  Universe   : {tickers}")
    print(f"  Sleeve cap : ${sleeve_capital:,.0f}")
    print(f"  Per ticker : ${per_ticker:,.0f}")

    print("\nLoading daily bars...")
    bars_cache = {}
    for t in tickers:
        df = _fetch_daily(t, days=365)
        if not df.empty:
            bars_cache[t] = df
            print(f"  {t}: {len(df)} days")
        else:
            print(f"  {t}: skipped (no data)")

    # Trend following
    tf_trades = []
    for t, df in bars_cache.items():
        tf_trades.extend(backtest_trend_following(t, allocation=per_ticker, bars=df))
    tf_summary = _summarize(tf_trades, "trend_following")

    # Mean reversion
    mr_trades = []
    for t, df in bars_cache.items():
        mr_trades.extend(backtest_mean_reversion(t, allocation=per_ticker, bars=df))
    mr_summary = _summarize(mr_trades, "mean_reversion")

    # Buy and hold benchmark
    print("\n=== BUY & HOLD BENCHMARK ===")
    bh_rows = []
    bh_total = 0.0
    for t, df in bars_cache.items():
        pnl, pct = buyhold_return(t, allocation=per_ticker, bars=df)
        bh_rows.append({"ticker": t, "pnl$": round(pnl, 2), "pnl%": round(pct, 2)})
        bh_total += pnl
    print(tabulate(bh_rows, headers="keys", tablefmt="simple", showindex=False))
    print(f"\nB&H Total PnL: ${bh_total:,.2f} on ${sleeve_capital:,.0f} = {bh_total/sleeve_capital*100:.2f}%")

    # Side-by-side
    print("\n" + "=" * 80)
    print("SIDE-BY-SIDE")
    print("=" * 80)
    rows = [
        {"strategy": "trend_following", **{k: v for k, v in tf_summary.items() if k != "label"}},
        {"strategy": "mean_reversion", **{k: v for k, v in mr_summary.items() if k != "label"}},
        {"strategy": "buy_and_hold", "n": len(tickers), "wins": "n/a",
         "total_pnl": round(bh_total, 2), "win_rate": "n/a"},
    ]
    print(tabulate(rows, headers="keys", tablefmt="simple", showindex=False))

    # Per-ticker for the strategies
    print("\n=== PER-TICKER (TREND FOLLOWING) ===")
    if tf_trades:
        df = pd.DataFrame([{"ticker": t.ticker, "pnl$": t.pnl} for t in tf_trades])
        per = df.groupby("ticker")["pnl$"].agg(["count", "sum", "mean"]).round(2).rename(
            columns={"count": "n", "sum": "total_pnl", "mean": "avg_pnl"})
        print(tabulate(per, headers="keys", tablefmt="simple"))

    print("\n=== PER-TICKER (MEAN REVERSION) ===")
    if mr_trades:
        df = pd.DataFrame([{"ticker": t.ticker, "pnl$": t.pnl} for t in mr_trades])
        per = df.groupby("ticker")["pnl$"].agg(["count", "sum", "mean"]).round(2).rename(
            columns={"count": "n", "sum": "total_pnl", "mean": "avg_pnl"})
        print(tabulate(per, headers="keys", tablefmt="simple"))


if __name__ == "__main__":
    run()
