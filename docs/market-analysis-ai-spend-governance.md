# US market analysis — AI-spend attribution & governance (Outlay)

**Question:** Who buys AI in the US, which variables predict they get real value from Outlay
(metadata-only, BYOK, read-only attribution + forecasting + budget governance of AI spend),
how do they buy AI compute today, and what's the defensible TAM — core vs incremental?

**Provenance.** Built from a deep-research run (fan-out web search → fetch → **3-vote adversarial
verification**). 19 claims survived verification; 5 were refuted and excluded (listed at the end so
we don't repeat them). Macro facts below are **cited**; the taxonomy, fit-scoring, purchasing
breakdown, and TAM are **Outlay's analysis on top of those facts**, with assumptions labeled.
Scope: **US**, demand-side AI spend (what companies pay to *use* AI — SaaS + API + their own cloud
AI), which is the pool Outlay can govern. (Supply-side data-center capex is sized separately and is
**not** Outlay's addressable pool — see TAM caveat.)

---

## 0. Executive summary

1. **The category is real and inflecting now.** AI-spend management went from a niche to near-
   universal in 24 months — **98% of organizations now manage AI spend as part of FinOps, up from
   31% in 2024**, the fastest cost-discipline adoption the FinOps survey has ever recorded, and it's
   the **#1 FinOps priority** for the next 12 months. [FinOps Foundation 2026]
2. **The pain is structural, not cyclical.** AI bills scale by **tokens/compute, not seats**, so
   per-seat pricing can't price them; spend is **consumption-based, opaque, account-level, and spread
   across many providers with no unified view** — the exact attribution gap Outlay closes.
   [Flexera; Datadog; Vantage]
3. **The bill is large, growing, and finance-visible.** **88% of large US enterprises plan to
   increase GenAI budgets in the next 12 months; 62% by ≥10%.** Enterprise LLM **API** spend alone
   was ~**$8.4B** by mid-2025 (≈2× in ~6 months), and the field is **multi-vendor** (Anthropic ~32–40%,
   OpenAI ~25–27%, Google ~20%, Llama ~9%). [Wharton/GBK; Menlo Ventures]
4. **The wedge is the engineering/coding-agent segment.** Code generation is AI's first breakout
   use case (~**$4B, ~28% of enterprise LLM deployments**, Claude ~42% developer share), it runs on
   **raw API tokens + coding agents** (the worst attribution gap), and **inference/production has
   overtaken training** — i.e., recurring usage cost, not one-time. [Menlo Ventures]
5. **TAM (Outlay model).** US **governable AI-spend pool ≈ $35–70B in 2026**, growing ~50–100%/yr.
   At a FinOps-style **2–5% software take-rate**, that's a **~$1–3B US revenue TAM**, of which the
   **core product** (attribution + forecast + budget governance) is the entry wedge and **incremental
   features** (enforcement, chargeback, procurement optimization) roughly double the wallet over time.

---

## 1. Market context (the facts the strategy rests on)

**AI-cost governance has become a board-level FinOps discipline — fast.**
- **98% of organizations now manage AI spend** as part of FinOps, **up from 31% two years ago** (2024);
  the survey calls it the fastest technology-cost adoption in its history. [FinOps Foundation, *State of
  FinOps 2026*, n=1,192 orgs representing $83B+ tech spend — data.finops.org] *(high confidence)*
- **Managing AI spend is the #1 FinOps priority** for the next 12 months (cited by 32.7% of teams — a
  plurality), and **AI cost management is the #1 skillset** teams want to build (58%). [FinOps 2026] *(high)*
- FinOps scope is expanding beyond cloud: **90% manage (or plan to manage) SaaS, 64% licensing, 57%
  private cloud, 48% data center.** [FinOps 2026] *(high)* — i.e., the buyer Outlay sells to already
  exists and is actively widening their remit to exactly this.

**The bill is big, growing, multi-vendor, and consumption-shaped.**
- **88% of US enterprises (1,000+ employees, >$50M revenue) plan to increase GenAI budgets in the next
  12 months; 62% expect ≥10% increases.** [Wharton/GBK Collective, *2025 AI Adoption Report*,
  ~800 US enterprise decision-makers — ai.wharton.upenn.edu] *(high)*
- Enterprise **LLM API spend ≈ $8.4B by mid-2025**, roughly double ~6 months prior; basis is a Menlo
  survey of 150 technical leaders. [Menlo Ventures, *2025 Mid-Year LLM Market Update*] *(medium — the
  "$8.4B" figure is corroborated; the specific "doubled in exactly 6 months" framing failed verification)*
- **Multi-vendor field:** Anthropic ~32% (year-end ~40%), OpenAI ~25% (down from ~50% in 2023),
  Google ~20%, Meta Llama ~9%. [Menlo] *(high on the numbers; nuance: top-3 ≈ 88% concentration and only
  ~11% of teams switched providers in the past year — vendor diversity is real at the **market** level
  and growing **within** large enterprises, but isn't yet universal per-company multi-homing)*
- **Inference (production) has overtaken training** — 74% of startups and 49% of large enterprises say
  most compute is now inference — i.e., **recurring usage cost**, not one-time training. [Menlo] *(high)*
- **Code generation is the breakout use case** (~$4B, ~28% of enterprise LLM deployments; Claude ~42%
  developer share vs OpenAI ~21%). [Menlo] *(high)*

**Why per-seat pricing broke (the structural opening).**
- **AI features scale by tokens, compute-minutes, and model complexity — not by user** — so per-seat
  pricing structurally can't price them; this is the core driver of the **seat → consumption** shift
  (~65% of vendors now use hybrid seat+usage pricing). [Flexera; corroborated by Bain] *(high)*
- **Consumption data is opaque and aggregated at the account level**, and AI usage is **spread across
  internal platforms, SaaS tools, and vendor APIs with no out-of-the-box unified view** — making
  attribution to workloads/teams hard. Provider billing "typically breaks down costs only to the
  model, project, or workspace level," and "team/cost-center metadata doesn't exist natively in AI
  billing data." [Flexera; Datadog; Vantage] *(high)* — **this is Outlay's problem statement, verbatim.**
- **Finance often can't map a credit back to a workload**; credit expirations/resets/rollover
  "silently create overages or strand value," producing budget surprises and uncontrolled use. A
  reported **78% of IT leaders saw surprise AI charges** in the past year. [Flexera] *(high)*
- **Seat overbuying already wastes money** (≈51–53% of SaaS licenses go unused; large enterprises
  waste ~$21M/yr), and AI makes the meter worse. [Flexera; CFO Dive] *(high)*

**Supply-side context (NOT the addressable pool).** Global **AI data-center capex is forecast at
$400–450B in 2026** ($250–300B of it chips), rising to **~$1T by 2028**; inference ≈ two-thirds of all
compute in 2026. [Deloitte, *TMT Predictions 2026*] *(high)*. This is the hyperscaler/AI-lab **build**;
Outlay governs the **consuming company's** AI bill, so capex is the backdrop, not the TAM (see §4 caveat).

---

## 2. Customer taxonomy — the variables, and what each implies for fit

Categorize US AI buyers on these axes. For each, the **"hot" end** (higher Outlay value) is bolded.

| Variable | Buckets (low-fit → high-fit) | Why it predicts value |
|---|---|---|
| **AI spend model** | seat-SaaS only → mixed → **heavy API/consumption + credits** | Attribution gap lives in token/usage spend, not flat seats [Flexera] |
| **Spend magnitude & growth** | flat/small → **large & growing ≥10%/yr** | 88% increasing budgets; bigger bill = bigger problem [Wharton] |
| **# providers / tools** | single tool → **many tools, multi-provider, no unified view** | Fragmentation = no native rollup [Menlo; Datadog] |
| **Cost-owner gap** | one owner, in control → **no owner / finance blind** | "can't map credit→workload" [Flexera] |
| **AI maturity / current state** | laggard → experimenter → **scaled adopter (production inference)** → AI-native | Inference = recurring cost; experiments are too small to govern [Menlo] |
| **Employee mix** | non-technical, light AI → **engineering/data-heavy + AI-native knowledge work** | Eng on coding agents = highest token spend [Menlo] |
| **Size (employees)** | <50 → 50–250 → **250–5k** → 5k+ | Big enough to have a real bill + departments to attribute; not so big they've already built it |
| **Stage / type** | pre-seed → **growth/late-stage startup**, **PE-backed**, **established corp digitizing** → public mega-cap | Budget pressure + finance scrutiny + can't-yet-build-it-themselves |
| **Vertical** | low-AI (e.g. traditional mfg) → **software/tech, financial services, digital-native, prof. services, gov/regulated** | Where AI spend concentrates and where governance is mandated |
| **Key tools** | one chat seat → **Cursor/Copilot + Claude/OpenAI/Bedrock APIs + Copilot/ChatGPT-Ent seats** | Coding agents + provider APIs are the consumption core |

**AI usage by employee function (where the spend actually is):**
- **Engineering / data-ML** — **highest $/head.** Coding agents (Cursor, Copilot, Claude Code) + raw
  provider API tokens (OpenAI/Anthropic/Bedrock/Azure). Consumption-based, volatile, hardest to
  attribute. *This is the core wedge.* [Menlo: code gen $4B/28%]
- **Customer support / service** — high and rising (deflection bots, agent assist); +16pp perceived
  impact vs 2024. Often usage-metered. [Wharton]
- **Sales & marketing** — broad seat adoption (Copilot, ChatGPT, content tools); mostly seats today.
- **Legal, Procurement, Finance, HR, Ops** — fastest-rising *perceived* impact (Legal **+24pp**,
  Procurement **+15pp**) — AI spend is **spreading across departments**, multiplying who needs
  attribution. [Wharton] Mostly seats now, drifting to usage.
- Cross-cutting: **82% of enterprise leaders use GenAI weekly, 46% daily** — adoption is broad-based
  and recurring (though that's leaders, not yet the whole workforce). [Wharton]

---

## 3. The critical value-prop-fit variables (ranked by predictive power)

If you could ask only a few questions to qualify a prospect, ask these — in order:

1. **"How much of your AI spend is consumption/usage-based (API tokens, credits, metered) vs flat
   seats — and is it growing?"** *(highest signal.)* Heavy + growing consumption spend = the
   attribution gap is real and worsening. [Flexera; Menlo]
2. **"How many AI tools/providers are in use, and can anyone produce one unified view of the spend
   and who/what drove it?"** Many tools + "no, nobody can" = textbook Outlay. [Datadog; Vantage]
3. **"Who owns the AI budget, and have you been surprised by an AI bill?"** No clear owner + surprise
   charges (78% have) = active pain, budget authority to buy. [Flexera]
4. **"What's your AI maturity — experiments, or production workloads running every day?"** Production
   inference = recurring, governable spend; experiments are too small. [Menlo]
5. **"What share of your headcount is engineering/data, and do they use coding agents / call model
   APIs directly?"** Eng-heavy = the highest-spend, lowest-visibility function. [Menlo]
6. **Spend magnitude / company size** — gates whether the ROI clears your price (below a threshold the
   bill is too small to bother governing).

**The threshold where the value prop becomes real (Outlay's qualifying line):**
> A company with **>$250–500k/yr of AI spend**, **at least a meaningful share consumption-based**,
> **2+ AI tools/providers**, **no single owner producing an attributed view**, and **an
> engineering/AI-native function** driving usage. Below that, the bill is too small or too simple to
> need a governance layer (seats with one owner ≈ low fit).

**High-fit ICP:** growth/late-stage software & digital-native companies (250–5k employees), AI-native
or "scaled adopter," engineering-heavy, multi-provider API + coding-agent spend, finance starting to
ask "what is this costing per team/project?" Plus **AI-forward financial services and regulated/gov**
where governance is *mandated* (your existing Maryland/gov motion is the regulated flavor of this).
**Low-fit:** pre-seed/tiny (no bill), AI-laggards (no spend), single-seat-SaaS shops with one owner
(little attribution pain — though budget/waste value still exists).

---

## 4. How companies buy AI compute today (the central question)

Four models coexist; most companies run **several at once**, which is itself the problem.

| Model | Who owns budget | Pricing | Who/what it covers | Why they choose it | Outlay value |
|---|---|---|---|---|---|
| **(a) Seat / enterprise subscriptions** (ChatGPT Enterprise, Copilot, Claude for Work, Glean) | **IT / Procurement** | per-seat, predictable | knowledge workers (sales, mktg, ops, legal, support) | control, security/SSO, simple budgeting, compliance | budget/showback + **waste** (overbought seats, ~50% unused) |
| **(b) Central API/compute + credits/budgets** (OpenAI/Anthropic/Bedrock/Azure orgs; cloud GPU) | **Engineering / Platform / sometimes Finance** | **usage/consumption**, volatile | engineers, data/ML, production features, coding agents | speed + developer experience, can't seat-price tokens, scale | **core wedge** — attribute tokens→team/ticket/workload, forecast, cap |
| **(c) Reimbursed individual subscriptions** | **Finance (expensed)** | per-seat, scattered | early/SMB, individual power users | speed, low friction, pre-policy | near-zero visibility; consolidation/showback opportunity |
| **(d) Shadow AI on personal accounts/cards** | **nobody (ungoverned)** | mixed | anyone, pre-policy | velocity, avoiding procurement | security/compliance + surprise-charge risk; the thing governance teams are chartered to kill |

**By employee type (the split that defines Outlay's land-and-expand):**
- **Engineers / data scientists →** model (b). Raw **API tokens + coding agents**; consumption-based;
  the **deepest attribution gap** (account-level bills, no team/ticket metadata). **This is where Outlay
  lands** — it's the spend that's biggest per head, most volatile, and least visible. [Menlo; Vantage]
- **Knowledge workers →** model (a). **Seats**; predictable but **wasteful** (over-buying) and now
  drifting to metered AI add-ons. Outlay's value here is **budget/showback + waste reduction** — the
  **expand** motion across the rest of the company.

**The shift that creates the opening:** the industry is moving **per-seat → consumption/credits**
because AI can't be seat-priced [Flexera]. Each new metered tool/provider adds another opaque,
account-level bill with no native team/workload attribution → finance can't map credits to work →
budget surprises. **Outlay sits across all of them and produces the attributed, forecastable,
governable view that no single vendor's billing console gives.** As consumption pricing spreads from
eng to every function, the attribution gap — and Outlay's TAM — spreads with it.

---

## 5. US TAM model (Outlay analysis — assumptions labeled)

> The research provided strong building blocks (LLM API ≈ $8.4B mid-2025 global; 88% increasing
> budgets; FinOps $83B+ sample; capex $400–450B) but **no clean published "US governable AI-spend"
> number**, so the pool below is **modeled bottoms-up with explicit assumptions** and sanity-checked
> top-down. Treat as ranges, not point estimates.

### 5a. Spend-under-management pool (US, 2026) — what Outlay can govern

| Layer | US 2026 (modeled) | Basis / assumption |
|---|---|---|
| **LLM provider API usage** | **~$10–15B** | Global enterprise API ≈ $8.4B mid-2025, annualizing/growing ~2×/yr → ~$20–30B global 2026; US ≈ ~50% [Menlo] |
| **Employee AI SaaS seats** (Copilot, ChatGPT-Ent, Claude, Cursor, Gemini, Glean…) | **~$8–15B** | ~20–35M US paid AI seats × ~$300–450/yr; penetration rising fast off 88% budget-increase intent [Wharton] |
| **Company-paid cloud AI inference/training** (their own Bedrock/Azure/GCP AI, GPU) | **~$15–35B** | Demand-side slice of cloud AI that *customer companies* pay (excludes hyperscaler/lab capex) |
| **Governable US AI-spend pool** | **≈ $35–70B (2026), → ~$100B+ by 2027–28** | Sum; growing ~50–100%/yr [Deloitte ramp; FinOps 98%] |

*Top-down sanity check:* global AI software/services spend estimates run ~$150–300B in 2026 depending
on scope; US ≈ 40–50% → ~$60–150B all-in, of which the **cleanly governable** SaaS+API+company-cloud
slice is the ~$35–70B above. Consistent order of magnitude. *(medium confidence — wide range by design.)*

### 5b. Outlay serviceable revenue TAM

FinOps/cost-governance tools monetize as either a **% of spend under management (~1–3%)** or a
platform subscription; savings-share models (Outlay's "% of realized savings") tend to net out in a
similar **~2–5% of governed spend** band.

| | Assumption | US revenue TAM |
|---|---|---|
| **Total addressable** | 2–5% take on $35–70B pool | **~$1.0–3.0B** |
| **Serviceable (near-term ICP)** | high-fit segment ≈ 25–35% of pool, 2–4% take | **~$0.3–0.9B** |
| **Obtainable (3-yr beachhead)** | low-single-% of serviceable | **~$15–60M ARR** is a credible early ceiling for the wedge |

### 5c. Core vs incremental TAM (the roadmap question)

- **Core product TAM** — **attribution + forecasting + budget governance** (the must-have to capture
  the base). This is what the FinOps-for-AI buyer needs *first* and what 98%-now-manage-AI-spend are
  shopping for. **≈ 60–70% of the revenue TAM (~$0.7–2.1B).** It's the price of entry and the durable
  wedge.
- **Incremental-feature TAM** — **enforcement/guardrails, chargeback/showback, procurement &
  commitment optimization, anomaly/waste reduction, multi-cloud FinOps-for-AI.** Each is a wallet
  expander on the same accounts. **≈ 30–40% on top (~$0.3–0.9B), and rising** as consumption pricing
  spreads to every function. Procurement optimization in particular grows as commitments/credits
  proliferate.
- **Implication:** the **core must nail attribution + forecast + budget** across the (b) consumption
  layer first — that's where the unaddressed pain and the biggest TAM slice are. Enforcement/chargeback
  are expansion, not the wedge.

### 5d. Fastest-growing, highest-fit segments (where to point GTM)
1. **Eng-heavy growth/late-stage software & AI-native companies (250–5k emp)** — biggest consumption
   gap, fastest spend growth, can't-yet-build-it. **Primary beachhead.**
2. **AI-forward financial services & insurance** — large bills, mandated cost governance, multi-provider.
3. **Regulated / public sector** — governance is *required* (your Maryland motion); slower cycle, higher
   ACV, defensible once SOC 2/StateRAMP land.
4. **Digital-native scale-ups in support-heavy verticals** (usage-metered support AI).

---

## 6. Customer personas

1. **"Platform Eng Lead at a Series C AI-native SaaS co"** (300 emp, eng-heavy). Buys model (b): central
   Anthropic/OpenAI/Bedrock orgs + Cursor/Copilot seats. Owns the AI budget himself; finance asks why
   it 3×'d. **Buys Outlay** to attribute tokens to team/feature, forecast the quarter, and cap runaway
   agents. *Highest fit.*
2. **"VP Finance / FinOps Lead at a 2,000-person digital enterprise."** Owns the cross-tool budget; AI
   is now the #1 line he can't explain. Multiple providers, no unified view. **Buys Outlay** for
   showback/chargeback and budget governance. *High fit — the economic buyer.*
3. **"Head of Eng at a PE-backed scale-up under margin pressure."** PE wants efficiency; AI spend is
   growing and unattributed. **Buys Outlay** to prove cost-per-output and cut waste. *High fit.*
4. **"CIO/CISO at a regulated enterprise or gov agency"** (your Maryland persona). Needs governance +
   audit + budget control, metadata-only for compliance. **Buys Outlay** as the AI cost-governance
   layer. *High ACV, slow cycle.*
5. **"IT/Procurement Lead at a 5k-person traditional enterprise."** Mostly seats today (Copilot,
   ChatGPT-Ent), lots of shadow AI. **Buys Outlay** for seat-waste + shadow-AI discovery + budget.
   *Medium fit, large expand.*
6. **(Low fit) "Founder at a 20-person pre-seed."** One ChatGPT Team seat set; bill too small. Not now.

---

## 7. Trends expanding the TAM (next 2–3 years)

- **Consumption/credits pricing spreads from eng to every function** → the attribution gap (and Outlay's
  pool) widens beyond engineering. [Flexera]
- **Agentic / token-usage explosion** — agents loop and consume far more tokens than chat; inference
  already two-thirds of compute and rising → recurring spend balloons. [Menlo; Deloitte]
- **AI-cost governance is institutionalizing as a FinOps sub-discipline** — 98% now manage AI spend,
  it's the #1 priority and #1 skill gap → a budget line and an owner now exist to sell to. [FinOps 2026]
- **Multi-provider is the steady state** (Anthropic/OpenAI/Google/Bedrock) → no single billing console
  will ever be the system of record; a neutral cross-provider layer is needed. [Menlo]
- **Shadow AI + surprise bills** drive security/finance to demand visibility → governance mandate. [Flexera]

---

## 8. Caveats, weak spots, and open questions

**Caveats / time-sensitivity.**
- Market-share and spend figures move fast (Menlo mid-year → year-end already shifted Anthropic 32%→40%);
  treat point numbers as quarters-fresh.
- Several primary pages (Deloitte, FinOps, Wharton, Menlo, Flexera) 403'd to direct fetch; facts were
  verified via search-index reproduction + independent corroboration (still high-confidence on the
  quotes, but we couldn't deep-read the full PDFs).
- The TAM pool is **modeled**, not a published figure — the research gave building blocks, not a clean
  US number. Ranges are intentional.

**Claims that FAILED verification — do NOT cite these (they sound useful but didn't hold up):**
- "$3.5B→$8.4B *doubled in exactly six months*" (the doubling-timeframe framing; the $8.4B level itself
  is fine).
- "53.4% of orgs don't understand the full scope of their AI spend."
- "41% of enterprises waste >15% of AI spend; only 7.5% embed FinOps in AI projects." *(refuted 0-3)*
- "74% already report positive GenAI ROI."
- "Hybrid pricing is the fastest-growing model; +21% median growth." *(refuted 0-3)*

**Open questions worth a follow-up run / primary research.**
1. **Buy-vs-credits mechanics by employee type, quantified** — public data describes the shift but not
   the % split of companies on seats vs central-credits vs reimbursement vs shadow, by size. This is a
   prime **customer-interview** question (and a survey we could own).
2. **Realized AI-spend waste %** — the clean "X% is wasted" stat got refuted; we need our own measured
   number (the dogfood/pilot data is how we earn it).
3. **Willingness-to-pay / take-rate** for AI-cost governance specifically (cloud FinOps benchmarks are
   the proxy; AI-native pricing is unproven).
4. **Where the budget actually sits** (Eng vs Finance vs IT) by segment — determines who we sell to first.

---

## 9. Implications for Outlay

- **Lead with the engineering/consumption wedge.** The biggest, fastest-growing, least-visible spend is
  eng on **API tokens + coding agents** — and it's exactly what metadata-only/BYOK/read-only fits. Win
  the platform/eng + FinOps buyer there first.
- **The core product is non-negotiable and is most of the TAM:** attribution → forecast → budget
  governance across multi-provider consumption spend. Nail that before enforcement/chargeback.
- **Qualify on the §3 variables;** the threshold (>$250–500k AI spend, consumption-heavy, multi-tool,
  no owner, eng-driven) is your ICP filter.
- **The regulated/gov motion** (Maryland) is a real, high-ACV *flavor* of persona #4 — but the
  **volume beachhead** is eng-heavy growth-stage software (#1–#3). Run both: gov for lighthouse ACV,
  software for velocity.
- **Earn the proof the research couldn't give us** — measured coverage + waste numbers from real pilots
  are both the product validation *and* the marketing stat that the refuted claims show is missing.
