# ModelPilot — Proving the Savings (Dashboard & Methodology)

The dashboard's job is to make a skeptical FinOps lead or CFO say "fine, that number is real."
That requires getting the *measurement* right before the visualization. Three layers, in
increasing order of rigor — the dashboard shows all three and labels them honestly.

## 1. Measurement layers

### Layer 1 — Counterfactual ledger (every request, always on)

For each request: `saved = cost(baseline model, tokens) − cost(actual model, tokens)`.

- Token counts are exact — taken from the API's `usage` block (`input_tokens`,
  `output_tokens`, `cache_read_input_tokens`, `cache_creation_input_tokens`), priced from the
  current price table.
- **Known bias, corrected:** different models produce different output lengths for the same
  prompt (and cache states would have differed). Re-pricing actual tokens at baseline rates is
  only an estimate. We correct it with Layer 2's replay coefficient (below) and label the
  ledger number "estimated."
- Escalation retries and cache-rewrite costs incurred *because of* routing are charged
  against savings automatically. The ledger nets, never gross-only.

### Layer 2 — Replay sampling (continuous calibration)

Nightly, sample ~0.5–1% of routed requests and **actually replay them on the baseline model**
via the Batch API (50% off makes this cheap). This yields the true counterfactual cost
distribution, per task category:

- Produces a **calibration coefficient** per category (e.g. "Haiku outputs run 1.18× longer
  than Opus on summarization") that corrects Layer 1's estimates.
- Doubles as a quality audit: judge-compare the replayed baseline output vs. the routed
  output — a continuous, production-traffic non-inferiority check feeding the tuning loop.

### Layer 3 — Randomized holdout (the headline number)

The gold standard, and the only thing that survives a procurement review:

- **Design:** within consenting scopes, randomly assign 5–10% of requests to **control**
  (always baseline model, recommendations logged but not applied). The rest get routing.
  Randomize at the conversation/session level, not per-request (avoids cache contamination
  and interference between arms).
- **Compare:** cost per request / per 1K tokens-of-work between arms, with bootstrap
  confidence intervals. Quality parity via the guardrail metrics (regenerate rate, escalation
  rate, customer validation failures) under a pre-registered non-inferiority margin.
- **Report:** "Routing reduced cost 31% ± 4% (95% CI) with no detectable quality difference
  (regenerate rate 2.1% vs 2.2%, n.s.)." That sentence is the product.
- Holdout percentage decays over time (10% → 2%) once results stabilize; it never goes to
  zero — it's also our live regression alarm.

## 2. Dashboard views

### A. Live ticker (in-product, both modes, per user/team)
- This request: model used vs. baseline, tokens, $ saved (or $0 — "Opus was the right call").
- Session/day running totals, in tokens and $.
- Mode 1 split: **realized** (advice followed) vs **unrealized** (advice ignored) savings.
  The unrealized number is the built-in upsell to Mode 2.

### B. Savings overview (org admin home)
- Cumulative savings curve: actual spend vs. counterfactual baseline spend, shaded CI band
  (Layer 1 estimate, Layer 3-anchored where RCT data exists).
- Headline cards: $ saved this month, % of baseline spend, RCT-verified savings rate,
  projected annualized.
- **Model-mix shift:** stacked area of traffic share by model over time — the visual story of
  Opus traffic migrating to Sonnet/Haiku.

### C. Quality assurance panel (the trust page)
- Routed vs. holdout guardrail metrics side by side: regenerate rate, escalation rate,
  override rate, validation-failure rate, each with CIs and a green/amber/red
  non-inferiority status.
- Escalation log: every Mode-2 quality save, with cost of the re-run (charged against
  savings) — visible proof the system polices itself.
- Replay audit summary: judge non-inferiority rate on production samples, per category.

### D. Drill-downs
- Per team / per route / per task category: spend, savings, follow-rate, top opportunities
  ("the support-summarization route is 92% Opus traffic; router says 85% of it is
  Haiku-safe — $4.2K/mo on the table").
- Per-request explorer (audit trail): original model, routed model, confidence, rationale,
  tokens, outcome. Prompt text redacted by default.

### E. Opportunity & levers panel (roadmap)
- Non-model levers detected by the gateway: routes with broken prompt caching, batchable
  traffic patterns, oversized `max_tokens`, effort-parameter candidates — each with estimated
  $ impact.

### F. The monthly report (exportable PDF/email)
One page, CFO-ready: verified savings (RCT number front and center), estimate vs. verified
clearly distinguished, quality parity statement, model-mix chart, next-month opportunities.
This artifact is the renewal motion.

## 3. Statistical honesty rules (product principles, not fine print)

1. **Never report gross savings.** Always net of escalation re-runs, cache rewrites, replay
   sampling costs, and our own router inference costs.
2. **Label estimates as estimates.** Layer 1 numbers carry an "estimated" badge until Layer 3
   data anchors them; the two are never silently blended.
3. **Pre-register the quality margin.** The non-inferiority threshold is agreed with the
   customer before the RCT starts, not chosen after seeing the data.
4. **Session-level randomization** to avoid cache and conversation interference between arms.
5. **Show the failures.** The escalation log is visible, not buried. A system that admits its
   5 mistakes is believed about its 5,000 wins.
6. **No savings claimed on Mode-1-ignored advice** — unrealized savings are shown as
   opportunity, never added to the savings total.

## 4. Implementation sketch

- **Ledger pipeline:** gateway emits a per-request event (request hash, models, usage block,
  routing metadata, outcome signals) → stream into a columnar store (ClickHouse-class) →
  dashboard queries are simple aggregations. No prompt text in the event by default.
- **Stats jobs:** nightly replay batch (Layer 2), weekly RCT analysis with bootstrap CIs
  (Layer 3), drift tripwires shared with the tuning loop.
- **The dashboard is the demo.** Shadow mode populates views B, D, and E with "would-have"
  data from day one — a prospect sees their own savings opportunity before we've routed a
  single request.
