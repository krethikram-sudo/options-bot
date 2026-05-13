"""Build a clean 2-year backtest dataset for strategy R&D.

Fully isolated from the live trading bot. Outputs parquet files under
research/data/ that are fast to load and easy to slice.

Usage:
    cd ~/options-bot
    ./venv/bin/python research/build_dataset.py

Re-run any time to refresh. Existing files are overwritten.
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
PER_TICKER_DIR = DATA_DIR / "tickers"

# Universe by category — each ticker tagged with the layer/role it plays
UNIVERSE = {
    # === Existing live bot universe ===
    "core_ai_infra": ["NVDA", "AMD", "AVGO", "SNDK", "MU", "TSM", "MRVL", "ARM", "SMCI"],

    # === Layer 1: Materials & semi equipment ===
    "semi_equipment": ["ASML", "AMAT", "LRCX", "KLAC", "TER", "ENTG", "ONTO", "MKSI"],

    # === Layer 2: Foundries / manufacturers ===
    "foundries": ["INTC", "GFS", "UMC"],

    # === Layer 3: Other silicon / chips ===
    "other_silicon": ["QCOM", "TXN", "ADI", "ON", "MCHP", "NXPI", "WOLF", "MPWR"],

    # === Layer 4: Networking, optical, storage ===
    "networking_optical": ["ANET", "CSCO", "JNPR", "CIEN", "LITE", "CRDO", "COHR"],
    "storage": ["WDC", "STX", "NTAP", "PSTG"],

    # === Layer 5: Servers, power, cooling ===
    "servers_power": ["DELL", "HPE", "VRT", "ETN", "GEV", "HUBB", "PWR"],

    # === Layer 6: Cloud / hyperscalers ===
    "hyperscalers": ["AMZN", "MSFT", "GOOGL", "GOOG", "META", "ORCL", "IBM", "CRWV"],

    # === Layer 7-8: AI software, applications ===
    "ai_software": ["PLTR", "SNOW", "DDOG", "MDB", "ESTC", "AI", "AMZN"],  # AMZN dup intentionally absorbed
    "ai_saas": ["CRM", "NOW", "ADBE", "INTU", "WDAY", "HUBS"],

    # === Layer 9: Cybersecurity ===
    "cybersecurity": ["CRWD", "PANW", "ZS", "FTNT", "S", "CYBR", "RBRK", "NET"],

    # === Layer 10: Vertical AI ===
    "vertical_ai": ["ISRG", "TEM", "VEEV", "SYM"],

    # === Layer 11: Power utilities + data center REITs ===
    "power_utilities": ["CEG", "VST", "NEE"],
    "data_center_reits": ["DLR", "EQIX", "IRM"],

    # === Layer 12: Quantum (speculative) ===
    "quantum": ["IONQ", "RGTI", "QBTS"],

    # === Benchmarks ===
    "benchmarks": ["SPY", "QQQ", "IWM", "DIA"],

    # === Factor ETFs ===
    "factor_etfs": ["MTUM", "VLUE", "QUAL", "USMV", "SIZE"],

    # === Sector ETFs ===
    "sector_etfs": ["SOXX", "SMH", "XLK", "XLF", "XLE", "XLV", "XLY", "XLP", "XLU", "XLI", "XLRE"],

    # === Volatility ===
    "volatility": ["VXX", "UVXY"],

    # === Bonds ===
    "bonds": ["TLT", "IEF", "AGG", "HYG", "LQD", "TIP"],

    # === Commodities / safe haven ===
    "commodities": ["GLD", "SLV", "USO", "DBC", "UNG"],

    # === Currencies / dollar ===
    "currencies": ["UUP", "FXE", "FXY"],

    # === Indexes (for VIX etc.) ===
    "indexes": ["^VIX", "^VIX9D", "^VIX3M", "^VIX6M", "^TNX", "^TYX", "^IRX", "^GSPC", "^NDX", "^DJI"],

    # === Macro proxies / defense / safe-haven equities ===
    "defense": ["LMT", "RTX", "NOC", "GD", "BA"],

    # === Robotics / automation ===
    "robotics": ["ABB", "ROK", "EMR"],
}


def _flat_universe() -> list[str]:
    seen = []
    out = []
    for cat, tickers in UNIVERSE.items():
        for t in tickers:
            if t not in seen:
                seen.append(t)
                out.append(t)
    return out


def _category_lookup() -> dict[str, list[str]]:
    """Reverse: ticker -> list of categories it belongs to."""
    out: dict[str, list[str]] = {}
    for cat, tickers in UNIVERSE.items():
        for t in tickers:
            out.setdefault(t, []).append(cat)
    return out


def fetch_daily(ticker: str, start: str, retries: int = 2) -> pd.DataFrame:
    """Fetch daily OHLCV via yfinance with adjusted prices."""
    last_err: Exception | None = None
    for attempt in range(retries + 1):
        try:
            df = yf.download(
                ticker, start=start, interval="1d",
                auto_adjust=True, progress=False, threads=False,
            )
            if df.empty:
                return df
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df.columns = [c.lower() for c in df.columns]
            df.index = pd.to_datetime(df.index).tz_localize(None)
            df.index.name = "date"
            # ensure standard columns
            keep = [c for c in ("open", "high", "low", "close", "volume") if c in df.columns]
            return df[keep]
        except Exception as e:
            last_err = e
            time.sleep(0.5 + attempt * 0.5)
    print(f"  ! {ticker}: failed after {retries+1} attempts — {last_err}")
    return pd.DataFrame()


def build_combined_long(per_ticker: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Stack into long format: (date, ticker) MultiIndex, cols=OHLCV."""
    frames = []
    for t, df in per_ticker.items():
        if df.empty:
            continue
        x = df.copy()
        x["ticker"] = t
        x = x.reset_index().set_index(["date", "ticker"])
        frames.append(x)
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames).sort_index()


