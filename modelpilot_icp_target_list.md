# ModelPilot — SF Seed/Early-Stage Target List (first-party Claude likely, not Bedrock)

_Research date: June 2026. Compiled from multi-angle web research (Anthropic-published sources, recent YC batches, funding press, eng/job signals, use-case clusters). ~44 qualifying companies + adjacent/excluded appendix._

---

## ⚠️ Read this first — methodology & honesty limits

- **"Doesn't have Bedrock" is NOT publicly verifiable.** No company publishes its cloud/LLM wiring. This list is built on *positive signals of first-party Anthropic/Claude usage* and AI-native SF seed profile. **No Bedrock claim is made about any company.**
- **First-party likelihood is rated High / Med / Low** with the evidence shown:
  - **High** = product literally wraps Claude (e.g., "interface for Claude Code"), Anthropic is an investor, or explicit multi-provider config naming Anthropic.
  - **Med** = Claude named among tools, "Claude's Corner"/Anthropic-adjacent coverage, or strong category fit + Claude positioning.
  - **Low** = category/use-case fit only; provider undisclosed.
- **Key finding:** stealthy seed startups rarely disclose their model provider. So for many, the honest play is to **lead outreach with the cost-of-inference value prop**, not assume a Claude-specific bill. Prioritize the **High-confidence confirmed-Claude** names for the cleanest fit.
- Sources: anthropic.com / claude.com / ycombinator.com frequently 403'd direct fetch, so many facts come from search snippets + third-party profiles (Crunchbase, LinkedIn, TechCrunch, VentureBeat, SiliconANGLE, StartupHub). Treat funding/stage as "best public estimate"; **verify before spending money on outreach.**

---

## 🎯 Outreach priority tiers

**Tier 1 — High first-party Claude signal + strong cost-routing fit + reachable contact (start here):**
1. **Omnara** — interface for Claude Code (wraps Claude). Kartik Sarangmath (LinkedIn).
2. **21st.dev** — orchestrates *parallel* Claude Code instances (token multiplication). Serafim Korablev (LinkedIn).
3. **Paradigm** — AI spreadsheet, explicitly switches Anthropic/OpenAI/Gemini per cell at huge volume. Anna Monaco (LinkedIn).
4. **HumanLayer** — human-in-the-loop agent oversight; named in Anthropic's YC blog + Founder's Playbook. Dexter Horthy (LinkedIn).
5. **Ambral** — AI account management; named in Anthropic's YC blog + Playbook. Sam Brickman (LinkedIn).
6. **Sapiom** — agent payments infra; **Anthropic is a named seed investor**. (contact via site/Accel network.)

**Tier 2 — Med signal, clear high-volume LLM workload (great product-fit interviews + outreach):**
Castari, Replicas, Browser Use, Manufact (mcp-use), Hyper, Corvera, Unsiloed AI, Trellis AI, Melder, Midship, CodeAnt AI, Rulebase, Adaptional, Beacon Health, Bryckel AI, General Legal, Aurorin CAD, REV1.

**Tier 3 — Low signal / undisclosed provider / verify stage (cost-of-inference outreach, lower priority):**
Kilo Code (also a partial competitor), Runtime, Compyle, Dataleap (verify still pre-A), Laminar, Crafting, Minimal AI, 14.ai, Cignara, Primer, Questom, Berry, Arcline, LegalOS, VoiceCare AI, Propaya, Avoice, LunaBill, tday, Trace (⚠ name/HQ conflict — verify).

**Adjacent (partner OR competitor, not clean prospects):** SuperPenguin (AI spend tracking), Kilo Code & Castari (already building their own routing) → strong *demand validation* that ModelPilot's category is real.

---

## Profiles by sector

### A. Dev tools / coding agents  (highest token burn — agentic, long-running, often parallel)

**Omnara** — Mobile/web/voice command center for Claude Code (start on desktop, continue from phone). HQ: SF. Stage: YC S25, ~$500K, team ~2. Use: wraps Claude Code agent sessions. First-party: **High** (entire product depends on Claude Code). Pain: per-session token spend scales with always-on mobile usage; long agent loops. Angle: cap/route Claude Code spend as mobile usage scales. Contact: Kartik Sarangmath https://www.linkedin.com/in/kartiksarangmath/

