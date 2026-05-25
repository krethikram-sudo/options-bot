# AV training data — what's actually valuable, and where aerial drone fits

Internal research compiled May 2026 from public sources. Purpose: validate
whether Skydock's aerial BEV data solves a real customer problem, or just
adds another option to a saturated training-data market.

**TL;DR (for the impatient):** Aerial drone BEV data has a real, validated
role in AV development — but it's narrower than "more data for AV training."
The honest customer is the **simulation / validation / trajectory-prediction**
side of the AV stack, NOT the perception model training side. This research
refines (and in places narrows) the Skydock thesis vs the current PR-FAQ.

---

## 1. How AV training actually works in 2026

AV development now sits across three converging architectures:

| Architecture | Who uses it | Data needs |
|---|---|---|
| **Modular** (perception → prediction → planning) | Aurora, Zoox, Nuro | Ego-sensor data (camera + lidar + radar) for perception. Trajectory data for prediction. Plan-and-control simulations. |
| **End-to-end foundation model** | Tesla, Wayve, Waymo (recent) | Multimodal vision/language/trajectory at massive scale. ~10x more data per generation (per Wayve GAIA-3 launch Dec 2025). |
| **Hybrid scenario-based validation** | Applied Intuition, Foretellix, OEMs | OpenSCENARIO 2.0 scenarios with agent tracks + road network for replay-driven testing. |

Critical distinction: **training data and validation data are different categories**.
- Training data feeds the model what it should learn to see/predict/decide
- Validation data tests whether the model is correct, using ground truth from a different source

