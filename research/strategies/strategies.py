"""Candidate strategies derived from the research synthesis.

Each function returns a `BacktestResult`. Run via `run_all.py`.

Strategies map to the research findings as follows:
  1. xs_momentum_ai9        — Jegadeesh-Titman within the AI-9 (factor research)
  2. xs_momentum_universe   — same idea but across 50+ AI value chain names
  3. quality_trend_composite — multi-factor (AQR Quality Minus Junk + Momentum)
  4. pairs_trade_basket     — cointegration pairs (D.E. Shaw / Renaissance lineage)
  5. vol_targeted_trend     — TS momentum with vol target (AQR Helix-style)
  6. power_infra_basket     — equal-weight VRT/GEV/CEG/ETN/HUBB (expanded universe)
  7. networking_basket      — equal-weight ANET/LITE/CRDO/COHR/CIEN
  8. wfe_basket             — equal-weight ASML/AMAT/KLAC/LRCX/TER (semi equipment)
  9. regime_gated_universe  — long AI-9 only when VIX < 25 AND NVDA above 50-SMA
 10. risk_parity_overlay    — inverse-vol weights across AI / SPY / TLT / GLD / cash
"""
from __future__ import annotations

import math

import numpy as np
import pandas as pd

from research.data_lib import category, load_closes, load_returns, load_ticker
from research.strategies.framework import (BacktestResult, equal_weight,
                                            make_rebalance_dates, metrics,
                                            momentum_score, realized_vol,
                                            simulate_long_portfolio,
                                            step_weights, zscore_cross_section)


# ---------- benchmarks ----------

def benchmark_buy_hold(ticker: str, name: str | None = None) -> BacktestResult:
    closes = load_closes()
    if ticker not in closes.columns:
        raise ValueError(f"{ticker} not in dataset")
    px = closes[ticker].dropna()
    equity = px / px.iloc[0] * 100_000
    return BacktestResult(name=name or f"buy_hold_{ticker}", equity=equity,
                          weights=pd.DataFrame({ticker: 1.0}, index=equity.index),
                          trades=[], metrics=metrics(equity))


def benchmark_equal_weight(tickers: list[str], name: str) -> BacktestResult:
    closes = load_closes()
    cols = [t for t in tickers if t in closes.columns]
    px = closes[cols].dropna(how="all")
    # Start fresh — first row where all tickers have data
    px = px.dropna()
    if px.empty:
        return BacktestResult(name=name, equity=pd.Series(dtype=float),
                              weights=pd.DataFrame(), metrics={})
    rebalance_dates = make_rebalance_dates(px.index, "monthly")
    weights_at = {d: equal_weight(cols) for d in rebalance_dates}
    weights = step_weights(weights_at, px.index, cols)
    equity, trades = simulate_long_portfolio(weights, closes[cols].loc[px.index])
    return BacktestResult(name=name, equity=equity, weights=weights, trades=trades,
                          metrics=metrics(equity))


def benchmark_60_40() -> BacktestResult:
    closes = load_closes()
    cols = ["SPY", "TLT"]
    if not all(c in closes.columns for c in cols):
        return BacktestResult(name="60_40_spy_tlt", equity=pd.Series(dtype=float),
                              weights=pd.DataFrame(), metrics={})
    px = closes[cols].dropna()
    rebalance_dates = make_rebalance_dates(px.index, "quarterly")
    weights_at = {d: pd.Series({"SPY": 0.6, "TLT": 0.4}) for d in rebalance_dates}
    weights = step_weights(weights_at, px.index, cols)
    equity, trades = simulate_long_portfolio(weights, closes[cols].loc[px.index])
    return BacktestResult(name="60_40_spy_tlt", equity=equity, weights=weights,
                          trades=trades, metrics=metrics(equity))


# ---------- 1: cross-sectional momentum within AI-9 ----------

def xs_momentum_ai9(top_n: int = 3, lookback: int = 252, skip: int = 21,
                    rebalance: str = "monthly", cost_bps: float = 5.0) -> BacktestResult:
    closes = load_closes()
    universe = [t for t in category("core_ai_infra") if t in closes.columns]
    px = closes[universe].dropna()
    if px.empty:
        return BacktestResult(name="xs_momentum_ai9", equity=pd.Series(dtype=float),
                              weights=pd.DataFrame(), metrics={})

    mom = momentum_score(px, lookback=lookback, skip=skip)
    rebalance_dates = make_rebalance_dates(mom.dropna().index, rebalance)
    weights_at = {}
    for d in rebalance_dates:
        scores = mom.loc[d].dropna()
        if len(scores) < top_n:
            continue
        top = scores.nlargest(top_n).index.tolist()
        w = pd.Series(0.0, index=universe)
        w[top] = 1.0 / top_n
        weights_at[d] = w
    weights = step_weights(weights_at, px.index, universe)
    equity, trades = simulate_long_portfolio(weights, closes[universe].loc[px.index],
                                              cost_bps=cost_bps)
    return BacktestResult(name=f"xs_momentum_ai9_top{top_n}_{rebalance}",
                          equity=equity, weights=weights, trades=trades,
                          metrics=metrics(equity))


