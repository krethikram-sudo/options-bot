# Outlay — market sizing (bottoms-up)

Fills deck Slide 7. **Bottoms-up, not top-down** — VCs discount "1% of a $30B
market." This builds TAM from orgs × spend × take rate, then triangulates against
two independent anchors (the AI-coding market and the cloud-FinOps analog).

All figures are **modeled estimates** from the cited public inputs below; the
softest input (# of target orgs) is flagged for you to firm up. Tune the
assumptions in the sensitivity table — don't present a single false-precise number.

---

## Cited inputs (June 2026)

| Input | Value | Source |
|---|---|---|
| AI coding-assistant market | $4.9B (2024) → $30B+ by 2032 | DigitalApplied / market reports |
| Cursor ARR | ~$2–3B annualized (early 2026), enterprise = 60% | Sacra / DigitalApplied |
| Dev adoption of AI tools | 90% use AI tools; ~51% daily | JetBrains / DEV surveys |
| Enterprise trajectory | Gartner: 90% of enterprise engineers on AI assistants by 2028 (from <14% early 2024) | Gartner |
| **AI spend per developer** | **$150–250/dev/mo avg; $200–600 all-in (seats + tokens); outliers $500–2,000** | getDX / Memeburn |
| Per-dev AI usage growth | ~**18.6× in 9 months** | Jellyfish |
| Cloud-FinOps software market (the analog) | ~**$15.8B in 2026**, ~10% CAGR → ~$25B by 2031; software ≈ 65% | Mordor / Research&Markets |

**Read:** AI engineering spend is large, growing absurdly fast (18.6× per-dev in
9 months), and structurally identical to the cloud spend that birthed a ~$16B
FinOps category — except it's ungoverned and lives where the FinOps suites can't
see it.

---

## The build

### Unit: annual contract value (ACV) per target org
- **Target org:** an eng org with ~50–150 developers actively using AI coding
  tools at real spend (the "spend-maturity moment" ICP).
- **AI spend per dev:** use **$250/dev/mo blended = $3,000/dev/yr** (conservative —
  the low end of the $200–600 all-in range; heavy agentic teams run far higher).
- **Per-org AI spend:** 75 devs × $3,000 = **$225k/yr** governed spend.
- **Outlay ACV:** platform fee + a share of realized savings. At a blended
  **~10–12% of governed spend** (a flat platform fee plus ~20% of a conservative
  ~30% routing saving ≈ 6% savings-share), a 75-dev org is **~$22–27k ACV.**
  → use **$25k ACV** as the planning unit.

> Take-rate sanity: cloud-FinOps tools capture low-single-digit % of *cloud* spend
> managed; savings-share players (ProsperOps/Zesty) take a share of realized
> savings. ~10–12% of AI spend is defensible because Outlay both *governs* (SaaS)
> and *reduces* (savings share) the bill — two value lines on one account.

### TAM — all eng orgs with material AI spend, at maturity
Frame: total **AI engineering spend under management × Outlay take rate.**
- AI coding spend heading to **$30B+/yr by 2032** (and broader LLM/agent spend on
  top). At a ~**8–12% capture**, the governance-and-optimization layer is a
  **~$2.4–6B TAM.**

### SAM — reachable orgs, near-to-mid term
- **# of target orgs (FOUNDER TO FIRM UP):** software/eng orgs with 50+ engineers
  meaningfully on AI coding tools, English-speaking / cloud-native first.
  Planning estimate: **~30,000 orgs** `[validate — softest input in the model]`.
- 30,000 orgs × $25k ACV = **~$750M SAM.**

### SOM — obtainable in the first ~3 years
- Beachhead = the **high-discipline GitHub-Issues mid-market** (day-one value,
  zero instrumentation — the 60–90%-joinable cluster).
- Year-3 target: **~300–500 paying orgs × $25k = ~$7.5–12.5M ARR.** That's the
  number the pre-seed milestones ladder toward (pilots → first paying → this).

---

## Triangulation (two independent checks)

1. **vs. the AI-coding market.** $25k ACV across even 30k orgs = $750M, ~2–3% of
   the projected $30B AI-coding spend pool — a *conservative* governance capture.
2. **vs. cloud FinOps.** That category is ~$16B governing *cloud* spend. An
   "AI-FinOps" category reaching just **15–35% of FinOps's size** = **$2.4–5.6B**,
   matching the TAM build from the other direction. Given AI spend's growth rate,
   that's not aggressive.

Both roads land at a **multi-$B TAM** with a **~$750M SAM** — comfortably big
enough for a venture outcome, which is all Slide 7 needs to prove.

---

## Sensitivity (show this, not a single number)

| Spend/dev/mo | ACV (75-dev org) | × 30k orgs (SAM) |
|---|---|---|
| $150 (avg low) | ~$16k | ~$480M |
| **$250 (base)** | **~$25k** | **~$750M** |
| $400 (all-in mid) | ~$40k | ~$1.2B |
| $600 (heavy agentic) | ~$60k | ~$1.8B |

(Holds org count fixed; the org count is the input to firm up next.)

---

## What to say on the slide (script)

> "AI engineering spend is on track for $30B+/yr and growing ~18× per developer
> in well under a year — the same setup that made cloud FinOps a $16B category,
> except this spend is completely ungoverned and invisible to those tools. A
> typical 75-engineer customer runs ~$225k/yr of AI spend; we govern and reduce
> it for ~$25k. That's a ~$750M reachable market today and a multi-billion TAM as
> the spend compounds — and we start with the GitHub-Issues mid-market that gets
> value on day one."

## Caveats (know them before they're asked)
- **Org count is the soft input** — firm it up (e.g. from Apollo/LinkedIn counts
  of companies with 50+ engineers, discounted by AI-adoption %). Everything else
  is cited.
- **ACV is pre-validation** — your first pilots set real pricing; treat $25k as a
  hypothesis, not a fact.
- Keep the spend/dev figure on the conservative end in the room; you have headroom
  to surprise upward, which is the right direction to be wrong.

## Sources
- AI coding market / Cursor: digitalapplied.com, sacra.com/c/cursor
- Adoption: JetBrains AI Pulse (Jan 2026), DEV/Stack Overflow surveys, Gartner
- Spend/dev: getdx.com/blog/ai-coding-assistant-pricing, memeburn.com (AI worker spend)
- Cloud FinOps market: mordorintelligence.com, researchandmarkets.com
