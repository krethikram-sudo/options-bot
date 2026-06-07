# Skydock V2 execution plan — fixed-point + library subscription

Internal operating plan. End-to-end from current discovery state through
seed round close ~24 months out, restructured for the V2 architecture
(fixed-point capture + curation-as-product + validation-positioning).

Replaces V1 EXECUTION_PLAN.md (mobile fleet model). The phase structure
is similar; what changes is everything inside the phases.

**Top-of-doc summary:**

| Phase | Months | Goal | Money | Headcount end |
|---|---|---|---|---|
| **Phase 0** | Now → −1 | Customer discovery (safety teams) + investor prep + site partnerships scoped | $0 (founder bootstrapping) | 1 (founder) |
| **Phase 1** | 0 | Pre-seed close | **+$2.2M** | 1 + contractors |
| **Phase 2** | 1-6 | First 3 fixed sites + curation pipeline + first free pilot | −$570K cumulative | 1 + 2 contractors + 1 eng + 0.5 op |
| **Phase 3** | 7-12 | First 2 paid Library subscriptions + 2 more sites + GTM hire | Trough at M12: −$1.12M | 1 + 1 eng + 1 GTM + 1 op |
| **Phase 4** | 13-18 | Scale to 7 sites + 6 customers + CFP run-rate | CFP at M18-20, +$600K cash at M18 | 1 + 2 eng + 1 GTM + 1 op + 0.5 CS |
| **Phase 5** | 18-22 | Seed prep + raise | $600K decreasing, seed close at M21-22 | Same as above |
| **Phase 6** | 22-24 | Seed close, Phoenix + Austin Model C sites | +$5-10M | 12-15 FTE |

---

## Product catalog (what we're operationalizing toward)

Per SKYDOCK_V2_THESIS.md, the productized SKUs for V2:

| Tier | Product | Annual price | Notes |
|---|---|---|---|
| Library Access — Starter | Multi-tenant subscription, single market | $100K-$150K | 1-2 cities access |
| Library Access — Growth | Multi-tenant subscription, multi-market | $200K-$300K | 3-5 cities, custom waypoint requests up to 1/quarter |
| Library Access — Enterprise | Multi-tenant subscription, full coverage + custom | $400K-$500K | All cities, unlimited custom waypoint requests, integration support |
| Custom Capture | New site deployment for customer-specified location | $75K-$150K | One-time + site folds into library |
| Exclusive Captures | Time-bounded exclusivity on specific site captures | 2-5× standard | Annual contract, time-windowed |

Product shape changes everything downstream: hiring (curation engineers
over operator-drivers), sales cycle (4-6 months for Library subscription),
revenue recognition (subscription month-over-month vs per-scenario), and
KPIs.

---

## Phase 0: Now → month 0 (pre-raise)

**Goal**: customer discovery validated against V2 positioning + investor
pipeline built + first 3 site partnerships scoped.

### Customer discovery — refocused on safety teams

Per the V2 thesis, the customer cohort shifted from perception teams to
**safety teams** (and regulatory safety officers at OEMs preparing NHTSA
AV STEP submissions). Update DISCOVERY_PLAN.md target list:

- **Tier 1**: AV company safety teams (Waymo Safety, Aurora Safety, Pony.ai
  Safety, Zoox Safety, Cruise Safety [if still operating])
- **Tier 1b**: Scenario validation platforms with safety-case integration
  (Foretellix safety toolchain, Applied Intuition Validation Toolset)
- **Tier 2**: OEM safety officers preparing AV STEP submissions (Toyota,
  Mercedes, GM, Ford — slower cycle)
- **Tier 3**: Regulatory advisors at NHTSA, EU EASA contacts (signal
  validation, not direct customers)

Target conversations: 15-20 over Phase 0. Outcomes:
- ≥3 safety teams confirm "we'd run a closed-loop pilot on your scenarios
  if you cover the cost"
- ≥1 explicit "we'd commit to a paid Library subscription if pilot success
  criteria are met"
- 2-3 building/rooftop partnership conversations scoped (the first sites)

### Site identification

Phase 0 deliverable: ranked list of **top 15 high-criticality
intersections** across Bay Area, with:
- Criticality data from SFMTA / CHP crash records
- Building partnership feasibility assessment
- Customer demand signal alignment

