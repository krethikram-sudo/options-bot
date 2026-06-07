> ⚠ **STALE — V1 ARCHITECTURE.** This document plans the V1 mobile-dock
> 18-month rollout (6-vehicle Bay Area fleet). The V2 fixed-point
> architecture replaced V1 in May 2026. Current execution plan is
> V2_EXECUTION_PLAN.md (7 fixed-point sites, curation pipeline build,
> BVLOS waiver work, library subscription product). V2 hiring sequence
> shifts engineering-heavy from V1's operator-driver-heavy structure.
> Kept for historical context on operating-plan methodology.

---

# Skydock execution plan — now → pre-seed → 18 months → seed

Internal operating plan. End-to-end from current discovery state through
seed round close ~24 months out.

**Top-of-doc summary:**

| Phase | Months | Goal | Money | Headcount end |
|---|---|---|---|---|
| **Phase 0** | Now → −1 | Customer discovery + investor prep + MVP technical proof | $0 (founder bootstrapping) | 1 (founder) |
| **Phase 1** | 0 | Pre-seed close | +$2.0M | 1 founder + contractors |
| **Phase 2** | 1-6 | MVP build, first capture, prospect reviews | −$471K cumulative | 1 + 2 contractors |
| **Phase 3** | 7-12 | First paid pilots, 3-vehicle fleet operational | Trough at M12: −$680K | 1 + 1 eng + 2 ops + contractor |
| **Phase 4** | 13-18 | Scale to 6 vehicles + CFP achieved | CFP at M16-18, +$1.89M cash at M18 | 1 + 2 eng + 1 GTM + 4 ops + 0.5 CS |
| **Phase 5** | 18-22 | Seed round + multi-market prep | $1.89M decreasing, seed close at M22 | Same as above |
| **Phase 6** | 22-24 | Seed close, Phoenix launch begins | +$5-10M | 10-12 FTE |

---

## Product catalog (what we're building toward)

Per the customer-facing site's Order options section, the productized SKUs
we're operationalizing through the 18-month plan:

| Tier | Pack | Scenarios | Price | Per scenario |
|---|---|---|---|---|
| Pilot | Discovery Pack (single scene class) | 50 | $17,000 | $340 |
| Pilot | Validation Library Sampler (mixed, recommended first pilot) | 100 | $33,900 | $339 |
| Pilot | VRU Safety / Intersection Behavior Pack | 100 | $33,900 | $339 |
| Volume 1 | Library Foundation | 250-500 | from $50,000 | $200 |
| Volume 2 | Production Corpus | 500-1,000 | from $100,000 | $150 |
| Volume 3 | Enterprise | 1,000+ | contact us | $100 |

Custom captures, add-ons (raw 4K video, exclusive licensing, expedited
delivery), and integration services priced separately. See website
[Order options](../site/src/pages/index.astro) section.

This product structure shapes the rest of the plan:
- **Phase 2-3 must support all 6 pack SKUs** in the delivery pipeline by
  first paid pilot
- **Phase 3 first pilots = Discovery Packs or Validation Samplers** (not
  custom-negotiated deals)
- **Phase 4 revenue grows via pack-mix evolution** (customers move from
  pilot → volume tiers, plus net-new customers entering at pilot)

---

## Phase 0: Now → month 0 (pre-raise)

**Goal**: validate enough of the thesis to close pre-seed cleanly.

### Customer discovery — primary activity

Per DISCOVERY_PLAN.md. Target outcomes by end of Phase 0:
- 15-20 conversations with named AV scenario engineering / prediction / validation leads (Tier 1 + Tier 1b + Tier 2)
- 3-5 leads confirmed at "would do a paid pilot subject to MVP delivery"
- 2-3 leads confirmed at "would commit a pilot $25-80K when you're ready"
- Verbal commitment from 1+ design partner

**Why this matters for the raise**: investors weigh "I talked to 15 customers and 5 said they'd buy" 10× more than they weigh "I built a sim model that says $339 ASP." The conversations are the unlock.

### MVP technical proof — secondary

Already have: 7K-line simulation with full unit economics, OpenSCENARIO output, brief.py auto-generator. Strong artifact for investor demos.

Optional add before raise (if time permits):
- 3D-printed dock concept prototype (visual prop for investor meetings, $1-3K)
- Sample OpenSCENARIO package downloadable from website (replaces "request a sample" friction)
- 5-minute founder demo video walking through sim + delivery package

