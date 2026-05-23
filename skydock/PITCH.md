# Skydock — Pre-seed PR-FAQ

*Written backwards from the moment Skydock matters to a customer.*

---

## 1. Press release  (target date: April 2027)

> **FOR IMMEDIATE RELEASE**

### Skydock reaches cash-flow positive operations 18 months after MVP launch with first-of-its-kind aerial training data pipeline for autonomous vehicles

**Mountain View, CA — April 2027.** Skydock, the operator of the first vehicle-deployed aerial training-data pipeline for autonomous vehicles, today announced it has delivered 4,200+ customer-validated scenarios to four AV customers since MVP launch, achieving cash-flow positive operations on a six-vehicle Bay Area fleet.

The company's platform addresses a long-standing gap in AV training datasets: aerial bird's-eye-view footage of real road scenarios. Ground-vehicle perspectives — cameras, lidar, radar — have become commodity. Aerial BEV has not, because the operational model didn't exist. Internal AV teams could fly drones manually, but the cost-per-scenario was prohibitive at $1,000+ per usable clip and capacity capped at a handful per day. Skydock's automation — roof-mounted dock, autonomous deployment, BVLOS-eligible mission control, OpenSCENARIO 2 delivery pipeline — drops that to under $400 per scenario and 20 captures per vehicle per day.

> *"For our scenario validation library, aerial BEV is the perspective we'd been trying to source internally for two years. Skydock turned what was a months-long project into a six-week purchase, and the data quality holds up against our internal benchmarks."*
> — **[Head of Scenario Engineering, Pilot Customer]**

Skydock operates six Toyota vehicles in the Bay Area, each carrying a custom dock and three DJI Mini 4 Pro drones rotating between active capture and battery swap. The system auto-deploys on operator command or at pre-planned GPS waypoints, captures 30–120 second BEV footage at 80m AGL, returns to dock, and delivers processed scenarios in OpenSCENARIO 2 format within four hours.

> *"Aerial BEV is the data category nobody could collect at scale because the operational model — getting a drone to the right intersection at the right time, reliably, 20 times per day per vehicle — didn't exist. We invented that. The hardware is off-the-shelf. The wedge is the operational system that gets you to spec-target reliability."*
> — **Krethik Ram, Founder, Skydock**

The company sells to four AV customers and has two additional signed pilots. Roadmap: expansion to 12 vehicles and two additional markets (Phoenix, Austin) by Q4 2027.

**About Skydock.** Founded in 2026 by Krethik Ram, Skydock builds vehicle-deployed aerial data collection systems for autonomous vehicle training. Backed by [pre-seed investors]. Based in Mountain View, CA.

---

## 2. Internal FAQ  (Investor lens)

### Q1. What's the wedge? Why hasn't this existed?

**Aerial BEV is the AV training data category nobody could collect at scale.**

Ground-perspective AV data is commoditised — Waymo Open, nuScenes, KITTI are free; Scale AI labels custom corpora for any AV team that wants them. Aerial BEV is structurally different:

