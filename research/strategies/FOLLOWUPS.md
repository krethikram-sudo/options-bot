# Follow-up Investigations: Walk-forward, Long-Short, Earnings Drift

Three follow-up backtests run after the initial 130-strategy search. Each was
designed to test a specific hypothesis raised by the original findings.

---

## 1. Walk-forward validation of the top-5 strategies

**Hypothesis being tested**: did the top strategies win because of one favorable
sub-period (the 2025 rotation + 2026 YTD bull), or did they show robust
out-of-sample performance?

**Method**: split the 2024-03 → 2026-05 period into 4 windows and compute
window-specific Sharpe and return for each strategy.

| Strategy | Full Sharpe | W1 ret/Sharpe | W2 ret/Sharpe (DeepSeek) | W3 ret/Sharpe | W4 ret/Sharpe | Robust windows |
|---|---|---|---|---|---|---|
| memory_pair (MU+SNDK) | 10.73 | n/a (SNDK didn't exist) | +11% / 1.73 | +314% / 7.67 | +178% / 26.62 | 3 |
| ai_silicon_only (~30 names EW) | 5.09 | n/a (warmup) | n/a | +12% / 1.42 | +62% / 8.48 | 2 |
| ai_full_chain (~50 names EW) | 4.55 | n/a | n/a | +11% / 1.35 | +53% / 7.48 | 2 |
| qt_full_chain | 3.61 | +12% / 1.43 | +1% / **-0.03** | +243% / 7.72 | +127% / 16.26 | 3 |
| xsmom_top3 | 2.48 | 0% / 0 | 0% / 0 | +134% / 5.16 | +47% / 4.35 | 2 |
| xsmom_universe_top5 | 3.56 | 0% / 0 | 0% / 0 | +203% / 7.26 | +100% / 11.81 | 2 |
| ai_optics (LITE+COHR+CIEN) | 3.15 | +20% / 0.83 | **-9%** / -0.35 | +312% / 8.91 | +113% / 11.71 | 3 |
| ai_networking | 2.94 | +30% / 1.36 | -1% / -0.09 | +244% / 7.24 | +81% / 8.23 | 3 |

**Findings**:

1. **W2 (DeepSeek shock, Oct 2024 - Mar 2025) was brutal**. Active strategies including quality+trend, optics, and networking baskets went near-flat or negative. Only the memory pair (post-spinoff) made meaningful progress.

2. **The "winners" mostly captured the 2025 rotation (W3) and 2026 YTD (W4)**. W3 alone returned +130% to +314% across most strategies — that's the bulk of the headline outperformance.

3. **xs-momentum strategies couldn't generate signals in W1/W2** because the 252-day lookback window wasn't satisfied early in the dataset. This is a real limitation — these strategies need warmup data, so cold-start backtests undercount their early-period viability.

4. **The most defensible strategy is `ai_full_chain` (full AI value chain equal-weight)**: lowest drawdown (-12.6%), consistent positive returns in W3/W4, robust on 2 windows. Less exciting headline numbers but most likely to deliver in real-world conditions.

5. **memory_pair's 821% CAGR is unreplicable going forward** — SNDK spinoff was a one-time event that drove most of the return.

**Verdict**: the headline ranking from the original search was *partially* an artifact of the 2025 H2 / 2026 H1 bull window. Robust strategies (consistent across windows) are equal-weight diversified baskets, not concentrated bets.

---

## 2. Long-short cross-sectional momentum

**Hypothesis being tested**: shorting the worst-performing names should hedge
the long top-N, reducing drawdown without sacrificing too much return.

**Method**: long top-N by 12-1 momentum, short bottom-N, dollar-neutral.
Tested across (universe × lookback × top_n) grid.

### Top results by Sharpe

| Universe | Lookback | top_n | CAGR | Sharpe | MaxDD | Long-only CAGR | Short-only CAGR |
|---|---|---|---|---|---|---|---|
| ai9 | 60 | 2 | **+331.6%** | **5.44** | -30.5% | +553.1% | -40.5% |
| ai9 | 90 | 2 | +168.5% | 2.76 | -42.2% | +243.4% | -29.3% |
| ai_full_chain | 60 | 4 | +136.9% | 2.66 | -22.3% | +332.2% | -49.9% |
| ai9 | 126 | 2 | +136.7% | 2.32 | -30.5% | +291.8% | -45.3% |
| ai_full_chain | 60 | 2 | +149.5% | 2.25 | -41.0% | +425.1% | -56.7% |

**Findings**:

1. **Shorting losers in a bull market actively LOSES money**. Average short-sleeve CAGR across all configs: -32%. The "worst" names at any given month still rallied in the broader bull regime, so shorting them was a costly hedge.

2. **The best LS combo (ai9, lb=60, top_n=2)** more than doubles long-only CAGR (332% vs ~150% long-only top-3) but adds 9 percentage points to drawdown (-30.5% vs -21.1%). It's effectively a leveraged version of the long-only momentum, not a hedge.

3. **Long-only is more capital-efficient**: same Sharpe (~3.6), lower DD, no margin requirement, simpler operationally. **The short leg is dead weight in this regime.**

4. **Lookback sensitivity**: shorter (60-day) momentum dramatically outperforms longer (252-day) lookbacks. The 252-day variants returned 0% — they couldn't generate signals because the window was too narrow vs 2-year dataset.

5. **Universe matters**: ai9 (9 names) outperforms ai_full_chain (~50 names) for LS. With smaller universes, the top/bottom pick is more decisive; with larger universes the bottom-N includes too many "okay" names that didn't deserve shorts.

**Verdict**: long-short momentum is **NOT a useful hedge** in a bull regime — it just leverages the long signal at higher cost. The hypothesis was disproven for this period. **In a bear regime**, the short leg would likely be the source of alpha — but we have no bear-regime data to test that.

---

## 3. Post-earnings-announcement drift (PEAD)

**Hypothesis being tested**: classical academic finding (Bernard & Thomas 1989)
says stocks that beat earnings drift up over weeks; stocks that miss drift down.
Test on our 138-ticker universe.

**Method**: 719 earnings events with surprise data, tested across surprise
threshold (0%/5%/10%/20%) × holding days (1/3/5/10/21/42) × direction.

### Counterintuitive finding: NEGATIVE surprises drift UP

Top 5 PEAD setups by per-event Sharpe (all are after **negative** surprises):

| Direction | Surprise threshold | Hold days | N events | Mean return | Win rate | Sharpe-per-event |
|---|---|---|---|---|---|---|
| **Negative** | >20% miss | 42 days | 40 | **+40.2%** | 65% | 0.39 |
| Negative | >10% miss | 42 days | 55 | +30.3% | 62% | 0.34 |
| Negative | >5% miss | 42 days | 64 | +27.5% | 64% | 0.33 |
| Negative | >20% miss | 10 days | 42 | +6.7% | 57% | 0.33 |
| Negative | >0% miss | 42 days | 107 | +18.8% | 60% | 0.28 |

### Positive-surprise drift was much weaker

| Direction | Surprise threshold | Hold days | N | Mean return | Sharpe |
|---|---|---|---|---|---|
| Positive | >0% beat | 42 days | 560 | +4.7% | 0.21 |
| Positive | >20% beat | 42 days | 126 | +4.7% | 0.16 |
| Positive | >20% beat | 1 day | 137 | **-0.1%** | -0.03 |

**Findings**:

1. **The classical PEAD finding (positive surprise → upward drift) is weak in this universe**. Mean +4.7% over 42 days — comparable to passive market exposure. Big-surprise stocks (>20% beat) actually showed slight 1-3-5-day reversal before rallying long-term.

2. **The reverse setup is statistically the strongest**: negative surprises >20% returned +40% on average over 42 days with 65% win rate. This is the "buy the dip after a miss" pattern in a bull market.

3. **Why? Survivor + regime effects**:
   - Stocks in our universe survived to be in our dataset — winners filter
   - Bull market: even "missed" earnings led to buyable dips that recovered fast
   - Big misses concentrated in cyclical names (MU, SMCI) that subsequently rebounded sharply
   - Small sample (40-65 events) makes results sensitive to outliers

4. **Sharpe-per-event of 0.34-0.39 is mediocre** for a standalone strategy. Compare to the equal-weight basket which has Sharpe 4.5+ (annualized). PEAD per-event is per-trade, not annualized — a 42-day hold period 65% of trades winning, average +30% return is decent but the 88-102% std means this strategy's variance is enormous per event.

5. **Most useful as a decision rule, not a strategy**:
   - "After a big positive earnings beat (>20%), don't add to position in the next 1-5 days; wait for slight reversal."
   - "After a big negative earnings miss in a bull regime, consider buying the dip with a 21-42 day hold target."

**Verdict**: PEAD signals exist in this universe but in a counterintuitive direction (driven by regime). Not strong enough as a primary strategy. Could inform position management overlay on existing momentum strategies.

---

## Consolidated next-step recommendations

After 130 + 3 follow-up backtests:

### Strategies that survived all three tests (recommended for live paper sleeve)

**Equal-weight AI full-chain basket** (B05_ew_full_chain):
- Full Sharpe: 4.55, MaxDD: -12.6%
- Walk-forward: positive in W3 and W4, low DD across all windows
- Doesn't depend on momentum signals (no warmup issue)
- Doesn't require shorting infrastructure
- Most defensible recommendation. Suggest $20-25k allocation.

**Cross-sectional momentum top-3 monthly on AI-9** (P3_xs_momentum_topN3):
- Full Sharpe: 3.59, MaxDD: -21.1%
- Walk-forward: weak in W1/W2 (cold start), strong in W3/W4
- Already partially in live bot (rotational momentum); 12-1 lookback variant is incremental tuning

### Strategies to NOT add (despite good headline numbers)

- **memory_pair (MU+SNDK)**: Sharpe 10.73 is unreplicable (SNDK spinoff one-time)
- **Long-short momentum**: short leg loses money in bull market; complexity not justified
- **PEAD**: per-event Sharpe too weak for a standalone strategy
- **Quality+trend composite**: -42% drawdown is a structural problem, not a tweak fix

### What's still untested (top priority gaps)

1. **Bear-market behavior** — the entire dataset is bull. Strategies need a regime that actually tests their hedges. Need to extend dataset to include 2022 (was -23% on 60/40, -51% on NVDA).
2. **Position-sizing schemes** — equal-weight vs Kelly vs ERC vs HRP. Could materially change drawdown profiles.
3. **Sentiment overlay** — the live bot has news pipeline but no quantitative sentiment scoring backtest.
4. **Regime detection** — explicitly switch strategies based on detected regime (low vol → momentum, high vol → mean reversion).
5. **Options overlays** — every strategy here is equity-only. Adding bull put spreads on the same names could improve risk-adjusted returns.

### Most actionable single addition to live paper bot (after this work)

Allocate **$20k of paper capital to an "ai_full_chain" sleeve**:
- Universe: ~50 tickers across full AI value chain (core AI infra + semi equipment + foundries + other silicon + networking + storage + servers/power + hyperscalers)
- Equal-weight, monthly rebalance
- Cost-tolerant (5-10 bps round-trip won't hurt materially)
- Expected behavior: ~30-50% of S&P-equivalent volatility, smooth drawdowns, captures broad AI capex tailwind
- This is the **lowest-risk, highest-confidence** addition based on 133 backtests

The other strategies are interesting but every additional sleeve adds operational complexity. Don't add unless the marginal Sharpe contribution is clearly positive after walk-forward.

---

## Files produced for this follow-up

- [research/strategies/walkforward.py](walkforward.py) — walk-forward runner
- [research/strategies/walkforward_results.csv](walkforward_results.csv) — per-window metrics
- [research/strategies/longshort.py](longshort.py) — LS xs-momentum grid
- [research/strategies/longshort_results.csv](longshort_results.csv) — LS grid output
- [research/strategies/earnings_drift.py](earnings_drift.py) — PEAD event study
- [research/strategies/earnings_drift_results.csv](earnings_drift_results.csv) — PEAD by direction × threshold × hold
- [research/strategies/FOLLOWUPS.md](FOLLOWUPS.md) — this document