### Investor pipeline build

Target: 50-80 investor conversations during the 8-12 week raise period.

Categories to target:
1. **Pre-seed funds focused on hard tech / vertical SaaS / operations** (~30 contacts): Founders Fund Pre-seed, Floodgate, K9 Ventures, Bloomberg Beta, Wing Venture Capital, BoxGroup, NEA Seed
2. **Specialist AV / mobility funds** (~15 contacts): Autotech Ventures, Trucks Venture Capital, Compound, Vela Partners
3. **Angels with AV / robotics / data background** (~20 contacts): network-driven, founder-led outreach
4. **Strategic angels** (~5 contacts): senior people at Applied Intuition, Foretellix, Parallel Domain, Waymo, etc. — value beyond capital

Tactical:
- Week 1-2: Build investor target list, write outreach scripts
- Week 3-6: Cold outreach, founder-led intros, first meetings
- Week 7-10: Term sheet conversations, due diligence
- Week 11-12: Close, wire funds

### Legal + admin prep

- Delaware C-corp formation if not done
- SAFE template ready (YC standard or Wilson Sonsini)
- Vesting schedules for founder + key hires
- Bank account at SVB / Mercury / Brex
- Bookkeeping setup (Pilot / Bench / Bench.co)
- IP assignment from prior contractor work

### Founder time allocation (Phase 0)

- 50% customer discovery (conversations, follow-ups, scoring)
- 30% investor outreach + meetings
- 15% MVP technical work + sample artifacts
- 5% legal + admin

### Phase 0 exit criteria → ready to close raise

- ≥3 customers verbally committed to paid pilot when MVP ready
- ≥1 investor at term sheet stage
- Legal entity + SAFE + bank ready to receive funds
- Founder bio + website + pitch deck final
- Sample OpenSCENARIO package downloadable

---

## Phase 1: Month 0 (pre-seed close)

**Goal**: $2.0M wire transferred. Operating clock starts.

**Key activities (1-3 weeks)**:
- Final negotiations, signed SAFEs
- $2M wire received, deposited
- Founder transitions from "raising" to "executing"
- Announce raise publicly (if appropriate — investor-dependent)
- Begin hardware contractor recruiting

**Founder time**: 100% executing, exit fundraising mode.

---

## Phase 2: Months 1-6 (MVP build)

**Goal**: First scenario delivered to a prospect for review by month 5-6.

### Month 1
- Hire hardware contractor (0.5-1 FTE) for custom dock design — $20K/month
- Hire ML/pipeline contractor (0.5 FTE) for cloud pipeline — $10K/month
- Procure first vehicle (Toyota RAV4 Hybrid ~$35K)
- Procure first drone fleet (3× DJI Mini 4 Pro ~$2.5K)
- Founder gets FAA Part 107 certified ($175 exam + study)
- Commercial drone insurance secured ($1.5K/year)
- Set up Bay Area home base for fleet operations

### Month 2-3
- Custom dock CAD design + prototype build
- Cloud pipeline architecture: S3 ingest → BEV transform → YOLOv8 + ByteTrack → OpenSCENARIO export
- First dock prototype tested in lab (drone launch + return + latch)
- Continue customer discovery in parallel (~2 conversations/week)
- Begin operator-driver recruiting (job posts, ride-share-platform poaching)

### Month 4
- First field-mounted dock on vehicle
- First end-to-end test: trigger → launch → climb → capture → return → land → process → deliver package
- 1-2 operators hired part-time (months 4-5 start) at $7K/month each
- Resolve top hardware reliability issues from first field test
- First scenario package emitted to internal QA review

### Month 5
- First scenarios delivered to 2-3 prospect customers for offline review (no charge)
- Begin negotiating first paid pilot — focus on **Validation Library Sampler ($33.9K, 100 mixed scenarios)** as the recommended first SKU
- Reliability: target 80%+ landing success, 70%+ end-to-end delivery
- 2 operators full-time at $7K/month each
- **Productize the catalog**: order forms, pricing sheet, signed pilot agreement templates for all 6 pack SKUs (Discovery / Validation / Library Foundation / Production / Enterprise / Custom). Stripe + invoicing infrastructure for one-time pack purchases.

### Month 6
- First paid pilot signed (target month 7 but push for early-month-6 signature)
- First 20-30 scenarios delivered against the pilot
- Customer feedback loop established
- Hardware contractor handing off to first eng hire (recruiting in parallel)

