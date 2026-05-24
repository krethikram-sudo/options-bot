# Skydock — Thesis reconsideration

*Triggered by RESEARCH_LOG.md findings. Written to interrogate whether the current wedge actually holds, and what alternative framings the research opens up.*

---

## What we now know that we didn't before

Distilled from the research log:

1. **Aerial drone trajectory datasets exist** academically (highD, inD, rounD, HetroD) and are widely used in AV research. The "category nobody collects" framing is false.

2. **The AV training data market is ~$1B globally** in 2025, growing modestly (9.3% CAGR for real datasets). The **synthetic data market is $1B → $29B by 2035 (39% CAGR)**. Synthetic is winning the AV data category by an order of magnitude.

3. **The named §4.1 customer list (Applied Intuition, Foretellix, Parallel Domain, Cognata) are toolchain / synthetic vendors, not data buyers.** Their business model is selling software to AV OEMs, not buying training data.

4. **AV OEMs have their own fleets generating proprietary data.** They process this data via Foretellix-style extraction or synthesize variations via Parallel Domain. They are not in the market for third-party real driving data at scale.

5. **Robotaxi operators (Waymo, Cruise) have massive proprietary data** and use sophisticated synthetic generation (Waymo's DeepMind-powered World Model). They are not addressable as customers in the foreseeable future.

6. **Scale AI's AV-specific labeling work declined post-2022** as VC funding in the sector dried up. The market for AV-specific data services contracted, not expanded.

7. **Applied Intuition is hiring "Robotic Software Engineer (Drone Stack)"** and has an entire Applied Intuition Defense aerial autonomy product line. They have the capability to build competing aerial AV data collection in-house.

8. **The vehicle-deployed drone for AV training data is genuinely unbuilt commercially** — that part of the wedge holds. Prior art is in crash data / insurance / emergency response, not AV training.

9. **NHTSA AV STEP is voluntary, not a mandate**. The "regulatory tailwind" was overstated.

10. **DataFromSky has been operating for 13 years** (founded 2013) with 10 employees on the closest commercial parallel (tethered drone traffic analytics). The fact that they haven't scaled into AV training data is itself a market signal worth interpreting.

---

## What the original thesis assumed vs what's true

| Thesis assumption | Reality |
|---|---|
| Aerial BEV is a missing AV training data category | Aerial BEV datasets exist academically (highD/inD); commercial AV training data market is dominated by synthetic |
| AV scenario validation platforms (Applied Intuition, Foretellix) are primary buyers | They're tool sellers, not data buyers — and Applied Intuition is hiring drone engineers, potentially competing |
| Pricing $200-500/scenario is the market rate | Unverified by direct market evidence; could be much lower or higher |
| TAM of $30M conservative / $150M aspirational | Probably 3-10× smaller for the originally-framed customer set |
| Pre-seed → CFP at 6 vehicles is plausible | Math still works if you find the right customer, but the customer set is murkier |
| "Wedge" is operational system + corpus | Operational system holds; corpus economics depend on a customer set that may not exist |

The original thesis was a plausible-sounding story built on insufficient evidence. The research doesn't kill it outright, but it forces a real reconsideration.

---

## Alternative thesis candidates

Seven repositionings worth considering, with honest assessment of each.

### Option A: Independent ground-truth for AV perception validation

**Pitch:** Skydock provides aerial ground-truth captures for AV perception teams to validate their on-vehicle BEV models. Every AV company runs perception models that produce a BEV-like representation from cameras + lidar. There's no truly independent way to validate that representation — until now. Skydock flies a drone over the same scene, captures real overhead truth, and the customer's perception model accuracy is measured against it.

**Customer:** AV perception engineering teams (different from scenario validation teams). Decision-maker is Head of Perception or Director of Perception Eng.

**Why now:** Perception models are increasingly important; perception failures are the largest cause of disengagements. Independent ground-truth is a real procurement gap.

**Defensibility:** The mobility moat (vehicle-deployed drone) is exactly the right tool — you can validate perception at the actual location their fleet operates, not in a separate test environment.

**Risks:**
- Customer may say "we use simulator-based validation" — but simulators have their own sim-to-real gap, so independent real validation is still valuable
- Customer may say "we capture our own ground truth with stationary drones" — addressable by the mobility advantage
- Small customer set: ~20 AV companies have meaningful perception teams

**Verdict: Most credible repositioning.** Uses the mobility moat for a real, documented pain point. Customer set is small but exact.

### Option B: Synthetic-data input vendor

**Pitch:** Skydock sells aerial-perspective captures to synthetic-data companies (Parallel Domain, Cognata, Mira) as input for their generation pipelines. They generate millions of synthetic variations from one real Skydock capture; we get paid per real seed scenario at premium rates because each one underwrites high-volume synthetic output.

**Customer:** Synthetic-data companies (5 named).

**Why now:** Synthetic data growing 39% CAGR; demand for diverse real inputs growing proportionally.

**Defensibility:** Smaller, more concentrated customer base; the data feeds into their existing pipelines without disrupting their business model.

**Risks:**
- Synthetic-data companies prefer to source real data from their customers (Foretellix's model), not third parties
- They might generate aerial synthetic from ground-vehicle inputs without ever needing real aerial captures
- Lower-margin position: we're a vendor to vendors
- Customer set is 5 companies — concentration risk

**Verdict: Plausible secondary thesis.** Could work as a channel, not as a primary business.

### Option C: AV company geographic-diversity supplier

**Pitch:** Skydock helps AV companies fill geographic / scenario gaps their own fleet doesn't cover. AV companies are mostly fleet-bounded to their HQ city (Waymo: Phoenix + SF; Cruise: SF; Aurora: Pittsburgh; Wayve: London). They want training data from cities they don't operate in. Skydock operates fleets in target cities and sells customised captures.

**Customer:** AV OEMs and operators.

**Why now:** Geographic expansion is a stated priority for most AV programs; data is the bottleneck.

**Defensibility:** The mobility moat is geographic — we can be in any city.

**Risks:**
- AV companies prefer to operate their own fleet in target cities (counts as on-road testing for regulatory)
- Foretellix-style synthetic extraction can generalise from one city's data to another
- High operational cost for us (multiple cities)
- Customer set is the same AV OEMs that have shown low willingness to buy external real data

**Verdict: Weaker than Option A.** Geographic diversity is a real pain point but harder to defend the buy-vs-build economics.

### Option D: Insurance / underwriting data

**Pitch:** Skydock provides aerial intersection / road-segment risk-assessment data to auto insurance companies. Insurance underwriting models need data on intersection danger, pedestrian density, accident-prone road segments. Skydock captures this data at scale and sells to State Farm, Progressive, Geico, etc.

**Customer:** Insurance underwriting teams.

**Why now:** Insurance is increasingly data-driven; ADAS-equipped vehicle pricing requires road-quality data.

**Defensibility:** Different customer with different buying motion. Less competition.

**Risks:**
- Insurance procurement cycles are long (12-24 months)
- They typically buy from existing data brokers (LexisNexis, Verisk) — incumbent relationships hard to break
- Total pivot away from the AV thesis; doesn't leverage the spec / sim work
- Requires building insurance domain expertise from zero

**Verdict: Plausible pivot if AV thesis dies, but a different company.** Worth keeping in mind.

### Option E: Smart city / municipal traffic engineering

**Pitch:** Skydock provides on-demand aerial traffic analytics to cities, DOTs, and traffic-engineering consultancies. Cities want to study intersection performance, pedestrian flows, traffic patterns — and currently have to commission expensive one-off studies.

**Customer:** City transportation departments, traffic engineering consultancies (Kimley-Horn, Stantec, AECOM), state DOTs.

**Why now:** Vision Zero initiatives, increasing pedestrian safety focus, federal infrastructure funding.

**Defensibility:** The mobility moat is real — city DOTs don't have permanent traffic-monitoring infrastructure everywhere.

**Risks:**
- DataFromSky already does this — and they're 10 people after 13 years, suggesting the market is small or hard to monetise
- Municipal procurement is slow (RFP cycles, prevailing wage requirements)
- Lower per-unit pricing than AV market would have been
- Different customer entirely; AV-engineering work doesn't transfer cleanly

**Verdict: Real market, but DataFromSky's scale tells us it's a tough market to grow in.** Possible but unexciting.

### Option F: Vertical AV markets beyond automotive

**Pitch:** Skydock provides aerial data services for non-automotive AV markets: agriculture (Blue River, Carbon Robotics), construction (Built Robotics), mining (Caterpillar), warehouse robotics (Symbotic, Locus). Each of these has AV development needs and limited internal data collection capacity.

**Customer:** Vertical-AV companies (~20-30 named).

**Why now:** These verticals are 3-5 years behind automotive AV in maturity — exactly the moment when external data services find traction.

**Defensibility:** Less crowded competition. Different customer dynamics.

**Risks:**
- Each vertical requires separate sales motion + domain expertise
- Per-vertical TAM may be small
- Some verticals (mining, construction) have on-site drone restrictions
- Loses focus

**Verdict: Worth one customer-discovery conversation per vertical to validate.** Not a near-term primary.

### Option G: Reposition entirely as a perception-validation tool / data platform

**Pitch:** Skydock is a perception-validation platform that AV perception teams subscribe to. They flag scenarios their on-vehicle BEV model struggles with; we capture independent aerial ground truth at those locations; they use the comparison to improve their model. SaaS pricing, recurring revenue.

**Customer:** AV perception teams (overlap with Option A).

**Why now:** Same as Option A.

**Defensibility:** Combined SaaS + data services moat is harder to replicate than data alone.

**Risks:**
- Building a SaaS pipeline on top of data services adds engineering scope
- Sales cycle is longer (SaaS deals are bigger / more procurement-heavy)
- The "tool" framing requires us to invest in the customer's perception workflow, not just deliver data

**Verdict: Stronger version of Option A.** Worth considering as the eventual platform vision after a data-services beachhead.

---

## Recommendation

The most credible single repositioning is **Option A: Independent ground-truth for AV perception validation**, with **Option G as the platform vision** in 18-24 months.

Why:

1. **Uses the actual moat correctly**. Vehicle-deployed drone = mobile = can validate at the customer's actual operating location. This is the right tool for the perception-validation problem.

2. **Solves a real pain that has no current solution**. AV perception teams have no truly independent ground-truth source. Self-collected data is contaminated by the same sensor stack the model uses. Simulators have sim-to-real gap. Aerial drone capture is genuinely orthogonal.

3. **Customer set is small but exact**. ~20 named AV companies with perception teams. Decision-maker is identifiable (Head of Perception). Procurement is more tractable than the murkier "scenario validation" space.

4. **Pricing logic flips**. Perception-validation captures can be priced higher per scenario ($500-$2000?) because each one is high-value for model improvement, vs. low-volume / commodity training data.

5. **The sim work mostly carries over**. Capture mechanics, dock physics, quality scoring, deliverable format all apply. Some scene-generation logic would change.

6. **The fabricated customer discovery in PITCH.md becomes more answerable**. "Would your perception team pay $1,000 per independent aerial ground-truth capture at locations your models struggle with?" is a much sharper question than "would you buy aerial BEV training data?"

---

## What changes in the pitch under Option A

| Section | Original | Option A |
|---|---|---|
| Wedge | Aerial BEV training data is a missing category | Independent aerial ground-truth for AV perception validation is impossible to acquire at scale |
| Customer | Applied Intuition, Foretellix, etc. | AV perception teams at OEMs and robotaxi operators |
| Why us | Operational moat | Mobility moat: only Skydock can validate perception at the actual operating location |
| Pricing | $339/scenario (volume tiered) | $500-$2000/capture (higher per-unit value, lower volume) |
| Volume | 22 captures/vehicle-day | 5-10 captures/vehicle-day (fewer but higher-value) |
| Comp | Synthetic data vendors | Stationary drone-in-a-box (Skydio, DJI) — wrong tool for the job |
| Defense | Corpus + customer integration | Mobility + customer perception-pipeline integration |

Unit economics likely come out similar or better — higher per-capture price compensates for lower volume.

---

## What changes in the simulation under Option A

Most of the sim work carries over directly. The biggest changes:

- **Scene generation** would need to support "perception validation scenarios" rather than (or in addition to) "scenario library categories." Probably parameterised by what kind of perception error the customer is debugging (occlusion, lighting, weather, agent density).
- **Quality scoring** becomes more about per-frame agent positional accuracy (the ground-truth quality matters because the customer compares their model to it) rather than scene diversity.
- **Deliverable format** would include direct comparison hooks for the customer's perception output (e.g., timestamped frames with synchronised positions, suitable for diff-checking against their model's BEV output).
- **Capture duration / altitude** could be optimised for ground-truth accuracy rather than coverage.

Nothing in the sim is invalidated. The economics module, failure cascades, GPS jitter, dock physics, etc. all apply unchanged.

---

## Questions only customer conversations can answer

Even after this repositioning, these remain open:

1. **Do AV perception teams have budget allocated for independent ground-truth?** Or would this need to be a new line item?
2. **What's their current validation methodology?** Self-collected? Simulator? Outsourced?
3. **What perception-error categories cost them the most?** This shapes which scenarios to capture.
4. **Would they prefer subscription (Option G) or per-capture (Option A)?** Affects pricing model.
5. **What's the technical decision-maker title and team size?** Affects sales motion.
6. **How do they currently address the "no independent ground truth" problem?** Is there pain or have they accepted the gap?

10-15 outreach conversations with named perception leads at the §4.1 customer list (rethought) could answer these in 4-6 weeks.

---

## Decision points for you

1. **Do you buy Option A as the repositioning?** Or does one of the other options resonate more? Or none of them — different angle I haven't considered?
2. **Are you willing to abandon the "aerial BEV training data" framing entirely**, given the research findings? Or does the original framing have a defensible version I missed?
3. **Should we run customer discovery against Option A's customer set** (AV perception teams) before doing more sim or PR-FAQ work? Probably yes.
4. **Does anything in this thesis review feel wrong or off?** I'm working from desk research only; you may have context I don't.

---

*Written May 2026 in response to research log findings. The original PITCH.md is preserved in git; this document is the basis for a v3 rewrite if the repositioning is accepted.*
