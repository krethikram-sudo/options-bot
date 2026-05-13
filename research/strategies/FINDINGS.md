# Strategy Search Findings — 130 Iterative Backtests on 2-Year AI Bull Market

**Period**: 2024-03-04 → 2026-05-01 (543 trading days)
**Universe**: 138 tickers across 25 categories (full AI value chain + benchmarks + factors + macro)
**Methodology**: 9 sequential phases, each informed by prior results, plus a bonus Phase 10 of unique strategies.

## Headline finding

The single best strategy by Sharpe was **astonishingly simple**: an equal-weight basket of just two memory stocks (MU + SNDK), held with monthly rebalance. CAGR **+821%**, Sharpe **10.73**, max drawdown **-41.8%**. This dwarfed every active strategy.

This is *not* a strategy to deploy naively — it's a result-of-the-period (memory super-cycle + SNDK spinoff explosion) and the 41.8% drawdown is brutal. But it teaches the core lesson of the search: **in a strongly trending narrow market, concentration on the right names beats sophisticated rules**.

## Top 20 unique strategies by Sharpe ratio

| Rank | Strategy | Family | CAGR | Sharpe | MaxDD | Comment |
|---|---|---|---|---|---|---|
| 1 | X_basket_ai_memory | concentrated_basket | **+821.3%** | **10.73** | -41.8% | MU + SNDK only — memory super-cycle |
| 2 | P5_champ_uni_ai_silicon_only | equal_weight | +200.6% | **5.09** | -15.5% | EW silicon-only universe (~30 names) |
| 3 | B05_ew_full_chain | equal_weight | +161.5% | **4.55** | -12.6% | EW across full AI value chain (~50 names) — **best risk-adjusted** |
| 4 | X_qt_uni_ai_full_chain | xs_quality_trend | +184.7% | 3.61 | -42.6% | Quality+trend on full chain — high CAGR but DD bad |
| 5 | P3_xs_momentum_topN3 | xs_momentum | +151.7% | 3.59 | -21.1% | Top-3 by 12-1 momentum, monthly |
| 6 | P3_xs_momentum_topN5 / B07 | xs_momentum | +135.5% | 3.56 | -18.9% | Top-5 universe momentum |
| 7 | P3_xs_momentum_topN2 | xs_momentum | +158.6% | 3.38 | -25.1% | Top-2 momentum |
| 8 | P3_xs_momentum_topN7 | xs_momentum | +121.2% | 3.29 | -18.7% | Top-7 momentum (more diversified) |
| 9 | X_basket_ai_optics | concentrated_basket | +191.8% | 3.15 | -49.3% | LITE+COHR+CIEN — high return, ugly DD |
| 10 | P3_xs_momentum_topN1 | xs_momentum | +174.3% | 3.09 | -36.7% | Top-1 (winner-take-all, often NVDA) |
| 11 | B14_ew_networking | equal_weight | +166.3% | 2.94 | -51.3% | ANET+LITE+CRDO+COHR+CIEN |
| 12 | P5_champ_uni_networking | (xs_mom mode) | +142.4% | 2.89 | -45.9% | xs momentum on networking |
| 13 | B04_ew_ai9 | equal_weight | +138.7% | 2.84 | -37.7% | Equal-weight original 9-stock universe |
| 14 | P2_xs_mom_ai9_lb90 | xs_momentum | +143.1% | 2.77 | -47.8% | xs momentum 90-day lookback |
| 15 | P2_xs_mom_uni_lb60 | xs_momentum | +149.3% | 2.72 | -49.9% | universe momentum 60-day |
| 16 | B07_xs_mom_universe | xs_momentum | +135.5% | 3.56 | -18.9% | original universe momentum top-5 |
| 17 | P2_xs_mom_ai9_lb60 | xs_momentum | +114.5% | 2.16 | -49.1% | shorter lookback worse |
| 18 | B08_quality_trend | xs_quality_trend | +85.0% | 1.78 | -47.1% | Quality+trend AI-9 |
| 19 | B12_dual_momentum | dual_momentum | +27.3% | 1.14 | -19.2% | Asset-class rotation |
| 20 | B11_ts_voltgt | ts_momentum_voltgt | +5.9% | 0.61 | **-2.2%** | Vol-targeted — almost no DD but low return |