Target: confirm 3 sites where we have realistic building access + clear
customer demand signal by end of Phase 0.

### Investor pipeline build

Target: 60-100 investor conversations during the 8-12 week raise period.
Same fund categories as V1 plan, but pitch updated for V2:

1. **Pre-seed funds focused on AV / autonomy / safety-critical systems**:
   Autotech Ventures, Trucks Venture Capital, Compound, Vela Partners,
   New Stack Ventures
2. **Generalist pre-seed with strong vertical SaaS conviction**: Floodgate,
   K9 Ventures, Bloomberg Beta, Wing Venture Capital
3. **Specialist enterprise data infra funds**: Madrona, Boldstart, S28
4. **Angels with AV / safety case / regulatory background**: senior
   safety engineers at Waymo/Cruise, former AV STEP regulators

### MVP technical proof for investor meetings

Skydock V1 sim methodology + first-cut curation pipeline architecture
demonstrating the scoring stack (criticality + epistemic uncertainty +
corpus frequency). No need to fully build before close — proof of concept
sufficient.

### Founder time allocation (Phase 0)

- 40% customer discovery (safety teams)
- 30% investor outreach + meetings
- 15% site partnership scoping + criticality analysis
- 10% MVP technical proof updates
- 5% legal + admin

### Phase 0 exit criteria → ready to close raise

- ≥3 safety teams interested in closed-loop pilot
- **3 signed LOIs from Model A building partners** (non-binding intent
  to host pending pre-seed close, with rent terms agreed in principle —
  see V2_DEPLOYMENT_LOGISTICS.md "Landlord economics" section). Reduces
  M4 first-site-live risk to near-zero. Verbal commitments alone are
  insufficient given the negotiation cycle length (30-60 days for Class
  B office; longer for city-owned buildings)
- **20-30 candidate building partners under conversation** (the 6:1
  pipeline ratio needed to handle landlord conversion losses)
- ≥1 investor at term sheet stage
- Legal entity + SAFE + bank ready
- Founder bio + website (with V2 positioning) + pitch deck final
- Updated discovery materials reflecting V2 thesis

---

## Phase 1: Month 0 (pre-seed close)

**Goal**: $2.2M wire transferred. Operating clock starts.

Same shape as V1 plan but with $2.2M target. Founder transitions to
execution mode. Begin contractor recruiting.

---

## Phase 2: Months 1-6 (MVP build + first 3 sites + first free pilot)

**Goal**: 3 Model A sites operational, curation pipeline delivering scored
scenarios, first free closed-loop pilot in customer's hands.

### Month 1
- Hire **curation/ML engineering contractor** (0.5 FTE) for scoring stack
  development — $20K/month
- Hire **hardware/site engineering contractor** (0.5 FTE) for mounting +
  cellular + cloud infrastructure — $20K/month
- **File BVLOS waiver application** (Part 107.31, novel deployment) — long
  process, decision expected M16-18
- Begin negotiation with 3 site building partners (offices, parking structures)
- Set up Bay Area home base for ops
- Founder obtains FAA Part 107 certification

### Month 2-3
- **Curation pipeline architecture**: criticality scoring (TTC/PET/jerk
  detection), epistemic uncertainty against baseline detector (YOLOv8 +
  ByteTrack as baseline), corpus frequency scoring infrastructure
- **Site mounting infrastructure**: power, cellular uplink, edge compute,
  weatherproofing
- First site (Model A) signed and access negotiated
- Continue safety-team discovery (target 1-2 conversations/week)
- Begin first prospect "would commit to free pilot at X intersection?"
  conversations

### Month 4
- **1st Model A site deployed** (e.g., Bay Area downtown intersection
  with documented high-criticality)
- Site capture pipeline tested end-to-end: capture → cloud → scoring →
  delivery package
- 1st FT curation/ML engineer hired ($21K/month) — replaces ML contractor
- **First scoring methodology benchmarked against highD reference**

### Month 5
- **2nd Model A site deployed**
- 1-2 prospect customers offered free closed-loop pilot at their
  specified intersection
- 0.5 FTE **curation operator** hired ($7K/month) — remote monitoring of
  sites + curation pipeline operations
- First scoring methodology benchmarked against customer's existing
  scenario library

### Month 6
- **3rd Model A site deployed**
- First free closed-loop pilot delivered (100 scenarios at customer-specified
  intersection)
