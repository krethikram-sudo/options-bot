# Skydock V2 — Outreach Scripts

Four variants tuned to V2 customer cohort (AV safety teams + OEM regulatory safety officers + validation-platform channel partners). Replaces V1 OUTREACH_SCRIPTS.md.

**Universal V2 principles:**
- Subject line ≤ 8 words, no exclamation marks
- First sentence: who you are + the V2 thesis core (independence requirement) in one line
- Specific reference to their public safety case work or NHTSA AV STEP engagement in second sentence
- The ask: 30 min for a closed-loop pilot scoping conversation (longer than V1's 15-min because V2 has a concrete product offer, not a thesis test)
- Close: explicit "free pilot, no commitment, you measure the value on your own held-out eval"
- Never attach a deck on the first message; do attach the V2 thesis one-pager if the conversation gets past the first reply
- Warm intros are 3-4× more valuable than cold reach for V2 (safety teams are guarded against cold outreach but very open to warm intros from investors / AV-Safety conference network)

---

## Variant A — AV safety team (primary V2 cohort)

**Best for:** Head of Safety Case at Waymo / Cruise / Aurora / Zoox / Pony.ai / Wayve / Mobileye / Nuro

**Subject:** Independent validation data for your closed-loop safety case

**Body (~130 words):**

> Hi [Name],
>
> I'm Krethik, founder of Skydock — we operate a fixed-point aerial BEV capture network at high-incident US intersections and deliver a criticality-scored, OpenODD-tagged scenario library to AV safety teams running closed-loop validation.
>
> [SPECIFIC HOOK — one sentence referencing their public safety case work, NHTSA AV STEP submission, or closed-loop sim public position].
>
> The structural problem: synthetic libraries can't serve as independent ground truth in a safety case because they share the generative assumptions of the model being validated. Skydock fills that gap with real captures from sensor systems independent of your vehicle stack.
>
> 30 minutes to scope a free 30-day closed-loop pilot:
> - You specify a Bay Area intersection
> - We deliver 100 criticality-scored scenarios in OpenSCENARIO 2.0
> - You measure collision-rate change on your held-out eval
> - Pre-agreed Phase 1 success criteria (we draft jointly)
>
> If the criteria are met, conversion to annual Library subscription ($100K-$500K depending on tier). If not, you keep the 100 scenarios as a free permanent license. Honest pilot.
>
> Thanks,
> Krethik

---

## Variant B — OEM regulatory safety officer (secondary V2 cohort)

**Best for:** Director of Regulatory Safety / Director of AV Safety Engineering at GM / Ford / Toyota / Mercedes / Stellantis / Hyundai-Kia

**Subject:** Validation evidence for NHTSA AV STEP / EU AI Act submission

**Body (~125 words):**

> Hi [Name],
>
> I'm Krethik, founder of Skydock. We provide validation-grade aerial BEV scenario libraries to AV safety teams preparing NHTSA AV STEP, EU AI Act, and UK CCAV safety-case submissions.
>
> [SPECIFIC HOOK — reference their company's public position on AV safety case / NHTSA engagement / EU compliance roadmap].
>
> The submission frameworks increasingly require *independent* validation evidence. Synthetic data fails the independence requirement by construction (the model trained on the same generative assumptions). Skydock is real overhead capture from fixed-point sites independent of any AV stack, criticality-scored through a 5-signal curation pipeline, indexed against your OpenODD coverage model.
>
> 30 minutes to walk through how this fits your safety case evidence structure:
> - Are you preparing for AV STEP voluntary participation? On what timeline?
> - What independent validation data is your safety case team assembling now?
> - Would a free 30-day closed-loop pilot at one Bay Area intersection — Skydock delivers 100 criticality-scored scenarios, you measure collision-rate change on your held-out eval — be useful evidence in your submission package?
>
> No pitch on the first call, just safety-case context.
>
> Thanks,
> Krethik

---

## Variant C — Validation-platform partner channel

**Best for:** Foretify / Applied Intuition Validation Toolset / Parallel Domain / Cognata partnership leads

**Critical framing:** Position as channel partnership and integration discussion, not direct competition. Their tools are where our library gets queried; we're the data source, they're the workflow integration.

**Subject:** Skydock validation library — partnership integration

**Body (~120 words):**

> Hi [Name],
>
> I'm Krethik, founder of Skydock. We operate a fixed-point aerial BEV capture network and deliver a criticality-scored validation-grade scenario library to AV safety teams.
>
> [SPECIFIC HOOK — reference their tool's safety-case customer integrations, recent partnership announcements, or scenario library expansion publicly stated].
>
> The library is delivered in OpenSCENARIO 2.0 + OpenLABEL natively. Safety-team subscribers currently integrate via API; partner integration with [Foretify / Applied Intuition Validation Toolset / etc.] would expose the library to your existing scenario-validation workflow.
>
> 30 minutes to discuss:
> 1. Does your current customer base ask for *independent* validation data (as opposed to synthetic-only)? How prominent is the ask?
> 2. Would a Skydock library data source within [your tool] be a partner integration your team would pursue?
> 3. What's the partner motion look like — rev-share, integration fees, co-sell?
>
> I'm explicitly not pitching direct competition — we're the data layer; you're the integration layer. The conversation is about the partnership shape.
>
> Thanks,
> Krethik

---

## Variant D — Warm intro (highest-priority Tier 1A)

**Best for:** Waymo / Cruise / Aurora / Zoox safety case leads where investor network or AV-Safety conference contacts open a warm channel

**Use:** Reach out to the warm-intro source first. Give them this template + Skydock one-pager. Let the source forward.

**Subject (forwarded):** Intro — Krethik @ Skydock — closed-loop validation library

**Body (~90 words, written for source to forward):**

> [Name],
>
> Wanted to intro you to Krethik, founder of Skydock. He's building a validation-grade aerial BEV scenario library for AV safety teams — fixed-point capture from high-incident US intersections, criticality-scored through a 5-signal curation pipeline, delivered in OpenSCENARIO 2.0 + OpenLABEL for closed-loop sim integration.
>
> The closed-loop pilot he's offering — free 100 scenarios from a Bay Area intersection of your choice, you measure on your held-out eval, pre-agreed conversion criteria — is structured for safety teams running independence-requirement-aware validation.
>
> Worth 30 minutes? Happy to make the intro.
>
> [Source]

After the intro lands:

> Hi [Name], thanks for connecting via [Source]. 30 minutes to walk through whether the closed-loop pilot structure fits your safety case work would be great. Some times that work this week — [times]. — Krethik

---

## Follow-up sequence

Cadence: **Day 0 → Day 5 → Day 12 → done** (3 touches max). V2 follow-up is slower than V1 because safety-team contacts respond on longer cycles.

### Day 5 follow-up (no response yet)

> Hi [Name],
>
> Quick bump — wanted to make sure my note didn't get buried.
>
> 30 minutes to scope a free closed-loop pilot if independent validation data is on your safety case team's radar. If now isn't a good time, totally understand; happy to circle back next quarter.
>
> Thanks,
> Krethik

### Day 12 follow-up (still no response)

> Hi [Name],
>
> Last note from me on this. If independent validation data isn't relevant to your team's safety case process, a one-line "not for us" would be hugely helpful — falsification is valuable data when you're doing customer discovery.
>
> Either way, appreciate your time.
>
> Krethik

---

## Specific-context customization for top 5 V2 contacts

### → Senior Manager / Director, Safety Case Engineering, Waymo

**Use Variant A.** Specific hook to swap into the bracketed section:

> *"I follow Waymo's AV STEP voluntary participation signaling closely, and your team's published safety case rigor is industry-defining. The closed-loop independent-validation problem keeps coming up in safety-team conversations as the layer synthetic libraries can't quite cover."*

**Why this hook works:** Acknowledges Waymo's leadership without flattering; names the specific problem (closed-loop independent validation) without claiming we've solved Waymo's specific case.

**Send via:** Warm intro through investor network is dramatically higher leverage than cold LinkedIn. Default to warm intro; cold LinkedIn only if no warm path exists.

---

### → Director of Safety Engineering, Cruise

**Use Variant A.** Specific hook:

> *"Cruise's restart safety case is one of the most-watched AV safety processes of 2026. Closed-loop validation library independence requirements seem to be a particular focus for safety teams rebuilding from a public incident."*

**Why this hook works:** Acknowledges the specific Cruise context (restart) and a specific safety-process question (rebuild + independence) without trivializing.

**Send via:** Warm intro priority. Cold LinkedIn backup; the safety case team at Cruise is high-priority and likely guarded.

---

### → VP Safety / Director of Safety Case, Aurora

**Use Variant A.** Specific hook:

> *"Aurora's public commentary on trucking safety case milestones — including the L4 trucking lane-keeping validation independent of the Aurora Driver stack — has me thinking about exactly the independence question Skydock is built to address."*

**Why this hook works:** References Aurora's public trucking-safety-case position, which is specifically about validation independence; ties Skydock's thesis to their stated problem.

**Send via:** LinkedIn cold message is workable here (Aurora is public, smaller comms team). Warm intro through automotive-AV investor network is upside.

---

### → Director of Regulatory Safety, GM (Cruise + post-Cruise AV)

**Use Variant B.** Specific hook:

> *"GM's restructured Cruise / post-Cruise AV roadmap will require a fresh safety case structure for any restart. The NHTSA AV STEP submission framework is where I'd guess your team is anchoring; independent validation evidence is the part of the framework synthetic data structurally can't satisfy."*

**Why this hook works:** Acknowledges the regulatory-safety angle specifically, references the AV STEP framework, and surfaces the independence problem at the level of submission evidence.

**Send via:** Warm intro through automotive-OEM investor network. Cold LinkedIn likely to be intercepted; warm intro through GM Ventures network is higher leverage.

---

### → Head of Partnerships / Channel, Foretify (Foretellix)

**Use Variant C.** Specific hook:

> *"Foretify's Applied Intuition partnership announcement in late 2025 confirms the validation-tooling layer is consolidating around a few platforms. We see Foretify as the workflow layer; Skydock is the validation-grade data layer that subscribers query through Foretify. The partnership shape question is whether co-sell, integration-fee, or rev-share works best for your model."*

**Why this hook works:** Positions Skydock as a partner-not-competitor, references Foretify's specific recent positioning, and gets directly to the partnership-economics question. Disarming and concrete.

**Send via:** LinkedIn message. Foretify is partnership-friendly; warm intro through Foretify investor network is upside but cold is also viable.

---

## V2-specific outreach principles

Three things that work differently for V2 outreach vs V1:

### 1. Lead with the structural argument, not the product

V1 outreach led with "we capture aerial BEV." V2 leads with **"synthetic libraries can't serve as independent ground truth in a safety case."** The structural argument is what gets safety-team attention because they already know the problem; they don't know there's a vendor focused on solving it.

### 2. Pitch the pilot, not the library

V1 outreach asked for 15 minutes of thesis validation. V2 asks for 30 minutes to scope **a concrete free 30-day closed-loop pilot.** The conversation shape is "let's scope a pilot" not "let me learn about your pain." This converts faster but requires a tighter customer fit upfront — don't pitch the pilot to a team that doesn't have closed-loop sim already.

### 3. Honest non-conversion fallback

V2 pilot is structured so the customer walks away with 100 free criticality-scored scenarios as a permanent license, regardless of Phase 1 outcome. This is the conversion-credibility move: customers don't believe a "free pilot" unless the failure-mode economics are also clear. Stating this explicitly in the first outreach message ("If the criteria aren't met, you keep the 100 scenarios as a free permanent license") removes the customer's "what's the catch?" concern.

---

*v1 (V2 outreach scripts), June 2026. Replaces V1 OUTREACH_SCRIPTS.md. Customer cohort + thesis + conversion mechanism all refocused. Track response rates per variant in the first 8 weeks; iterate based on what gets safety-team and OEM-regulatory replies vs cold ignores.*
