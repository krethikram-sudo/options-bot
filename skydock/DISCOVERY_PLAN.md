# Skydock — Customer discovery plan

**Goal:** Over 4-6 weeks, run 15-20 conversations with named decision-makers at AV companies to validate which of three thesis framings has actual buyer pull. Exit the discovery period with enough evidence to commit to a single thesis and rewrite PITCH.md against it.

**Mode:** Parallel discovery on three theses through the same customer conversations. One outreach, one 30-min conversation per contact, three hypotheses tested simultaneously.

---

## The three theses being tested

| ID | Thesis | What we sell | What we'd charge |
|---|---|---|---|
| **A** | **Perception validation** | Independent aerial ground-truth captures the customer compares against their on-vehicle BEV perception output, to find perception failures | $500-$2000 per capture |
| **C** | **Geographic diversity** | Aerial captures in cities where the customer's own AV fleet doesn't operate | $200-$500 per capture |
| **Orig** | **Scenario library data** *(control test)* | Curated aerial scenarios for AV training corpora — the original PITCH.md framing | $200-$400 per scenario |

Each thesis has a different value proposition. The same 30-min conversation can probe all three because they all hit AV engineering teams at the same companies.

---

## Target customer list

Twelve target companies. For each, the role we want to reach and why. The actual person names need to be sourced via LinkedIn; this list gives the search filter.

### Tier 1 — Active perception teams, addressable for pre-seed pilot

| # | Company | Role to target | Why this company |
|---|---|---|---|
| 1 | **Volvo Cars / Zenseact** | Head of Perception (Zenseact), Engineering Team Lead at Volvo perception group | Public investment in scenario-based AI safety; uses Gaussian splatting for corner cases (active perception R&D); collaborates externally with Foretellix-style toolchain |
| 2 | **Nuro** | Director of Perception, founding team member with public perception lineage | Operates a robotaxi pilot; raised $1B+; smaller team than Waymo so external data could be additive |
| 3 | **Aurora Innovation** | Senior Director of Perception, ML Perception leads | Public company; under cost pressure to scale efficiently; perception accuracy directly affects truck-driver replacement timeline |
| 4 | **Pony.ai** | Head of Perception (US team) | Public company since 2024; operates fleets in CA + China; geographic diversity is a real pain |
| 5 | **Wayve** | Head of AV Foundation Models / perception | London-based; UK fleet only; explicit interest in foundation-model + real-data combinations |
| 6 | **Torc Robotics / Daimler Truck** | Head of Perception (Torc) | Foretellix customer (so familiar with external data tools); trucking perception has different geographic requirements |

### Tier 2 — Toolchain / synthetic vendors (potential channel partners)

| # | Company | Role to target | Why this company |
|---|---|---|---|
| 7 | **Applied Intuition** | Director of Aerial Programs (per their Defense product line) OR Director of Scenario Library Engineering | Have drone-stack hiring; could be partner OR competitor; finding out which is the deciding factor |
| 8 | **Foretellix** | Head of Scenario Generation / Head of Real-World Data Integration | Their Foretify platform takes real driving data as input; aerial captures could be a complementary input feed |
| 9 | **Parallel Domain** | Head of Data Lab / Director of Real-World Data | Their Data Lab API generates synthetic from real drive log reconstructions; aerial captures could seed new variants |
| 10 | **Cognata** | Head of Real-World Data Acquisition (DriveMatrix product) | Synthetic from real test-drive data; possible channel partner |

### Tier 3 — Adjacent / harder to reach (defer if Tier 1+2 conversations are productive)

| # | Company | Role to target | Why this company |
|---|---|---|---|
| 11 | **Waymo** | Senior Manager, Perception Validation | Largest budget, but proprietary fleet may eliminate need; useful as a counterfactual benchmark |
| 12 | **Tesla** | Senior Director, Autopilot Perception | Their fleet-data advantage suggests no need, but worth one probe for falsification |

---

## Outreach plan

