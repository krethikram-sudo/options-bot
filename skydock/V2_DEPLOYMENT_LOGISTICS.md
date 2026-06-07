# V2 deployment logistics — Model A, B, C operational appendix

Internal. Operational deep dive on each of the three V2 deployment
models (rooftop, tethered, drone-in-a-box). Companion to
SKYDOCK_V2_THESIS.md and V2_EXECUTION_PLAN.md. Covers hardware stacks,
site selection, partner negotiation, install + commissioning, failure
modes + maintenance, and regulatory specifics.

**Status (June 2026):** Replaces the high-level model summaries in
V2_THESIS.md with the operational detail an execution-stage operator
needs. Two findings from this analysis flowed back into other docs:
(a) Model A site-availability is a real scale limiter beyond dense
urban cores; (b) realistic Model A rooftop rent is materially higher
than V2_FINANCIAL_MODEL.md initially assumed. See "Site availability
and landlord economics" section.

---

## Model A — Rooftop installation

### Hardware stack

| Component | Spec | Cost |
|---|---|---|
| Camera (4K fixed dome, ~80° HFOV) | Axis P3367-V or Hikvision DS-2CD7A85G0-IZS | $1.5-2.5K |
| Camera (8K premium sites) | Sony IMX-based industrial 8K | $5-8K |
| Edge compute | Jetson Orin Nano 8GB or Orin NX 16GB | $0.5-1K |
| Cellular modem + antenna | Cradlepoint IBR900 (enterprise) or Peplink BR1 | $0.5-1.5K |
| Power + surge protection | PoE+ injector or AC tap | $0.2-0.4K |
| NEMA 4X enclosure + active cooling | Weatherproof + thermally managed | $0.5-1K |
| Mount + cabling + anti-tamper | Non-penetrating parapet or pole | $1-2.5K |
| Install labor | Licensed electrician + contractor | $2-4K |
| **Total per-site capex** | | **$15-25K** |

Fixed-wide beats PTZ for BEV capture (no moving parts, static
calibration, consistent geometry). Edge compute runs YOLOv8 + ByteTrack
on-device so the cellular uplink carries metadata + compressed clips,
not raw 4K firehose.

### Site selection criteria

- **Building height:** 4-15 stories (~12-46m). Lower = limited
  coverage; higher = pixels-per-agent below detection threshold at the
  intersection plane
- **Line of sight:** clean view to target intersection — no parapet,
  HVAC, billboard, or sign occlusion
- **Power:** nearby electrical room with available 120V circuit, or
  conduit run feasible without roof-membrane penetration
- **Cell coverage:** actual signal strength on the rooftop (elevation
  sometimes hurts signal from low-elevation tower sites)
- **Roof access:** stair access > ladder-only; single landlord >
  HOA/condo board; office building > residential
- **Structural:** non-penetrating mount under landlord's allowed
  attachment limits (typically <50 lb total)

### Capture geometry

Model A captures **elevated-side overhead from rooftop heights** — NOT
true 80m AGL aerial BEV. From a building 30-60m tall, 30m horizontally
offset from the intersection center, the camera looks down at roughly
55-72° from horizontal. This captures a full signalized intersection
but with edge perspective distortion at the intersection's far side.

Customers should treat Model A captures as a different SKU from Model
B/C true-overhead captures. Metadata tags `deployment_model: A` to let
QA filter accordingly. The capture quality bar (≥70 score) is the same;
the geometry signature differs.

### Partner negotiation

**Target building hierarchy by tractability:**

1. **Class B office buildings, single corporate landlord, vacant
   rooftop.** 30-60 day negotiation cycles. Primary V2 target.
2. **Parking structures** (city or private operator-owned). Less HVAC
   clutter but lower elevation; geometry tighter.
3. **Transit-adjacent mixed-use** (BART, Caltrain stations) — owners
   often receptive to civic-tech framing.
4. **Industrial/warehouse on arterials** — fewer aesthetic concerns;
   simpler owners.
5. **Hotels** — possible but resistant on view-quality optics.

**Standard rooftop agreement terms:**

- **Term:** 3-5 years with auto-renewal; successor-landlord binding
  clause is essential (building sales are a real risk)
