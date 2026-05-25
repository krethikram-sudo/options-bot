# Skydock — Pre-seed PR-FAQ

**Executive Summary:** Today we will discuss the product idea and business opportunity for Skydock. We are seeking $1.7M pre-seed funding to build the MVP and reach cash-flow positive operations on a 6-vehicle Bay Area fleet by month 18 (technical architecture is largely finalized; see [skydock simulation](.)). Reasons why this is a good investment: (1) Aerial bird's-eye-view (BEV) training data is a structurally underserved category that addresses a documented and growing AV-customer pain point (FAQs #9, #11, #15); (2) the operational model — vehicle-deployed dock + autonomous drone deployment + delivery pipeline — has not been built before and gives us a defensible time-to-market advantage (FAQs #12, #14); (3) we have already de-risked the technical and unit-economic assumptions through a fully-instrumented simulation that lets us answer pricing, capacity, and reliability questions before spending hardware capital (FAQ #13); (4) in the mid-case scenario, Skydock delivers ~$1.2M LTV per vehicle, ~57% gross margin (at weighted-volume ASP) or ~65% (at pilot-tier ASP), ~$492K monthly revenue at a 6-vehicle steady state, and reaches CFP in months 16-18 without a Series A dependency (FAQ #21).

---

## Skydock: Aerial Training Data for Autonomous Vehicles, From the Roof of a Car

**MOUNTAIN VIEW, CA — (Business Wire) — April 9, 2027** — Today Skydock announced US launch of the first vehicle-deployed aerial training-data pipeline for autonomous vehicles, with four AV customers (including a Tier-1 scenario-validation platform) under paid commercial agreement, cash-flow positive operations achieved on a six-vehicle Bay Area fleet, and 4,200+ customer-validated scenarios delivered since MVP launch in October 2026.

AV development teams have spent the last decade collecting ground-perspective training data — cameras and lidar mounted on test vehicles, augmented by synthetic data generated from 3D scenes. Aerial bird's-eye-view (BEV) footage — drone perspective from 80m AGL — has been a structurally missing category because the operational model didn't exist. Fixed-base drone-in-a-box systems (DJI Dock 2, Skydio Dock 2) capture only the location they're installed at. Manually-piloted drone collection caps at 2-4 captures per day per crew and costs $1,000+ per usable clip. Skydock automates the operational layer: a roof-mounted dock containing a sub-250g drone deploys autonomously at pre-planned waypoints or operator command, captures 30-120 seconds of BEV footage above the scene, returns to dock, and the resulting OpenSCENARIO 2.0 scenario package is delivered to the customer within four hours.

> *"For our scenario-validation library, aerial BEV was the perspective we'd been trying to source internally for two years. Skydock turned what was a 6-month internal-build project into a 6-week purchase. The data quality holds up against our internal benchmarks and the OpenSCENARIO output dropped directly into our existing pipeline with no schema rewrite."*
> — **[Head of Scenario Engineering, Pilot Customer]**

Each Skydock vehicle carries a custom roof dock that houses three DJI Mini 4 Pro drones (249g each, sub-250g FAA Remote ID exemption), rotated between active capture, battery recharge, and standby. The dock provides 60cm precision-landing tolerance via BLE beacon guidance, an anti-tampering alarm, weatherproof IP55 enclosure, and inductive charging. An NVIDIA Jetson Orin Nano 8GB edge-compute unit runs the trigger detection, mission state machine, and data buffer; an LTE Cat-12 cellular modem uploads captured footage to the AWS cloud pipeline where the BEV transformation, agent detection (YOLOv8 + ByteTrack), and OpenSCENARIO export run before delivery to the customer.

> *"Aerial BEV is the AV training-data category nobody could collect at scale because the operational model — getting a drone to the right intersection at the right time, reliably, twenty times per day per vehicle — didn't exist. We invented that model. The hardware is off-the-shelf. The wedge is the integrated system that gets to spec-target reliability."*
> — **Krethik Ram, Founder, Skydock**

Skydock is currently delivering to four AV-industry customers and has two additional pilot agreements signed for Q3 2027. Per-scenario pricing starts at $339 (volume tier) with custom edge-case scenarios at premium rates. The company plans to expand to twelve vehicles operating across three markets (Bay Area, Phoenix, Austin) by Q4 2027. Skydock is backed by [pre-seed investors] and is based in Mountain View, CA. For more information, visit skydock.ai.

---

## Customer FAQs

**Q1. What is a Skydock scenario?**

A Skydock scenario is a 30–120 second aerial bird's-eye-view recording of a real road interaction (intersection, merge, school zone, construction zone, VRU interaction, etc.) captured from a drone at 80m AGL, delivered as a four-file package: `metadata.json` (scene classification, location with GPS uncertainty, capture geometry including drone altitude and gimbal pitch, camera calibration matching DJI Mini 4 Pro spec, quality score with documented methodology), `agent_tracks.json` (frame-by-frame ENU positions of every visible vehicle, pedestrian, and cyclist at 30 fps interpolated from the simulation's continuous-time agent model, with heading and speed computed from successive positions so traffic-light stops produce `speed_mps: 0`), `scenario.xosc` (OpenSCENARIO 2.0 export with the road network reference, scenario entities, and storyboard skeleton), and optionally the raw 4K H.265 source video.

**Q2. How does a Skydock scenario get captured? What's the operational flow?**

When a Skydock-equipped vehicle arrives at a pre-planned waypoint or the operator triggers capture, the system performs a 2-second pre-flight check (vehicle stationary or <5 mph per spec §1.2 envelope, wind <20 mph, drone battery >40%, no overhead obstacles), then deploys the drone in approximately 4 seconds. The drone climbs to 80m AGL in 18-25 seconds, holds position over the capture point for 30-120 seconds (operator-configurable), and returns to the dock in 18-25 seconds. Landing uses a BLE precision-landing system that takes over below 10m AGL and brings the drone within the dock's 1.5m horizontal tolerance for latch. Total mission time: ~90 seconds. The vehicle is stationary throughout the mission per FAA Part 107 VLOS requirements.

**Q3. How do I receive the scenarios? What's the format and timing?**

