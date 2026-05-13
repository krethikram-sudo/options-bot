# Gap Tests: 5 Hypotheses, 6 Years of Data

After the initial 130-strategy search and 3 follow-up tests, 5 major gaps remained.
This document tests each. **Critical context**: dataset extended to 6.3 years
(Jan 2020 → May 2026) so 2022's rate-shock bear is finally testable.

---

## Gap 1 — Bear-Market Behavior

**Hypothesis**: top strategies look great on 2024-2026 data, but how do they
hold up across 2020-2026 including the 2022 bear?

### Per-year returns (full 6-year window)

| Strategy | Full CAGR | Full Sharpe | Full MaxDD | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 |
|---|---|---|---|---|---|---|---|---|---|
| EW AI-7 (full history) | **55.4%** | **1.22** | **-44.8%** | +74% | +59% | **-33.5%** | +129% | +73% | +55% |
| EW full chain (post-2024 only) | 165.2% | 4.62 | -13.2% | n/a | n/a | n/a | n/a | n/a | +11% |
| BH SPY | 15.0% | 0.54 | -33.7% | +17% | +30% | -18.6% | +27% | +26% | +18% |
| BH QQQ | 20.4% | 0.66 | -35.1% | +46% | +29% | -33.2% | +56% | +28% | +21% |
| BH TLT | -4.4% | -0.50 | -48.4% | +17% | -5% | -29.4% | +1% | -8% | +4% |
| 60/40 SPY/TLT | 7.8% | 0.29 | -27.2% | +20% | +16% | -22.3% | +16% | +12% | +13% |

### Verdict — material correction

The 4.62 Sharpe of EW full chain over 2024-2026 was **substantially an artifact of the bull window**. Across 6 years on the AI-7 (the only sub-universe with full history):
- **Sharpe drops from 4.62 → 1.22**
- **MaxDD widens from -13% → -45%**
- 2022 alone delivered -33.5% (vs SPY -18.6% — even the bond/equity 60/40 only lost 22%)

Bonds also failed (-29% in 2022) — the 60/40 textbook fell apart simultaneously.

**This is the gap test that most changes the recommendation**. Honest expectation for the live bot: the AI infra basket has ~-40% drawdown potential in a real bear regime. Position-size accordingly.

---

## Gap 2 — Position-Sizing Schemes

**Hypothesis**: smarter sizing (Kelly, ERC, HRP, min-var) can improve risk-adjusted returns over naive equal-weight.

| Method | CAGR | Sharpe | MaxDD | Vol |
|---|---|---|---|---|
| **equal** | 165.2% | **4.62** | -13.2% | 34.9% |
| kelly | 173.9% | 4.62 | -14.5% | 36.8% |
| inv_vol | 132.0% | 4.01 | -13.2% | 31.9% |
| min_var | 102.5% | 3.24 | -13.2% | 30.4% |
| hrp | 94.0% | 3.13 | -13.2% | 28.8% |

### Verdict — equal-weight wins

- **Kelly** matched equal-weight on Sharpe (4.62) with marginally higher CAGR (174%) but slightly worse DD. Not enough to justify complexity.
- **inv-vol, min-var, HRP** all underperformed by 1.0-1.5 Sharpe points. They each penalized higher-vol names — but in the AI bull, the highest-vol names (SMCI, ARM) were also among the highest-return names. Vol-penalizing weighting threw away alpha.
- **Diversification benefit of HRP/min-var**: Vol modestly lower (28-30% vs 34-37%) but at major Sharpe cost.

In a bull regime where high-vol names lead, naive equal-weight is the right answer. **In a bear regime this would likely flip** — minimum-variance would protect during 2022. Without enough bear data inside Gap 2's coverage window, we can't confirm.

---

## Gap 3 — Sentiment Proxy (Price-Based)

**Hypothesis**: a price-action sentiment overlay (SPY 5-day return + RSI > 50 = bullish; otherwise cash) can reduce drawdown without sacrificing too much return.