- **Monthly fee:** $300-500 standard ($3.6-6K/yr), $500-1,500 premium
  intersections ($6-18K/yr) — see landlord economics section
- **Liability:** landlord typically demands $1-2M general liability +
  waiver
- **Privacy clause:** increasingly common in CA; preempt with AB 856 /
  CCPA / no-PII language
- **Termination:** 90-180 day notice on either side; tenant-improvement
  removal language for equipment

**Recurring landlord objections + responses:**

| Objection | Response |
|---|---|
| "Is this surveillance?" | No PII retention, anonymized agent tracks, AV-safety-validation use case documented in master license |
| "Will this conflict with my existing cell tower lease?" | Cameras coexist with T-Mobile/AT&T rooftop antennas; positioning matters but no RF interference |
| "Will it look bad?" | Renderings ready, low-profile NEMA enclosure, paint-to-match available |
| "What if my building sells?" | Successor-landlord clause in lease; we provide indemnification |

### Install + commissioning

- **Pre-install survey:** 1-2 hours, founder + electrician. Document
  mount location, power tap, line of sight, cellular signal strength
- **Permits:** most cities allow without separate permit if
  non-penetrating + <50 lb + no new exterior conduit. SF requires
  permit if new exterior conduit (~30-60 day cycle)
- **Install crew:** 1 licensed electrician (any new circuit) + 1
  contractor (physical mount). Half-day job, ~4-6 hours
- **Commissioning:** power + cellular uplink + video feed + agent
  tracking + OpenLABEL ingestion, ~2-4 hours, same day as install
- **Total time-to-first-capture:** **6-12 weeks** from "yes" on partner
  negotiation to first capture

### Failure modes + maintenance

| Failure mode | Frequency | Mitigation |
|---|---|---|
| Lens fouling (dust, birds, snow) | Quarterly | Cleaning visits ~$200-400 per |
| Cellular outage | 0.5-2 hr/month | Redundant carriers via SIM swap (budget option) |
| Building power outage | Variable | UPS bridges 1-4 hours; longer outages = capture gap (documented in uptime) |
| Compute crash / OOM | Rare | Remote restart via Cradlepoint OOB management |
| Physical tampering / vandalism | Low | Anti-tamper enclosure; insurance covers replacement |
| Building owner sells | Real risk | Successor-landlord lease clause + 6-month notice |

**Annual maintenance budget: $1-3K per site.** Mean uptime target ≥95%.

### Regulatory

- **NOT a drone deployment** — Part 107 doesn't apply
- **California privacy:**
  - AB 856 (anti-paparazzi): narrow scope for commercial AV but
    documentation matters
  - CCPA: covered by deidentification + no PII retention
  - Civil Code §1708.8: aerial surveillance for personal purposes;
    commercial use case is different category
  - SF Chapter 19B (surveillance technology ordinance): use case
    characterization matters — we're data infrastructure not police
    surveillance
- **Insurance:** $1-3K/yr per site through SkyWatch or Hiscox ($1M
  general liability)

---

## Model B — Tethered drone

### Hardware stack

| Component | Options | Cost |
|---|---|---|
| Drone + tether system bundle | Elistair Orion 2 + Safe-T 2 (industry standard) | $30-50K |
| | Hoverfly Tethered LiveSky (US-made, military-grade) | ~$40K |
| | Easy Aerial Albatross (longer-duration ops) | $50-60K |
| Tether station (ground unit) | AC mains tap, tether reel, autonomous launch/recover, mast | Bundled with drone |
| Camera payload | Sony A7-class or Phase One iXM gimbal-stabilized 4K/8K | Bundled or +$5-10K swap |
| Edge compute (in ground station, preferred) | Industrial PC + GPU | Bundled |
| Cellular | Cradlepoint from ground station | $1.5K |
| **Total per-site capex** | | **$40-65K** |

V2 financial model baseline of $40K is achievable with Elistair
entry-tier configuration.

### Site selection criteria

- **Ground footprint:** ~10ft × 10ft for tether station; cannot be
  public sidewalk
- **Vertical clearance:** 50-150m AGL (165-500ft) with NO overhead
  power lines, flight paths, or wind-shadow from nearby tall buildings
- **Structural anchor:** flat stable surface, bolted concrete pad;
  rooftop ground stations possible with structural review