Standard delivery is via signed S3 pre-signed URL within 4 hours of capture. The package is a directory `scenario_{id}/` containing the four files described in Q1. Enterprise customers can request SFTP delivery, custom S3 bucket targeting, or an API endpoint for streaming integration. OpenSCENARIO 2.0 is the default schema; alternative schemas (CommonRoad, custom JSON) are supported at engineering rates. Bulk corpus access — historical scenarios from the library — is immediate via a queryable index.

**Q4. What's the pricing? How does volume tiering work?**

Per-scenario pricing follows the spec §4.2 volume tier structure, derived bottoms-up from cost-to-replicate. Pilot pricing (1-99 scenarios): $339/scenario standard, $250 minimum, $632 premium edge cases. Volume tier 1 (100-499 scenarios): $200/scenario. Volume tier 2 (500-999 scenarios): $150/scenario. Volume tier 3 (1000+ scenarios): $100/scenario or custom enterprise pricing. Premium edge cases (specific weather conditions, specific traffic patterns, custom waypoints) priced 2-3× the relevant tier rate. See FAQ #19 for the bottoms-up pricing methodology.

**Q5. Can I get custom scenario types?**

Yes. Custom scenario waypoints (specific intersections, specific times of day, specific weather conditions if reproducible) are added to the operator's route plan and captured on the next operating day matching the conditions. Custom scenario taxonomies (beyond the spec §3.5 categories — `intersection_signalized`, `unprotected_left_turn`, etc.) are supported with a 1-week onboarding for the scene-class definition. Custom delivery formats beyond OpenSCENARIO 2.0 are supported at $5,000-$15,000 engineering rates depending on schema complexity. Custom geographic regions outside currently-operating markets require operational expansion and are quoted separately.

**Q6. What's the data quality methodology? How do I know what I'm buying?**

Every scenario carries a quality score from 0-100 computed via the published methodology: 60 points from agent visibility ratio (frames each agent was inside the drone's FOV / total frames observed), 20 points from agent coverage (saturated at 70% of spawned agents to reflect realistic FOV limits), 20 points from agent class diversity. The score is then multiplied by an altitude-resolution factor (1.0 at 80m AGL, scaling down above) and a wind-shake factor (1.0 at ≤12 mph, scaling down above to a 10% floor). Quality below 70 is not delivered (the scenario is generated, but not sold). The `quality.methodology` field in every `metadata.json` references this calculation explicitly so an AV engineer can verify the score against the agent_tracks.json.

**Q7. How does the system handle weather, time of day, and edge conditions?**

Capture happens during civil daylight hours only (sunrise +30 min to sunset −30 min). Pre-flight checks reject capture attempts at wind >20 mph or non-clear weather. The drone's wind-shake quality penalty kicks in above 12 mph average wind during capture, so customers may opt to reject scenarios captured in marginal conditions via the quality threshold. Capture is paused for the duration of any rain event; the vehicle continues to its next waypoint or returns to dock. Operating envelope is documented in scenario metadata so customers can filter their corpus by capture conditions.

**Q8. What's the SLA and what happens if a scenario fails to deliver?**

SLA: 99% of triggered missions complete delivery within 4 hours; 95% of delivered scenarios pass the published quality threshold (≥70); 99.5% of paid scenarios match the customer's scene-class request. If a scenario fails to deliver (mission aborted mid-capture, upload failed, quality below threshold), no charge is applied. If a scenario passes quality threshold but the customer's QA team rejects it within 30 days for documented schema or content issues, a credit is applied toward future scenarios. Enterprise customers can negotiate custom SLA terms in the master service agreement.

---

## Internal FAQs

**Q9. What customer problems are we solving?**

Today, AV scenario validation teams cannot acquire aerial bird's-eye-view training data at scale, despite documented demand for it. We commissioned conversations with 8 AV engineering leads (a mix of validation-platform companies and Tier-1 AV companies) in March-April 2026; in 7 of 8 conversations, the lead confirmed (1) they maintain an internal scenario library, (2) aerial BEV slots in that library are currently empty or filled with low-quality opportunistic captures (one team has 200 scenarios from a former employee's hobby drone collection), (3) they would pay $200-$500 per validated aerial BEV scenario at meaningful volume. Existing alternatives — internal drone teams ($1,000+/scenario, capacity caps at 4/day), synthetic data (acknowledged by 6 of 8 leads to underperform real data on edge cases), opportunistic public-data scraping (legal ambiguity + quality issues) — are all unsatisfying. The category exists but is structurally underserved because nobody has built the operational system to populate it at scale. See FAQs #10–#11 for market sizing and competitive landscape, and Appendix C for the discovery conversation summary.

**Q10. Who are the target customers and why?**

The target customer is an AV scenario validation team with a defined scenario-library product or program. From spec §4.1, the prioritised customer list is:

| Customer | Buying behaviour | Likely deal shape | Target year |
|---|---|---|---|
| Applied Intuition | Sells scenario libraries to OEMs; buys data aggressively | 200-500 scenarios, $50K-$150K | Year 1 pilot |
| Foretellix | Edge-case validation platform; ideal aerial BEV customer | 100-300 scenarios, $30K-$80K | Year 1 pilot |
| Parallel Domain | Synthetic-data company; buys real data to validate synthetics | 500-1000 scenarios, $50K-$100K | Year 1-2 |
| Cognata | Smaller validation player; entry-tier pilot | 100-200 scenarios, $20K-$50K | Year 1-2 |
| Tier-1 AV companies (Waymo, Cruise, Aurora, Zoox, Pony.ai) | Long sales cycle; large deal sizes | 1000+ scenarios, $100K-$500K | Year 2+ |
| OEMs (GM, Ford, Toyota, Mercedes) | Slowest sales cycle; largest deal sizes | 5K+ scenarios, $500K-$2M | Year 3+ |

The first four are the immediate pre-seed-to-CFP customer set; one or two paid pilots from this group is required to hit the cash-flow positive milestone. The Tier-1 and OEM cohort is the seed/Series-A growth thesis, not the pre-seed thesis.

The buying decision-maker is the Head of Scenario Engineering (or equivalent — sometimes the Head of Simulation, sometimes the VP of Engineering) — typically a former AV research lead with technical hiring authority and a budget in the $100K-$1M/year range for data acquisition. We are *not* selling to procurement or to general operations; the technical buyer needs to be convinced first.

**Q11. What alternatives exist today? Why haven't they captured the aerial BEV market?**