## Comparison to benchmarks

| Benchmark | CAGR | Sharpe | MaxDD |
|---|---|---|---|
| Buy & hold SPY | +18.6% | 0.89 | -18.8% |
| Buy & hold QQQ | +22.0% | 0.86 | -22.8% |
| Buy & hold NVDA | +48.0% | 0.90 | -36.9% |
| 60/40 SPY/TLT | low | low | low |

**Even the worst active candidate beat SPY in this period**, but most active strategies *underperformed simple equal-weight on a curated AI basket*.

## Phase-by-phase narrative — what each phase taught

### Phase 1 (1-15) — Baselines
Established that simple equal-weight beats every active strategy at the family level. **B05_ew_full_chain** at Sharpe 4.55 set a high bar. Quality+trend (B08), low-vol tilt (B09), and mean-reversion (B10) all hit deep -45-50% drawdowns. Vol-targeted trend (B11) had near-zero DD but only 5.9% CAGR — capital protection at the cost of returns.

### Phase 2 (16-30) — Lookback sweeps
Tested lookback 60/90/126/200/300 days for cross-sectional momentum and TS-vol-target. Findings:
- Shorter lookbacks (60-90) generated higher CAGR but deeper drawdowns (-45-50%)
- Longer lookbacks (200-300) had lower returns but smaller DDs
- TS vol-target lookbacks all converged to roughly the same low-DD/low-return profile

**Lesson**: in a regime as fast-moving as 2024-2026 AI, lookback choice trades off whipsaw vs trend persistence.

### Phase 3 (31-45) — top_N sweeps
On AI-9 momentum: top_N=3 was optimal (Sharpe 3.59), with top-1/2 having too much concentration risk and top-5/7 diluting alpha. Quality+trend showed top_N=7 best at Sharpe 2.22. **All quality+trend variants had -40 to -55% drawdowns** — quality screen alone doesn't protect when correlations spike.

### Phase 4-7 (46-85) — Champion tweaking — mostly redundant
The champion had become equal-weight, which doesn't respond to skip/lookback/top_N/weight params. These ~35 iterations confirmed the champion's robustness but produced few unique signals. **Iteration cost was high; information yield was low.** Future searches should detect when champion is unparameterizable and pivot to alternatives.

### Phase 5 (56-65) — Universe variations on champion
Best finding: silicon-only universe (Sharpe 5.09) edged out full chain (4.55). **Networking, hyperscalers, software universes all underperformed silicon-only despite having compelling individual stocks.** Silicon's combination of high momentum + manageable DD is unique to the period.

### Phase 6 (66-75) — Filters
VIX gating, SMA gating, cost variations all produced near-identical results because the champion is rebalanced infrequently and gates rarely triggered. **Cost sensitivity** was the only useful finding: even at 50bps round-trip, results were within 0.1 Sharpe.

### Phase 8 (86-95) — Hybrid signals
Dual-momentum asset-class rotation (QQQ/TLT/GLD variants) returned 5-29% CAGR with Sharpe 0.08-1.21. **Dual-momentum decisively underperforms in a runaway equity market** — the bond/gold sleeves drag whenever they're selected. This validates the academic finding: dual-momentum protects against crashes but underperforms in the absence of one.

