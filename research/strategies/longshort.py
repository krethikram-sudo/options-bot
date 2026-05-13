"""Long-short cross-sectional momentum.

Long top-N by 12-1 momentum, short bottom-N, dollar-neutral. Hypothesis: this
should reduce drawdowns versus the long-only top-3 strategy because the short
leg should hedge market beta.

Tests several variations:
  - lookback ∈ {60, 90, 126, 252}
  - top_n / bottom_n ∈ {2, 3, 4, 5}
  - rebalance ∈ {weekly, monthly}
  - universe ∈ {ai9, ai_full_chain}
  - cost = 5 bps per leg (10 bps round-trip per rebalance per ticker)

Compared against long-only equivalents.
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd
from tabulate import tabulate

from research.data_lib import load_closes
from research.strategies.engine import resolve_universe
from research.strategies.framework import (make_rebalance_dates, metrics,
                                            momentum_score)


def long_short_xs_momentum(
    universe_spec: str = "ai9",
    lookback: int = 252,
    skip: int = 21,
    top_n: int = 3,
    rebalance: str = "monthly",
    cost_bps_per_side: float = 5.0,
    initial_capital: float = 100_000,
) -> tuple[pd.Series, dict, dict]:
    """Compute LS strategy returns directly without simulator.

    Each rebalance:
      Long top_n at +1/N notional each (sum = +1 = full long exposure)
      Short bottom_n at -1/N notional each (sum = -1 = full short exposure)
      Net: dollar-neutral

    Daily P&L = sum(long_weight * ticker_return) - sum(short_weight * ticker_return)
    Costs applied at rebalance based on weight changes.

    Returns (equity_series, metrics, sleeve_breakdown).
    """
    closes = load_closes()
    universe = resolve_universe(universe_spec)
    px = closes[universe].dropna()
    if px.empty:
        return pd.Series(dtype=float), {}, {}

    rets = px.pct_change()
    mom = momentum_score(px, lookback=lookback, skip=skip)
    rdates = make_rebalance_dates(mom.dropna(how="all").index, rebalance)
    rdates_set = set(rdates)

    # build per-day weights (forward-filled from rebalance days)
    long_w = pd.DataFrame(0.0, index=px.index, columns=universe)
    short_w = pd.DataFrame(0.0, index=px.index, columns=universe)

    cur_long = pd.Series(0.0, index=universe)
    cur_short = pd.Series(0.0, index=universe)
    rebalance_log = []

    for d in px.index:
        if d in rdates_set:
            scores = mom.loc[d].dropna()
            if len(scores) >= 2 * top_n:
                top = scores.nlargest(top_n).index.tolist()
                bot = scores.nsmallest(top_n).index.tolist()
                new_long = pd.Series(0.0, index=universe)
                new_short = pd.Series(0.0, index=universe)
                new_long.loc[top] = 1.0 / top_n
                new_short.loc[bot] = 1.0 / top_n
                cur_long = new_long
                cur_short = new_short
                rebalance_log.append({"date": d, "long": top, "short": bot})
        long_w.loc[d] = cur_long
        short_w.loc[d] = cur_short

    # daily P&L: weights from prior day applied to today's returns
    long_ret = (long_w.shift(1) * rets).sum(axis=1)
    short_ret = (short_w.shift(1) * rets).sum(axis=1)
    ls_ret = long_ret - short_ret

    # transaction costs: at each rebalance, sum of |weight change| * cost_bps
    daily_turnover = pd.Series(0.0, index=px.index)
    for i, d in enumerate(px.index):
        if d in rdates_set and i > 0:
            prev = px.index[i - 1]
            change_long = (long_w.loc[d] - long_w.loc[prev]).abs().sum()
            change_short = (short_w.loc[d] - short_w.loc[prev]).abs().sum()
            daily_turnover.loc[d] = change_long + change_short

    cost_drag = daily_turnover * (cost_bps_per_side / 10_000)
    ls_ret_net = ls_ret - cost_drag
    ls_ret_net = ls_ret_net.fillna(0)

    equity = (1 + ls_ret_net).cumprod() * initial_capital
    m = metrics(equity)

    # also report sleeve-level (long-only and short-only) for context
    long_equity = (1 + (long_ret - cost_drag * 0.5).fillna(0)).cumprod() * initial_capital
    short_equity = (1 + (-short_ret - cost_drag * 0.5).fillna(0)).cumprod() * initial_capital
    sleeves = {
        "long_only": metrics(long_equity),
        "short_only": metrics(short_equity),  # this is "going short the bottom-N", returns flip
    }

    return equity, m, sleeves


def run_grid() -> pd.DataFrame:
    rows = []
    configs = []
    for universe in ["ai9", "ai_full_chain"]:
        for lookback in [60, 90, 126, 252]:
            for top_n in [2, 3, 4]:
                for rebalance in ["monthly"]:
                    configs.append((universe, lookback, top_n, rebalance))

    for universe, lookback, top_n, rebalance in configs:
        try:
            eq, m, sleeves = long_short_xs_momentum(
                universe_spec=universe, lookback=lookback,
                top_n=top_n, rebalance=rebalance,
            )
        except Exception as ex:
            print(f"  ERROR {universe} lb{lookback} n{top_n}: {ex}")
            continue
        if not m:
            continue
        rows.append({
            "universe": universe,
            "lookback": lookback,
            "top_n": top_n,
            "rebalance": rebalance,
            "cagr_pct": round(m.get("cagr", 0) * 100, 2),
            "sharpe": round(m.get("sharpe", 0), 2),
            "sortino": round(m.get("sortino", 0), 2),
            "vol_pct": round(m.get("vol", 0) * 100, 2),
            "max_dd_pct": round(m.get("max_dd", 0) * 100, 2),
            "calmar": round(m.get("calmar", 0), 2),
            "long_cagr_pct": round(sleeves["long_only"].get("cagr", 0) * 100, 1),
            "short_cagr_pct": round(sleeves["short_only"].get("cagr", 0) * 100, 1),
        })
    return pd.DataFrame(rows)


if __name__ == "__main__":
    print("Running long-short momentum grid...")
    df = run_grid()
    if df.empty:
        print("no results")
        raise SystemExit
    df_sorted = df.sort_values("sharpe", ascending=False)
    print()
    print("=== LONG-SHORT XS-MOMENTUM RESULTS ===")
    print(tabulate(df_sorted, headers="keys", tablefmt="simple", showindex=False))

    from pathlib import Path
    out = Path(__file__).resolve().parent / "longshort_results.csv"
    df_sorted.to_csv(out, index=False)
    print(f"\nSaved: {out}")

    print()
    best = df_sorted.iloc[0]
    print(f"Best LS combo: universe={best['universe']}, lb={best['lookback']}, "
          f"top_n={best['top_n']}, rebalance={best['rebalance']}")
    print(f"  CAGR={best['cagr_pct']}%  Sharpe={best['sharpe']}  MaxDD={best['max_dd_pct']}%")
    print()
    print("Long-only vs LS comparison:")
    print(f"  long sleeve avg CAGR : {df['long_cagr_pct'].mean():.1f}%")
    print(f"  short sleeve avg CAGR: {df['short_cagr_pct'].mean():.1f}%")
    print(f"  combined LS avg DD   : {df['max_dd_pct'].mean():.1f}%")