**Channel preference:** LinkedIn cold message > warm intro (if available via founder network) > email cold.

**Volume / cadence:**
- Week 1: Send 12 outreach messages (one per Tier 1+2 target).
- Week 2: Send 8 follow-ups + 4 new outreach (Tier 3 if Tier 1 lagging).
- Week 3-4: Schedule conversations as responses come in. Expect 30-40% response rate, 50-60% conversation conversion → 4-8 conversations.
- Week 5-6: Second wave of outreach to any tier we didn't fully cover. Aim for 15-20 total conversations by week 6.

**Outreach script (LinkedIn cold message, ~120 words):**

> Subject: 15 min on aerial ground-truth for AV perception validation
>
> Hi [Name],
>
> I'm building Skydock — a vehicle-mounted drone platform that captures aerial ground-truth data at the exact locations an AV fleet operates. We're pre-seed; trying to validate whether AV perception teams actually have a "no truly independent ground-truth" pain point worth paying to fix.
>
> Three short questions I'd love 15 minutes on:
> 1. How does your team currently validate your on-vehicle BEV perception against ground truth?
> 2. What's the biggest gap in your perception training data today — geographic coverage, edge case curation, or independent validation?
> 3. Would you ever pay an external vendor for one of those, and what would change to make that a yes?
>
> Happy to share the simulation work we've already done as background. No pitch — just trying to learn whether the pain we think exists actually does.
>
> [Krethik]

**Variations:**
- For toolchain/synthetic vendors (Applied Intuition, Foretellix, etc.): replace Q1 with "Could real aerial captures feed your existing synthetic pipelines as inputs?"
- For warm-intro path: shorten by half; lead with the intro source's name.

---

## Conversation guide

**30-minute structure**:

```
0:00-3:00     Their context: role, team size, current data approach
3:00-10:00    Their pain: what's missing today? (open-ended; let them lead)
10:00-18:00   Thesis-specific probes (see below)
18:00-25:00   Pricing + procurement: would they pay? how much? what process?
25:00-30:00   Close: thank, ask for one referral, confirm follow-up
```

**Thesis-specific probes (the meat of the conversation):**

### Probe set A — Perception validation

1. "How do you currently validate the accuracy of your on-vehicle BEV perception output? Self-collected ground truth, simulator, or something else?"
2. "Are you confident your validation methodology is truly independent of the model you're validating? Or is there a sensor-stack contamination concern?"
3. "If you could get an independent aerial overhead capture at the exact location your fleet hits a perception failure, would that be valuable? How valuable?"
4. "What's a perception-validation budget line item look like in your org? Do you have one?"

### Probe set C — Geographic diversity

5. "Where does your fleet operate? Where do you wish it operated for training-data purposes?"
6. "How do you currently get data from cities you don't have a fleet in? Synthetic? Public datasets? Partnerships?"
7. "If you could buy real aerial captures from any city in the US, would you? Which cities? At what price?"

### Probe set Orig — Scenario library

8. "Do you maintain a scenario library (internal or external)? Roughly how many scenarios in it?"
9. "Is aerial-perspective coverage a real gap in that library, or do other gaps matter more?"
10. "Would you procure aerial scenarios as a category from a vendor, or only as inputs to synthetic generation?"

### Universal closing probes

11. "If we hypothetically delivered a sample of [whatever they said they wanted], what would you do with it? Who would review?"
12. "Who else on your team or in the industry should I be talking to?"

---

## Scoring rubric

Score each conversation against each thesis on a 0-3 scale per criterion:

| Criterion | 0 | 1 | 2 | 3 |
|---|---|---|---|---|
| **Pain magnitude** | "We don't have this problem" | "Minor inconvenience" | "Real pain, but we've worked around it" | "Top 3 problem on my list" |
| **Willingness to pay** | "Wouldn't buy" | "Maybe at very low price" | "Yes at price X subject to quality" | "Yes, and I have budget to spend now" |
| **Procurement tractability** | "Procurement process would kill it" | "Possible but takes 12+ months" | "Tractable, 6-9 month cycle" | "I can sign a pilot agreement today" |
| **Volume potential** | "<10 captures/year" | "10-100" | "100-500" | "500+ at scale" |