**21st.dev** — Control panel to run Claude Codes in parallel (local/remote sandboxes), automate Linear/PRs. HQ: SF. Stage: YC W26, ~$500K, 370K MAU. Use: parallel Claude Code orchestration. First-party: **High**. Pain: parallel agents multiply token cost; sandbox fan-out. Angle: per-agent cost caps + routing for parallel orchestration. Contact: Serafim Korablev https://www.linkedin.com/in/serafimkorablev/

**Castari** — "Vercel for AI agents"; runtime/sandboxes for agents built on the Claude Agent SDK. HQ: SF. Stage: YC pre-seed. First-party: **Med–High** (ships `castari-proxy` to swap models behind the Claude Agent SDK — direct routing signal). Pain: per-run token cost; model-swap demand. Angle: they're already proxying models — offer proven routing + holdout vs. hand-rolled. Contact: Jacob Wright; https://www.castari.com/

**Replicas** — End-to-end background coding agents (delegate tickets via Slack/Linear/GitHub; sandboxed VMs). HQ: SF. Stage: YC S26, small; used by 20+ YC startups. First-party: **Med** (orchestrates Claude Code). Pain: highly parallel long sessions + CI-fix retry loops. Angle: route simple tickets cheap, cap feedback-loop cost. Contact: Connor Loi; https://tryreplicas.com/

**CodeAnt AI** — AI PR code review / code quality. HQ: SF (355 Bryant St). Stage: YC W24, ~$2.5M seed. First-party: **Med** (multi-model incl. Claude Sonnet; diff-only context). Pain: review runs on every PR; token scales with diff size; per-seat pricing squeezes margin. Angle: cheap model for trivial diffs, Claude for complex review. Contact: Amartya Jha; https://www.ycombinator.com/companies/codeant-ai

**Kilo Code** — Open-source agentic coding platform routing one agent across 500+ models (incl. Claude Opus/Sonnet). HQ: SF. Stage: $8M seed. First-party: **Med** (supports Claude). ⚠ **Also a partial competitor** — already markets dynamic cost routing. Angle: coopetition / proof-of-quality layer; or learn from their routing UX. Contact: @kilocode; founders Scott Breitenother, Sid Sijbrandij.

**Runtime (runtm.com)** — Governance/observability layer so non-engineers can run coding agents safely. HQ: SF. Stage: YC S26, ~3. First-party: **Low**. Pain: per-user/session spend attribution + caps. Angle: cost visibility + routing under their guardrails. Contact: https://www.ycombinator.com/companies/runtime

**Compyle** — Collaborative coding agent (Cursor/Claude Code alternative). HQ: SF. Stage: YC F25, ~2. First-party: **Low–Med**. Pain: coding agents = top token consumers (COGS). Angle: lower coding-agent COGS via routing. Contact: YC careers (Jonathan Miranda, Mark Nazzaro).

**Aurorin CAD** — AI-native mechanical CAD; "Claude code for mechanical engineers." HQ: SF. Stage: YC W26, solo. First-party: **Med** (strong Claude positioning; "Claude's Corner"). Pain: iterative design = many LLM calls/session; freemium cost control. Angle: protect freemium margins. Contact: Michael Baron (ex-SpaceX/Apple); YC careers.

**REV1** — Turns 3D CAD into 2D manufacturing drawings; "Claude Code for mechanical engineers." HQ: SF. Stage: YC W26, ~2. First-party: **Med**. Pain: per-drawing vision+reasoning, scales with output. Angle: cost-efficient routing for high-volume drawing gen. Contact: Alex Rivero https://www.linkedin.com/in/alex-rivero-sabiote/ , Louis Liu https://www.linkedin.com/in/louis-sp-liu/

### B. AI agents & infrastructure