- It's **physically harder to collect**: you need a drone in the right place at the right time, deployed within seconds of a trigger event, returned safely, and you need to do this dozens of times per day per operating unit. A fixed-base drone-in-a-box (DJI Dock 2, Skydio Dock 2) doesn't get you there — those are stationary. A manually-piloted drone doesn't get you there either — the cost per scenario is $1,000+ and capacity caps at a few per day.
- It's **operationally novel**: vehicle-deployed drones for data collection are a category of one. Percepto does industrial inspection from vehicles, but not data sales. DJI sells drones, not operational services. Synthetic-data companies (Parallel Domain, Datagen, Mira) generate BEV from 3D scenes, but customers consistently report that real-world data outperforms synthetic for edge cases.
- The **demand is real and unmet**: AV scenario validation teams ([Applied Intuition](https://www.appliedintuition.com), [Foretellix](https://www.foretellix.com), [Parallel Domain](https://paralleldomain.com), [Cognata](https://www.cognata.com)) all maintain internal scenario libraries that are dominated by simulated and ground-perspective real data. Aerial real-data slots in those libraries are largely empty.

The wedge is the **operational system** — dock + autonomous deployment + mission planning + delivery pipeline — that turns aerial BEV into a service that scales linearly with vehicles. The hardware is off-the-shelf.

### Q2. How big is the market?

**Bottom-up sizing.**

There are roughly 30 AV companies globally that maintain scenario validation libraries: Waymo, Cruise, Zoox, Aurora, Mobileye, Tesla, BYD, NIO, Wayve, Pony.ai, the OEMs (GM, Ford, VW, Toyota, Stellantis, Mercedes), the validation platforms (Applied Intuition, Foretellix, Parallel Domain, Cognata, Aurora Sim, Voyage), and the academic / government labs (DARPA, NIST, TRI).

The validation platforms (~6 companies) buy aggressively — that's their product. They each maintain scenario libraries of 5,000-50,000 scenarios. If 10% of those slots are realistically addressable by aerial BEV (the edge cases where ground perspective is occluded or unavailable), that's a 3,000-30,000 scenario opportunity per customer.

At the derived mid-price of $339/scenario:
- One large customer at 10K scenarios = $3.4M
- All 6 validation platforms at 5K average = $10M
- Plus the AV companies themselves at 1K-5K each = $20M-$80M

**Conservative TAM: $30M ARR addressable in years 1-3.** Aggressive TAM: $150M as the data category matures and gets specified into validation procurement.

### Q3. What are the unit economics?

**The model is built bottoms-up from cost-to-replicate** (see [pricing.py](skydock/skydock/pricing.py)). A customer producing one Skydock-equivalent scenario in-house pays:

| Cost component | Per scenario |
|---|---|
| Operator labour ($100/h loaded × 0.5h/scenario) | $50 |
| Annotation / QA (Scale AI rate, low–high) | $30 – $150 |
| Capital amortisation (drone + vehicle + dock) | $6 |
| Software / cloud / tooling | $5 |
| **Internal cost** | **$91 – $211** |

Apply a 1.5×–3.0× vendor markup (industry-typical for specialty data) and the **defensible price band is $136–$632, with a midpoint of $339**.

The simulation defaults to $339 for revenue calculations. At that price:

| Metric | Month-6 priors (sim output, 95% CI) | Spec target |
|---|---|---|
| Captures / vehicle-day | 22 [19, 25] | 12–20 |
| Mission success rate | 86% [82%, 90%] | ≥90% |
| Avg delivered quality | 79 [78, 80] | ≥80 |
| **Gross margin** | **65% [60%, 71%]** | ≥78% |

At a 6-vehicle fleet × 22 captures/day × 22 operating days × $339 × 0.65 delivery rate = **~$640K monthly revenue**, with the largest single cost being operator wages ($30/h × 6 operators × 22 days × 8h = ~$32K/month).

The largest sensitivity in the sim is fleet size — each marginal vehicle adds roughly $100K/month at scale.

### Q4. Who are the customers? What's the buying process?

**Named target customers** (spec §4.1, prioritised by buying behaviour):

1. **Applied Intuition** — sells scenario libraries to OEMs; buys data aggressively to populate them. Likely deal: 200–500 scenarios, $50K–$150K pilot.
2. **Foretellix** — focused on edge cases for their validation product; ideal customer for premium-priced aerial BEV.
3. **Parallel Domain** — synthetic-data company; would buy real data to validate their synthetic generators.
4. **Cognata** — smaller validation player; entry-tier pilot.
5. **Tier-1 AV companies** (Aurora, Pony.ai, Wayve) — longer sales cycle but larger deal sizes.

**Buying process** is consultative, 3-6 month sales cycle:

- **Discovery call**: founder shows a sample deliverable (the sim emits real `metadata.json + agent_tracks.json + scenario.xosc` packages today — see [skydock/deliverable.py](skydock/skydock/deliverable.py)).
- **Pilot scope**: customer specifies scenario types they want; Skydock commits to N scenarios at $X each.
- **Pilot delivery**: 4–8 weeks to deliver and review.
- **Conversion**: pilot graduates to ongoing commitment if quality holds.

The sim's per-pilot funnel models this with realistic conversion rates (~30% per active prospect over a 60-day lifetime, modulated by recent delivered quality).

### Q5. What's the competition? Why don't existing players do this?

| Player | Why they aren't direct competition |
|---|---|
| **DJI / Skydio (drone makers)** | Sell hardware, not operational data services. Their drone-in-a-box products are stationary. |
| **Percepto** | Vehicle-mounted drones for industrial inspection. Different use case, different customer. |
| **Scale AI / Sama (data labellers)** | Annotate data customers collect; don't collect themselves. |
| **Parallel Domain / Datagen / Mira (synthetic)** | Generate BEV synthetically. Customers acknowledge real edge-case data outperforms synthetic. |
| **DataFromSky** | Aerial traffic analytics from existing drone footage. Different operational model (static drones from rooftops), different output (analytics, not training data). |
| **Internal teams at AV cos** | Have tried manual drone deployment. Capacity caps at 2–4 captures/day, cost is $1K+/scenario. Don't have the dock automation. |

Two competitors could appear:

- **Skydio entering the data business**: most likely. Skydio Dock 2 + Skydio X10 is defense-grade and ~10× the price; they would have to build the vehicle-deployment dock and the data pipeline; cultural fit unclear (they're a hardware company).
- **An AV scenario platform building it internally**: Foretellix or Applied Intuition could build their own collection arm. Buying from us is cheaper if our unit economics hold, and our data is exclusive only if we choose; non-exclusive licensing lets them buy from us *and* compete on validation.

**The moat is the operational system + the data corpus + customer relationships.** The hardware is replicable but the integrated stack (and 12 months of operational learning) isn't.

### Q6. What's the moat as we scale?

Three layers:

1. **The corpus**. Every scenario captured stays in the library. Customers buy access; the corpus grows with every operator-day. After 18 months at fleet scale, Skydock has ~25,000 scenarios — an unmatched aerial BEV training set. New customers buy access to that corpus from day one.
2. **Operational expertise**. Drone-from-vehicle deployment at 95%+ success rate is a process problem. The 18 months of MVP iteration — dock tolerance, BLE precision landing, weather-day rescheduling, BVLOS waiver process — compound into a hard-to-replicate operational moat.
3. **Customer integration**. Once Skydock data is in a customer's validation pipeline (OpenSCENARIO format, naming conventions, QA workflow), switching cost is real.

### Q7. What's the path to cash-flow positive on this raise?

**~$1.7M to CFP in 18 months.**

| Phase | Months | Spend | Milestone |
|---|---|---|---|
| 1. MVP build | 0-6 | $400K (hardware, integration, contractor labour) | First vehicle operational, sample deliverables generated and reviewed by 3 prospects |
| 2. First pilot | 4-9 | $200K (operations, first hire) | First $50K paid pilot signed and delivered |
| 3. Fleet expand | 8-14 | $400K (5 additional vehicles + 1 ops hire) | 6 vehicles operating; $200K MRR by month 14 |
| 4. CFP | 14-18 | $400K (cushion + sales hire) | $400K+ MRR by month 18, CFP achieved |
| Buffer | — | $300K | — |
| **Total** | **18 months** | **$1.7M** | **CFP at month 18** |

This is tight but credible because:
- MVP cost matches spec §5.5 lower bound ($300-700K)
- The unit economics (65% gross margin at month-6 priors per the sim) leave room for fast scaling
- Pre-seed at this size targets cash-flow positive without a Series A — investor walks away with a profitable single-vehicle proof and clear scale-up path

### Q8. What are the biggest risks?

**Honest list, in priority order:**

1. **Customers don't pay $339/scenario** (~40% probability). Real price could land at $150 (spec §4.2 lower tier, sim's "tight commodity margin" case). At $150, CFP slips by ~6 months but is still reachable on the same raise.
2. **MVP reliability is worse than the sim suggests** (~30% probability). The sim's month-6 priors are aspirational; v0 defaults show 70% mission success, which would not be customer-acceptable. Mitigation: 6-month build phase before paid pilots, calibrating reliability against spec targets.
3. **FAA regulatory delay** (~25% probability). BVLOS waiver is non-trivial. Mitigation: V1 envelope is VLOS-only (spec §1.2), no waiver required. V2 BVLOS is upside.
4. **Customer says "synthetic data is good enough"** (~15% probability). Mitigation: target customers already buy real-data corpora alongside synthetic; aerial BEV is a fill-in, not a replacement.
5. **Skydio enters the market** (~10% probability in 18 months). Mitigation: operational moat + corpus + customer relationships.

The sim makes risks #1 and #2 quantitative — see the sensitivity tornado in [brief.md](out/brief/brief.md).

### Q9. Why this team, why now?

**Why now**: AV scenario validation is moving from research curiosity to procurement line-item. Applied Intuition's 2024 ScenarioLib launch, Foretellix's growing OEM partnerships, and NHTSA's incoming scenario-based testing rules all create concrete demand for edge-case data corpora over the next 24 months. Aerial BEV is the perspective those corpora lack.

**Why solo founder is workable at this stage**: the MVP is a hardware-integration problem, not a deep R&D problem. Off-the-shelf drone + custom dock + ML pipeline. Solo execution risk mitigated by:
- A fully-instrumented simulation (this repo) that lets pricing, capacity, and reliability questions be answered without burning hardware capital.
- A clear MVP spec and unit economics worked through bottoms-up.
- Hardware engineering contracted out (1 hardware engineer, 1 ML engineer in spec §5.4).
- First operational hire in month 4-6 to share operator + sales load.

**Why Krethik**: [insert your background here — what makes you specifically the right person to execute this. The PR-FAQ should not bury this; it's the strongest single argument for a pre-seed cheque after the wedge.]

### Q10. What are we raising and what's the use of funds?

**Raising $1.7M on a SAFE at $10M post-money cap.**

Use of funds:

| Category | Amount | Outcome |
|---|---|---|
| Hardware (6 vehicles + drones + dock fabrication) | $200K | Operational MVP fleet |
| Founder + 2 hires (18 mo) | $700K | Engineering + ops capacity |
| Cloud + tooling | $50K | Pipeline infrastructure |
| Sales & customer acquisition | $200K | First 4 paid pilots |
| Insurance + legal + incorporation | $100K | FAA Part 107, commercial drone insurance |
| Operations (vehicle, fuel, maintenance) | $150K | 18 months of fleet ops |
| Buffer | $300K | Risk cushion |
| **Total** | **$1.7M** | **CFP at month 18, no Series A required** |

The pitch to investors: this raise gets the company to durably profitable on a real customer base, without a Series A as a dependency. The seed round (if ever raised) becomes a growth round, not a survival round.

---

## 3. External FAQ  (Customer lens)

### What is a Skydock scenario?

A 30–120 second aerial bird's-eye-view recording of a real road scenario (intersection, merge, school zone, construction, VRU interaction, etc.) captured from a drone at 80m AGL, delivered as:

- **metadata.json** — scene classification, location, capture geometry, camera calibration, GPS uncertainty, quality score with methodology
- **agent_tracks.json** — frame-by-frame ENU positions of every visible vehicle / pedestrian / cyclist, with heading and speed (computed from successive positions; traffic-light stops produce `speed_mps: 0`)
- **scenario.xosc** — OpenSCENARIO 2.0 export
- **raw video** (optional) — 4K source footage

A sample deliverable is available; see [skydock/deliverable.py](skydock/skydock/deliverable.py).

### Why aerial BEV vs. ground perspective?

Three reasons AV teams pay for aerial BEV:

1. **Complete agent visibility**. Ground sensors are occluded by other vehicles, buildings, foliage. Aerial BEV sees every agent in a scene simultaneously.
2. **Spatial relationships**. Lane geometry, agent interactions, right-of-way disputes are easier to label and validate from above.
3. **Edge case curation**. Skydock pre-plans scenario waypoints (unprotected left turns, school zones, etc.) so the captured data is dominated by interesting edge cases, not commute traffic.

### What's the price?

$100–$400 per scenario depending on volume tier and scenario rarity. Pilot pricing: $50K-$150K for 200-500 scenarios. Premium edge-case scenarios (specific weather, specific traffic patterns) priced 2–3× base rate.

### What's the data quality methodology?

Quality is computed per-scenario from actual frame-by-frame agent visibility, agent class diversity, capture conditions (wind, altitude), and pipeline checks (upload integrity, OpenSCENARIO validation). Methodology is published; see the `quality.methodology` field in every scenario's metadata.json.

### Can we get custom scenario types?

Yes. Custom scenario waypoints are added to the operator's route plan and captured on the next operating day. Custom delivery formats (beyond OpenSCENARIO 2.0) are supported at engineering rates.

### How quickly do we receive the data?

Standard delivery is 4 hours from capture to delivery for processed scenarios. Bulk corpus access (historical scenarios from the library) is immediate.

### What's the SLA?

99% scenarios delivered within 4 hours; 95% scenarios pass quality threshold (≥70 on the published methodology); annual contract guarantees can be negotiated for enterprise customers.

---

## 4. What I'd want to discuss in a 30-minute meeting

Anchored on **three slides** (or three minutes) if all you have is that:

1. **The wedge** — aerial BEV is a missing AV training data category, the hardware to collect it exists, the operational model to do it at scale didn't, and we built it.
2. **The proof** — fully-instrumented simulation showing 22 captures/vehicle-day at 65% gross margin at $339/scenario, with bottoms-up cost-to-replicate pricing the customer can verify independently.
3. **The ask** — $1.7M to durable cash-flow positive on a 6-vehicle Bay Area fleet by month 18.

And the artefact I'd send before the meeting: this PR-FAQ, plus the auto-generated investor brief from `brief.py`, plus a sample scenario deliverable package emitted by the sim. All three are real artefacts today, not aspirational.

---

*Last updated: May 2026. Companion artefacts: [brief.md](out/brief/brief.md), [simulation repo](.).*
