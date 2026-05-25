# Founder equity projection — pre-seed through seed

Internal. Cap table evolution through Skydock's funding stages with explicit
assumptions. Numbers are approximations — actual cap table at any moment
depends on specific SAFE / seed terms which are negotiated.

**TL;DR**: As **sole founder**, you'd own approximately:
- **100% at incorporation**
- **100% of issued shares after pre-seed close** (~80% pro-forma when SAFE converts)
- **~50-55% after seed round** (typical scenario)
- **~38-45% after Series A** (if raised)
- **~28-35% after Series B** (if raised)

Solo-founder status is a meaningful advantage — co-founder splits halve this. Most
seed-stage founders end up at 35-45% post-seed; you're projected at 50-55% because
no co-founder dilution.

---

## Assumptions

| Variable | Assumed value | Source |
|---|---|---|
| Founder split | Solo founder (you own 100% of common at start) | Your background |
| Pre-seed structure | $2.0M on YC post-money SAFE at $10M post-money cap | RAISE_SIZING.md |
| Pre-seed → SAFE share | 20% at conversion | $2M / $10M = 20% |
| Seed round size | $5-10M | EXECUTION_PLAN.md Phase 5 |
| Seed valuation | $25-40M post-money | EXECUTION_PLAN.md |
| Option pool at seed | 10% pre-money (standard pre-seed → seed) | Industry standard |
| Series A (if raised) | $15-25M at $60-100M post-money + 5% pool top-up | Standard trajectory |
| Series B (if raised) | $30-50M at $150-250M post-money + 5% pool top-up | Standard trajectory |

---

## Stage-by-stage cap table

### Stage 1: Incorporation (Day 0)
| Holder | Shares | % |
|---|---|---|
| Founder | 10,000,000 | **100%** |

You own everything. Standard founder stock at incorporation.

### Stage 2: Pre-seed close (SAFE issued, not converted)
| Holder | Shares | % of issued | Pro-forma at conversion |
|---|---|---|---|
| Founder | 10,000,000 | 100% | ~80% |
| Pre-seed SAFE | — (right to ~20% on conversion) | 0% | ~20% |

You still own 100% of *issued* equity. SAFEs are a promise of future shares,
not actual shares yet. You retain full voting control through pre-seed.

### Stage 3: Seed close — typical scenario

**Variables**: $7.5M seed at $30M post-money cap + 10% option pool added pre-money

| Holder | Approximate % |
|---|---|
| **Founder** | **~50%** |
| Pre-seed SAFE (now converted) | ~15% |
| Option pool (ESOP) | ~10% |
| Seed investors | ~25% |

The math:
- Seed investors: $7.5M / $30M = 25%
- Option pool: 10% (added pre-money, dilutes founder + SAFE)
- Pre-seed SAFE conversion: ~15% (20% allocated minus dilution from option pool)
- Founder retains: 100% − 25% − 10% − 15% = **50%**

### Stage 4: Series A (if raised) — typical scenario

**Variables**: $20M at $80M post-money + 5% option pool top-up

| Holder | Approximate % |
|---|---|
| **Founder** | **~38%** |
| Pre-seed SAFE | ~11% |
| Option pool | ~14% (10% + 5% top-up minus prior usage) |
| Seed investors | ~19% |
| Series A investors | ~18% (or 25% if reaching for full $20M / $80M) |

Founder drops 12 percentage points (50% → 38%) at Series A — meaningful but
this is standard. Most Series A founders sit in the 30-45% range.

### Stage 5: Series B (if raised) — typical scenario

**Variables**: $40M at $200M post-money + 5% pool top-up

| Holder | Approximate % |
|---|---|
| **Founder** | **~28-32%** |
| Earlier round investors (SAFE + Seed + A) | combined ~40% |
| Option pool | ~15-18% |
| Series B investors | ~20% |

Founder at 28-32% is common for late-stage startup founders. CEOs typically
retain 15-25% by IPO if multiple rounds happen.

---

## What you actually own in dollar terms

Approximate paper value of founder equity at each stage:

