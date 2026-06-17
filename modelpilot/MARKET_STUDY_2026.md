# LLM Cost-Optimization, Model-Routing & AI-Gateway Market — Independent Study (June 2026)

*A neutral industry analysis of the players, their economics, and what drives success in this
category. Written as a market study, not a positioning document — it deliberately does not
reference our own product. Every funding/pricing/traction figure is flagged **[FACT]**
(primary or well-corroborated) or **[CLAIM]** (vendor marketing / single-source / estimate).
Compiled from ~11 parallel source-verified research passes; most vendor sites returned HTTP 403
to automated fetch, so figures rest on cross-checked search extracts of primary pages plus live
GitHub/SEC reads. Re-verify exact dollars against live pages before external use.*

---

## 1. The category is four overlapping segments, not one

"AI gateway / routing" is loosely used to describe products that actually do different jobs.
They overlap at the edges but win on different things:

1. **Pure model routers** — decide, *per request*, which **model** to call (cheapest that's
   good enough). Martian, Not Diamond, RouteLLM (OSS reference), Unify (exited), Pulze.
2. **Unified gateways / marketplaces** — one API/key in front of many models; route by
   **provider/price**, add fallbacks, caching, budgets, keys. OpenRouter, LiteLLM, Portkey,
   Vercel AI Gateway, Cloudflare AI Gateway, Requesty, Kong, TrueFoundry, nexos.ai.
3. **Observability / eval** — sit *beside* the request path to trace, measure, and evaluate;
   they track cost but never pick a model. LangSmith, Langfuse, Datadog, Arize/Phoenix,
   Traceloop/OpenLLMetry, Helicone (hybrid).
4. **Provider-native features** — the cost levers the clouds and model vendors ship themselves.
   AWS Bedrock, Anthropic, OpenAI, Google Vertex, Azure Foundry.

The single most important structural fact: **the big money has flowed to the gateway/marketplace
and observability segments, while pure routing has stayed seed-stage** — and several pure routers
have either pivoted out (Unify) or rank poorly on independent benchmarks (Not Diamond). Routing
*as a standalone product* is the weakest commercial position in the category.

---

## 2. Funding & status leaderboard (verified)

| Company | Segment | Funding (latest) | Valuation | Status | Source flag |
|---|---|---|---|---|---|
| **OpenRouter** | Marketplace/gateway | Series B **$113M**, CapitalG, May 2026 (~$153M total) | **$1.3B** | Independent, scaling | [FACT] |
| **Vercel** (AI Gateway + AI SDK) | Gateway + dev toolkit | Series F **$300M**, Accel/GIC, Sep 2025 | **$9.3B** (company) | Independent | [FACT] |
| **LangChain / LangSmith** | Observability/eval | Series B **$125M**, IVP, Oct 2025 (~$160M total) | **$1.25B** | Independent | [FACT] |
| **Kong** (AI Gateway) | Gateway (API-mgmt incumbent) | Series E **$175M**, Tiger, Nov 2024 (~$345M total) | **$2B** | Independent | [FACT] |
| **Arize** (Phoenix) | Observability/eval | Series C **$70M**, Adams Street, Feb 2025 (~$131M total) | n/a (no confirmed) | Independent | [FACT] |
| **nexos.ai** | Enterprise gateway | Series A **€30M (~$35M)**, Evantic/Index, Oct 2025 (~$43M total) | ~€300M [CLAIM] | Independent | [FACT]/[CLAIM] |
| **Martian** | Pure router | **$9M** seed, NEA, Nov 2023 + Accenture Ventures, Sep 2024 | "$1.3B nearing" = **RUMOR** | Independent; drifting to interpretability/safety | [FACT] seed; [CLAIM] val |
| **Portkey** | Gateway/control plane | $3M seed + **$15M** A, Elevation (~$18M) | undisclosed | **Acquired by Palo Alto Networks, May 2026** | [FACT] |
| **Helicone** | Observability + gateway | **$5M** seed @ ~$25M, YC, Sep 2024 | ~$25M | **Acquired by Mintlify, Mar 2026** (maintenance mode) | [FACT] |
| **Langfuse** | Observability (OSS) | **$4M** seed, Lightspeed, Nov 2023 | undisclosed | **Acquired by ClickHouse, Jan 2026** | [FACT] |
| **Traceloop** (OpenLLMetry) | Observability (OTel) | **$6.1M** seed, May 2025 | undisclosed | **Acquired by ServiceNow, Mar 2026** | [FACT] |
| **Not Diamond** | Pure router | **$2.3M** pre-seed, Defy, Jul 2024 + undisclosed IBM/SAP strategic, May 2025 | undisclosed | Independent; narrowing to coding agents | [FACT] seed |
| **LiteLLM** (BerriAI) | Gateway (OSS) | **$1.6M** seed, YC W23, 2023 | undisclosed | Independent; high OSS adoption | [FACT] |
| **Requesty** | Gateway (EU governance) | **$3M** seed, 20VC, Sep 2025 | undisclosed | Independent; ~5 employees | [FACT] |
| **Unify** | (ex-)router | **$8M** seed, mid-2024 | undisclosed | **Pivoted out of routing → AI agents** | [FACT] |
| **RouteLLM** (LMSYS) | OSS research | none (Apache-2.0) | n/a | Reference design, ICLR 2025 | [FACT] |
| **Datadog** / **Cloudflare** | Obs / gateway | public (DDOG / NET) | $81B / $82B mkt cap | Features within large platforms | [FACT] |

