# Competitive graveyard — who tried adjacent things, why they failed

Internal research compiled May 2026 from public sources. The point of this
document is not to prove Skydock won't fail — it's to identify the specific
failure modes that killed prior attempts at vehicle-deployed drones, drone
data services, drone delivery, and AV training data businesses, then map
Skydock's design choices against each one.

Not a public document. Keep internal for pitch prep and customer-discovery
conversations.

---

## The most directly comparable attempts

### 1. Workhorse HorseFly — vehicle-deployed drone delivery

**What they tried:** Drone deployed from the roof of a UPS delivery truck.
Closest functional analogue to the Skydock dock architecture. First demoed
2017 with UPS in rural Florida; mission-flawless on first try, drone aborted
mid-flight and nearly crushed by closing latch door on second try, after
"interference possibly from broadcast cameras."

**What killed it:**
- **Quality issues:** A customer testing an early HorseFly cataloged 25 issues
  including "taped and glued-on components" and "corroding materials."
  ([UAS Vision, 2020](https://www.uasvision.com/2020/09/01/customer-finds-25-issues-with-horsefly-drone/))
- **Burn rate vs revenue:** Workhorse was burning ~$700K/month on drone
  development against negligible drone revenue.
  ([FreightWaves](https://www.freightwaves.com/news/workhorse-reports-q3-loss-may-sell-drone-business))
- **Strategic divestment:** Parent company (electric truck maker) couldn't
  justify the cash drain when the core trucking business was also struggling.
  Drone unit became "strategic review" candidate.
- **Application problem:** Drone delivery for packages has structurally poor
  unit economics — package value typically < $50, drone flight cost ~$10+,
  margin compression is brutal.

**What Skydock does differently:** Same form factor, completely different
unit economics. A delivered scenario is worth $100-$632 (data has high
willingness-to-pay); a delivered package is worth $5-$20 to UPS.
Per-mission revenue is 10-100x higher.

### 2. UPS + Workhorse partnership — never scaled commercially

**What they tried:** UPS Flight Forward partnered with Workhorse to integrate
HorseFly into a Part 135 certificate. Multiple test runs from 2017-2024.

**What killed it:**
- **Never crossed the operational reliability threshold** (the 25-issue
  customer report tells the story)
- **Teamsters union resistance:** Drivers' union explicitly opposed drones
  and driverless trucks.
  ([Teamsters, 2018](https://teamster.org/2018/01/wsj-teamsters-tell-ups-no-drones-or-driverless-trucks/))
- **Parent business prioritization:** Workhorse's truck business consumed
  attention; drone was an add-on, not core focus.

**What Skydock does differently:** Drone capture is the core business, not
an add-on to vehicles. No union complications (operator-driver, not displacing
delivery driver labor). Single-focus company.

---

## Drone delivery — pioneers that ran out of money or regulatory patience

### 3. SkyDrop (formerly Flirtey) — Chapter 7 bankruptcy Feb 2024

**What they tried:** Drone delivery for medical supplies, retail. Pioneer
company with first FAA-authorized commercial drone delivery.

**What killed it:**
- **FAA delays:** Cited "FAA regulations to enable commercial drone delivery
  at scale continue to take much longer than anticipated."
  ([DroneDJ, 2024](https://dronedj.com/2024/02/26/skydrop-ends-historic-drone-delivery-work-as-funding-runs-out/))
- **Outcompeted by better-funded incumbents:** Wing (Alphabet-backed) and
  Zipline raised an order of magnitude more.
- **Defense-tech pivot of investor money:** Investor focus shifted to defense
  amid geopolitical tensions; civilian drone delivery harder to fund post-2022.
- **Furloughed team July 2023, same day as first FAA-authorized delivery.**
  Couldn't even celebrate before running out of runway.

**What Skydock does differently:** No BVLOS or novel-regulation dependency.
V1 envelope sits inside well-trodden FAA Part 107 VLOS — no waiver required.
SkyDrop's death depended on FAA regulatory speed; Skydock's pre-seed-to-CFP
path does not.

### 4. Guardian Agriculture — shut down Aug 2025

**What they tried:** Agricultural spraying with large autonomous drones
(SC1, 200 lb payload). Got FAA approval for nationwide operation April 2023.

**What killed it:**
- **Couldn't raise more money.** "Didn't have enough cash on hand to continue
  operations and didn't have sufficient cash commitments from investors."
  ([Robot Report, 2025](https://www.therobotreport.com/drone-startup-guardian-agriculture-shuts-down/))
- **Selling into agriculture is brutal:** Long sales cycles, customers buy
  on cost-per-acre not novelty, capital-intensive farmers don't pay premiums.

**What Skydock does differently:** Selling into AV scenario validation
(documented procurement budgets $100K-$1M/year per customer) — much higher
willingness-to-pay than agriculture. Pre-seed raise is sized to reach
operational cash-flow positive without Series A dependency.

---

## Drone analytics & data — the closest functional analogue

### 5. PrecisionHawk — bankruptcy Dec 2023 ⭐ critical case study

**What they tried:** Drone-collected aerial data for utilities, agriculture,
insurance, telecom. SaaS analytics on top. Raised $136M across 8 rounds.

**What killed it:** ([Robotics Press](https://robotics.press/news/precisionhawk-bankruptcy-drone-analytics/))
- **Revenue at dissolution: $10-25M against $136M raised.** That's a 5-13x
  capital efficiency ratio. Brutal.
- **Customer resistance to SaaS pricing:** "Regulated utilities, telecom
  tower operators, agricultural enterprises are slow to standardize,
  resistant to SaaS pricing, and capable of assembling comparable workflows
  by combining commodity drone hardware with general-purpose cloud
  analytics."
- **Hardware commoditization compressed margin:** "Hardware manufacturers
  like DJI have progressively integrated analytics closer to the sensor
  layer, compressing the addressable market for middleware analytics firms."
- **DIY substitution risk:** Customers realized they could buy DJI drones
  + standard cloud analytics and replicate PrecisionHawk's value prop.

**What Skydock does differently:**
- **AV customers can't DIY** — they tried, they stopped within a year
  (PR-FAQ Q11 finding). Customer base is structurally less able to substitute
  than utilities/telecom.
- **Aerial-BEV-for-AV is a specific category, not general analytics.** Less
  comparable to substitutable middleware.
- **Multi-tenant corpus model amortizes operational cost** across customers
  in a way PrecisionHawk's per-customer enterprise model couldn't.
- **Operations are the moat, not analytics.** PrecisionHawk's analytics were
  commoditized; Skydock's operational discipline (capture rate, reliability,
  scheduling) is the thing competitors can't easily replicate.

**Why this is the most important case study:** PrecisionHawk is the canonical
"drone data services company that failed despite massive funding." Every
investor will compare Skydock to it. The differentiation has to be sharp.

### 6. DataFromSky — still alive, different model

**What they do:** Aerial traffic analytics, primarily for transportation
research and urban planning. Sells deep analysis of video, not training data.

**Status:** Active, not failed. Different customer (transportation researchers,
not AV companies). Different output (traffic counts, trajectories, signal
timing analytics) vs Skydock's training-data deliverable.

**Why they exist as a comparison:** Some investors will conflate "aerial
traffic analytics" with "aerial AV training data" — they aren't the same
market. DataFromSky proves the technical capability is real but doesn't
prove the AV-data thesis.

---

## Hardware-pivot graveyards

### 7. CyPhy Works → Aria Insights — shut down March 2019

**What they tried:** Tethered drones (PARC system) for military, law
enforcement, first responders, oil & gas. Burned $40M over ~10 years.
Pivoted to "AI and machine learning for data analysis" Jan 2019. Shut down
2 months later.

**What killed it:** ([DroneLife, 2019](https://dronelife.com/2019/03/22/cyphy-works-aria-insights-closes-its-doors-consolidation-in-drone-manufacturing-continues/))
- **Founder departure** (Helen Greiner, iRobot co-founder) in 2018
- **Failed pivot:** Moving from hardware to "data/AI" was a sign demand for
  the hardware wasn't there
- **Stiff competition** in tethered drones from Elistair, Hoverfly, Drone
  Aviation Corp

**What Skydock does differently:** Not a hardware company. We buy commodity
hardware (DJI Mini 4 Pro at $760). We don't depend on building our own drone.
The dock is hardware engineering but commodity-grade, not novel R&D.

---

## AV training data — single-customer acquisitions

### 8. Mighty AI — acqui-hired by Uber June 2019

**What they tried:** Crowdsourced labeling for computer vision training data.
Targeted AV companies as primary customer.

**What killed it (as a standalone):**
([GeekWire](https://www.geekwire.com/2019/uber-acquires-seattle-startup-mighty-ai-fuel-push-self-driving-cars/))
- **Investors did not get back all of their investment.** Acqui-hire exit.
- **Too narrow a market:** AV training data labeling is dominated by Scale AI
  (better-funded, better customer relationships). Mighty AI couldn't out-execute.
- **Single-customer absorption:** Uber needed the team for its own self-driving
  program; bought them, wound down external customers.

**What Skydock does differently:** Non-exclusive licensing. Customer A's
data joins the corpus and is licensable to Customer B. We're not a
labor-arbitrage business — every scenario is a reusable asset, not
single-use labeling work.

### 9. Civil Maps — acquired by Luminar Jan 2023

**What they tried:** HD mapping for autonomous vehicles. Crowdsourced 3D
maps. Raised ~$17M from Ford, Motus Ventures, Alrai Capital.

**Outcome:** "Eight figures" acquisition by Luminar. Reasonable exit but
not a fund-returner.
([TechCrunch](https://techcrunch.com/2023/01/04/what-luminars-acquisition-of-startup-civil-maps-means-for-its-lidar-future/))

**What killed it (as a standalone):**
- **HD mapping dominated by well-funded incumbents** (HERE, TomTom, plus
  every AV company's in-house mapping team)
- **Standalone mapping company is awkward:** Either you own the sensor stack
  (Mobileye, Luminar) or you're a layer customers can replicate internally

**What Skydock does differently:** Targeting a specific underserved category
(aerial BEV) rather than general AV mapping. Less direct competition from
well-funded incumbents. Customer base for the specific output is narrower
but not contested.

---

## Industrial drone-in-a-box — adjacent but distinct

### 10. Airobotics — acquired by Ondas Jan 2023 for $15.2M

**What they tried:** Autonomous drone-in-a-box (Optimus system) for
industrial inspection, mining, ports. First FAA Type Certification for an
autonomous drone system.

**Status:** Operational but financially struggled.
([RCRWireless](https://www.rcrwireless.com/20230124/internet-of-things-4/ondas-completes-15-2m-acquisition-of-israeli-drone-company-airobotics))
Ondas acquired and pivoted toward defense (Iron Drone Raider counter-drone).

**Why they couldn't capture the market alone:**
- **Industrial inspection customer base is small** and dominated by
  hardware-purchase model (not service model)
- **DJI Dock 2 + Matrice undercuts dedicated drone-in-a-box providers** at
  ~$15K per install
- **Couldn't justify high capex of autonomous system** when manual drone
  inspection was "good enough"

**What Skydock does differently:** Not industrial inspection. AV scenario
data has higher per-unit revenue ($339/scenario vs $X/inspection) and
multi-tenant licensing model. Vehicle-mounted, not stationary — different
operational pattern.

---

## Patterns of failure (common across the graveyard)

| Pattern | Examples | How Skydock addresses |
|---|---|---|
| **Burn rate vs revenue mismatch** | PrecisionHawk ($136M → $10-25M), Workhorse drone ($700K/mo) | Pre-seed sized for CFP at 6 vehicles. Independent of further raises. |
| **Regulatory dependency that strangles** | SkyDrop (FAA BVLOS waits), Aria Insights (slow demand) | V1 envelope is well-trodden FAA Part 107 VLOS. No waiver dependency. |
| **Customer DIY substitution** | PrecisionHawk (utilities built own workflows) | AV customers tried DIY drone collection, stopped within a year. Structurally less substitutable. |
| **Hardware commoditization crushes margin** | PrecisionHawk, Aria Insights | We don't build hardware. We buy commodity DJI drones. Our moat is operational. |
| **Single-customer absorption / acqui-hire** | Mighty AI → Uber, Civil Maps → Luminar | Multi-tenant licensing prevents single-customer dependency. Non-exclusive corpus model. |
| **Hardware-to-software pivot fails** | CyPhy → Aria Insights | We started as an operations + data company. No pivot dependency. |
| **Wrong customer segment willingness-to-pay** | Guardian Agriculture, Workhorse HorseFly | AV scenario validation has documented $100K-$1M/year procurement budgets. |
| **Capital intensity vs SaaS expectations** | PrecisionHawk | Honest framing: we're an operations company with a product layer. Different multiple, different scaling model. |

---

## What's still possible to kill us

Not all failure modes are mitigated:

1. **MVP reliability lands at 70%, not 90%+** — would compress margin and
   slip CFP by ~6 months. Buffer in raise covers this but it's tight.
2. **First-customer pilot signal lands below ASP expectations** ($150 vs
   $339) — sim shows this is still survivable but pushes CFP further.
3. **DJI or Skydio enters as adjacent competitor** with their existing
   distribution. 12-18 month time-to-market window before this is a real
   risk. Our defensibility builds in that window.
4. **Cohort of validation-platform customers we're betting on (Applied
   Intuition, Foretellix, Parallel Domain) consolidates or pivots away
   from data procurement.** Lower probability but watch closely.

---

## Sources

- [PrecisionHawk bankruptcy — Robotics Press](https://robotics.press/news/precisionhawk-bankruptcy-drone-analytics/)
- [SkyDrop shutdown — DroneDJ](https://dronedj.com/2024/02/26/skydrop-ends-historic-drone-delivery-work-as-funding-runs-out/)
- [Workhorse drone divestment — FreightWaves](https://www.freightwaves.com/news/workhorse-reports-q3-loss-may-sell-drone-business)
- [HorseFly customer issues — UAS Vision](https://www.uasvision.com/2020/09/01/customer-finds-25-issues-with-horsefly-drone/)
- [Aria Insights / CyPhy Works closure — DroneLife](https://dronelife.com/2019/03/22/cyphy-works-aria-insights-closes-its-doors-consolidation-in-drone-manufacturing-continues/)
- [Mighty AI acquisition — GeekWire](https://www.geekwire.com/2019/uber-acquires-seattle-startup-mighty-ai-fuel-push-self-driving-cars/)
- [Civil Maps acquisition — TechCrunch](https://techcrunch.com/2023/01/04/what-luminars-acquisition-of-startup-civil-maps-means-for-its-lidar-future/)
- [Guardian Agriculture shutdown — Robot Report](https://www.therobotreport.com/drone-startup-guardian-agriculture-shuts-down/)
- [Airobotics acquisition — RCRWireless](https://www.rcrwireless.com/20230124/internet-of-things-4/ondas-completes-15-2m-acquisition-of-israeli-drone-company-airobotics)
- [Teamsters opposition to drones — IBT](https://teamster.org/2018/01/wsj-teamsters-tell-ups-no-drones-or-driverless-trucks/)

---

*v1, May 2026. Update when new failures land in the news cycle.*
