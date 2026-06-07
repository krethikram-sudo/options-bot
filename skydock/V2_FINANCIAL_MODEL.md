# V2 financial model — fixed-point library subscription business

Internal. Companion to SKYDOCK_V2_THESIS.md. Honest 18-month financial
projection for V2 architecture: 3-10 fixed-point sites + library
subscription product + closed-loop pilot conversion model.

**TL;DR**: Recommend **$2.2M pre-seed** (revised up from initial $1.7M
analysis after founder direction to widen buffer). Lower capex than V1
($205K vs $342K) but slower revenue ramp because subscription model
takes months to compound. Trough cumulative cash: ~−$700K at M6-7. CFP
target month 18-20 (slightly later than V1's M16-18, but at higher MRR
run-rate and better unit economics). End-M18 cash with $2.2M raise:
~$600K (4 months of buffer at mature burn).

---

## 1. Per-site cost structure

### Capex by deployment model

| Model | Description | Capex | Operating annual |
|---|---|---|---|
| **A: Rooftop mount** | Camera + compute + cellular on partner building rooftop. DJI Mini 4 Pro or Skydio X10 mounted, not flying continuously | $25K | $9K (lease $3K + cell $2K + cloud $3K + insurance $1K) |
| **B: Tethered drone** | LTE-tethered drone hovering 50-150m indefinitely. Bigger drone (>250g) for tether weight | $40K | $11K (same as A + tether maintenance $2K) |
| **C: Drone-in-a-box** | Persistent ground station, drone rotates for battery swap. Needs BVLOS waiver | $50-80K | $15K (DIB maintenance higher) |

### Amortization
- 5-year life on all deployment hardware
- Model A: $5K/year amortization → all-in per site $14K/year
- Model B: $8K/year → all-in $19K/year
- Model C: $13K/year → all-in $28K/year

### Centralized labor allocation to sites

Curation operator (centralized, remote monitoring): $80K loaded for 1 FTE
covering ~5-10 sites. Per-site allocation: $10K/year.

**Total per-site annual cost at Y1 mix (Model A only)**: ~$24K/year per site

### Production per site
- Continuous daylight capture × 8h × 30 days = 240 site-hours/month
- ~5,000 raw candidate scenarios per site-month (highD reference: 110K
  vehicles in 16.5 hours from single hover; we expect ~6,600 vehicle-
  interactions per site-month conservatively)
- Curation filter: top 20% on 2+ of 5 signals → ~1,000 delivered
  scenarios per site-month
- **Annual delivered scenarios per site: ~12,000**

### Per-delivered-scenario cost
- $24K annual cost ÷ 12,000 scenarios = **$2.00/scenario delivered**
- vs V1's $87/scenario all-in at steady state

This is the unit-economics flip the V2 thesis depended on.

---

## 2. Monthly burn projection (18 months)

Using V2 labor structure: founder $200K cash + benefits = $250K loaded;
$250K senior eng; $220K GTM; $160K CS; $80K curation ops; $20K/mo
hardware contractor (M1-6 only).

### Phase 1 (M1-3): Build phase

- Founder ($21K/mo) + curation/ML eng contractor ($20K/mo) + hardware/site
  contractor ($20K/mo) + overhead + legal
- **Monthly cost: $75K**
- **Phase total: $225K**
- Capex: $0 (site negotiations in progress)
- Revenue: $0

### Phase 2 (M4-6): First 3 Model A sites deployed

- Founder + 1st FT eng hire (curation) starts M5 ($21K/mo)
- 0.5 FTE curation operator hire M6 ($7K/mo)
- Hardware contractor wraps up by M6
- **Monthly cost: $90K**
- **Phase total: $270K**
- Capex: $75K (3 × Model A at $25K each, deployed M4, M5, M6)
- Revenue: $0 (free pilots start M5 with 1st prospect customer)

### Phase 3 (M7-9): First paid customer + 4th site