- Joint success-criteria document signed with first prospect customer
- Hardware contractor wraps to 0 by M7
- Curation pipeline serves all 3 sites + delivers scored scenarios on
  customer request

### Phase 2 KPIs
- 3 sites operational by M6 — yes/no gate
- Curation pipeline functional (criticality + uncertainty + frequency
  scoring on every captured scenario)
- First scenario package delivered M4 to internal QA, M5-6 to customer
- 1 customer joint success-criteria document signed
- Cumulative burn end M6: ~$570K against $2.2M raise = $1.63M in bank

### Risk gates at end of Phase 2
- If curation pipeline fails to produce defensibly scored scenarios:
  hold customer pilots, sprint pipeline reliability for 1-2 months
- If first 3 sites can't be deployed by M6 (building partner backout):
  pivot to Model B tethered as fallback ($40K/site instead of $25K)
- If first prospect won't sign joint success-criteria document:
  positioning may need refinement; reconsider safety-team pitch
- BVLOS waiver: if rejected outright in M6 review, plan for Model A/B
  only through M18; defer Model C to post-seed

---

## Phase 3: Months 7-12 (First paid customers + 2 more sites + GTM)

**Goal**: 2 paid Library subscription customers, 5 sites operational,
GTM hire onboarded.

### Pack-mix progression Phase 3 (subscription model)

| Month | New deal events | Recurring MRR by EOM |
|---|---|---|
| 7 | 1st Library subscription signed ($150K ARR) | $12.5K |
| 8 | Joint pilot success measured; conversion confirmed | $12.5K |
| 9 | — | $12.5K |
| 10 | 2nd customer signs ($150K ARR) | $25K |
| 11 | 2nd customer ramping | $25K |
| 12 | — | $25K |
| End Q3 | — | **~$25K MRR / $300K ARR** |

### Month 7-8
- **First paid Library subscription signed** (1st customer converts from
  free pilot to paid)
- Onboarding workflow operationalized (data delivery, integration support,
  customer success cadence)
- Order **4th site materials** (Model A, $25K)
- Curation pipeline scales: 4-5 sites supported

### Month 9-10
- **4th Model A site deployed**
- 2nd prospect customer pilot underway (free pilot phase)
- Begin 2nd customer's joint success-criteria conversation
- Continue Phase 0 customer discovery cadence (2-3 conversations/week)
- BVLOS waiver: 6 months into application, status check

### Month 11-12
- **5th Model A site deployed**
- **2nd paid Library subscription signed** (M11)
- Start GTM/sales hire recruiting (target start month 12-13)
- First case study from initial pilot finalized (for seed pitch later)
- Honest ASP signal validated: $150K Library subscription tier converts

### Phase 3 KPIs
- 2 paid Library subscription customers by M12
- 5 sites operational
- ARR run-rate M12: $300K ($25K MRR)
- Scoring methodology validated by 2 customers' closed-loop sim
- Cumulative burn end M12: ~$1.12M ($1.08M in bank with $2.2M raise)

### Risk gates at end of Phase 3
- If 1st customer's closed-loop pilot fails to meet success criteria:
  product-pipeline issue — sprint curation methodology improvements
  before scaling
- If 2nd paid customer slips past M12: extends burn ~$130K/month, may
  require bridge or extended sales cycle
- If GTM hire takes 4+ months to land: founder stays in sales lead role
  for 2-3 more months

---

## Phase 4: Months 13-18 (Scale to CFP)

**Goal**: 6-7 sites operational, 6 paid customers (mix of Library
subscriptions + custom capture), CFP run-rate achieved by M18.

### Pack-mix progression Phase 4

| Month | New deal events | Recurring MRR by EOM |
|---|---|---|
| 13 | 3rd Library subscription signed | $37.5K |
| 14 | 4th Library subscription + 1st custom capture order ($75K) | $37.5K + $75K one-time |
| 15 | 1st Model B tethered site deployed; new customer (5th) | $54.2K |
| 16 | 5th customer ramping | $54.2K |
| 17 | 6th Library subscription signed | $75K |
| 18 | 2nd Model B site deployed | $75K |

End Q6: $75K MRR / **$900K-$1.2M ARR run-rate**

### Month 13-14
- GTM/sales hire starts ($18K/month)
- **First custom capture order signed** ($75K, customer-specified new site)
- 3rd paid Library subscription signed
- BVLOS waiver: 8-9 months in, decision expected M16-18