- **Power:** 1-2kW continuous draw → dedicated 240V/30A circuit or
  robust 120V/20A
- **VLOS:** operator physically present (see operator dependency below)
- **Airspace:** tethered exempt from Remote ID + simplified
  registration, but NOT exempt from LAANC. Most Bay Area urban
  intersections are Class B (within 30nm of SFO/OAK/SJC); LAANC
  authorization required for >200ft AGL ops

### Capture geometry

Model B captures **true aerial 50-150m AGL** — the geometry that
makes highD/inD/openDD work. Closer to V2 customer-facing claim of
aerial BEV than Model A.

### Partner negotiation — different host shape from Model A

Tethered drones can't sit on rooftops cleanly (need ground footprint +
open airspace above). Host hierarchy:

1. **Parking lots adjacent to high-incident intersections** — flat
   surface, edge space, owner-host. Partner: parking operator.
2. **Plazas / hardscape in mixed-use developments** — partner: property
   manager.
3. **Vacant lots / underutilized commercial land** — partner:
   landowner. Cheap but zoning risk.
4. **City-owned land** (parks/plazas) — partner: city Parks/Rec. Slow
   but potentially fee-free with civic-data framing.
5. **Gas stations / fast-food at busy intersections** — partner:
   franchise operator. Hard — parking conflicts.

**Negotiation timeline:** 60-120 days private; 6-12+ months municipal.

### Operator dependency — the economic make-or-break

Part 107 VLOS requires an operator physically present and watching the
drone during operation. Three resolution paths:

| Path | Cost per site | V2 plan compatibility |
|---|---|---|
| Dedicated per-site operator | $60-90K/yr loaded | Kills Model B economics; per-site cost balloons to $80-110K/yr |
| Shared operator across 2-3 geographically clustered sites | $25-40K/yr allocation | Workable for Bay Area cluster; better than dedicated |
| BVLOS waiver (eliminates VLOS) | ~$0 marginal | **Required for V2's $19K/yr per-site Model B economics** |

V2 plan files BVLOS waiver M1; Model B first deploy M16-M18 — explicitly
conditional on waiver progress at M9-M12.

### Install + commissioning

- More involved pre-install survey: airspace clearance + structural
  anchor review + 240V electrical assessment
- LAANC application: 24-72 hr standard airspace; longer for controlled
  facility ops near airports
- Install crew: drone tech + electrician + structural specialist if
  anchored. 1-2 days
- Commissioning: drone test flights, tether tension verification,
  autonomous launch/recover validation, ground station compute +
  uplink test. 2-3 days
- **Total time-to-first-capture:** **12-20 weeks**

### Failure modes + maintenance

| Failure mode | Severity | Mitigation |
|---|---|---|
| Tether kink/break | Catastrophic (drone falls) | Quality tether + failsafe auto-land on tension loss |
| Wind >25 mph | Capture pause | Operating envelope documented; metadata-tagged |
| Bird strike | Drone loss | Insurance covers; redundant fleet |
| Cable degradation (1000-3000 hr life) | Capture pause for swap | Preventive replacement at 70% rated life |
| Ground station compute/power | Same as Model A | UPS + OOB management |

**Annual maintenance: $5-10K per site.** Plus drone wear/replacement
~$3-5K/yr amortized.

### Regulatory

- Tethered drones don't need Remote ID; drone still needs Part 107
  commercial certificate; operator still needs Part 107 license
- LAANC airspace authorization required for controlled airspace
- Weather minimums (3sm vis, 500ft below clouds) still apply
- **BVLOS waiver pursuit:** single biggest regulatory gate. Filed M1,
  expected resolution M9-M12. Approval rates have improved with Part
  108 progress but uncertain.
- **Privacy:** tethered capture at 50-150m AGL is closer to AB 856 /
  §1708.8 territory than rooftop cameras; documentation matters more.

---

## Model C — Drone-in-a-box

### Hardware stack

