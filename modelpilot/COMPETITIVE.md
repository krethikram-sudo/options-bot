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
