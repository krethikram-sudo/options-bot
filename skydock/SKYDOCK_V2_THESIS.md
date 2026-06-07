# Skydock V2 thesis — fixed-point capture, curation-as-product, validation-as-positioning

Internal. Written in response to the structural critique that killed the
mobile-dock V1 architecture. This is the clean restatement; everything else
(financial model, customer site, execution plan) needs to be rebuilt to flow
from this.

**Date**: May 2026 pivot
**Status**: Replaces the V1 mobile-dock architecture documented in
EXECUTION_PLAN.md, PITCH.md, RAISE_SIZING.md, and the customer-facing
website. Those docs reflect the V1 thesis and need substantial revision.

---

## What we got wrong in V1

Three structural errors, each fatal on its own:

**1. Mobility was a feature customers didn't pay for.** Vehicle-mounted dock
gave us geographic flexibility, but customers buy *data*, not capture method.
Mobile capture is labor-heavy and one-scenario-at-a-time; fixed-point hover
captures continuously. levelXdata's highD recorded 110,000 vehicles from a
single hovering drone over a German highway in 16.5 hours. Our V1 model
required a vehicle + operator + drone to deliver 60 seconds of capture, then
drive 30 minutes to the next waypoint. The economics never close.

**2. We sold the commodity layer (raw captures) and disclaimed the
defensible layer (curation).** The page said "we're a capture platform, not
a long-tail mining platform" — but the long-tail mining IS the value. Raw
clips are a commodity headed toward synthetic substitution. Curated,
criticality-scored libraries that gate safety cases are the moat.

**3. We led with training-data improvement (RMSE -64%) — a race we lose to
world models.** Wayve GAIA-3, NVIDIA Cosmos, and synthetic generators are
manufacturing infinite training data. Training-data willingness-to-pay
erodes with each generation of generative models. Validation use cases —
where independent ground truth is *structurally required* and synthetic
data is *circular* — have durable WTP.

## V2 thesis (one sentence)

**Skydock is the curated, criticality-scored, validation-grade aerial BEV
scenario library that AV safety teams use to close their closed-loop
collision-rate gates, captured from fixed high-criticality US installations.**

Three architectural choices unpacked below.

## Architectural choice 1: fixed-point capture

### What it means

Persistent overhead capture at high-criticality US intersections. 5-10 sites
in year 1, expanding to 20-30 across Bay Area + Phoenix + Austin by year 3.
Each site captures continuously during daylight (V1 regulatory envelope) or
24/7 (V2 with BVLOS waiver).

### Site options

Three deployment models, ranked by capex and regulatory tractability:

**Model A: Rooftop mount on partner building**
- Negotiated access to a building rooftop overlooking target intersection
- DJI Mini 4 Pro on stationary mount, or Skydio X10 for higher-precision
- Power + cellular + cloud uplink from building
- ~$25K capex per site (camera + compute + cell + mount)
- ~$1K/year rooftop rental per site
- Regulatory: simplest path; Part 107 stationary observation

**Model B: Tethered drone (LTE-tethered)**
- Drone tethered to ground station via power + data cable
- Can hover 50-150m indefinitely (no battery limit)
- Sub-250g model not viable (need bigger drone for tether weight)
- ~$40K capex per site
- Regulatory: tethered drones have simplified Part 107 path; no Remote ID

**Model C: Drone-in-a-box (DJI Dock 2 / Percepto)**
- Persistent ground station that launches drones on schedule
- Drone returns to base for battery swap
- Continuous capture via rotation
- ~$50-80K capex per site
- Regulatory: needs BVLOS waiver for unattended ops

### Recommended sequence

V2 month 1-6: Model A at 3 sites. Validate site selection + customer
willingness-to-pay. Capex ~$75K, modest first-customer pilot capacity.

V2 month 7-12: Add Model B at 2-3 additional sites if traffic demands tether
durability. Capex ~$120K.

V2 month 13-18: Add Model C in 2-3 markets if BVLOS waiver clears. Begin
geographic expansion. Capex ~$200K.

Total V2 capex through CFP: ~$400K vs V1 plan's $342K — similar order of
magnitude, dramatically different unit economics.

### Site selection criteria

Three signals to prioritize sites:
1. **Criticality density** — intersections with documented high incident
   rates from city/state DOT data
2. **Customer demand signal** — locations validation-team customers ask
   for explicitly (e.g., specific Waymo operating area corridors)
3. **Building access tractability** — willing rooftop partners (offices,
   parking structures, transit hubs)

### Operational profile

- 5-10 sites × 8 hours daylight × 30 days = 1,200-2,400 site-hours/month
- Continuous capture yields thousands of agent-interactions per site-hour
- ~50,000-100,000 raw scenario candidates per month per site at maturity
- Curation pipeline reduces to ~500-1,000 *delivered* scenarios per site per
  month after criticality + epistemic uncertainty + corpus frequency
  filtering

Per-site economics:
- Capex: $25K-$80K (amortize over 5 years = $5K-$16K/year)
- Operating: $1K/year rooftop + $2K/year cellular + $3K/year cloud = $6K/year
- Curation labor (centralized): $20K/year per site amortized (1 FTE per ~5
  sites)
