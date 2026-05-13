"""Backtest framework — common utilities used by every strategy in this directory.

Designed for daily-bar, long-only or long-short equity strategies. Position
sizing, rebalancing, and metric calculation live here so each strategy file
focuses on its signal logic.

Outputs a `BacktestResult` with:
  - equity curve (pd.Series of portfolio value over time)
  - trades list
  - per-day weights
  - metrics dict (CAGR, vol, Sharpe, MaxDD, hit rate, etc.)
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from datetime import date
from typing import Callable

import numpy as np
import pandas as pd


@dataclass
class BacktestResult:
    name: str
    equity: pd.Series              # portfolio value over time (starts at initial_capital)
    weights: pd.DataFrame          # date × ticker, target weights at each rebalance
    trades: list[dict] = field(default_factory=list)
    metrics: dict = field(default_factory=dict)


def metrics(equity: pd.Series, rf: float = 0.04, trading_days: int = 252) -> dict:
    """Standard performance metrics from an equity curve."""
    if len(equity) < 2:
        return {}
    rets = equity.pct_change().dropna()
    if len(rets) == 0:
        return {}

    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
    vol = rets.std() * math.sqrt(trading_days)
    sharpe = (cagr - rf) / vol if vol > 0 else 0

    running_max = equity.cummax()
    dd = (equity - running_max) / running_max
    max_dd = float(dd.min())

    # Sortino: downside vol only
    neg = rets[rets < 0]
    downside_vol = neg.std() * math.sqrt(trading_days) if len(neg) > 0 else 0
    sortino = (cagr - rf) / downside_vol if downside_vol > 0 else 0

    # Calmar
    calmar = cagr / abs(max_dd) if max_dd < 0 else 0

    # Hit rate, win/loss
    hit_rate = (rets > 0).mean()

    return {
        "cagr": cagr,
        "total_return": equity.iloc[-1] / equity.iloc[0] - 1,
        "vol": vol,
        "sharpe": sharpe,
        "sortino": sortino,
        "calmar": calmar,
        "max_dd": max_dd,
        "hit_rate_daily": hit_rate,
        "n_days": len(equity),
        "years": years,
    }


def simulate_long_portfolio(
    weights: pd.DataFrame,
    closes: pd.DataFrame,
    initial_capital: float = 100_000.0,
    cost_bps: float = 5.0,            # one-way trading cost in basis points
) -> tuple[pd.Series, list[dict]]:
    """Simulate a long-only portfolio given target weights per date.

    `weights` : DataFrame indexed by date, columns = subset of closes columns.
                Must sum to <=1 across columns each row (cash = 1 - sum).
    `closes`  : DataFrame with same date index, all needed tickers as columns.

    Returns (equity_series, trade_log).
    """
    # align
    common_dates = weights.index.intersection(closes.index)
    if len(common_dates) == 0:
        return pd.Series(dtype=float), []
    weights = weights.loc[common_dates].fillna(0.0)
    px = closes.loc[common_dates]

    cash = initial_capital
    shares = pd.Series(0.0, index=weights.columns)
    equity_history: list[float] = []
    trade_log: list[dict] = []

    prev_target = pd.Series(0.0, index=weights.columns)

    for d, target_w in weights.iterrows():
        prices_today = px.loc[d, weights.columns].ffill()
        # current portfolio value
        port_value = float(cash + (shares * prices_today.fillna(0)).sum())

        # rebalance: only act if target weight has changed materially OR we're at first day
        # Compute target dollar per ticker
        target_dollars = port_value * target_w
        cur_dollars = shares * prices_today.fillna(0)
        delta = (target_dollars - cur_dollars).fillna(0)

        # Skip rebalances smaller than 0.5% portfolio
        material = delta.abs() > port_value * 0.005

        if material.any():
            # Sell first to free capital, then buy
            for t in delta.index[delta < 0]:
                if not material[t] or pd.isna(prices_today.get(t)):
                    continue
                px_t = float(prices_today[t])
                if px_t <= 0:
                    continue
                shares_to_sell = min(shares[t], abs(delta[t]) / px_t)
                proceeds = shares_to_sell * px_t * (1 - cost_bps / 10_000)
                cash += proceeds
                shares[t] -= shares_to_sell
                trade_log.append({
                    "date": d, "ticker": t, "side": "sell",
                    "shares": shares_to_sell, "price": px_t, "value": proceeds,
                })

            for t in delta.index[delta > 0]:
                if not material[t] or pd.isna(prices_today.get(t)):
                    continue
                px_t = float(prices_today[t])
                if px_t <= 0:
                    continue
                want_dollars = float(delta[t])
                # apply cost upfront
                effective_dollars = want_dollars / (1 + cost_bps / 10_000)
                buy_dollars = min(effective_dollars, max(cash, 0))
                shares_to_buy = buy_dollars / px_t
                cash -= buy_dollars * (1 + cost_bps / 10_000)
                shares[t] += shares_to_buy
                trade_log.append({
                    "date": d, "ticker": t, "side": "buy",
                    "shares": shares_to_buy, "price": px_t, "value": buy_dollars,
                })

        # Recompute end-of-day portfolio value at close
        port_value = float(cash + (shares * prices_today.fillna(0)).sum())
        equity_history.append(port_value)

    equity = pd.Series(equity_history, index=common_dates, name="equity")
    return equity, trade_log


def make_rebalance_dates(dates: pd.DatetimeIndex, freq: str) -> pd.DatetimeIndex:
    """Pick rebalance dates from a date index by frequency."""
    if freq == "daily":
        return dates
    if freq == "weekly":
        return pd.DatetimeIndex([d for i, d in enumerate(dates) if i == 0 or d.weekday() < dates[i-1].weekday()])
    if freq == "monthly":
        return pd.DatetimeIndex([d for i, d in enumerate(dates) if i == 0 or d.month != dates[i-1].month])
    if freq == "quarterly":
        return pd.DatetimeIndex([d for i, d in enumerate(dates) if i == 0 or (d.month - 1) // 3 != (dates[i-1].month - 1) // 3])
    raise ValueError(f"unknown freq: {freq}")


def step_weights(weights_at_rebalance: dict[pd.Timestamp, pd.Series], all_dates: pd.DatetimeIndex,
                 universe: list[str]) -> pd.DataFrame:
    """Forward-fill rebalance-date weights to a full daily weights DataFrame."""
    if not weights_at_rebalance:
        return pd.DataFrame(0.0, index=all_dates, columns=universe)
    df = pd.DataFrame(0.0, index=all_dates, columns=universe)
    rebalance_dates = sorted(weights_at_rebalance.keys())
    for i, d in enumerate(rebalance_dates):
        next_d = rebalance_dates[i + 1] if i + 1 < len(rebalance_dates) else df.index[-1] + pd.Timedelta(days=1)
        mask = (df.index >= d) & (df.index < next_d)
        for t, w in weights_at_rebalance[d].items():
            if t in df.columns:
                df.loc[mask, t] = w
    return df


def equal_weight(tickers: list[str]) -> pd.Series:
    return pd.Series(1.0 / len(tickers), index=tickers)


def realized_vol(returns: pd.Series, window: int = 30, annualize: bool = True) -> pd.Series:
    v = returns.rolling(window).std()
    if annualize:
        v = v * math.sqrt(252)
    return v


def momentum_score(closes: pd.DataFrame, lookback: int = 252, skip: int = 21) -> pd.DataFrame:
    """Jegadeesh-Titman style 12-1 momentum: trailing N-day return excluding most recent skip days."""
    far = closes.shift(skip)
    long_ago = closes.shift(skip + lookback)
    return (far - long_ago) / long_ago


def zscore_cross_section(df: pd.DataFrame) -> pd.DataFrame:
    """Z-score each row (across tickers)."""
    return df.sub(df.mean(axis=1), axis=0).div(df.std(axis=1), axis=0)
