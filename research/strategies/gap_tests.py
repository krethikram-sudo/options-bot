"""All five gap tests in one consolidated module.

Loads from research/data_extended/ (6+ years of data) so we can test bear
behavior. Each function tests one gap and prints a summary table.
"""
from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
from tabulate import tabulate

ROOT = Path(__file__).resolve().parent.parent
EXT_DIR = ROOT / "data_extended"


# ---------- data loaders ----------

def load_ext_closes() -> pd.DataFrame:
    df = pd.read_parquet(EXT_DIR / "closes.parquet")
    df.index = pd.to_datetime(df.index)
    return df


def load_ext_returns() -> pd.DataFrame:
    df = pd.read_parquet(EXT_DIR / "returns.parquet")
    df.index = pd.to_datetime(df.index)
    return df


def metadata():
    import json
    with (EXT_DIR / "metadata.json").open() as f:
        return json.load(f)


def category(name: str) -> list[str]:
    m = metadata()
    return m["universe_categories"].get(name, [])


def ai9() -> list[str]:
    return category("core_ai_infra")


def ai_full_chain() -> list[str]:
    cats = ["core_ai_infra", "semi_equipment", "foundries", "other_silicon",
            "networking_optical", "storage", "servers_power", "hyperscalers"]
    out = []
    for c in cats:
        for t in category(c):
            if t not in out:
                out.append(t)
    closes = load_ext_closes()
    return [t for t in out if t in closes.columns]


# ---------- shared metrics ----------