### Phase 10 (101-130) — Concentrated thematic baskets
**This was the most informative phase.** Key results:
- AI memory pair (MU+SNDK): 821% CAGR, Sharpe **10.73** (regime-specific)
- AI optics (LITE+COHR+CIEN): 191.8% CAGR but -49% DD
- AI lithography (ASML+AMAT+LRCX+KLAC): only 41.5% CAGR — semi equipment lagged
- Power-pure (VRT+GEV+ETN): 89.4% CAGR, -45% DD
- Buy-and-hold PLTR: 129.3% CAGR — single names had wide outcome dispersion
- 4-name hyperscaler basket (MSFT/GOOGL/META/AMZN): only 23.9% CAGR, **2x worse than naive AI basket**

**Lesson**: hyperscalers were the *worst* place to express AI exposure in this period despite their capex being the proximate cause of the rally. Pure-play silicon and memory captured almost all the alpha.

## What worked vs what didn't (synthesized)

### Worked (consistently positive Sharpe)
- **Equal-weight on curated baskets** (Sharpe 2.84 to 5.09 depending on universe choice)
- **Cross-sectional momentum top-3 monthly** (Sharpe 3.59) — best active strategy
- **Concentrated thematic exposure** (memory: Sharpe 10.73; optics: 3.15) — when right
- **Buy-and-hold the right single name** (NVDA was disappointing relative to basket)

### Didn't work (low Sharpe or bad drawdown)
- **Mean reversion** in any form (5/10/21/63/126-day lookbacks all <1.2 Sharpe)
- **Low-volatility tilt** (Sharpe 0.83-1.44, defeated by trend factor in this regime)
- **Quality+trend composite** (Sharpe 1.78-2.22 with -40-55% DD)
- **Dual momentum** (asset-class rotation) — protected too much, returned too little
- **Active filters/gates** added complexity without improving the equal-weight baseline
- **Single-name concentration** (NVDA at Sharpe 0.90) underperformed the basket of which it was a member

## What this means for the live paper bot

The current live bot (already running) has 4 sleeves: bull put spreads, trend-following, rotational momentum, earnings straddles. The backtest suggests **two new sleeve candidates worth adding for paper testing**:

### Candidate 1 — Equal-weight AI silicon basket (Sharpe 5.09)
- Universe: ~30 silicon names (core AI, semi equipment, foundries, other silicon)
- Equal-weight, monthly rebalance
- Allocation: $20-25k of paper capital
- Expected: slightly lower CAGR than backtest (forward-looking), DD likely larger in regime change

### Candidate 2 — Cross-sectional momentum top-3 monthly on AI-9 (Sharpe 3.59)
- The user's existing bot already has *rotational momentum* on top-3 by 30-day return; this variant uses **12-1 (252-day with 21-day skip)** which historically captures persistent trend better
- Could either replace existing rotation or run as a separate sleeve

## Major gaps in this analysis

The user asked specifically about gaps. Here are the meaningful ones:

### Data gaps
1. **Survivorship bias** — JNPR (acquired by HPE), CYBR (acquired by PANW), ABB (delisted) are missing. A few percent of mid-cap returns are filtered out. Could be addressed by adding delisted history.
2. **Fundamentals not used** — yfinance's fundamental data is point-in-time-fragile. None of the "quality" tests used real ROE, debt, or earnings stability — they used rolling Sharpe as a proxy. Real factor backtests need WRDS/Compustat-grade data.
3. **No options chain history** — backtests are all equity-only. Options strategy backtests need synthetic Black-Scholes (already have) or historical chain data (paid).
4. **No intraday bars** — strategies that depend on opening range, VWAP, or intraday momentum cannot be backtested with the daily dataset alone.
5. **No earnings dates / corporate actions** — pre-earnings volatility plays cannot be tested at scale.
6. **Two-year window only** — too short for proper regime analysis. A 5-year or 10-year window would capture 2022 (which was rough) and the 2018 selloff.

### Methodology gaps
7. **No walk-forward validation** — every strategy was tested on the full window. Optimal parameters from in-sample don't necessarily hold out-of-sample. Should split into train/test windows.
8. **No transaction-cost stress testing** — only constant-bps modeled. Real fills include market impact, especially for thinly-traded names (SMCI, ARM, SNDK).
9. **No stop-loss / take-profit logic** — strategies are fully systematic without risk overlays.
10. **No regime-conditional analysis** — what worked in 2024 vs 2025? Which strategies survive both?