| Component | Options | Cost |
|---|---|---|
| Drone-in-a-box system | **DJI Dock 2 + Matrice 3D** ($15-20K dock + $5K drone) — NOT recommended (DJI commercial restrictions tightening; customer sourcing policy objections) | n/a |
| | **Skydio Dock 2 + X10** — recommended; US-made, defense-grade, mature autopilot | ~$40K complete |
| | **Percepto AIM** — industrial inspection focused; overkill for AV scenario capture | $80-150K |
| | **Easy Aerial SAMS** — US-made, military-adjacent | $60-80K |
| Cellular (bundled with dock) | LTE Cat-12 | $1-2K |
| Power + UPS | 120V/15A constant (200W idle, 500W charging) + graceful shutdown UPS | $0.5-1K |
| **Total per-site capex** | | **$50-80K** |

Skydio bundle lands ~$45-55K + install + UPS. V2 financial baseline of
$50-80K reflects vendor + install + tax-and-fees range.

### Site selection criteria

Closer to Model B than Model A: ground footprint (4ft × 4ft for dock +
30-50ft clear takeoff/landing zone above), vertical clearance for flight
path, dedicated power circuit, robust cellular. **Plus a defined
emergency landing zone within the operating area** — required by BVLOS
waiver conditions.

**Best site type:** parking structure rooftops — combines elevated
capture geometry with ground footprint for dock. Best of Model A and B
worlds.

### Capture geometry

True aerial 50-100m AGL — same geometry category as Model B.

### Partner negotiation

Similar to Model B (ground footprint), 60-120 days private partner
cycle, longer for municipal. Parking structure operators (Impark, ABM,
Diamond Parking) are the primary V2 target host for Phoenix and Austin
scale-up.

### Operator role — the V2 thesis on Model C

With BVLOS waiver, one operator supervises multiple sites remotely from
a central control room. Skydio enterprise integration enables remote
supervisory ops out of the box. Per-site operator cost approaches zero
at scale, vs Model B's $25-40K/yr/site (without waiver) or Model A's
no-operator floor.

### Continuous capture potential

With 24/7 ops permission + battery rotation + auto launch/recover,
Model C captures continuously through the regulatory envelope. ~3× the
raw scenario candidate volume of Model A (limited to daylight) per
site-month.

### Install + commissioning

- BVLOS waiver application (filed M1) is the gating regulatory item
- Pre-install: standard site assessment + BVLOS-waiver-driven
  operational risk assessment
- Skydio-authorized installer + electrician, 1-day install
- Vendor-supported test flights + integration with Skydock curation
  pipeline. 2-3 days commissioning
- **Total time-to-first-capture:** **18-30 weeks** (assuming waiver in
  hand — without waiver, deployment paused)

### Failure modes + maintenance

| Failure mode | Severity | Mitigation |
|---|---|---|
| In-flight failure (drone fails return-to-dock) | High | Emergency landing protocols; insurance covers loss + third-party damage |
| Dock mechanical (battery swap mechanism) | Medium | Vendor service contract; downtime 2-4 days |
| Drone wear | Medium | Preventive maintenance every 3-6 months |
| Bird strikes / collisions | Medium | More frequent than Models A/B (more flights/day); insurance covers |
| Weather lockouts | Low | Auto-cancel missions; capture gaps tagged in metadata |

**Annual maintenance + vendor support contract: $8-15K per site.**
Drone replacement amortized: $5-10K every 18-24 months. **Vendor
service contract essential** — no Skydio dock without support contract.

### Regulatory

- **BVLOS waiver** = single largest gate; without waiver, Model C is
  non-operational
- Remote ID required (drone >250g, commercial)
- Ongoing ATC coordination for any Class B/C/D ops
- **Phoenix and Austin scale-up rationale:** AZ and TX have historically
  had more permissive regulatory environments and faster BVLOS approval
  rates than CA
- **Privacy:** highest scrutiny of three models; community notice +
  deidentification rigor matter most

---

## Site availability and landlord economics (the V2 scale limiter)

### Model A site availability by geography

Model A's elevated-side overhead geometry needs a 4-15 story building
within ~30m of the target intersection. Building stock varies
dramatically by metro:

| Geography | % high-incident intersections with viable building |
|---|---|
| SF FiDi / SoMa / Mission | ~70-85% |
| Oakland downtown | ~60-70% |
| San Jose downtown | ~55-65% |
| South Bay tech corridor (Sunnyvale, MV, Cupertino, Santa Clara) | ~30-45% |
| Peninsula suburbs (San Mateo, Burlingame, Redwood City) | ~25-40% |
| East Bay suburbs (Walnut Creek, Concord) | ~30-50% |
| **Phoenix downtown** | **~35-50%** (lower-rise) |
| **Phoenix suburbs** | **~15-30%** |
| **Austin downtown** | **~40-55%** |
| **Austin suburbs** | **~20-35%** |