### Month 15-16
- **1st Model B tethered drone site deployed** at $40K capex
- 2nd eng hire (hardware/site ops engineer) at $21K/month
- 5th paid customer signs (M16)
- BVLOS waiver decision: if approved, plan Phoenix/Austin Model C
  deployments for Phase 6

### Month 17-18
- **2nd Model B site deployed** ($40K capex)
- 0.5 FTE customer success hire ($7K/month)
- 6th paid customer signs (M18)
- CFP run-rate: MRR $75K vs burn $140K = -$65K monthly deficit, but each
  new customer adds $12.5K-$20K MRR, so M19+ approaches breakeven
- Cumulative burn end M18: ~$1.6M against $2.2M raise + $508K revenue =
  **~$600K cash position**

### Phase 4 KPIs
- 7 sites operational (5 Model A + 2 Model B) by M18
- 6 paid customers by M18
- ARR run-rate M18: $900K-$1.2M
- Custom capture revenue Q5: $75K + Q6: $75K = $150K
- CFP at M18-20 expected
- Add-on attach rate: custom capture order on first M14 customer = first
  signal of expansion revenue
- LTV per customer tracking toward $297K

### Risk gates at end of Phase 4
- If MRR < $40K by M18: pessimistic case, may need $300-500K bridge
- If BVLOS waiver rejected: Phoenix/Austin Phase 6 expansion shifts to
  Model A/B only; some sites slip 6-12 months
- If 3rd-4th customer don't sign by M16: sales cycle longer than
  modeled, may force GTM team expansion or pricing rethink

---

## Phase 5: Months 18-22 (Seed prep + raise)

**Goal**: Close $5-10M seed at $25-40M post-money. Strong story given
proven Library subscription model + $1M+ ARR run-rate.

### Why this is a stronger seed pitch than V1's would have been

- Operating data: "$1M+ ARR run-rate from 6 paying customers, 12-month
  retention to be tested in Q4-Q5 of fiscal year"
- Unit economics proven: $2/scenario cost, $297K LTV per customer
- Defensible moat: 7-site curation corpus + multi-tenant integration
- Regulatory tailwind: BVLOS waiver in hand (if M16-18 went well)
- Different exit story: "data layer for AV safety case validation" vs V1's
  "data services for AV training"

### Month 18-19 — Prep
- Update PR-FAQ with real numbers (subscription customer count, ARR,
  retention indicators, churn)
- Build seed pitch deck emphasizing closed-loop pilot conversion + Library
  subscription unit economics
- Customer case studies: 2-3 named customer testimonials (subject to PR
  approval)
- Refresh investor target list — series A funds open to seed:
  Sequoia (with seed program), Bessemer, Trinity Ventures, Lightspeed seed
- Engage seed-stage attorneys for term sheet drafting

### Month 20-21 — Active raise
- 4-6 weeks of investor meetings
- 30-40 funds + 10-15 angel/strategic conversations
- Target term sheet by end of M21

### Month 22 — Close
- Negotiate term sheet
- Legal docs: Series Seed equity (preferred stock)
- Board structure: 3-member (founder + lead + independent)
- Wire transfer: $5-10M

---

## Phase 6: Months 22-24 (Seed close + multi-market launch)

**Goal**: Begin Phoenix + Austin expansion with Model C sites (BVLOS-
permitted), corpus subscription product growth.

### Month 22
- Seed wire received
- Hire VP of Engineering (~$300K loaded) + VP of Sales (~$280K loaded)
- Begin Phoenix market manager + Austin market manager recruiting
- Order first Model C drone-in-a-box site (Phoenix)

### Month 23
- Phoenix Model C deployed
- Austin recruiting completed; site partnership initiated
- Corpus subscription product engineering kick-off (annual access to
  historical library at premium tier)
- Bay Area at $1.5M+ ARR run-rate

### Month 24
- Austin Model C site deployed
- Combined: 7 (Bay Area) + 2-3 (Phoenix) + 1 (Austin) = 10-11 total
  sites
- Total team: 12-15 FTE
- 8-10 paid customers, $1.8M+ ARR run-rate

### Phase 6 KPIs
- 10-11 sites operational by M24
- 8-10 paid customers
- Phoenix + Austin Model C deployment confirmed
- Cash position end M24: $4-7M (seed funds + ongoing positive cash from
  Bay Area)