- Founder + curation eng + 1 FT curation operator + contractor wrap
- **Monthly cost: $90K**
- **Phase total: $270K**
- Capex: $25K (4th Model A site M9)
- Revenue: 1st customer signs M7 ($150K ARR = $12.5K/mo from M8) →
  $12.5K + $12.5K + $12.5K = **$37.5K**

### Phase 4 (M10-12): 2nd customer + 5th site

- Above team + GTM hire starts M11 ($18K/mo)
- **Monthly cost: $110K**
- **Phase total: $330K**
- Capex: $25K (5th Model A site M11)
- Revenue: $12.5K (M10) + $25K (M11, 2nd customer ramped) + $25K (M12) =
  **$62.5K**

### Phase 5 (M13-15): 3rd-4th customers + 1st Model B site

- + 2nd eng hire M14 ($21K/mo)
- **Monthly cost: $130K**
- **Phase total: $390K**
- Capex: $40K (1st Model B tethered drone site M15)
- Revenue: M13 $37.5K + M14 $37.5K + M15 $54K = **$129K**
- Plus first custom-capture order M14 ($75K) = **$204K phase total**

### Phase 6 (M16-18): 5th-6th customers + 0.5 CS hire

- + 0.5 FTE customer success M17 ($7K/mo)
- **Monthly cost: $140K**
- **Phase total: $420K**
- Capex: $40K (2nd Model B tethered site M18)
- Revenue: M16 $54K + M17 $75K + M18 $75K = **$204K**

### 18-month rollup

| Phase | Months | Recurring monthly | Capex | Phase total cost | Phase revenue |
|---|---|---|---|---|---|
| 1 | 1-3 | $75K | $0 | $225K | $0 |
| 2 | 4-6 | $90K | $75K | $345K | $0 |
| 3 | 7-9 | $90K | $25K | $295K | $37.5K |
| 4 | 10-12 | $110K | $25K | $355K | $62.5K |
| 5 | 13-15 | $130K | $40K | $430K | $204K (incl $75K custom) |
| 6 | 16-18 | $140K | $40K | $460K | $204K |
| **Total** | | | **$205K capex** | **$2.11M** | **$508K** |

---

## 3. Cumulative cash with $2.2M raise

| Milestone | Month | Cumulative cash position |
|---|---|---|
| Pre-seed close | 0 | $2.2M |
| End M3 (build phase done) | 3 | $1.98M |
| End M6 (3 sites + first pilots) | 6 | $1.63M |
| First paid pilot signed | 7 | $1.63M |
| End M9 (4 sites, 1 customer ramping) | 9 | $1.38M |
| End M12 (5 sites, 2 customers, GTM hire) | 12 | $1.08M |
| End M15 (5 sites, 4 customers, +Model B + custom) | 15 | $0.86M |
| End M18 (7 sites, 6 customers ARR $1.2M run-rate) | 18 | **$0.60M** |
| M19+ (positive contribution kicks in) | 19+ | growing |

**End-M18 cash position: ~$600K** with $2.2M raise. At Phase 6 burn rate
of $140K/month, that's ~4 months of buffer.

**Pessimistic-case survivability**:
- 3-month customer-ramp slip → −$420K → still $180K positive at M18
- BVLOS waiver +6 months → ~−$200K capex shift later → still positive
- Combined ASP pressure (Library subscription closes at $100K avg
  instead of $150K) → −$100K revenue → still positive

### Why $2.2M not $1.7M

Comparison of two raise options:

| Metric | $1.7M raise | **$2.2M raise (recommended)** | $2.5M raise (cushioned) |
|---|---|---|---|
| End M18 cash | $0.10M | **$0.60M** | $0.90M |
| Months of buffer at M18 burn | 0.7 | **4.3** | 6.4 |
| Pessimistic-case survival | Tight | **Comfortable** | Comfortable + accelerated seed |
| Dilution at post-money cap | 17% @ $10M | **18% @ $12M** | 19% @ $13M |
| Seed prep timing | M20-22 | **M19-21** | M18-20 (pulls forward) |