| Stage | Founder % | Implied valuation | Founder paper value |
|---|---|---|---|
| Pre-seed (post-conversion) | ~80% | $10M (SAFE cap) | $8M |
| Seed | ~50% | $30M | $15M |
| Series A | ~38% | $80M | $30M |
| Series B | ~30% | $200M | $60M |
| Acquisition at $150M (year 4-5 honest case) | ~30-50% (depends on if seed raised) | $150M | $45-75M |
| Acquisition at $300M (year 5-7 optimistic) | ~25-30% (after seed + A) | $300M | $75-90M |

Note: paper value ≠ liquidity. Founder shares are common stock — convert to
cash only at liquidity event (acquisition, IPO, or secondary sale).

---

## Solo-founder advantage

For comparison, here's what the typical multi-founder split looks like:

| Co-founder structure | Each founder's seed-post % |
|---|---|
| **You (solo)** | **~50%** |
| 2 co-founders, 60/40 | 30% / 20% |
| 2 co-founders, 50/50 | 25% / 25% |
| 3 co-founders | 17% each |

You retain 2× the equity of a typical 50/50 co-founded startup. The downside:
all the execution risk is on one person. That's reflected in why you have a
founder + GTM hire + 2 eng + ops team plan — to spread execution while
preserving founder economics.

---

## Three ways to retain more equity

1. **Skip the Series A.** Bootstrap from CFP. Stay at ~50% post-seed.
   Per ASSUMPTIONS_AND_PROFITABILITY.md, this is a real option given Skydock
   hits CFP at M15-17.

2. **Smaller seed round.** $5M seed at $25M post-money (instead of $7.5M at
   $30M) leaves you at ~52% instead of ~50%. Trade-off: less capital for
   expansion.

3. **Aggressive SAFE cap.** Negotiate pre-seed at $12-15M post-money cap
   (instead of $10M). Lower SAFE dilution. Trade-off: investors may push back
   given pre-revenue stage.

---

## What affects the actual % most

| Lever | Range | Founder impact |
|---|---|---|
| Pre-seed cap | $8M-$15M | ±3% founder % |
| Seed round size | $5M-$10M | ±5% founder % |
| Seed valuation | $20M-$40M | ±5-7% founder % |
| Option pool size | 5-15% | ±5% founder % |
| Series A timing | Year 2 vs Year 3-4 | ±3-5% founder % |
| Acquisition vs IPO path | Earlier exit = less dilution | up to 10% founder % |

The single biggest lever after the raise is: **don't raise more than you need**.
Each round is dilution. Bootstrap-or-raise discipline matters more than getting
a slightly better valuation.

---

## Real considerations beyond %

Equity ownership is one of three things that matter at exit:

1. **% ownership** (this doc) — share of proceeds
2. **Liquidation preferences** — investors typically get their money back
   *first* in low-exit scenarios (1× non-participating preferred is standard)
3. **Board control** — typically 3-member board post-seed: 1 founder, 1
   investor, 1 independent. Founder can retain CEO role even with <50%
   ownership.

For a moderate-acquisition outcome ($75-150M), liquidation preferences
matter more than %. At $200M+ acquisition, % dominates and the preferences
are absorbed.

---

## Recommended cap table negotiation priorities

In order of importance for pre-seed:

1. **Post-money SAFE structure** (not pre-money, not convertible note) — clearer math, less ambiguity at conversion
2. **Cap, not discount** — $10M post-money cap is industry standard for pre-seed
3. **MFN (Most Favored Nation) clause** — protects later pre-seed investors from worse terms than earlier ones
4. **Pro-rata rights** — let early investors participate in later rounds; signals confidence
5. **No special seat / observer rights at pre-seed** — keep founder control intact

What to push back on at pre-seed:
- Founder vesting acceleration (single trigger vs double trigger — accept double trigger)
- Voting rights restrictions on common stock
- Restrictions on founder secondary sales
- Aggressive anti-dilution provisions (full ratchet — push for weighted average)

---

*v1, May 2026. Update when actual SAFE / seed term sheets come in.
Get a startup attorney (~$5K for pre-seed cap table review) before
signing any term sheet.*
