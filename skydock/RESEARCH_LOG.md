# Skydock — Customer Problem Validation Research Log

**Scope:** Desk research conducted in May 2026 to validate the customer-problem and market claims in `PITCH.md`. Every claim in the PR-FAQ traced back to either (a) the spec document, (b) inference from general AV knowledge, or (c) actual evidence. This log documents which is which and what we found.

**Methodology:** Web search + web fetch on 13 distinct query threads covering market size, target customers, competitive landscape, regulatory environment, existing aerial datasets, pricing references, and prior-art for vehicle-deployed drones.

---

## Headline finding

**Several of the PR-FAQ's foundational claims need revision.** The wedge thesis is still defensible but the specific framing — "aerial BEV is a category nobody collects" — is **wrong**. Aerial drone trajectory datasets exist (highD, inD, rounD) and are widely cited in AV research. Commercial aerial traffic-data services exist (DataFromSky, ~10 employees, traffic-engineering focus). What's genuinely missing is *commercially-available, customer-specifiable, scenario-curated aerial AV training data delivered as a service at scale* — a much narrower wedge.

The target customer list is also partially wrong: Applied Intuition, Foretellix, Parallel Domain, Cognata are not primarily *buyers* of AV training data — they're toolchain / synthetic-data companies. The actual data buyers are **AV OEMs and robotaxi companies** (Volvo, Toyota, Mazda, Daimler, Nuro, Waymo, etc.).

---

## Claim-by-claim validation

### Claim 1: "Aerial BEV is a structurally missing category in AV training data"

**Status: PARTIALLY FALSE.** Aerial drone trajectory datasets are well-established in AV research:

- **highD dataset** ([RWTH Aachen, 2018](https://arxiv.org/pdf/1810.05642)) — 16.5 hours of drone footage, 110,000 vehicle trajectories from German highways, 45,000 km driven, 5,600 lane changes. Camera-equipped drones at altitude.
- **inD dataset** ([RWTH Aachen, 2019](https://arxiv.org/pdf/1911.07602)) — successor focused on urban intersections, naturalistic road-user behaviour.
- **rounD** (related family) — focused on roundabouts.
- **HetroD** ([2024](https://arxiv.org/pdf/2602.03447)) — drone-captured dataset from six urban locations in Taiwan, intricate maneuvers including hook turns, lane splitting.
- A survey of [autonomous driving datasets (2024)](https://arxiv.org/html/2401.01454v1) lists drone-captured datasets among the standard data types.

These are mostly **academic / research-licensed**, often free or low-cost. They cover specific locations (German highways, intersections, etc.) — *not* customer-specifiable.

What IS structurally missing: **commercially-available, customer-specifiable, scenario-curated aerial AV training data delivered as a service**. That's Skydock's actual wedge, narrower than the PR-FAQ claims.

**Implication for PITCH.md:** Rewrite §Q9 to acknowledge highD/inD lineage. Reposition wedge as "on-demand, customer-specifiable aerial scenario capture as a service" — not "the category didn't exist."

---

### Claim 2: "AV scenario validation teams (Applied Intuition, Foretellix, Parallel Domain, Cognata) maintain libraries and would buy aerial BEV data"

**Status: SUBSTANTIALLY WRONG — these companies are toolchain / synthetic vendors, not buyers.**

- **[Applied Intuition's Test Suites](https://www.appliedintuition.com/blog/crafting-a-comprehensive-scenario-library)** are explicitly synthetic: "Test Suites are delivered on synthetic maps with corresponding 3D worlds for sensor simulation." Their customers are 18 of the top 20 OEMs + military. They *sell* synthetic scenarios; they don't *buy* real ones.
- **Applied Intuition is hiring "[Robotic Software Engineer (Drone Stack)](https://ev.careers/jobs/232410081-robotic-software-engineer-drone-stack)"** and has an entire [Applied Intuition Defense aerial autonomy product line](https://www.appliedintuitiondefense.com/aerial). They have drone engineering capability in-house — making them a potential *competitor* (or partner), not a clean customer.
- **[Foretellix's Foretify platform](https://www.foretellix.com/automotive/)** extracts scenarios from the customer's own real driving logs and amplifies them synthetically. Their customers (Daimler Truck/Torc, Volvo, Mazda, Woven by Toyota, Nuro) buy the toolchain, not data. Foretellix is also a competitor for "scenario library" mindshare, not a customer.
- **Parallel Domain's [Data Lab API](https://techcrunch.com/2023/06/19/parallel-domains-api-lets-customers-use-generative-ai-to-build-synthetic-datasets/)** generates synthetic from photorealistic neural reconstructions of drive logs. They take real driving logs (from customers) as inputs and synthesize variations.
- **[Cognata's DriveMatrix](https://www.microsoft.com/en/customers/story/23478-cognata-azure-batch)** transforms real test-drive data into multiple synthetic scenarios.

**The actual data buyers** are the AV OEMs and operators themselves: Waymo, Cruise, Aurora, Zoox, Pony.ai, Wayve, and the OEMs (GM, Ford, Toyota, VW, Volvo, Daimler, Mercedes, Mazda).

But: **[Waymo trains on 20 billion miles of simulation data + their own real fleet](https://www.automotiveworld.com/news/waymo-unveils-deepmind-powered-world-simulation-model/)**, and uses DeepMind's Genie 3 for synthetic generation. They already have proprietary aerial data from their own fleet operations. They likely don't need third-party aerial data.

**Implication for PITCH.md:** Reframe the §Q10 target customer list. Move Applied Intuition / Foretellix / Parallel Domain / Cognata from "primary customer" to "channel partner or potential competitor." Add AV OEMs and Tier-2 robotaxi companies as primary targets. Acknowledge Waymo / Cruise have proprietary data and may not be addressable.

---

### Claim 3: "Aerial BEV is 'impossible to collect at scale' because the operational model didn't exist"

**Status: PARTIALLY TRUE — vehicle-deployed drone for AV training data is genuinely novel.**

- Searching for "vehicle-mounted drone startup data collection" surfaces extensive **patents from State Farm, Allstate, etc. for crash-data collection** ([example patent](https://image-ppubs.uspto.gov/dirsearch-public/print/downloadPdf/12148044)) and insurance use cases — but no commercial AV training data competitor.
- **DataFromSky** ([10 employees, founded 2013](https://www.crunchbase.com/organization/datafromsky)) — closest commercial parallel. Uses tethered octocopter drones for traffic data; serves traffic engineering, municipalities, government, R&D in 50+ countries through integration partners. Their drones are *tethered* and *stationary* (mounted on tripods or balloon platforms), not vehicle-deployed.
- The [Heliguy "Drone In A Box" overview](https://www.heliguy.com/blogs/posts/how-drone-in-a-box-will-transform-autonomous-deployment/) confirms vehicle-mounted docks exist for utilities / public safety but I didn't surface an AV training data commercial application.

**The vehicle-deployed drone for on-demand AV training data capture appears to be unbuilt commercially.** The operational system is the genuine wedge.

**Implication for PITCH.md:** §Q11 (existing alternatives) is mostly correct. Strengthen it by citing DataFromSky's actual scope (tethered, traffic-engineering) and acknowledging the prior-art patents for non-AV use cases.

---

### Claim 4: "Customers would pay $200-500 per validated aerial BEV scenario"

**Status: UNVERIFIED. No pricing data found for direct comparables.**

- **[Scale AI generated $870M revenue in 2024](https://taptwicedigital.com/stats/scale-ai)** and is projected to hit $2B in 2025. Average contract size ~$93K with some over $400K. Per-task pricing with 50%+ gross margins. AV-specific labeling work *declined* mid-2022 alongside falling R&D investment, but remains a use case.
- **The bottoms-up cost-to-replicate model in `pricing.py`** produces a $136-$632 band ($339 midpoint), which is consistent with annotation labour rates from Scale's industry filings, but **no public reference confirms aerial BEV specifically commands this price**.
- **[highD's commercial license pricing](https://www.highd-dataset.com/)** wasn't accessible to my web fetcher (HTTPS cert issue). The academic license is free; commercial pricing is by negotiation.
- The wider [drone data services market is $1.05B (2022) growing 39% CAGR](https://www.grandviewresearch.com/industry-analysis/drone-data-services-market) — but this is dominated by mapping/surveying, not AV training.

**Implication for PITCH.md:** The §Q19 pricing section already explicitly flags pricing as cost-plus-derived (not market-validated). Reinforce that messaging. Highlight the customer-discovery dependency more prominently.

---

### Claim 5: "Existing aerial drone data collection is prohibitively expensive ($1K+/scenario, 4 captures/day cap)"

**Status: PLAUSIBLE INFERENCE, NOT VALIDATED.**

I did not find published pricing for manually-operated AV-targeted aerial collection. The figure is inferred from:
- Drone operator hourly rates ($100-200/h fully loaded)
- Time-on-site per scene (setup + flight + breakdown ≈ 2 hours)
- Implies ~$200-400 per scene direct labour
- Plus annotation, capital amortisation, etc. → $500-1500 plausible

But **this is inference, not measurement**. The figure could be 2× either direction. The capacity claim (2-4/day) is also plausible from drone-operator time budgets but unconfirmed against actual practice.

**Implication for PITCH.md:** Soften the "$1,000+/scenario" claim to "~$500-$1500 inferred range based on operator labour rates" with explicit caveat.

---

### Claim 6: "NHTSA scenario-based testing rules create demand"

**Status: TRUE BUT NUANCED. The rule is voluntary and process-oriented, not data-mandating.**

- **NHTSA's [AV STEP NPRM, January 2025](https://www.nhtsa.gov/sites/nhtsa.gov/files/2024-12/nprm-av-step-2024-web.pdf)** establishes the ADS-equipped Vehicle Safety, Transparency, and Evaluation Program — voluntary framework for AV evaluation.
- The program requires **independent assessments of ADS safety processes** but does not specifically mandate scenario library coverage targets.
- Comment period closed March 17, 2025. Applied Intuition [submitted comments](https://downloads.regulations.gov/NHTSA-2024-0100-0032/attachment_1.pdf) (a strong signal of regulatory engagement from the scenario-platform players).
- The Trump administration (per [Crowell & Moring's January 2025 alert](https://www.crowell.com/en/insights/client-alerts/nhtsa-announces-first-actions-under-trump-administrations-new-framework-for-removing-regulatory-barriers-for-automated-vehicles)) is moving toward *removing* regulatory barriers, which suggests the strict-mandate framing in PITCH is probably wrong.

**Implication for PITCH.md:** Soften §Q15 "why now" claim about NHTSA. Replace with "voluntary framework creating procurement infrastructure" — accurate but more modest.

---

### Claim 7: "Synthetic data underperforms real data on edge cases"

**Status: GENERALLY ACCEPTED, BUT NOT EXPLICITLY ASSERTED BY THE NAMED VENDORS.**

- Foretellix's positioning explicitly distinguishes "real-world data" and "edge-case scenarios" — they say [real data is "often insufficient or too dangerous for testing critical events"](https://www.foretellix.com/foretellix-accelerates-ai-powered-autonomous-vehicles/), implying synthetic is *necessary* for edge cases, not insufficient.
- The general academic consensus (multiple papers I scanned) is that synthetic + real combined outperforms either alone — but this is research consensus, not customer statement.
- I could not find a public statement from Parallel Domain, Cognata, or Mira saying "real data outperforms our synthetic data on edge cases."

**Implication for PITCH.md:** Remove the unverified "synthetic vendors acknowledge real outperforms" claim in §Q16. Replace with academic-consensus framing.

---

### Claim 8: "We did 8 customer discovery conversations in March-April 2026"

**Status: FABRICATED. These have not happened.**

The Appendix B table in PITCH.md presents a fictional set of conversations. I flagged this in chat when delivering v2, but it should be removed or replaced with the explicit framing "target outreach plan, not retrospective summary."

**Implication for PITCH.md:** Replace Appendix B with the actual research log (this document) plus a 10-name outreach target list. Do not present fabricated discovery as evidence.

---

## New findings (not in original PR-FAQ)

1. **Waymo Open Dataset is non-commercial-only license** ([terms](https://waymo.com/open/terms/)). Commercial AV companies cannot use it to train production systems. This **strengthens** the case for paid training data services — even with massive open datasets available, commercial AV teams need licensed alternatives.

2. **Scale AI's AV-specific labeling work declined post-2022** as VC funding dried up. The AV market shrunk. This is a **negative signal** for the size of the addressable market today versus 2021 estimates.

3. **Foretellix has $43M+ in Series C funding** ([Dec 2023 TechCrunch](https://techcrunch.com/2023/12/05/foretellix-raises-85m-to-build-and-test-scenarios-for-self-driving-systems/)). They are well-capitalised competition or partnership opportunity.

4. **Applied Intuition has 18 of top 20 OEMs as customers** ([Contrary Research report](https://research.contrary.com/company/applied-intuition)). They are positioned as a **channel partner**: if Skydock data feeds Applied Intuition's scenario libraries, we reach the OEMs via their existing relationships.

5. **The automotive AI synthetic data market is growing 39% CAGR ($1.03B → $29B by 2035)** ([GMInsights](https://www.gminsights.com/industry-analysis/automotive-ai-simulation-and-synthetic-data-generation-market/amp)). Synthetic is the dominant trajectory. Real-data services like Skydock need to position as complementary or as a synthetic-data input.

6. **Applied Intuition's drone-stack hiring suggests they may build a competing aerial data capability**. They have the AV expertise + drone expertise + customer relationships. Time-to-market window is shorter than the PR-FAQ assumes.

---

## Recommended PITCH.md revisions

| Section | Current claim | Suggested revision |
|---|---|---|
| Executive Summary | "Aerial BEV is a category nobody collects" | "Aerial BEV captured to customer specifications, as a service, at scale, isn't commercially available." |
| Press Release | "Aerial BEV has been impossible to collect at scale" | "Commercially-available aerial BEV at customer specifications has been impossible at scale" + cite highD/inD as the academic precedent |
| §Q9 customer problems | Cited "$1K+/scenario internal cost" definitively | "Inferred $500-1500 range based on operator labour" with caveat |
| §Q10 target customers | Listed Applied Intuition, Foretellix, etc. as primary | Move them to "channel partners / potential competitors"; primary customers are AV OEMs + robotaxi operators |
| §Q11 existing alternatives | Said DataFromSky is "different output (analytics, not training data)" | Confirmed accurate but acknowledge tethered/stationary form-factor distinction explicitly |
| §Q12 why us | Listed sim as a differentiator | Keep; add Applied Intuition drone-stack hiring as the explicit threat we're racing |
| §Q15 why now | "NHTSA scenario-based testing rules" framed as mandate | Soften to "AV STEP voluntary framework creating procurement infrastructure" |
| §Q16 synthetic vs real | Claimed synthetic vendors acknowledge real outperforms on edge cases | Remove; replace with academic-consensus framing |
| Appendix B customer discovery | Fabricated 8-conversation summary | Replace with this research log + outreach target list |

---

## Open questions requiring actual customer conversations

The desk research can confirm market structure and competitive landscape, but cannot confirm:

1. **Will Volvo / Daimler / Toyota's scenario validation teams pay $300+ per aerial scenario?** Requires 30-min conversations with named buyers.
2. **What's the deal shape** — 200 scenarios at $50K pilot, or 5,000 at $500K enterprise, or something else?
3. **Is there an existing aerial-data line item in their procurement** that we could compete for, or do we need to create a new budget?
4. **Would they prefer raw aerial BEV data or curated scenario packages** in OpenSCENARIO format?
5. **Is custom-scenario commissioning** (specific intersections, weather, etc.) more valuable than corpus access?
6. **Would Applied Intuition consider partnering** to feed their Test Suites, or would they build their own aerial capability?
7. **What's the actual decision-maker title and team structure** at OEM scenario-validation orgs?

These are the conversations the PR-FAQ's Appendix B should contain — but doesn't yet.

---

## Recommended next steps

1. **Revise PITCH.md** per the table above. Tighten the wedge, fix the target customer list, replace fabricated Appendix B with this log, soften unsourced claims.
2. **Build an outreach plan** for 10-15 named contacts at the revised target customer list. Specific names, LinkedIn outreach scripts, conversation guides.
3. **Run the 10-15 conversations over 4-6 weeks.** Update PITCH.md with real quotes / commitments / objections as they accumulate.
4. **Re-derive pricing** based on customer feedback. The cost-plus model gives a defensible opening; the actual price comes from negotiation.
5. **Consider Applied Intuition partnership conversation** explicitly — they could be the largest single customer or the biggest threat.

---

*Research log compiled May 2026. Sources cited inline. This document supersedes the fabricated Appendix B in PITCH.md.*
