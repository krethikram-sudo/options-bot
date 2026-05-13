"""Loader for the research dataset built by `research/build_dataset.py`.

Use these helpers in any backtest or analysis script — keeps load logic in one
place so strategy code stays focused.

Examples:
    from research.data_lib import load_closes, load_ticker, category

    closes = load_closes()                   # DataFrame: dates × all tickers
    nvda   = load_ticker("NVDA")             # DataFrame: OHLCV for NVDA
    semis  = closes[category("semi_equipment") + category("foundries")]
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path

import pandas as pd

DATA_DIR = Path(__file__).resolve().parent / "data"
PER_TICKER_DIR = DATA_DIR / "tickers"


@lru_cache(maxsize=1)
def metadata() -> dict:
    with (DATA_DIR / "metadata.json").open() as f:
        return json.load(f)


@lru_cache(maxsize=1)
def all_tickers() -> list[str]:
    return list(metadata()["tickers"])


def category(name: str) -> list[str]:
    """Return tickers in a single category, e.g. 'core_ai_infra' or 'semi_equipment'."""
    return list(metadata()["universe_categories"].get(name, []))


def categories_for(ticker: str) -> list[str]:
    return list(metadata()["category_by_ticker"].get(ticker, []))


def list_categories() -> list[str]:
    return list(metadata()["universe_categories"].keys())


@lru_cache(maxsize=1)
def load_closes() -> pd.DataFrame:
    """Wide DataFrame: index=date, columns=ticker, values=adjusted close."""
    df = pd.read_parquet(DATA_DIR / "closes.parquet")
    df.index = pd.to_datetime(df.index)
    return df


@lru_cache(maxsize=1)
def load_returns() -> pd.DataFrame:
    df = pd.read_parquet(DATA_DIR / "returns.parquet")
    df.index = pd.to_datetime(df.index)
    return df


@lru_cache(maxsize=1)
def load_long() -> pd.DataFrame:
    """Long format: MultiIndex (date, ticker), columns=OHLCV."""
    df = pd.read_parquet(DATA_DIR / "ohlcv_long.parquet")
    return df


def load_ticker(ticker: str) -> pd.DataFrame:
    """Daily OHLCV for one ticker."""
    safe = ticker.replace("^", "_idx_")
    p = PER_TICKER_DIR / f"{safe}.parquet"
    if not p.exists():
        raise FileNotFoundError(f"No parquet for {ticker} (expected {p})")
    df = pd.read_parquet(p)
    df.index = pd.to_datetime(df.index)
    return df


def load_tickers(tickers: list[str]) -> dict[str, pd.DataFrame]:
    """Bulk-load OHLCV per ticker. Returns dict ticker -> DataFrame."""
    return {t: load_ticker(t) for t in tickers if (PER_TICKER_DIR / f"{t.replace('^','_idx_')}.parquet").exists()}


def correlation_matrix(tickers: list[str] | None = None, period: int | None = None) -> pd.DataFrame:
    """Pearson correlation of daily returns. `period` = last N trading days, or None for full."""
    rets = load_returns()
    if tickers is not None:
        rets = rets[[t for t in tickers if t in rets.columns]]
    if period is not None:
        rets = rets.tail(period)
    return rets.corr()


def universe_stats() -> pd.DataFrame:
    """Per-ticker summary stats: cagr, vol, sharpe, max_dd."""
    import math

    closes = load_closes()
    out = []
    for t in closes.columns:
        s = closes[t].dropna()
        if len(s) < 30:
            continue
        years = (s.index[-1] - s.index[0]).days / 365.25
        cagr = (s.iloc[-1] / s.iloc[0]) ** (1 / years) - 1 if years > 0 else 0
        ret = s.pct_change().dropna()
        vol = ret.std() * math.sqrt(252)
        sharpe = (cagr - 0.04) / vol if vol > 0 else 0
        running_max = s.cummax()
        max_dd = ((s - running_max) / running_max).min()
        out.append({
            "ticker": t, "cagr": cagr, "vol": vol, "sharpe": sharpe,
            "max_dd": max_dd, "days": len(s),
            "categories": ",".join(categories_for(t)),
        })
    return pd.DataFrame(out).set_index("ticker").sort_values("cagr", ascending=False)


def summary() -> None:
    """Print a human-readable summary of what's in the dataset."""
    m = metadata()
    print(f"Dataset built: {m['built_at']}")
    print(f"Date range  : {m['start_date']} → {m['end_date']}")
    print(f"Tickers     : {m['n_tickers']}")
    print(f"Failures    : {m.get('failures', [])}")
    print(f"Categories  : {len(m['universe_categories'])}")
    for cat, tks in m["universe_categories"].items():
        present = [t for t in tks if t in m["tickers"]]
        print(f"  {cat:<22} {len(present):>3} tickers")


if __name__ == "__main__":
    summary()
    print("\nTop 10 by CAGR:")
    stats = universe_stats()
    print(stats.head(10).to_string())