def build_close_matrix(per_ticker: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Wide format: index=date, columns=ticker, values=adjusted close."""
    closes = {t: df["close"] for t, df in per_ticker.items() if not df.empty and "close" in df.columns}
    if not closes:
        return pd.DataFrame()
    return pd.DataFrame(closes)


def build_returns_matrix(close_df: pd.DataFrame) -> pd.DataFrame:
    return close_df.pct_change().dropna(how="all")


def main() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PER_TICKER_DIR.mkdir(parents=True, exist_ok=True)

    tickers = _flat_universe()
    cat_lookup = _category_lookup()
    print(f"Universe: {len(tickers)} unique tickers across {len(UNIVERSE)} categories")
    print()

    # 2 years + a small buffer for indicator warmup
    end = datetime.now(timezone.utc).date()
    start = (end - timedelta(days=int(2 * 365.25 + 60))).isoformat()
    print(f"Date range: {start} to today")
    print()

    per_ticker: dict[str, pd.DataFrame] = {}
    failures: list[str] = []

    for i, t in enumerate(tickers, 1):
        print(f"  [{i:>3}/{len(tickers)}] {t} ", end="", flush=True)
        df = fetch_daily(t, start)
        if df.empty:
            print(f"NO DATA")
            failures.append(t)
            continue
        per_ticker[t] = df
        # Save per-ticker parquet
        out = PER_TICKER_DIR / f"{t.replace('^', '_idx_')}.parquet"
        df.to_parquet(out)
        print(f"{len(df)} rows  [{df.index.min().date()} → {df.index.max().date()}]")

    print()
    print(f"Successfully fetched: {len(per_ticker)} / {len(tickers)} tickers")
    if failures:
        print(f"Failures: {failures}")

    # Combined wide-format closes (most useful for cross-ticker analysis)
    close_df = build_close_matrix(per_ticker)
    if not close_df.empty:
        close_df.to_parquet(DATA_DIR / "closes.parquet")
        print(f"Saved closes.parquet: {close_df.shape[0]} dates × {close_df.shape[1]} tickers")

    # Returns matrix
    ret_df = build_returns_matrix(close_df)
    if not ret_df.empty:
        ret_df.to_parquet(DATA_DIR / "returns.parquet")
        print(f"Saved returns.parquet: {ret_df.shape[0]} dates × {ret_df.shape[1]} tickers")

    # Long-format full OHLCV
    long_df = build_combined_long(per_ticker)
    if not long_df.empty:
        long_df.to_parquet(DATA_DIR / "ohlcv_long.parquet")
        print(f"Saved ohlcv_long.parquet: {len(long_df):,} rows")

    # Metadata
    metadata = {
        "built_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "start_date": start,
        "end_date": close_df.index.max().date().isoformat() if not close_df.empty else None,
        "n_tickers": len(per_ticker),
        "tickers": sorted(per_ticker.keys()),
        "failures": failures,
        "universe_categories": UNIVERSE,
        "category_by_ticker": cat_lookup,
    }
    with (DATA_DIR / "metadata.json").open("w") as f:
        json.dump(metadata, f, indent=2)
    print(f"Saved metadata.json")
    print()
    print(f"Dataset ready in {DATA_DIR}")


if __name__ == "__main__":
    main()
