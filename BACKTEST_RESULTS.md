# Backtest Results

> ⚠️ **These are backtest results, not live trading results.** Backtested
> performance has well-documented selection bias and routinely fails to
> replicate in live markets. See **Limitations** section at the bottom of
> this document before drawing any conclusions.

## Methodology

- **Period studied**: 2024-03-04 → 2026-05-01 (543 trading days, ~2.2 years)
- **Universe**: 138 tickers spanning the full AI value chain
  (semis, semi equipment, foundries, networking, optical, storage, servers,
  power, hyperscalers, software) + benchmarks + factor ETFs
- **Strategies tested**: 130 unique variants across 9 sequential phases
- **Engine**: vectorized daily-bar backtests, equal-weight unless specified,
  monthly rebalance, 5-basis-point round-trip transaction cost assumption
- **Data**: yfinance daily OHLCV (with documented survivorship-bias caveat)

The full per-iteration log is in `research/strategies/iter_results.csv` and
`research/strategies/iter_log.jsonl`. The methodology is in
`research/strategies/framework.py` and `research/strategies/engine.py`.

## Headline numbers

| Strategy | CAGR | Sharpe | Max DD |
|---|---:|---:|---:|
| **Equal-weight AI silicon basket** (~30 names) | +200.6% | **5.09** | -15.5% |
| **Equal-weight AI full-chain basket** (~50 names) | +161.5% | **4.55** | -12.6% |
| **Cross-sectional momentum top-3** (monthly) | +151.7% | **3.59** | -21.1% |
| Concentrated AI optics (LITE+COHR+CIEN) | +191.8% | 3.15 | -49.3% |
| Top-1 momentum (often NVDA) | +174.3% | 3.09 | -36.7% |
| **Vol-targeted trend** (capital protection) | +5.9% | 0.61 | **-2.2%** |
| --- | | | |
| Buy & hold NVDA | +48.0% | 0.90 | -36.9% |
| Buy & hold QQQ | +22.0% | 0.86 | -22.8% |
| Buy & hold SPY | +18.6% | 0.89 | -18.8% |

Equal-weight on a curated AI basket beat ~85% of the 130 active strategies
tested. **Most active strategies underperformed the passive baseline.**

## What's actually in the live bot

Five strategy sleeves are live in the paper-trading bot. The configurations
below were selected from backtest results and adjusted for live execution:

| Sleeve | Strategy | Paper capital | Backtest basis |
|---|---|---|---|
| Bull put credit spreads | 20-delta, 5%-wide, 45 DTE, 25% profit-target | risk cap $17.5k | Synthetic Black-Scholes; not in the 130-test ledger |
| Trend-following equities | Long when >50-day SMA, 8% stop | $21k | Adapted from ts-trend variants |
| Rotational momentum | Top-3 by 10-day return, ~monthly rebalance | $17.5k | `P3_xs_momentum_topN3` (Sharpe 3.59) |
| Earnings straddles | AVGO + MRVL only, T-1 open / T+1 close | $10.5k | Custom; not in main backtest set |
| AI full-chain basket | ~48 names equal-weight, monthly drift rebalance | $17.5k | `B05_ew_full_chain` (Sharpe 4.55) |

Total deployed: $84k of $100k paper capital. The $16k buffer is intentional
to absorb drawdowns and avoid forced delevering at the wrong time.

## What worked (consistent positive Sharpe in backtest)

- **Equal-weight on curated universes** (Sharpe 2.84 to 5.09)
- **Cross-sectional momentum top-3 monthly** (Sharpe 3.59) — best active strategy
- **Concentrated thematic exposure**, when the theme was right
- **Vol-targeted trend** for capital protection (low return, near-zero drawdown)

## What didn't work

- **Mean reversion** in any form — all variants Sharpe <1.2
- **Low-volatility tilt** — defeated by the strong trend factor in this regime
- **Quality+trend composite** — high CAGR but -40 to -55% drawdowns
- **Dual momentum** (asset-class rotation) — protected too much, returned too little
- **Active filters and gates** — added complexity without improving the equal-weight baseline
- **Single-name concentration** (NVDA alone) underperformed the basket containing it

## Limitations (you should read these before believing the numbers above)

1. **2-year window only.** The studied period was a strong AI bull market.
   These strategies have not been tested through 2022-style drawdowns, 2018
   selloffs, or 2008-style crises. **The forward-looking max drawdown is
   almost certainly larger than the backtest shows.**

2. **Survivorship bias.** Stocks delisted, acquired, or that went bankrupt
   in the window are missing (JNPR, CYBR, ABB, etc.). A few percent of
   mid-cap returns are filtered out — and the filtered-out returns are
   probably negative.

3. **No walk-forward validation in the headline numbers.** Strategies were
   tested on the full window. Out-of-sample, results will be worse.

4. **Transaction costs are modeled at 5bps round-trip.** Real costs for
   thinly-traded names (SMCI, ARM, SNDK at certain hours) are higher.
   No market-impact model.

5. **No options-chain history.** The bull-put-spread sleeve uses synthetic
   Black-Scholes pricing calibrated to real-chain mid quotes
   (`SPREAD_IV_HAIRCUT = 0.65` in `config.py`). It is **not** based on a
   historical-chain backtest — that would require paid data.

6. **No intraday bars.** Strategies are daily-bar; any signal that depends
   on opening range, VWAP, or intraday momentum cannot be evaluated here.

7. **Fundamentals not used.** "Quality" tests used rolling Sharpe as a proxy
   for fundamental quality, not real ROE/debt/earnings data. WRDS/Compustat
   grade data would be required for proper factor backtests.

The expanded list of 20+ gaps is in
[`research/strategies/FINDINGS.md`](research/strategies/FINDINGS.md).

## The live record will be the credibility check

Backtests are necessary but not sufficient. The bot is publishing a daily
debrief to a public account beginning shortly. After ~90 days of live paper
trading, that audit-able record (sourced from Alpaca's API, not self-reported)
becomes the meaningful evidence for or against the strategies. Until then,
treat everything above as a hypothesis, not a result.

[Sponsors of this project on GitHub Sponsors](https://github.com/sponsors/krethikram-sudo)
get the weekly written debrief, access to additional strategies that haven't
yet been released to the open-source repo, and a private Discord for setup
help and discussion.
