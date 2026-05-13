# Research Dataset & Strategy Lab

Isolated from the live trading bot. Use this directory to backtest strategies on
historical data without touching production.

## What's here

```
research/
├── build_dataset.py       # one-shot fetch from yfinance → parquet
├── data_lib.py            # loader utilities (use this in your code)
├── data/
│   ├── tickers/           # one parquet per ticker (OHLCV, adjusted)
│   ├── closes.parquet     # wide: dates × tickers, adjusted close
│   ├── returns.parquet    # daily pct_change of closes
│   ├── ohlcv_long.parquet # long: (date, ticker) MultiIndex × OHLCV
│   └── metadata.json      # universe map, dates, categories
└── README.md
```

## Universe (138 tickers across 25 categories)

- **core_ai_infra** — the 9 names the live bot trades
- **semi_equipment** — ASML, AMAT, LRCX, KLAC, TER, ENTG, ONTO, MKSI
- **foundries** — INTC, GFS, UMC
- **other_silicon** — QCOM, TXN, ADI, ON, MCHP, NXPI, MPWR, WOLF
- **networking_optical** — ANET, CSCO, CIEN, LITE, CRDO, COHR (+ JNPR delisted)
- **storage** — WDC, STX, NTAP, PSTG
- **servers_power** — DELL, HPE, VRT, ETN, GEV, HUBB, PWR
- **hyperscalers** — AMZN, MSFT, GOOGL, GOOG, META, ORCL, IBM, CRWV
- **ai_software** — PLTR, SNOW, DDOG, MDB, ESTC, AI
- **ai_saas** — CRM, NOW, ADBE, INTU, WDAY, HUBS
- **cybersecurity** — CRWD, PANW, ZS, FTNT, S, RBRK, NET (+ CYBR delisted)
- **vertical_ai** — ISRG, TEM, VEEV, SYM
- **power_utilities** — CEG, VST, NEE
- **data_center_reits** — DLR, EQIX, IRM
- **quantum** — IONQ, RGTI, QBTS
- **benchmarks** — SPY, QQQ, IWM, DIA
- **factor_etfs** — MTUM, VLUE, QUAL, USMV, SIZE
- **sector_etfs** — SOXX, SMH, XLK, XLF, XLE, XLV, XLY, XLP, XLU, XLI, XLRE
- **volatility** — VXX, UVXY (+ ^VIX, ^VIX9D, ^VIX3M, ^VIX6M as indexes)
- **bonds** — TLT, IEF, AGG, HYG, LQD, TIP
- **commodities** — GLD, SLV, USO, DBC, UNG
- **currencies** — UUP, FXE, FXY
- **indexes** — ^VIX (and term structure), ^TNX/^TYX/^IRX (Treasury yields), ^GSPC/^NDX/^DJI
- **defense** — LMT, RTX, NOC, GD, BA
- **robotics** — ROK, EMR (+ ABB delisted on yfinance)

Failures: JNPR (acquired by HPE, July 2025), CYBR (acquired by PANW), ABB (OTC ticker not on yfinance).

## Date range

**2024-03-04 → 2026-05-01** (543 trading days). Some tickers shorter:
- ARM IPO Sep 2023 — full window
- SNDK spinoff Feb 2025 — partial
- CRWV IPO Mar 2025 — partial
- WOLF post-bankruptcy Sep 2025 — partial
- TEM IPO Jun 2024 — partial
- GEV spinoff Mar 2024 — full window

## Refreshing the data

```bash
cd ~/options-bot
./venv/bin/python research/build_dataset.py
```

Re-run any time. Pulls 2 years + 60 days of buffer so indicator warmups are safe.

## Quick usage

```python
from research.data_lib import (
    load_closes, load_returns, load_ticker, category,
    correlation_matrix, universe_stats, summary,
)

# Print what's in the dataset
summary()

# Load all closes (dates × tickers wide)
closes = load_closes()

# Load returns
rets = load_returns()

# Single ticker OHLCV
nvda = load_ticker("NVDA")  # cols: open, high, low, close, volume

# Get tickers in a category
power = category("servers_power") + category("power_utilities")
power_closes = closes[power]

# Correlation matrix on a subset
corr = correlation_matrix(category("core_ai_infra"), period=126)  # last 6 months

# Per-ticker performance stats
stats = universe_stats()
```

## Designing a backtest using this dataset

The dataset is intentionally **independent of the live bot**. Pattern:

```python
# strategies/my_idea.py
from research.data_lib import load_closes, load_ticker, category

def backtest_my_strategy(start="2024-06-01", end="2026-04-30"):
    closes = load_closes().loc[start:end]
    universe = category("core_ai_infra") + category("semi_equipment")
    px = closes[universe]

    # ... your strategy logic ...

    return trades, equity_curve

if __name__ == "__main__":
    trades, equity = backtest_my_strategy()
    print(equity.iloc[-1])
```

Once a backtest meets your criteria (positive expectancy, robust to parameter
sweeps, sensible drawdown), then we discuss whether to wire it into the live
bot under a new sleeve allocation. **Nothing in this directory should be
imported by the live bot or its launchd agent.**

## Conventions

- All prices are **dividend- and split-adjusted** (`auto_adjust=True` in yfinance).
- Returns are **daily simple returns** (`pct_change`).
- Index ticker symbols (^VIX etc.) are stored with `^` replaced by `_idx_` in filenames.
- Cached parquet files; loaders use `lru_cache` so repeated calls are free.

## What's NOT in here (yet)

- Intraday bars (the live bot has Alpaca for this; could add for backtesting)
- Options chain history (not freely available)
- Earnings dates / fundamentals (yfinance has earnings_dates; could add a snapshot)
- Macro time series outside of ^TNX/^TYX/^IRX (could pull FRED data)
- News sentiment (the live bot has its own ntfy + Alpaca News pipeline)

Easy adds if needed.