# ---------- 2: cross-sectional momentum across full AI value chain ----------

def xs_momentum_universe(top_n: int = 5, lookback: int = 126, skip: int = 21,
                         rebalance: str = "monthly", cost_bps: float = 5.0) -> BacktestResult:
    closes = load_closes()
    universe = sorted(set(
        category("core_ai_infra") + category("semi_equipment") + category("foundries")
        + category("other_silicon") + category("networking_optical") + category("storage")
        + category("servers_power") + category("hyperscalers") + category("ai_software")
        + category("cybersecurity") + category("vertical_ai") + category("power_utilities")
        + category("data_center_reits")
    ))
    universe = [t for t in universe if t in closes.columns]
    px = closes[universe]

    mom = momentum_score(px, lookback=lookback, skip=skip)
    rebalance_dates = make_rebalance_dates(mom.dropna(how="all").index, rebalance)
    weights_at = {}
    for d in rebalance_dates:
        scores = mom.loc[d].dropna()
        if len(scores) < top_n:
            continue
        top = scores.nlargest(top_n).index.tolist()
        w = pd.Series(0.0, index=universe)
        w[top] = 1.0 / top_n
        weights_at[d] = w
    weights = step_weights(weights_at, px.index, universe)
    equity, trades = simulate_long_portfolio(weights, closes[universe].loc[px.index],
                                              cost_bps=cost_bps)
    return BacktestResult(name=f"xs_momentum_universe_top{top_n}",
                          equity=equity, weights=weights, trades=trades,
                          metrics=metrics(equity))


# ---------- 3: quality + trend composite ----------

def quality_trend_composite(top_n: int = 4, rebalance: str = "monthly",
                             cost_bps: float = 5.0) -> BacktestResult:
    """
    Quality proxy (no fundamentals available cleanly): trailing 60-day Sharpe ratio.
      "Quality" = high return / low vol over recent window.
    Trend proxy: 6-month total return.
    Composite = z-score average. Pick top-N monthly.
    """
    closes = load_closes()
    universe = [t for t in category("core_ai_infra") if t in closes.columns]
    px = closes[universe].dropna()
    rets = px.pct_change()

    rolling_mean = rets.rolling(60).mean() * 252
    rolling_vol = rets.rolling(60).std() * math.sqrt(252)
    quality = (rolling_mean - 0.04) / rolling_vol     # rolling Sharpe

    trend = px.pct_change(126)  # 6-month return

    quality_z = zscore_cross_section(quality)
    trend_z = zscore_cross_section(trend)
    composite = (quality_z + trend_z) / 2

    rebalance_dates = make_rebalance_dates(composite.dropna(how="all").index, rebalance)
    weights_at = {}
    for d in rebalance_dates:
        scores = composite.loc[d].dropna()
        if len(scores) < top_n:
            continue
        top = scores.nlargest(top_n).index.tolist()
        w = pd.Series(0.0, index=universe)
        w[top] = 1.0 / top_n
        weights_at[d] = w
    weights = step_weights(weights_at, px.index, universe)
    equity, trades = simulate_long_portfolio(weights, closes[universe].loc[px.index],
                                              cost_bps=cost_bps)
    return BacktestResult(name=f"quality_trend_composite_top{top_n}",
                          equity=equity, weights=weights, trades=trades,
                          metrics=metrics(equity))


# ---------- 4: pairs trade on cointegrated AI pairs ----------