**Implications:**

1. **Bay Area V2 plan (5 sites by M12) is achievable.** Concentrating
   on SF + Oakland + SJ urban cores gets us 30-40 candidate
   intersections; landlord conversion of 30-50% gives 9-20 viable
   sites. Tractable.

2. **Phoenix and Austin scale-up post-seed will hit Model A
   site-availability ceiling fast.** Lower-rise downtowns mean fewer
   intersections have a suitable rooftop. By year 3 target (15 sites)
   and year 5 (20+), Model A alone cannot scale.

3. **Models B and C are the structural answers to Model A's site
   ceiling**, not just deployment-option variants. Model B uses ground
   footprint (parking lots, plazas, city land) — doesn't depend on
   rooftop availability. Model C similarly uses parking structure
   rooftops + ground sites. Three-model portfolio is essential, not
   optional.

### Landlord economics

V2_FINANCIAL_MODEL.md initially assumed $1K/yr (~$80/mo) rooftop rental
per site. This is unrealistic.

**Industry rooftop attachment comparables:**

| Comparable | Monthly fee | Context |
|---|---|---|
| T-Mobile rooftop cell tower (major metro) | $1,500-3,500 | Large footprint, high RF revenue |
| Verizon small-cell | $300-1,000 | Mid-size footprint |
| ISP small-cell mount | $200-500 | Small footprint |
| HD radio antenna | $100-300 | Smallest footprint |
| **Skydock Model A camera + enclosure** | **realistic $300-500** | Small footprint, civic-tech framing |

Our installation footprint is much smaller than a cell tower, but
landlords will use cell-tower rates as a negotiating reference. We
shouldn't be paying cell-tower rates; we shouldn't be paying $0 either.

**Realistic Model A monthly rent by site type:**

- Standard Class B office + civic-tech framing + indemnification:
  **$300-500/mo ($3.6-6K/yr)**
- Premium location at a marquee high-incident intersection:
  $500-1,500/mo ($6-18K/yr)
- City-owned building or transit-adjacent with civic mission framing:
  $0-200/mo (real path; longer cycle but scales differently)
- Truly resistant private owner: pass entirely, find another building

**V2 financial model rent assumption update:** $1K/yr → **$5K/yr per
Model A site** (~$415/mo midpoint). This shifts Model A operating cost
from $9K/yr to $13K/yr (44% jump), per-delivered-scenario cost from
$2.00 to ~$2.67. Still 30× better than V1's $87 and still well within
unit economics that close at scale. No material change to the $2.2M
raise sizing (~$15K extra cost over 18 months at 5 Model A sites).

### Negotiation levers beyond cash

What we can offer landlords to keep cash compensation as low as possible:

- **Insurance + full indemnification** — net-zero risk to landlord
- **Civic-tech framing** — helps Class A office owners with ESG
  storytelling; "Skydock data is used by AV safety teams to close
  closed-loop validation gates required for production deployment"
- **Brand association** — modest reputational upside for landlords who
  want visibility in the AV-infrastructure space
- **City-owned building partnerships** at $0-200/mo with civic mission
  framing — slower negotiation cycle (city Real Estate / Public Works
  involvement) but materially lower per-site cost when it closes
- **Custom-capture-funded sites** — customers pay $50K-$150K to
  commission Model A sites at intersections they specify; the
  custom-capture revenue absorbs landlord rent above the $5K baseline,
  turning landlord economics from a cost-center constraint into a
  customer-funded option

### V2 plan implications

Three concrete changes flow back to V2_EXECUTION_PLAN.md and
V2_FINANCIAL_MODEL.md:

1. **Pre-pre-seed site pipeline metric:** target 20-30 candidate
   building partners under conversation at pre-seed close. Need 6:1
   ratio to handle landlord conversion losses; gets us to 4-5 viable
   sites for M4-M6 deployment.