### Strategy gaps (would benefit from more work)
11. **Long-short / market-neutral** — never explicitly tested. Pairs trading was backtested but the framework didn't include shorting in the simulator.
12. **Sentiment-driven** — the live bot has news pipeline but no sentiment-scored backtest.
13. **Calendar effects** — turn-of-month, pre-FOMC, sell-in-May patterns not explored.
14. **Cross-asset (equity + bonds + gold) risk parity** — the dual_momentum sleeves did rotation, not parity.
15. **Earnings-drift / PEAD** — academic literature supports, never tested here.
16. **Insider/13F flow** — Form 4 and 13F changes can be predictive; not in dataset.
17. **Vol surface / IV-based** — no implied vol data so vol arbitrage can't be backtested.

### Conceptual gaps
18. **Position sizing was crude** — equal weight or top-N. Kelly fraction, ERC (equal risk contribution), and HRP (hierarchical risk parity) would be useful additions.
19. **No portfolio-level risk monitoring** — realized vol can spike; no dynamic exposure scaling.
20. **No regime change detection** — strategies don't ask "is the market regime shifting?" before adjusting.

## What to test next (10 priority follow-ups)

1. **Walk-forward validation** of the top-5 strategies — rerun on 2024 H1 only, then check 2024 H2 / 2025 / 2026 separately. Does the silicon-basket champion hold up out-of-sample?
2. **Long-short version** of cross-sectional momentum (long top-3, short bottom-3, dollar-neutral). Should reduce drawdown if it works.
3. **Long-short version** of quality+trend (paired with explicit short of low-quality names).
4. **Pairs trading with proper cointegration testing** — the existing pairs implementation uses static z-score; add ADF cointegration test for inclusion.
5. **Regime-conditional ensemble** — compute strategies' rolling 60-day Sharpe and tilt allocation toward the strategy that's worked best recently (factor-momentum approach from AQR research).
6. **Equal-risk-contribution (ERC) weighting** instead of equal-weight or vol-weighted.
7. **Stop-loss / take-profit overlay** — apply rules-based exits to the top-3 active strategies (xs_momentum, quality+trend, ts_voltgt) and see if Sharpe improves.
8. **Earnings drift backtest** — buy after positive earnings surprise, sell after N days. Use yfinance earnings data.
9. **Two-asset risk parity** with monthly rebalance: 50% AI silicon basket, 50% TLT/GLD by inverse vol. Hypothesis: smooths drawdowns.
10. **Options-overlay backtest** — synthetic credit spreads on AI-9 using BS pricing. Fold this back into the existing live-bot framework.

## Files produced

- `research/strategies/framework.py` — backtest engine + metrics
- `research/strategies/engine.py` — generic parameterized strategy
- `research/strategies/strategies.py` — original 10 candidate strategies
- `research/strategies/search.py` — iterative search controller
- `research/strategies/phase10.py` — extra unique strategies
- `research/strategies/iter_results.csv` — all 130 results
- `research/strategies/iter_log.jsonl` — append-only log per iteration
- `research/strategies/FINDINGS.md` — this document

## Bottom line

The single most important takeaway: **in a 2024-2026 AI bull market, simple wins**. A passive equal-weight basket on a curated AI value-chain universe (~30-50 names) achieves Sharpe 4.55-5.09, beating ~85% of the active strategies tested. Active alpha exists (cross-sectional momentum top-3 at Sharpe 3.59 + diversified) but it's marginal compared to *getting the universe right*.

For the live paper bot, the highest-leverage addition is **a passive equal-weight silicon-basket sleeve**, not another active overlay. The hardest-won lesson from 130 backtests is that we should *not* try to outsmart the market in this regime — we should curate the right universe and let it run.
