# ModelPilot — prospect list & sourcing playbook (internal)

Built 2026-06-16 from 4 web-research streams (AI-native startups, regulated verticals,
Anthropic customer showcase, bill-shock signals). **All companies from public sources;
no names/emails/contacts were fabricated** — named people appear only where publicly
stated as founders/CEOs (usually NOT the technical buyer — confirm the CTO/Head of
AI/platform lead on LinkedIn before outreach). Anthropic customer pages 403'd to the
crawler, so verify each case-study URL loads + the quote before using it in outreach.

## ⏰ Timing — use this now
A mid-2026 Anthropic billing change (separate metered pool for agentic usage; steep
effective increase for heavy users, then a partial walk-back) created an active wave of
Claude bill-shock. **Lead every outreach with the narrative:** *"Uber burned its entire
2026 AI budget by April; Microsoft's Experiences+Devices division ripped Claude Code out
over cost. You don't have to abandon Claude — just stop overpaying for the cheap 60–80%
of calls, measured and proven."* (Uber: Fortune/The Information; Microsoft: The Next Web.)

## Per-company flags (read before pitching)
- **Claude: confirmed vs assumed** — only assert "you use Claude" where confirmed.
- **Multi-model** — savings scale with the *Claude share*; quantify before promising numbers.
- **Bedrock** — deploys Claude via Amazon Bedrock; integration + economics differ (and Bedrock
  has native intra-Claude routing ~30% free — pitch done-for-you breadth + proof, not the mechanic).