We surveyed the current alternatives in March 2026 through (a) Amazon / Google product searches, (b) Crunchbase data on drone-data startups, (c) the conversations referenced in FAQ #9. Comparable offerings classify into five categories:

1. **Fixed-base drone-in-a-box** (DJI Dock 2 + Matrice 3D at ~$15K; Skydio Dock 2 + Skydio X10 at ~$40K). Captures only at the installed location. Useful for industrial inspection (Percepto's market) but cannot follow a moving operating area. Not viable for diverse road scenarios.
2. **Manually-piloted drone collection** (small consulting outfits, AV company internal teams). Capacity caps at 2-4 captures/day per crew. Per-scenario cost $1,000+. Customers we spoke to who have tried this all stopped within a year — operational overhead too high.
3. **Synthetic BEV** (Parallel Domain, Mira, Datagen). Strong on volume; weaker on edge case fidelity. All 6 of 8 customer-discovery leads confirmed they use synthetic *alongside* real data, not as a substitute.
4. **Opportunistic public footage** (YouTube, traffic cam scrapes). Quality and legal issues. Three of eight customers had tried this; none reported it working for their use case.
5. **Aerial traffic analytics services** (DataFromSky, Vivacity). Sell analytics products derived from static rooftop cameras, not training data. Different operational model, different output, different customer.

None of these solutions has achieved meaningful share of the aerial-BEV-for-training-data market because the category is structurally hard to enter: you need (a) the drone hardware, (b) the dock/integration system, (c) the operational discipline to hit 20 captures/day reliably, and (d) the data pipeline to deliver in customer-acceptable format. Each one of these is doable; the integration is the wedge.

**Q12. What gives us confidence that we can do better with our system than existing solutions?**

Four reasons:

1. **The operational model didn't exist.** Vehicle-deployed drone-from-car dock with autonomous deployment is a category of one. The closest analogue is Percepto's industrial-inspection vehicles, which don't sell data and don't do BVLOS. Our wedge is the operational system, not the drone or the data pipeline individually.
2. **We have a fully-instrumented simulation that de-risks the assumptions before hardware.** Every quantitative claim in this document (capture rate, success rate, dock latch probability, quality distribution, unit economics) is grounded in a working physical-layer simulation (this repo) that an engineer can interrogate. No competitor has this; most pre-seed startups are pitching with spreadsheets. We're pitching with a system.
3. **The hardware is off-the-shelf.** DJI Mini 4 Pro is a $760 commodity drone. NVIDIA Jetson Orin Nano is a $499 commodity edge-compute module. The custom dock is a 2-3 month hardware engineering project. We're not asking investors to fund a quadrotor R&D program — we're asking them to fund integration and operations.
4. **The customer pain is documented and recent.** AV scenario validation has gone from research curiosity to procurement line-item over the last 24 months. NHTSA's incoming scenario-based testing rules, Applied Intuition's 2024 ScenarioLib launch, and Foretellix's growing OEM partnerships all create concrete demand in the pre-seed-to-seed timeframe.

See FAQ #13 for our existing competence, FAQ #15 for "why now," and FAQ #16 for why this is the right approach vs. synthetic-only.

**Q13. Do we have competence in this space, and if not, can we acquire it quickly?**

Yes, partially, and the gaps are well-scoped:

- **Simulation and unit-economic modeling**: ✓ established. The repo backing this document is a 7,000-line physical-layer simulation with 16 passing regression tests covering flight dynamics, dock latch math, scene visibility, and integration smoke tests. The investor brief generator (`brief.py`) produces a Monte Carlo + sensitivity report in 19 seconds.
- **AV training data pipeline architecture**: ✓ established. OpenSCENARIO 2.0 is a published ASAM standard. YOLOv8 + ByteTrack are proven object-detection and tracking models with reference implementations. The cloud pipeline architecture (S3 ingest → time-sync → BEV processing → agent tracking → OpenSCENARIO export → delivery) is a straightforward ML-ops integration, not novel research.
- **Drone hardware integration**: contractor required. DJI provides an SDK for autonomous mission programming. The custom dock (precision landing pad, latch system, BLE beacons, charging contact) is a hardware engineering project we will contract to a 0.5-1.0 FTE hardware engineer for the first 6 months (spec §5.4 cost model: $15K-$30K/month).
- **FAA Part 107 / VLOS operations**: required but well-documented. V1 envelope (spec §1.2) is VLOS only — no waiver required. The operator becomes the licensed pilot. V2 BVLOS waiver is upside, not a dependency.
- **Customer discovery and enterprise sales**: founder-led for the first 4 pilots, then a dedicated GTM hire in month 9-12.

Capabilities that need to be built (not currently owned): the operational discipline to achieve 20 captures/vehicle-day at 90%+ success rate. This is the explicit goal of the 6-month MVP build phase (Phase 1-2 in spec §5.1). The simulation tells us this is achievable; the hardware iteration tells us whether it actually works.

**Q14. Why is this important for us / what does success mean for the founder?**

Three layers of strategic importance:

1. **The wedge has a defensible time-to-market window**. The category exists, the demand is there, and nobody is building it. Whoever ships first establishes the operational moat (corpus, customer relationships, process refinement) that's hard to displace. If we don't capture this in 2026-2027, Skydio or DJI could enter as adjacent moves from their current businesses, or an AV scenario platform could vertical-integrate. Either would be defensible against us, but only if they get there first.
2. **The product is the foundation of a larger data services company**. Aerial BEV is the first product. Subsequent products (ground sensor data, multi-modal capture, on-demand custom-scenario commissioning, V2X data collection) extend the same operational platform without rebuilding it. The pre-seed funding is for the wedge product; the seed/Series-A is the platform expansion.
3. **Founder commitment**: this is what I'm building. Pre-seed solo founder, full-time on the project, deep-tech background applicable to the hardware and ML layers (founder bio in Q33). If the wedge fails, I have specific learnings about how to redirect — but the wedge isn't currently failing in the simulation, so the priority is to ship.

**Q15. Why now?**

Three converging timing pressures make 2026-2027 the right window:

1. **NHTSA scenario-based testing rules**. The agency's December 2024 NPRM (Notice of Proposed Rulemaking) for AV safety testing moves the industry from miles-driven to scenario-coverage as the validation standard. Scenario libraries are no longer optional for AV companies — they're regulatory infrastructure. The libraries need to be filled. Aerial BEV is one of the categories they need to be filled with.
2. **Validation platform commercialisation**. Applied Intuition launched their ScenarioLib product in 2024, Foretellix has growing OEM partnerships, Parallel Domain is mid-pipeline on a Series C. The validation-platform layer of the AV ecosystem is going from R&D to revenue, which means scenario procurement is going from research budget to product budget. Procurement budgets are larger, more sustained, and harder to cut.
3. **First-mover infrastructure lock-in**. Whoever ships the first credible aerial BEV service captures the AV-customer integration relationships first. Once Skydock data is in a customer's validation pipeline (file format, naming convention, QA workflow, billing integration), switching cost is real. We have an estimated 12-18 month window before a competitor with similar capital can ship a comparable system. If we don't capture customers in this window, we leave the door open for Skydio or a vertical integrator.

We have not seen a single competing aerial-BEV vehicle-deployed product launch announcement as of the current cycle. The category window is open.

**Q16. Why should we invest in aerial BEV when synthetic data already covers most of the use case?**

Synthetic data (Parallel Domain, Mira, Datagen) is a large and growing market, and Skydock is *not* trying to displace it. Synthetic and real data are complementary:

- **Synthetic strengths**: infinite volume, perfect labeling, parameterisable, no real-world capture constraints.
- **Synthetic weaknesses (acknowledged by 6 of 8 customer-discovery leads)**: edge-case fidelity, distribution shift from real-world sensor noise, perception model performance on out-of-distribution scenes.
- **Real-data strengths**: ground truth, distribution match to the deployed sensor stack, edge-case authenticity.
- **Real-data weaknesses**: cost per scenario, slow turnaround, coverage gaps.

AV scenario validation teams use both. The procurement decision is "what percentage of my library should be synthetic vs. real?" — and the consistent answer from our discovery conversations is "we want more real, especially aerial BEV, but we can't get it." Skydock fills that demand. We don't compete with synthetic; we expand the real-data side of the same customer's library budget.

A direct cannibalisation question: would Skydock's customer also reduce their synthetic spend in proportion? Discovery feedback: no — the library budget is growing fast enough that aerial BEV is additive, not substitutive, for the next 24-36 months.

**Q17. What is the estimated cost per scenario (TCPU)?**

Per-scenario unit economics, sim-verified ([economics.py](skydock/skydock/economics.py)) with both variable and all-in figures:

| Component | Per scenario (USD) |
|---|---|
| Operator labour ($30/h × ~0.5 h/scenario amortised over the operating day) | $15.00 |
| Vehicle operating cost (fuel + maintenance, $5/h × ~0.5h) | $2.50 |
| Cloud processing (S3 + Lambda + EC2 GPU instance) | $0.80 |
| Drone wear (battery cycles + airframe amortisation, ~$1.00 per flight) | $1.00 |
| **Variable cost per scenario** | **~$19.30** |
| Capex amortization (vehicles + rigs + dock R&D over 3-year fleet life) | $7.50 |
| Engineering + GTM labour amortized (founder + 2 eng + 1 GTM + 0.5 CS) | $54.00 |
| Overhead allocation (insurance + office + legal + marketing + admin) | $9.80 |
| **All-in cost per scenario at 6-vehicle steady state** | **~$87.00** |

Two different numbers because they answer two different questions:
- **Variable cost ($19.30)** is the marginal cost of one more scenario at steady state. Contribution margin against any ASP is computed against this.
- **All-in cost ($87)** properly amortizes fixed labor + capex + overhead. Gross margin against ASP is computed against this. Honest number for investor / customer scrutiny.

Both numbers improve at higher utilization. Year-1 ramp utilization gives all-in cost closer to $120-$140/scenario; the $87 is the 6-vehicle mature-cadence target.

The hardware capex per vehicle (spec §5.2): drone fleet ~$2,500 (3 × DJI Mini 4 Pro), dock ~$11,000 (materials + custom fabrication), edge compute ~$1,030, sensors ~$630, mounting ~$1,500, spares ~$2,000, contingency ~$3,700 — total ~$22,400 per vehicle in rig capex. **Plus the vehicle itself** (compact hybrid SUV ~$35,000), bringing all-in per-vehicle capex to ~$57,400. Amortized at $7.50/scenario across the fleet's 3-year life. See [COST_MODEL_AUDIT.md](COST_MODEL_AUDIT.md) for the full line-by-line audit.

**Q18. What is the financial impact beyond the direct sale revenue?**

Two additional revenue and value streams we have *not* counted in the base entitlement (Q21) but which materially expand the business:

1. **Corpus access subscription**: once we have a library of 5,000+ scenarios, we can sell annual access to historical scenarios separately from per-scenario capture. Customers who don't need fresh capture but want corpus access pay a subscription ($20K-$200K/year depending on coverage). Estimated $200K-$1M ARR by month 24.

2. **Custom capture engagements**: customers occasionally need a very specific scenario (e.g., a particular intersection at 5:30 PM on Thursday in rain). Custom captures price 3-5× standard rate. Estimated $100K-$300K/year by month 18 as customer relationships deepen.

A third potential stream is *data licensing to academic / non-AV-OEM users* (autonomous-agriculture, robotics, urban-planning research). We have not pursued this in our customer discovery but it represents ~$50K-$200K/year of low-margin revenue if we choose to enable it.

**Q19. What is the pricing strategy? What are the resulting unit economics?**

Pricing is derived bottoms-up from cost-to-replicate (the customer's in-house cost) plus a documented vendor markup band, *not* from spec §4.2's unsourced volume tiers. From [pricing.py](skydock/skydock/pricing.py):

| Cost-to-replicate component | Per scenario |
|---|---|
| Customer operator labour ($100/h loaded × 0.5h/scenario) | $50.00 |
| Annotation / QA (Scale AI public-filing band, low–high) | $30 – $150 |
| Capital amortisation (drone + vehicle + dock) | $6.00 |
| Software / cloud / tooling | $4.80 |
| **Customer internal cost band** | **$91 – $211** |
| Vendor markup band (1.5× – 3.0×, industry-typical for specialty data) | applied below |
| **Skydock price band** | **$136 – $632** |
| **Sim default (mid-cost × mid-markup)** | **$339** |

At the $339 mid-price, unit economics per scenario:
- Revenue: $339
- Variable cost: $19.30
- Contribution profit: $319.70
- Contribution margin: 94%

At a 1,452 scenarios/month run rate (6 vehicles × 22 captures/day × 22 days × ~50% delivery-vs-trigger ratio), this gives:
- Monthly revenue: $492,228
- Monthly variable cost: $28,025
- Monthly contribution profit: $464,203
- Less: operator + vehicle labour ($32K), cloud and infra ($5K), founder + 2 eng + 1 GTM + 0.5 CS at honest loaded comp (~$92K/month, was understated as $30K), insurance + overhead ($13K), capex amortization ($14K) ≈ **$156K monthly opex**
- **Monthly net contribution: ~$308K at steady-state 6-vehicle scale** (mid-case $339 ASP — drops to ~$195K at the $200 weighted ASP across volume tiers)

LTV per vehicle (over 24-month operational period at this pace): ~$1.2M (down from prior $1.4M estimate; see [COST_MODEL_AUDIT.md](COST_MODEL_AUDIT.md) for the honest re-derivation that surfaced ~$60K/year/vehicle of previously under-counted engineering + sales labor).

**Q20. How many units (scenarios) do we project to sell?**

Projection by quarter from MVP launch (Q4 2026) through CFP (Q2 2028):

| Quarter | Vehicles operating | Scenarios captured | Scenarios delivered (~50% rate) | Revenue at $339 mid |
|---|---|---|---|---|
| Q4 2026 | 1 | ~1,200 | ~600 | $200K |
| Q1 2027 | 2 | ~3,000 | ~1,500 | $500K |
| Q2 2027 | 3 | ~5,000 | ~2,500 | $850K |
| Q3 2027 | 5 | ~8,500 | ~4,250 | $1.4M |
| Q4 2027 | 6 | ~10,500 | ~5,250 | $1.8M |
| Q1 2028 | 6 | ~10,500 | ~5,250 | $1.8M (CFP achieved) |

Total scenarios delivered through CFP: ~19,000. Total revenue through CFP: ~$6.5M.

The 50% delivery-vs-trigger rate is the sim's month-6-priors output (Q22 sensitivity) — failed pre-flight, weather aborts, quality threshold rejects, dock failures together reduce delivered scenarios to ~50% of triggered missions. This is the conservative case; sim's optimistic case (95th percentile) gives ~70% delivery rate.

The customer demand to absorb this throughput exists in the §4.1 target list (Q10). Six committed customers at 2,000 scenarios/year average = 12,000 scenarios/year demand; we project 21,000 scenarios/year throughput at 6 vehicles, leaving ~40% capacity for additional customers or corpus accumulation.

**Q21. What are the program-level financials? When does Skydock reach cash-flow positive?**

Program-level financials, 18-month projection from pre-seed close:

| Category | Months 1-6 (MVP build) | Months 7-12 (Pilot phase) | Months 13-18 (Scale to CFP) | Total 18 mo |
|---|---|---|---|---|
| Revenue | $0 | $700K | $5.0M | $5.7M |
| Variable costs | $0 | $30K | $200K | $230K |
| Founder + hires (1-3 FTE ramping) | $300K | $400K | $500K | $1.2M |
| Hardware capex (6 vehicles over time) | $50K | $100K | $50K | $200K |
| Cloud + infra | $5K | $20K | $50K | $75K |
| Sales + marketing | $20K | $80K | $100K | $200K |
| Operations + insurance + overhead | $30K | $80K | $100K | $210K |
| **Period net cash** | **−$405K** | **−$10K** | **+$4.0M** | **+$3.6M** |

CFP achieved in month 14-15 (mid-Q2 2028) under the mid-case sim assumptions. The $1.7M pre-seed funds the negative-cash window (months 1-12) with $300K buffer. Beyond month 18, the business is self-funding; the seed round (if raised) is for growth into new markets, not survival.

**Program-level KPIs and IRR**:
- Revenue at month 18 run-rate: $1.8M/quarter = $7.2M annual
- Gross margin at month-6-priors: ~65% at pilot-tier $339 ASP, ~57% at weighted $200 ASP across volume tiers (honest blended figure)
- LTV per vehicle: ~$1.2M over 24 months (down from prior $1.4M after cost-model audit — see Q17 and [COST_MODEL_AUDIT.md](COST_MODEL_AUDIT.md))
- Total LTV across 6-vehicle CFP fleet: ~$7.2M
- Pre-seed capital deployed: $1.7M
- 24-month IRR (pre-seed dollars to month-18 LTV): ~160% (revised from prior 190% claim; this is sensitive to delivery rate, ASP, and operator utilization — see Q22)

**Q22. How sensitive is the entitlement? What are the key input drivers?**

Sensitivity tornado (from [brief.py](skydock/brief.py) auto-generation, 24 seeds per perturbation, all other parameters held at month-6 priors):

| Input | Range tested | Delivered scenarios / vehicle-day (low → high) | LTV impact |
|---|---|---|---|
| `host_vehicles.count` | 1 → 5 | 11.6 → 49.6 (+38.0) | Linear scaling |
| `trigger.poisson_rate_per_hour` | 1.4 → 3.2 | 10.0 → 14.8 (+4.8) | Diminishing returns above 2.5/h |
| `conditions.wind_mph_amplitude` | 4.0 → 10.0 | 14.5 → 11.5 (−3.0) | Significant; weather-day rescheduling required |
| `probabilities.pre_flight_pass` | 0.90 → 0.98 | 10.5 → 13.1 (+2.6) | Modest; closes via process |
| `conditions.weather_clear_prob` | 0.85 → 0.98 | 9.1 → 11.6 (+2.5) | Modest; weather forecasting closes most |
| `economics.price_per_scenario_usd` | $100 → $250 | 11.6 → 11.6 (+0.0) | No delivery impact; pure revenue lever |

Three cases for the entitlement, anchored on the price sensitivity (the dominant unknown):

- **Pessimistic ($150/scenario, sim p10 delivery rate)**: monthly revenue $245K at 6 vehicles, gross profit $115K, CFP slips to month 22, $300K buffer would need to be drawn down — feasible but tight.
- **Mid-case ($339/scenario, sim mean delivery rate)**: monthly revenue $492K at 6 vehicles, gross profit $387K, CFP at month 15, buffer preserved. This is the base case for the raise.
- **Optimistic ($500/scenario, sim p90 delivery rate)**: monthly revenue $850K at 6 vehicles, gross profit $720K, CFP at month 11, $500K+ surplus by month 18 — would enable expansion to 12 vehicles or a second market without seed round.

The key signal to monitor in the first 6 months: actual ASP from the first 2 paid pilots. If ASP < $150, we redirect the raise to extending runway rather than scaling fleet. If ASP > $300, we accelerate the second-market expansion.

**Q23. What additional opportunities have we not included in the entitlement calculation?**

Six categories of upside not modelled in Q21's mid-case financials:

1. **Corpus subscription revenue** (Q18). $200K-$1M ARR by month 24 from customers buying access to the historical library separately from fresh capture.
2. **Custom capture engagements** (Q18). $100K-$300K/year by month 18 at premium pricing.
3. **Multi-market expansion** (Phoenix, Austin in Q4 2027). The MVP entitlement is Bay Area only; expansion 2-3× revenue without proportional capex.
4. **V2 envelope** (BVLOS, moving-vehicle launch/recovery from spec §1.2). Increases capture capacity per vehicle by ~40%. Estimated +$200K monthly revenue at 6 vehicles, +$2.4M annual.
5. **Data licensing to non-AV customers** (Q18). $50K-$200K/year low-margin additional revenue if pursued.
6. **OpenSCENARIO-adjacent tooling sales**. The customer-facing pipeline (scenario validation, ingestion-format converters) has standalone product potential for AV teams that don't buy our data. Speculative; not in the next 18 months but a credible Series-A thesis.

These collectively suggest $5M-$15M ARR by month 30 against the $1.7M raise — and underwrite the seed-round growth story. The current PR-FAQ is anchored on the pre-seed-to-CFP path, which is the wedge product alone.

---

## Appendix A — Additional Internal FAQs

**Q24. What is the North Star of the product?**

Our North Star is to enable AV development teams to acquire any aerial BEV training scenario they need, anywhere we operate, at a per-scenario cost low enough that aerial BEV becomes a default category in their scenario library rather than a research curiosity. Success is when Applied Intuition's ScenarioLib (or equivalent) lists "aerial BEV" as a checkable category in their procurement pipeline, populated primarily by Skydock data.

**Q25. Tenets (unless you know better ones).**

1. **The customer's existing pipeline is sacred**. Our data drops into their existing OpenSCENARIO workflow without schema rewrite, naming-convention negotiation, or QA process changes. The customer should not have to do work to ingest us.
2. **Every quantitative claim is grounded in the simulation**. No projection in any external document (pitch, pricing, customer SLA) is asserted without a corresponding sim configuration that produces it. If an investor or customer asks "how do you know?", the answer is "run this command."
3. **Spec-target reliability is non-negotiable**. <90% mission success rate is unsellable at $300+ per scenario. Operational reliability is the wedge; we don't ship until the sim tells us we're at the target.
4. **Cost-plus pricing is a starting position, not a destination**. The cost-to-replicate model gives us a defensible opening price. The actual price gets discovered through customer conversations. We update the model when we learn.
5. **The drone is hardware; the operational system is software**. We buy commodity drones. We build operational excellence. Hardware is replaceable; operational learning is not.
6. **One vehicle that works > five vehicles that don't**. Reliability over scale until reliability is proven. The MVP is one vehicle achieving spec targets, not six vehicles producing variance.

**Q26. How do we control which scenes get captured? What's the operator interface?**

The operator has three trigger modalities (spec §1.3):
- **Manual**: physical button or app button to trigger capture at the current waypoint.
- **Pre-planned waypoint**: a list of GPS coordinates with scene-class labels; the vehicle drives the route, and capture auto-triggers when the vehicle arrives at a waypoint (with operator confirmation override).
- **Hard-brake event**: the vehicle's IMU detects a sudden deceleration (>0.3g); the operator gets a one-tap deploy prompt, useful for capturing the scene that caused the brake event.

Per-scene metadata (scene class, target altitude, capture duration, custom waypoints) is set at the route-planning stage in a dispatcher UI. Customers requesting custom scenarios provide a waypoint specification (lat/lon + scene class + capture conditions); the dispatcher integrates it into the next operating day's route.

V2 (post-pre-seed) adds ML-based scene anomaly detection from the forward camera (auto-trigger when the vehicle's view contains an interesting scene). Not in the MVP envelope.

**Q27. How did we choose the camera + drone + dock specifications?**

Three design decisions worth interrogating:

1. **DJI Mini 4 Pro at 249g**: Selected for the sub-250g FAA Remote ID exemption (lowers regulatory burden), the 34-minute flight time (allows 30-120s captures with sufficient battery margin for return + landing), 4K/30fps camera (matches customer expectation for delivery resolution), and the OcuSync 4 transmission (12-mile range, useful for V2 BVLOS expansion). Alternatives considered: Skydio X10 (10× cost, defense-grade, deferred to V2); custom drone (R&D risk, not aligned with pre-seed scope).

2. **Target altitude 80m AGL with 80° diagonal FOV**: Footprint radius = 80 × tan(40°) ≈ 67m, large enough to capture a typical signalized intersection. Higher altitude (120m+) gives wider coverage but pixel-per-agent drops below typical detection thresholds (see resolution penalty in quality methodology). Lower altitude (50m) gives better resolution but smaller footprint and more wind sensitivity. 80m is the sim-optimised midpoint and matches Part 107's 400ft (122m) ceiling with margin.

3. **Custom dock with BLE precision-landing instead of DJI Dock 2**: DJI Dock 2 is $15K and designed for stationary installation; vehicle adaptation would require significant mechanical engineering and would still leave us at 10× the cost. Custom dock (~$1,200 materials + ~$10K engineering) gives equivalent functional precision-landing with the vehicle-mount form factor we actually need. Skydio Dock 2 is even further off the cost target.

**Q28. How did we choose the operational envelope (V1 vs V2)?**

V1 envelope per spec §1.2: vehicle stationary or <5 mph during launch, capture, and recovery; VLOS only; altitude 50-120m AGL; daylight only; wind <20 mph. This is the minimum-viable envelope that we can operate under FAA Part 107 without any waiver, which is essential for pre-seed scope (waivers take 6-12 months and have low single-digit-percent approval rates for novel use cases).

V2 envelope (post-CFP, seed-round-funded): BVLOS waiver, moving-vehicle launch and recovery up to 35 mph, night operations, broader weather. Each V2 capability roughly doubles capture capacity per vehicle. The pre-seed thesis does not depend on V2; V2 is the seed-round growth thesis.

**Q29. Why "Skydock" — branding rationale?**

Three options considered: "Skydock" (chose), "Aerial Scenarios", "Roof Drone Data". Skydock won because:
- It names the *operational primitive* (the dock + drone unit) rather than the *output* (scenarios) or the *form factor* (roof drone). The output and form factor can change; the operational primitive is the wedge.
- It's a defensible product mark, not generic. "Aerial Scenarios" is descriptive and unprotectable.
- It generalises to future products (Skydock Lite for industrial inspection, Skydock Cloud for the corpus subscription product) without renaming.

Risk of confusion with DJI Dock / Skydio Dock products: minimal, because those are stationary drone-in-a-box systems aimed at industrial inspection customers, not data services. Customer-discovery feedback on the name was positive in 7 of 8 conversations.

**Q30. How much do we need to invest in marketing and sales?**

Pre-seed marketing investment is intentionally lean because the target customer base is small (~30 named decision-makers across §4.1 customers) and reached through direct founder-led outreach, not paid acquisition.

- **Months 1-9 (founder-led)**: $0 paid marketing. Founder handles all customer conversations directly. LinkedIn outreach, warm intros, conference presence at AV-Sim 2027 ($10K).
- **Months 10-18 (GTM hire)**: dedicated GTM hire at $180K-$220K loaded compensation. Quota: 4 paid pilots by month 18.
- **Total 18-month sales + marketing budget**: ~$200K in the Q21 financial summary.

This is dramatically lower than a typical consumer or SMB SaaS startup because the buyer is a small named cohort, not a broad market.

**Q31. Why aren't we just licensing the data from internal AV company collections?**

Three reasons:
1. **They don't have aerial BEV in volume**. The point of FAQ #9 is that the category is empty *because* internal teams have failed to collect it.
2. **What they have, they don't sell**. AV companies treat training data as IP. Waymo Open Dataset is the major exception, and it's general-purpose, not edge-case curated.
3. **Even if available, licensing has structural problems**. Customer A's data goes to Customer B's training pipeline; competitive concerns block this.

Skydock collecting data ourselves bypasses all three. We own the corpus, we license non-exclusively to multiple customers, and the data is captured to our specifications.

**Q32. What's the launch timeline? What are the milestones?**

Per spec §5.1, adapted for the pre-seed schedule:

| Milestone | Target | Outcome |
|---|---|---|
| M0: Pre-seed close | Month 0 | $1.7M committed; founder + hardware contractor onboarded |
| M1: First MVP capture | Month 4 | One vehicle operational; first scenario package emitted; reviewed by ≥3 prospects |
| M2: First paid pilot signed | Month 7 | $30K-$80K commitment from a §4.1 customer |
| M3: First paid pilot delivered | Month 9 | 100+ scenarios delivered, customer NPS ≥7 |
| M4: Three-vehicle fleet operational | Month 11 | 1,500 scenarios/month capacity proven |
| M5: Three paid customers | Month 14 | $200K+ MRR, fleet expanding to 5-6 vehicles |
| M6: CFP achieved | Month 15-18 | Monthly net cash positive on operational revenue |
| M7: Seed-round-ready milestone | Month 18 | $400K+ MRR, $5M+ ARR run-rate, 4-6 paid customers, ready for seed if raising |

**Q33. What resourcing is needed to get this launched?**

Headcount + contractor plan over 18 months:

- **Months 1-3**: Founder full-time + 1.0 FTE hardware engineering contractor + 0.5 FTE ML/pipeline contractor. Burn ~$50K/month.
- **Months 4-9**: Founder + 1.0 FTE first full-time engineering hire (drone/ops integration) + 0.5 FTE part-time hardware contractor. Burn ~$45K/month.
- **Months 10-15**: Founder + 2.0 FTE engineering + 1.0 FTE GTM/sales hire + 0.5 FTE operator. Burn ~$70K/month.
- **Months 16-18**: Founder + 3.0 FTE (2 eng, 1 GTM) + 1.0 FTE operator + 0.5 FTE customer success. Burn ~$80K/month (offset by revenue).

Total full-time headcount at CFP: 4 + founder = 5 people. This is intentionally small; the operational excellence required is process-driven more than headcount-driven.

Founder bio: [TO BE FILLED IN BY KRETHIK — what's your background, why are you specifically the right person to build this? This is the single highest-leverage paragraph in the document for a pre-seed investor.]

**Q34. What's launching first — US or other markets? Why sequential vs simultaneous?**

US (specifically Bay Area) only for the pre-seed. Rationale:
- FAA Part 107 is the regulatory envelope we know; EU EASA equivalent has different and slower-evolving rules.
- §4.1 customer base is US-headquartered (Applied Intuition, Foretellix, Parallel Domain all US; Cognata Israel-based but US-active).
- One regulatory regime + one operator pool + one customer relationship management = lower coordination overhead.
- Bay Area specifically because (a) high customer concentration, (b) regulatory familiarity, (c) operator hiring depth.

Phoenix expansion (Q4 2027): warm-weather year-round operation, AV testing density, Waymo / Cruise presence. Austin expansion (Q1 2028): Tesla / GM partnership zone, growing AV test fleet, lower operating cost.

EU expansion deferred to post-seed; the regulatory work alone is 9-12 months of preparation.

**Q35. What are the biggest risks and how are they mitigated?**

Honest risk register, prioritised by impact-probability product:

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Customers refuse to pay $339/scenario; actual ASP lands at $150 | 40% | High | (a) Sim shows CFP still reachable at $150 with 6-month slip; (b) buffer in raise covers slip; (c) ASP signal in first 2 pilots informs fleet-size decision. |
| MVP reliability < sim's month-6 priors; success rate stuck at 70% | 30% | High | (a) 6-month build phase before paid pilots; (b) sim's v0-defaults case is the 70% scenario, and CFP still reachable at 6 vehicles albeit slower; (c) explicit reliability gate at M2 (paid pilot signature) — if we're not at 80%+ success rate, we hold paid pilots. |
| FAA Part 107 issue (e.g., novel-use-case review) | 20% | Medium | V1 envelope is intentionally inside well-trodden Part 107 territory. Pre-flight legal review with an aviation lawyer in month 1-2. |
| Customer says "synthetic data is enough" | 15% | Medium | (a) Customer discovery already disconfirms this for 7 of 8 leads; (b) sim-grounded pricing band lets us drop price to $150 if needed. |
| Skydio or DJI enters as a direct competitor | 10% | High | (a) 12-18 month time-to-market window; (b) operational moat + corpus + customer integration accrue over time; (c) pre-seed → seed transition should happen before any competitor ships. |
| Solo founder burns out or has a critical event | 10% | Critical | First engineering hire in month 4-7 has operational + technical context to continue in founder's absence. Co-founder search active but not gating. |
| Drone flyaway / fleet incident causing reputational damage | 5% | High | Insurance ($1-3K/year per spec §7.3), redundant fleet (3 drones per vehicle so a loss doesn't stop operations), public communications plan ready for incident. |

The two risks with the largest impact-probability product (ASP < $339 and reliability < month-6-priors) both have sim-quantified mitigations and converging signals in the first 6 months. We will know early whether the thesis is on track.

---

## Appendix B — Customer discovery summary (March-April 2026)

8 conversations with AV-industry leads, all under non-disclosure but anonymised here:

| # | Role | Company type | Key takeaway |
|---|---|---|---|
| 1 | Head of Scenario Engineering | Tier-1 validation platform | "Aerial BEV is the perspective we'd been trying to source internally for two years." Would commit to a 200-scenario pilot at $300-$400/scenario subject to quality review. |
| 2 | VP of Simulation | Top-5 OEM | Confirmed aerial BEV gap in library. Procurement cycle 6-9 months. Pricing tolerance $200-$500/scenario. |
| 3 | Head of Validation | Synthetic-data company | Buys real data to validate synthetic generators. Would buy aerial BEV non-exclusively. $200K annual budget mentioned. |
| 4 | Director of AV Test | Top-10 AV company | Library budget $2M/year, currently 90% spent on simulated data. Open to aerial BEV at $300/scenario if quality validates. |
| 5 | CTO | Sim-platform startup (post-Series A) | Less interested as a direct customer; more interested in partnership / data-sharing. Could become a channel partner for their customers. |
| 6 | Research Lead | AV academic lab | Free / low-cost interest only; not a paying customer but useful for sample validation. |
| 7 | Head of Data | Logistics-AV company | Strong interest in custom-scenario commissioning. Pricing tolerance higher ($500+/scenario) but smaller volume (50-100/year). |
| 8 | VP of Engineering | Tier-2 robotaxi co. | Confirmed library gap. Procurement gate is internal QA validation of first 20 scenarios. |

Across 8 conversations: 7 confirmed library gap, 6 confirmed pricing tolerance ≥$200, 4 expressed commit-intent for a pilot subject to quality evidence.

## Appendix C — Competitive analysis table

| Player | Product | Pricing | Distinction from Skydock |
|---|---|---|---|
| DJI | Mini 4 Pro + Dock 2 | $15K dock + $760 drone | Stationary; not vehicle-mounted; sells hardware not data services |
| Skydio | Dock 2 + X10 | $40K+ | Defense-grade stationary; not vehicle-mounted; no data services |
| Percepto | Air Mobile | Industrial pricing | Vehicle-mounted but industrial inspection use case; not AV data |
| Parallel Domain | PD-Replica | Per-scenario synthetic | Synthetic BEV; complementary, not competitive |
| Datagen | Synthetic CV data | Subscription | Synthetic; primarily indoor / vehicle interior |
| Mira Scenario | Synthetic library | Per-scenario | Synthetic; AV-specific |
| DataFromSky | Traffic analytics | Per-analysis | Aerial but stationary; analytics output, not training data |
| Internal AV teams | Manual drone collection | Internal cost $1K+/scenario | Caps at 2-4/day capacity |

## Appendix D — Sample deliverable schema

Per-scenario file structure (auto-generated by `skydock/deliverable.py`):

```
scenario_skydock-mission-00042/
  metadata.json           # scene class, location, capture geometry, camera calibration, GPS uncertainty, quality
  agent_tracks.json       # per-agent ENU positions, 30 fps interpolated from sim agent model
  scenario.xosc           # OpenSCENARIO 2.0 stub with entities + road network reference
```

Sample sizes:
- metadata.json: ~2 KB
- agent_tracks.json: 50-500 KB (depending on agent count and capture duration)
- scenario.xosc: ~5 KB
- Raw 4K video (optional): 200-600 MB

A sample package can be auto-generated by running `python run.py --emit-packages out/scenarios` against the simulation; the output is the same shape and methodology as production.

## Appendix E — Methodology references

- Drone hardware spec: DJI Mini 4 Pro public datasheet.
- Camera FOV: DJI Mini 4 Pro specifications; sensor 1/1.3" CMOS, 24mm equivalent focal length.
- Battery model: linear discharge calibrated against DJI's 34-minute published flight time.
- Wind physics: point-mass with proportional velocity control + horizontal wind coupling at 0.18 m/s per mph (calibrated against published quadcopter wind tolerance).
- GPS uncertainty: consumer GPS 2.5m 2σ (standard reference: u-blox NEO-M9N spec).
- Dock latch model: geometry-based, calibrated against commercial drone-in-a-box reported tolerances (DJI Dock 2 ~ 60cm; we use 1.5m to reflect BLE-augmented precision landing in our custom design).
- OpenSCENARIO format: ASAM OpenSCENARIO 1.2 specification (publicly published standard).
- Annotation rate references: Scale AI public S-1 filings (2024) and Mighty AI acquisition press materials (2019).

Full simulation methodology is in `brief.py` output and `skydock/` repo.

---

*Last updated: May 2026. This is v2 of the PR-FAQ, restructured to match the Amazon canonical format. Source artefacts: [skydock simulation repo](.), [brief.md](out/brief/brief.md), [sample deliverable](out/scenarios/).*
