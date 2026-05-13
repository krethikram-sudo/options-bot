"""Generic parameterized strategy engine.

A single function `run_strategy(config)` can express most candidate strategies
by varying its config dict. This makes 100-strategy iterative search tractable.

Supported `signal` types:
  - "buy_hold"           : single ticker hold
  - "equal_weight"       : equal-weight static basket
  - "xs_momentum"        : cross-sectional momentum (top-N by N-day return ex skip)
  - "xs_meanrev"         : cross-sectional mean reversion (bottom-N by N-day return)
  - "xs_quality_trend"   : composite of rolling Sharpe + trend
  - "ts_momentum_voltgt" : per-name TS momentum with vol-targeted sizing
  - "dual_momentum"      : asset-class rotation between equity + bonds based on momentum
  - "regime_long_short"  : long basket when regime=on, short basket or cash when off
  - "concentration"      : single highest-momentum name (top-1, focused)
  - "lowvol_tilt"        : equal-weight bottom-N by realized vol

Filters supported:
  - vix_gate            : only long when VXX < its rolling-N median
  - sma_gate            : only long when SPY > its N-day SMA
  - drawdown_gate       : cut to cash when portfolio is X% below peak
  - momentum_filter     : only include tickers with positive 3-month return
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

import numpy as np
import pandas as pd

from research.data_lib import category, load_closes
from research.strategies.framework import (BacktestResult, equal_weight,
                                            make_rebalance_dates, metrics,
                                            momentum_score, simulate_long_portfolio,
                                            step_weights, zscore_cross_section)


# ---- universe resolver ----

_UNIVERSE_PRESETS = {
    "ai9": "core_ai_infra",
    "semi_equipment": "semi_equipment",
    "foundries": "foundries",
    "other_silicon": "other_silicon",
    "networking": "networking_optical",
    "storage": "storage",
    "servers_power": "servers_power",
    "hyperscalers": "hyperscalers",
    "ai_software": "ai_software",
    "cybersecurity": "cybersecurity",
    "vertical_ai": "vertical_ai",
    "power_utilities": "power_utilities",
    "data_center_reits": "data_center_reits",
    "quantum": "quantum",
    "factor_etfs": "factor_etfs",
    "sector_etfs": "sector_etfs",
    "defense": "defense",
}

_COMPOSITE_UNIVERSES = {
    "ai_full_chain": ["core_ai_infra", "semi_equipment", "foundries", "other_silicon",
                      "networking_optical", "storage", "servers_power", "hyperscalers"],
    "ai_silicon_only": ["core_ai_infra", "semi_equipment", "other_silicon", "foundries"],
    "ai_software_full": ["ai_software", "ai_saas", "cybersecurity", "vertical_ai"],
    "ai_infra_plus_power": ["core_ai_infra", "servers_power", "power_utilities", "data_center_reits"],
    "broad_diversifier": ["benchmarks", "factor_etfs", "bonds", "commodities"],
    "sector_etfs_all": ["sector_etfs"],
}


def resolve_universe(spec) -> list[str]:
    closes = load_closes()
    if isinstance(spec, list):
        return [t for t in spec if t in closes.columns]
    if spec in _UNIVERSE_PRESETS:
        return [t for t in category(_UNIVERSE_PRESETS[spec]) if t in closes.columns]
    if spec in _COMPOSITE_UNIVERSES:
        out = []
        for cat in _COMPOSITE_UNIVERSES[spec]:
            out.extend(t for t in category(cat) if t in closes.columns and t not in out)
        return out
    raise ValueError(f"unknown universe spec: {spec}")


# ---- signal generators ----

def _sig_xs_momentum(closes: pd.DataFrame, lookback: int, skip: int) -> pd.DataFrame:
    return momentum_score(closes, lookback=lookback, skip=skip)


def _sig_xs_meanrev(closes: pd.DataFrame, lookback: int) -> pd.DataFrame:
    """Negative momentum — trailing N-day return, lower = stronger buy."""
    return -closes.pct_change(lookback)


def _sig_quality_trend(closes: pd.DataFrame, sharpe_window: int, trend_window: int) -> pd.DataFrame:
    rets = closes.pct_change()
    rmean = rets.rolling(sharpe_window).mean() * 252
    rvol = rets.rolling(sharpe_window).std() * math.sqrt(252)
    quality = (rmean - 0.04) / rvol
    trend = closes.pct_change(trend_window)
    return (zscore_cross_section(quality) + zscore_cross_section(trend)) / 2


def _sig_lowvol(closes: pd.DataFrame, vol_window: int) -> pd.DataFrame:
    """Inverse of realized vol — higher value = lower vol = better candidate."""
    return -closes.pct_change().rolling(vol_window).std()


# ---- weight builders ----

def _equal_weight_top_n(scores: pd.Series, top_n: int, universe: list[str]) -> pd.Series:
    s = scores.dropna()
    if len(s) < top_n:
        return pd.Series(0.0, index=universe)
    top = s.nlargest(top_n).index.tolist()
    w = pd.Series(0.0, index=universe)
    w.loc[top] = 1.0 / top_n
    return w


def _vol_weighted_top_n(scores: pd.Series, top_n: int, universe: list[str],
                        closes: pd.DataFrame, date) -> pd.Series:
    s = scores.dropna()
    if len(s) < top_n:
        return pd.Series(0.0, index=universe)
    top = s.nlargest(top_n).index.tolist()
    rets = closes[top].pct_change().loc[:date].tail(60)
    vols = rets.std() * math.sqrt(252)
    inv = 1.0 / vols.replace(0, np.nan)
    norm = (inv / inv.sum()).fillna(0)
    w = pd.Series(0.0, index=universe)
    w.loc[norm.index] = norm.values
    return w


# ---- regime filters ----

def _vix_calm_mask(closes: pd.DataFrame, lookback: int = 60) -> pd.Series:
    if "VXX" not in closes.columns:
        return pd.Series(True, index=closes.index)
    vxx = closes["VXX"]
    return vxx < vxx.rolling(lookback).median()


def _sma_uptrend_mask(closes: pd.DataFrame, ticker: str = "SPY",
                       window: int = 200) -> pd.Series:
    if ticker not in closes.columns:
        return pd.Series(True, index=closes.index)
    px = closes[ticker]
    return px > px.rolling(window).mean()


# ---- main entrypoint ----

@dataclass
class Strategy:
    id: int
    name: str
    family: str
    rationale: str
    config: dict


def run_strategy(strat: Strategy) -> BacktestResult:
    cfg = strat.config
    signal = cfg.get("signal", "equal_weight")
    closes = load_closes()
    universe_spec = cfg.get("universe", "ai9")
    universe = resolve_universe(universe_spec)
    if not universe:
        return BacktestResult(name=strat.name, equity=pd.Series(dtype=float),
                              weights=pd.DataFrame(), metrics={})
    px = closes[universe]
    rebalance_freq = cfg.get("rebalance", "monthly")
    cost_bps = cfg.get("cost_bps", 5.0)

    # --- buy-and-hold flavors ---
    if signal == "buy_hold":
        ticker = cfg["ticker"]
        if ticker not in closes.columns:
            return BacktestResult(name=strat.name, equity=pd.Series(dtype=float),
                                  weights=pd.DataFrame(), metrics={})
        s = closes[ticker].dropna()
        eq = s / s.iloc[0] * 100_000
        return BacktestResult(name=strat.name, equity=eq,
                              weights=pd.DataFrame({ticker: 1.0}, index=eq.index),
                              trades=[], metrics=metrics(eq))

    if signal == "equal_weight":
        px2 = px.dropna(how="any")
        if px2.empty:
            return BacktestResult(name=strat.name, equity=pd.Series(dtype=float),
                                  weights=pd.DataFrame(), metrics={})
        rdates = make_rebalance_dates(px2.index, rebalance_freq)
        weights_at = {d: equal_weight(universe) for d in rdates}
        weights = step_weights(weights_at, px2.index, universe)
        equity, trades = simulate_long_portfolio(weights, closes[universe].loc[px2.index],
                                                  cost_bps=cost_bps)
        return BacktestResult(name=strat.name, equity=equity, weights=weights,
                              trades=trades, metrics=metrics(equity))

    # --- score-based strategies ---
    if signal == "xs_momentum":
        scores = _sig_xs_momentum(px, lookback=cfg.get("lookback", 252), skip=cfg.get("skip", 21))
    elif signal == "xs_meanrev":
        scores = _sig_xs_meanrev(px, lookback=cfg.get("lookback", 21))
    elif signal == "xs_quality_trend":
        scores = _sig_quality_trend(px, sharpe_window=cfg.get("sharpe_window", 60),
                                     trend_window=cfg.get("trend_window", 126))
    elif signal == "lowvol_tilt":
        scores = _sig_lowvol(px, vol_window=cfg.get("vol_window", 60))
    elif signal == "ts_momentum_voltgt":
        return _ts_momentum_voltgt(strat, closes, universe, cfg)
    elif signal == "dual_momentum":
        return _dual_momentum(strat, closes, cfg)
    else:
        raise ValueError(f"unknown signal: {signal}")

    # --- pick top-N and weight ---
    top_n = cfg.get("top_n", 3)
    weight_method = cfg.get("weight_method", "equal")
    rdates = make_rebalance_dates(scores.dropna(how="all").index, rebalance_freq)
    weights_at = {}

    # filters
    vix_mask = _vix_calm_mask(closes) if cfg.get("vix_gate", False) else None
    sma_mask = _sma_uptrend_mask(closes, window=cfg.get("sma_window", 200)) if cfg.get("sma_gate", False) else None

    for d in rdates:
        # apply gating filters: if any filter says "off", go to cash
        if vix_mask is not None and d in vix_mask.index and not bool(vix_mask.loc[d]):
            weights_at[d] = pd.Series(0.0, index=universe)
            continue
        if sma_mask is not None and d in sma_mask.index and not bool(sma_mask.loc[d]):
            weights_at[d] = pd.Series(0.0, index=universe)
            continue
        s = scores.loc[d] if d in scores.index else None
        if s is None:
            continue
        if weight_method == "equal":
            w = _equal_weight_top_n(s, top_n, universe)
        elif weight_method == "vol":
            w = _vol_weighted_top_n(s, top_n, universe, closes, d)
        else:
            w = _equal_weight_top_n(s, top_n, universe)
        weights_at[d] = w

    weights = step_weights(weights_at, px.index, universe)
    equity, trades = simulate_long_portfolio(weights, closes[universe].loc[px.index],
                                              cost_bps=cost_bps)
    return BacktestResult(name=strat.name, equity=equity, weights=weights,
                          trades=trades, metrics=metrics(equity))


def _ts_momentum_voltgt(strat: Strategy, closes: pd.DataFrame, universe: list[str],
                        cfg: dict) -> BacktestResult:
    px = closes[universe].dropna()
    rets = px.pct_change()
    mom = momentum_score(px, lookback=cfg.get("lookback", 252), skip=cfg.get("skip", 21))
    vol = rets.rolling(60).std() * math.sqrt(252)
    target_vol = cfg.get("target_vol", 0.15)
    rebalance = cfg.get("rebalance", "weekly")
    rdates = make_rebalance_dates(mom.dropna(how="all").index, rebalance)
    weights_at = {}
    for d in rdates:
        m = mom.loc[d]
        v = vol.loc[d]
        signal = (m > 0).astype(int)
        raw = signal * (target_vol / v.replace(0, np.nan))
        raw = raw.clip(upper=1.0).fillna(0)
        per_name_cap = 1.0 / len(universe)
        scaled = raw * per_name_cap
        if scaled.sum() > 1.0:
            scaled = scaled / scaled.sum()
        weights_at[d] = scaled
    weights = step_weights(weights_at, px.index, universe)
    equity, trades = simulate_long_portfolio(weights, closes[universe].loc[px.index],
                                              cost_bps=cfg.get("cost_bps", 5.0))
    return BacktestResult(name=strat.name, equity=equity, weights=weights,
                          trades=trades, metrics=metrics(equity))


def _dual_momentum(strat: Strategy, closes: pd.DataFrame, cfg: dict) -> BacktestResult:
    """Asset-class rotation: hold whichever (equity, bonds, gold) had best 6-month return,
    fall back to T-bills (cash) if all are below 0."""
    sleeve_tickers = cfg.get("sleeves", {"equity": "QQQ", "bonds": "TLT", "gold": "GLD"})
    sleeves = {name: t for name, t in sleeve_tickers.items() if t in closes.columns}
    if not sleeves:
        return BacktestResult(name=strat.name, equity=pd.Series(dtype=float),
                              weights=pd.DataFrame(), metrics={})
    universe = list(sleeves.values())
    lookback = cfg.get("lookback", 126)
    rebalance = cfg.get("rebalance", "monthly")
    px = closes[universe].dropna()
    mom = px.pct_change(lookback)
    rdates = make_rebalance_dates(mom.dropna(how="all").index, rebalance)
    weights_at = {}
    for d in rdates:
        m = mom.loc[d].dropna()
        if m.empty or m.max() <= 0:
            weights_at[d] = pd.Series(0.0, index=universe)
            continue
        winner = m.idxmax()
        w = pd.Series(0.0, index=universe)
        w.loc[winner] = 1.0
        weights_at[d] = w
    weights = step_weights(weights_at, px.index, universe)
    equity, trades = simulate_long_portfolio(weights, closes[universe].loc[px.index],
                                              cost_bps=cfg.get("cost_bps", 5.0))
    return BacktestResult(name=strat.name, equity=equity, weights=weights,
                          trades=trades, metrics=metrics(equity))
