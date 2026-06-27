# Outlay — product & segment strategy (reasoned from the market analysis)

Derived from `docs/market-analysis-ai-spend-governance.md` (taxonomy, ranked fit variables,
purchasing models, US TAM core-vs-incremental, competitive landscape). This is the **reasoning**:
what the core should be and why, who to land, and how to expand — in sequence, with the logic.

---

## TL;DR

- **Core = the work-attribution + honest-forecast + budget-governance layer for AI spend** — *not* "an
  AI cost dashboard." Lead with the thing only our data can do (token → ticket/feature/engineer via the
  tracker join, forecast back-tested on the customer's own delivered work, governed to budget). The
  generic "visibility" framing is already crowded (Vantage/CloudZero/Finout) and commoditizing; the
  *join + forecast + read-only posture* is the moat.
- **Beachhead = engineering-heavy, consumption-spending software & AI-native companies, ~250–5k
  employees, >$250–500k/yr AI spend.** That's where the spend is biggest, the attribution gap is worst,
  our differentiated join actually works, and a buyer with budget + urgency exists.
- **Expansion is one data asset, reused three ways:** (A) **more spend layers** (eng consumption →
  seats → every department), (B) **more value on the same data** (attribution → chargeback →
  enforcement → **commitment/procurement optimization**), (C) **more segments** (software → enterprise
  → financial services → regulated/gov). Each step adds a buyer or a spend layer, raises ACV, and
  deepens system-of-record lock-in.

---

## 1. What the core product should be — and why

### The decision: differentiated governance, not commodity visibility
The research forces one sharp call. The "see your AI spend" layer is **contested and commoditizing** —
Vantage, CloudZero, Finout, Datadog, Flexera all connect billing APIs and show team/project/customer
breakdowns. If Outlay is "another AI cost dashboard," it competes on table stakes against funded
incumbents and the cloud-FinOps installed base. **So the core must be what only Outlay's data enables:**