**$2.2M is the sweet spot**: $500K more buffer than $1.7M for only
~1% more dilution. Allows for comfortable pessimistic-case survival
without giving up materially more equity.

**$2.5M considered** but rejected for now: adds ~$300K more buffer
than $2.2M for ~1% more dilution. Worth revisiting if first investor
conversations show preference for chunkier rounds. Some funds (Floodgate,
K9) actively prefer to over-fund cleaner rounds; if that signal emerges,
$2.5M at $13M post-money is the upgrade.

### What the extra $500K buys

Beyond pure buffer, $2.2M vs $1.7M enables:
- **One extra eng hire 2 months earlier** (M11 instead of M13) — accelerates
  curation pipeline maturity
- **OR one extra site M15** (a 2nd Model B tethered drone deploy) —
  accelerates revenue with one more site coming online by M16
- **OR seed-prep work starts M16 instead of M18** — pulls seed close
  forward by 2 months

These are all "optionality" not "necessity" — the core plan works at $1.7M
but with no margin for surprise. $2.2M turns surprise into adjustment.

---

## 4. Unit economics at maturity (Year 3, 15 sites)

| Metric | Value |
|---|---|
| Annual cost (15 Model A sites + 3 Model B + 2 Model C) | $24K × 15 + $34K × 3 + $43K × 2 = $548K site costs |
| Centralized labor (3 eng + 1 GTM + 1 CS + 2 ops + founder) | $1.6M loaded |
| Overhead | $200K |
| **Total annual cost** | **~$2.35M** |
| Customers (Year 3 thesis projection) | 15 |
| Average library subscription | $250K/year |
| Library subscription ARR | $3.75M |
| Custom capture revenue (5-6 new sites) | $500K |
| **Total Year 3 revenue** | **$4.25M** |
| **Gross profit** | **$1.9M** |
| **Gross margin** | **45%** |

### Comparison vs V1

| Metric | V1 (mobile) at 6 vehicles | V2 (fixed-point) at 15 sites |
|---|---|---|
| Annual cost | $1.91M | $2.35M |
| Annual revenue | $4.4M (at $200 weighted ASP) | $4.25M |
| Gross profit | $2.49M | $1.9M |
| Gross margin | 57% | 45% |
| Customer count | 4-6 | 15 |
| Average per-customer ARR | $440K-$733K | $283K |

V2 has **slightly lower gross margin** at maturity, but:
- **15 customers vs 6** = more customer-base diversification, less
  concentration risk
