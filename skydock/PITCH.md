# Skydock — Pre-seed PR-FAQ (V2)

**Executive Summary:** Today we will discuss the product idea and business opportunity for Skydock. We are seeking **$2.2M pre-seed funding** to build the V2 architecture: a fixed-point aerial BEV capture network feeding a validation-grade scenario library that AV safety teams subscribe to. Cash-flow positive operations on a 5-7 site Bay Area + adjacent footprint by **months 18-20** with $900K-$1.2M ARR run-rate (see [V2_EXECUTION_PLAN.md](V2_EXECUTION_PLAN.md) and [V2_FINANCIAL_MODEL.md](V2_FINANCIAL_MODEL.md)). Reasons why this is a good investment: (1) AV safety teams have a structurally non-substitutable need for *independent* validation-grade scenario libraries that synthetic data cannot satisfy (FAQs #9, #11, #15, #16); (2) fixed-point capture economics — already validated commercially by levelXdata's 7-year German precedent — deliver $2/scenario all-in cost vs $87/scenario in the V1 mobile model we abandoned (FAQ #17); (3) the curation pipeline (5-signal scoring on every captured scenario) is the defensible product layer that raw clips cannot displace (FAQ #12); (4) at maturity (Year 3-5), 15 sites + 15 customers + Library subscription model delivers $4-8M ARR at 45-62% gross margin with multi-tenant corpus growth as the moat (FAQ #21); (5) the closed-loop pilot conversion structure — free 30 days, jointly-authored success criteria, conversion to annual subscription — aligns customer purchase decisions with measured safety-case improvements they verify on their own held-out evals (FAQ #4). Founder comp: $150K cash + $50K/yr deferred + benefits = $200K cash-loaded through Phase 4 (deferred portion accrues as $75K liability payable from seed close).

**This V2 architecture replaces the V1 mobile-dock approach** documented in earlier drafts. The V1 mobile-dock model fought physics on unit economics (one vehicle + operator delivers ~60 seconds of capture; drives 30 minutes to next site) and sold the commodity layer (raw captures) while disclaiming the defensible one (curation). V2 inverts both. The thesis is in [SKYDOCK_V2_THESIS.md](SKYDOCK_V2_THESIS.md).

---

## Skydock: Validation-Grade Aerial BEV Scenario Library for AV Safety Teams

**SAN FRANCISCO, CA — (Business Wire) — September 24, 2027** — Today Skydock announced the production release of its validation-grade aerial bird's-eye-view (BEV) scenario library for autonomous vehicle (AV) safety teams, with six AV companies under paid annual subscription, five active fixed-point capture sites across the Bay Area, and a multi-tenant library of 35,000+ criticality-scored scenarios used in closed-loop safety case evaluation by the company's customers.

The AV industry has converged on closed-loop simulation as the gating mechanism for production safety cases. NHTSA's AV STEP framework, the EU AI Act's high-risk system requirements, and the UK CCAV safety-case process all increasingly require independent validation evidence — evidence that synthetic data libraries cannot provide because they share the underlying generative assumptions of the systems being validated. Skydock fills this gap with continuous overhead capture at high-incident US intersections, processed through a 5-signal curation pipeline (criticality, epistemic uncertainty, corpus frequency, multi-agent interaction density, scene-class taxonomy match) and indexed against customers' OpenODD coverage models. Subscribers query the library via API and partner integrations (Foretellix, Applied Intuition Validation Toolset, CARLA).

> *"The Skydock library closed a gap we'd been trying to fill internally for three years. We measured our collision rate before and after adding their criticality-scored scenarios to our held-out eval, and the reduction was meaningful enough that our safety case timeline pulled forward by a full quarter. The curation is what we're paying for, not the raw captures."*
> — **[Head of Safety Case, Pilot Customer]**

Each Skydock fixed-point site captures continuously during the operational envelope using one of three deployment models: a Model A rooftop installation (high-resolution camera + edge compute + cellular uplink mounted on a partner building rooftop overlooking the target intersection), a Model B tethered drone (LTE-tethered drone hovering 50-150m AGL indefinitely with simplified Part 107 tethered-ops registration), or a Model C drone-in-a-box (DJI Dock 2 / Percepto persistent ground station deployed post-BVLOS waiver clearance). Raw candidate scenarios — approximately 5,000 per site-month — pass through the curation pipeline. A scenario must score in the top 20% on at least two of five signals to enter the delivered library; approximately 80% of raw captures are filtered out, matching Waymo's WOD-E2E human-review acceptance rate.

> *"We sell the filtered, scored library — not the bucket of raw clips. That's the difference between commodity drone capture and validation-grade infrastructure. Curation methodology is the moat; site footprint is the substrate."*
> — **Krethik Ram, Founder, Skydock**

Skydock operates an FAA Part 107 commercial license; per-site operators hold individual remote pilot certificates. Library subscriptions price at $100K-$500K/year by access tier, with custom site deployment ($50K-$150K per new site) and time-bounded exclusivity (2-5× standard subscription rate) as expansion products. The company plans to expand to 7 active sites across Bay Area, Phoenix, and Austin by Q4 2028, with EU expansion on the post-seed roadmap. Skydock is backed by [pre-seed investors] and is based in San Francisco, CA.

---

## Customer FAQs

**Q1. What is the Skydock Library?**

The Skydock Library is a continuously-growing, criticality-scored collection of aerial bird's-eye-view scenarios captured from fixed-point installations at high-incident US intersections. Every scenario is a 30-300 second BEV recording captured at 50-120m AGL, scored across 5 independent signals (criticality, epistemic uncertainty, corpus frequency, multi-agent interaction density, scene-class taxonomy match), tagged with OpenODD axis metadata, and delivered in ASAM OpenSCENARIO 2.0 + OpenLABEL format. Subscribers access the library via API, with filterable queries on scene class, criticality bin, agent count, geography, time-of-day, weather, and OpenODD axis match. New scenarios are added continuously: ~1,000 scored scenarios per site per month after the curation filter, ~60,000 net-new scenarios per year added to the corpus all subscribers can query at 5 active sites.

**Q2. How does the closed-loop pilot work?**

The pilot has three phases, structured so the customer measures the value themselves on their own safety case:

- **Phase 0 (free, 30 days):** Skydock delivers 100 criticality-scored scenarios from a customer-specified Bay Area intersection (or a site from our active list). All 5 curation signals are tagged. Customer imports into their closed-loop simulation pipeline. No charge, no NDA.
- **Phase 1 (measurement, 30 days):** Customer measures their AV's collision rate on their existing held-out evaluation set, segmented by criticality bin, before and after augmenting with the Skydock scenarios. Success criteria are jointly authored before pilot start — typically a ≥10% collision-rate reduction in at least one criticality bin, or coverage-gap closure on ≥3 OpenODD axes.
- **Phase 2 (conversion):** If success criteria are met, customer signs an annual Library subscription at the agreed tier ($100K-$500K). 12-month initial commitment, 30-day notice for renewal.

Joint authorship of success criteria in advance binds the conversion economics before either party has skin in the game. The structure matches the Forrester 2023 finding that predefined success criteria lift pilot-to-paid conversion 3.2×.

**Q3. How do I access the library? What's the format and integration?**

Standard access is via the Skydock library API with filterable queries on the curation signals + scene-class taxonomy + OpenODD axes. Delivery format is OpenSCENARIO 2.0 + OpenLABEL natively, dropping into Foretellix, Applied Intuition Validation Toolset, CARLA, Cognata, or any internal closed-loop sim pipeline without schema rewrite. Partner integration available with Foretify and Applied Intuition Validation Toolset for in-tool query/import. Enterprise tier subscribers can request custom S3 bucket targeting, SFTP delivery, or streaming-API endpoint integration. Each scenario package is a directory containing `metadata.json` (5-signal curation scores, OpenODD tags, site ID, capture geometry), `agent_tracks.json` (per-frame ENU agent positions at 30 fps), `scenario.xosc` (OpenSCENARIO 2.0 export), and optionally `raw_video.mp4` (4K H.265 source video — toggleable by subscription tier).

**Q4. What's the pricing? How do subscription tiers work?**

Library subscriptions are annual, with 30-day notice for renewal. Tier is based on access scope (which sites, which scene classes, how much of the corpus) and on integration depth:

| Tier | Scope | Annual |
|---|---|---|
| Starter | 1 metro library access (Bay Area), 3 scene classes, API access | $100K |
| Standard | 1 metro full access, all scene classes, OpenLABEL + OpenSCENARIO, partner integration | $250K |
| Production | All US metros, all scene classes, all corpus tiers, raw 4K access, expansion priority | $500K |
| Enterprise | Production + custom taxonomies + custom-capture rights + exclusivity windows | Custom |

Expansion products (priced separately):
- **Custom site deployment:** $50K-$150K per new site (Model A $50K / Model B $100K / Model C $150K) — customer specifies high-criticality intersection in their operating area, we deploy if economics justify, capture for 6-12 months folds into subscription
- **Time-bounded exclusivity:** 2-5× standard subscription rate for the exclusive window — useful for safety-case-sensitive deployments
- **Custom taxonomies:** bundled in Standard tier and above; ~1 week scoping

See FAQ #19 for the bottoms-up subscription pricing methodology.

**Q5. Can I get capture from a specific intersection?**

Yes — through custom site deployment. You specify a high-criticality intersection in your operating area (typically tied to a safety-case requirement: specific Waymo operating corridor, specific OEM test deployment zone, specific high-incident location flagged by your QA). We deploy a Model A/B/C site at $50K-$150K setup cost depending on deployment model. Capture for 6-12 months, then the captured scenarios fold into your Library subscription. Site selection is one of our highest-leverage decisions, so customer demand signal weights heavily on what we build next. Custom taxonomies (your internal scene-class definitions, your OpenODD axis labels) onboarded in ~1 week and bundled in Standard tier and above.

**Q6. What's the data quality methodology? How do I know what I'm subscribing to?**

Every scenario carries two score blocks in its `metadata.json`. **Capture quality (0-100):** 60 points from agent visibility ratio (frames each agent was inside the capture FOV / total frames observed), 20 points from agent coverage (saturated at 70% of spawned agents to reflect realistic FOV limits), 20 points from agent class diversity (vehicle / pedestrian / cyclist representation). Multipliers: altitude-resolution factor (1.0 at 80m AGL, decreasing above), wind-shake factor (1.0 at ≤12 mph, decreasing above with 10% floor for Model B/C sites). Scenarios scoring below 70 are not added to the library; no exception, no opt-in.

**Curation scores (per scenario, for QA team filtering):**
1. **Criticality:** TTC, PET, jerk thresholds, near-miss detection — Westhofen et al. 2021 catalog
2. **Epistemic uncertainty:** per-frame score against baseline perception detector — Mining the Long Tail methodology (arXiv 2508.18397)
3. **Corpus frequency:** rarity ranking vs growing Skydock library — Waymo WOD-E2E <0.03% threshold methodology
4. **Multi-agent interaction density:** distinct agent interactions per scenario — InterHub methodology (Nature Scientific Data 2025)
5. **Scene-class taxonomy match:** alignment with customer's OpenODD axes

A scenario must score in the top 20% on at least 2 of 5 signals to enter the library. ~80% of raw captures are filtered out — matching Waymo WOD-E2E's 30% human-review acceptance rate.

**Q7. How does the system handle weather, time of day, and the operating envelope?**

Capture happens during the regulatory envelope — civil daylight only in V1 (sunrise +30 min to sunset −30 min) for Part 107 stationary observation. V2 envelope expands with BVLOS waiver clearance (filed M1 of operations; expected resolution M9-M12). Capture is rejected at wind >20 mph or non-clear weather for Model B/C sites (tethered and drone-in-a-box). Wind-shake quality penalty kicks in above 12 mph average wind during capture. Model A rooftop captures continue through most weather since the camera is fixed-mounted on a partner building. Operating envelope is documented in scenario metadata so subscribers can filter the library by capture conditions — useful when validation needs only fair-weather data, or specifically wants edge-weather scenarios.

**Q8. What's the SLA and what happens if a site goes offline or a scenario fails?**

SLA: 99.5% library API availability per calendar month (excluding planned maintenance); 99% of newly-captured scenarios at operational sites reach the subscription library within 48 hours of capture; 95% of delivered scenarios pass the published capture quality threshold (≥70). Per-site uptime targets ≥95% of operational-envelope hours captured. Outages past 72 hours trigger pro-rated subscription credit. Library subscribers retain access to all already-captured scenarios from a site even if the site is paused or decommissioned. If your QA team identifies documented schema or content issues with a library scenario within 30 days, credit applies toward subscription renewal. Production and Enterprise tier subscribers can negotiate custom availability, latency, and quality SLAs in the master service agreement.

---

## Internal FAQs

**Q9. What customer problems are we solving?**

AV safety teams cannot satisfy the closed-loop collision-rate gates in their safety cases without *independent* validation-grade scenario libraries — and synthetic libraries cannot serve that role because they share the underlying generative assumptions of the system being validated. NHTSA AV STEP, EU AI Act, and UK CCAV all increasingly require independent validation evidence; synthetic data fails the independence requirement by construction. Internal capture from the customer's own fleet has correlated errors with the model being tested. Aerial BEV captured from a sensor system independent of the customer's vehicle stack provides the structural independence the safety case requires.

We commissioned conversations with AV safety teams in May 2026 (V2-pivot discovery phase, refocused from V1's perception/training-team list); the consistent feedback was: (a) closed-loop collision-rate evaluation is the production deployment gate; (b) aerial BEV is the data class they need but cannot economically capture at scale; (c) curation methodology (criticality scoring, OpenODD axis tagging) matters more than raw scenario count. The category exists and the customer pain is documented, but the operational system to populate it at validation-grade quality has not been built. See FAQs #10–#11 for market sizing and competitive landscape.

**Q10. Who are the target customers and why?**

The target customer is an AV safety team or regulatory safety officer at an AV company or OEM with a defined closed-loop validation gate in their safety case. The V2 customer cohort shifted from V1's "scenario validation platforms + perception teams" to "safety teams + regulatory safety officers" because safety teams have the structurally non-substitutable need for independent ground truth, whereas perception teams have shrinking willingness-to-pay as world models manufacture infinite training data.

| Customer | Buying behaviour | Likely deal shape | Target year |
|---|---|---|---|
| Safety teams at Tier-1 AV companies (Waymo, Cruise, Aurora, Zoox) | Closed-loop validation is gating; willingness-to-pay tied to regulatory deadlines | $250K-$500K Library subscription | Year 1-2 pilots |
| OEM regulatory safety officers (GM, Ford, Toyota, Mercedes, Stellantis) | Slower cycle; tied to NHTSA AV STEP submissions | $300K-$1M Library subscription + custom sites | Year 2-3 |
| Validation platforms (Foretify, Applied Intuition Validation Toolset) | Channel partners — sell Library access through integration | Channel: rev-share or co-sold subscriptions | Year 2+ |
| Logistics/trucking AV (Aurora Innovation trucking arm, Kodiak Robotics, Embark legacy) | Tighter unit economics; subscription cost-benefit clear on safety-case-tied revenue | $100K-$250K Starter/Standard | Year 1-2 |
| Robotaxi operators in pilot phase (Pony.ai, May Mobility, Zoox launch) | Subscription tied to operating-area expansion | $250K-$500K Standard/Production | Year 2-3 |

The decision-maker is the **Head of Safety Case** or **Director of Safety Engineering** — typically a former regulatory or safety-critical-systems lead with budget authority in the $250K-$2M/year range for validation infrastructure. This is a smaller, more durable customer base than V1's perception-team list. Safety teams are the part of an AV company that cannot substitute synthetic for real ground truth.

**Q11. What alternatives exist today? Why haven't they captured the validation-grade aerial BEV market?**

Five categories of alternatives:

1. **Synthetic scenario libraries** (Parallel Domain, Mira, Datagen, NVIDIA Cosmos, Wayve GAIA-3). Strong on volume, weaker on edge-case fidelity. **Cannot serve as independent ground truth in a safety case** because the model being validated trained on the same generative assumptions. Used alongside real data by every safety team we spoke to, not as a substitute for it in validation gates.
2. **Replay from internal fleet** (every AV company runs this). Adequate for monitoring deployed-AV performance; insufficient for the independence required by safety case. Internal capture has correlated errors with the model being tested; ego-perspective limits visibility into multi-agent interactions.
3. **levelXdata (highD/inD/rounD/exiD)**. Established commercial aerial datasets — the 7-year fixed-point hover precedent that validates the unit economics of our architecture. German highways/intersections/roundabouts only. Fixed-location captures from one-time research collections, no on-demand library growth, no criticality scoring, no OpenODD axis tagging. Useful for training; weaker for safety case.
4. **Academic datasets** (openDD, MiTra, DeepUrban, AUTOMATUM, InteractionDataset). Fixed snapshots from one-time research collections. Free for research, commercial use restricted. No criticality scoring, no library growth, no SLA.
5. **Internal drone teams** (4-6 AV companies run small internal drone ops). Capacity caps at a few captures per day per crew. Operational overhead, FAA Part 107 compliance, dedicated drone-ops engineering pulls senior eng off core work. Result: stale, small, single-geography internal library.

None of these solutions has captured the validation-grade aerial BEV category because the structural requirements — continuous fixed-point capture + 5-signal curation + OpenODD axis tagging + safety-case-grade SLA + multi-tenant corpus — require coordinated operational + curation methodology investment that no incumbent has assembled. levelXdata is the closest precedent but is anchored on German fixed datasets without the US footprint or curation depth safety teams need. Our wedge is the integrated system + US coverage + curation IP, not the drone or the BEV transform individually.

**Q12. What gives us confidence that we can do better with our system than existing solutions?**

Four reasons:

1. **The architecture problem has been solved by precedent.** levelXdata has proven for 7 years that fixed-point hover capture at high-incident intersections delivers commercial-grade trajectory libraries at unit economics that close. highD recorded 110,000 vehicles from a single hovering drone over a German highway in 16.5 hours. We are extending this proven architecture with US coverage, criticality scoring, and OpenODD axis tagging — not inventing a new operational primitive.
2. **The curation pipeline is the defensible product layer.** Raw drone captures are a commodity headed toward synthetic substitution. Curated, criticality-scored, OpenODD-tagged libraries that gate safety cases are the moat. The 5-signal curation methodology (criticality + epistemic uncertainty + corpus frequency + interaction density + taxonomy match) compounds over time as the multi-tenant corpus grows. Safety teams cannot rebuild this internally because they lack the cross-customer corpus that gives the corpus-frequency signal meaning.
3. **Validation positioning sits on the side of regulation.** NHTSA AV STEP, EU AI Act, UK CCAV all push the industry toward independent validation evidence. World models manufacturing infinite training data erode training-data willingness-to-pay every generation; validation-data willingness-to-pay grows with every regulatory requirement. We sit on the right side of this curve.
4. **The hardware is commodity.** DJI Mini 4 Pro and Skydio X10 are off-the-shelf hardware. The custom Model A rooftop installation (camera + edge compute + cellular + power) is a straightforward integration project. We're not asking investors to fund hardware R&D — we're asking them to fund the curation IP, the site network, and the customer-facing API + safety-case integration work.

See FAQ #13 for our existing competence, FAQ #15 for "why now," and FAQ #16 for why this is the right approach vs synthetic-only.

**Q13. Do we have competence in this space, and if not, can we acquire it quickly?**

Yes, partially, and the gaps are well-scoped:

- **Domain thesis + curation methodology research**: ✓ established. The thesis is grounded in published research (Westhofen 2021 criticality catalog, Mining the Long Tail 2025 epistemic-uncertainty methodology, Waymo WOD-E2E corpus-frequency threshold, InterHub interaction-density methodology, ASAM OpenSCENARIO + OpenLABEL standards). The 5-signal curation pipeline maps directly onto these published methods.
- **AV scenario format + validation pipeline architecture**: ✓ established. OpenSCENARIO 2.0 and OpenLABEL are published ASAM standards. YOLOv8 + ByteTrack are proven object-detection and tracking models with reference implementations. The library API + customer integration work is straightforward ML-ops integration, not novel research.
- **Fixed-point site deployment + operations**: contractor required for Model A integration. Camera + edge compute + cellular + mount + power are commodity hardware integration. Model B tethered drone deployment uses commercial tethered-drone systems with simplified Part 107 registration. Model C drone-in-a-box uses DJI Dock 2 or Percepto with BVLOS waiver (filed M1; expected resolution M9-M12).
- **FAA Part 107 + BVLOS waiver process**: required, with documented preparation path. V1 envelope (Model A + Model B stationary or tethered ops) is within standard Part 107 — no waiver dependency. V2 envelope (Model C drone-in-a-box at expansion markets) requires BVLOS waiver, filed M1 of operations as an explicit milestone with a 6-12 month expected resolution timeline (FAA BVLOS waiver approval rates have improved with Part 108 progress).
- **Rooftop access negotiation + site selection**: founder-led for first 3 sites; documented site-selection methodology (criticality density from city/state DOT data + customer demand signal + building access tractability) used in subsequent rollout.
- **Customer discovery + enterprise sales**: founder-led for the first 4 paid customers, then a dedicated GTM hire in month 11 specifically targeting AV safety teams.

Capabilities that need to be built: the curation pipeline at production scale (5-signal scoring on every captured scenario, OpenODD axis tagging, multi-tenant corpus management), and the rooftop-partner negotiation process. Both are the explicit deliverables of the M1-M6 build phase in [V2_EXECUTION_PLAN.md](V2_EXECUTION_PLAN.md).

**Q14. Why is this important for us / what does success mean for the founder?**

Three layers:

1. **The validation gate is on the critical path of AV commercialization.** Every AV company that wants to ship in 2027-2029 needs to close their closed-loop safety case. Aerial BEV captured by an independent operator is the structurally non-substitutable data class for that gate. Whoever builds the validation-grade library first establishes the integration moat with safety teams — and integration moats with safety-critical workflows are slow to displace. levelXdata took 7 years to establish their German precedent; we have the opportunity to establish the US precedent in the next 18-24 months.
2. **The product extends into a platform.** Library subscriptions are the wedge. Adjacent products that share the same site network, curation pipeline, and customer relationships: custom site deployment, time-bounded exclusivity, OpenSCENARIO-adjacent tooling, V2X data products, regulatory-evidence-as-a-service. The pre-seed funds the wedge; the seed/Series-A funds the platform.
3. **Founder commitment.** This is what I'm building. Pre-seed solo founder, full-time on the project, deep-tech background applicable to the curation + site integration + customer-facing API work. Co-founder search is active but not gating; first engineering hire in M5 has operational + technical context to take operational continuity if a critical event hits.

**Q15. Why now?**

Three converging timing pressures make 2026-2027 the right window:

1. **NHTSA AV STEP framework finalization (2025).** The voluntary AV safety, transparency, and evaluation program is finalizing through 2025-2026, moving scenario-based closed-loop validation from research curiosity to procurement line-item for AV companies preparing production deployment. Scenario libraries are no longer optional; they're regulatory infrastructure.
2. **World model substitution forces validation differentiation.** Wayve GAIA-3 (December 2025) and NVIDIA Cosmos demonstrate that training data is becoming infinitely manufacturable. Training-data willingness-to-pay erodes every generation. Validation data — where independence is a structural requirement, not a preference — survives this. The next 18 months are when the industry sorts companies that compete in the training-data race from companies that occupy the validation differentiation. We're explicitly in the second camp.
3. **Site footprint lock-in.** Whoever builds the first credible US fixed-point capture network at validation-grade quality captures the customer integration relationships first. Once Skydock data is integrated into a safety team's closed-loop sim pipeline (library API, OpenLABEL schema, OpenODD axis tagging, QA workflow, billing), switching cost is real. We have an estimated 18-24 month window before levelXdata enters US markets or before a vertical integrator (Foretify, Applied Intuition, or an OEM safety team) builds equivalent capture themselves.

We have not seen a US fixed-point validation-grade aerial BEV library product launch announcement as of the current cycle. The category window is open.

**Q16. Why should we invest in real aerial BEV when synthetic data is rapidly improving?**

Synthetic data and real validation-grade aerial BEV serve different roles in the AV development cycle, with structurally different willingness-to-pay trajectories:

- **Training:** synthetic data is rapidly substituting real data. Cost approaches zero per scenario. Real-data willingness-to-pay erodes. This is the race we are explicitly not competing in.
- **Validation:** synthetic data cannot serve as independent ground truth in a safety case. NHTSA AV STEP, EU AI Act, UK CCAV all increasingly require independent validation evidence. Real-data willingness-to-pay grows with each regulatory cycle. This is where we sell.

A direct cannibalization question: as synthetic libraries get better, do safety teams stop subscribing to Skydock? Our view: no, the opposite — better synthetic libraries make the independence problem more acute. If your synthetic training data is generated by the same world model your closed-loop sim runs against, the validation evidence is circular. Safety teams will increase, not decrease, the share of their validation library that comes from independent real-world capture as synthetic capabilities improve. The trend that hurts training-data vendors helps validation-data vendors.

**Q17. What is the per-delivered-scenario cost?**

V2 fixed-point unit economics, derived in [V2_FINANCIAL_MODEL.md](V2_FINANCIAL_MODEL.md):

| Component | Annual per Model A site | Per delivered scenario |
|---|---|---|
| Capex amortization (5-year life on $25K Model A install) | $5K | $0.42 |
| Operating (rooftop lease + cellular + cloud + insurance) | $9K | $0.75 |
| Centralized curation labor allocation (1 FTE per ~5-10 sites at $80K loaded) | $10K | $0.83 |
| **Total annual cost per site (Model A)** | **$24K** | **~$2.00** |
| Annual delivered scenarios per site (after 80% curation filter) | ~12,000 | — |

Comparison with V1 mobile-dock model we abandoned: V1 all-in cost was $87/scenario at 6-vehicle steady state ([COST_MODEL_AUDIT.md](COST_MODEL_AUDIT.md), now stale as a V1 artifact). The 43× unit-economics improvement is what made the V2 architecture pivot necessary — V1 mobile fought physics on per-scenario delivery cost; V2 fixed-point absorbs the continuous-capture economics levelXdata proved commercially over 7 years.

Per-site deployment models and capex (more detail in V2_FINANCIAL_MODEL.md):
- **Model A (rooftop):** $25K capex, $9K/yr operating, simplest regulatory path
- **Model B (tethered drone):** $40K capex, $11K/yr operating, simplified Part 107 tethered-ops
- **Model C (drone-in-a-box):** $50-80K capex, $15K/yr operating, requires BVLOS waiver

The 18-month plan deploys 5 sites by M12 (3 Model A + 2 Model A) and 7 sites by M18 (5 Model A + 2 Model B). Model C deployment begins post-seed (Phoenix + Austin expansion).

**Q18. What is the financial impact beyond the direct subscription revenue?**

Three additional revenue and value streams not modeled in Q21's base entitlement but which materially expand the business:

1. **Custom site deployment:** Customer-specified high-criticality intersection deployment at $50K-$150K per site setup. Captures fold into the customer's subscription for 6-12 months. Modeled at one custom site M14 ($75K) in the base entitlement; could deliver $200K-$500K/yr expansion revenue by M24 as the customer base grows.
2. **Time-bounded exclusivity:** 2-5× standard subscription rate premium for safety-case-sensitive deployments. Customers we expect to consider this: OEMs preparing first NHTSA AV STEP submission, Tier-1 robotaxi operators in geographic launch windows. Estimated $300K-$1M ARR by M24 at maturity.
3. **Channel revenue via validation-platform partners:** Foretify, Applied Intuition Validation Toolset, CARLA integrations allow Skydock library access to be sold through partner channels with rev-share or co-sold models. Estimated $200K-$500K/yr by M30 as partner integrations mature.

A fourth potential stream — **regulatory evidence-as-a-service** — bundles library access with safety-case documentation support for OEMs preparing NHTSA submissions. Not modeled in the 18-month plan; speculative seed-round growth thesis.

**Q19. What is the pricing strategy? What are the resulting unit economics?**

Library subscription pricing is derived from three anchors:

1. **Customer's in-house cost-to-replicate (cost-plus floor).** Customer running internal drone capture at the same site footprint would face: 1 senior eng × 0.5 FTE × $250K loaded = $125K/yr; 1 Part 107 operator × $80K = $80K/yr; capex amortization $5K-$15K/yr; operational overhead $30K = $240K-$250K/yr for *one site* internally, with no curation pipeline and no multi-tenant corpus benefit. Our Standard tier ($250K) is roughly the customer's cost for *one site* internally — they get full-corpus access (5+ sites at maturity) plus curation IP for the same outlay.
2. **levelXdata commercial precedent (industry comparable).** levelXdata's commercial licensing for highD/inD/rounD is in the $50K-$200K/yr range per dataset, validating willingness-to-pay for fixed-location aerial trajectory libraries at this price tier. Our Standard tier sits at the upper end of the levelXdata range for materially more (US coverage + criticality scoring + library growth + OpenODD axis tagging).
3. **Safety-case-tied value (revenue-impact ceiling).** Faster safety-case closure equals faster AV commercial deployment. A 1-quarter pull-forward on a $50M-$500M annual deployment revenue is a 7-9 figure value. Subscription pricing in the $250K-$500K range is small against that value when the closed-loop pilot demonstrates measurable collision-rate movement.

Unit economics at Year 3 maturity (15 sites + 15 customers):

| | Y3 entitlement |
|---|---|
| Annual cost (15 Model A + 3 Model B + 2 Model C) | $2.35M |
| Library subscription ARR ($250K avg × 15 customers) | $3.75M |
| Custom capture revenue | $500K |
| **Total Year 3 revenue** | **$4.25M** |
| **Gross margin** | **45%** |

LTV per customer (subscription retention assumptions: Y1 100%, Y2 80% renewal at expansion, Y3 70% retention from Y2 base, Y4 60%): **$659K expected gross revenue LTV**. At 45% mature GM: **$297K gross profit LTV**. CAC analysis (GTM cost per customer ~$80K loaded): **LTV/CAC = 3.7×**, clearing the 3× SaaS benchmark.

**Q20. What is the subscriber and revenue projection?**

Projection from pre-seed close through CFP (M0 → M20):

| Quarter | Active sites | Active subscribers | Library subscription ARR | Custom capture (cumulative) | Phase revenue |
|---|---|---|---|---|---|
| Q1 (M1-3, build) | 0 | 0 | $0 | $0 | $0 |
| Q2 (M4-6, MVP sites live) | 3 | 0 paid (free pilots in flight) | $0 | $0 | $0 |
| Q3 (M7-9, first paid) | 4 | 1 | $150K | $0 | $37.5K |
| Q4 (M10-12, GTM hire) | 5 | 2 | $300K | $0 | $62.5K |
| Q5 (M13-15, 1st Model B) | 6 | 4 | $600K | $75K (first custom site M14) | $204K |
| Q6 (M16-18, 2nd Model B) | 7 | 6 | $900K-$1.2M | $75K | $204K |

Total 18-month revenue (recurring + custom): $508K. End-M18 ARR run-rate: $900K-$1.2M. The slower revenue ramp vs V1 (which projected ~$2.3M through M18 in the now-stale [RAISE_SIZING.md](RAISE_SIZING.md)) reflects the structural reality of subscription revenue: customer cycles take longer to convert, but recurring revenue compounds afterwards. End-M18 cash with $2.2M raise: ~$600K, ~4 months of buffer at mature burn. Trough cumulative cash: ~-$700K at M6-7.

**Q21. What are the program-level financials? When does Skydock reach cash-flow positive?**

Program-level financials, 18-month monthly burn projection from pre-seed close ($2.2M raise; see [V2_FINANCIAL_MODEL.md](V2_FINANCIAL_MODEL.md) for the full month-by-month build):

| Phase | Months | Recurring monthly | Capex | Phase total cost | Phase revenue |
|---|---|---|---|---|---|
| 1: Build | 1-3 | $75K | $0 | $225K | $0 |
| 2: 3 sites + free pilots | 4-6 | $90K | $75K | $345K | $0 |
| 3: 1st paid + 4th site | 7-9 | $90K | $25K | $295K | $37.5K |
| 4: 2nd paid + 5th site + GTM hire | 10-12 | $110K | $25K | $355K | $62.5K |
| 5: 4 customers + Model B | 13-15 | $130K | $40K | $430K | $204K (incl $75K custom) |
| 6: 6 customers + 0.5 CS hire | 16-18 | $140K | $40K | $460K | $204K |
| **Total 18 mo** | | | **$205K capex** | **$2.11M** | **$508K** |

**Cumulative cash with $2.2M raise:**

| Milestone | Month | Cumulative cash position |
|---|---|---|
| Pre-seed close | 0 | $2.2M |
| End M3 (build phase done) | 3 | $1.98M |
| End M6 (3 sites + first pilots) | 6 | $1.63M |
| First paid pilot signed | 7 | $1.63M |
| End M9 (4 sites, 1 customer ramping) | 9 | $1.38M |
| End M12 (5 sites, 2 customers, GTM hire) | 12 | $1.08M |
| End M15 (5 sites, 4 customers, +Model B + custom) | 15 | $0.86M |
| End M18 (7 sites, 6 customers, ARR $1.2M run-rate) | 18 | **$0.60M** |

CFP achieved in **months 18-20** at $900K-$1.2M ARR run-rate. The $2.2M pre-seed funds the negative-cash window (trough ≈ -$700K cumulative burn) with **$600K of buffer** for slip risk at M18. Beyond M18, the business approaches self-funding; the seed round becomes a growth investment for Phoenix + Austin expansion + Model C deployment + scaling the curation engineering team — not a survival requirement.

**Program-level KPIs and IRR**:
- ARR run-rate at M18: $900K-$1.2M growing toward $1.6M-$2.0M by M24
- Gross margin at M18: scaling toward 45% as recurring revenue compounds against fixed engineering cost
- LTV per customer: $297K gross profit at 45% mature GM (per Q19)
- LTV/CAC: 3.7× (per Q19)
- Pre-seed capital deployed: $2.2M ($12M post-money cap, ~18% dilution)
- 24-month IRR (pre-seed dollars to M24 ARR + corpus value): ~80-120% range (sensitive to subscription conversion rate, expansion ASP, and BVLOS waiver timing — see Q22)

**Q21a. Does the pre-seed get us to profitability before the seed round?**

**Approximately — CFP achieved at M18-20 with $600K cash buffer at M18, but slower revenue ramp than V1 means seed-round dependence is higher than V1's plan suggested.** The $2.2M raise is sized to comfortably survive the pessimistic case and bridge into the seed; it does not deliver V1's "seed becomes optional" outcome. This is a deliberate V2 tradeoff: the V2 business is structurally more durable (curation moat, multi-tenant corpus, regulatory-aligned positioning) but it ramps revenue slower because subscription cycles take longer to convert and compound. We are trading early-revenue ramp for durable defensibility.

Three different definitions of "profitability":

| Definition | Timing | What it implies |
|---|---|---|
| **Cash-flow positive** (monthly cash > monthly costs) | M18-20 | Self-sustaining at 7-site, 6-customer scale |
| **GAAP net profit** (includes depreciation + deferred comp accrual) | M22-26 | True P&L profitability 4-6 months behind CFP |
| **Self-sustaining for indefinite growth** | Not at 7-site scale | Seed needed for Phoenix + Austin + Model C + curation eng team |

**Strategic implication:** Skydock's pre-seed buys us into a position where we **start seed conversations from M16-18 with measured pilot conversion data and a clear $1M+ ARR trajectory.** The seed pitch is "we've proven the V2 architecture, we have 6+ subscription customers, we're at $1M+ ARR growing, we want capital to expand to 3-market footprint and Model C deployment." This is materially better than V1's prior framing of "seed becomes optional" — V2 is honestly seed-dependent, but the seed conversations start from a defensible position rather than from desperation.

**Q22. How sensitive is the entitlement? What are the key input drivers?**

Sensitivity analysis combines (a) V2 unit-economics from [V2_FINANCIAL_MODEL.md](V2_FINANCIAL_MODEL.md) with (b) the V2 plan-killer audit from [V2_EXECUTION_PLAN.md](V2_EXECUTION_PLAN.md). Key drivers ranked by impact-probability product:

| Input | Range | Impact on CFP timing | Confidence |
|---|---|---|---|
| **First paid pilot conversion timing** | M7 → M11 | CFP slips 3-4 months at M11 first-paid | 🟡 Medium (biggest single risk) |
| **Library subscription ASP** | $100K → $300K | CFP M22 → M16 | 🟡 Medium (closed-loop pilot conversion economics drive this) |
| **BVLOS waiver timing** | M9 → M18 | M9-12 enables Phoenix Model C by M20; slip delays expansion revenue | 🟡 Medium-high (FAA approval rate uncertain) |
| **Rooftop access negotiation timeline** | M3 → M7 per site | Site deployment delay → revenue delay | 🟢 Higher confidence (commercial real-estate negotiation is well-understood) |
| **Curation pipeline production scale** | M5 → M9 ready | Customer integration delays subscription start | 🟡 Medium |
| **Multi-tenant corpus retention** | 60% Y2 → 90% Y2 | LTV/CAC 2.5× → 5× | 🟡 Medium (early — no V2 customer data yet) |

**Three cases for the entitlement:**

- **Pessimistic (first paid M11, ASP $150K, BVLOS slip):** $600K ARR at M18, CFP slips to M22, cash position at M18 +$180K (4-month bridge runway). Need $300-500K bridge round at M20-22 if pessimistic signals persist. Still survivable within $2.2M raise.
- **Mid-case (first paid M7, ASP $200K, BVLOS clears M12):** $900K-$1.2M ARR at M18, CFP at M18-20, $600K cash at M18 — the base case projected throughout this PR-FAQ.
- **Optimistic (first paid M6, ASP $300K, BVLOS clears M9, Phoenix Model C live by M18):** $1.5M-$2M ARR at M18, CFP at M16, $1M+ cash at M18 — accelerates seed prep and enables 3-market footprint by M24.

The key signal to monitor in the first 8 months: **conversion rate of the first 3-5 free closed-loop pilots into paid subscriptions**, and the average subscription tier customers convert to. If the conversion rate is below 40%, we revisit the pilot success-criteria definition; if average ASP lands below $150K, we revisit the subscription tier scope. The $2.2M raise is sized to survive the pessimistic case and execute the mid-case.

**Q23. What additional opportunities have we not included in the entitlement calculation?**

Six categories of upside not modeled in Q21's mid-case financials:

1. **Custom site expansion revenue** (Q18). $200K-$500K/yr by M24 from customers commissioning additional high-criticality intersections.
2. **Time-bounded exclusivity premium** (Q18). $300K-$1M ARR by M24 from safety-case-sensitive deployments.
3. **Channel revenue via Foretify, Applied Intuition Validation Toolset, CARLA partner integrations** (Q18). $200K-$500K/yr by M30.
4. **Multi-market expansion** (Phoenix, Austin Q3-Q4 2027). Per-market deployment 2-3× the multi-tenant corpus value without proportional capex.
5. **V2 envelope (Model C drone-in-a-box at scale, BVLOS waiver clearance)**. Continuous 24/7 capture; ~3× capture volume per site for the same operational cost.
6. **Regulatory-evidence-as-a-service**. Library subscription + safety-case documentation support for OEMs preparing NHTSA AV STEP submissions. Speculative seed-round growth thesis.

These collectively suggest $5M-$8M ARR by M30 against the $2.2M raise — and underwrite the seed-round growth story. The current PR-FAQ is anchored on the pre-seed-to-CFP path, which is the wedge product alone.

---

## Appendix A — Additional Internal FAQs

**Q24. What is the North Star of the product?**

Our North Star is to become the validation library that AV safety teams reference by default when closing closed-loop collision-rate gates. Success looks like: every Tier-1 AV company and every major OEM safety team has a Skydock library subscription documented as part of their NHTSA AV STEP submission package, and the curation methodology (criticality scoring, OpenODD axis tagging) becomes a quoted reference point in safety-case documentation. The library is the artifact safety teams reach for; the site network is the substrate that produces it.

**Q25. Tenets.**

1. **The safety case is the buyer's actual workflow.** Our product drops into closed-loop sim pipelines without schema rewrite, without QA process change, without naming-convention negotiation. The safety team should not have to do work to ingest us.
2. **Curation methodology is the moat.** Every captured scenario passes through 5 independent scoring signals. Curation IP + multi-tenant corpus + safety-case integration are the layers raw drone captures cannot displace.
3. **Independence is the validation principle.** Synthetic libraries cannot serve as ground truth in a safety case. We do not compete with synthetic generators on volume; we sell the structurally non-substitutable layer.
4. **Subscription aligns incentives with library growth.** Per-scenario pricing taxes customers for each capture and incentivizes us to sell volume. Subscription pricing aligns us with making the library more useful over time.
5. **Fixed-point operations is the unit-economic primitive.** levelXdata proved this for 7 years in Germany. We do not invent a new operational primitive; we extend the proven primitive with US coverage + curation IP.
6. **One site that delivers validation-grade quality > five sites that don't.** Per-site reliability is non-negotiable. We do not expand site footprint past the per-site quality bar.

**Q26. How does customer integration work? How is library access scoped?**

Library access is via the Skydock API + partner integrations:

- **Skydock API:** OAuth2 + scoped API keys per subscriber, with filterable queries on scene class, criticality bin, agent count, geography, time-of-day, weather, OpenODD axis match. Subscribers pull scenarios on demand into their closed-loop sim pipeline or build automated nightly integration jobs against their evolving safety case.
- **Foretify integration:** library access exposed as a Foretify scenario library within the Foretify scenario-validation tool, with customer queries flowing through Foretify's existing UX.
- **Applied Intuition Validation Toolset integration:** library access exposed as a data source within the Applied Intuition validation pipeline.
- **CARLA / custom integration:** Production and Enterprise subscribers can request custom S3 bucket targeting, SFTP delivery, or streaming-API endpoints.

Scope of access is set by subscription tier (Q4). Multi-tenant access is the default; time-bounded exclusivity available at premium for safety-case-sensitive deployments.

**Q27. How did we choose the camera + site deployment + capture geometry?**

Three design decisions worth interrogating:

1. **Three deployment models (A rooftop / B tethered / C drone-in-a-box):** Selected to span the regulatory tractability + capex tradeoff space. Model A is the simplest path (stationary observation; no waiver) and the first 3-5 V2 sites use it. Model B is the next-tier path (tethered drone, simplified Part 107 tethered-ops registration, no Remote ID requirement for tethered) for sites where intersection geometry needs higher vantage. Model C is the production-scale path (drone-in-a-box for 24/7 continuous capture) but requires BVLOS waiver — filed M1 of operations as an explicit milestone.
2. **Capture altitude 50-120m AGL (default 80m for signalized urban intersections):** Footprint radius = 80 × tan(40°) ≈ 67m, large enough to capture a typical signalized intersection. Higher altitude (120m+) gives wider coverage but pixel-per-agent drops below typical detection thresholds. Lower altitude (50m) gives better resolution but smaller footprint. 80m is the levelXdata-precedent midpoint matching Part 107's 400ft (122m) ceiling with margin.
3. **Important regulatory correction (V1 PR-FAQ error):** V1 stated that DJI Mini 4 Pro at 249g qualifies for "sub-250g FAA Remote ID exemption." **This was wrong.** The sub-250g Remote ID exemption applies only to recreational flight, not commercial Part 107 operations. Skydock holds the FAA Part 107 commercial certificate; per-site operators hold individual remote pilot certificates. All non-tethered commercial drone operations require Remote ID compliance regardless of drone weight. Tethered drones (Model B) have a separate, simplified registration path that does not require Remote ID on the tethered aircraft. Model C drone-in-a-box requires BVLOS waiver — a separate, well-documented regulatory process with 6-12 month expected resolution time.

**Q28. How did we choose the operational envelope (V1 vs V2)?**

V1 envelope: Model A rooftop installations (stationary observation, no waiver) + Model B tethered drone (simplified Part 107 tethered-ops, no Remote ID for tethered drones). Daylight only for Model A (Part 107 stationary observation). Altitude 50-120m AGL. Wind <20 mph for Model B. This is the minimum-viable envelope that we can operate under FAA Part 107 without any waiver, which is essential for pre-seed scope (waivers take 6-12 months and have improved approval rates with Part 108 progress but remain time-uncertain).

V2 envelope: Model C drone-in-a-box at expansion markets, requiring BVLOS waiver. Filed M1 of operations as an explicit milestone with expected resolution M9-M12. Enables 24/7 continuous capture and Phoenix + Austin expansion by Q3-Q4 2027. The pre-seed thesis does not depend on Model C; V2 envelope is the post-seed growth thesis.

**Q29. Why "Skydock" — branding rationale?**

Three options considered: "Skydock" (chose), "Aerial Sentinel", "Skylib". Skydock won because:

- It names the *operational primitive* — the fixed-point capture installation that the entire system orbits around. The output (curated library) and the customer-facing API can evolve; the operational primitive doesn't change.
- It's a defensible product mark, not generic. "Aerial Sentinel" and "Skylib" are descriptive and unprotectable.
- It generalizes to future products (Skydock Cloud for the library API, Skydock for Compliance for regulatory-evidence-as-a-service) without renaming.

Risk of confusion with DJI Dock / Skydio Dock products: minimal, because those are stationary drone-in-a-box hardware aimed at industrial inspection customers, not data services. The "Skydock V2 actually does use drone-in-a-box hardware at Model C sites" overlap is acceptable — we're a data + curation services company, not a hardware vendor.

**Q30. How much do we need to invest in marketing and sales?**

Pre-seed sales motion is intentionally lean because the target customer base is small (~40 named safety-team decision-makers across V2 customer list) and reached through direct founder-led outreach + paid pilots.

- **Months 1-10 (founder-led):** $0 paid marketing. Founder handles all customer conversations directly. Direct outreach to safety teams at named target accounts, conference presence at AV-Safety 2027 ($15K), Foretify and Applied Intuition partner alignment.
- **Months 11-18 (GTM hire):** Dedicated GTM hire at $220K loaded compensation, specifically targeting AV safety teams. Quota: 4 paid subscriptions by M18 (plus the 2 founder-converted from M7-M10).
- **Total 18-month sales + marketing budget:** ~$225K in the Q21 financial summary.

This is dramatically lower than a typical SMB SaaS startup because the buyer is a small named cohort and the closed-loop pilot is structured so the customer self-validates value rather than requiring marketing-driven proof.

**Q31. Why don't we license data from internal AV company collections?**

Three reasons:

1. **They don't have aerial BEV in volume.** Internal teams have failed to capture it economically (Q11). The few that have small internal datasets don't have curation pipelines.
2. **What they have, they don't sell.** AV companies treat internal data as IP; competitive concerns block cross-customer licensing.
3. **Independence requirement makes internal data structurally insufficient.** Even if a customer had aerial BEV from their own collection, it wouldn't satisfy the safety case's independence requirement for closed-loop validation.

Skydock collecting independent multi-tenant data ourselves bypasses all three structural problems.

**Q32. What's the launch timeline? What are the milestones?**

V2 milestones per [V2_EXECUTION_PLAN.md](V2_EXECUTION_PLAN.md):

| Milestone | Target | Outcome |
|---|---|---|
| M0: Pre-seed close | Month 0 | $2.2M committed; founder + ML/curation contractor + site/hardware contractor onboarded; BVLOS waiver application drafted |
| M1: BVLOS waiver filed | Month 1 | FAA filing complete; rooftop partner negotiations in progress for first 3 sites |
| M4: First Model A site live + first free closed-loop pilot in flight | Month 4 | One site capturing; curation pipeline alpha emits first scored scenarios; ≥1 free pilot customer reviewing |
| M7: First paid subscription signed | Month 7 | $150K ARR; 3 Model A sites live; first paid customer ramped from free pilot |
| M11: 5 sites live + 2nd paid subscription + GTM hire onboarded | Month 11 | $300K ARR; GTM hire owns prospect pipeline |
| M14: 3rd-4th paid subscriptions + 1st custom site commissioned | Month 14 | $600K ARR; first $75K custom site revenue |
| M16: 1st Model B tethered drone live | Month 16 | 6 sites live; production-grade BVLOS partial precedent |
| M18: 5th-6th paid subscriptions + 7 sites operational | Month 18 | $900K-$1.2M ARR; CFP trajectory; seed conversations start |
| M20-22: Seed-round close | Month 20-22 | $5-10M seed for Phoenix + Austin + Model C |

**Q33. What resourcing is needed to get this launched?**

Headcount + contractor plan over 18 months:

- **Months 1-3:** Founder full-time + 1.0 FTE ML/curation engineering contractor + 1.0 FTE hardware/site integration contractor + legal/aviation lawyer engagement. Burn ~$75K/month.
- **Months 4-6:** Founder + 1.0 FTE curation eng first full-time hire starts M5 + 0.5 FTE curation operator starts M6 + 1.0 FTE hardware contractor wrapping M6. Burn ~$90K/month.
- **Months 7-10:** Founder + curation eng + 1.0 FTE curation operator. Burn ~$90K/month.
- **Months 11-13:** Above + 1.0 FTE GTM hire starts M11. Burn ~$110K/month.
- **Months 14-17:** Above + 2nd curation eng hire M14 + 0.5 FTE customer success M17. Burn ~$130-140K/month.

Total full-time headcount at CFP (end M18): 5 + founder = 6 people (founder + 2 curation eng + 1 GTM + 1 ops + 0.5 CS).

Founder bio: Krethik Ram has spent the last several years leading product on autonomous hardware-software systems at scale — hardware, firmware, real-time sensor integration, and safety-critical control deployed across major US logistics operations. The same operational discipline applies to fixed-point aerial capture site network + curation pipeline + customer-facing safety-case integration. Earlier work includes a smart-access hardware and firmware system with a provisional patent. B.S. Computer Science, University of Wisconsin–Madison. Based in San Francisco.

**Q34. What's launching first — US or other markets? Why sequential vs simultaneous?**

US only (specifically Bay Area) for the pre-seed. Rationale:

- FAA Part 107 + BVLOS waiver process is the regulatory envelope we know; EU EASA equivalent has different and slower-evolving rules.
- V2 customer base (safety teams at Tier-1 AV companies + OEMs) is concentrated in California, Michigan, Texas, and Arizona — Bay Area is the densest cluster.
- Site selection requires deep knowledge of city/state DOT incident data + rooftop partner access; concentrating on one metro for V1 sites builds the methodology before geographic scaling.
- One regulatory regime + one site-deployment methodology + one customer relationship pattern = lower coordination overhead.

Phoenix expansion (Q3 2027): warm-weather year-round operation, AV testing density, Waymo + Cruise + Aurora presence. Austin expansion (Q4 2027): Tesla / GM partnership zone, growing AV deployment, lower operating cost. Both markets are post-BVLOS waiver clearance and post-seed.

EU expansion deferred to post-Series A; the regulatory + site-selection + partner-integration work alone is 12-18 months of preparation.

**Q35. What are the biggest risks and how are they mitigated?**

Honest risk register, prioritized by impact-probability product:

| Risk | Probability | Impact | Mitigation |
|---|---|---|---|
| Closed-loop pilot conversion rate <40%; ASP averages $100K not $200K | 40% | High | (a) Pre-agreed pilot success criteria force binary conversion decision rather than slow customer drift; (b) closed-loop sim already integrated into target customer workflows so adoption friction is low; (c) Foretify + Applied Intuition partnerships create channel acceleration if direct sales slow. |
| BVLOS waiver slip beyond M18 | 30% | Medium | (a) V1 envelope (Model A + Model B) is intentionally inside Part 107 territory, so V1 thesis doesn't depend on waiver; (b) Model B tethered drone provides expansion vector for higher-vantage sites without waiver; (c) Phoenix + Austin Model C deployment is post-seed, so pre-seed CFP doesn't depend on Model C. |
| Synthetic data improves faster than expected; safety teams lower validation-data willingness-to-pay | 25% | High | (a) Validation independence requirement is a structural argument, not a "synthetic is bad" argument — better synthetic actually strengthens our independence case; (b) NHTSA AV STEP, EU AI Act, UK CCAV all push regulation toward independence; we sit on the right side of this curve; (c) library compounds in value over time so even reduced new-customer signups still grow corpus value. |
| Rooftop access negotiations slip past M3 per site | 25% | Medium | (a) Founder-led negotiation focused on commercial real-estate partners with existing technical infrastructure (office towers, parking structures, transit hubs); (b) parallel site negotiations so timeline-slip on one doesn't delay all; (c) Model B tethered drone provides land-only deployment path that doesn't require rooftop access. |
| Curation pipeline doesn't reach production scale by M5 | 20% | High | (a) 5 curation signals are individually well-published methods; the integration work is straightforward ML-ops; (b) curation engineering contractor onboarded from M1; (c) explicit M5 gate before first free pilot starts. |
| Solo founder burns out or has a critical event | 10% | Critical | First engineering hire in M5 has operational + technical context to continue in founder's absence. Co-founder search active but not gating. |
| Drone fleet incident at Model B/C site causing reputational damage | 5% | High | Insurance ($1-3K/year per site), redundancy across multi-site footprint (single-site outage doesn't stop library access), tethered + DIB hardware has demonstrated reliability records, public communications plan ready for incident. |

The two risks with the largest impact-probability product (pilot conversion <40% and synthetic data substitution) both have structural mitigations and converging signals in the first 8-10 months. We will know early whether the V2 thesis is on track.

---

## Appendix B — V2 customer discovery summary (May 2026 refocus)

V2-pivot discovery (May 2026) refocused on safety teams + regulatory safety officers, replacing V1's perception-team / training-data discovery from March-April 2026. V2 discovery is ongoing; this appendix updates as conversations close.

Key V2 discovery questions:
1. Is closed-loop collision-rate evaluation a gating mechanism for your safety case? — Expected: ≥80% yes.
2. Does your closed-loop sim library include aerial BEV scenarios from an independent source? — Expected: <20% yes.
3. Would your team subscribe to a curated, criticality-scored library at $100K-$500K/year if the closed-loop pilot demonstrated measurable collision-rate reduction? — Expected: ≥50% yes subject to pilot evidence.

V1 discovery (March-April 2026) remains relevant for context on the AV scenario-library market and the validation-platform landscape (Applied Intuition, Foretellix, Parallel Domain are still channel partners and competitive context), but V1 was anchored on perception/training-team buying behavior which doesn't map directly to V2's safety-team positioning.

## Appendix C — V2 competitive analysis

| Player | Product | Pricing | Distinction from V2 Skydock |
|---|---|---|---|
| levelXdata | German fixed-location aerial datasets (highD/inD/rounD/exiD) | $50K-$200K/yr per dataset | German-only; no US coverage; no criticality scoring; no library growth; no OpenODD axis tagging — the 7-year fixed-point hover precedent that validates our unit economics |
| Foretify | Scenario-validation platform | Per-scenario / per-license | Channel partner — sells Foretify integrations alongside Skydock library subscriptions |
| Applied Intuition Validation Toolset | AV validation pipeline | Per-scenario / per-license | Channel partner — Skydock library accessible as a data source in their toolset |
| Parallel Domain | Synthetic BEV / sensor data | Per-scenario synthetic | Synthetic — fails independence requirement in closed-loop validation; complementary in training |
| Mira | Synthetic AV library | Subscription | Synthetic; complementary |
| Wayve GAIA-3 | Generative world model | Internal use / API access TBD | Training-data substitution thesis — explicitly what we positioned away from in V2 |
| NVIDIA Cosmos | Generative world model | API access | Training-data substitution thesis |
| DJI / Skydio (Dock 2 / X10) | Stationary drone-in-a-box hardware | $15K-$40K + hardware | Hardware vendor; sells installations not curated libraries |
| Internal AV drone teams | Manual or semi-automated drone capture | Internal cost $500-$1K+/scenario | Cap at low daily capacity; no curation; no library growth |

## Appendix D — Sample library scenario schema

Per-scenario file structure (auto-generated by Skydock curation pipeline):

```
scenario_skydock-cap-00042/
  metadata.json           # site ID, capture geometry, scene class, OpenLABEL tags,
                           # 5-signal curation scores, OpenODD axis match
  agent_tracks.json       # per-agent ENU positions, 30 fps from BEV transform + ByteTrack
  scenario.xosc           # OpenSCENARIO 2.0 stub with entities + road network reference
  raw_video.mp4           # optional 4K H.265, toggleable per subscription tier
```

Sample sizes:
- metadata.json: ~3 KB (includes 5-signal scores + OpenLABEL + OpenODD)
- agent_tracks.json: 50-500 KB (depending on agent count and capture duration)
- scenario.xosc: ~5 KB
- raw_video.mp4 (optional): 200-600 MB

## Appendix E — Methodology references

- **Curation methodology:**
  - Criticality: Westhofen et al. 2021 catalog (TTC, PET, jerk, near-miss)
  - Epistemic uncertainty: Mining the Long Tail (arXiv 2508.18397)
  - Corpus frequency: Waymo WOD-E2E methodology (<0.03% threshold)
  - Multi-agent interaction density: InterHub (Nature Scientific Data 2025)
  - Scene-class taxonomy: OpenODD axes per customer integration
- **Aerial BEV unit economics precedent:** levelXdata commercial datasets (highD: 16.5h of drone capture, 110,000 vehicles, German highway); validates fixed-point hover commercial economics over 7 years.
- **Standards:**
  - ASAM OpenSCENARIO 2.0 (publicly published)
  - ASAM OpenLABEL (publicly published)
  - NHTSA AV STEP NPRM (December 2024); finalized framework 2025-2026
- **Hardware references:**
  - DJI Mini 4 Pro / Skydio X10 public datasheets
  - DJI Dock 2 / Percepto drone-in-a-box specifications for Model C
  - Commercial tethered drone systems for Model B
- **Regulatory references:**
  - FAA Part 107 commercial operations (commercial certificate held by Skydock; per-site operators hold remote pilot certificates)
  - Part 107 tethered-drone simplified registration (Model B path)
  - FAA BVLOS waiver process (Model C path; filed M1 of V2 operations)

Full execution plan in [V2_EXECUTION_PLAN.md](V2_EXECUTION_PLAN.md); financial model in [V2_FINANCIAL_MODEL.md](V2_FINANCIAL_MODEL.md); thesis in [SKYDOCK_V2_THESIS.md](SKYDOCK_V2_THESIS.md).

---

*v3 (V2 architecture rewrite), May 2026. Replaces v2 PR-FAQ (V1 mobile-dock architecture). The V1 PR-FAQ remains in git history for reference but does not reflect current product, financial model, customer cohort, or regulatory posture. V1 PR-FAQ Q27 contained an incorrect Remote ID exemption claim that is corrected in this V2 document.*