A frequently-overlooked observation from the [BEV perception literature](https://www.sciencedirect.com/science/article/abs/pii/S0957417424019705):
**BEV perception models in the AV stack are GENERATED from ego-vehicle
cameras and lidar** (via Lift-Splat-Shoot or Fast-BEV). They reconstruct a
top-down view from the perspective of cameras mounted on the car. They
don't natively consume aerial drone footage as a sensor input.

This matters because it constrains where aerial drone data can fit.

## 2. What data is actually scarce / valuable

From [Tenyks' CVPR 2023 hidden-challenges talk](https://medium.com/@tenyks_blogger/cvpr-2023-five-hidden-challenges-in-autonomous-driving-where-data-is-key-8666fff09ed7), the [Uber AV Labs long-tail
focus](https://www.automotivetestingtechnologyinternational.com/news/rd/uber-launches-av-labs-to-collect-long-tail-autonomous-vehicle-data.html), and the trajectory-prediction long-tail literature:

| Data type | Scarcity | Value | Who needs it |
|---|---|---|---|
| **Long-tail trajectory data** (rare/dangerous behaviors) | Very high | Very high | Trajectory prediction model trainers; scenario library builders |
| **VRU interactions** (peds, cyclists, motorcyclists) | High — "more than half of global traffic deaths, yet detection remains challenging" ([source](https://www.digitaldividedata.com/blog/vru-detection-for-autonomous-vehicle-safety)) | Very high (safety case) | Perception teams, scenario library builders |
| **Adverse weather** (snow, heavy rain, fog) | Very high | High | Perception teams (ego sensor data needed) |
| **Edge case scenarios** (construction zones, unusual events, animals on road) | Very high | High | Scenario libraries; end-to-end model training |
| **4D radar data** | High (new sensor category) | Medium | Sensor fusion teams |
| **Vision-language-action joint data** | High | High | End-to-end foundation model teams (Wayve, Tesla, Waymo) |
| **Emergency vehicles, exotic vehicles** | High | Medium | Perception robustness |
| **Naturalistic driving from above** (real interactions, ground truth) | Medium (academic datasets exist but limited) | High for trajectory + scenario use cases | Validation platforms; sim companies |

Key quote from the long-tail edge case research: *"The problem isn't that we
don't have data, but rather that we don't have a good way to understand where
the edge cases are."* ([source](https://www.basic.ai/blog-post/15-new-autonomous-driving-datasets-in-2024-2025))

**This is a sharp challenge to "more data is better" pitches.** AV companies
have a lot of data; what they need is *the right kind of curated coverage*.

## 3. The existing aerial drone dataset competition (mostly missed in our PR-FAQ)

This was the most surprising finding. **Drone-collected aerial datasets for
AV research have existed since 2018** and several are commercially licensed.

| Dataset | Year | Provider | Scope | License |
|---|---|---|---|---|
| **highD** | 2018 | levelXdata ([drone-dataset.com](https://www.drone-dataset.com)) | German highways, 16.5h, 110,000 vehicles, 5,600 lane changes | Free for research, commercial license required |
| **inD** | 2019 | levelXdata | German intersections | Same as highD |
| **rounD** | 2020 | levelXdata | German roundabouts | Same as highD |
| **exiD** | 2022 | levelXdata | Highway exits | Same as highD |
| **openDD** | 2020 | Aptiv research | 7 roundabouts, ~10h | Open / research |
| **MiTra** | 2025 | Polytechnic Milan | Milan A50 freeway, 6 drones, all traffic states | Open / academic |
| **DeepUrban** | 2026 | Academic | Dense urban intersections at ~100m altitude | Open / academic |
| **AUTOMATUM DATA** | 2021 | AUTOMATUM | Drone-based highway, German | Commercial |

What this means for Skydock:
- **The category is not unaddressed.** levelXdata has been selling aerial
  trajectory data to the AV industry for 7 years.
- **The market accepts this product class.** Commercial licenses are sold
  (we can assume major OEMs and Tier 1s are buyers).
- **But the existing offerings are geographically and operationally limited.**
  Mostly German, mostly highways, one-off captures, not customizable.

The Skydock wedge **vs existing aerial datasets**:
- **US geographic coverage** (existing competition is European-dominated)
- **On-demand custom waypoints** vs fixed academic-style snapshots
- **Continuous capture** at customer-specified locations vs one-time research collections
- **OpenSCENARIO 2.0 native delivery** vs format-converter-required academic data
- **Commercial SLA + delivery pipeline** vs research-grade data dumps

This is a meaningful but *narrower* wedge than "the missing aerial BEV
category" claim in our PR-FAQ.

## 4. Where aerial drone data ACTUALLY fits in AV development

Honest mapping based on the architecture overview in §1:

### High value (clear product-market fit)

1. **Trajectory prediction model training** — every cited drone dataset (highD,
   inD, openDD) is used for exactly this. Naturalistic agent trajectories
   from above with no occlusion are the gold standard for training trajectory
   prediction models. **Customer cohort: trajectory prediction teams at AV
   companies + research labs.**

2. **Scenario library population** — Applied Intuition, Foretellix, and
   similar platforms convert real-world recordings into OpenSCENARIO 2.0
   scenarios for replay-driven validation. **Drone footage is an ideal
   capture modality** because it provides full multi-agent ground truth
   without ego-vehicle occlusion. **Customer cohort: validation platforms.**

3. **Independent perception validation ground truth** — when an AV team
   wants to validate their on-vehicle perception, they need ground truth
   from a sensor system that's independent of the one being tested. Aerial
   drone provides this independence. **Customer cohort: AV company
   perception validation teams (a subset of perception, focused on QA).**

4. **Multi-agent interaction studies** — research and product teams studying
   how vehicles, peds, cyclists interact at intersections benefit from
   uncluttered top-down views. **Customer cohort: behavior research teams,
   urban planning, scenario authors.**

### Medium value (works but with caveats)

5. **Synthetic data validation** — Parallel Domain, Cognata, and Mira need
   real data to validate their synthetic generators. Aerial real data is
   useful here, but they ALSO need ego-perspective real data. We're one
   input among several. **Customer cohort: synthetic data companies.**

6. **End-to-end foundation model training** — Wayve, Tesla, Waymo
   foundation models can ingest aerial data, but ego-perspective video
   dominates the training distribution. Aerial is a small fraction of
   their data needs.

### Low value (don't pitch this)

7. **Perception model training (ego-vehicle sensors)** — Wrong perspective.
   The AV's perception model needs to learn from ego-vehicle camera/lidar
   perspective. Aerial drone footage doesn't match the sensor stack the
   model is deployed against.

8. **Sensor fusion training** (camera + lidar + radar) — Drone footage has
   none of these sensors in the right configuration.

## 5. Refined Skydock thesis

Based on this research, the honest customer-facing pitch is:

> **Skydock sells on-demand, US-geography, OpenSCENARIO-formatted aerial
> capture for AV scenario libraries and trajectory prediction model
> training. We are not a replacement for ego-vehicle sensor data; we are
> the aerial-ground-truth complement to it.**

This is more precise than the PR-FAQ's current framing ("aerial BEV is the
structurally missing AV training category"). The category is partly
addressed by existing players; what's missing is **commercial, on-demand,
US-coverage capture at customer-specified waypoints**.

### Implications for target customers (vs current PR-FAQ)

| Customer cohort | Current PR-FAQ claim | Research-validated claim |
|---|---|---|
| Validation platforms (Applied Intuition, Foretellix) | Primary buyer | ✓ Strong — they need scenarios for libraries, our data drops in via OpenSCENARIO |
| Synthetic data co's (Parallel Domain, Cognata) | Primary buyer | ⚠️ Real data is one of several inputs; we're a complement not a substitute |
| AV perception teams (Waymo, Aurora, Pony.ai) | Primary buyer | ⚠️ For perception validation YES; for perception model training NO (perspective mismatch) |
| AV trajectory prediction teams | Not explicit | ✓ STRONG and overlooked — this is the highD/inD use case |
| OEMs (GM, Ford, Toyota) | Year-3 customer | ⚠️ Depends on their internal AV strategy maturity |

The biggest reframe: **trajectory prediction is an underemphasized customer
cohort** in our current pitch. Every academic aerial dataset (highD, inD,
openDD) is used primarily for trajectory prediction research. This is a
crystal-clear, validated customer need that doesn't depend on novel
arguments about "aerial BEV is the missing category."

### What this means for differentiation vs levelXdata

Our website's "competitive landscape" table currently lists fixed-base
drones, manual collection, synthetic, public scraping. **It should also
list levelXdata** (and we should differentiate against them):

| Player | Coverage | On-demand | Commercial SLA | Native AV format |
|---|---|---|---|---|
| levelXdata (highD/inD/rounD) | German, fixed locations | No — fixed dataset releases | Yes (paid commercial license) | Custom format, conversion required |
| Academic (openDD, MiTra, DeepUrban) | Various, fixed | No | No (free, research-grade) | Various |
| Skydock | US, expanding | Yes, custom waypoints | Yes | OpenSCENARIO 2.0 native |

This is a more defensible and accurate competitive claim than "category
is empty."

## 6. Critical residual questions

Even with this refined thesis, three unanswered questions remain:

1. **Are validation platforms actually budget-buying aerial scenarios at
   the rates we're pricing?** Discovery showed pricing tolerance at
   $200-$500 — but the question is whether that's verbal interest or
   committed budget. Need a paid pilot to confirm.

2. **Will trajectory prediction teams pay for our data when levelXdata's
   commercial license is available?** levelXdata has 7-year incumbency.
   We need to understand their pricing and customer base to position
   against them.

3. **How fast does end-to-end foundation model architecture eat the
   modular scenario-based approach?** If Wayve / Tesla / Waymo all
   converge on end-to-end and stop maintaining scenario libraries, our
   biggest customer cohort (validation platforms) could shrink. The
   counter-evidence: Foretellix + Parallel Domain partnership in Nov
   2025 suggests scenario-based validation is still being heavily
   invested in.

## 7. Concrete next steps

1. **Update the website's competitive landscape** to include levelXdata
   and frame the differentiation more sharply (US + on-demand + native
   OpenSCENARIO).

2. **Add trajectory prediction as an explicit customer use case** on the
   "Scene classes" or "What you get" sections.

3. **Sharpen the discovery script** to probe trajectory prediction teams
   specifically (currently the discovery plan targets perception leads —
   we should also probe behavior / prediction / simulation teams).

4. **Reach out to levelXdata** for a peer / partnership / "we focus on a
   different geography" conversation. Either they validate our wedge or
   they consider a partnership.

5. **Survey 3-5 trajectory prediction researchers** (academic and
   industry) on whether they'd pay for US-specific custom-waypoint aerial
   data. This is a cheap signal to verify the refined thesis.

---

## Sources

- [Edge cases & long-tail driving — Basic.AI](https://www.basic.ai/blog-post/15-new-autonomous-driving-datasets-in-2024-2025)
- [VRU detection challenges — DDD blog](https://www.digitaldividedata.com/blog/vru-detection-for-autonomous-vehicle-safety)
- [Uber AV Labs long-tail collection](https://www.automotivetestingtechnologyinternational.com/news/rd/uber-launches-av-labs-to-collect-long-tail-autonomous-vehicle-data.html)
- [BEV perception state of the art — ScienceDirect](https://www.sciencedirect.com/science/article/abs/pii/S0957417424019705)
- [Camera-only BEV perception — arxiv](https://arxiv.org/pdf/2505.06113)
- [Wayve GAIA-3 launch](https://wayve.ai/press/wayve-launches-gaia3/)
- [highD dataset paper](https://arxiv.org/pdf/1810.05642)
- [inD dataset paper](https://arxiv.org/pdf/1911.07602)
- [levelXdata commercial license](https://www.drone-dataset.com)
- [openDD dataset paper](https://arxiv.org/pdf/2007.08463)
- [MiTra dataset paper — Nature](https://www.nature.com/articles/s41597-025-05472-0)
- [DeepUrban dataset paper](https://arxiv.org/pdf/2601.10554)
- [Trajectory prediction long-tail — SAIL paper](https://arxiv.org/pdf/2604.04573)
- [NHTSA AV STEP NPRM 2024](https://www.nhtsa.gov/sites/nhtsa.gov/files/2024-12/nprm-av-step-2024-web.pdf)
- [Foretellix + Parallel Domain partnership Nov 2025](https://www.foretellix.com/foretellix-parallel-domain-simulation/)
- [Waymax simulator paper](https://ar5iv.labs.arxiv.org/html/2310.08710)
- [Tenyks: Five hidden CVPR challenges](https://medium.com/@tenyks_blogger/cvpr-2023-five-hidden-challenges-in-autonomous-driving-where-data-is-key-8666fff09ed7)

---

*v1, May 2026. This document refines the customer thesis and should
inform: PITCH.md updates, the website's competitive landscape section,
the discovery plan target list, and any conversations with prospects
about what they actually use our data for.*