def metrics(equity: pd.Series, rf: float = 0.04) -> dict:
    if len(equity) < 2:
        return {}
    rets = equity.pct_change().dropna()
    years = (equity.index[-1] - equity.index[0]).days / 365.25
    cagr = (equity.iloc[-1] / equity.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
    vol = rets.std() * math.sqrt(252)
    sharpe = (cagr - rf) / vol if vol > 0 else 0
    running = equity.cummax()
    max_dd = float((equity - running).div(running).min())
    return {"cagr": cagr, "vol": vol, "sharpe": sharpe, "max_dd": max_dd,
            "total_return": equity.iloc[-1] / equity.iloc[0] - 1, "years": years}


def yearly_metrics(equity: pd.Series) -> dict[int, dict]:
    out = {}
    for year in sorted(set(equity.index.year)):
        sub = equity[equity.index.year == year]
        if len(sub) < 5:
            continue
        rets = sub.pct_change().dropna()
        if len(rets) == 0:
            continue
        total_ret = sub.iloc[-1] / sub.iloc[0] - 1
        vol = rets.std() * math.sqrt(252)
        out[year] = {
            "total_ret": float(total_ret),
            "vol": float(vol),
            "sharpe": float(total_ret / vol) if vol > 0 else 0,
            "max_dd": float((sub - sub.cummax()).div(sub.cummax()).min()),
        }
    return out


# ---------- portfolio simulation ----------

def simulate_weights(weights: pd.DataFrame, closes: pd.DataFrame,
                     initial: float = 100_000, cost_bps: float = 5.0) -> pd.Series:
    """Simulate portfolio with daily weights forward-applied to next-day returns."""
    common = weights.index.intersection(closes.index)
    weights = weights.loc[common]
    closes = closes.loc[common]
    rets = closes.pct_change().fillna(0)
    # daily returns of portfolio = weighted avg of constituent returns (using yesterday's weights)
    port_rets = (weights.shift(1) * rets).sum(axis=1).fillna(0)
    # transaction costs: turnover at each rebalance
    turnover = weights.diff().abs().sum(axis=1).fillna(0)
    cost = turnover * (cost_bps / 10_000)
    port_rets = port_rets - cost
    return (1 + port_rets).cumprod() * initial


def make_rebalance_dates(dates: pd.DatetimeIndex, freq: str = "monthly") -> pd.DatetimeIndex:
    if freq == "daily":
        return dates
    if freq == "weekly":
        return pd.DatetimeIndex([d for i, d in enumerate(dates)
                                  if i == 0 or d.weekday() < dates[i-1].weekday()])
    if freq == "monthly":
        return pd.DatetimeIndex([d for i, d in enumerate(dates)
                                  if i == 0 or d.month != dates[i-1].month])
    if freq == "quarterly":
        return pd.DatetimeIndex([d for i, d in enumerate(dates)
                                  if i == 0 or (d.month - 1) // 3 != (dates[i-1].month - 1) // 3])
    raise ValueError(f"unknown freq: {freq}")


def equal_weight_strategy(universe: list[str], closes: pd.DataFrame,
                          rebalance: str = "monthly") -> pd.Series:
    px = closes[universe].dropna(how="any")
    if px.empty:
        return pd.Series(dtype=float)
    rdates = make_rebalance_dates(px.index, rebalance)
    rdates_set = set(rdates)
    weights = pd.DataFrame(0.0, index=px.index, columns=universe)
    cur_w = pd.Series(1.0 / len(universe), index=universe)
    for d in px.index:
        if d in rdates_set:
            cur_w = pd.Series(1.0 / len(universe), index=universe)
        weights.loc[d] = cur_w
    return simulate_weights(weights, closes[universe].loc[px.index])


# ============================================================
# GAP 1: BEAR-MARKET TEST
# ============================================================

def gap1_bear_market_test():
    print("\n" + "=" * 70)
    print("GAP 1 — BEAR-MARKET BEHAVIOR (2020-2026)")
    print("=" * 70)
    closes = load_ext_closes()

    # Build top equity strategies on the extended dataset
    strategies = {}
    # 1. EW AI-9 (core 9 names that have full history)
    ai9_names = [t for t in ai9() if t in closes.columns]
    # NB: ARM (IPO Sep 2023) and SNDK (Feb 2025) won't have full history
    # Use AI-9 with whatever data exists per name
    full_history_ai9 = [t for t in ai9_names if t not in ("ARM", "SNDK")]
    strategies["EW_AI7_full_history"] = equal_weight_strategy(full_history_ai9, closes)
    strategies["EW_full_chain"] = equal_weight_strategy(ai_full_chain(), closes)

    # benchmarks
    spy = closes["SPY"].dropna()
    strategies["BH_SPY"] = spy / spy.iloc[0] * 100_000
    qqq = closes["QQQ"].dropna()
    strategies["BH_QQQ"] = qqq / qqq.iloc[0] * 100_000
    tlt = closes["TLT"].dropna()
    strategies["BH_TLT"] = tlt / tlt.iloc[0] * 100_000

    # 60/40
    spy_r = spy.pct_change().fillna(0)
    tlt_r = tlt.pct_change().fillna(0)
    common = spy_r.index.intersection(tlt_r.index)
    sixty40_r = 0.6 * spy_r.loc[common] + 0.4 * tlt_r.loc[common]
    strategies["60_40"] = (1 + sixty40_r).cumprod() * 100_000

    # Print yearly returns table
    rows = []
    for name, eq in strategies.items():
        if eq.empty:
            continue
        m = metrics(eq)
        ym = yearly_metrics(eq)
        row = {"strategy": name, "cagr_full": round(m["cagr"] * 100, 1),
               "sharpe_full": round(m["sharpe"], 2),
               "max_dd": round(m["max_dd"] * 100, 1)}
        for year in [2020, 2021, 2022, 2023, 2024, 2025]:
            if year in ym:
                row[f"y{year}"] = round(ym[year]["total_ret"] * 100, 1)
            else:
                row[f"y{year}"] = None
        rows.append(row)
    df = pd.DataFrame(rows)
    print(tabulate(df, headers="keys", tablefmt="simple", showindex=False))

    # Highlight 2022 specifically
    print("\nFocus: 2022 (rate-shock bear)")
    for r in rows:
        y2022 = r.get("y2022")
        if y2022 is not None:
            verdict = "✓ ok" if y2022 > -10 else "✗ deep loss" if y2022 < -25 else "⚠ moderate"
            print(f"  {r['strategy']:<25} 2022: {y2022:+.1f}%  {verdict}")

    df.to_csv(ROOT / "strategies" / "gap1_bear_test_results.csv", index=False)
    return df


# ============================================================
# GAP 2: POSITION-SIZING SCHEMES
# ============================================================

def position_sizing_strategy(method: str, universe: list[str], closes: pd.DataFrame,
                              rebalance: str = "monthly", lookback: int = 60) -> pd.Series:
    px = closes[universe].dropna(how="any")
    if px.empty or len(px) < lookback + 5:
        return pd.Series(dtype=float)
    rets = px.pct_change()
    rdates = make_rebalance_dates(px.index, rebalance)
    rdates_set = set(rdates)
    weights = pd.DataFrame(0.0, index=px.index, columns=universe)
    cur_w = pd.Series(1.0 / len(universe), index=universe)

    for d in px.index:
        if d in rdates_set:
            past_rets = rets.loc[:d].tail(lookback)
            if len(past_rets) < lookback // 2:
                cur_w = pd.Series(1.0 / len(universe), index=universe)
            elif method == "equal":
                cur_w = pd.Series(1.0 / len(universe), index=universe)
            elif method == "inv_vol":
                vols = past_rets.std() * math.sqrt(252)
                inv = 1.0 / vols.replace(0, np.nan)
                cur_w = (inv / inv.sum()).fillna(0)
            elif method == "kelly":
                # half-Kelly approximation: weight ∝ mean / variance
                mu = past_rets.mean() * 252
                var = (past_rets.std() ** 2) * 252
                kelly = mu / var.replace(0, np.nan)
                kelly_clipped = kelly.clip(lower=0)  # long-only
                if kelly_clipped.sum() > 0:
                    cur_w = (kelly_clipped / kelly_clipped.sum()).fillna(0)
                else:
                    cur_w = pd.Series(1.0 / len(universe), index=universe)
            elif method == "risk_parity":
                # ERC approximation via inverse-vol normalized to equal RC
                # True ERC requires solving a system; this is the inv-vol shortcut
                # which is the same as inv_vol when correlations are similar
                vols = past_rets.std() * math.sqrt(252)
                inv = 1.0 / vols.replace(0, np.nan)
                cur_w = (inv / inv.sum()).fillna(0)
            elif method == "min_var":
                # naive min-variance via inverse covariance row sums
                try:
                    cov = past_rets.cov() * 252
                    if cov.shape[0] != cov.shape[1] or cov.isna().any().any():
                        cur_w = pd.Series(1.0 / len(universe), index=universe)
                    else:
                        inv_cov = np.linalg.pinv(cov.values)
                        ones = np.ones(len(universe))
                        w = inv_cov @ ones
                        w = np.maximum(w, 0)  # long-only
                        if w.sum() > 0:
                            w = w / w.sum()
                        else:
                            w = ones / len(universe)
                        cur_w = pd.Series(w, index=universe)
                except Exception:
                    cur_w = pd.Series(1.0 / len(universe), index=universe)
            elif method == "hrp":
                # Hierarchical Risk Parity: cluster + recursive bisection on inv-vol
                cur_w = _hrp_weights(past_rets, universe)
            else:
                cur_w = pd.Series(1.0 / len(universe), index=universe)
        weights.loc[d] = cur_w
    return simulate_weights(weights, closes[universe].loc[px.index])


def _hrp_weights(returns: pd.DataFrame, universe: list[str]) -> pd.Series:
    """Hierarchical Risk Parity: cluster correlation matrix, bisect into sub-portfolios."""
    if returns.empty or len(returns) < 10:
        return pd.Series(1.0 / len(universe), index=universe)
    try:
        from scipy.cluster.hierarchy import linkage, leaves_list
        from scipy.spatial.distance import squareform
        corr = returns.corr()
        if corr.isna().any().any():
            return pd.Series(1.0 / len(universe), index=universe)
        dist = np.sqrt(0.5 * (1 - corr))
        link = linkage(squareform(dist.fillna(0).values, checks=False), method="single")
        order_idx = leaves_list(link)
        ordered = [returns.columns[i] for i in order_idx]
        # recursive bisection
        cov = returns.cov()
        weights = pd.Series(1.0, index=ordered)
        clusters = [ordered]
        while clusters:
            new_clusters = []
            for cluster in clusters:
                if len(cluster) <= 1:
                    continue
                mid = len(cluster) // 2
                left = cluster[:mid]
                right = cluster[mid:]
                # compute variances for each sub-cluster (inv-vol weighted)
                def cluster_var(sub):
                    sub_cov = cov.loc[sub, sub]
                    inv_vol = 1.0 / np.sqrt(np.diag(sub_cov))
                    if inv_vol.sum() == 0:
                        return 0
                    w = inv_vol / inv_vol.sum()
                    return w @ sub_cov.values @ w
                vL = cluster_var(left); vR = cluster_var(right)
                if vL + vR == 0:
                    aL, aR = 0.5, 0.5
                else:
                    aL = 1 - vL / (vL + vR)
                    aR = 1 - aL
                weights.loc[left] *= aL
                weights.loc[right] *= aR
                new_clusters.extend([left, right])
            clusters = new_clusters
        out = pd.Series(0.0, index=universe)
        out.loc[weights.index] = weights.values
        if out.sum() > 0:
            out = out / out.sum()
        return out
    except Exception:
        return pd.Series(1.0 / len(universe), index=universe)


def gap2_position_sizing():
    print("\n" + "=" * 70)
    print("GAP 2 — POSITION-SIZING SCHEMES")
    print("=" * 70)
    closes = load_ext_closes()
    universe = ai_full_chain()
    methods = ["equal", "inv_vol", "kelly", "min_var", "hrp"]

    rows = []
    for method in methods:
        eq = position_sizing_strategy(method, universe, closes, rebalance="monthly")
        if eq.empty:
            continue
        m = metrics(eq)
        ym = yearly_metrics(eq)
        row = {"method": method,
               "cagr": round(m["cagr"] * 100, 1),
               "sharpe": round(m["sharpe"], 2),
               "max_dd": round(m["max_dd"] * 100, 1),
               "vol": round(m["vol"] * 100, 1),
               "y2022": round(ym.get(2022, {"total_ret": 0})["total_ret"] * 100, 1) if 2022 in ym else None,
               "y2025": round(ym.get(2025, {"total_ret": 0})["total_ret"] * 100, 1) if 2025 in ym else None,
               }
        rows.append(row)
    df = pd.DataFrame(rows)
    df = df.sort_values("sharpe", ascending=False)
    print(tabulate(df, headers="keys", tablefmt="simple", showindex=False))
    df.to_csv(ROOT / "strategies" / "gap2_sizing_results.csv", index=False)
    return df


# ============================================================
# GAP 3: SENTIMENT PROXY (price-based)
# ============================================================

def sentiment_proxy_strategy(closes: pd.DataFrame, universe: list[str]) -> pd.Series:
    """Price-based sentiment: combine RSI, volume z-score, gap behavior into score.
    Buy positions only when broad-market sentiment proxy is bullish."""
    px = closes[universe].dropna(how="any")
    if px.empty:
        return pd.Series(dtype=float)
    rets = px.pct_change()

    # SPY sentiment proxy: 5-day return + RSI
    spy = closes["SPY"]
    spy_5d = spy.pct_change(5)
    # simple RSI
    delta = spy.diff()
    gain = delta.clip(lower=0).ewm(alpha=1/14).mean()
    loss = -delta.clip(upper=0).ewm(alpha=1/14).mean()
    rs = gain / loss.replace(0, 1e-10)
    spy_rsi = 100 - 100 / (1 + rs)

    # bullish sentiment: SPY 5d ret > 0 AND RSI > 50 (uptrend confirmed)
    bullish = (spy_5d > 0) & (spy_rsi > 50)

    rdates = make_rebalance_dates(px.index, "weekly")
    rdates_set = set(rdates)
    weights = pd.DataFrame(0.0, index=px.index, columns=universe)
    cur_w = pd.Series(1.0 / len(universe), index=universe)
    for d in px.index:
        if d in rdates_set:
            if d in bullish.index and bool(bullish.loc[d]):
                cur_w = pd.Series(1.0 / len(universe), index=universe)
            else:
                cur_w = pd.Series(0.0, index=universe)  # cash
        weights.loc[d] = cur_w
    return simulate_weights(weights, closes[universe].loc[px.index])


def gap3_sentiment_proxy():
    print("\n" + "=" * 70)
    print("GAP 3 — SENTIMENT PROXY (price-based, since free historical news limited)")
    print("=" * 70)
    closes = load_ext_closes()
    universe = ai_full_chain()
    eq_sentiment = sentiment_proxy_strategy(closes, universe)
    eq_baseline = equal_weight_strategy(universe, closes, rebalance="weekly")

    rows = []
    for name, eq in [("baseline_EW", eq_baseline), ("sentiment_gated", eq_sentiment)]:
        if eq.empty:
            continue
        m = metrics(eq)
        ym = yearly_metrics(eq)
        row = {"strategy": name,
               "cagr": round(m["cagr"] * 100, 1),
               "sharpe": round(m["sharpe"], 2),
               "max_dd": round(m["max_dd"] * 100, 1),
               "y2022": round(ym.get(2022, {"total_ret": 0})["total_ret"] * 100, 1) if 2022 in ym else None,
               "y2025": round(ym.get(2025, {"total_ret": 0})["total_ret"] * 100, 1) if 2025 in ym else None,
               }
        rows.append(row)
    df = pd.DataFrame(rows)
    print(tabulate(df, headers="keys", tablefmt="simple", showindex=False))
    df.to_csv(ROOT / "strategies" / "gap3_sentiment_results.csv", index=False)
    return df


# ============================================================
# GAP 4: REGIME DETECTION + SWITCHING
# ============================================================

def gap4_regime_detection():
    print("\n" + "=" * 70)
    print("GAP 4 — REGIME DETECTION + STRATEGY SWITCHING")
    print("=" * 70)
    closes = load_ext_closes()
    universe = ai_full_chain()

    # Define regimes via SPY 200-SMA + VXX (vol)
    spy = closes["SPY"]
    spy_sma200 = spy.rolling(200).mean()
    in_uptrend = spy > spy_sma200
    vxx = closes.get("VXX")
    if vxx is not None and not vxx.dropna().empty:
        vxx_median = vxx.rolling(60).median()
        low_vol = vxx < vxx_median
    else:
        low_vol = pd.Series(True, index=spy.index)

    # 4 regimes: uptrend+lowvol (best for momentum), uptrend+highvol, downtrend+lowvol, downtrend+highvol
    regime = pd.Series("neutral", index=spy.index)
    regime[in_uptrend & low_vol] = "uptrend_lowvol"
    regime[in_uptrend & ~low_vol] = "uptrend_highvol"
    regime[~in_uptrend & low_vol] = "downtrend_lowvol"
    regime[~in_uptrend & ~low_vol] = "downtrend_highvol"

    # Switching strategy:
    #  uptrend_lowvol → long EW AI infra
    #  uptrend_highvol → long but vol-targeted (50% exposure)
    #  downtrend_lowvol → cash + 30% TLT
    #  downtrend_highvol → all cash + 50% TLT
    px = closes[universe].dropna(how="any")
    rdates = make_rebalance_dates(px.index, "weekly")
    rdates_set = set(rdates)

    # We need TLT in our universe for defensive
    have_tlt = "TLT" in closes.columns
    full_universe = universe + (["TLT"] if have_tlt else [])
    weights = pd.DataFrame(0.0, index=px.index, columns=full_universe)
    n_ai = len(universe)
    for d in px.index:
        if d in rdates_set:
            if d not in regime.index:
                continue
            r = regime.loc[d]
            w = pd.Series(0.0, index=full_universe)
            if r == "uptrend_lowvol":
                w[universe] = 1.0 / n_ai
            elif r == "uptrend_highvol":
                w[universe] = 0.5 / n_ai
            elif r == "downtrend_lowvol" and have_tlt:
                w["TLT"] = 0.3
            elif r == "downtrend_highvol" and have_tlt:
                w["TLT"] = 0.5
            weights.loc[d] = w
        else:
            weights.loc[d] = weights.loc[:d].iloc[-2] if len(weights.loc[:d]) > 1 else pd.Series(0.0, index=full_universe)

    # Forward-fill weights between rebalances
    weights = weights.ffill().fillna(0)

    eq_regime = simulate_weights(weights, closes[full_universe].loc[px.index])
    eq_baseline = equal_weight_strategy(universe, closes, rebalance="weekly")

    rows = []
    for name, eq in [("baseline_EW", eq_baseline), ("regime_switch", eq_regime)]:
        if eq.empty:
            continue
        m = metrics(eq)
        ym = yearly_metrics(eq)
        row = {"strategy": name,
               "cagr": round(m["cagr"] * 100, 1),
               "sharpe": round(m["sharpe"], 2),
               "max_dd": round(m["max_dd"] * 100, 1),
               "y2022": round(ym.get(2022, {"total_ret": 0})["total_ret"] * 100, 1) if 2022 in ym else None,
               "y2025": round(ym.get(2025, {"total_ret": 0})["total_ret"] * 100, 1) if 2025 in ym else None,
               }
        rows.append(row)
    df = pd.DataFrame(rows)
    print(tabulate(df, headers="keys", tablefmt="simple", showindex=False))

    # regime distribution
    print()
    print("Regime distribution (full period):")
    print(regime.value_counts())

    df.to_csv(ROOT / "strategies" / "gap4_regime_results.csv", index=False)
    return df


# ============================================================
# GAP 5: OPTIONS OVERLAY
# ============================================================

def bs_put_price(spot, strike, t_years, rate, iv):
    from scipy.stats import norm
    if t_years <= 0:
        return max(strike - spot, 0)
    d1 = (math.log(spot / strike) + (rate + 0.5 * iv * iv) * t_years) / (iv * math.sqrt(t_years))
    d2 = d1 - iv * math.sqrt(t_years)
    return strike * math.exp(-rate * t_years) * norm.cdf(-d2) - spot * norm.cdf(-d1)


def gap5_options_overlay():
    print("\n" + "=" * 70)
    print("GAP 5 — OPTIONS OVERLAY (bull put credit spreads on basket)")
    print("=" * 70)
    closes = load_ext_closes()
    universe = ai_full_chain()
    universe_short = [t for t in universe if t in closes.columns][:9]  # use top 9 to keep tractable
    # Actually use original AI-9 since they have weekly options chains
    target = [t for t in ["NVDA", "AMD", "AVGO", "MU", "TSM", "MRVL"]
              if t in closes.columns]

    # Baseline: EW basket
    eq_basket = equal_weight_strategy(target, closes, rebalance="monthly")

    # Overlay: each month, sell 16-delta put 30 DTE on each, hold to expiry
    # Simplification: assume IV = 30-day realized vol, monthly expiry
    px = closes[target].dropna(how="any")
    if px.empty:
        print("no data"); return pd.DataFrame()

    rets = px.pct_change()
    realized_vol = rets.rolling(30).std() * math.sqrt(252)

    # For each ticker, monthly: sell put at -16 delta strike, 30-day expiry
    # Strike approximate: spot - 1 SD = spot * (1 - vol*sqrt(30/365))
    monthly_dates = make_rebalance_dates(px.index, "monthly")
    # cumulative premium income
    overlay_pnl = pd.Series(0.0, index=px.index)

    for i, d in enumerate(monthly_dates):
        if d not in px.index:
            continue
        for t in target:
            spot = px[t].loc[d]
            iv = realized_vol[t].loc[d] if pd.notna(realized_vol[t].loc[d]) else 0.5
            if pd.isna(spot) or iv <= 0:
                continue
            iv = min(iv, 1.5)  # cap
            t_years = 30 / 365
            # 1 SD OTM ≈ ~16-delta
            strike = spot * (1 - iv * math.sqrt(t_years))
            credit = bs_put_price(spot, strike, t_years, 0.04, iv)
            # next monthly date
            next_d = monthly_dates[i + 1] if i + 1 < len(monthly_dates) else None
            if next_d is None or next_d not in px.index:
                continue
            spot_at_expiry = px[t].loc[next_d]
            # P&L = credit - max(strike - spot_at_expiry, 0)
            intrinsic = max(strike - spot_at_expiry, 0)
            # apply per-share P&L scaled to overlay's notional vs basket
            # assume overlay sized so each put covers 5% of basket
            pnl_per_share = credit - intrinsic
            # daily mark — for simplicity, distribute P&L linearly between d and next_d
            mask = (px.index >= d) & (px.index <= next_d)
            n_days = mask.sum()
            if n_days > 0:
                overlay_pnl.loc[mask] += (pnl_per_share / spot) / len(target) * 0.05 / n_days
                # 5% of basket allocated to overlay, 1/N per ticker

    # Apply overlay returns to baseline equity
    baseline_rets = eq_basket.pct_change().fillna(0)
    overlay_rets = overlay_pnl.reindex(baseline_rets.index).fillna(0)
    combined_rets = baseline_rets + overlay_rets
    eq_overlay = (1 + combined_rets).cumprod() * 100_000

    rows = []
    for name, eq in [("basket_only", eq_basket), ("basket_plus_credit_spreads", eq_overlay)]:
        if eq.empty:
            continue
        m = metrics(eq)
        ym = yearly_metrics(eq)
        row = {"strategy": name,
               "cagr": round(m["cagr"] * 100, 1),
               "sharpe": round(m["sharpe"], 2),
               "max_dd": round(m["max_dd"] * 100, 1),
               "vol": round(m["vol"] * 100, 1),
               "y2022": round(ym.get(2022, {"total_ret": 0})["total_ret"] * 100, 1) if 2022 in ym else None,
               "y2025": round(ym.get(2025, {"total_ret": 0})["total_ret"] * 100, 1) if 2025 in ym else None,
               }
        rows.append(row)
    df = pd.DataFrame(rows)
    print(tabulate(df, headers="keys", tablefmt="simple", showindex=False))
    df.to_csv(ROOT / "strategies" / "gap5_options_overlay_results.csv", index=False)
    return df


# ============================================================
# RUN ALL
# ============================================================

if __name__ == "__main__":
    g1 = gap1_bear_market_test()
    g2 = gap2_position_sizing()
    g3 = gap3_sentiment_proxy()
    g4 = gap4_regime_detection()
    g5 = gap5_options_overlay()
    print("\nAll five gap tests complete.")