- **Subscription revenue is durable** (12-month contracts, expansion-heavy)
- **Higher contribution margin per scenario** (94% per V1, but V2 is more
  like 96% since cost-per-scenario is $2 vs V1's $19)
- **Defensible moat in curation methodology** (V1's moat was operational
  discipline; V2's is curation IP + multi-tenant corpus + customer
  integration)

### Why margin is lower at maturity

V2 has more centralized labor (curation engineers > $250K loaded, vs V1
operator-drivers at $80K). The 3 senior engineering hires vs 4 operators
costs ~$450K/year more. This is offset by:
- Subscription revenue compounds (Y4 and beyond add net-new customers
  without new capex)
- Each new site costs $25K (Model A) to expand, much lower than V1's
  $57K per vehicle
- Curation pipeline scales sub-linearly with sites

So at year 5: revenue maybe $8M+, cost ~$3M, GM 62%+. The maturity case
gets better than V1 once the engineering team is fully utilized across
many sites.

---

## 5. LTV per customer (subscription model)

Library subscription customer retention assumptions:
- Year 1: 100% (12-month commitment)
- Year 2: 80% renewal at expansion ($250K → $300K)
- Year 3: 70% retention from Y2 base
- Year 4: 60% (some customers consolidate suppliers)

LTV calculation:
- Y1 revenue: $150K
- Y2 revenue: $300K (with 80% retention probability)
- Y3 revenue: $300K × 70% = $210K
- Y4 revenue: $300K × 70% × 60% = $126K
- Expected lifetime gross revenue: $150K + ($300K × 0.8) + ($300K × 0.56)
  + ($300K × 0.336) = $150K + $240K + $168K + $101K = **$659K LTV**

At 45% mature GM: **gross profit LTV per customer: ~$297K**

CAC analysis:
- GTM cost per customer: $220K GTM × 1 / 4 customers/year × 1.5 (year of
  ramp) = ~$80K CAC
- LTV/CAC: $297K / $80K = **3.7x** (target is 3x+, this clears)

---

## 6. Comparison V1 vs V2 in summary

| | V1 (mobile) | V2 (fixed-point) |
|---|---|---|
| Raise | $2.0M | **$2.2M** |
| Total 18-mo cost | $2.16M | $2.11M |
| Total 18-mo capex | $342K | $205K |
| Total 18-mo revenue | $2.30M | $508K |
| CFP timing | M16-18 | M18-20 |
| End-M18 cash | $1.89M | $0.60M |
| 18-mo cumulative cash position | Better | Worse (lower revenue ramp) |
| Year 3 revenue | $4.4M | $4.25M |
| Year 3 gross margin | 57% | 45% |
| Year 5 trajectory | ~$5-7M ARR, 65% GM | $8M+ ARR, 62%+ GM |
| Customer concentration risk | Higher (6 customers) | Lower (15 customers) |
| Moat | Operational discipline | Curation IP + corpus + integration |
| Race vs synthetic data | Direct race (loses long-term) | Wins (validation can't substitute) |
| Dilution at post-money cap | 17% @ $10M | 18% @ $12M |

**V2 is structurally a slower-to-CFP, lower-margin-at-MVP, higher-margin-
at-maturity, harder-to-kill business.** Trades early-revenue ramp for
durable defensibility.

---

## 7. What this implies for the rest of the rebuild

### RAISE_SIZING update needed
- Recommend $2.2M raise (revised up from initial $1.7M per founder
  direction to widen buffer)
- New monthly burn projection above replaces V1's
- New trough analysis: M18 not M12
- $12M post-money cap, ~18% dilution
- $2.5M alternative if investor signal supports chunkier rounds

### EXECUTION_PLAN update needed
- Phase 2-6 rebuilt around site deployment sequence (not vehicle
  ramp)
- Hiring sequence changes: curation eng > operator-drivers, GTM later
- BVLOS waiver work added as Phase 4-5 deliverable

### PITCH.md (Q21) update needed
- New 18-month financial table
- CFP timing M18-20 honest case
- Run-rate ARR at M18: $900K-$1.2M
- LTV/CAC story: $297K LTV / $80K CAC = 3.7x

### EQUITY_PROJECTION update needed
- Slightly lower post-money cap (~$10M, similar to V1)
- Same ~17% dilution
- Founder ownership trajectory unchanged
- Path to acquisition: $75M-$150M at Year 4-5 (similar to V1 but cleaner
  story for safety-team-focused buyer like Mobileye, Aurora Innovation,
  or Cognata)

### Customer site rewrite needed
- Kill Order options (per-scenario tiers don't fit subscription)
- Add Library subscription tiers + custom capture pricing
- Replace lead with closed-loop pilot CTA
- Replace "vehicle-deployed" everywhere with "fixed-point site-deployed"

### Discovery scripts update needed
- Refocus on safety teams (not perception teams)
- Lead with closed-loop pilot offer
- Update target customer list to safety officers at AV companies

---

*v1, May 2026. V2 financial model. Replaces V1 RAISE_SIZING.md
and COST_MODEL_AUDIT.md (those docs reflect V1 mobile architecture
and should be marked stale until the rebuild propagates through).*