**Consolidation wave (the headline of the last 12 months):** five independent players were
acquired between Sep 2025–May 2026 — **OpenPipe→CoreWeave** (Sep 2025), **Langfuse→ClickHouse**
(Jan 2026), **Helicone→Mintlify** (Mar 2026), **Traceloop→ServiceNow** (Mar 2026), and
**Portkey→Palo Alto Networks** (May 2026). The middle of this market is being absorbed into
GPU clouds, databases, docs platforms, ITSM, and security suites. This is the clearest possible
signal that "a gateway or an observability tool" is increasingly a *feature of a larger platform*,
not a standalone company — except at the very top (OpenRouter, LangChain, Together) where scale
created an independent destination.

**Adjacent players worth tracking** (gateway is secondary to their core): **Together AI** — the
largest independent open-model inference cloud, **$305M Series B at $3.3B** (Feb 2025, NVIDIA-backed);
its "single API to 200+ models" is a real gateway surface but bound to its own hosted fleet (no
closed frontier models). **Braintrust** — eval/observability with an OSS proxy on the side, **$36M
Series A** (a16z, Oct 2024), the best-funded eval pure-play. **OpenPipe** — fine-tuning/RL with a
proxy on-ramp, acquired by CoreWeave. **Eden AI** — a full-stack AI-API aggregator (LLM + OCR/
speech/vision), small (~€3M seed, ~22 staff), differentiated by covering the *whole* AI stack, not
just chat.

---

## 3. Segment-by-segment: what they do and why they've won

### 3a. Unified gateways & marketplaces — the segment that produced the winners

**OpenRouter** is the category's breakout. One OpenAI-compatible endpoint in front of **~400+
models / 60+ providers** [FACT], **zero markup on tokens**, monetized on a **~5.5% credit-purchase
fee (5% crypto)** and a **BYOK fee (5% after 1M free requests/mo)** [FACT]. It processes
**~25–29 trillion tokens/week** (≈5× growth in six months) [FACT] and ~**$50M ARR** [CLAIM, Sacra
estimate]. Why it won:
- **Distribution & default status** — OpenAI compatibility makes switching ~one line of code; it
  became the default "one key for every model" for indie devs and AI-native startups.
- **Speed-to-list** — new frontier and Chinese open models appear within days of release.
- **The rankings flywheel** — its public token-usage leaderboard is cited industry-wide, making
  OpenRouter the neutral *scoreboard* of the LLM market → continuous free press → more data → more
  authority. This is its real moat, and it's a *data/distribution* moat, not a routing-tech moat.
- **Asset-light economics** — no GPUs; ~5% take on payment flow at edge scale = high margin.
- **BYOK-as-anti-churn** — turns customers graduating to direct provider contracts into a revenue
  line instead of lost accounts.

**Vercel AI Gateway + AI SDK** shows the other winning shape: a **free open-source developer
wedge** (the AI SDK, ~25K GitHub stars, tens of millions of weekly installs) funneling into a
**zero-markup hosted gateway** ("hundreds of models," **$5/mo free credits**) [FACT]. The moat is
**Next.js** — Vercel owns the dominant React meta-framework and cross-sells AI into a captive
developer base. Company raised a **$300M Series F at $9.3B** (Sep 2025) [FACT]. The gateway reports
routing tens of trillions of tokens/month across **200K+ teams** [CLAIM, vendor index], with a
heavily **agentic** workload mix.