### Phase 2 KPIs
- First-capture date achieved by month 4
- 3+ prospect reviews delivered by month 5
- First paid pilot signed by month 7 (latest)
- Reliability: 80%+ mission success, 70%+ delivery rate
- Burn: ~$471K cumulative through month 6 (per RAISE_SIZING.md)

### Risk gates at end of Phase 2
- If MVP reliability < 60% by month 6: hold paid pilots, extend reliability sprint by 1-2 months
- If hardware contractor needs ≥1.0 FTE for ≥3 more months: take from buffer
- If no first paid pilot by month 8: shift focus to customer-discovery iteration, reconsider pricing

---

## Phase 3: Months 7-12 (Pilot phase)

**Goal**: 2-3 paid customers, 3-vehicle fleet operational, validate ASP via pack-mix.

### Pack-mix progression (the customer journey through pilot phase)

| Month | New deals signed | New deal value | Cumulative committed |
|---|---|---|---|
| 7 | 1× Validation Library Sampler ($33.9K) | $33.9K | $33.9K |
| 8 | — (deliver + evaluate) | — | $33.9K |
| 9 | 1st customer expands to Library Foundation ($50K) + 2nd customer pilot Sampler ($33.9K) | $83.9K | $117.8K |
| 10 | 1st customer Library delivering; 2nd customer evaluating | — | $117.8K |
| 11 | 2nd customer expands to Library Foundation ($50K); 3rd customer Discovery Pack ($17K) | $67K | $184.8K |
| 12 | 4th customer Validation Sampler ($33.9K); 5th customer Validation Sampler ($33.9K) | $67.8K | $252.6K |

This is the **honest** revenue picture for Phase 3:
- 5 customers signed by M12
- Total committed $252.6K (mix of pilots + volume tier expansions)
- Recognized revenue M7-12: ~$150-200K depending on delivery cadence and recognition timing
- ~50% of pilot customers expand to volume tier within 60-90 days

This is materially lower than the prior PR-FAQ projection ($700K through Q1 2027) because the pack-mix reflects realistic pilot-to-volume conversion timing. Updated revenue model now drives RAISE_SIZING.md trough analysis.

### Month 7-8
- First paid pilot fully ramped (100+ scenarios from Validation Sampler)
- First eng hire onboarded (perception/data engineering) at $21K/month — replaces ML contractor
- Order 2nd vehicle + rig ($57K total)
- Hardware contractor winds to 0.5 FTE then 0 by month 9
- **Productize**: customer success workflow (post-delivery QA, NPS survey, expansion conversation)

### Month 9-10
- 2-vehicle fleet operational
- Second pilot signed (target: a validation platform like Foretellix or trajectory-prediction team)
- 1st customer expansion conversation: Validation Sampler → Library Foundation
- Cloud pipeline scales: 200+ scenarios/month delivered combined
- Insurance + regulatory: keep clean Part 107 record, no incidents

### Month 11-12
- 3-vehicle fleet operational
- 4-5 paid customer engagements active (mix of pilots and volume expansions)
- Start GTM/sales hire recruiting (target start month 12-13)
- First case study from initial pilot ready (for seed pitch later)
- Honest ASP signal validated: pilot tier $339/scenario for Discovery + Validation packs; Volume 1 $200/scenario for expansions

### Phase 3 KPIs
- 4-5 paid customers (multiple SKUs sold) by month 12
- ~150-200 scenarios delivered cumulatively (lower than prior plan; reflects realistic pilot-then-expand cadence)
- Cumulative committed revenue: $250-300K (mix of pilots + Volume 1 expansions)
- Reliability: 90%+ mission success, 80%+ delivery rate
- **Pack-mix**: ≥50% of pilot customers expand to Volume 1 (Library Foundation) within 90 days
- **Discovery → Validation upsell rate**: ≥30% (Discovery customers move to Validation Sampler before Volume)
- Cash position end of M12: trough ~−$680K cumulative burn against $2M raise (so ~$1.32M in bank)

### Risk gates at end of Phase 3
- If MRR-equivalent (committed revenue / 12) < $30K by M12: hold capex, extend runway, validate why pilot-to-volume conversion lagged
- If pilot customers don't expand to Library Foundation (< 30% conversion): rethink pack pricing, possibly drop pilot tier to $250/scenario to make Volume 1 a clearer step up
- If reliability < 80%: pause new customer onboarding, sprint reliability fix
- If pilot ASP < $300 (customers pushing back on $339 pack pricing): trigger pessimistic-case plan, consider $300-500K bridge round at M14-15