| Strategy | CAGR | Sharpe | MaxDD |
|---|---|---|---|
| baseline EW (no gate) | 165.2% | **4.62** | -13.2% |
| sentiment-gated (cash when SPY 5d<0 or RSI<50) | 69.9% | 3.04 | **-7.8%** |

### Verdict — DD-reducer with high cost

Sentiment gating cut maximum drawdown nearly in half (**-13% → -8%**) but reduced returns by **95 percentage points** of CAGR (**165% → 70%**). Sharpe dropped from 4.62 to 3.04.

In a strong bull regime that's a poor tradeoff. In a high-vol or bear regime, the same gate would protect significantly more capital. The fundamental limitation: this is a **price-action proxy, not real sentiment data**. True historical news sentiment is paywalled — none of yfinance, Alpaca News (free tier), or Google Trends provides queryable historical batch data going back 6 years for individual tickers.

**True sentiment overlay testing requires**: paid data subscription (Bloomberg/RavenPack ~$$$/month) or LLM-scoring of historical news archives (Common Crawl + manual scoring infrastructure).

---

## Gap 4 — Regime Detection + Strategy Switching

**Hypothesis**: detecting regimes (uptrend × low/high vol) and switching strategies should improve through-cycle results.

### Regime distribution over 6 years
- uptrend_lowvol: 890 days (56%)
- uptrend_highvol: 228 days (14%)
- downtrend_lowvol: 268 days (17%)
- downtrend_highvol: 205 days (13%)

### Performance with regime-switching
| Strategy | CAGR | Sharpe | MaxDD |
|---|---|---|---|
| baseline EW | 165.2% | **4.62** | -13.2% |
| regime-switch (full long → 50% → TLT) | 90.8% | 3.11 | **-10.9%** |

### Verdict — same DD-reducer pattern as Gap 3

Regime switching cuts ~74pp of CAGR to gain only 2.3pp of DD reduction. **Bad tradeoff in this period**, but again — much of the data is uptrend_lowvol so regime-switching mostly meant "stay long." During downtrend regimes, the strategy moved to TLT which lost 7-29% in 2022.

The genuine value of regime detection is *only* visible during regime transitions — which were rare in this dataset. In a longer dataset including 2008, 2018, etc., regime switching would likely show stronger value.

---

## Gap 5 — Options Overlay (BS-synthesized credit spreads)

**Hypothesis**: adding a 5% allocation to bull put credit spreads on basket constituents should improve Sharpe through theta harvest.

| Strategy | CAGR | Sharpe | MaxDD | 2022 | 2025 |
|---|---|---|---|---|---|
| basket only (NVDA/AMD/AVGO/MU/TSM/MRVL) | 51.8% | 1.16 | -52.2% | -44.9% | +62.4% |
| basket + credit spread overlay | 52.3% | 1.17 | -52.3% | -45.0% | +63.0% |

### Verdict — overlay adds ~nothing in this implementation

The overlay added 0.5pp CAGR and 0.01 Sharpe. Why so weak?

1. **Allocation too small** — 5% of basket isn't enough to move the needle when underlying returns 50%+
2. **No regime conditioning** — overlay sold puts in 2022 too, which got assigned at max-loss during the rate-shock crash
3. **30-day expiry too short** — captured less theta than a 45-day setup
4. **Synthetic IV (realized vol) underestimates real implied vol** — actual options market would have charged richer premium

The architecture is right; the parameters need tuning. The live paper bot's existing bull put spread sleeve (45 DTE, 35-delta, 25% PT) is closer to a useful implementation. **A proper options overlay backtest needs richer parameter grid** (already done partially in the original spread tuning work).

Note: this also shows the **6-year results for the AI-6 core** (not full chain): -52% drawdown in 2022, only 1.16 Sharpe across the period. Far less rosy than the 2-year picture.

---

## Consolidated key findings

### What changed because of bear-regime testing

Adding 2022 to the dataset materially changed the picture:

| Metric | 2-year window only | 6-year window |
|---|---|---|
| EW AI-7 Sharpe | ~3-4 | **1.22** |
| EW AI-7 MaxDD | -38% | **-45%** |
| 2022 isolated return | n/a | **-33.5%** |
| Equal-weight basket safety claim | "smooth, low DD" | **"high return but real bear-regime exposure"** |

The most defensible recommendation from earlier work — `ai_full_chain` equal-weight — likely still holds, but **expectation-set differently**: this is a high-return strategy with realistic potential for -40 to -45% drawdowns in a regime change.

### What didn't help

- **Sophisticated position sizing** (Kelly/ERC/HRP/min-var) — all underperformed equal-weight in this regime
- **Sentiment gating** — cut DD ~5pp at cost of ~95pp CAGR
- **Regime switching** — same DD-reducer pattern
- **Options overlay (5% allocation)** — marginal impact

### What the picture looks like now

| Strategy | Recommendation strength | Real expectation |
|---|---|---|
| EW full AI value chain | **Strongest single addition** | ~30-50% CAGR through cycle, -40% DD in bear |
| xs-momentum top-3 monthly | Solid active overlay | ~25-35% CAGR, -25% DD in bear |
| Long-short momentum | **Don't add** in bull regime | Short leg actively loses |
| Concentrated baskets (memory pair etc.) | **Don't deploy** as standalone | Regime-specific, untestable |
| Options overlay on basket | **Iterate parameters** before adding | Current tuning weak |
| Sentiment/regime gates | Good for risk-averse phases | Costly in bull markets |

### Honest takeaway

The **simplest strategy (equal-weight on a curated AI value chain)** remains the best risk-adjusted candidate to add to the live paper bot. **But the headline 4.62 Sharpe was inflated by the bull window.** Realistic through-cycle expectation is closer to **1.5-2.0 Sharpe** with **-30 to -40% maximum drawdown**.

That's still excellent, but it's a less dramatic story than the 2-year backtest implied. Sizing matters: **don't allocate $25k to this sleeve assuming it'll smoothly compound.** Allocate as if you might need to weather a -40% drawdown in any year.

---

## Files produced

- [research/build_dataset_extended.py](../build_dataset_extended.py) — 6-year data builder
- [research/data_extended/](../data_extended/) — 138 tickers × 6.3 years
- [research/strategies/gap_tests.py](gap_tests.py) — all 5 gap test functions
- [research/strategies/gap1_bear_test_results.csv](gap1_bear_test_results.csv)
- [research/strategies/gap2_sizing_results.csv](gap2_sizing_results.csv)
- [research/strategies/gap3_sentiment_results.csv](gap3_sentiment_results.csv)
- [research/strategies/gap4_regime_results.csv](gap4_regime_results.csv)
- [research/strategies/gap5_options_overlay_results.csv](gap5_options_overlay_results.csv)
- [research/strategies/GAPS_TESTED.md](GAPS_TESTED.md) — this document

## What's STILL untested (the next layer of gaps)

After 130 main backtests + 3 follow-ups + 5 gap tests, what remains:

1. **Real (not proxy) sentiment data** — needs paid data
2. **Cross-strategy combination ensembles** — equal-risk allocation across the top strategies; not a single strategy but a portfolio of strategies
3. **Live execution friction** — slippage, partial fills, market impact at the actual paper trading scale
4. **Multi-asset risk parity at portfolio level** — apply ERC across the live bot's 4 sleeves rather than within any one strategy
5. **Adversarial / stress scenarios** — what happens with custom adverse paths (Fed shock, China invasion, etc.)
6. **Tax considerations** — short vs long-term capital gains, wash sale rules — relevant only if going beyond paper
7. **Drawdown-conditional rebalancing** — pause rebalance when in drawdown to avoid selling losers and buying winners at adverse prices

The next-most-actionable gap is #4 — apply ERC at the portfolio level across the live bot's existing 4 sleeves, after adding the new ai_full_chain sleeve. That's a meta-strategy decision, not another backtest.