**LiteLLM (BerriAI)** is the open-source standard for the proxy layer: MIT-licensed,
OpenAI-compatible across 100+ providers, **~45K+ GitHub stars, 240M Docker pulls, 1B+ requests**,
adopted by Netflix/Adobe/Stripe [FACT funding/stars; CLAIM logos]. Tiny seed (**$1.6M**, YC W23)
but enormous developer mindshare — the classic OSS-flywheel infra play; monetizes via an enterprise
tier on top of the free proxy.

**Portkey** bundled gateway + observability + guardrails + governance into a "control plane,"
fully open-sourced the gateway (MIT, ~12.1K stars) in Mar 2026, and was **acquired by Palo Alto
Networks (May 2026)** to become the AI gateway for its Prisma AIRS security platform. It monetized
on **logged-request volume + enterprise contracts** — explicitly *not* a percentage-of-savings
model. Its exit was driven by the **agent-governance/security** angle.

**Kong** and **Cloudflare** are incumbents extending existing distribution. Kong layers AI plugins
(semantic caching, model load-balancing, token governance) onto its **43.6K-star** API gateway and
$2B-valuation install base — an upsell, not a new vendor. Cloudflare AI Gateway is a **free**
observability/control plane (logging, caching, rate limits, spend caps, guardrails, rule-based
"Dynamic Routing") riding its **330+ city network and ~265K+ paying customers**; it's a loss-leader
on-ramp to Workers. Neither does quality-aware "cheapest good-enough model" routing — both do
rule/fallback routing.

