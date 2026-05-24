# Skydock — Customer Discovery Contact List

**Compiled May 2026.** Names and roles sourced via web search of public LinkedIn / company / news content. **Verify each name is still in their current role on LinkedIn before outreach** — these snapshots are point-in-time and people move.

Each contact is annotated with a suggested outreach approach. Many companies have multiple plausible target roles; I've listed the primary contact and 1-2 backups for each.

---

## Tier 1 — Active AV perception teams (primary outreach targets)

### 1. Volvo Cars / Zenseact

**Primary contact:** Erik Rosén
**Role:** Senior Director of AI & Perception, Zenseact
**Background:** Previously Chief AI Officer and Chief Architect at Zenseact/Zenuity; led Automated Driving & Preventive Safety at Autoliv research; PhD in superstring theory (Chalmers 2006). Eight years in statistical accident research.
**Why him:** Senior, technical, directly responsible for perception architecture. Zenseact is the autonomy arm spun out of Volvo+Veoneer.
**LinkedIn search:** `Erik Rosén Zenseact` — confirm via RocketReach reference. Profile id appears to be visible publicly.
**Backup:** Maryam Fatemi (Zenseact AI/perception); Ognjan Hedberg (Zenseact engineer).
**Outreach angle:** Lead with "I noticed Zenseact's recent work on Gaussian splatting for corner-case scenario generation — curious how you currently validate perception against ground truth at the locations your fleet operates."

### 2. Nuro

**Primary contact:** Tilo Schwarz
**Role:** VP of Engineering, Nuro Driver
**LinkedIn:** linkedin.com/in/tilo-schwarz-42289b166/
**Why him:** Heads the Nuro Driver (AV stack) engineering, including perception. Recently presented at Traffic Safety Summit. More approachable than CTO-level.
**Backup:** Andrew Clare (CTO); Dave Ferguson (co-founder, ex-Google Streetview/Waymo perception).
**Outreach angle:** "Saw Nuro received the Nevada driverless permit ahead of the Uber robotaxi launch — congratulations. I'm researching how perception teams validate BEV models against truly independent ground truth, would love 15 min."

### 3. Aurora Innovation

**Primary contact:** Drew Bagnell
**Role:** Co-founder, Chief Scientist (was Uber ATG Head of Perception)
**LinkedIn:** linkedin.com/in/drew-bagnell — confirm
**Why him:** Co-founder, deep perception lineage. **Probably too senior for a cold ask** — use as referral source or only if you have a warm intro.
**Better backup:** Search Aurora's LinkedIn for "Director of Perception" or "Director of Engineering, Perception" — those are the right level for a 30-min discovery call. Aurora currently has open roles for "3D Technical Director, Perception Simulation" (per LinkedIn) — same team, different role title to search around.
**Outreach angle:** Aurora is the most likely to be ambivalent about external data (they have a robust internal fleet). Lead with the question rather than the pitch: "How do you currently validate the accuracy of your on-vehicle perception against independent ground truth?"

### 4. Pony.ai

**Primary contact:** Dr. Yimeng Zhang
**Role:** VP of Engineering, U.S. Site Lead (Fremont office)
**LinkedIn:** linkedin.com/in/yimeng-zhang-04144127/
**Background:** Recently joined Uber AV Labs as Senior Director.
**Note:** She may have moved from Pony.ai to Uber recently — **verify current employer on LinkedIn before outreach**. If at Uber AV Labs, she's still a strong contact for a different framing.
**Backup at Pony.ai:** Dr. Tiancheng Lou (Executive Director & CTO); Ning Zhang (VP, Head of AD System, Beijing).
**Outreach angle:** Pony.ai operates fleets in both California and China — geographic-diversity (Thesis C) probe is especially relevant. "How do you handle scenario coverage for cities your fleet doesn't operate in?"

### 5. Wayve