**Theses scoring**:
- A thesis with **mean score ≥ 8/12 across 5+ conversations** = validated, commit to it.
- A thesis with **mean ≤ 4/12** = killed, drop it.
- Anything in between = unclear; either run more conversations or pick the best of the inconclusive.

---

## Decision framework at week 6

Three scenarios likely after the discovery period:

**Scenario 1: One thesis clearly wins (e.g. A scores 9, C scores 5, Orig scores 4).**
→ Commit to A. Rewrite PITCH.md to A's framing. Begin pilot conversations with the 2-3 hottest conversations.

**Scenario 2: Two theses tie (e.g. A scores 8, C scores 7).**
→ Pick whichever has the larger named-customer pull. If still tied, run 5 more focused conversations against the tiebreaker thesis only.

**Scenario 3: All three score ≤ 5.**
→ The wedge is not in AV-on-roads at the OEM/robotaxi layer. Time to step back further — interrogate whether the AV-on-roads constraint itself is the problem, or whether the customer cohort needs to expand beyond §4.1.

---

## Operational checklist

**Week 0 (this week):**
- [ ] Source named LinkedIn contacts for 12 target roles (5-7 hours)
- [ ] Draft 4 outreach script variations (perception team, toolchain vendor, OEM eng. lead, warm intro)
- [ ] Set up a tracking spreadsheet (target / contact / status / score)
- [ ] Build the 30-min conversation guide doc to use live

**Week 1:**
- [ ] Send 12 outreach messages
- [ ] Track responses; respond within 24h
- [ ] Schedule first 3-4 conversations

**Week 2-4:**
- [ ] Run conversations (2-4 per week)
- [ ] Score each conversation within 24h of completion against the rubric
- [ ] Update a running thesis-scoring tracker
- [ ] Send follow-up notes within 48h thanking + recapping
- [ ] Ask each conversation for 1 referral

**Week 5-6:**
- [ ] Final wave of outreach to any tier not yet covered
- [ ] Synthesise findings into a discovery-results memo
- [ ] Decision meeting: pick the thesis
- [ ] Rewrite PITCH.md to the chosen thesis
- [ ] Update the PR-FAQ Appendix B with real conversation summary

---

## What I (Claude) can vs cannot help with

**I can help with:**
- Drafting and iterating outreach script variations
- Sourcing additional target companies / roles via web research
- Building the tracking spreadsheet template
- Synthesising conversation notes into the discovery memo
- Rewriting PITCH.md once the thesis is chosen
- Drafting follow-up emails

**I cannot help with:**
- Sourcing actual LinkedIn profiles / email addresses (requires LinkedIn auth)
- Sending the messages
- Conducting the conversations (these need to be founder-led for credibility)
- Generating warm intros (no graph data)

The cold start is fully on the founder. After that, I can be the analyst.

---

## Confidence checks for me

Before you start outreach, sanity-check three assumptions I'm making:

1. **The conversations are credible if I'm cold-emailing pre-seed?** Many AV decision-makers will respond to a founder doing customer discovery — it's the standard pattern. But if you have a network advantage (warm intros via investors, alumni connections, AV-Sim conference contacts), use it first.

2. **Volvo / Aurora / Pony.ai are reachable as a solo pre-seed founder?** They are. Heads of Perception at public AV companies regularly take customer-discovery calls. They're not Tier-1 VCs guarding their time; they're engineering leaders who actively want to know what's being built in their space.

3. **6 weeks is enough time?** It's tight but doable. 15-20 conversations at 2-3/week is sustainable founder bandwidth. If you have other commitments competing, extend to 8 weeks.

---

*Customer discovery plan v1. Compiled May 2026 based on RESEARCH_LOG.md and THESIS_REVIEW.md findings. Update after each conversation; revise the plan if response rates or response content suggest a different approach.*