2. **M0 deliverable: 3 signed LOIs from Model A building partners
   before pre-seed close.** Reduces M4 first-site-live risk to near
   zero. LOIs don't need to be fully-negotiated leases — non-binding
   intent to host pending pre-seed close, with rent terms agreed in
   principle.

3. **Model B repositioning in seed pitch:** currently framed as
   "higher vantage when needed"; better framing is "structural answer
   to Model A site-availability ceiling — doesn't depend on rooftop
   stock geography." Materially strengthens the seed-round expansion
   story for Phoenix and Austin.

---

## Cross-model comparison

| Dimension | Model A | Model B | Model C |
|---|---|---|---|
| Capex per site | $15-25K | $40-65K | $45-80K |
| Annual operating (excl curation) | $8-13K | $15-25K (with waiver) | $12-20K (with waiver) |
| Time-to-first-capture | 6-12 weeks | 12-20 weeks | 18-30 weeks (+BVLOS) |
| Regulatory complexity | Lowest (fixed camera) | Medium (tethered + LAANC) | Highest (BVLOS waiver) |
| Continuous capture | Daylight only | Daylight + operator hours | Potentially 24/7 (with waiver) |
| Capture geometry | Elevated-side overhead from 30-60m | True aerial 50-150m AGL | True aerial 50-100m AGL |
| Operator dependency | None | Heavy without BVLOS waiver | Light/supervisory with waiver |
| Failure mode severity | Low | Medium | High (autonomous flight) |
| Vendor relationship | Commodity integrate-ourselves | Elistair/Hoverfly bundled | Skydio bundled + support contract |
| Site-availability constraint | High (4-15 story building dependency) | Medium (ground footprint) | Medium (ground footprint + power) |
| V2 plan position | M4-M12 primary | M16-M18 first deploy | Post-seed Phoenix/Austin |

---

## Honest operational observations

1. **Only Model A is regulatory-unconditional.** Models B and C both
   have specific FAA dependencies. Model B economics fall apart without
   BVLOS waiver (operator costs); Model C depends on waiver entirely.
   V2 plan should treat the M16 Model B and post-seed Model C as
   conditional milestones, not commitments.

2. **Only Model A has a structural site-availability ceiling.** Models
   B and C use ground footprint, which is more abundant. This makes
   the three-model portfolio essential, not optional. Model A is the
   pre-seed proof-point; Models B and C are the structural scale
   answers.

3. **Capture geometry varies meaningfully across models.** Model A is
   "elevated-side overhead" from rooftop heights. Models B and C are
   "true aerial" at 50-150m AGL. Metadata tagging by deployment model
   lets customers filter; the capture quality bar (≥70 score) is the
   same.

4. **Site selection criteria differ enough that the V2 site pipeline
   must be modeled separately per type.** Sites that work for Model A
   often don't work for Models B/C (rooftop without ground footprint),
   and vice versa. "5 V2 sites by M12" implies 5 Model A site-type
   negotiations.

5. **Three different vendor relationships.** Model A is "buy commodity
   + integrate ourselves." Model B is "buy bundle from Elistair." Model
   C is "buy from Skydio with service contract." Three different vendor
   escalation patterns, three different price-negotiation dynamics.

6. **Privacy framing escalates with model.** Model A (rooftop fixed
   camera) is lightest. Model B (tethered drone hovering visibly) draws
   community attention. Model C (autonomous drone-in-box launching
   repeatedly) draws the most. Pre-seed budget needs a community-
   relations + privacy-policy line item for Model C deployment.

7. **The BVLOS waiver is the biggest single-variable risk in the V2
   plan.** Affects Model B economics (operator-dependent without it)
   and Model C feasibility (entirely dependent on it). Worth a
   dedicated waiver-pursuit workstream — pre-application consultation
   with the FAA, retain aviation counsel specializing in BVLOS
   waivers, structured operational risk assessment ready for filing M1.

---

*v1, June 2026. Operational appendix to V2_EXECUTION_PLAN.md. Two
findings flowed back into V2_FINANCIAL_MODEL.md (rent assumption
$1K → $5K/yr per Model A site) and V2_EXECUTION_PLAN.md (3 signed LOIs
from building partners as M0 pre-pre-seed deliverable). Re-derive
per-site economics if the rent comparables shift materially based on
early site negotiations.*