- **Total annual cost per site: ~$30K/year**
- **Delivered scenarios per site: ~6,000-12,000/year**
- **Cost per delivered scenario: $3-$5** (vs V1's $87/scenario at scale)

## Architectural choice 2: curation-as-product

### What it means

We sell a *library*, not individual captures. The library is the moat;
the captures feed it.

### Product structure

**Library subscription** (primary product, V2):
- Annual access to the full Skydock criticality-scored corpus
- Filterable by scene class, criticality bin, epistemic uncertainty,
  corpus frequency, geography, time-of-day, weather
- Customer queries the library via API or via partner integration
  (Foretify, Applied Intuition Validation Toolset)
- Pricing: $100K-$500K/year per customer based on access tier (vs V1's
  per-scenario pricing)

**Custom capture** (secondary product, V2):
- Customer specifies a new high-criticality intersection they want covered
- We deploy a new fixed-point site (Model A/B/C) if economics justify
- Capture for 6-12 months, then captures fold into library subscription
- Pricing: $50K-$150K per new site setup

**Exclusive captures** (premium product, V2):
- Customer requests time-bounded exclusivity on specific site captures
- Pricing: 2-5× standard library access for the exclusive window
- Useful for safety-case-sensitive deployments

### What we curate (the score stack)

Every captured candidate scenario runs through:

1. **Criticality scoring** — TTC, PET, jerk thresholds, near-miss detection
   (Westhofen et al. 2021 catalog)
2. **Epistemic uncertainty** — against our baseline perception detector
   (Mining the Long Tail methodology)
3. **Corpus frequency** — rarity ranking vs the growing Skydock library
   (Waymo WOD-E2E <0.03% threshold methodology)
4. **Multi-agent interaction density** — number of distinct interactions
   per scenario (InterHub methodology)
5. **Scene-class taxonomy match** — alignment with customer's OpenODD axes

A scenario must score in the top 20% on at least 2 of 5 signals to enter
the delivered library. ~80% of raw captures are filtered out. This matches
Waymo's WOD-E2E human-review acceptance rate (30%).

### Why this is the defensible layer

- **Curation methodology** is the IP. Raw captures are commodity; the
  scored, filtered, taxonomy-tagged library is hard to replicate without
  the full processing pipeline + multi-tenant corpus.
- **The library compounds over time.** Each year of capture adds to the
  multi-tenant corpus; customers benefit from cumulative coverage they
  could never afford solo.
- **Synthetic data cannot substitute.** Closed-loop validation requires
  *real, independent ground truth*. Synthetic libraries fail this test by
  construction.

## Architectural choice 3: validation-as-positioning

### What it means

We sell to **safety teams** (not perception teams), with a pitch built
around **closed-loop collision-rate gates**, not offline training metrics.

### The pitch

> "Your AV's safety case requires demonstrating performance against a
> library of high-criticality scenarios in closed-loop simulation.
> Synthetic libraries can't gate the safety case because the ground truth
> is circular. Skydock provides real, multi-tenant, criticality-scored
> aerial captures from the highest-incident intersections in your
> operating geography — gated through our curation pipeline and indexed
> against your OpenODD coverage model. Your safety case closes 6-12
> months faster because you spend less time fighting library coverage
> gaps and more time fighting the actual edge cases that move
> collision-rate-per-criticality-bin."

### The customer cohort shift

V1 targeted:
- Validation platforms (Applied Intuition, Foretellix, Parallel Domain)
- Perception teams at AV companies

V2 targets:
- **Safety teams** at AV companies (the people closing safety cases)
- **Regulatory safety officers** at OEMs (the people preparing NHTSA AV STEP
  submissions)
- Validation platforms (still relevant, but as channel partners)

This is a smaller but more durable customer base. Safety teams are the part
of an AV company that *cannot* substitute synthetic for real ground truth.

### Why this is the durable layer

- **Regulation pushes this way.** NHTSA AV STEP, EU AI Act, UK CCAV safety
  case requirements all increasingly require independent validation
  evidence. Synthetic data fails the "independence" requirement by
  construction.
- **World models can't substitute.** Training data willingness-to-pay
  erodes with each Cosmos / GAIA generation. Validation data willingness-
  to-pay grows with each regulatory requirement.
- **Tied to product velocity.** Faster safety case = faster commercial
  deployment = direct revenue impact for customers. Easier to sell.

## The closed-loop proof-of-value pilot (answering the critique's final question)

### Pilot structure

**Phase 0** (free, 30 days): Skydock delivers 100 criticality-scored
scenarios from one customer-specified Bay Area intersection. Customer
imports into their closed-loop sim. **No charge.**

**Phase 1** (jointly authored success criteria, 30 days):
- Customer's existing safety case includes a held-out collision-rate eval
  set, segmented by criticality bin
- Customer measures their AV's collision rate on this set BEFORE adding
  Skydock scenarios
- Customer augments their library with Skydock's 100 scenarios
- Customer measures collision rate AFTER on the same held-out set
- **Success criterion (written in advance)**: collision-rate reduction
  of ≥10% in at least one criticality bin OR coverage-gap closure on
  ≥3 OpenODD axes
- Joint authorship of success criteria binds the customer to defined
  conversion if met

**Phase 2** (conversion to Library subscription if Phase 1 succeeds):
- Customer signs annual Library subscription at agreed tier ($100K-$500K)
- 12-month commitment, 30-day notice for renewal
- Captures + curation continue against customer's evolving safety case

### Why this works as a sales motion

- **Customer measures the value themselves on their own safety case.**
  No vendor-self-reported metrics. No marketing claims. They run the
  closed-loop sim; they see the number move.
- **Predefined success criteria → 3.2× conversion lift** per the
  Forrester 2023 data (cited in DATA_VALUE_AND_LONGTAIL_RESEARCH.md).
- **Aligns with the safety-case buyer's actual workflow** — they're
  already running closed-loop sim, already segmenting by criticality.
  We just feed scenarios into a process they already have.

### What success looks like at scale

Year 1 (M1-12): 3 pilot customers convert at $150K/year average = $450K ARR
Year 2 (M13-24): 8 customers at $200K average = $1.6M ARR
Year 3 (M25-36): 15 customers at $250K average + $300K custom capture =
$4M ARR + $300K = $4.3M ARR

This is a different revenue profile than V1's per-scenario sales model.
ARR-based subscription is more like SaaS economics; expansion comes from
custom-capture upsell + corpus-tier upgrades + new customer acquisition.

## What this means for everything else

### Dies in V2

- **The 6-vehicle fleet plan** (EXECUTION_PLAN.md)
- **Mobile dock R&D** (custom roof-mounted dock with auto-launch)
- **Customer site Order options section** — Discovery / Validation / Library
  packs priced per scenario
- **Per-scenario pricing tiers** ($339 / $200 / $150 / $100)
- **Vehicle-deployed messaging** throughout customer site
- **Sora aerial drone prompts** for mobile-deployed footage
- **Most of the Python simulation** — modeled vehicle-mounted operations
- **Discovery script's primary value prop** — "vehicle-deployed for any
  location"

### Survives in V2

- **Aerial BEV value thesis** (course-validated)
- **Independence-for-validation argument** (the strongest card, now the
  primary pitch)
- **Customer cohort identification** (refined to safety teams)
- **OpenSCENARIO 2.0 + OpenLABEL compliance work**
- **Three long-tail scoring methodology** (now the core product, not
  metadata)
- **Cost model audit framework** (just different inputs)
- **Founder background fit** (Smart TDR → fixed-installation hardware)
- **Sim methodology** (still useful for simulating fixed-point operations)
- **Customer discovery investments** (target list, prep docs, outreach
  scripts — easy to update for V2 pitch)

### New shape of the rebuild

In order of dependency:

1. **V2 thesis doc** (this) ← done
2. **V2 closed-loop pilot design** ← included above
3. **V2 financial model** — rebuild RAISE_SIZING.md, COST_MODEL_AUDIT.md
   for fixed-point economics
4. **V2 raise sizing** — likely $1.5-2.5M; capex profile is similar but
   timing is different (front-loaded site builds vs vehicle ramp)
5. **V2 customer site** — rewrite Problem / Evidence / What you get / How
   it works to reflect library subscription product
6. **V2 execution plan** — site deployment sequence, BVLOS waiver work,
   curation pipeline development
7. **V2 PITCH.md** — full PR-FAQ rewrite with V2 product structure
8. **V2 discovery scripts** — refocus on safety teams, lead with
   closed-loop validation pitch
9. **V2 investor materials** — different metrics dashboard, different
   competitive landscape

## Open questions for the founder to sit with

Before going deeper into the rebuild, three honest questions:

1. **Do you actually agree with the critique on the merits?** Or are you
   reacting to the persuasiveness of the writing? The mobile-dock model
   has been your central instinct; abandoning it is a real cost. Sit
   with it for 24 hours before committing.

2. **Does fixed-point capture survive the same scrutiny?** levelXdata
   already does this in Germany. Their commercial license costs vs. our
   pricing — we need to honestly compare. Are we materially better than
   "levelXdata for US-coverage + criticality scoring"? If not, we have
   a competition problem at the curation layer too.

3. **Can you raise to fund the regulatory work?** Fixed-point at scale
   requires BVLOS waivers, rooftop access negotiations, possibly local
   permits. This is harder and longer than mobile Part 107 operations.
   Investors may be more skeptical of the regulatory path. Honest
   self-assessment: is this a 6-month founder-led BVLOS-waiver
   campaign, or does it require a co-founder with regulatory background?

If the answers to 1-3 are "yes, yes-with-caveats, yes" then the rebuild
proceeds. If any of them is "no" or "I need to think more," then we don't
write the V2 docs yet.

---

*v1, May 2026. This thesis replaces V1 (mobile-dock architecture) and
requires substantial rebuild of all downstream planning docs. The
underlying domain thesis (aerial BEV solves long-tail / prediction /
validation) survives unchanged.*
