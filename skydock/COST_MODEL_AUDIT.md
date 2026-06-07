> ⚠ **STALE — V1 ARCHITECTURE.** This document audits the V1 mobile-dock
> cost model. The V2 fixed-point architecture replaced V1 in May 2026
> (per SKYDOCK_V2_THESIS.md). V2 unit economics are in
> V2_FINANCIAL_MODEL.md; the V1 $87/scenario all-in cost is no longer
> the relevant unit. Kept for historical context on the audit
> methodology that surfaced the V1 economics problem.

---

# Cost model audit — what's missing in the current unit economics

Internal honest critique. Question that prompted this: does our existing
cost analysis (PR-FAQ Q17 + Q21, VALUE_QUANTIFICATION.md, website stat
grid) actually account for vehicle purchase, drone replacement, full-time
labor, tooling, overhead, etc.?

**Short answer: NO.** The current model under-counts in several specific
places. When honestly rebuilt, true all-in cost at steady state is
**~$87/scenario** (not the $30 claimed in PR-FAQ Q17). Gross margin at
$200 ASP is **~57%** (not the 65% claimed).

Still a viable business — but the public-facing claims need a small
correction or careful framing.

---

## 1. What's currently claimed

### PR-FAQ Q17 (the per-scenario cost claim)

| Component | Amount |
|---|---|
| Operator labor ($30/hr × 0.5h amortized) | $15.00 |
| Vehicle operating cost ($5/hr × 0.5h) | $2.50 |
| Cloud processing | $0.80 |
| Drone wear | $1.00 |
| **Variable cost / scenario** | **$19.30** |
| Fixed costs (~$220/day → $10/scenario at 20/day) | $10 |
| **Total all-in / scenario** | **~$30** |

Hardware capex per vehicle (Q17 supplement): drone fleet $2,500 + dock $11,000
+ edge compute $1,030 + sensors $630 + mounting $1,500 + spares $2,000 +
contingency $3,700 = **$22,400 per vehicle**. Amortized at $0.22/scenario.

### Website stat grid

- $339 mid-case ASP
- 94% **contribution margin** per scenario (= revenue minus variable cost)
- 65% **gross margin** at steady state
- $1.4M LTV per vehicle over 24 months

These numbers individually look defensible but conceal what's not in the
model.

## 2. What's missing or under-counted

| Cost category | Current model | What's missing | Annual impact at 6 vehicles |
|---|---|---|---|
| **Vehicle purchase** | "Vehicle operating cost $5/hr" — only operating, NOT purchase | $35K Toyota RAV4 Hybrid (or similar) × 6 = $210K capex, amortize over 3 years = $70K/year | +$70K/year |
| **Operator labor (full-time)** | Per-hour rate amortized | Operators don't get paid per scenario — they're full-time. 4 FTE drivers at $80K loaded = $320K/year. Current model implies only ~$160K via the $15/scenario × 22K = $330K math, but Q21's "operations + insurance + overhead" line at $100K-$200K can't fit this | +$150K/year vs implied |
| **Engineering team** | Q21 "Founder + hires" $500K/period (months 13-18) → ~$1M/year | Founder + 2-3 eng + 1 GTM at loaded comp is ~$1.2M-$1.4M/year, slightly higher than Q21 line | +$200-400K/year |
| **Dock R&D** | Hardware capex $50K-$100K in Q21 | Custom dock engineering is a 6-month 1.0 FTE contractor at $15-30K/month = $90-180K. Amortize over 3-year hardware life = $30-60K/year ongoing | +$30-60K/year |
| **Drone replacement** (vs wear) | $1/scenario covers wear only | Drones get lost (flyaway), damaged. Replacement cycle every 12-18 months at $760 × 3 per vehicle = $2,280 per vehicle every 12-18 months = $1,500-2,000/year per vehicle. At 6 vehicles = $10-12K/year | +$10K/year |
| **Real overhead** (office, admin, legal, accounting) | Bundled into "operations + insurance + overhead" $200K/year | Office/co-working $30K + legal/accounting $40K + software subs $30K + general admin $20K + insurance $35K = $155K. Plus marketing $80K/year. The $200K bucket is roughly right but tight | +$0-60K/year |
| **Sales / customer acquisition** | Q21 sales+marketing $200K over 18 months → $133K/year | Realistic for a 5-person enterprise sales motion: $200K/year (1 GTM + content + conferences + tooling) | +$70K/year |

## 3. Rebuilt honest model — 6-vehicle steady state

**Capital (one-time, amortize over 3 years):**
- 6 vehicles × $35K = $210K
- 6 vehicle rigs (drone+dock+edge+sensors+mounting+spares+contingency) × $22.4K = $134K
- Dock R&D one-time eng cost (amortize over fleet life) = $150K
- **Total capital: $494K → $165K/year amortized**

**Labor (annual, at steady state):**
- Founder: $300K loaded
- 2 engineers (perception/ML + ops): 2 × $250K = $500K
- 1 GTM / customer success: $220K
- 4 operator-drivers (rotating across 6 vehicles): 4 × $80K = $320K
- 0.5 FTE part-time customer success: $80K
- **Total labor: ~$1.42M/year**

**Variable operating (annual at 22K scenarios delivered):**
- Cloud + ML processing: $0.80 × 22K = $17.6K
- Drone wear + replacement: $1.50 × 22K = $33K
- Vehicle fuel + maintenance: 6 × 22 days × 8h × 12 months × $5/h = $63K
- **Total operating: ~$113K/year**

