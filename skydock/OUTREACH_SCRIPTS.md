> ⚠ **STALE — V1 OUTREACH POSTURE.** These scripts target perception-
> team decision-makers with V1's mobile-dock thesis. The V2 architecture
> (May 2026) refocused outreach on AV safety teams + OEM regulatory
> safety officers + validation-platform channel partners. Current
> outreach scripts are V2_OUTREACH_SCRIPTS.md. Kept for historical
> context on V1 outreach methodology and specific-context customization
> patterns.

---

# Skydock — Outreach Scripts

Four variants tuned to contact type, plus follow-up sequences and customization examples for the top 3 priority contacts.

**Universal principles:**
- Subject line ≤ 7 words, no exclamation marks
- First sentence: who you are + why you're reaching out, in one line
- Specific reference to their work in second sentence (proves you're not mass-spamming)
- The ask: 15 min, not 30. Easier "yes."
- Close: explicit "no pitch — just trying to learn"
- Never attach a deck on the first message

---

## Variant A — Technical engineering leader

**Best for:** Felix Heide (Torc), Tilo Schwarz (Nuro), Vijay Badrinarayanan (Wayve), Director-level Aurora contact.

**Subject:** Aerial ground-truth for AV perception validation

**Body (~110 words):**

> Hi [Name],
>
> I'm Krethik, building Skydock — a vehicle-mounted drone platform that captures aerial ground-truth at the same locations an AV fleet operates. Pre-seed, doing customer discovery.
>
> [SPECIFIC HOOK — one sentence referencing their public work].
>
> Three questions I'd love 15 minutes on:
> 1. How does your team currently validate on-vehicle BEV perception against truly independent ground truth?
> 2. Where's the biggest gap in your training data today — geographic coverage, edge cases, or independent validation?
> 3. Would you ever procure aerial captures from an external vendor, and what would change to make that a yes?
>
> No pitch. Just trying to learn whether the pain we think exists actually does.
>
> Thanks,
> Krethik

---

## Variant B — Senior director / VP (less technical surface)

**Best for:** Erik Rosén (Zenseact), Drew Bagnell (Aurora — if you go that high), Andrew Clare (Nuro CTO backup).

Senior leaders get more cold pitches. Hook needs to reference a strategic question, not a technical detail.

**Subject:** AV perception validation — 15 min on a thesis

**Body (~100 words):**

> Hi [Name],
>
> I'm Krethik, building Skydock — early-stage company exploring whether AV teams have a real, paid-for-pain around independent ground-truth capture for perception validation.
>
> [SPECIFIC HOOK — reference a strategic decision or public position they've taken].
>
> Hoping for 15 minutes to learn whether this thesis is real. Three short questions:
>
> 1. Is independent perception validation a budgeted line item at [Company], or does it live inside ML eng?
> 2. What would have to be true for an external aerial-capture vendor to be worth a pilot?
> 3. Who at [Company] would own that procurement decision?
>
> Happy to share what we've built in simulation as background. No pitch.
>
> Thanks,
> Krethik

---

## Variant C — Toolchain / synthetic vendor (partner-or-competitor)

**Best for:** Jason Brown (Applied Intuition Defense), Foretellix data lead, Kevin McNamara/James Grieve (Parallel Domain), Danny Atsmon (Cognata).

**Critical framing:** Don't pitch. Position as research / partnership-exploration. They may already be your competitor (Applied Intuition Defense has aerial autonomy products); the call is to find out which.

**Subject:** Aerial real-data inputs for synthetic pipelines — research call

**Body (~110 words):**

> Hi [Name],
>
> I'm Krethik, founder of Skydock — early-stage, exploring whether real aerial captures from AV operating locations could feed synthetic-data pipelines like [Company's product].
>
> [SPECIFIC HOOK — reference their product/program publicly].
>
> Three questions, 15 minutes:
> 1. Does [Company product] currently use real driving logs from customers as scenario seeds, or do you generate purely from synthetic priors?
> 2. Would aerial captures from the same locations as your customers' ground-vehicle logs add value as an input feed?
> 3. Is this something [Company] is building internally, or might it be a vendor-supply opportunity?
>
> I'm doing customer discovery, not pitching. Honest "we'd build this ourselves" answers are exactly the data I'm looking for.
>
> Thanks,
> Krethik

---

## Variant D — Foundation-model / end-to-end team (Wayve)

**Best for:** Vijay Badrinarayanan (Wayve), Aniruddha Kembhavi (Wayve).

Wayve uses end-to-end foundation models, not modular perception. The "independent validation" thesis may not apply the same way. The conversation needs to discover what their actual pain is.

**Subject:** Real aerial data for end-to-end driving foundation models

**Body (~100 words):**

> Hi [Name],
>
> I'm Krethik, building Skydock — capturing aerial real-world data at AV operating locations. Pre-seed, doing customer discovery.
>
> [SPECIFIC HOOK — reference Wayve's foundation-model approach or specific paper].
>
> End-to-end foundation models have different data needs than modular perception stacks, and I'd love 15 minutes to understand yours:
> 1. What's the highest-leverage incremental data source for Wayve's models today — geographic diversity, novel viewpoints, edge-case capture, or something else?
> 2. Would real overhead-viewpoint captures (vs. synthetic) add anything to your training distribution?
> 3. What's the procurement model — internal-only, or do you buy data from external vendors?
>
> No pitch.
>
> Thanks,
> Krethik

---

## Follow-up sequence

Cadence: **Day 0 → Day 4 → Day 10 → done** (3 touches max).

### Day 4 follow-up (no response yet)

> Hi [Name],
>
> Quick bump — wanted to make sure my note didn't get buried.
>
> 15 min on whether aerial ground-truth is a real pain for AV perception teams. If now isn't a good time, totally understand; happy to circle back next quarter.
>
> Thanks,
> Krethik

### Day 10 follow-up (still no response)

> Hi [Name],
>
> Last note from me on this. If aerial ground-truth isn't relevant to your team, a one-line "not for us" would be hugely helpful — falsification is valuable data when you're doing customer discovery.
>
> Either way, appreciate your time.
>
> Krethik

---

## Specific-context customization for top 3 contacts

### → Felix Heide (Torc Robotics, Head of AI)

**Use Variant A.** Specific hook to swap into the bracketed section:

> *"Your team's ICCV 2025 paper on self-supervised sparse sensor fusion for 250m perception was excellent — the camera-LiDAR forecasting Chamfer-Distance gains have me thinking about ground-truth at long-range. Also caught the CES 2026 'hallucination-free video generation' demo."*

**Why this hook works:** It proves you read his actual work (not just his title), and the long-range / hallucination-free synthetic angles both connect to the perception-validation thesis.

**Send via:** LinkedIn message (he's active on the platform — recently posted about CES 2026). Email backup via Princeton academic page if no response in 7 days.

---

### → Tilo Schwarz (Nuro, VP Engineering Nuro Driver)

**Use Variant A.** Specific hook to swap in:

> *"Congrats on the California driverless permit and the Lucid Gravity rollout heading into the late-2026 commercial launch. Curious how the perception validation cadence changes when you're operating Bay Area public roads under the Uber app vs. the Las Vegas proving ground."*

**Why this hook works:** Shows you're tracking the Uber/Lucid partnership rollout closely. The "validation cadence as you scale to commercial" angle is one Tilo himself owns.

**Send via:** LinkedIn message (linkedin.com/in/tilo-schwarz-42289b166/).

---

### → Jason Brown (Applied Intuition Defense, GM)

**Use Variant C.** Specific hook to swap in:

> *"Saw the April 28 Dstl drone-swarm demo and the Axion + Acuity all-domain announcement. I'm trying to understand whether real aerial capture-at-location is a data source Applied Intuition Defense is sourcing externally, or building in-house via the Axion stack."*

**Why this hook works:** Shows you've done the work to understand Applied's actual aerial-autonomy programs. Names both Axion (developer cloud) and Acuity (paired aerial autonomy product). Positions you as researcher, not competitor — disarming.

**Critical:** With Jason, **be prepared for him to be a competitor**. The most valuable outcome of the call is clarity: "Applied is going to do this themselves" → you redirect. "Applied wants to buy real-data inputs" → potential channel partner. Don't oversell; let him talk.

**Send via:** LinkedIn message. If no reply, email through Applied Intuition's defense team contact form is unlikely to reach him; try a connection request with a 300-char note instead.

---

*Outreach scripts v1. Iterate based on response rates after first 5 sends — track which subject lines and hooks get replies, kill what doesn't work.*