- **Pass-through billing** — model-agnostic tools sometimes have *their customers* pay Anthropic;
  confirm who holds the bill (that's the real buyer).
- **Size** — mega/well-funded likely have in-house FinOps + direct Anthropic deals → strategic
  message (margin), not "you have no one to fix this."

---

## TIER 1 — Start here (confirmed Claude-core · scaling A–B · lean/no-FinOps · routable)
1. **Augment Code** — enterprise AI coding agent, Claude Sonnet primary; 100K+ devs, long agent loops. Buyer: CTO/AI-infra. *Confirmed.* https://claude.com/customers/augment-code
2. **Warp** — agentic terminal, Claude default; 800K monthly devs. Buyer: Head of AI/VP Eng. *Confirmed.* https://claude.com/customers/warp
3. **Chatbase** — support chatbots; ~18 people, ~$10M ARR (lean = no FinOps, ideal). Buyer: CEO+eng **Yasser Elsaid** (public). *Confirmed.* https://claude.com/customers/chatbase
4. **Greptile** — AI code review on the Claude Agent SDK; Series A ($25M). Buyer: founding eng/CTO. *Confirmed.* https://siliconangle.com/2025/09/23/greptile-bags-25m-funding...
5. **Inscribe** — AI risk agents for banks/fintechs (doc verification/fraud); Series B. Buyer: CTO/Head of AI. *Confirmed* (also fintech/privacy fit). https://claude.com/customers/inscribe
6. **Robin AI** — contract review built on Claude; Series B. Buyer: **James Clough (CTO)**, **Richard Robinson (CEO)** (public). *Confirmed* (legal/privilege fit). https://www.robinai.com/post/robin-ai-claude-3-models-anthropic
7. **Solve Intelligence** — patent/IP drafting, "Powered by Claude"; ~$12M (lean). Buyer: CTO/founding eng. *Confirmed* (trade-secret privacy fit). https://www.solveintelligence.com/blog/post/solve-intelligence-powered-by-claude
8. **Lindy** — no-code AI agents, Claude default; agents run continuously. Buyer: founder/CTO. *Confirmed.* https://claude.com/customers/lindy
9. **Gamma** — AI decks/sites, 50M+ users; already frames Claude in cost terms (buying intent). Buyer: CTO. *Confirmed.* https://www.anthropic.com/customers/gamma
10. **Carta Healthcare** — clinical-data abstraction; cuts cost 50%+. Buyer: CEO **Brent Dover** (public)/Head of AI. *Confirmed* (**Bedrock**; PHI/privacy fit). https://claude.com/customers/carta-healthcare

## TIER 2 — Strong (confirmed Claude; multi-model→quantify share, or larger but reachable)
11. **Elation Health** — primary-care EHR, Claude incl. Haiku for chart summaries. CTO/Head of AI. *Confirmed* (PHI). https://claude.com/customers/elation-health
12. **Commure** — ambient clinical scribing on Claude. CTO/Head of AI. *Confirmed* (PHI). https://www.anthropic.com/news/healthcare-life-sciences
13. **Equisoft** — life-insurance platform on Claude; policyholder PII. CTO. *Confirmed* (privacy). https://www.equisoft.com/insights/insurance/equisoft-embeds-anthropics-claude-ai-models...
14. **Legora** — legal AI "mostly on Claude"; larger (Series D). CEO **Max Junestrand** (public). *Confirmed · size.* https://claude.com/customers/legora
15. **Eve** — plaintiff legal ("EveOS") on Claude; ~$1B. CEO **Jay Madheswaran** (public). *Confirmed · size.* https://www.lawnext.com/2026/06/eve-builds-on-ai-workforce-launch...
16. **CodeRabbit** — AI code review (every PR), Claude Marketplace; Series B ($60M). CTO. *Confirmed · multi-model.* https://www.innovationopenlab.com/news-biz/67716/coderabbit-joins-the-claude-marketplace.html
17. **Copy.ai** — content/GTM gen, 10–16M users. CEO **Paul Yacoubian**, CTO **Chris Lu** (public). *Confirmed.* https://claude.com/customers/copy-ai
18. **Gorgias** — ecommerce support, multi-model (already routes; 2 calls/resolution). CTO/platform. *Confirmed · multi-model.* https://www.gorgias.com/ai-agent/support-skills
19. **Sendbird** — support-agent platform; 4,000+ customers. CEO **John S. Kim** (public). *Confirmed · size.* https://www.anthropic.com/customers/sendbird
20. **Decagon** — enterprise support agents; multi-model; $4.5B (strategic). Co-founder **Jesse Zhang** (public). *Confirmed · size · multi-model.* https://www.anthropic.com/customers/decagon
21. **11x** — AI SDR agents, Claude for personalization; Series B. CTO/Head of AI. *Confirmed · multi-model.* https://www.zenml.io/llmops-database/rebuilding-an-ai-sdr-agent...
22. **Factory.ai** — coding agents; Claude top performer (model-agnostic); $1.5B. CTO. *Confirmed-as-option · pass-through risk.* https://factory.ai/news/terminal-bench
23. **ASAPP** — contact-center automation (**Bedrock**). CTO (verify CEO). *Confirmed · size.* https://www.anthropic.com/customers/asapp
24. **Brex** — corporate spend, Claude via **Bedrock**; larger. VP Eng/Head of AI. *Confirmed · Bedrock · size.* https://www.anthropic.com/customers/brex
25. **Hebbia** — finance/legal doc analysis, Claude Sonnet, huge bursty volume; Series B+ (large). CEO **George Sivulka** (public). *Confirmed · size.* https://claude.com/customers/hebbia

## TIER 3 — Best ICP *stage* (seed/A, reachable founders) but Claude UNCONFIRMED
Pitch routing on its merits; **do not assert Claude** until verified.
- **Casey** (YC F25, insurance submissions) — VP Eng **Pascal Küng** (public). https://www.ycombinator.com/companies/casey
- **CopyCat** (YC, insurance-ops browser agents) — eng co-founder. https://www.runcopycat.com/
- **Leaping AI** (YC W25, voice support, >100k calls/yr) — CTO co-founder. https://www.ycombinator.com/companies/leaping-ai
- **Cassidy** (YC, internal-docs copilots) — CTO **Ian Woodfill** (public). (verify on YC page)
- **Caretta** (YC, real-time sales agent) — eng lead. (verify on YC page)
- **Ambral** (YC W25, account mgmt) — founder/CTO. *Claude confirmed in build tooling.* https://claude.com/blog/building-companies-with-claude-code
- **Norm Ai** (RegTech compliance) — CTO. *Verify Claude.* https://siliconangle.com/2025/03/11/ai-agent-powered-compliance-automation-startup-norm-ai-raises-48m/
- **EvenUp** (PI legal demand letters) — Head of AI. *Verify model mix.* https://www.evenuplaw.com/products/demands/
- **Spellbook** (contract review, multi-model incl. Claude) — CTO. *Multi-model.* https://spellbook.com/learn/claude-for-lawyers

## STRETCH / strategic (large → in-house FinOps; lead with margin, not "no one's minding it")
Lovable, Harvey, Cognition (Devin), Reducto, Sourcegraph (Cody/Amp), FIS (financial-crimes AI), Intuit, Notion (already optimizes via caching), Intercom (Fin), Klaviyo.
**Deprioritize (mega, direct deals):** Citadel, Goldman Sachs, Allianz, Bridgewater, Carlyle, Banner Health.

---

## Sourcing playbook (find more + reach the buyer)
1. **Bloomberry "companies that use Claude"** (~62k, DNS-detected, filterable by size/industry, with a **"renewal in next 3 months"** buying-trigger filter) — the single best database. https://bloomberry.com/data/anthropic-claude/  · also **TheirStack** (~49k) https://theirstack.com/en/technology/claude-by-anthropic
2. **GitHub code search** for `@anthropic-ai/sdk` (package.json), `anthropic` (requirements.txt/pyproject), `messages.create` → finds teams + engineers running the SDK. *(Founder action — Claude's GitHub tools here are scoped to this repo only.)*
3. **Anthropic customer showcase** (highest-spend, publicly committed): https://claude.com/customers
4. **Warm/free leads — HN & Reddit** where people complain about Claude bills NOW (handles → identifiable): e.g. https://news.ycombinator.com/item?id=44942890 ; r/LLMDevs, r/ClaudeAI, r/LocalLLaMA.
5. **Job boards** — postings naming "Claude/Anthropic API" + "cost/FinOps/LLM cost/token/rate limits" = a company mid-bill-shock.
6. **Events** — Anthropic "Code with Claude"; FinOps/AI-cost meetups.
7. **Find the buyer:** LinkedIn (titles: Head of AI/ML Platform, VP/Dir Eng, Platform/Infra, FinOps, or CTO for smaller cos) + company eng-blog/GitHub org members. Warm path: reply helpfully in the HN/Reddit threads, then DM.

## First-week focus (recommendation)
- **Mine HN/Reddit + Bloomberry's "renewal in 3 months" × 51–200-employee software/fintech** for warm, right-sized, trigger-ready leads.
- **Open with Tier 1** (Augment, Warp, Chatbase, Greptile, Inscribe, Robin AI, Solve Intelligence) — cleanest confirmed-Claude + right-size + routable + (several) privacy fit.
- Pair each with the estimator link + the one-pager (`PILOT_ONEPAGER.md`) and log in `pilot_tracker.csv`.
