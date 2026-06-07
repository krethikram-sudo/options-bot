> ⚠ **STALE — V1 ARCHITECTURE.** This document sizes the V1 mobile-dock
> raise at $2.0M based on the audited V1 cost model. The V2 fixed-point
> architecture replaced V1 in May 2026 and the V2 raise is $2.2M per
> V2_FINANCIAL_MODEL.md. V2 has materially different burn timing,
> capex profile, and revenue ramp. Kept for historical context on raise
> sizing methodology.

---

# Pre-seed raise sizing — honest re-derivation post-audit

Internal. Builds on COST_MODEL_AUDIT.md. The prior PITCH.md claim was
$1.7M based on a model that under-counted labor by ~$700K/year. This
doc re-derives the right raise size with the audit-adjusted cost
model, presents three scenarios with explicit tradeoffs, and gives a
recommendation.

**TL;DR:** Recommended raise: **$2.0M** (range $1.8M-$2.2M). Covers
honest trough burn of ~$1M with ~$1M buffer for slips, working capital,
and optionality. The prior $1.7M was approximately right *by accident*
— the original justification under-stated burn but also over-stated
revenue capture in the early periods.

---

## 1. Monthly burn projection through month 18

Using honest loaded comp (**$200K founder cash-loaded** = $150K cash + $50K benefits/payroll tax under Option C hybrid; $250K senior eng, $220K GTM, $160K CS, $80K operator-driver), plus contractor / capex / overhead per the audit.

**Founder comp under Option C hybrid (recommended)**: $150K cash to founder ($16.7K/mo on P&L) + $50K/year accrued as deferred compensation liability on balance sheet (payable upon seed close, M&A, or M24). Total comp $200K/year, cash impact $150K/year. Saves $50K/year cash vs Option A (all-cash $200K), accumulating $75K deferred liability through M18.

| Phase | Months | Recurring monthly (cash) | Capex this phase | Phase cost | Revenue @ $339 ASP | Revenue @ $200 weighted |
|---|---|---|---|---|---|---|
| Build P1 | 1-3 | $60K (founder + 2 contractors + minimal ops) | $5K (parts/setup) | $185K | $0 | $0 |
| MVP P2 | 4-6 | $62K (+ 2 operators part-time) | $57K (1 vehicle + 1 rig) | $243K | $0 | $0 |
| Pilot P3 | 7-9 | $82K (+ 1st eng hire, marketing starts) | $57K (1 vehicle + 1 rig) | $303K | $200K | $118K |
| Scale P4 | 10-12 | $70K (3-vehicle fleet ops) | $57K (1 vehicle + 1 rig) | $267K | $500K | $295K |
| Ramp P5 | 13-15 | $132K (+ GTM + 2 eng + 3 ops + 0.5 CS) | $114K (2 vehicles + 2 rigs) | $510K | $1.4M | $826K |
| Mature P6 | 16-18 | $153K (full 6-vehicle fleet + team) | $57K (1 vehicle + 1 rig) | $516K | $1.8M | $1.06M |
| **Total 18mo** | | | **$347K capex** | **$2.02M** | $5.9M | $2.30M |

Off-balance-sheet: **$75K founder deferred comp liability** at M18 (paid from seed proceeds at M22-24, or M24 if no seed).

*~$140K cash reduction from original $300K-loaded plan; $75K cash reduction vs Option A (all-cash $200K) by deferring half of founder comp.*

## 2. Cumulative cash analysis

The raise covers the negative-cash window. Trough = deepest negative
cumulative cash position.

### Mid-case ($339 ASP throughout, Option C founder comp):

| End of period | Period net | Cum cash |
|---|---|---|
| Month 3 | −$185K | **−$185K** |
| Month 6 | −$243K | −$428K |
| Month 9 | −$103K | −$531K ← **trough** |
| Month 12 | +$233K | −$298K |
| Month 15 | +$890K | +$592K |
| Month 18 | +$1.28M | +$1.87M |

Trough: **−$531K at end of month 9** (mid case). Raise needed: $531K + buffer.