**Primary contact:** Vijay Badrinarayanan
**Role:** VP of AI
**Background:** Previously led R&D at Magic Leap on power-constrained mixed-reality deep nets. Foundation-model focus at Wayve.
**LinkedIn:** searchable via Wayve's leadership page or `Vijay Badrinarayanan Wayve`.
**Why him:** Wayve is foundation-model-pure; perception is integrated into their end-to-end model rather than a separate module. Their pain may be different ("we need diverse training data," not "we need independent ground truth").
**Backup:** Jamie Shotton (Chief Scientist) — too senior; Aniruddha Kembhavi (Director of Science Strategy).
**Outreach angle:** Wayve specifically may not have a "perception team" with independent-validation pain in the classical sense. Lead with "how does your foundation model approach handle ground-truth diversity?" — let them tell you what their pain actually is.

### 6. Torc Robotics

**Primary contact:** Felix Heide
**Role:** Head of AI, Torc Robotics (also Assistant Professor at Princeton)
**LinkedIn:** linkedin.com/in/felix-heide-7b7bb889/
**Background:** Founded Algolux (perception startup acquired by Torc); Princeton CS faculty; NSF CAREER Award winner; works at intersection of optics, ML, computer vision.
**Why him:** The most academic / public-facing target on the list. Approachable for technical discovery calls because he's also a researcher. Strong perception lineage.
**Backup at Torc:** Boris Sofman *(NOTE: he left Torc and now leads Bedrock Robotics — different company, construction not on-roads)*. Peter Vaughan Schmidt is current CEO.
**Outreach angle:** "Saw your team's CVPR 2024 papers on perception. Curious how Torc validates perception against independent ground truth in a trucking context where the operating envelope is different from passenger vehicles."

---

## Tier 2 — Toolchain / synthetic vendors (channel-partner-or-competitor check)

These conversations test a different question: **would they partner with Skydock as a real-data input source for their synthetic pipelines, or would they build it themselves?**

### 7. Applied Intuition

**Primary contact:** Jason Brown
**Role:** General Manager, Defense (Applied Intuition Defense)
**Why him:** Leads the defense / aerial autonomy product line. They have drone-stack hiring — he's the most likely person to know whether Applied is building its own aerial AV data capability.
**Backup:** Search for "Director of Scenario Library" at Applied Intuition core (non-defense); their leadership page lists Qasar Younis (CEO) and Peter Ludwig (CTO) but those are too senior for a discovery cold ask.
**Outreach angle (sensitive — they may be a competitor):** Don't pitch. Lead with "I'm exploring the aerial-perspective gap in AV training data and noticed Applied Intuition Defense has aerial autonomy products. Would love your perspective on whether AV training data customers actually want aerial captures, or whether synthetic generation handles it."
**Falsification value:** If they say "we're building our own," that's a clear time-window signal. If they say "we'd buy real-data inputs," that's a channel partnership opening.

### 8. Foretellix

**Primary contact:** Ziv Binyamini
**Role:** CEO
**Note:** CEO is usually too senior for first contact, but at ~140 employees, founders are still accessible. **Better target: search for "Head of Real-World Data" or "Director of Data Engineering" at Foretellix.** Their Foretify platform explicitly takes real driving logs as inputs.
**Backup:** Gianmarco Macaro (Foretellix engineer found in search); Ítalo Andrade (engineer).
**Outreach angle:** "Foretify takes real driving logs from your OEM customers as scenario seeds. Would aerial captures from the same locations be a useful complementary input?"

### 9. Parallel Domain

**Primary contact:** Kevin McNamara
**Role:** CEO
**Backup (probably better first contact):** James Grieve, CTO; or search for "Head of Data Lab" / "Director of Real-World Data" — the Data Lab product feeds synthetic from real reconstructions, so there's a real-data team somewhere.
**Outreach angle:** "Data Lab generates synthetic from photorealistic neural reconstructions of drive logs. Would aerial captures at customer-specified locations enhance the input distribution?"
**Falsification value:** If they say "no, we generate from ground-vehicle logs and that's sufficient," Thesis B (synthetic-data input vendor) is dead.

### 10. Cognata

