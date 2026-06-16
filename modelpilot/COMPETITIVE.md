# Competitive landscape — ModelPilot (internal)

Researched 2026-06-11. Web-sourced; vendor claims are theirs, not verified.
This file is internal (not on the publish allowlist).

## TL;DR

Model routing is an **established category** (Martian, Not Diamond, Unify,
open-source RouteLLM, plus a long tail), and every major AI gateway has some
routing feature. Nobody we found ships ModelPilot's combination of
**session-context routing + customer-side verification** (RCT holdout,
escalation netting, side-by-side compare artifact). Position as the
**proof/assurance layer**, not "a router."

**Verified good news:** Anthropic's API docs (checked 2026-06-11) contain
**no native cost-routing product** — model choice guidance is manual, and the
only "routing" is Bedrock/Vertex geographic endpoint routing. "Fable 5 safety
routing" headlines refer to a safety measure, not cost optimization. The
platform-level router that does exist is **Microsoft Foundry's**, on Azure.

## Competitor cards

### Martian (withmartian.com) — the incumbent
- **What:** LLM router + gateway since 2023. Publishes RouterBench (the
  category's benchmark). Enterprise motion incl. Accenture partnership;
  claims engineers at 300+ companies (Amazon→Zapier).
- **Claims:** up to 98% cost savings; "100K req/mo teams save ~$3.2K/mo
  (72%)"; agent workloads 85–90%.
- **Pricing:** volume-based; enterprise by consultation (not public).
- **vs us:** Stronger: brand, scale, benchmark ownership, multi-provider.
  Weaker: per-request routing (no session-context story found); savings
  claims are vendor-benchmarked, not customer-RCT-verified.

### Not Diamond (notdiamond.ai) — the ML leader
- **What:** Trained query-level router ("hundreds of thousands of data
  points"); will train a **custom router on the customer's own evals**;
  joint prompt optimization (DSPy/SAMMO). Homepage now leads with
  "Model Routing for Coding Agents." AWS Marketplace listing.
- **Claims:** outperform any single LLM by up to 25% accuracy at up to 10×
  cost reduction; Rootly case study +39% accuracy; "30%+ cost savings."
- **Pricing:** pricing page exists but blocks scrapers — check manually
  before customer calls (notdiamond.ai/pricing).
- **vs us:** Stronger: router accuracy (trained vs our heuristic v0) — this
  is the accuracy bar corpus-v1 calibration must chase; per-customer
  training is OUR roadmap item they already ship. Weaker: optimizes, doesn't
  *verify*; no holdout/escalation-netting/compare-style audit artifact found.

### RouteLLM (LMSYS, open source) — the free baseline
- 85% cost reduction at 95% GPT-4 quality on MT-Bench. Free. Per-prompt,
  benchmark-calibrated. Expect "why not RouteLLM?" from engineer-led buyers:
  answer = ops burden + no measurement layer + no session context.

### Gateways with routing features (commodity layer)
OpenRouter (600+ models, auto-router), LiteLLM (OSS, self-hosted), Portkey,
Kong AI Gateway, Cloudflare AI Gateway, Bifrost (11μs overhead), Requesty.
Some do cache-aware passthrough. They make our *proxy plumbing* a commodity;
none make our measurement claims. Integration risk: customers already behind
one of these may want ModelPilot as a scoring/verification sidecar rather
than another proxy hop — keep the advisory API (`/modelpilot/preview`) and
declared-baseline header first-class for that.

### Platform-native
- **Anthropic:** no cost router in API docs as of 2026-06-11 (verified
  directly). Risk remains forward-looking, not current.
- **Microsoft Foundry:** ships a model router at the Azure platform level
  (Claude models are on Foundry). For Azure-committed accounts, "Foundry
  does this" is a live objection.
- **claude-code-router (OSS):** free routing specifically for Claude Code —
  our Claude Code surface has a $0 competitor; differentiation there is the
  dashboard/measurement, not the routing.

## Differentiation that held up under research

| Capability | Field | ModelPilot |
|---|---|---|
| Per-prompt routing | Everyone | Yes (commodity) |
| Session-context routing (follow-up inheritance, mechanical-task carve-out) | Not found anywhere | **Yes** |
| Cache-rewrite economics on mid-conversation switches | Cache *passthrough* exists; switch-economics not found | **Yes** |
| Customer-traffic RCT holdout with CIs | Not found | **Yes** |
| Escalation costs netted against claimed savings | Not found | **Yes** |
| Side-by-side outputs + costs + judge verdicts on customer prompts | Vendors publish own benchmarks | **Yes** (`modelpilot compare`) |
| Progressive trust (shadow→advise→autopilot) + declared-baseline tracking | Mostly autopilot-or-nothing | **Yes** |
| Trained router accuracy | Not Diamond leads | **Behind** (heuristic v0; corpus-v1 path) |
| Multi-provider | Most competitors | **Behind** (Claude-only v1; by design) |

## Objection cheat-sheet additions

- **"We already use / evaluated Martian / Not Diamond."** "They optimize;
  we verify. Ask them for a randomized holdout on *your* traffic with
  escalation costs deducted, and a side-by-side output report on *your*
  prompts. We ship both — and we'd happily measure their routing too."
- **"Why not RouteLLM (free)?"** "RouteLLM is a per-prompt router calibrated
  on benchmarks. You'd still build the measurement, governance, session
  logic, and per-tenant calibration around it — that's the product."
- **"Won't Anthropic build this?"** "As of June 2026 their docs have no cost
  router — and when they do ship one, you'll want independent verification
  of it even more. We're the layer that doesn't grade its own homework."
- **"We're on Azure; Foundry has a router."** Acknowledge; pivot to
  verification + session-context + the compare artifact on their prompts.

## Implications (priority order)

1. **Reposition: sell the proof, route as the engine.** Lead demos with
   `modelpilot compare` and the RCT dashboard, not the switching.
2. **Close the accuracy gap:** corpus-v1 calibration on customer traffic is
   now competitive necessity, not roadmap nicety; per-customer trained
   routers (Not Diamond's move) is the v1 target.
3. **Keep the sidecar path viable** (advisory API + declared baseline) for
   accounts already behind another gateway.
4. **Manual TODO before first pitches:** check notdiamond.ai/pricing and
   withmartian.com/pricing in a browser (both block scrapers); skim
   RouterBench to speak its language.

## Update — 2026-06-15 (deeper pass + OpenRouter Fusion)

**OpenRouter Fusion** (new): multi-model *ensemble* — a panel of models answers a
prompt in parallel, a judge model synthesizes. Priced ≈ **4–5× a single completion**
(sum of all panel + judge calls). It optimizes for *quality by spending more* — the
opposite of ModelPilot (route down to spend less). Reinforces our wedge: we're a
cost-DOWN layer, not an ensemble. (openrouter.ai/docs/guides/routing/routers/fusion-router)

**Pricing anchors (2026-06):** Portkey ~$49/mo Pro; Helicone $79/mo Pro ($799 Team);
LiteLLM ~$49/mo; Cloudflare AI Gateway generous free tier; OpenRouter BYOK 1M free
req/mo then **5% fee**; Martian metered (2.5k free req); Not Diamond enterprise/usage,
**SOC-2 + ISO 27001**. Performance-billing comparables: **ProsperOps** ($0.05 per $1
saved), **CloudHealth** ~3% of spend — validates our %-of-savings model. Hybrid
(subscription + usage) pricing shows the best median growth/NRR — validates our
subscription + 15% tiers.

**Martian** reportedly nearing a **$1.3B valuation** (Accenture-backed) — a well-funded
incumbent that routes ON the prompt (data path). Don't out-fund; out-position.

**Routing cost-savings claims in the wild:** 40–85% (RouteLLM ~85% at ~95% quality;
Martian "20–97%"; Not Diamond "30%+"). Our differentiator isn't a bigger % — it's that
ours is **measured against a held-out control** and **non-inferiority-checked on the
customer's own traffic** (0% false-downgrades on the golden set), so it's auditable, not
a brochure number.

### How ModelPilot compares across the WHOLE field (gateways + routers)
Three structural wedges **no competitor we found combines**:
1. **Prompts never leave the customer's system.** We classify *locally* and send only
   metadata. The entire router/gateway category structurally must SEE the prompt to route
   it (Martian, Not Diamond, OpenRouter, Unify, Requesty all route on the prompt → it's in
   their data path). This is our hardest-to-copy edge.
2. **Pay only for realized savings** (20% / 15%). Others bill usage, token markup, % of
   spend, or flat subscription — they win when spend rises; we win when it falls.
3. **Proof, not promises** — RCT control arm + per-customer non-inferiority judging.

Plus: BYOK (keep your Anthropic account), **fail-open**, and depth on the Claude family.

**Honest read:** crowded, hot, well-funded category. We will not out-breadth OpenRouter
or out-fund Martian. The defensible wedge is the **privacy architecture + pay-for-savings
+ Claude specialization** combo. Lead with privacy ("route without ever seeing your
prompts") — it's the one claim the rest of the field can't make.

---

## Deep research update — 2026-06-16 (5-stream web research, adversarially verified)

Multi-agent web research (Martian/NotDiamond, OpenRouter, gateways, routing technique,
privacy/defensibility). Sources prioritized 2025-2026; confidence + UNVERIFIED flags carried.
This update **corrects earlier claims** and is deliberately un-flattering — truth to act on.

### Corrections to prior assumptions (and to the live landing table)
- **The ~$1.3B valuation is OpenRouter's, NOT Martian's.** OpenRouter raised a $113M Series B
  led by CapitalG (Alphabet) at ~$1.3B, May 2026 (TechCrunch/BusinessWire — HIGH). The Martian
  $1.3B traces to a single retail-investor Medium post — DEBUNKED. **Martian is ~$9M seed-stage**
  (NEA, Sept 2024; Accenture *Ventures invested*, did not acquire). Fixed on the site.
- **OpenRouter is ~400+ models / 60+ providers**, not "600+" (their own docs say 400+/300+).
  Fixed on the site (we had "600+").
- **"Route without seeing the prompt" is NOT unique.** Earlier docs called it the one claim
  "the rest of the field can't make" — that's overstated. Not Diamond (client-side routing +
  fuzzy hashing + VPC/local + SOC2/ISO), and self-hosted LiteLLM/Portkey (no-egress when you run
  them), already keep prompt data local. **Privacy architecture is closer to table-stakes than a
  moat; it's copyable in ~1-2 quarters.** Treat it as a *feature in a bundle*, not THE moat.

### Per-competitor (verified highlights)
- **Martian** — predicted-best-model router that **reads the prompt**; hosted gateway (prompts
  transit it). $9M seed (NEA), Accenture Ventures partner ("Airlock" compliance suite + enterprise
  distribution). Claims "20-97%"/"beats GPT-4" — self-referential (own RouterBench). Independent
  **RouterArena (2025) ranks Martian's published methods mid/low-pack** (#16-19), below Azure's
  router. No verified self-host/SOC2/HIPAA. Does well: research credibility, Accenture channel.
- **OpenRouter** — marketplace/gateway, ~400+ models/60+ providers; **at real scale (~25T
  tokens/wk, ~$1.3B)**. Auto-router is NotDiamond-powered and reads the prompt (privacy-preserving
  fuzzy-hash claim). **Fusion = multi-model ENSEMBLE, ~4-5x cost-UP** (confirmed; opposite of a
  cost router). BYOK: **1M free req/mo then 5%** (confirmed). Prompts transit their servers; ZDR
  mode + EU "Sovereign AI" routing; SOC2/HIPAA/BAA/self-host UNVERIFIED (a third-party profile
  listing FedRAMP etc. looks overstated). Does well: breadth, failover, DX, scale.
- **Not Diamond** — **closest privacy peer.** Client-side SDK (completions go direct to provider),
  fuzzy hashing so "never sees raw query strings," **VPC + local/on-prem, SOC2 + ISO 27001, ZDR**.
  Nuance: the routing *decision* is hosted by default (input reaches them unless ZDR/local).
  Predicted-best-model, reads prompt. Strategic distribution: IBM Ventures + SAP.iO + AWS
  Marketplace. Claims "30%+/up to 10x" (self-referential). RouterArena reportedly ranks it low
  (#12, "picks expensive models" — MEDIUM). Does well: trainable custom routers, low latency,
  prompt-adaptation, compliance posture.
- **LiteLLM** — OSS self-hostable gateway. **Shipped auto cost-down routing in 2025** (Auto-Router
  stable Jul 2025; Adaptive Router beta, 7 task types, quality-vs-cost weights). Self-host = true
  no-egress (their existing pitch). **Compliance credibility collapse:** SOC2/ISO issued by "Delve"
  (fake-compliance-as-a-service, imploded ~2026) + a Mar 2026 PyPI supply-chain compromise. Free
  OSS; enterprise pricing unpublished (a "$49/mo" figure is UNVERIFIED/likely false).
- **Portkey** — OSS gateway (**fully open-sourced Mar 2026**) + managed. **Has the full regulated
  stack: SOC2/ISO/GDPR/HIPAA + custom BAA, air-gap/VPC.** Routing is manual rule config + semantic
  caching (no auto quality-gated downgrade). Could add cost routing trivially.
- **Helicone** — **sunsetting** (acquired by Mintlify, Mar 2026, maintenance-only). Observability +
  caching; OSS self-host. Not a cost-down model router.
- **Cloudflare AI Gateway** — hosted edge; Dynamic Routing (Aug 2025, by latency/cost/availability),
  caching, budgets, DLP content inspection. Auto task-based cheapest-model routing = roadmap, not GA.
  Not self-hostable. Core free.
- **Vercel AI Gateway** — hosted; **0% token markup** (headline), ZDR by default; routes among
  providers of the *same* model (not cheaper-substitute). OpenRouter dropped fees in response.
- **Unify** — **PIVOTED OUT of LLM routing** to GTM/sales agents. Cautionary tale: the standalone
  pure-router business is commercially fragile.
- **Requesty** — active hosted cost-routing gateway / OpenRouter alternative; "~40% savings"
  (vendor marketing, UNVERIFIED); proprietary SaaS, prompts transit.
- **Provider-native (the structural threat):** **AWS Bedrock Intelligent Prompt Routing is GA and
  routes WITHIN the Claude family (Sonnet<->Haiku) for ~30% — built-in, free.** GPT-5 ships a
  built-in real-time router. Databricks AI Gateway routes/combines models. Anthropic's own caching
  (~90%) + Batch (~95%) capture most savings first-party (our auto-cache even helps customers do it).

### Honest defensibility verdict
- **Weak/copyable:** the privacy architecture (peers have it), the cost-routing mechanic (LiteLLM
  shipped it; providers ship it free), Claude-only depth (also a TAM/single-vendor limiter).
- **Genuinely differentiated:** **pay-on-realized-savings billing — no competitor does it** (all
  bill seat/usage/subscription/markup). Wins trust when spend FALLS; aligns incentives.
- **Credibility opening (timing):** vendor savings claims are inflated and **independently
  debunked** (RouterArena shows routers underdeliver; LLM-judge leniency is a documented hole).
  LiteLLM's compliance is discredited (Delve); Helicone is sunsetting; Unify exited. An **honest,
  substantiated (control-arm) savings + clean compliance** story can win *right now*.
- **Real but narrow openings:** managed, drop-in, zero-config for teams that won't run LiteLLM;
  buyers who reject ANY egress even with a BAA (narrow — most accept BAA+ZDR from Anthropic).

### Steelman against us (internalize)
1. Provider-native routing (Bedrock intra-Claude GA ~30%; GPT-5 router) absorbs the core wedge free.
2. Anthropic caching/batch capture most savings without us or our fee.
3. Regulated buyers increasingly accept egress under BAA+ZDR (Anthropic signs BAAs, offers ZDR).
4. Privacy architecture isn't unique (Not Diamond, self-hosted OSS) and rivals have stronger certs.
5. Claude-only shrinks TAM + single-vendor risk; can't route to a cheaper non-Claude model.
6. Pay-on-savings depends on a contested counterfactual baseline — procurement may distrust it.
7. Routing is commoditizing toward zero margin (Vercel 0%, Cloudflare free, OSS).

### So why we can still win (narrowed, honest)
Not "the only private router." The defensible play = **the combination, aimed narrowly**:
**incentive-aligned pay-on-realized-savings + honest/audited (control-arm) savings + managed
drop-in + Claude-family depth + no-egress-by-architecture**, sold to the **regulated, Claude-heavy,
won't-DIY** buyer — and racing to **harden the real moats**: SOC2/HIPAA/BAA certs (peers already
have them — this is now table stakes, not optional), per-customer embeddedness/switching cost, and
defensible savings measurement. De-risk the Bedrock/native-routing threat by being cross-cutting
(works regardless of where they run Claude) and by competing on *proof + alignment*, not the
routing mechanic.

### Action items surfaced
- [x] Fix site: "600+"->"400+/60+"; Martian "$1.3B/✓ mature"-> "~$9M seed / ~ early-stage".
- [ ] Stop calling "route without seeing prompts" unique anywhere in copy; reframe as a *bundle*.
- [ ] Make **pay-on-realized-savings** the lead differentiator (it's the genuinely unique one).
- [ ] Prioritize SOC2/HIPAA/BAA (now competitive table stakes, not a future nicety).
- [ ] Add a direct **vs. Not Diamond** comparison (closest peer) to /compare.
- [ ] Address the **AWS Bedrock intra-Claude routing** threat explicitly in positioning.
- [ ] Re-verify (manual, primary-source) before any external use: Not Diamond no-egress default,
      Portkey ZDR/BAA, LiteLLM post-incident compliance, Requesty/Martian pricing + compliance.
