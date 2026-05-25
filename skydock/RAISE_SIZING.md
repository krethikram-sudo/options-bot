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

Using honest loaded comp ($300K founder, $250K senior eng, $220K GTM,
$160K CS, $80K operator-driver), plus contractor / capex / overhead per
the audit.

| Phase | Months | Recurring monthly | Capex this phase | Phase cost | Revenue @ $339 ASP | Revenue @ $200 weighted |
|---|---|---|---|---|---|---|
| Build P1 | 1-3 | $68K (founder + 2 contractors + minimal ops) | $5K (parts/setup) | $204K | $0 | $0 |
| MVP P2 | 4-6 | $70K (+ 2 operators part-time) | $57K (1 vehicle + 1 rig) | $267K | $0 | $0 |
| Pilot P3 | 7-9 | $90K (+ 1st eng hire, marketing starts) | $57K (1 vehicle + 1 rig) | $327K | $200K | $118K |
| Scale P4 | 10-12 | $78K (3-vehicle fleet ops) | $57K (1 vehicle + 1 rig) | $291K | $500K | $295K |
| Ramp P5 | 13-15 | $140K (+ GTM + 2 eng + 3 ops + 0.5 CS) | $114K (2 vehicles + 2 rigs) | $534K | $1.4M | $826K |
| Mature P6 | 16-18 | $161K (full 6-vehicle fleet + team) | $57K (1 vehicle + 1 rig) | $540K | $1.8M | $1.06M |
| **Total 18mo** | | | **$347K capex** | **$2.16M** | $5.9M | $2.30M |

## 2. Cumulative cash analysis

The raise covers the negative-cash window. Trough = deepest negative
cumulative cash position.

### Mid-case ($339 ASP throughout):

| End of period | Period net | Cum cash |
|---|---|---|
| Month 3 | −$204K | **−$204K** |
| Month 6 | −$267K | −$471K |
| Month 9 | −$127K (revenue starts) | −$598K ← **trough** |
| Month 12 | +$209K | −$389K |
| Month 15 | +$866K | +$477K |
| Month 18 | +$1.26M | +$1.74M |

Trough: **−$598K at end of month 9**. Raise needed: $600K + buffer.

### Honest case ($200 weighted ASP):

| End of period | Period net | Cum cash |
|---|---|---|
| Month 3 | −$204K | **−$204K** |
| Month 6 | −$267K | −$471K |
| Month 9 | −$209K | −$680K |
| Month 12 | +$4K | −$676K ← **trough** |
| Month 15 | +$292K | −$384K |
| Month 18 | +$520K | +$136K |

Trough: **−$680K at end of month 12**. Raise needed: $680K + buffer.

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

- Covers trough of $680K (honest case) with $820K buffer
- Headroom: ~12 months of slip absorption
- Risk: if pessimistic case hits, runway gets tight by month 18 — would need bridge financing
- Dilution at $7.5M post-money: ~17%
- **Best for**: high-conviction founder who'd rather take less capital and execute fast

### Scenario B — $2.0M raise (recommended)

- Covers trough of $760K (pessimistic case) with $1.24M buffer
- Headroom: ~18 months of slip absorption
- Sufficient runway to reach CFP under pessimistic ASP + extended-MVP slip
- Allows seizing 1-2 unexpected hires or geographic expansion opportunity
- Dilution at $10M post-money: ~17%
- **Best for**: prudent reserve against the realistic risk set

### Scenario C — $2.5M raise (cushioned)

- Trough + $1.74M buffer
- Could pull CFP forward by 1-2 months via earlier eng hires
- Could fund partial Phoenix expansion before seed round
- Could survive a 12-month sales-cycle slip with no panic
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