def pairs_trade_basket(z_entry: float = 2.0, z_exit: float = 0.5,
                       z_stop: float = 4.0, lookback: int = 60,
                       cost_bps: float = 5.0) -> BacktestResult:
    """
    Cash-neutral pair: when z(spread) > z_entry, short rich / long cheap with equal capital.
    This implementation tracks $ P&L only on the spread, treating each pair as
    a contribution to total portfolio value. Sized at $10k per pair when active.
    """
    closes = load_closes()
    pairs = [
        ("NVDA", "AMD"),
        ("AVGO", "MRVL"),
        ("MU", "SNDK"),
        ("AMAT", "LRCX"),
        ("KLAC", "ASML"),
        ("DLR", "EQIX"),
    ]
    pairs = [(a, b) for (a, b) in pairs if a in closes.columns and b in closes.columns]

    # daily P&L from each pair as a fraction of capital allocated to it
    pair_capital = 10_000
    portfolio_value = 100_000  # initial cash
    cash = portfolio_value
    equity_history: list[float] = []
    trades: list[dict] = []

    pair_state: dict[tuple[str, str], dict] = {p: {"position": 0, "entry_a": 0.0, "entry_b": 0.0, "entry_z": 0.0}
                                                  for p in pairs}

    common_dates = closes[[t for p in pairs for t in p]].dropna().index

    for d in common_dates:
        spread_pnl_today = 0.0
        for (a, b) in pairs:
            sub = closes[[a, b]].loc[:d].tail(lookback + 1)
            if len(sub) < lookback:
                continue
            log_spread = np.log(sub[a]) - np.log(sub[b])
            mu = log_spread.tail(lookback).mean()
            sigma = log_spread.tail(lookback).std()
            if sigma == 0 or pd.isna(sigma):
                continue
            z = (log_spread.iloc[-1] - mu) / sigma

            state = pair_state[(a, b)]
            if state["position"] == 0:
                # entry rules
                if z > z_entry:
                    # short A, long B (a is rich vs b)
                    state["position"] = -1
                    state["entry_a"] = float(closes.loc[d, a])
                    state["entry_b"] = float(closes.loc[d, b])
                    state["entry_z"] = z
                    trades.append({"date": d, "pair": (a, b), "action": "open_short_a"})
                elif z < -z_entry:
                    state["position"] = 1
                    state["entry_a"] = float(closes.loc[d, a])
                    state["entry_b"] = float(closes.loc[d, b])
                    state["entry_z"] = z
                    trades.append({"date": d, "pair": (a, b), "action": "open_long_a"})
            else:
                # daily mark-to-market for the pair
                pos = state["position"]
                pa, pb = float(closes.loc[d, a]), float(closes.loc[d, b])
                # log-return-based, half capital each side
                ret_a = math.log(pa / state["entry_a"])
                ret_b = math.log(pb / state["entry_b"])
                pair_pnl_pct = pos * (ret_b - ret_a)  # if pos=1: long A short B → ret_a - ret_b... fix below
                # Actually: pos=1 means long A short B (A was cheap), pos=-1 means short A long B
                if pos == 1:
                    pair_pnl_pct = ret_a - ret_b
                else:
                    pair_pnl_pct = ret_b - ret_a

                # exit rules
                if abs(z) <= z_exit:
                    # close — realize PnL
                    realized = pair_pnl_pct * pair_capital
                    spread_pnl_today += realized
                    state["position"] = 0
                    trades.append({"date": d, "pair": (a, b), "action": "close",
                                   "pnl": realized, "z_exit": z})
                elif abs(z) > z_stop:
                    realized = pair_pnl_pct * pair_capital
                    spread_pnl_today += realized
                    state["position"] = 0
                    trades.append({"date": d, "pair": (a, b), "action": "stop",
                                   "pnl": realized, "z_stop": z})
        # apply daily spread PnL to cash
        cash += spread_pnl_today
        equity_history.append(cash)

    equity = pd.Series(equity_history, index=common_dates, name="equity")
    return BacktestResult(name="pairs_trade_basket", equity=equity,
                          weights=pd.DataFrame(), trades=trades,
                          metrics=metrics(equity))


# ---------- 5: vol-targeted single-name trend ----------

def vol_targeted_trend(target_vol: float = 0.15, lookback: int = 252, skip: int = 21,
                       rebalance: str = "weekly", cost_bps: float = 5.0) -> BacktestResult:
    """
    For each AI-9 name independently: long if 12-1 momentum > 0, scale exposure
    inversely to 60-day realized vol to hit `target_vol` per name. Equal capital
    across names; max 100% notional total.
    """
    closes = load_closes()
    universe = [t for t in category("core_ai_infra") if t in closes.columns]
    px = closes[universe].dropna()
    rets = px.pct_change()

    mom = momentum_score(px, lookback=lookback, skip=skip)
    vol = rets.rolling(60).std() * math.sqrt(252)
    rebalance_dates = make_rebalance_dates(mom.dropna(how="all").index, rebalance)

    weights_at = {}
    for d in rebalance_dates:
        m = mom.loc[d]
        v = vol.loc[d]
        signal = (m > 0).astype(int)
        # vol-targeted exposure per name; cap at 1.0
        raw_exposure = signal * (target_vol / v.replace(0, np.nan))
        raw_exposure = raw_exposure.clip(upper=1.0).fillna(0)
        per_name_cap = 1.0 / len(universe)
        scaled = raw_exposure * per_name_cap
        # ensure total <= 1
        if scaled.sum() > 1.0:
            scaled = scaled / scaled.sum()
        weights_at[d] = scaled

    weights = step_weights(weights_at, px.index, universe)
    equity, trades = simulate_long_portfolio(weights, closes[universe].loc[px.index],
                                              cost_bps=cost_bps)
    return BacktestResult(name="vol_targeted_trend",
                          equity=equity, weights=weights, trades=trades,
                          metrics=metrics(equity))


