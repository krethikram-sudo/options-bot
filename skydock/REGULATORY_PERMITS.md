# Regulatory permits + compliance for Skydock

Internal doc. Comprehensive list of permits, licenses, and compliance
requirements for commercial drone-on-vehicle aerial BEV capture in the US,
operating from a Bay Area base.

**⚠️ Critical correction to PITCH.md Q27**: Our prior claim that "DJI Mini
4 Pro at 249g qualifies for sub-250g FAA Remote ID exemption" is **wrong
for commercial Part 107 operations**. The sub-250g exemption applies only
to RECREATIONAL flying. **Under Part 107, drones of any weight require
registration AND Remote ID compliance.** This was confirmed in 2024-2026
FAA enforcement guidance. PITCH.md and any investor materials referencing
this exemption need an update.

---

## 1. Federal (FAA) — required to operate at all

### 1.1 Part 107 Remote Pilot Certificate
- **Required for every operator** flying commercially
- $175 exam (FAA Initial Airman Knowledge Test)
- Background check via TSA
- 60-month renewal cycle (free online recurrent training)
- **Skydock count**: every operator-driver must hold this. 4 ops at full fleet
  = 4 certificates. Total cost: $700 one-time + recurrent training time.
- Source: [FAA Part 107](https://www.faa.gov/uas/commercial_operators)

### 1.2 Drone registration
- $5 per drone, 3-year validity
- **Required for ALL drones under Part 107** regardless of weight
- Skydock count at full fleet: 6 vehicles × 3 drones = 18 drones registered
- Total cost: $90 (renewable every 3 years)
- Source: [FAA registration](https://www.faa.gov/uas/getting_started/register_drone)

### 1.3 Remote ID compliance ⚠️ THIS IS THE CORRECTION
- **MANDATORY for all Part 107 operations as of March 16, 2024**
- **Sub-250g exemption does NOT apply to commercial Part 107 flights**
  (only recreational under §44809)
- DJI Mini 4 Pro has built-in Remote ID broadcast — compliance is automatic
- Alternative: fly from FAA-Recognized Identification Area (FRIA) —
  impractical for vehicle-mounted ops since FRIAs are fixed sites
- **Implication**: our planned hardware is compliant out-of-box; the *claim*
  that we benefit from a sub-250g exemption is wrong
- Source: [HOVERAir Part 107 guide](https://hoverair.com/blogs/guide/faa-part-107-guide),
  [Drone Nestle](https://dronenestle.com/what-size-drone-requires-a-license/)

### 1.4 LAANC airspace authorization
- **Required for every flight in controlled airspace**
- Bay Area has three stacked controlled airspace rings:
  - SFO Class B (SF peninsula + much of city)
  - OAK Class C (East Bay)
  - SJC Class C (most of South Bay)
- LAANC = Low Altitude Authorization and Notification Capability — automated
  via apps like Aloft, Skyward
- **Authorization is per-flight, not a blanket permit** — operational
  overhead but routine; typically instant for daylight + standard altitudes
- Source: [Drone Girl SF guide](https://www.thedronegirl.com/2025/10/03/flying-drones-in-san-francisco/)

### 1.5 Part 107 waivers (only needed for V2 envelope)
- **Not required for V1** (daylight, VLOS, stationary vehicle)
- Required for V2: BVLOS, night ops, ops over people, moving-vehicle launch
- BVLOS waivers: 6-12 month process, **single-digit approval rate for novel
  use cases**
- Cost: free to apply but legal counsel typically $5K-$15K per waiver
- Source: PR-FAQ Q28

### 1.6 Part 137 / Part 135 — NOT needed
- Part 137: agricultural ops (not us)
- Part 135: package delivery (not us — we deliver data, not packages)
- Stick to Part 107 = simpler regulatory path

---

## 2. State (California) — privacy + business

### 2.1 California Civil Code §1708.8 (anti-paparazzi)
- **Cannot fly below 350 ft over private property to capture images of
  personal activities without consent**
- **Civil penalties: $5,000 - $50,000 per violation**
- Property owner can sue directly
- **Implication for Skydock**: must stay over public right-of-way (streets,
  intersections) and avoid flying into private airspace at low altitude.
  Our 80m AGL captures over public intersections are compliant.
- Source: [California Drone Laws](https://drone-laws.com/drone-laws-in-california/)

### 2.2 California AB 856 (2015) + 2025 expanded privacy protections
- Expanded privacy law explicitly banning drone recording in private
  spaces without consent
- Strengthens §1708.8 — more enforcement teeth
- **Implication**: our agent_tracks.json output (anonymized positions, no
  PII) plus face/license-plate blurring on optional raw video is the
  right defensive posture
- Source: [California Drone Laws](https://drone-laws.com/drone-laws-in-california/)

### 2.3 California state parks ban
- Drones banned in 280+ state parks
- Special permits available but rarely granted
- **Implication for Skydock**: stay off state-park airspace; not relevant
  to typical urban intersection captures

### 2.4 California business registration
- Delaware C-corp (per EXECUTION_PLAN) registered as foreign entity in CA
  — California Secretary of State filing, ~$70 + $25 statement of info
- California EDD employer registration (required when first hire)
- California EIN (federal already; state often needed too)
- Workers' compensation insurance — **required by California for any W-2
  employee**, including operator-drivers
- Source: [California Secretary of State](https://www.sos.ca.gov/business-programs)

### 2.5 Sales tax — likely exempt
- California treats data licensing as a service (generally not taxable)
- BUT delivery of recorded video on physical media or with software access
  may trigger sales tax
- **Get a CPA review at Phase 0/1** before pricing decisions are locked in
- Source: [California BOE](https://www.cdtfa.ca.gov/)

---

## 3. Local (San Francisco + Bay Area) — operational restrictions

### 3.1 San Francisco Park Code §3.09
- Bars launching or landing any aircraft in city parks without SF Rec &
  Park written permission
- Currently under standing moratorium on recreational drone permits
- **Only commercial film/photography shoots processed through SF Film
  Office can obtain authorization**
- **Implication for Skydock**: must launch from streets / private property,
  not city parks. Operational planning needs to account for this.
- Source: [SF Park Code](https://www.sf.gov/information--requirements-film-drone)

### 3.2 SF Film Office permit (if filming on city property)
- **Requires $2M liability insurance specifically for drone operations**
- Per-shoot permit
- **Implication**: if we ever do customer-commissioned captures from city
  property (e.g., specific intersection rooftop), need this. Not required
  for waypoint captures from public streets / private property.

### 3.3 Presidio + National Parks (GGNRA)
- Drone operations **prohibited** on Presidio Trust lands
- Drone operations prohibited in Golden Gate National Recreation Area
- **Implication**: our operating territory is non-park urban areas only.
  No Presidio / GGNRA captures.

### 3.4 Per-city business licenses
- Each Bay Area city where we have operations may require a business
  license:
  - SF: General Business License ($90+ annual, scaled by revenue)
  - Oakland, Berkeley, San Jose: separate filings
- **Implication**: budget ~$500-$1000/year for city business licenses

### 3.5 No-fly zones to be aware of
- Stadiums during events (FAA TFR — Temporary Flight Restriction)
- VIP visits (presidential / dignitary TFRs)
- Wildfires (FAA fire TFRs)
- Major public events (Pride parade, marathons, etc.)
- **Implication**: operational scheduling needs daily TFR checks (Aloft app)

---

## 4. Insurance — required by customers and CA

### 4.1 Commercial drone liability
- California "generally requires $1M minimum liability" per state guidance
- Enterprise customers typically require $1M-$2M
- Premium: $750-$1,500/year for $1M coverage
- **Skydock at 6-vehicle scale**: probably $3-5K/year aggregated
- Source: [SkyWatch](https://www.skywatch.ai/blog/part-107-commercial-drone-insurance-guide),
  [BWI Fly](https://bwifly.com/drone-insurance/)

### 4.2 Commercial vehicle insurance
- Required for commercial use of Toyota RAV4 fleet (different from personal
  insurance — personal coverage void if used commercially)
- Estimated $1,500-$2,500/year per vehicle
- 6 vehicles: $9K-$15K/year

### 4.3 General business liability
- ~$500-$2K/year typical for small B2B

### 4.4 Workers' compensation
- **Mandatory in California** for any W-2 employee
- ~$2-5K/year per operator (varies by job class)
- 4 operators: $8K-$20K/year

### 4.5 Cyber / professional liability
- Recommended given customer data handling
- ~$2-5K/year
- Required by some enterprise customers

### Aggregate insurance estimate at 6-vehicle steady state
- Drone liability: $5K
- Vehicle: $15K
- General + cyber: $5K
- Workers' comp: $15K
- **Total: ~$40K/year** — matches the $35K-$40K assumption in
  COST_MODEL_AUDIT.md

---

## 5. Privacy & data — CCPA + handling rules

### 5.1 California Consumer Privacy Act (CCPA)
- Applies if business: (a) has annual gross revenue >$25M, (b) sells data
  on >50K consumers, or (c) gets >50% revenue from sale of personal info
- **Skydock at MVP scale: probably below CCPA threshold** initially
- **At Volume 2+ scale or seed-funded growth: CCPA almost certainly applies**
- Implications:
  - Right to know what's collected
  - Right to delete
  - Right to opt out of sale
  - Privacy policy required
- Cost: ~$5K-$15K to set up CCPA compliance with legal counsel

### 5.2 Recording laws
- California is "two-party consent" for **audio** recording
- **Visual recording in public places is generally legal** (no consent needed)
- **Implication**: our drones should NOT record audio (current product
  doesn't). Visual capture of public intersections is fine.

### 5.3 Face/license plate blurring
- No statutory requirement to blur — but defensive best practice
- Customers will require it for delivered raw video (per our SLA already)
- Cost: included in cloud pipeline processing (~$0.50/scenario in compute)

---

## 6. Data licensing — customer contracts

### 6.1 Master Service Agreement (MSA)
- Drafted with Phase 0/1 startup attorney (~$5-10K)
- Defines: data ownership, licensing terms, IP indemnity, SLA, liability
  caps, termination, payment terms
- **Implication for sales velocity**: have MSA template ready before
  first customer conversation in Phase 3

### 6.2 NDA template
- Mutual NDA for prospect conversations
- Standard, free template from Common Paper or Cooley GO

### 6.3 Insurance indemnification language
- Customers will require us to carry $1M-$2M drone liability + name them
  as additional insured
- Our broker handles the additional-insured paperwork

---

## 7. Phase 0/1 regulatory checklist

Before pre-seed close, get these in place:

| Item | Status | Cost | Owner |
|---|---|---|---|
| Founder Part 107 certificate | Get during Phase 0 | $175 + study time | Founder |
| First drone registration | Phase 2 month 1 | $5 | Founder |
| Delaware C-corp formation | Phase 0 | $100 + attorney $2K | Founder + attorney |
| California foreign filing | Phase 1 | $95 | Attorney |
| Federal EIN | Phase 0 | Free | Founder |
| Commercial drone insurance ($1M) | Phase 1 month 1 | $1,500/year | Founder |
| Commercial vehicle insurance | Phase 2 month 1 (per vehicle) | $1,500-$2,500/year per vehicle | Founder |
| General liability | Phase 1 month 1 | $500-$1K/year | Founder |
| Workers' comp (when first hire) | Phase 1 month 1 | $2-5K/year per employee | Founder |
| CCPA-compliant privacy policy | Phase 1 month 1 | $5K legal | Attorney |
| Customer MSA template | Phase 2 month 4 | $5-10K legal | Attorney |
| LAANC account (Aloft / Skyward) | Phase 2 month 1 | Free | Operator |
| SF Business License | Phase 1 month 1 | $90+/year | Founder |
| Founder employment agreement with deferred comp provision (per Option C) | Phase 0 | $2K legal | Attorney |

**Aggregate Phase 0/1 regulatory + legal cost**: ~$25K-$40K
**Aggregate ongoing annual cost**: ~$45K-$55K (incl. all insurance + licenses)

---

## 8. V2 envelope considerations (post-pre-seed, post-CFP)

These are growth-phase, not required for $2M pre-seed plan:

1. **BVLOS waiver** — 6-12 month process for V2 envelope expansion
2. **Night operations waiver** (Part 107.29) — easier than BVLOS
3. **Operations over people waiver** (Part 107.39) — case-by-case
4. **Moving-vehicle launch waiver** — novel use case, low success probability without strong safety case
5. **FAA Part 108** — proposed BVLOS rulemaking; status uncertain as of 2026,
   may eliminate need for case-by-case waivers if adopted

---

## 9. Implications for existing planning docs

**Critical update needed**:
- **PITCH.md Q27**: "DJI Mini 4 Pro at 249g, sub-250g FAA Remote ID exemption"
  → reframe: "DJI Mini 4 Pro at 249g for low regulatory burden in size class;
  Remote ID compliance built-in to hardware"

**Optional updates**:
- **EXECUTION_PLAN.md Phase 0/1**: incorporate the Phase 0/1 regulatory
  checklist as a specific deliverable list
- **PITCH.md Q13**: add "FAA Part 107 / Federal regulatory" credential to
  the competence section (we'd have founder certified + ops team certified
  by Phase 2)
- **COST_MODEL_AUDIT.md / RAISE_SIZING.md**: insurance line ($35-40K/year)
  already matches this audit — no adjustment needed

---

## Sources

- [FAA Part 107 commercial operators](https://www.faa.gov/uas/commercial_operators)
- [FAA drone registration](https://www.faa.gov/uas/getting_started/register_drone)
- [eCFR Title 14 Part 107](https://www.ecfr.gov/current/title-14/chapter-I/subchapter-F/part-107)
- [HOVERAir Part 107 guide (sub-250g commercial)](https://hoverair.com/blogs/guide/faa-part-107-guide)
- [Drone Nestle license requirements](https://dronenestle.com/what-size-drone-requires-a-license/)
- [California drone laws comprehensive guide](https://drone-laws.com/drone-laws-in-california/)
- [California Drone Launch Academy guide](https://dronelaunchacademy.com/drone-laws-by-state/california/)
- [SF Drone Laws + Park Code §3.09](https://drone-laws.com/drone-laws-in-san-francisco/)
- [SF Film Permit requirements](https://www.sf.gov/information--requirements-film-drone)
- [The Drone Girl SF flying guide](https://www.thedronegirl.com/2025/10/03/flying-drones-in-san-francisco/)
- [Presidio drone operations](https://presidio.gov/about/operating-drones)
- [SkyWatch commercial drone insurance](https://www.skywatch.ai/blog/part-107-commercial-drone-insurance-guide)
- [BWI Drone Insurance](https://bwifly.com/drone-insurance/)
- [California Drone Insurance Requirements](https://www.thebfis.com/insurance-requirements-for-drone-operators-in-california)

---

*v1, May 2026. Update when FAA Part 108 BVLOS rulemaking publishes
(currently in NPRM, status uncertain). Update when first operator is hired
(Phase 2 month 5) to confirm workers' comp class code and rates.*