*Plus $75K deferred comp liability paid at seed close.*

### Honest case ($200 weighted ASP, Option C founder comp):

| End of period | Period net | Cum cash |
|---|---|---|
| Month 3 | −$185K | **−$185K** |
| Month 6 | −$243K | −$428K |
| Month 9 | −$185K | −$613K |
| Month 12 | +$28K | −$585K ← **trough** |
| Month 15 | +$316K | −$269K |
| Month 18 | +$544K | +$275K |

Trough: **−$613K at end of month 9** (honest case). Raise needed: $613K + buffer.

*Plus $75K deferred comp liability accrued through M18, paid at seed close or M24.*

### Pessimistic case ($150 weighted ASP + 6-month MVP slip):

If MVP reliability lands below target and ASP comes in below the
weighted band:

| End of period | Period net | Cum cash |
|---|---|---|
| Month 3 | −$204K | −$204K |
| Month 6 | −$267K | −$471K |
| Month 9 | −$239K (lower rev) | −$710K |
| Month 12 | −$50K | −$760K |
| Month 15 | +$98K | −$662K ← **trough recovers slowly** |
| Month 18 | +$305K | −$357K |
| Month 21 | +$420K | +$63K |
| Month 24 | +$420K | +$483K |

Trough: **−$760K at end of month 12, CFP slips to month 21-22**. Raise
needed: $760K + buffer for the extended runway.

## 3. The three raise-size scenarios

### Scenario A — $1.5M raise (lean)

- Covers trough of $613K (honest case) with $887K buffer
- Headroom: ~14 months of slip absorption
- Risk: if pessimistic case hits (−$668K trough), buffer drops to $832K — still survivable but less comfortable
- Dilution at $7.5M post-money: ~17%
- **Best for**: high-conviction founder who's confident on $200K founder comp + lean ops

### Scenario B — $2.0M raise (recommended)

- Covers trough of $668K (pessimistic case) with $1.33M buffer
- Headroom: ~20 months of slip absorption
- Sufficient runway to reach CFP under pessimistic ASP + extended-MVP slip
- Allows pulling founder comp toward market rate at month 15+ if traction supports it
- Allows seizing 1-2 unexpected hires or geographic expansion opportunity
- Dilution at $10M post-money: ~17%
- **Best for**: prudent reserve against the realistic risk set; preserves optionality for founder comp adjustment + expansion

### Scenario C — $2.5M raise (cushioned)

- Trough + $1.83M buffer
- Could pull CFP forward by 1-2 months via earlier eng hires
- Could fund partial Phoenix expansion before seed round
- Could survive a 12-month sales-cycle slip with no panic
- Allows founder comp at market rate ($300K) from month 6+
- Dilution at $12.5M post-money: ~20%
- **Best for**: investor preference for more cash + greater optionality

## 4. Why $2.0M is the recommendation

Three reasons:

1. **The pessimistic case isn't tail-risk; it's plausible.** ASP at $150 (40% probability per Q22 sensitivity) and MVP reliability slip (30% probability per Q35) together hit a meaningful conjunction probability (~12%). Need the runway to survive both happening.

2. **Pre-seed → seed bridges work better with cash to spare.** When raising seed in month 18-20, having 6+ months of runway in the bank is the difference between negotiating from strength and accepting any term sheet. $1.5M leaves you negotiating on fumes if revenue ramps slowly.

3. **$2.0M is a clean round size.** SAFEs at $10M post-money cap is a standard pre-seed structure. Smaller rounds ($1.5M) often get pushed up by interested investors anyway; might as well plan for $2M from the start.

## 5. What the $2.0M deploys against

Honest 18-month deployment:

| Category | $ over 18 months | Note |
|---|---|---|
| Founder + 2 eng + 1 GTM + 0.5 CS labor | $1.2M | Scaling from 1 → 4.5 FTE |
| 4 operator-drivers (ramping) | $250K | From 0 to 4 FTE over months 5-16 |
| 6 vehicles + 6 rigs + dock R&D | $497K | Capex spread Q2 → Q6 |
| Cloud / ML / tooling | $80K | Scales with operations |
| Insurance / legal / office / admin | $180K | Steady-state ramp |
| Marketing / sales / events | $120K | Conference presence, content, GTM tooling |
| Variable operating (fuel, drone wear) | $80K | Scales with delivery volume |
| **Total deployed** | **$2.41M** | |
| **Revenue captured (honest weighted ASP)** | **$2.30M** | Per Phase 3-6 |
| **Net cash position end of M18** | **−$110K** | Without buffer |
| **With $2.0M raise** | **+$1.89M** | Cash in bank end of M18 |

Cash position end of M18 with $2.0M raise: **+$1.89M**. That's 12 months
of operating runway at the M16-18 burn rate of $161K/month — substantial
bridge to seed if needed.

## 6. Comparison to prior $1.7M claim

| Metric | Prior PITCH.md (Q21) | Honest model |
|---|---|---|
| Total 18-month cost | $2.1M (low) | $2.16M (similar) |
| Total 18-month revenue | $5.7M (overstated) | $2.30M (honest) |
| Trough cumulative cash | −$415K | −$760K |
| Recommended raise | $1.7M | $2.0M |
| End-of-M18 cash with raise | $4.99M (too high) | $1.89M (realistic) |

The cost numbers were close; revenue projections were the major source
of the prior over-statement. The PR-FAQ Q21 implicitly assumed all
revenue would land at pilot-tier $339 ASP, which doesn't survive contact
with volume-tier customers.

## 7. What goes into the pitch

Updated headline: **"Raising $2M pre-seed to fund the negative-cash
window through CFP. Buffer for ASP slip, MVP reliability slip, and 12+
months of seed-bridge optionality."**

Use of funds breakdown for investors:
- 60% labor (founder + 3-4 hires + operators)
- 20% capex (6 vehicles + 6 rigs + dock R&D)
- 10% overhead (insurance, office, admin, legal)
- 5% sales + marketing
- 5% variable operating + buffer

## 8. Sensitivity — what would change the answer

| If this changes... | Raise should move to... |
|---|---|
| ASP weighted lands at $250+ (more pilots stay at pilot tier) | $1.7M (mid case) |
| ASP weighted lands at $150 (price pressure earlier) | $2.3M |
| MVP reliability hits 90%+ at month 5 (early product confidence) | $1.5M |
| Hardware contractor needs 1.0 FTE instead of 0.5 | $2.2M |
| First paid pilot signs at month 10 instead of month 7 | $2.3M |
| Bay Area + Phoenix simultaneous launch | $3.0M |

## 9. Risks to flag in the pitch

The honest pre-seed pitch needs to surface:

1. **"$2.0M is a 4-vehicle plan, not a 6-vehicle plan."** The 6-vehicle
   target relies on early revenue compounding. If revenue slips, we
   slow capex to maintain runway.
2. **"CFP at month 16-18 assumes weighted ASP $200."** If pricing is
   tougher, CFP slips to month 22-24 — within the raised runway, but
   we'd want to brief investors on this.
3. **"Operator utilization is the dominant cost driver year-1."** Per
   the audit, low utilization in year-1 ramp pushes per-scenario cost
   to $120-140 not $87. We'd communicate ramp curve transparently.

---

## 10. Concrete recommendation

**Raise $2.0M pre-seed on a SAFE at $10M post-money cap.**

- $2.0M is the right number based on honest cost model + pessimistic-case
  trough analysis + 12-month bridge optionality.
- $10M post-money is standard for pre-seed in this space (pre-Series A
  enterprise data + ops business).
- 17% dilution is appropriate for the stage.
- Use-of-funds breakdown above is defensible against investor scrutiny.

The prior $1.7M claim in PITCH.md should be updated to $2.0M with the
honest re-derivation. Other PR-FAQ sections (Q21 financials, Q33
resourcing) need a small refresh to match the labor numbers from the
audit.

---

*v1, May 2026. Update when first paid pilot signal lands (informs ASP
sensitivity) or when MVP reliability data is available (informs
utilization sensitivity).*