**HumanLayer** — Human-in-the-loop oversight/approvals for AI agents (+ CodeLayer). HQ: SF. Stage: YC F24, seed, ~3–6. First-party: **High** (Anthropic YC blog + Founder's Playbook). Pain: agent workflows; context engineering. Angle: routing + spend control for agent platforms. Contact: Dexter Horthy https://www.linkedin.com/in/dexterihorthy/

**Sapiom** — Payments/auth infra so agents can buy tools/APIs/compute. HQ: SF. Stage: $15.75M seed (Accel, Feb 2026). First-party: **High** (Anthropic is a named investor). Pain: per-call agent economics. Angle: warm intro via Anthropic investor tie; routing as a cost line in agent transactions. Contact: founder Ilan Zerbib (LinkedIn).

**Browser Use** — Open-source + cloud browser/computer-use agents. HQ: SF. Stage: $17M seed, YC W25. First-party: **Med** (Anthropic reported as a user). Pain: many sequential LLM calls/task; long DOM context. Angle: route simple page steps cheap; cut per-step cost. Contact: https://browser-use.com/ (Gregor Zunic, Magnus Muller).

**Manufact (mcp-use)** — SDK + cloud for MCP servers / "MCP apps for ChatGPT & Claude." HQ: SF + Zurich. Stage: YC S25, $6.3M seed. First-party: **Med** (Claude a first-class target, multi-provider). Pain: multi-provider routing/observability is core. Angle: complementary routing layer (partner/customer). Contact: Pietro Zullo https://www.linkedin.com/in/pietrozullo/

**Hyper** — "Company brain" memory feeding Claude Code/Cursor on every chat turn. HQ: SF. Stage: YC P26, small. First-party: **Med** (Claude Code primary integration). Pain: per-turn enrichment = high LLM volume; synthesis over millions of docs. Angle: cut synthesis cost on per-turn enrichment. Contact: Shalin Shah https://www.linkedin.com/in/shalins/

**Laminar** — Open-source observability/debugging for long-running agents. HQ: SF. Stage: YC S24, $3M seed. First-party: **Low** (model-agnostic). Pain: already captures per-call token/cost. Angle: their customers feel the pain — partner on cost-aware visibility→routing. Contact: https://laminar.sh/ (Robert Kim, Dinmukhamed Mailibay).

**Crafting** — Infra for "agentic engineering" (agents write/test/ship against real infra). HQ: SF (likely). Stage: $5.5M seed (Mar 2026). First-party: **Low**. Pain: large repo context + iterative test/fix turns. Angle: route routine steps cheap. Contact: unknown (globenewswire release).

**Dataleap** — Agentic OS giving non-eng "Claude Code superpowers." HQ: SF. Stage: YC S24/2023 — ⚠ **verify still pre-Series A**. First-party: **Med**. Pain: non-tech users → unpredictable per-seat token spend. Angle: per-seat caps + routing. Contact: Jan-Hendrik Ruettinger https://www.linkedin.com/in/janruettinger/

### C. Customer support / CX & Sales / GTM  (volume kills margin)

**Ambral** — AI account-management/customer-success "team." HQ: SF. Stage: YC S25, pre-seed/seed. First-party: **High** (Anthropic YC blog + Playbook; Claude Code + Agent SDK). Pain: multi-subagent research loops. Angle: route the research fan-out; cap agent cost. Contact: Sam Brickman https://www.linkedin.com/in/sam-brickman-086341136/ , Jack Stettner.

**Rulebase** — AI coworker reviewing 100% of bank/fintech customer interactions for compliance/QA. HQ: SF. Stage: YC F24, $2.1M pre-seed. First-party: **Med**. Pain: **100%-of-interactions classification** = extreme volume; structured scoring. Angle: cheap classifier for full coverage, frontier only on flagged. Contact: Chidi Williams, Gideon Ebose (LinkedIn).

**Minimal AI** — Automates ~90% of e-commerce support tickets. HQ: SF. Stage: YC S25, $3.6M seed. First-party: **Low–Med**. Pain: huge ticket classification + RAG volume. Angle: Haiku-tier bulk triage, premium for hard tickets. Contact: Titus Ex, Niek Hogenboom (LinkedIn).

**14.ai** — AI-native support agency replacing support teams. HQ: SF (likely). Stage: $3M seed (General Catalyst, SV Angel). First-party: **Low–Med**. Pain: many tenants, agency margin = per-ticket model cost. Angle: routing lifts gross margin directly. Contact: Michael Fester, Marie Schneegans (LinkedIn).

**Cignara** — Enterprise voice/chat agents for support + sales. HQ: SF. Stage: YC P26, ~$500K. First-party: **Med**. Pain: agentic voice+chat loops; RAG; structured actions. Angle: route routine turns cheap, premium for high-stakes upsell/retention. Contact: Nalin Gupta (LinkedIn).

**Primer** — AI agent for live personalized product walkthroughs (sales/onboarding/support). HQ: SF. Stage: YC F25, ~2. First-party: **Low–Med**. Pain: real-time gen per visitor session. Angle: per-session routing. Contact: Chris Farestveit (LinkedIn).

**Questom** — AI phone/chat/email sales+support for print/custom-merch. HQ: SF. Stage: YC F25. First-party: **Low**. Pain: structured order extraction at volume across 3 channels. Angle: structured extraction → cheap tier. Contact: Crunchbase/LinkedIn (Ritanshu Dokania).

**Berry** — AI customer-success manager (onboarding/renewals). HQ: SF. Stage: YC W23 (⚠ older), ~$1.6M pre-seed. First-party: **Low**. Pain: per-account RAG + gen. Angle: routing across onboarding vs. renewal convos. Contact: Kerry Wang (LinkedIn).

**Trace** — ⚠ **NAME/HQ CONFLICT**: one source says SF voice-AI support for banks (YC W25, $3M); another describes a London workflow-orchestration "Trace." **Verify identity/HQ before outreach.** First-party: **Low–Med**.

### D. Vertical SaaS  (document-heavy: long context + extraction + structured output)

**General Legal** — AI law firm; $500 flat-fee commercial contract review/drafting via Slack (Casetext/CoCounsel team). HQ: SF. Stage: YC W26, pre-seed/seed. First-party: **Med** ("Claude's Corner"). Pain: long-context contracts; flat-fee margin pressure; structured clauses. Angle: route boilerplate clauses cheap, frontier for nuanced redlines → protect flat-fee unit economics. Contact: Ryan Walker, Javed Qadrud-Din (LinkedIn).

**Adaptional** — "Underwriter AI" classifies/extracts/validates insurance submissions + risk summary. HQ: SF. Stage: YC S25, seed. First-party: **Med**. Pain: high-volume email/doc classification, long multi-file submissions, structured outputs (⚠ insurance = "high risk" in Anthropic policy → compliance angle). Angle: cheap triage + frontier risk summary; profile/min-model for compliance. Contact: Kevin Cox, Suril Kantaria (LinkedIn).

**Beacon Health** — "AI employees" for primary-care back office (screenings, prior-auth, referrals, risk adjustment) inside the EHR. HQ: SF (likely). Stage: YC W26, seed (Accel). First-party: **Med** ("Claude's Corner"). Pain: long-context chart reads; high-volume extraction/coding; structured billing fields; HIPAA. Angle: route chart extraction cheap, frontier for prior-auth reasoning; profile for compliance. Contact: founder "Mark" (YC profile/LinkedIn).

**Bryckel AI** — CRE lease-document intelligence ("Abstract 360," clause-cited). HQ: SF (likely). Stage: pre-seed. First-party: **Med** (publishes Claude-for-CRE tutorials). Pain: long-context full-lease ingestion; batch abstraction across portfolios. Angle: cheap extraction pass + frontier validation. Contact: https://www.linkedin.com/company/bryckel

**Propaya** — AI commercial-lease abstraction with citations. HQ: SF (likely). Stage: YC, pre-seed. First-party: **Low**. Pain: long-context leases; structured JSON w/ citations. Angle: cheap extraction + frontier verify tier. Contact: Reader Wang, Jake Golas (LinkedIn).

**Arcline** — AI-native legal services for startups (80% AI / 20% lawyer, flat fee). HQ: SF. Stage: YC W26, seed. First-party: **Low**. Pain: templated doc gen, structured outputs, flat-fee pressure. Angle: routing templated drafting vs. bespoke review. Contact: Pamir Ehsas (LinkedIn).

**LegalOS** — AI-native immigration law firm (petition drafting, evidence abstraction). HQ: SF (likely). Stage: YC W26; >$1.5M annualized rev. First-party: **Low**. Pain: long-context evidence packets; classification; structured petitions. Angle: cheap classify/extract, frontier for narrative. Contact: Matthew Asir (LinkedIn).

**VoiceCare AI** — Healthcare-admin voice agent ("Joy") for payer calls (benefits, prior-auth, claims). HQ: SF. Stage: $4.54M seed (Mayo Clinic). First-party: **Low**. Pain: call-transcript summarization/extraction; policy long-context; structured auth fields. Angle: route transcript triage cheap, frontier for coverage logic. Contact: careers/LinkedIn co page.

**Avoice** — AI back-office workspace for architecture/AEC firms. HQ: SF. Stage: YC W26, ~$1M, ~4. First-party: **Med** ("Claude's Corner"). Pain: spec/schedule docs, material research. Angle: doc extraction routing. Contact: YC profile.

**LunaBill** — AI voice callers for healthcare billing/AR follow-up. HQ: SF. Stage: YC, seed (Pioneer Fund), $764K ARR. First-party: **Low** (voice-first). Pain: call automation volume. Angle: cost-of-inference. Contact: https://fyicombinator.com/company/lunabill

### E. Document extraction / classification / content  (★ the cheapest-tier sweet spot — biggest measurable savings)

**Paradigm** — AI-native spreadsheet; thousands of agents per cell for gather/enrich/generate ("500 cells/min"). HQ: SF. Stage: ~$7M (GC seed + YC pre-seed). First-party: **High** (explicitly switches across **Anthropic**/OpenAI/Gemini + model switching). Pain: massive per-cell call volume = textbook cheap-tier routing; already multi-provider → near-zero integration friction. Angle: auto-route per-cell jobs to cheapest adequate tier; proof/holdout beats their manual switching. Contact: Anna Monaco (CEO), June Lee (CTO) — LinkedIn.

**Unsiloed AI** — Vision+LLM turning multimodal unstructured docs into structured/queryable data ("millions of pages"). HQ: SF. Stage: YC F25, ~$500K. First-party: **Med**. Pain: extreme page volume; cheap-tier extraction is the biggest lever; structured outputs. Angle: page-level cost reduction on the LLM layer atop their vision models. Contact: Aman Mishra https://www.linkedin.com/in/aman005/ , Adnan Abbas.

**Trellis AI** — Healthcare pre-service paperwork → structured EHR data (intake, prior-auth, appeals). HQ: SF. Stage: seed (ex-Stanford/Cresta/Meta founders). First-party: **Med**. Pain: high-volume clinical doc classification/extraction; long records; HIPAA routing constraints. Angle: cheap extraction + compliance profile. Contact: Mac Klinkachorn, Jacky Lin (LinkedIn).

**Melder** — AI formulas + doc support in Excel (`=EXTRACT()` summarize/classify/analyze; contract review). HQ: SF (likely). Stage: YC W26, seed. First-party: **Med**. Pain: per-cell/per-formula call volume; short classify/extract = cheap-tier sweet spot; structured outputs. Angle: cheapest-tier routing on bulk formula calls. Contact: YC / Work at a Startup.

**Midship** — "Extract documents straight to your spreadsheets." HQ: SF (likely). Stage: early YC. First-party: **Med**. Pain: page-level extraction volume; structured/JSON. Angle: cheap-tier extraction routing. Contact: YC launch page.

**Corvera** — MCP "context layer" + agent workforce for CPG back-office. HQ: SF. Stage: YC W26, $6.2M seed; $0→$33K MRR in 4 wks. First-party: **Med** (deploy agents via Claude + ChatGPT). Pain: agent fan-out across workflows; per-brand multi-tenant spend attribution. Angle: per-brand cost attribution + routing. Contact: Christopher Kong https://www.linkedin.com/in/cwnkong/

**tday** — Turns a product + git repo into on-brand marketing creative. HQ: SF (likely). Stage: early YC. First-party: **Low**. Pain: content gen (higher-quality tier). Angle: quality-vs-cost routing. Contact: YC profile.

---

## Master summary table

| # | Company | Sector | Stage (best public est.) | LLM use case | First-party | Lead outreach angle |
|---|---|---|---|---|---|---|
| 1 | Omnara | Coding agents | YC S25, ~$500K | Claude Code interface | **High** | Cap/route Claude Code spend |
| 2 | 21st.dev | Coding agents | YC W26, ~$500K | Parallel Claude Code | **High** | Per-agent caps + routing |
| 3 | Paradigm | Doc/content | ~$7M seed | Per-cell extract/gen | **High** | Auto-route per-cell to cheapest tier |
| 4 | HumanLayer | Agent infra | YC F24, seed | Agent oversight | **High** | Spend control for agent platforms |
| 5 | Ambral | CS/accounts | YC S25, seed | Subagent research | **High** | Route the research fan-out |
| 6 | Sapiom | Agent infra | $15.75M seed | Agent payments | **High** (investor) | Warm Anthropic tie; routing line-item |
| 7 | Castari | Coding agents | YC pre-seed | Claude Agent SDK runtime | Med–High | Proven routing vs. their proxy |
| 8 | Replicas | Coding agents | YC S26 | Background coding agents | Med | Route simple tickets; cap loops |
| 9 | Browser Use | Agent infra | $17M seed | Browser agents | Med | Cheap page steps |
| 10 | CodeAnt AI | Coding agents | YC W24, ~$2.5M | PR review | Med | Cheap model for trivial diffs |
| 11 | Manufact | Agent infra | YC S25, $6.3M | MCP for Claude apps | Med | Complementary routing layer |
| 12 | Hyper | Agent infra | YC P26 | Per-turn memory enrich | Med | Cut synthesis cost |
| 13 | Corvera | Doc/content | YC W26, $6.2M | CPG agents (Claude+GPT) | Med | Per-brand attribution + routing |
| 14 | Unsiloed AI | Doc extraction | YC F25, ~$500K | Millions of pages | Med | Page-level cost cut |
| 15 | Trellis AI | Doc (health) | seed | Clinical doc → EHR | Med | Cheap extract + compliance profile |
| 16 | Melder | Doc extraction | YC W26 | Excel extract/classify | Med | Cheapest-tier bulk formulas |
| 17 | Midship | Doc extraction | early YC | Docs → spreadsheets | Med | Cheap-tier extraction |
| 18 | Rulebase | CX/compliance | YC F24, $2.1M | 100% interaction QA | Med | Cheap classifier full-coverage |
| 19 | Adaptional | Insurance | YC S25, seed | Submission extract/risk | Med | Cheap triage + frontier risk; profile |
| 20 | Beacon Health | Healthcare | YC W26, seed | EHR back-office agents | Med | Cheap chart extract; compliance |
| 21 | Bryckel AI | Real estate | pre-seed | CRE lease abstraction | Med | Cheap extract + verify tier |
| 22 | General Legal | Legal | YC W26, seed | Contract review (flat fee) | Med | Protect flat-fee unit economics |
| 23 | Aurorin CAD | Dev/CAD | YC W26 | AI CAD agent | Med | Protect freemium margins |
| 24 | REV1 | Dev/CAD | YC W26 | 3D→2D drawings | Med | Route high-volume drawing gen |
| 25 | Avoice | Vertical (AEC) | YC W26, ~$1M | AEC back-office docs | Med | Doc extraction routing |
| 26 | Kilo Code | Coding platform | $8M seed | Multi-model coding | Med ⚠comp | Coopetition / proof layer |
| 27 | Dataleap | Agent infra | YC S24 ⚠ | Agentic OS (Claude Code) | Med | Per-seat caps (verify stage) |
| 28 | Laminar | Agent infra | YC S24, $3M | Agent observability | Low | Partner: visibility→routing |
| 29 | Crafting | Coding infra | $5.5M seed | Agentic eng | Low | Route routine steps |
| 30 | Runtime | Coding infra | YC S26 | Agent governance | Low | Cost visibility + routing |
| 31 | Compyle | Coding agents | YC F25 | Coding agent | Low–Med | Lower coding COGS |
| 32 | Minimal AI | CX | YC S25, $3.6M | E-comm ticket automation | Low–Med | Haiku bulk triage |
| 33 | 14.ai | CX | $3M seed | Support agency | Low–Med | Routing lifts agency margin |
| 34 | Cignara | CX/Sales | YC P26, ~$500K | Voice/chat agents | Med | Cheap turns; premium upsell |
| 35 | Primer | Sales/GTM | YC F25 | Walkthrough agent | Low–Med | Per-session routing |
| 36 | Questom | Sales/CX | YC F25 | Order extraction | Low | Structured extract → cheap |
| 37 | Berry | CS | YC W23 ⚠ | AI CSM | Low | Onboarding vs renewal routing |
| 38 | Arcline | Legal | YC W26, seed | Startup legal docs | Low | Templated vs bespoke routing |
| 39 | LegalOS | Legal | YC W26 | Immigration petitions | Low | Cheap classify; frontier narrative |
| 40 | VoiceCare AI | Healthcare | $4.54M seed | Payer-call agent | Low | Transcript triage routing |
| 41 | Propaya | Real estate | YC, pre-seed | Lease abstraction | Low | Cheap extract + verify |
| 42 | LunaBill | Healthcare | YC, seed | Billing voice calls | Low | Cost-of-inference |
| 43 | tday | Content | early YC | Marketing creative | Low | Quality-vs-cost routing |
| 44 | Trace ⚠ | CX (verify) | YC W25?, $3M? | Voice support (banks?) | Low–Med | Verify identity/HQ first |

---

## 🔧 5 product-tuning themes (what this segment needs)

1. **Coding/agentic workloads are the biggest token burners — and the loudest.** Omnara, 21st.dev, Replicas, Castari, Kilo, Compyle, the CAD pair, HumanLayer, Hyper. They run long, parallel, multi-turn agent loops. **Tune:** strong agentic-category routing, per-session/per-agent spend caps + attribution, the structured-output/tool-call guard, and cache-aware economics for repeated repo/context. **Pitch:** "cut your coding-agent COGS without touching quality."

2. **High-volume extraction/classification is the cheap-tier jackpot.** Paradigm, Melder, Midship, Unsiloed, Trellis, Rulebase, Adaptional, Minimal. Per-item, short, schema-constrained calls where a frontier default is overkill. **Tune:** the Haiku floors for extraction/classification (already), structured-output safety, `learn-floors` on their own data, and `prompt-audit` for repeated-context caching. **This is where our measured savings are largest** — lead demos here.

3. **Many already model-switch or are building their own routing.** Paradigm (Anthropic/OpenAI/Gemini), Corvera (Claude+ChatGPT), Manufact (multi-provider), Kilo (500 models), Castari (`castari-proxy`), SuperPenguin (spend tracking). **Implication:** (a) demand is real and validated; (b) integration friction is low (they already abstract the model); (c) our wedge vs. their hand-rolled routing is **proof** — RCT holdout + side-by-side non-inferiority. **Tune/pitch:** drop in behind their existing abstraction; lead with the audit, not the concept.

4. **Margin pressure from flat-fee / per-seat / agency pricing makes routing a CFO story.** General Legal ($500 flat), Arcline (per-doc flat), 14.ai (agency), CodeAnt (per-seat), CAD freemium. Their COGS *is* model spend. **Pitch:** "every routed request is gross margin" — quantify with the digest's annualized run-rate.

5. **Regulated verticals need Track B (the profile) before they'll adopt.** Fintech (Rulebase, Trace), healthcare/HIPAA (VoiceCare, Beacon, Trellis), insurance "high-risk" (Adaptional), legal. **Tune:** lead these with `allowed_models`/`min_model`/data-residency controls + the structured-output guard + proof — savings second. The per-customer profile is the unlock for this whole column.

**Bonus (sales process):** because stealth seed rarely confirms their provider, qualify on **use-case fit + spend**, not disclosed Claude usage; reserve the "first-party only / not Bedrock" framing for the High-signal confirmed-Claude names (Tier 1).

---

## Appendix — excluded (too large or non-SF), with reasons
Too large/late: Campfire (Series A+B), Lindy (Series B), Decagon (Series D), Lovable (Series B ~$6.6B), Gamma ($2.1B), Conductor ($63M), Greptile (Series A $25M), Reducto (Series B $108M), Sierra (~$10B), Sycamore/Inferact (huge seeds). Non-SF: Vulcan Technologies (Austin), Gradient Labs (London), Trace-workflow (London), Parsewise (London — note: had the *strongest* explicit Claude/MCP signal, disqualified on HQ only), Dust (Paris), Legora (Stockholm). Different company/weak fit: Chatbase (HQ unclear), Section (uses Claude internally, not API-native), Trellis Health (consumer women's health), Pulse/Interfaze (built own OCR models — compete with, not consume, Claude).
