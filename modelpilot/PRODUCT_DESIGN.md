# Maven — Product Design

## 1. Where the product sits: two deployment surfaces

The phrase "the prompt the user enters into the chat box" covers two very different surfaces.
Both matter; they need different builds.

### Surface A — API gateway (the enterprise wedge; build first)

A drop-in proxy in front of the Claude API. Customers change one line — `base_url` — in their
SDK config and route their traffic through us:

```
app ──► Maven gateway ──► api.anthropic.com
              │
              ├─ router scores prompt + context (target <150ms added latency)
              ├─ Mode 1: annotates response with recommendation (headers + dashboard)
              ├─ Mode 2: rewrites the `model` field before forwarding
              └─ logs token usage from the API's own `usage` block → savings ledger
```

Why this is the wedge:

- **Mode 2 is technically clean.** We control the request, so "automatically change the model"
  is a field rewrite, not UI automation.
- **Measurement is airtight.** The API returns exact `input_tokens` / `output_tokens` /
  cache token counts per request. No estimation.
- **Spend concentrates here.** Enterprise AI cost overruns are dominated by API/agent traffic
  (RAG pipelines, agents, internal tools), not seat-based chat subscriptions.
- **Zero-risk trial.** The gateway runs in *shadow mode* first: forward requests untouched,
  score them anyway, accumulate a "what you would have saved" ledger. That report closes deals.

Mode semantics on this surface:

| Mode | Mechanism |
|---|---|
| Advise | Response carries `x-modelpilot-recommended-model` + `x-modelpilot-est-savings` headers; the dashboard aggregates per-route/per-team recommendations; engineers act on them (or accept per-route policies). |
| Autopilot | Gateway rewrites `model` when router confidence ≥ threshold AND the request matches admin policy (e.g. "auto-route only Opus→Sonnet, never touch the legal team's traffic"). Always logs original + routed model. |

### Surface B — claude.ai browser extension (Phase 3 companion)

For human chat users. The extension reads the draft prompt and visible conversation, shows a
recommendation chip next to the model picker ("Haiku is enough for this — save ~$0.04"), and in
Autopilot mode flips the model picker itself before send.

Honest caveats, stated up front:

- Mode 2 here is **UI automation** — brittle against claude.ai DOM changes and needs review
  against Anthropic's ToS before we ship it. Mode 1 (suggest only) is much safer.
- Per-seat chat plans are flat-rate, so the "savings" story for claude.ai is *usage-limit
  headroom* (fewer rate-limit hits, longer runway in a session) more than dollars. Real dollar
  savings live on Surface A. We should not let the demo-friendly extension distort the roadmap.
- Privacy: prompt text must be scored locally or in the customer's tenant; an extension that
  ships prompt text to our cloud is an instant enterprise-security "no."

### Also worth knowing: Claude Code / SDK plugins

A third surface — a hook for Claude Code and the Agent SDK that suggests `model` +
`output_config.effort` per task. Agentic coding is one of the highest-burn workloads in most
orgs. This is cheap to build once the router exists (it's just another client of the routing
API) and is a strong developer-marketing channel.

## 2. The router (summary — full treatment in ROUTER_TUNING_PLAN.md)

Input: prompt text + conversation context (turn count, accumulated tokens, prior model,
cache state, task category, customer policy).
Output: `(recommended_model, confidence, est_savings, rationale)`.

Latency budget ≤150ms p95 on the gateway hot path, which forces the architecture: a fast local
feature/embedding model for the bulk of decisions, with an optional Haiku-based classifier for
the ambiguous band (and for bootstrapping — see tuning plan).

## 3. The detail most competitors will miss: the prompt-cache trap

Prompt caches are **model-scoped**. Switching models mid-conversation invalidates the cached
prefix, and cache reads cost ~0.1× the input price while a fresh cache write costs ~1.25×.

Worked example — a 100K-token conversation currently on Opus 4.8:

- Stay on Opus, next turn input: 100K cached read ≈ 100K × $0.50/MTok = **$0.05**
- Switch to Sonnet 4.6, next turn input: 100K fresh write ≈ 100K × $3.75/MTok = **$0.375**

The "cheaper" model costs 7.5× more *for that turn*. The switch only pays off if the
conversation continues on Sonnet long enough for per-turn savings to amortize the re-write.

So the router's objective is not "cheapest model for this prompt" — it's:

```
net_benefit(switch) = E[remaining conversation tokens] × (price_old − price_new)
                      − cache_rewrite_penalty(current prefix size)
recommend switch only if net_benefit > 0 with margin
```

Implications:

- Routing decisions are most valuable at **conversation start** (no cache to lose) and for
  **stateless/single-shot traffic** (the bulk of API volume) — that's where Phase 1 focuses.
- Mid-conversation, the router needs the expected-remaining-length model (estimable from
  historical per-route/per-user conversation length distributions).
- This is also why naive per-prompt routers can *increase* cost — a fact that becomes a sales
  weapon once our dashboard shows we account for it.

## 4. Beyond model choice (roadmap levers, same machinery)

Model selection is lever #1, but the router sees every request and can recommend the others:

| Lever | Savings | When |
|---|---|---|
| Model downgrade | 40–90% on the request | Core product |
| `output_config.effort` (low/medium/high/xhigh/max on supporting models) | Large output-token reductions without switching models — often safer than a downgrade | Phase 2 |
| Batch API | flat 50% | Detect non-latency-sensitive traffic patterns (cron-like timing, no streaming) and flag candidates |
| Prompt-caching hygiene | up to ~90% of input cost | Gateway sees cache-hit rates per route; flag routes with broken caching (timestamps in system prompts, etc.) |
| `max_tokens` right-sizing | Truncation-retry waste | Flag routes with frequent `max_tokens` stop reasons |

These compound the headline number and deepen the moat: we become the AI-spend control plane,
not a one-trick router.

## 5. The live savings ticker

Visible in both modes, both surfaces.

- **Per request:** `saved_$ = cost_at_baseline_model − cost_actual`, where baseline = what the
  request *would have* used (the org default or the model the caller specified). Token counts
  come from the API `usage` block; baseline cost re-prices those tokens at baseline rates
  (with a replay-calibrated correction for output-length differences — see SAVINGS_DASHBOARD.md).
- **Cumulative:** running total in tokens and dollars, per user / team / org, since install.
- **Honest accounting:** escalation retries (router downgraded, quality failed, request re-ran
  on the bigger model) count as *negative* savings, automatically. Nothing erodes trust faster
  than a savings counter that ignores its own mistakes.
- In Mode 1, the ticker splits into **realized savings** (user followed the advice) and
  **unrealized savings** (advice ignored) — the unrealized number is the internal sales motion
  for flipping teams to Mode 2.

## 6. Guardrails & governance (what makes it enterprise-grade)

- **Policy engine:** per-team/per-route rules — allowed model range, "never downgrade" lists
  (legal, customer-facing), confidence thresholds, Mode 1 vs Mode 2 per scope.
- **Escalation safety valve (Mode 2):** if quality failure is detected (user regenerate,
  explicit thumbs-down, downstream validation failure signal from the customer's app), auto
  re-run on the original model and feed the example back to training.
- **Audit trail:** every routed request logs original model, routed model, confidence,
  rationale, and outcome. Required for enterprise change-management sign-off.
- **Kill switch:** instant org-wide revert to passthrough.
- **Privacy:** prompt text never persisted by default; the router consumes embeddings +
  features; raw-text retention is opt-in (needed for the customer's own golden-set tuning).

## 7. MVP phasing

| Phase | Scope | Exit criterion |
|---|---|---|
| **0 — Shadow (4–6 wks)** | Gateway passthrough + router v0 (Haiku-as-judge) + counterfactual ledger. No traffic altered. | A pilot customer's 2-week shadow report showing credible would-have-saved $ |
| **1 — Advise** | Mode 1 headers + dashboard, golden dataset v1, trained fast router, savings ticker | Routing accuracy ≥ target on golden set; ≥1 design partner acting on recommendations |
| **2 — Autopilot** | Mode 2 with confidence gates, policy engine, escalation valve, randomized holdout, dashboard GA | RCT shows savings with quality parity (escalation rate < threshold) at a paying customer |
| **3 — Expand** | Browser extension (Mode 1 first), Claude Code plugin, effort/batch/caching levers, second provider | Multi-surface, multi-lever; renewal/expansion motion running |

## 8. Risks

| Risk | Mitigation |
|---|---|
| One bad downgrade torches trust | Asymmetric loss + confidence gating + escalation valve + "never-touch" policies; default conservative |
| Anthropic ships native routing | Cross-provider neutrality, governance layer, independent measurement (vendors grading their own savings aren't credible) |
| Added gateway latency | Local router, ≤150ms p95 budget; shadow path adds ~0 |
| claude.ai ToS / DOM brittleness | Extension is Mode-1-first, Phase 3, legal review before Mode 2 |
| Cache-trap mispricing | Cache-aware objective (above) is in the v1 router, not a later patch |
| Model/price churn (new Claude versions) | Models API + price table as config, not code; re-run golden set on every model launch (see tuning plan) |
