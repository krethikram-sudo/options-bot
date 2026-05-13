"""Year-over-year forward-looking backtest of the deployed 5-sleeve strategy.

Strict no-lookahead: every signal/decision uses only data up to and including
that day. Indicators warm up naturally; early days of the dataset will have
NaN signals which means no positions until they're computable.

Sleeves modeled:
  1. spreads      — 35-delta bull put credit spreads, monthly entry, BS-synthesized
  2. trend        — 50-SMA cross, equal $/ticker, -8% stop
  3. rotation     — top-3 by 30-day return, monthly rebalance
  4. straddles    — AVGO/MRVL pre-earnings ATM straddles, BS-synthesized
  5. chain        — equal-weight 48-ticker AI value chain, monthly rebalance

Outputs: per-sleeve daily equity, total portfolio equity, sliced by calendar
year (2020-2026 YTD). Plots saved to research/strategies/yearly_charts/.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf
from scipy.stats import norm

import config
from research.strategies.gap_tests import load_ext_closes, ai_full_chain

OUT_DIR = Path(__file__).resolve().parent / "yearly_charts"
OUT_DIR.mkdir(parents=True, exist_ok=True)

YEARS = [2020, 2021, 2022, 2023, 2024, 2025, 2026]

# Initial allocations per sleeve (must sum to <= 100k)
ALLOC = {
    "spreads": 25_000,
    "trend": 30_000,
    "rotation": 25_000,
    "straddles": 15_000,
    "chain": 25_000,
}
COST_BPS = 5.0
RATE = 0.045
IV_HAIRCUT = config.SPREAD_IV_HAIRCUT       # 0.65


# ============================================================
# Black-Scholes helpers
# ============================================================

def bs_price(spot, strike, t_years, rate, iv, kind):
    if t_years <= 0:
        intr = (spot - strike) if kind == "call" else (strike - spot)
        return max(intr, 0.0)
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    d2 = d1 - iv * math.sqrt(t_years)
    if kind == "call":
        return spot * norm.cdf(d1) - strike * math.exp(-rate * t_years) * norm.cdf(d2)
    return strike * math.exp(-rate * t_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def bs_delta(spot, strike, t_years, rate, iv, kind):
    if t_years <= 0 or iv <= 0:
        if kind == "call":
            return 1.0 if spot > strike else 0.0
        return -1.0 if spot < strike else 0.0
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    return norm.cdf(d1) if kind == "call" else norm.cdf(d1) - 1


def realized_vol_to_date(closes: pd.Series, as_of: pd.Timestamp, window: int = 30) -> float:
    """Realized vol using only data up to and including as_of. No lookahead."""
    sub = closes.loc[:as_of]
    if len(sub) < window:
        return 0.0
    log_ret = np.log(sub / sub.shift(1)).dropna().tail(window)
    return float(log_ret.std() * math.sqrt(252))


# ============================================================
# SLEEVE 1: Bull put credit spreads (BS-synthesized)
# ============================================================

@dataclass
class SpreadPos:
    ticker: str
    open_date: pd.Timestamp
    expiry: pd.Timestamp
    short_strike: float
    long_strike: float
    entry_credit: float
    entry_iv: float


def simulate_spreads(closes: pd.DataFrame, dates: pd.DatetimeIndex,
                     initial: float = ALLOC["spreads"],
                     dte: int = 45, target_delta: float = 0.35,
                     width_pct: float = 0.05,
                     profit_target: float = 0.25) -> pd.Series:
    universe = ["NVDA", "AMD", "AVGO", "MU", "TSM", "MRVL", "SMCI"]
    universe = [t for t in universe if t in closes.columns]
    cash = initial
    open_pos: dict[str, SpreadPos] = {}
    equity = []

    # try to open one new spread per month per ticker (skip if already open)
    rebalance_dates = [d for i, d in enumerate(dates)
                       if i == 0 or d.month != dates[i-1].month]
    rebal_set = set(rebalance_dates)

    risk_cap = initial  # max combined max-loss across open positions

    for d in dates:
        # close any expired positions
        to_close = []
        for ticker, pos in open_pos.items():
            try:
                spot = float(closes.loc[d, ticker])
            except (KeyError, ValueError):
                continue
            if pd.isna(spot):
                continue
            days_left = (pos.expiry - d).days
            if days_left <= 0:
                # exit at intrinsic
                short_int = max(pos.short_strike - spot, 0)
                long_int = max(pos.long_strike - spot, 0)
                liability = short_int - long_int
                pnl = (pos.entry_credit - liability) * 100
                cash += pnl
                to_close.append(ticker)
                continue
            # mark to market & check profit target
            iv_now = realized_vol_to_date(closes[ticker], d) * IV_HAIRCUT
            if iv_now <= 0:
                continue
            t_now = days_left / 365.0
            try:
                short_p = bs_price(spot, pos.short_strike, t_now, RATE, iv_now, "put")
                long_p = bs_price(spot, pos.long_strike, t_now, RATE, iv_now, "put")
                liability = short_p - long_p
                pnl_pct = (pos.entry_credit - liability) / pos.entry_credit
                if pnl_pct >= profit_target:
                    pnl_dollars = (pos.entry_credit - liability) * 100
                    cash += pnl_dollars
                    to_close.append(ticker)
            except Exception:
                continue
        for t in to_close:
            del open_pos[t]

        # try to open new positions (monthly)
        if d in rebal_set:
            current_risk = sum(
                ((p.short_strike - p.long_strike) - p.entry_credit) * 100
                for p in open_pos.values()
            )
            for ticker in universe:
                if ticker in open_pos:
                    continue
                if current_risk >= risk_cap:
                    break
                try:
                    spot = float(closes.loc[d, ticker])
                except KeyError:
                    continue
                if pd.isna(spot) or spot <= 0:
                    continue
                iv = realized_vol_to_date(closes[ticker], d) * IV_HAIRCUT
                if iv <= 0:
                    continue
                t_years = dte / 365.0
                # find -35-delta strike via BS (rough analytical approximation)
                # for put: delta = N(d1) - 1; want delta = -0.35 → N(d1) = 0.65 → d1 ≈ 0.385
                # strike = spot * exp(-(d1*iv*sqrt(t)) - (rate+0.5*iv^2)*t)
                d1 = 0.385
                strike = spot * math.exp(-(d1 * iv * math.sqrt(t_years)) - (RATE + 0.5 * iv * iv) * t_years)
                short_strike = round(strike)
                long_strike = round(short_strike - max(spot * width_pct, 1.0))
                if long_strike >= short_strike or long_strike <= 0:
                    continue
                short_premium = bs_price(spot, short_strike, t_years, RATE, iv, "put")
                long_premium = bs_price(spot, long_strike, t_years, RATE, iv, "put")
                credit = short_premium - long_premium
                if credit < 0.20:
                    continue
                max_loss = (short_strike - long_strike - credit) * 100
                if current_risk + max_loss > risk_cap:
                    continue
                open_pos[ticker] = SpreadPos(
                    ticker=ticker, open_date=d,
                    expiry=d + pd.Timedelta(days=dte),
                    short_strike=short_strike, long_strike=long_strike,
                    entry_credit=credit, entry_iv=iv,
                )
                current_risk += max_loss

        # daily mark
        # cash + sum of open spreads' current value (entry_credit - current_liability)
        unrealized = 0.0
        for ticker, pos in open_pos.items():
            try:
                spot = float(closes.loc[d, ticker])
            except KeyError:
                continue
            if pd.isna(spot):
                continue
            days_left = (pos.expiry - d).days
            if days_left <= 0:
                short_int = max(pos.short_strike - spot, 0)
                long_int = max(pos.long_strike - spot, 0)
                liability = short_int - long_int
            else:
                iv_now = realized_vol_to_date(closes[ticker], d) * IV_HAIRCUT
                if iv_now <= 0:
                    continue
                t_now = days_left / 365.0
                short_p = bs_price(spot, pos.short_strike, t_now, RATE, iv_now, "put")
                long_p = bs_price(spot, pos.long_strike, t_now, RATE, iv_now, "put")
                liability = short_p - long_p
            unrealized += (pos.entry_credit - liability) * 100
        equity.append(cash + unrealized)
    return pd.Series(equity, index=dates, name="spreads")


# ============================================================
# SLEEVE 2: Trend-following equities
# ============================================================

def simulate_trend(closes: pd.DataFrame, dates: pd.DatetimeIndex,
                   initial: float = ALLOC["trend"],
                   sma_period: int = 50, stop_pct: float = -0.08) -> pd.Series:
    universe = ["NVDA", "AMD", "AVGO", "MU", "TSM", "MRVL", "ARM", "SMCI", "SNDK"]
    universe = [t for t in universe if t in closes.columns]
    sma = closes[universe].rolling(sma_period).mean()
    n = len(universe)
    cash = initial
    shares = {t: 0.0 for t in universe}
    entry = {t: 0.0 for t in universe}
    per_ticker_alloc = initial / n
    equity = []

    for d in dates:
        if d not in closes.index:
            equity.append(cash + sum(shares[t] * closes[t].iloc[-1] if len(closes[t]) else 0
                                     for t in universe))
            continue
        for t in universe:
            try:
                price = float(closes.loc[d, t])
                cur_sma = float(sma.loc[d, t])
            except (KeyError, ValueError):
                continue
            if pd.isna(price) or pd.isna(cur_sma):
                continue
            if shares[t] > 0:
                cur_pnl = (price - entry[t]) / entry[t]
                # exit on cross-below or stop
                if price < cur_sma or cur_pnl <= stop_pct:
                    proceeds = shares[t] * price * (1 - COST_BPS / 10_000)
                    cash += proceeds
                    shares[t] = 0
                    entry[t] = 0
            else:
                # enter on close > SMA
                if price > cur_sma:
                    n_shares = (per_ticker_alloc * (1 - COST_BPS / 10_000)) / price
                    cost = n_shares * price * (1 + COST_BPS / 10_000)
                    if cost <= cash:
                        shares[t] = n_shares
                        entry[t] = price
                        cash -= cost
        # mark
        held = 0.0
        for t in universe:
            if shares[t] > 0:
                try:
                    held += shares[t] * float(closes.loc[d, t])
                except KeyError:
                    pass
        equity.append(cash + held)
    return pd.Series(equity, index=dates, name="trend")


# ============================================================
# SLEEVE 3: Rotational momentum
# ============================================================

def simulate_rotation(closes: pd.DataFrame, dates: pd.DatetimeIndex,
                      initial: float = ALLOC["rotation"],
                      lookback: int = 30, top_n: int = 3,
                      rebalance_days: int = 30) -> pd.Series:
    universe = ["NVDA", "AMD", "AVGO", "MU", "TSM", "MRVL", "ARM", "SMCI", "SNDK"]
    universe = [t for t in universe if t in closes.columns]
    cash = initial
    shares = {t: 0.0 for t in universe}
    last_rebal = None
    equity = []

    for d in dates:
        if d not in closes.index:
            equity.append(cash + sum(shares[t] * closes[t].iloc[-1] if len(closes[t]) else 0
                                     for t in universe))
            continue
        # rebalance check
        if last_rebal is None or (d - last_rebal).days >= rebalance_days:
            # compute lookback returns
            returns = {}
            prices = {}
            for t in universe:
                try:
                    sub = closes[t].loc[:d].dropna()
                    if len(sub) < lookback + 1:
                        continue
                    cur = float(sub.iloc[-1])
                    past = float(sub.iloc[-(lookback + 1)])
                    returns[t] = (cur - past) / past
                    prices[t] = cur
                except KeyError:
                    continue
            if returns:
                top = sorted(returns.keys(), key=lambda x: returns[x], reverse=True)[:top_n]
                # liquidate non-top
                for t in list(universe):
                    if t not in top and shares[t] > 0:
                        try:
                            price = float(closes.loc[d, t])
                            cash += shares[t] * price * (1 - COST_BPS / 10_000)
                            shares[t] = 0
                        except KeyError:
                            pass
                # buy top equally
                if top:
                    held_value = sum(shares[t] * prices.get(t, 0) for t in top if shares[t] > 0)
                    total = cash + held_value
                    target = total / top_n
                    for t in top:
                        cur_value = shares[t] * prices.get(t, 0)
                        diff = target - cur_value
                        if diff > prices[t]:
                            n_shares = (diff * (1 - COST_BPS / 10_000)) / prices[t]
                            cost = n_shares * prices[t] * (1 + COST_BPS / 10_000)
                            if cost <= cash:
                                shares[t] += n_shares
                                cash -= cost
                last_rebal = d
        # mark
        held = sum(shares[t] * float(closes.loc[d, t])
                   for t in universe
                   if d in closes.index and t in closes.columns
                   and not pd.isna(closes.loc[d, t])
                   and shares[t] > 0)
        equity.append(cash + held)
    return pd.Series(equity, index=dates, name="rotation")


# ============================================================
# SLEEVE 4: Earnings straddles (BS-synthesized)
# ============================================================

def fetch_earnings_dates(ticker: str) -> list[pd.Timestamp]:
    try:
        ed = yf.Ticker(ticker).earnings_dates
        if ed is None or ed.empty:
            return []
    except Exception:
        return []
    if "Reported EPS" in ed.columns:
        past = ed[ed["Reported EPS"].notna()]
    else:
        past = ed
    if past.empty:
        return []
    out = []
    for ts in past.index:
        ts_naive = ts.tz_localize(None) if ts.tz is not None else ts
        out.append(ts_naive)
    return sorted(out)


def simulate_straddles(closes: pd.DataFrame, dates: pd.DatetimeIndex,
                       initial: float = ALLOC["straddles"],
                       iv_pre_mult: float = 1.6, iv_post_mult: float = 0.75,
                       dte: int = 7) -> pd.Series:
    universe = ["AVGO", "MRVL"]
    universe = [t for t in universe if t in closes.columns]
    earnings_per_ticker = {t: fetch_earnings_dates(t) for t in universe}
    cash = initial
    equity = []

    # Pre-compute event dates for fast lookup
    events: list[tuple[pd.Timestamp, str]] = []
    for t, dlist in earnings_per_ticker.items():
        for ed in dlist:
            events.append((ed, t))

    # Track open straddles
    open_straddles: list[dict] = []

    # Map of date -> events on or just before
    for d in dates:
        # close any straddles where d > earnings_date
        new_open = []
        for s in open_straddles:
            if d >= s["exit_date"]:
                # exit
                spot = closes[s["ticker"]].asof(d)
                if pd.isna(spot):
                    continue
                t_left = max((s["expiry"] - d).days / 365.0, 1 / 365 / 24)
                iv_exit = realized_vol_to_date(closes[s["ticker"]], d) * iv_post_mult
                if iv_exit <= 0:
                    continue
                call_x = bs_price(spot, s["strike"], t_left, RATE, iv_exit, "call")
                put_x = bs_price(spot, s["strike"], t_left, RATE, iv_exit, "put")
                proceeds = (call_x + put_x) * 100
                cash += proceeds
            else:
                new_open.append(s)
        open_straddles = new_open

        # check if any earnings is exactly tomorrow → open straddle today (T-1)
        for ed, ticker in events:
            ed_norm = ed.normalize()
            d_norm = d.normalize()
            # T-1: open today if next trading day is the earnings date
            future = dates[dates > d]
            if len(future) == 0:
                continue
            next_d = future[0]
            if abs((next_d - ed_norm).days) <= 1 and next_d <= ed_norm:
                # open if not already open on this ticker
                if any(s["ticker"] == ticker for s in open_straddles):
                    continue
                spot = float(closes.loc[d, ticker]) if (d in closes.index and ticker in closes.columns) else None
                if spot is None or pd.isna(spot):
                    continue
                iv_pre = realized_vol_to_date(closes[ticker], d) * iv_pre_mult
                if iv_pre <= 0:
                    continue
                t_years = dte / 365.0
                strike = round(spot)
                call_e = bs_price(spot, strike, t_years, RATE, iv_pre, "call")
                put_e = bs_price(spot, strike, t_years, RATE, iv_pre, "put")
                cost = (call_e + put_e) * 100  # 1 contract per ticker
                if cost > cash * 0.3:  # don't blow >30% of straddle sleeve on one event
                    continue
                cash -= cost
                # exit at T+1 (next trading day after earnings)
                future2 = dates[dates > ed_norm]
                if len(future2) == 0:
                    continue
                exit_d = future2[0]
                open_straddles.append({
                    "ticker": ticker, "open_date": d, "earnings_date": ed_norm,
                    "exit_date": exit_d, "expiry": d + pd.Timedelta(days=dte),
                    "strike": strike, "entry_cost": cost,
                })

        # mark to market
        marked = 0.0
        for s in open_straddles:
            try:
                spot = float(closes.loc[d, s["ticker"]])
            except KeyError:
                continue
            if pd.isna(spot):
                continue
            t_left = max((s["expiry"] - d).days / 365.0, 1 / 365 / 24)
            iv_now = realized_vol_to_date(closes[s["ticker"]], d) * iv_pre_mult
            if iv_now <= 0:
                continue
            call_p = bs_price(spot, s["strike"], t_left, RATE, iv_now, "call")
            put_p = bs_price(spot, s["strike"], t_left, RATE, iv_now, "put")
            marked += (call_p + put_p) * 100

        equity.append(cash + marked)
    return pd.Series(equity, index=dates, name="straddles")


# ============================================================
# SLEEVE 5: AI full chain basket
# ============================================================

def simulate_chain(closes: pd.DataFrame, dates: pd.DatetimeIndex,
                   initial: float = ALLOC["chain"],
                   rebalance_days: int = 30) -> pd.Series:
    universe = [t for t in config.CHAIN_TICKERS if t in closes.columns]
    cash = initial
    shares = {t: 0.0 for t in universe}
    last_rebal = None
    equity = []

    for d in dates:
        if d not in closes.index:
            equity.append(cash + sum(
                shares[t] * (closes[t].asof(d) if t in closes.columns else 0)
                for t in universe))
            continue
        if last_rebal is None or (d - last_rebal).days >= rebalance_days:
            # equal-weight rebalance
            available_tickers = [t for t in universe
                                  if t in closes.columns
                                  and not pd.isna(closes.loc[d, t])]
            if not available_tickers:
                last_rebal = d
            else:
                # liquidate to cash
                for t in universe:
                    if shares[t] > 0:
                        try:
                            price = float(closes.loc[d, t])
                            cash += shares[t] * price * (1 - COST_BPS / 10_000)
                            shares[t] = 0
                        except KeyError:
                            pass
                # buy equal weight
                target_per = cash / len(available_tickers)
                for t in available_tickers:
                    try:
                        price = float(closes.loc[d, t])
                    except KeyError:
                        continue
                    if pd.isna(price) or price <= 0:
                        continue
                    n_shares = (target_per * (1 - COST_BPS / 10_000)) / price
                    cost = n_shares * price * (1 + COST_BPS / 10_000)
                    if cost <= cash:
                        shares[t] = n_shares
                        cash -= cost
                last_rebal = d
        # mark
        held = 0.0
        for t in universe:
            if shares[t] > 0 and t in closes.columns:
                price = closes[t].asof(d)
                if pd.notna(price):
                    held += shares[t] * float(price)
        equity.append(cash + held)
    return pd.Series(equity, index=dates, name="chain")


# ============================================================
# Orchestrator
# ============================================================

def run_full_backtest():
    closes = load_ext_closes()
    dates = closes.index

    print(f"Backtest window: {dates.min().date()} → {dates.max().date()} ({len(dates)} days)")
    print(f"Sleeve allocations: {ALLOC}")

    print("\nRunning sleeves...")
    print("  spreads...")
    eq_spreads = simulate_spreads(closes, dates)
    print(f"    final: ${eq_spreads.iloc[-1]:,.0f}")
    print("  trend...")
    eq_trend = simulate_trend(closes, dates)
    print(f"    final: ${eq_trend.iloc[-1]:,.0f}")
    print("  rotation...")
    eq_rotation = simulate_rotation(closes, dates)
    print(f"    final: ${eq_rotation.iloc[-1]:,.0f}")
    print("  straddles...")
    eq_straddles = simulate_straddles(closes, dates)
    print(f"    final: ${eq_straddles.iloc[-1]:,.0f}")
    print("  chain...")
    eq_chain = simulate_chain(closes, dates)
    print(f"    final: ${eq_chain.iloc[-1]:,.0f}")

    sleeves = pd.DataFrame({
        "spreads": eq_spreads, "trend": eq_trend,
        "rotation": eq_rotation, "straddles": eq_straddles,
        "chain": eq_chain,
    })
    sleeves["total"] = sleeves.sum(axis=1)
    return sleeves


def yearly_metrics_table(sleeves: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for year in YEARS:
        sub = sleeves[sleeves.index.year == year]
        if sub.empty:
            continue
        for col in sleeves.columns:
            s = sub[col]
            if len(s) < 2:
                continue
            ret = s.iloc[-1] / s.iloc[0] - 1
            running = s.cummax()
            dd = float((s - running).div(running).min())
            rets = s.pct_change().dropna()
            vol = rets.std() * math.sqrt(252) if len(rets) > 0 else 0
            sharpe = ret / vol if vol > 0 else 0
            rows.append({
                "year": year, "sleeve": col,
                "start_value": round(float(s.iloc[0]), 0),
                "end_value": round(float(s.iloc[-1]), 0),
                "return_pct": round(ret * 100, 1),
                "vol_pct": round(vol * 100, 1),
                "sharpe": round(sharpe, 2),
                "max_dd_pct": round(dd * 100, 1),
            })
    return pd.DataFrame(rows)


def make_plots(sleeves: pd.DataFrame):
    import matplotlib.pyplot as plt
    plt.rcParams["figure.dpi"] = 100
    plt.rcParams["axes.grid"] = True
    plt.rcParams["grid.alpha"] = 0.3

    # Figure 1: per-year stacked equity curves
    n_years = len([y for y in YEARS if not sleeves[sleeves.index.year == y].empty])
    fig, axes = plt.subplots(n_years, 1, figsize=(12, 3 * n_years), sharex=False)
    if n_years == 1:
        axes = [axes]
    plt_idx = 0
    for year in YEARS:
        sub = sleeves[sleeves.index.year == year]
        if sub.empty:
            continue
        ax = axes[plt_idx]
        # rebase each sleeve to start at its initial allocation for the year
        sub_rebased = sub.copy()
        for col in ["spreads", "trend", "rotation", "straddles", "chain"]:
            if col in sub.columns:
                # express as % return from start of year
                start = sub_rebased[col].iloc[0]
                sub_rebased[col] = (sub_rebased[col] / start - 1) * 100
        for col in ["spreads", "trend", "rotation", "straddles", "chain"]:
            if col in sub_rebased.columns:
                ax.plot(sub_rebased.index, sub_rebased[col], label=col, alpha=0.85, linewidth=1.2)
        # total as percent of starting total
        total_start = sub["total"].iloc[0]
        ax.plot(sub.index, (sub["total"] / total_start - 1) * 100,
                label="TOTAL", color="black", linewidth=2.5)
        ax.axhline(0, color="gray", linestyle="--", linewidth=0.8)
        ax.set_title(f"{year} — return % from year start")
        ax.set_ylabel("% return")
        ax.legend(loc="best", fontsize=8)
        plt_idx += 1
    plt.tight_layout()
    out1 = OUT_DIR / "yearly_equity_curves.png"
    plt.savefig(out1, dpi=110, bbox_inches="tight")
    print(f"  saved: {out1}")
    plt.close()

    # Figure 2: YoY return bar chart per sleeve
    metrics = yearly_metrics_table(sleeves)
    if not metrics.empty:
        pivot = metrics.pivot(index="year", columns="sleeve", values="return_pct")
        cols = ["spreads", "trend", "rotation", "straddles", "chain", "total"]
        pivot = pivot[[c for c in cols if c in pivot.columns]]
        fig, ax = plt.subplots(figsize=(13, 6))
        pivot.plot(kind="bar", ax=ax, width=0.85)
        ax.set_title("YoY % return per sleeve + total portfolio")
        ax.set_ylabel("Return %")
        ax.set_xlabel("Year")
        ax.axhline(0, color="black", linewidth=0.8)
        ax.legend(loc="best", fontsize=9)
        plt.xticks(rotation=0)
        plt.tight_layout()
        out2 = OUT_DIR / "yoy_returns_bar.png"
        plt.savefig(out2, dpi=110, bbox_inches="tight")
        print(f"  saved: {out2}")
        plt.close()

    # Figure 3: cumulative equity over the full window
    fig, ax = plt.subplots(figsize=(13, 6))
    for col in ["spreads", "trend", "rotation", "straddles", "chain"]:
        if col in sleeves.columns:
            ax.plot(sleeves.index, sleeves[col], label=col, alpha=0.85, linewidth=1.2)
    ax.plot(sleeves.index, sleeves["total"], label="TOTAL", color="black", linewidth=2.5)
    for year in YEARS:
        ax.axvline(pd.Timestamp(year=year, month=1, day=1), color="gray",
                   linestyle="--", linewidth=0.5, alpha=0.5)
    ax.set_title("Full-period sleeve equity (initial sleeve allocation = baseline)")
    ax.set_ylabel("Sleeve $")
    ax.legend(loc="best")
    plt.tight_layout()
    out3 = OUT_DIR / "full_period_equity.png"
    plt.savefig(out3, dpi=110, bbox_inches="tight")
    print(f"  saved: {out3}")
    plt.close()


if __name__ == "__main__":
    sleeves = run_full_backtest()
    sleeves.to_parquet(OUT_DIR.parent / "yearly_sleeves_equity.parquet")
    print(f"\nSaved: {OUT_DIR.parent / 'yearly_sleeves_equity.parquet'}")

    metrics = yearly_metrics_table(sleeves)
    metrics.to_csv(OUT_DIR.parent / "yearly_sleeves_metrics.csv", index=False)
    print(f"Saved: {OUT_DIR.parent / 'yearly_sleeves_metrics.csv'}")

    print("\n=== YEARLY METRICS ===")
    from tabulate import tabulate
    print(tabulate(metrics, headers="keys", tablefmt="simple", showindex=False))

    print("\nGenerating plots...")
    make_plots(sleeves)
    print("\nDone.")