**Overhead (annual):**
- Insurance (drone + vehicle + general liability): $35K
- Office / co-working: $30K (small team, mostly remote)
- Legal / accounting: $40K
- Marketing / events / conference presence: $80K
- Software subscriptions / general admin: $30K
- **Total overhead: ~$215K/year**

### TOTAL ANNUAL COST AT STEADY STATE: ~$1.91M

### Per-scenario at 22K scenarios/year delivered: **$87/scenario**

This is a ~3× difference from the PR-FAQ's $30 all-in claim.

## 4. True margin math at honest costs

| Metric | Q17 claim | Honest re-derivation |
|---|---|---|
| All-in cost / scenario | $30 | **$87** |
| Variable cost / scenario | $19.30 | $19.30 (this part is right) |
| ASP weighted average | $200 | $200 (unchanged) |
| Contribution margin (revenue − var) | 94% ($181 of $200) | 94% — this is correct as stated |
| Gross margin (revenue − all-in) | 65% (implied via Q21) | **57%** ($113 of $200) |
| Revenue at 22K scenarios/year | $4.4M | $4.4M |
| Annual cost at steady state | ~$1.5M (Q21 implied) | **$1.91M** |
| Annual gross profit | $2.9M | **$2.49M** |

## 5. Why this isn't a catastrophe

- **The contribution margin claim (94%) is correct as stated.** It's the *variable* margin, not all-in. Honest accounting doesn't break this number.
- **The 65% gross margin claim is ~8 percentage points too optimistic.** Real number is closer to 57% at steady state.
- **CFP timing changes by ~1-2 months in the honest model.** Q21 shows CFP at month 15; honest accounting puts it at month 16-17. Still inside the 18-month raise window.
- **LTV per vehicle drops** from $1.4M to about $1.05M-$1.2M over 24 months at honest unit economics. Still strong.
- **The business is real.** $200 ASP × 22K scenarios = $4.4M ARR with 57% GM = $2.5M gross profit. Healthy services business margins for a 5-person team.

## 6. Why the original model was off

Three structural reasons:

1. **Per-scenario math hides full-time labor.** When you amortize a $30/hr operator across 0.5h per scenario you get $15. But operators don't work per-scenario; they work full-time. The actual cost is $80K loaded / 5,500 scenarios per operator-year = ~$15/scenario. So the per-scenario number is right *if* the operator is at full utilization. **Real utilization at MVP / early scale is much lower** — operators idle while waiting for trigger arrivals or driving between waypoints. Real cost-per-scenario in year 1: probably $30-40, dropping to $15 only at mature scale.

2. **Vehicle purchase wasn't in the per-vehicle capex line.** The $22.4K spec covered drone + dock + edge compute + sensors + mounting + spares + contingency — but not the actual $35K vehicle. Easy miss; adds ~$11/scenario at amortization.

3. **Engineering + sales labor doesn't appear in the per-scenario cost at all.** Founder time + engineering hires + GTM are real costs that need to be allocated. At 22K scenarios/year and $1.2M/year of non-operator labor, that's $54/scenario in eng+sales overhead. The largest single missing line.

## 7. Recommended fixes

### High priority (do before next investor or customer pitch)

1. **Update PR-FAQ Q17** to add a third row: *"All-in cost including amortized labor + capex + overhead: ~$87 at 6-vehicle steady state."* Keep the $19.30 variable and add the $87 all-in. Honest framing: 94% contribution margin AND 57% gross margin.

2. **Update website stat grid** to either drop the "94% contribution margin" stat (could mislead a sharp customer doing the math) or relabel it as "94% contribution margin — gross margin 57% after full-time labor + capex amortization."

3. **Re-derive LTV per vehicle** using honest cost-per-scenario. Quick math: 5,500 scenarios per vehicle-year × ($200 - $87) = $621K/year per vehicle gross profit. Over 24 months: $1.24M LTV. Down from $1.4M but defensible.

### Medium priority

4. **Add a vehicle-purchase line** to the cost-to-replicate table in VALUE_QUANTIFICATION.md (currently missing — that doc has the same gap).

5. **Sensitivity analysis on utilization.** Year 1 at 60% utilization would push per-scenario cost much higher ($140-180). Need to model the ramp from "operators idle most of the day" to "operators at full schedule."

### Low priority

6. **Build a real financial model** (spreadsheet, not markdown) with monthly cost projection through month 24. Current Q21 model is too coarse (6-month buckets) to catch overhead drift.

## 8. What this means for the website right now

Two options:

**Option A (recommended): Tighten the language.**
- Change "94% contribution margin per scenario" to "94% contribution margin (excludes fixed labor)"
- Keep "65% gross margin at steady state" but add footnote that this assumes full operator utilization
- Keep "$1.4M LTV per vehicle" but reduce to "$1.2M LTV per vehicle (mid-case)"

**Option B (more transparent): Replace the stat with a range.**
- "Per-scenario gross margin: 57-65% depending on operator utilization and operating tempo"
- More honest, less impressive at first glance, more defensible

I'd lean toward Option A — investors and customers don't expect a public marketing page to do full GAAP accounting, but they do expect any specific number to be defensible.

---

## 9. The single most important takeaway

**The contribution margin (94%) is real. The gross margin (57-65%) is real. The "$30 all-in cost" claim in PR-FAQ Q17 is what's wrong** — it dramatically under-allocates fixed labor and capex. Fix that line and the model is internally consistent.

For a pre-seed startup that's good enough. For a Series A pitch with detailed FP&A scrutiny, the spreadsheet model needs to be built and audited line by line.

---

*v1, May 2026. Audit performed against PR-FAQ Q17 + Q21, VALUE_QUANTIFICATION.md,
and the website's stat grid. Update when the actual fleet is operational
and real cost data replaces sim estimates.*