**Requesty** and **nexos.ai** are the *enterprise-governance + EU-data-residency* challengers.
Requesty markets itself as "the OpenRouter alternative Europe has been waiting for" (RBAC, SOC 2
Type II, EU/APAC residency) but is genuinely small (~5 people, $3M). nexos.ai (Nord Security
founders, ~$43M raised) attacks the **"Shadow AI"** governance problem and is the better-capitalized
of the two. **TrueFoundry** bundles the gateway into a full MLOps/BYOC platform (250+ models,
runs in the customer's own cloud), $19M Series A.

### 3b. Pure model routers — strong tech, weak commercial position

**Martian** ("invented the first LLM router") routes per-query using proprietary "Model Mapping"
(mechanistic-interpretability) and has a genuinely valuable **Accenture** distribution channel
(embedded in Accenture's "switchboard"). But only **$9M is cleanly documented** (the $32M total is
aggregator-grade, the **$1.3B valuation is an unconfirmed rumor**), there are no hard traction
numbers, and the company is visibly drifting toward interpretability/AI-safety research — a possible
soft pivot away from a commoditizing router market.

**Not Diamond** has elite signaling (angels: Jeff Dean, Ion Stoica, Tom Preston-Werner; design
partners IBM & SAP) and real technical depth (predictive routing without calling all models, plus
prompt adaptation). But it has raised only **$2.3M confirmed**, the independent **RouterArena
benchmark (Oct 2025) ranks it #12** and notes it "frequently selects expensive models" — directly
undercutting the savings pitch — and it has narrowed to "**model routing for coding agents**" to
find defensibility.

**RouteLLM** (LMSYS/Berkeley) is the **open-source, ICLR-2025 peer-reviewed reference design** for
the whole segment (matrix-factorization router; "~95% of GPT-4 quality at ~26% of GPT-4 calls").
Its impact is intellectual, not commercial — it legitimized the technique and gave everyone a free
baseline, which *commoditizes the core routing IP* that pure-play startups try to sell.

**Unify** is the cautionary tale: started as an LLM router (YC W23, $8M seed), then **abandoned
routing entirely** for an agentic "AI workers" product — direct evidence that the standalone-router
thesis is hard to monetize.

### 3c. Observability / eval — the most active consolidation target

None of these route or pick models; they trace, measure, and evaluate. The pattern is
**OpenTelemetry-as-substrate** + an OSS or free wedge → enterprise. The notable fact is how many
exited in 2026:
- **LangSmith** (LangChain) — the leader; **$125M Series B @ $1.25B** on the back of a ~140K-star
  framework that is the default agent on-ramp.
- **Langfuse** — full-featured MIT OSS (~29K stars), **acquired by ClickHouse (Jan 2026)**.
- **Traceloop / OpenLLMetry** — Apache-2.0 OTel-native instrumentation, **acquired by ServiceNow
  (Mar 2026)**.
- **Helicone** — OSS observability + a Rust gateway (one of the few here that *does* price/cost
  routing), **acquired by Mintlify (Mar 2026)**, now maintenance mode.
- **Arize/Phoenix** — ML-observability heritage, created the OpenInference standard, **$70M Series
  C**; still independent.
- **Datadog** — observes LLM calls as an add-on to its $3.43B-revenue platform; wins purely on
  **bundling** into a 32,700-customer install base.

### 3d. Provider-native features — the commoditization engine

The clouds and model vendors now ship the cost levers directly:
- **Caching is table stakes everywhere** — Anthropic/Vertex/Bedrock ~**90% off** cached reads;
  OpenAI **50%**. A gateway that merely "adds caching" on one provider offers little.
- **Batch is a universal flat 50% off** — no third party can beat a list discount; they can only
  orchestrate it.
- **Intra-family routing** is now first-party: **AWS Bedrock Intelligent Prompt Routing** (GA Apr
  2025, same-family only, "up to 30%" [CLAIM]), **Vertex Model Optimizer** (Gemini-only, pre-GA),
  and **GPT-5's internal router**. These directly substitute the most common pure-router pitch for
  single-provider customers.
- **The exception that matters: Azure Foundry Model Router** is the **only first-party feature doing
  genuine cross-vendor routing** (~18 models across OpenAI, Anthropic, DeepSeek, Meta, xAI, with
  Balanced/Cost/Quality strategies). It's the single biggest first-party threat to neutral gateways
  — offset only by Azure/single-cloud lock-in.

**Where first-party stops:** cross-provider/multi-cloud routing, vendor-neutral abstraction, and —
critically — **independent, audited, customer-specific proof of savings**. No model vendor is
incentivized to prove you're overspending on its own models, and every "up to 30%/90%" figure is a
best-case marketing number, not a measured one.

---

## 4. What actually drives success in this category

Synthesizing across all players and dev-infra history (a16z/Bessemer patterns, CDNs, API gateways,
payments):

1. **Bottom-up developer distribution beats everything.** Every winner led with a free/OSS wedge
   and drop-in, OpenAI-compatible integration: OpenRouter (free tier + one-line swap), Vercel (AI
   SDK), LiteLLM/Langfuse/Portkey (OSS), LangSmith (the framework). Procurement-led routers without
   a dev wedge (the pure routers) stayed small.
2. **A data or distribution flywheel is the real moat — not the routing algorithm.** OpenRouter's
   leaderboard, Vercel's Next.js base, Kong's install base, Datadog's platform, LangChain's
   framework. The routing/gateway *mechanism* is commoditizing (RouteLLM is free, the clouds ship it
   natively); durable advantage comes from owning distribution or a unique dataset.
3. **Pricing is converging on zero-markup + a thin take or enterprise contracts.** OpenRouter
   (~5% on payment flow), Vercel (0% markup), Cloudflare (5% on credits) all pass tokens through at
   list and monetize elsewhere. Markup-on-tokens models (some routers' ~5%) are under pressure.
   Notably, **no major player prices on *realized savings*** — the category bills on volume, seats,
   logs, or payment flow.
4. **Value is migrating *up* from routing to governance, attribution, and trustworthy
   measurement.** The acquisitions (security, ITSM, analytics DB, docs) all bought the
   *governance/observability* layer, not the routing layer.
5. **Timing + a sharp wedge.** The winners rode the 2024–2026 model-proliferation and agent waves;
   the freshest wedges that attracted capital/acquirers are **agent governance** (Portkey→PANW,
   nexos "Shadow AI") and **coding agents** (Not Diamond's pivot).

---

## 5. The demand side is real, board-level, and the best-substantiated part of the thesis

- **FinOps-for-AI has gone mainstream.** Share of FinOps teams managing AI spend: **~31% (2024) →
  63% (2025) → 98% (2026)**, now their **#1 forward-looking priority** (FinOps Foundation, State of
  FinOps 2026) [FACT — primary survey, the strongest single data point in the study].
- **The macro bill is exploding.** OpenAI inference spend ~**$3.8B (2024) → ~$8.65B in 9 months of
  2025**; 2025 losses **$38.5B** (audited, per FT) [FACT]. This is the visceral proof cost control
  is a board line.
- **The cost paradox.** Per-token prices fall ~**10×/year** ("LLMflation," a16z) yet total bills
  rise because usage scales faster — a Jevons dynamic [FACT/illustrative]. Implication: demand for
  *governance and attribution* grows, but demand for "just find me a cheaper model" *erodes over
  time* as the per-unit problem shrinks.
- **Market sizing is directional only.** No top-tier analyst sizes "LLM cost routing" as its own
  market. LLMOps ~$5.2B→$19.8B (21% CAGR) and AI gateway ~$2.4–3B→$8.7–15B are second-tier
  estimates with wide variance [CLAIM-ish]. The *substrate* (GenAI models >$25B in 2026 → $75B by
  2029, Gartner) is credibly large [FACT].

---

## 6. The trust/measurement problem — the category's structural weakness

- **Quality regression from cheaper models is documented, not hypothetical.** Routing research
  (RouterArena; LLMRouterBench 2026; "Towards Fair Evaluation of Routers" 2026) finds SOTA routers
  "misrank candidates and select the wrong LLM," degrade under distribution shift, and depend on
  domain-specific training data; below ~**80% judge reliability** performance drops sharply [FACT].
- **Benchmark savings ≠ production savings.** RouteLLM's headline "85% savings at 95% GPT-4 quality"
  is benchmark-specific (MT-Bench/2024 model pairs) yet travels far beyond its validity. The right
  metric is **cost per *successful task***, not cost per token — a cheaper model that fails 30% of
  the time is more expensive once rework is counted [FACT/well-argued].
- **Buyers are primed to distrust AI-ROI claims** (the disputed-but-viral MIT "95% of GenAI pilots
  show no ROI" study). In that climate, **verifiable, audited savings are a differentiator rather
  than a commodity** — and it's precisely the thing no provider-native feature and few third parties
  actually deliver.

---

## 7. Where the market is heading (12–24 months)

- **Pure routing → a feature, not a company.** Compressed from three sides simultaneously: clouds
  (Azure cross-vendor router, Bedrock/Vertex intra-family), model vendors (native caching/batch +
  how-to guides that teach the optimization), and observability/infra suites that bundle it. RouteLLM
  makes the IP free. Expect continued absorption.
- **Gateways consolidate into platforms** (security, ITSM, data, docs, clouds) — the 2026
  acquisition wave continues; standalone survival requires OpenRouter/LangChain-level scale and a
  distribution flywheel.
- **The defensible layers are above routing:** (a) genuine multi-vendor/multi-cloud neutrality
  (avoiding the Azure lock-in tax), (b) **governance/attribution** (the layer acquirers paid for),
  and (c) **independent, auditable savings measurement with visible quality safety** — the trust gap
  no incumbent is incentivized to close.
- **Pricing innovation is the open lane.** The whole category bills on volume/seats/logs/payment
  flow; *outcome- or savings-aligned pricing* aligns with FinOps's shift to "value-delivered" KPIs
  and is conspicuously unoccupied by the major players.

---

## 8. Data-quality caveats

- Most vendor and news sites returned **HTTP 403** to automated fetch; figures are cross-checked
  search extracts of those primary pages plus live GitHub/SEC reads. Treat single-sourced numbers
  (Martian $32M total / $1.3B; Requesty 70k devs / 90B tokens; most "tokens/day" and "% savings"
  marketing) with caution — flagged inline.
- **Confirmed via primary/live sources:** all four 2026 acquisitions; OpenRouter Series B
  ($113M/$1.3B, CapitalG); Vercel Series F ($300M/$9.3B); LangChain Series B ($125M/$1.25B); Kong
  Series E ($175M/$2B); Arize Series C ($70M); Martian $9M seed (NEA); Not Diamond $2.3M (Defy);
  the FinOps-for-AI 31%→98% progression; provider-native caching/batch/routing mechanics; GitHub
  star counts; RouterArena #12 ranking of Not Diamond.
- **Do not conflate Martian with OpenRouter.** Martian's *only* rock-solid funding number is its
  **$9M seed (Nov 2023, NEA)**. The "$1.3B" — and very likely the "$500M" — valuations attached to
  Martian in AI-blog/Medium coverage are **OpenRouter's** figures (its Series A ~$500M and Series B
  $1.3B) bleeding over; the $32M total and "$40.5M raised in 2025" are aggregator/single-snippet and
  unverified. Treat Martian as a seed/early-Series-A company until a primary round announcement says
  otherwise.
- Market-sizing figures are second-tier and directional. The Gartner API-demand-from-LLMs stat is
  from Mar 2024 and near its horizon — refresh before quoting.
