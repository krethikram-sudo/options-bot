# Assumptions audit + profitability vs next-raise timing

Internal companion doc to RAISE_SIZING.md. Two questions the prior
sizing analysis didn't fully surface:

1. **What assumptions are baked into the $2M pre-seed plan?**
2. **Does the pre-seed get us to profitability before the next raise?**

Short answers up front:

**Question 1**: Ten major assumption categories. Most are sim-grounded
or industry-benchmarked, but **none have been validated in real-world
operations yet**. The single highest-risk assumption is operator
utilization (year-1 ramp could be much slower than modeled).

**Question 2**: **Yes, in the honest case**. CFP at month 16-18 under
$200 weighted ASP, with $1.89M cash position remaining at M18. The
business is self-sustaining at that point. **The seed round becomes
optional** — needed for geographic expansion + product growth, not for
survival.

---

## 1. Ten assumptions baked into the model

### Confidence scale
- 🟢 **High** — peer-reviewed, industry-standard, or sim-validated
- 🟡 **Medium** — directionally right but unverified
- 🔴 **Low** — extrapolation that needs first-customer signal to confirm

### A. Operator capacity / utilization — 🟡 medium

- 20 captures per vehicle-day at 22 operating days/month
- 4 operators rotating across 6 vehicles (not 1:1 — driver pooling)
- Sustained productivity with no significant churn
- Operators reach full utilization by month 13

**What could break it:** Year-1 reality often has operators idle 30-50%
of the time waiting for trigger arrivals or transit between waypoints.
If utilization hits 60% instead of 90%, per-scenario cost rises from $87
to $140 and CFP slips by 4-6 months. This is the single biggest cost
risk in the model.

### B. Sales pipeline + conversion — 🟡 medium

- First paid pilot signed at month 7
- 3 paid customers by month 14, 6 by month 18
- Per-customer deal size $30-80K pilot, growing to $200-400K annual
- Sales cycle ~3-4 months from first conversation to PO

**What could break it:** Per the Q35 risk register, enterprise AV sales
cycles can be 6-9 months. If first pilot slips to month 10, runway is
tight but survivable; if it slips to month 14, the $2M pre-seed gets
stretched past its design point.

### C. ASP weighted average $200 — 🔴 low

- Mix of pilot tier ($339), Volume 1 ($200), Volume 2 ($150), Volume 3
  ($100) across the customer cohort
- Customers move down tiers as they scale → weighted average $200
- Discovery validated tolerance at $200-500/scenario but only as
  verbal interest; **no paid pilot has confirmed $200 yet**

**What could break it:** Customer price pressure at first pilot
negotiation. If the first 2 pilots land at $150-180, we update the
projection model and adjust raise / fleet ramp accordingly.

### D. Delivery rate / quality — 🟡 medium

- 50% of triggered missions actually deliver (sim mid-case)
- 95% of deliveries pass quality threshold
- 99.5% scene-class match

**What could break it:** Sim mid-case assumes ~90% pre-flight pass +
real weather + dock latch + quality. Real-world variance could push
this down to 30-40% delivery rate, halving revenue.

### E. Hardware reliability + dock R&D — 🟡 medium

- $150K + 6 months gets us a working custom dock
- 99% landing success rate by month 12
- Drone replacement cycle every 12-18 months
- No critical safety incidents

**What could break it:** Custom hardware R&D often takes 1.5-2× the
projected time. Dock latch reliability could be 90% not 99% in year 1,
forcing extra drone replacement spend. One serious incident (drone
flyaway into a car or person) could ground operations for weeks.

### F. Geographic + market — 🟢 high

- Bay Area-only through month 18
- No EU expansion
- Regulatory environment stable (no FAA Part 107 surprises)
- No corpus subscription revenue counted in base case

**What could break it:** Low probability but a Part 107 rule change
that affects sub-250g drone operations would force replanning. Tracking
the rulemaking pipeline.

### G. Team productivity — 🟡 medium

- 2 senior engineers + founder build the pipeline in 6 months
- 1 GTM hire enough sales capacity for 4-6 customers
- No critical attrition

**What could break it:** Hiring senior AV engineers in current Bay Area
market takes 3-6 months per hire and costs $250K+ loaded. If we miss
the eng hires by 3 months, build slips proportionally.

### H. Cloud + ML costs scale linearly — 🟢 high

- $0.80/scenario at any volume
- Storage growth manageable

**What could break it:** Low risk. Modern cloud has predictable
unit economics.

### I. Working capital / payment terms — 🟡 medium

- Net-30 to Net-60 customer payment terms standard
- No required vendor prepayment beyond initial drone procurement

**What could break it:** Enterprise customers often demand Net-90 or
quarterly billing. Could swing working capital needs by $100-200K.

### J. Macro / labor market — 🟢 high

- Bay Area engineer comp doesn't inflate beyond $250K loaded
- Drone hardware costs stable
- Insurance rates stable

**What could break it:** Insurance premiums for novel drone-mounted-on-
vehicle operations could be higher than $35K/year if underwriters classify
us as exotic. Recession would lower comp but also AV customer spend.

---

## 2. Does pre-seed get us to profitability before next raise?

Three perspectives — answers vary.

### Cash-flow positive (monthly operating cash > monthly costs)

**Yes, in honest case at month 16-18.** Per RAISE_SIZING.md analysis at
$200 weighted ASP:

| Milestone | Month | Cumulative cash with $2M raise |
|---|---|---|
| Pre-seed close | 0 | +$2.0M |
| MVP first capture | 4 | +$1.79M |
| First paid pilot signed | 7 | +$1.59M |
| Three-vehicle fleet operational | 11 | +$1.45M |
| Three paid customers | 14 | +$1.50M |
| **Cash-flow positive (M16-18 honest case)** | **16-18** | **+$1.89M** |
| 12 months past CFP | 30 | +$4.2M (if no expansion) |

**At M18, the business is self-sustaining.** No further capital is
required to keep operations running. The +$1.89M cash position covers
12 months of buffer at the M18 burn rate.

### GAAP net-profit positive

**Slightly later — month 18-22.** GAAP includes non-cash items like
depreciation of capex. With $497K in capex amortized over 3 years =
$165K/year non-cash expense, GAAP profitability lags CFP by ~3-4 months.
Still within the runway provided by the $2M raise.

### Self-sustaining for indefinite growth — 🚫 no, not at 6-vehicle scale

The pre-seed only funds the **6-vehicle Bay Area fleet**. Geographic
expansion (Phoenix Q4 27, Austin Q1 28, EU post-seed) requires more
capital:

- Phoenix expansion: ~$300K capex + $150K/year operating ramp = $450K-700K
- Austin expansion: similar $450K-700K
- EU expansion: $1-2M+ given regulatory work
- Corpus subscription product: $500K-1M in engineering + sales

**Conclusion**: Pre-seed pays for survival + initial market dominance.
**Seed round is needed for expansion + product growth**, but not for
survival of the core business.

---

## 3. The strategic implication: seed becomes optional

This is the most important finding. Most pre-seed startups have:
- Pre-seed → 12-18 months runway → must raise seed or die

Skydock at $2M pre-seed has a different structure:
- Pre-seed → 16-18 months → CFP + $1.89M cash → **choice**

The choice:

| Path | What it means | Outcome |
|---|---|---|
| **Bootstrap** | Stay at 6-vehicle Bay Area, grow revenue from delivered scenarios | Founder retains ownership, slower geographic expansion, no investor pressure to over-scale |
| **Raise seed (~$5-10M)** | Phoenix Q4 27 + Austin Q1 28 + corpus subscription product + team to 15-20 FTE | Hit larger market faster, accept dilution + board structure |
| **Bridge** | Smaller $2-3M bridge round at CFP milestone to ease seed-to-seed gap | Half-step expansion, minimal dilution, optionality preserved |

The pre-seed buys us into a position where we **negotiate seed from
strength** (or skip it entirely). Most pre-seed founders don't get
that option.

---

## 4. What we'd tell investors honestly

The pitch to a pre-seed investor:

> "$2M pre-seed funds us to cash-flow positive on a 6-vehicle Bay Area
> fleet by month 16-18, with $1.89M cash position remaining at that
> milestone. We don't *need* to raise a seed round — we can bootstrap
> further or raise seed for expansion at month 18-24, our choice. The
> business is self-sustaining at CFP."

Honest caveats to add:

> "Five assumptions could shift this timing by 4-8 months: (1) operator
> utilization year-1, (2) first paid pilot timing, (3) ASP at first
> pilot negotiation, (4) hardware reliability, (5) sales cycle length.
> The $2M raise has $1.24M of buffer for these slip risks. The
> pessimistic case (all five slip) pushes CFP to month 21-22 — still
> within runway. The mid-case puts CFP at month 14-15 with $2.5M+ cash
> at M18."

This is the version of the story that survives FP&A scrutiny.

---

## 5. Comparison to typical pre-seed startups

For context — what does the typical pre-seed startup look like?

| Metric | Typical pre-seed | Skydock |
|---|---|---|
| Raise size | $500K - $2M | $2M |
| Time to CFP | Never (most fail or raise seed) | 16-18 months |
| Dependence on seed | High — must raise seed to survive | Low — seed for expansion only |
| Pre-revenue period | 12-18 months | 6 months |
| Revenue at month 18 (if any) | $0 - $500K | $2.3M honest / $5.9M mid |
| Dilution at first round | 15-25% | 17% |

Skydock looks more like a **services + capex business with software
gross margins** than a typical software startup. The shape of the
financial model is unusual — operationally-leveraged, capex-heavy,
revenue-positive earlier than software peers.

This is both a feature (resilience, faster path to self-sustainability)
and a bug (lower IRR per dollar deployed than software, harder to raise
"venture scale" rounds later because investor-class fit is awkward).

---

## 6. Three questions to flag to investors

1. **"How would you change the plan if first pilot lands at $150 ASP?"**
   Answer: Slow capex (4 vehicles not 6 by M18), still CFP at M22, but
   ARR trajectory shifts down.

2. **"What's the worst-case scenario, and what does it cost?"**
   Answer: Pessimistic case (ASP $150 + MVP slip) puts CFP at M21-22
   with $360K negative cash at M18. Within the $2M raise buffer, but
   uncomfortably close. Would consider $300-500K bridge at M18 if
   pessimistic-case signals are clear by M14-15.

3. **"How does this story end — IPO, acquisition, bootstrapped
   profitable company?"**
   Honest answer: Acquisition is the most likely path. Acquirers:
   AV companies vertically integrating (Waymo, Cruise), AV data
   services consolidators (Scale AI), automotive mapping (HERE,
   TomTom), defense ISR-adjacent (Palantir, Anduril). Acquisition
   multiples for services businesses are 5-10× ARR vs 20-40× for
   software, so target acquisition price at $15M ARR (year 4-5
   honest case) = $75M-$150M.

---

*v1, May 2026. Update after first 3 customer-discovery conversations
land — those will tighten the ASP and sales-cycle assumptions
(currently the lowest-confidence inputs).*