---

## Critical-path decisions (across all phases)

| Decision | When | Trigger | Default |
|---|---|---|---|
| Sign first paid Library subscription | M7 | Customer joint success criteria met | Push to M8-9 if not measurable |
| BVLOS waiver application | M1 | Begin immediately | Apply same time as Phase 2 starts |
| Add 4th site | M9 | Curation pipeline stable, 1 paying customer | Hold at 3 sites |
| GTM hire | M11-13 | 2 customers signed, sales bandwidth limiting | Founder covers if needed |
| Add Model B (tethered) | M14-15 | Library subscription pricing validated | Stay Model A only |
| 1st Model C (post-BVLOS) | M19+ | Waiver approved + Phoenix expansion decision | Hold for V3 |
| Begin seed prep | M18 | CFP run-rate achieved | Bootstrap if revenue strong |
| Phoenix expansion | M22 | Seed closed | Bay Area only |

---

## Hiring sequence (V2 — much different from V1)

| Month | Role | Notes |
|---|---|---|
| 0 | Founder ($150K cash + $50K deferred = $200K cash-loaded, $250K all-in) | Per Option C structure |
| 1 | Hardware/site engineering contractor (0.5 FTE, 6 mo) | $20K/mo × 6 |
| 1 | Curation/ML engineering contractor (0.5 FTE, 6 mo) | $10K/mo × 6 |
| 5 | 1st FT engineer (curation/ML) | $250K loaded |
| 6 | 0.5 FTE curation operator | $80K @ 50% = $40K |
| 11 | GTM/sales lead | $220K loaded |
| 14 | 2nd FT engineer (hardware/site ops) | $250K loaded |
| 17 | 0.5 FTE customer success | $80K @ 50% = $40K |
| 22 | VP Engineering | $300K |
| 22 | VP Sales | $280K |
| 23 | Phoenix market manager | $180K |
| 23 | Phoenix curation operator | $80K |
| 24 | Austin market manager | $180K |
| 24 | 3rd FT engineer (corpus product) | $250K |

Total through M24: ~13 FTE incl founder. Heavy on engineering (5 eng) +
GTM (3 FTE) + ops (4 FTE) — vs V1's heavier ops weighting.

---

## KPIs by phase (V2 dashboard)

| KPI | M0 | M6 | M12 | M18 | M24 |
|---|---|---|---|---|---|
| Sites operational | 0 | 3 (Model A) | 5 (Model A) | 7 (5 A + 2 B) | 10-11 (incl Phoenix+Austin Model C) |
| Paid Library subscribers | 0 | 0 | 2 | 6 | 8-10 |
| ARR run-rate | $0 | $0 | $300K | $900K-$1.2M | $1.8M+ |
| Custom capture revenue (cumulative) | $0 | $0 | $0 | $150K | $400K+ |
| FTE (incl founder) | 1 | 3 (+2 contractors) | 4 | 7 | 13 |
| Cash position | $2.2M | $1.63M | $1.08M | $0.60M | $4-7M (with seed) |
| Customer LTV/CAC | n/a | n/a | n/a | tracking 3.7x | 3.7x+ |
| BVLOS waiver status | applied | applied | reviewing | decision (M16-18) | approved or pivoted |

---

## What kills the plan (top 5 watch items)

1. **BVLOS waiver rejected** — locks us into Model A/B only, Phoenix/Austin
   Phase 6 timeline slips 6-12 months
2. **First Library subscription pilot fails closed-loop success criteria**
   — product problem with curation pipeline; sprint to fix or reconsider
   methodology
3. **Customer ramp slips by 6+ months** — pessimistic case, may force
   $300-500K bridge round at M14-15
4. **Building partner backout on first 3 sites** — site selection becomes
   harder + may push to Model B early (higher capex)
5. **Curation pipeline labor scaling sub-linearly fails** — if 1 ML eng
   can't support 5+ sites, hiring more eng needed earlier, blowing budget

For each: monitoring metric defined in respective phase risk gate.

---

*v1, May 2026. V2 execution plan against $2.2M pre-seed. Update at each
phase gate. Major revisions trigger update to V2_FINANCIAL_MODEL.md and
SKYDOCK_V2_THESIS.md.*