---

## Phase 4: Months 13-18 (Scale to CFP)

**Goal**: 6-vehicle fleet, 6-10 customers (pack-mix evolving toward Volume 1+2), cash-flow positive by month 16-18.

### Pack-mix progression Phase 4

| Month | Customer pack-mix snapshot | Recognized MRR |
|---|---|---|
| 13 | 2 Library Foundation customers ($50K/quarter active) + 3 new Validation pilots in pipeline | $33K |
| 14 | 3 Library Foundation + 1 first Production Corpus ($100K) signed + 4-5 pilots in pipeline | $90K |
| 15 | 4 Library Foundation + 1 Production Corpus + 1 new Library Foundation = 5 volume-tier customers | $150K |
| 16 | 5 volume customers + 1 Enterprise quote in negotiation + 2 new pilot conversions | $250K |
| 17 | 6 volume customers + 1 Enterprise signed + first add-on attach (exclusive licensing premium) | $350K |
| 18 | 7-8 active customers, mix of Production Corpus + Library Foundation + 2-3 Enterprise prospects | $400K+ MRR run rate |

**Pack-mix dynamics**:
- Most revenue from 4-6 Library Foundation customers ($50K each per quarter)
- 1-2 Production Corpus customers ($100K each per quarter)
- 1 Enterprise in late-stage negotiation by M18 ($150K+)
- Continuous new pilot signings (Discovery + Validation packs) feeding the funnel
- Add-on attach: exclusive licensing premium begins (2-5x) on first scenarios for safety-case-sensitive customers

### Month 13-14
- GTM/sales hire starts ($18K/month) — quota: close 2 more Library Foundation pilots by M18, plus first Production Corpus
- 4th vehicle operational
- 2nd eng hire (perception ML or data engineering) at $21K/month
- 3 operators total
- **First add-on revenue**: customer requests exclusive licensing premium ($25K above standard)

### Month 15-16
- 5-vehicle fleet operational
- 5-6 paid customer engagements active, pack-mix moving toward volume tier
- 0.5 FTE customer success hire ($7K/month)
- Begin formal scenario library product positioning (sets up corpus subscription product later)
- CFP achievement: revenue exceeding monthly burn for first time
- First Production Corpus deal signed ($100K committed)

### Month 17-18
- 6-vehicle fleet operational (final ramp)
- 7-8 paid customers, $400K+ MRR run-rate
- 4 operators total
- CFP confirmed and sustained
- First customer case studies finalized + published (with permission)
- First Enterprise quote (1000+ scenarios, $150K+) in late-stage negotiation
- Cash position M18: ~$1.89M (honest case)

### Phase 4 KPIs
- 6-vehicle operational by M17
- 7-8 paid customers by M18 across pack-mix
- $400K+ MRR run rate
- Reliability: 95%+ mission success, 50%+ delivery rate
- CFP: cash position stable or growing
- LTV per vehicle tracking toward $1.2M
- **Pack mix at M18**: 4-5 Library Foundation, 1-2 Production Corpus, 1 Enterprise in late stage, continuous pilot inflow
- **Add-on attach rate**: ≥20% of customers using at least one paid add-on

### Risk gates at end of Phase 4
- If CFP not achieved by M18: extend by 3-6 months on remaining buffer, target M21-22
- If pack-mix stuck at pilot tier (no expansions): pricing problem, possibly raise pilot price OR widen volume tier discount
- If customer churn appears (early): root-cause analysis, may need product fix before scaling

---

## Phase 5: Months 18-22 (Seed round prep + raise)

**Goal**: Close $5-10M seed at $25-40M post-money.

### Why raise seed (the case)
- Multi-market expansion: Phoenix Q4 27, Austin Q1 28 — each $450-700K total cost
- Corpus subscription product development: $500K-1M in engineering + sales
- Team scale: 10-12 → 18-25 FTE
- Optional: BVLOS waiver work for V2 envelope (~$200K legal + lobbying)

### Why this is a *strong* seed pitch
- Operating data, not projections: "we have $400K+ MRR, 6 paid customers, $4M+ ARR run-rate, 57% gross margin"
- CFP achieved: "we don't need this capital to survive — we need it to expand"
- Proven unit economics: $1.2M LTV per vehicle validated
- Defensible moat: 18 months of operational learning + multi-tenant corpus + customer integrations