1. **Attribution to the unit of work** — AI spend mapped to the **ticket / feature / engineer / program**
   via the work-tracker join (Jira/GitHub/Linear), not just team/project/cost-center. This is the
   answer to the question finance actually asks — *"what is AI costing us per output?"* — and it's
   structurally harder to copy (requires the tracker join + a costing model, not just a billing
   connector). *(Outlay's #1 moat.)*
2. **Forecasting back-tested on the customer's own delivered work** — predict planned/open work cost
   from *their* closed-ticket history, and show the measured error (leave-one-out). This is the **trust
   unlock** — no vendor benchmark, their own data — and it's the basis for everything downstream
   (budgets, commitments). *(Outlay's #2 moat — the honesty layer.)*
3. **Budget governance + pacing** — program budgets, real-time pacing, projected breach, on-/off-track
   earned-value rating. This is what turns a report into a **system of record you act on** — the thing
   that gets Outlay into the monthly finance + eng-leadership ritual. *(The stickiness layer.)*

All three are already built. The strategic change is **positioning + sequencing**, not a rebuild: stop
selling "visibility," sell **"know what AI costs per unit of work, forecast it on your own data, and
hold it to budget — read-only, your keys, no PHI."**

### Why this is the right core (mapped to the research)
- **It sits on the biggest, fastest-growing, least-visible spend.** Engineering consumption — code gen
  (~$4B, ~28% of enterprise LLM deployments, Claude ~42% dev share), raw API tokens, coding agents,
  with inference now the dominant workload — is exactly where per-seat pricing fails and account-level
  bills hide the work context. [Menlo; Flexera]
- **It rides the category inflection.** 98% of orgs now manage AI spend (from 31% in 2024); it's the #1
  FinOps priority and #1 skill gap — there is a budget line and an owner to sell to *now*. [FinOps 2026]
- **It's defensible where "visibility" isn't.** The tracker join + own-data forecast + metadata-only /
  BYOK / read-only posture are things the cloud-cost dashboards don't lead with and the gateways
  (in-path) can't claim. [§11 competitive]
- **It's the precondition for the high-$ expansion** (commitment optimization, §3B) — you can't
  recommend a commitment without attributed + forecasted usage. Owning the core *is* owning the input
  the prize feature needs.

### What the core is NOT (guardrails)
- **Not in the request path.** Read-only / metadata-only is the differentiation *and* the compliance
  wedge — don't become a gateway. Keep enforcement as an optional bridge, not the core.
- **Not "lowest token price."** Routing/caching is the gateways' game and a race to the bottom; Outlay
  *recommends* savings from the read-only data, it doesn't broker tokens.
- **Not a generic cloud-cost tool.** Win the AI/eng-work attribution wedge deeply before going broad.

---

## 2. Who to target first — the beachhead

### The ICP (from the ranked fit variables)
> **Engineering-heavy, "scaled-adopter" software & AI-native companies, ~250–5,000 employees, with
> >$250–500k/yr AI spend that is consumption-based, multi-provider, and unowned.**

Qualifying signal (in order of predictive power): heavy + growing **consumption** spend → **multiple
tools/providers with no unified view** → **no clear owner / surprise bills** → **production (not
experiment) AI** → **eng/data-heavy headcount**.

### Why this beachhead (the reasoning)
1. **Fit is highest and the moat works here.** The attribution gap is worst in eng consumption, *and*
   the tracker join (our differentiator) only fires when there's a tracker + coding-agent/API usage —
   which is exactly this segment. Differentiation and pain peak in the same place.
2. **There's a buyer with budget and urgency.** Platform/eng leadership (technical champion, owns the
   API budget, feeling the heat) + VP Finance/FinOps (economic buyer asking "why did this 3×?"). Land
   eng, expand to finance.
3. **It's reachable and fast.** Founder-led sales work; no 12-month procurement. Big enough bill for
   clear ROI, not so big they've already built it in-house.
4. **It compounds.** These companies' AI spend is growing 50–100%/yr and spreading to other functions —
   land the hardest layer first, then ride the expansion (§3).

### The gov/regulated tension — resolve it explicitly
The Maryland/gov motion is **high-ACV but slow** and a *different* beachhead. Recommendation: **run it
as a parallel lighthouse, not the volume engine.** Gov gives (a) marquee logos, (b) a forcing function
for the SOC 2 / StateRAMP compliance moat we need anyway, and (c) validation of the metadata-only
posture. But **don't let gov procurement set the roadmap** — the velocity + PMF beachhead is eng-heavy
software. Two tracks: **software for learning-rate and revenue, gov for ACV and moat.**

### Lower-fit (de-prioritize, for now)
Pre-seed/tiny (bill too small), AI-laggards (no spend), single-seat-SaaS shops with one owner (little
attribution pain). Self-serve down-market is a *later* motion once the core is sticky.

---

## 3. How to expand — one data asset, three axes, sequenced

The strategic engine: **every expansion reuses the attribution+forecast data**, adds a **new buyer or
spend layer**, raises **ACV**, and deepens **system-of-record lock-in** (more spend under management =
harder to rip out). Sequence them so each step is funded by the last and earns the right to the next.

### Axis A — across the org (land eng, expand to every function's AI spend)
- **Land:** engineering/API/agent **consumption** spend (the hardest, highest-value layer).
- **Expand:** the **seat layer** — sales/marketing/support/legal on Copilot/ChatGPT-Ent/Glean. Same
  budget + showback engine; value shifts to **seat-waste + department budgets**. Rides the verified
  trend that AI spend is spreading across functions (Legal +24pp, Procurement +15pp impact) and that
  consumption pricing is moving from eng to everyone.
- **Become:** the **company-wide AI-cost system of record** (all layers, all providers, one attributed
  view) — the position no single-vendor console or in-path gateway can hold.

### Axis B — across the product (incremental TAM on the same data)
Sequence by "needs the least new data / new buyer" → "highest $, hardest":
1. **Core (shipped):** attribution + forecast + budget governance. *(Captures ~60–70% of revenue TAM;
   the wedge.)*
2. **Chargeback / showback:** turn attribution into cross-charge to teams/cost-centers. *Expands the
   buyer fully into Finance/FinOps; near-zero new data.*
3. **Enforcement / guardrails:** hard budget caps (the shipped enforcement endpoint / a gateway bridge)
   for teams that want control, not just visibility. *Optional, posture-preserving.*
4. **Commitment & procurement optimization (the prize):** the ProsperOps-for-the-model-API-layer gap —
   "commit/provision the steady X%, leave the spiky remainder on-demand," commitment pacing, PTU-vs-
   on-demand by workload, renewal/negotiation packs. **Highest-$ incremental lever** (cloud analog is
   the biggest FinOps saver, 30–60% cited), and our **attributed+forecasted data makes the
   recommendation better than an infra-only optimizer.** Attack it *after* the core owns the data —
   and before Flexera (ProsperOps + FinOps-for-AI) stitches it together.
5. **Adjacent:** shadow-AI discovery + seat-waste (new buyer: IT/Procurement) — expands to the seat
   layer and a new budget owner.

### Axis C — across segments (market expansion, after PMF in the beachhead)
1. **Beachhead:** eng-heavy software / AI-native (250–5k). *(now)*
2. **Up-market enterprise (5k+):** bigger bills, more departments, real chargeback need. Win on the
   **work-join + multi-vendor neutrality** (they're multi-provider and won't trust one vendor's
   console); guard against build-in-house with depth + the forecast. *(needs SOC 2 + scale.)*
3. **AI-forward financial services / insurance:** large bills, **mandated** cost governance,
   multi-provider — high ACV, governance is required not optional.
4. **Regulated / public sector (gov):** the **metadata-only posture is the wedge**; highest ACV,
   slowest cycle; **unlocked by SOC 2 → StateRAMP** (the Maryland motion is the entry; see the
   compliance sequencing doc).
5. **Down-market / PLG (later):** self-serve via the low-friction read-only connect — only once the
   core is sticky; small bills = low ACV, so this is a volume/funnel play, not the value center.

### Why this order (the strategic logic)
- **Beachhead first, deeply** — PMF in the segment where the moat is strongest before going broad;
  avoids the "shallow horizontal AI-cost tool" trap that the crowded visibility layer punishes.
- **Expand the data before the features** — own the attributed spend (Axis A) so the high-$ features
  (Axis B4) have a defensible data advantage; the commitment-optimizer that knows *which work is
  steady* beats one that only sees aggregate infra.
- **Compliance moat funds the premium segments** — SOC 2 / StateRAMP (from the gov lighthouse) is what
  opens fin-services and public-sector ACV; sequence it as a parallel investment, not a detour.
- **Race the consolidator** — Flexera is the one player positioned to own both layers; the defense is
  to own the **work-attribution data** (which they don't have) and reach the commitment layer from it.

---

## 4. The sequenced plan (one table)

| Phase | Core motion | Customer | Product focus | Why now |
|---|---|---|---|---|
| **Now** | Win the eng-consumption wedge | Eng-heavy software/AI-native, 250–5k, >$250k AI spend | Core: **work-attribution + forecast + budget**; reposition off "visibility" | Biggest gap, moat strongest, buyer urgent |
| **+** (parallel) | Gov lighthouse | Regulated / Maryland | Same core + Trust Center; **drive SOC 2** | Marquee ACV + funds the compliance moat |
| **Next** | Expand the account | Same logos | **Chargeback/showback** + seat layer (other functions) | New buyer (Finance), more spend under mgmt |
| **Then** | Capture the prize | Beachhead + up-market | **Commitment & procurement optimization** | Highest-$ incremental TAM; beat Flexera to it |
| **Later** | Broaden segments | Enterprise, fin-services, then gov-scale; PLG funnel | Enforcement, multi-cloud FinOps-for-AI, self-serve | After SOC 2/StateRAMP + PMF; grows serviceable share |

---

## 5. Open decisions to pressure-test (founder calls)
1. **How hard to reposition off "AI cost visibility"** in the marketing — the research says the generic
   framing is crowded; how aggressively do we lead with the work-join + forecast instead?
2. **Resource split between the software beachhead and the gov lighthouse** — they pull the roadmap in
   different directions (velocity vs compliance). Recommended ~70/30 toward software for learning-rate.
3. **When to start the commitment-optimization build** — it's the prize but needs the data + races
   Flexera. Trigger: once we have N accounts with attributed multi-provider spend and a forecast they
   trust.
4. **Build vs partner on enforcement/gateway** — keep the read-only posture central; bridge to a
   gateway for hard enforcement rather than becoming one?