# ---------- 6/7/8: thematic baskets ----------

def thematic_basket(name: str, tickers: list[str]) -> BacktestResult:
    return benchmark_equal_weight(tickers, name)


# ---------- 9: regime-gated long basket ----------

def regime_gated_universe(cost_bps: float = 5.0) -> BacktestResult:
    """
    Long equal-weight AI-9 only when:
      - VIX (using ^VIX proxy via VXX ETF — VXX rises when VIX rises) is below its 60-day rolling median, AND
      - NVDA close > 50-day SMA
    Otherwise hold cash.
    """
    closes = load_closes()
    universe = [t for t in category("core_ai_infra") if t in closes.columns]
    if "VXX" not in closes.columns or "NVDA" not in closes.columns:
        return BacktestResult(name="regime_gated_universe", equity=pd.Series(dtype=float),
                              weights=pd.DataFrame(), metrics={})
    vxx = closes["VXX"]
    vxx_median = vxx.rolling(60).median()
    vix_calm = vxx < vxx_median
    nvda_sma = closes["NVDA"].rolling(50).mean()
    nvda_uptrend = closes["NVDA"] > nvda_sma
    risk_on = vix_calm & nvda_uptrend

    rebalance_dates = make_rebalance_dates(closes.index, "weekly")
    weights_at = {}
    for d in rebalance_dates:
        if d in risk_on.index and bool(risk_on.loc[d]):
            weights_at[d] = equal_weight(universe)
        else:
            weights_at[d] = pd.Series(0.0, index=universe)
    weights = step_weights(weights_at, closes.index, universe)
    equity, trades = simulate_long_portfolio(weights, closes[universe].loc[closes.index],
                                              cost_bps=cost_bps)
    return BacktestResult(name="regime_gated_universe",
                          equity=equity, weights=weights, trades=trades,
                          metrics=metrics(equity))


# ---------- 10: risk parity overlay ----------

def risk_parity_overlay(rebalance: str = "monthly", lookback: int = 60,
                        cost_bps: float = 5.0) -> BacktestResult:
    """
    Inverse-volatility weights across AI-9 (treated as one 'sleeve' via its
    vol average), SPY (broad equity), TLT (long duration), GLD (commodity hedge),
    UUP (USD).
    Each "sleeve" gets weight ~ 1/vol normalized.
    AI-9 sleeve is implemented as equal-weight underneath.
    """
    closes = load_closes()
    sleeves = {
        "AI": [t for t in category("core_ai_infra") if t in closes.columns],
        "SPY": ["SPY"],
        "TLT": ["TLT"],
        "GLD": ["GLD"],
        "UUP": ["UUP"],
    }
    # only keep sleeves that have data
    sleeves = {k: v for k, v in sleeves.items() if all(t in closes.columns for t in v)}
    universe = sorted(set(t for v in sleeves.values() for t in v))
    px = closes[universe].dropna()
    rets = px.pct_change()

    # compute sleeve return = equal-weight of its tickers' returns
    sleeve_rets: dict[str, pd.Series] = {}
    for name, tickers in sleeves.items():
        sleeve_rets[name] = rets[tickers].mean(axis=1)
    sleeve_df = pd.DataFrame(sleeve_rets)

    sleeve_vol = sleeve_df.rolling(lookback).std() * math.sqrt(252)
    rebalance_dates = make_rebalance_dates(sleeve_vol.dropna(how="all").index, rebalance)

    weights_at = {}
    for d in rebalance_dates:
        v = sleeve_vol.loc[d].dropna()
        if v.empty:
            continue
        inv = 1.0 / v
        sleeve_w = inv / inv.sum()
        # fan out sleeve weight across its tickers (equal within sleeve)
        per_ticker = pd.Series(0.0, index=universe)
        for sleeve_name, sleeve_weight in sleeve_w.items():
            tickers = sleeves[sleeve_name]
            for t in tickers:
                per_ticker[t] += sleeve_weight / len(tickers)
        weights_at[d] = per_ticker
    weights = step_weights(weights_at, px.index, universe)
    equity, trades = simulate_long_portfolio(weights, closes[universe].loc[px.index],
                                              cost_bps=cost_bps)
    return BacktestResult(name="risk_parity_overlay",
                          equity=equity, weights=weights, trades=trades,
                          metrics=metrics(equity))