### Month 18-19 — Prep
- Update PR-FAQ with real numbers (Q21 financials become actuals, not projections)
- Build seed pitch deck (different from pre-seed — emphasize operational metrics, customer retention, expansion plan)
- Customer case studies: 2-3 named customer testimonials (subject to their PR approval)
- Refresh investor target list — same fund categories as pre-seed but the seed-stage offshoots (Founders Fund Seed, NEA Seed, etc.) + specialist mobility funds + strategics
- Engage seed-stage attorneys for term sheet drafting

### Month 20-21 — Active raise
- 4-6 weeks of investor meetings
- Target 30-40 funds, 15-20 angel/strategic conversations
- First-meeting → due diligence → term sheet
- Target term sheet by end of M21

### Month 22 — Close
- Negotiate term sheet (lead investor + smaller participants)
- Legal docs: Series Seed equity (preferred stock, not SAFE this time)
- Board structure: likely 3-member (founder + lead investor + independent)
- Wire transfer: $5-10M

### Phase 5 KPIs
- Seed term sheet by end of M21
- Seed close by end of M22
- $5-10M raised at $25-40M post-money (15-25% dilution)
- Founder retains majority + control

### Risk gates Phase 5
- If no term sheet by M21: extend runway via cost discipline, raise smaller bridge ($1-2M), try again at M24
- If valuation pressure (sub-$15M post-money): accept smaller raise OR delay until traction improves
- If only strategic interest (no financial leads): consider strategic seed but evaluate board / IP terms carefully

---

## Phase 6: Months 22-24 (Seed close + multi-market launch)

**Goal**: Begin Phoenix expansion + corpus product MVP.

### Month 22
- Seed wire received
- Hire VP of Engineering (~$300K loaded) — handles team scale + product expansion
- Hire VP of Sales (~$280K loaded) — multi-customer GTM
- Begin Phoenix operator + market manager recruiting

### Month 23
- Phoenix base of operations established
- Order 2 Phoenix vehicles + rigs ($114K)
- Phoenix operators hired (2 FTE, $7K/month each)
- Corpus subscription product engineering kick-off
- Bay Area fleet: continue 6-vehicle operations, MRR growing

### Month 24
- Phoenix first capture by end of M24
- Bay Area at $500K+ MRR
- Combined fleet: 6 (BA) + 2 (Phoenix) = 8 vehicles
- Total team: 12-15 FTE
- Corpus subscription beta with first 2 customers

### Phase 6 KPIs
- Phoenix first capture by M24
- 8-vehicle fleet operational
- 6-8 paid customers, $500K+ MRR
- Cash position end M24: $4-7M (seed funds + ongoing positive cash from BA)

---

## Critical-path decisions (across all phases)

| Decision | When | Trigger | Default |
|---|---|---|---|
| Sign first paid pilot | M6-7 | Customer verbal commitment + MVP reliability ≥80% | Push to M8 if not ready |
| Add 2nd vehicle | M8 | First pilot delivering, ASP confirmed ≥$200 | Hold at 1 vehicle |
| Hire GTM | M11-12 | 2 customers signed, sales bandwidth limiting | Delay 2-3 months if founder can cover |
| 4th vehicle | M14 | 3 customers, MRR ≥$200K | Hold at 3 vehicles |
| Reach for 5th-6th vehicles | M16-18 | 4-6 customers committed, MRR ≥$300K | Stay at 4 vehicles if pessimistic |
| Begin seed prep | M18 | CFP achieved or imminent | Bootstrap longer if cash strong |
| Begin Phoenix expansion | M22 | Seed closed | Stay BA-only if seed delayed |

## Founder time allocation by phase

| Phase | Customer / Sales | Engineering | Hiring / Ops | Fundraising | Other |
|---|---|---|---|---|---|
| 0 (now) | 50% | 15% | 5% | 30% | 0% |
| 1 (close) | 20% | 10% | 20% | 40% | 10% |
| 2 (M1-6) | 30% | 30% | 20% | 0% | 20% |
| 3 (M7-12) | 50% | 15% | 20% | 5% | 10% |
| 4 (M13-18) | 50% | 5% | 25% | 10% | 10% |
| 5 (M18-22) | 30% | 5% | 15% | 40% | 10% |
| 6 (M22-24) | 30% | 10% | 30% | 10% | 20% |