**Primary contact:** Danny Atsmon
**Role:** Founder & CEO
**Background:** Cognata co-founder (with Alon Atsmon — possibly relatives).
**Backup:** Shay Rootman (VP Business Development & Marketing) — the right person if Danny doesn't respond.
**Outreach angle:** "DriveMatrix transforms real test-drive video into synthetic variants. Does your team source the real test-drive video from customers only, or do you ever procure external real captures?"

---

## Tier 3 — Falsification benchmarks (deferred unless Tier 1-2 lagging)

### 11. Waymo

**Search:** "Senior Manager Perception" or "Tech Lead Perception" Waymo. Their proprietary fleet + DeepMind World Model likely eliminates need.
**Outreach value:** As a "no" datapoint, useful for understanding the upper bound of who is unaddressable.
**Outreach angle:** Hardest cold target. Probably skip unless you have warm intro.

### 12. Tesla

**Skip.** Tesla doesn't engage with external data vendors. Fleet-data advantage means they have orders of magnitude more real data than anyone else. Use only as falsification reference, not outreach target.

---

## Outreach tracking template

Copy this into a Google Sheet or Notion table and populate as you go:

| # | Company | Contact | Role | LinkedIn URL | Status | Sent date | Response | Convo date | A score (/12) | C score (/12) | Orig score (/12) | Notes |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 1 | Volvo/Zenseact | Erik Rosén | Sr Dir AI & Perception | TBD | not sent | | | | | | | |
| 2 | Nuro | Tilo Schwarz | VP Eng, Nuro Driver | linkedin.com/in/tilo-schwarz-42289b166/ | not sent | | | | | | | |
| 3 | Aurora | TBD | Director-level Perception | TBD | not sent | | | | | | | |
| 4 | Pony.ai | Yimeng Zhang | VP Eng U.S. (verify current employer) | linkedin.com/in/yimeng-zhang-04144127/ | not sent | | | | | | | |
| 5 | Wayve | Vijay Badrinarayanan | VP of AI | TBD | not sent | | | | | | | |
| 6 | Torc Robotics | Felix Heide | Head of AI | linkedin.com/in/felix-heide-7b7bb889/ | not sent | | | | | | | |
| 7 | Applied Intuition | Jason Brown | GM, Defense | TBD | not sent | | | | | | | |
| 8 | Foretellix | TBD | Head of Real-World Data (search) | TBD | not sent | | | | | | | |
| 9 | Parallel Domain | TBD | Head of Data Lab (search) | TBD | not sent | | | | | | | |
| 10 | Cognata | Danny Atsmon | Founder | TBD | not sent | | | | | | | |
| 11 | Waymo | TBD | Sr Mgr Perception (search) | TBD | not sent | | | | | | | |
| 12 | Tesla | — | (skip) | — | — | | | | | | | |

---

## Quick gut-check on this list

A few things to know about the list as compiled:

1. **All names are point-in-time snapshots from web search.** Anyone could have moved. Verify current employer on LinkedIn before outreach. The most-likely-to-have-moved: Yimeng Zhang (the search returned a mention of moving to Uber AV Labs).

2. **Tier-1 prioritization order I'd suggest:** Felix Heide (most academic/approachable) → Tilo Schwarz (engineering-leader-friendly) → Erik Rosén (senior but technical) → Vijay Badrinarayanan (foundation-model angle is different but interesting) → Yimeng Zhang or Tiancheng Lou (verify Pony.ai vs Uber) → Aurora (need to find right-level contact).

3. **Tier-2 may produce the most useful conversations.** Applied Intuition's Jason Brown is the single highest-information call on the list — he can tell you whether Applied is going to compete with you. That's worth more than 3 OEM "we're not sure" responses.

4. **Don't send all 10 outreaches at once.** Stage them: send 3-4 the first week so you have bandwidth to take the conversations. Refine the script based on responses, then send the rest.

5. **Bedrock Robotics** (Boris Sofman) is *not* on this list because it's construction robotics, off the AV-on-roads thesis. But Sofman's network at Waymo could be valuable for warm intros if you have a path to him.

---

*Contact list v1. Compiled May 2026 via web search of public LinkedIn / company / news content. Update as conversations land.*