## Hiring sequence

| Month | Role | Loaded comp/yr |
|---|---|---|
| 0 | Founder (CEO) — $150K cash + $50K/yr deferred (hybrid Option C) | $200K loaded (cash) + $50K/yr accrued liability |
| 1 | Hardware contractor (0.5-1 FTE, 6-9 mo) | $20K/mo × 6 = $120K |
| 1 | ML/pipeline contractor (0.5 FTE, 6 mo) | $10K/mo × 6 = $60K |
| 5 | Operator 1 (FT) | $80K |
| 5 | Operator 2 (FT) | $80K |
| 7 | Engineer 1 (perception/data) | $250K |
| 12 | GTM/sales lead | $220K |
| 13 | Engineer 2 (ML/data ops) | $250K |
| 14 | Operator 3 (FT) | $80K |
| 16 | Operator 4 (FT) | $80K |
| 17 | Customer success (0.5 FTE) | $80K (at 50% = $40K) |
| 22 | VP Engineering | $300K |
| 22 | VP Sales | $280K |
| 23 | Phoenix operators (2 FTE) | $80K × 2 |
| 23 | Phoenix market manager | $180K |
| 24 | Engineer 3 (corpus product) | $250K |

**Founder comp note (Option C — hybrid)**: $200K loaded ($16.7K/month
cash to company P&L) breaks down to: **$150K cash salary** (take-home
after fed+CA tax ~$105K, covers SF mortgage + tightened expenses) +
~$11.5K employer payroll tax + ~$25K family health insurance + ~$10K
other benefits (401k match, disability/life, equipment stipend). Plus
**$50K/year deferred / accrued compensation** booked as a balance-sheet
liability, payable upon defined trigger events (whichever comes first:
seed round close, M&A event, or month 24).

Net effect: $50K/year cash savings vs Option A ($200K cash all the way)
= ~$75K cumulative cash savings through M18. Total comp aligned with
$200K-cash market expectation, demonstrating capital discipline to
investors. Deferred liability of $75K at seed close, paid from seed
proceeds.

**Legal action item Phase 0/1**: founder employment agreement must
include a properly-structured Deferred Compensation Provision with IRS
Section 409A-compliant trigger events. Cost: ~$2K legal one-time.

Revisit at CFP — if performance supports, switch to $200K cash + $50K
back-to-market raise (clears the accrued amount). Market rate for an
at-CFP small-ops-business CEO is $300-400K loaded; structure that
adjustment from seed proceeds.

## KPIs by phase (one-pager dashboard)

| KPI | M0 | M6 | M12 | M18 | M24 |
|---|---|---|---|---|---|
| Paid customer engagements | 0 | 0-1 | 4-5 | 7-8 | 10-12 |
| Active pack mix (vol/pilot) | n/a | n/a | mostly pilot | 4-5 Library / 1-2 Production / 1 Enterprise | 6-8 Library / 3-4 Production / 2 Enterprise |
| MRR run rate | $0 | $0 | $20-30K | $400K+ | $600K+ |
| Add-on attach rate | n/a | n/a | <10% | ≥20% | ≥30% |
| Vehicles operational | 0 | 1 | 3 | 6 | 8 |
| FTE (incl. founder) | 1 | 3 (+2 contractors) | 5 | 9 | 14 |
| Cash position | $2.0M | $1.53M | $1.32M | $1.89M | $4-7M (with seed) |
| Cumulative scenarios delivered | 0 | 50 | 800-1,200 | 6,000-8,000 | 18,000+ |

## What kills the plan (top 5 watch items)

1. **First paid pilot slips to M10+** — extends burn 3-4 months, may force bridge round
2. **Operator utilization stays at 50-60% through M12** — per-scenario cost stays at $120-140, never reaches $87 target
3. **Pilot-to-Volume conversion < 30%** — customers stay on $33.9K Validation Samplers, never expand to $50K Library Foundation. Pricing or product fit issue.
4. **MVP reliability under 70% at M6** — delays first paid pilot, hardware contractor extends, burn grows
5. **Bay Area engineer hiring takes 6+ months** — first eng arrives M11 instead of M7, build slips

For each: monitoring metric defined in respective phase risk gate.

---

*v1, May 2026. This is the operating plan against the $2.0M pre-seed.
Update at each phase gate. Major revisions trigger an update to PITCH.md
and the website.*
