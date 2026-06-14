# Changelog

Versioning: **integer** bumps (1.0, 2.0) are breaking changes you should
re-validate against; **decimal** bumps (0.2, 0.3) are features, router
retunes, and fixes that are safe to take.

## 0.4.2 — 2026-06-14

- **Decluttered dashboard.** Default view is now just the conversion story:
  the "switch to autopilot" panel, the live session strip, the side-by-side
  proof, and the cumulative-savings chart. Totals, recent sessions, model-mix,
  the category table, and the RCT/quality block moved into a collapsible
  "Details & methodology" section.

## 0.4.1 — 2026-06-14

- **Side-by-side proof embedded in the dashboard.** `modelpilot compare
  --from-captures --save-to-db` stores the comparison; the dashboard then renders
  it inline — your prompt, the recommended model's output and the standard
  model's output in two columns, with per-chat and cumulative savings and the
  non-inferiority verdict. The "see for yourself" conversion evidence now lives
  on the dashboard, not just in a separate report.

## 0.4.0 — 2026-06-14

- **Guidance mode + a conversion-focused dashboard.** `--mode guidance` is the
  recommended starting point (advise mode, renamed for customers): zero behavior
  change, full measurement. The dashboard now opens with a "Ready to switch to
  autopilot?" panel showing the *gated* potential (what autopilot would actually
  capture at the confidence gate), the annualized run-rate, and the quality
  verdict — then, in autopilot, flips to a realized-savings + quality-held
  reassurance. This is the guidance→autopilot conversion path.
- **Side-by-side proof on your own traffic:** `modelpilot compare --from-captures`
  runs your captured prompts through the routed model vs the standard model and
  renders both outputs, costs, and non-inferiority verdicts on one page.
- **Continuous per-customer tuning:** `modelpilot tune` learns a per-category
  policy from this deployment's own outcomes — loosening the gate where routing
  has proven safe at volume, raising it on any category that caused escalations
  or negative feedback. The gateway applies it via `MODELPILOT_POLICY`. Savings
  improve the more the product is used.

## 0.3.3 — 2026-06-13

- **Failed requests no longer pollute the numbers.** `summary()` and
  `by_category()` now count only successful (HTTP 200) requests, so upstream
  errors (e.g. a bad API key returning 401) can't inflate request counts or
  skew the savings report.
- `seed_demo_traffic.py`: now models a representative support/document-ops (ICP)
  workload instead of a hard-heavy worst case, and fails fast with a clear
  message when `ANTHROPIC_API_KEY` is missing or still the placeholder.

## 0.3.2 — 2026-06-13

- **Router recall (behavior change):** the classifier was dropping easy
  mechanical tasks into the low-confidence `conversation` catch-all, so the
  autopilot gate withheld them and the savings were lost. `rewrite_format` now
  catches list-reformatting ("turn these into a numbered list"), concision/tone
  rewrites ("make this more concise/professional"), and simple linguistic
  transforms (past tense, plural, synonym/antonym); `classification` catches
  bare "spam". Measured on the golden set: false-downgrade stays 0.0% at every
  gate ≥0.60.
- **Honest shadow numbers:** the digest headline now uses *gated* potential —
  only switches that clear the confidence gate, i.e. what autopilot would
  actually apply — so shadow no longer oversells versus autopilot. `summary()`
  gains a `gate` parameter and a `gated_potential` field.

## 0.3.1 — 2026-06-13

- **Fix: `modelpilot gateway` now respects `MODELPILOT_*` env vars.** The CLI
  built its config from argparse defaults and `os.environ.update(...)`, which
  silently clobbered any env var the operator had set (e.g. `MODELPILOT_DB`,
  `MODELPILOT_UPSTREAM`) when the matching flag wasn't passed — so launchd/
  systemd deployments and `export MODELPILOT_DB=...` were ignored, sending the
  ledger to the wrong file. Flag defaults now fall back to the env var:
  explicit flag > env var > built-in default. Adds `MODELPILOT_PORT`.

## 0.3.0 — 2026-06-13

- **`modelpilot digest`: the proactive proof surface.** A short, buyer-facing
  savings summary ("Saved $X — Y% of your Claude spend; quality held") that
  prints, emits JSON, or posts to a Slack incoming webhook
  (`--slack-webhook` / `MODELPILOT_SLACK_WEBHOOK`). Repositions the value where
  the buyer lives instead of a dashboard they have to open: the gateway stays
  invisible infrastructure, and the digest is what renews the contract. Adapts
  to mode (potential savings in shadow, net realized once routing is live),
  projects an annualized run-rate, and reports the holdout quality verdict.

## 0.2.0 — 2026-06-12

- **Router retune (behavior change):** content-difficulty features —
  audience-constrained summarization/rewrite ("for a status page",
  "customer-facing", "press release") now floors at Sonnet; dense
  operational/legal content reduces confidence below the autopilot gate.
  Measured on the golden set: false-downgrade 1.4% → **0.0%** at every gate
  ≥0.60, accuracy up, coverage unchanged at the calibrated gate.
- `modelpilot compare`: side-by-side proof harness — routed vs all-baseline
  on the same prompts; HTML report with outputs, actual-token costs, and
  non-inferiority verdicts.
- `modelpilot replay`: Layer-2 calibration — replays captured switch-traffic
  on the baseline model and corrects the report's potential-savings estimate
  for output-length bias (per-category ratios).
- `x-modelpilot-baseline` header: advise-mode callers who followed a
  recommendation declare their true baseline, so realized savings are
  recorded from actual tokens.
- Chat playground defaults to a Fable 5 baseline; explicit "$0.00 saved —
  quality protected" line on stay decisions.
- Fixes: CLI subcommand flag parsing (`modelpilot demo --offline` etc.);
  confidence float-rounding that could miss the autopilot gate by epsilon.

## 0.1.0 (beta) — 2026-06-11

First beta release.

- Drop-in gateway for the Claude API with three modes: shadow (measure only),
  advise (recommendation headers), autopilot (confidence-gated routing with
  randomized holdout and escalation valve)
- Session-context-aware router: follow-ups inherit session difficulty;
  mechanical tasks over existing content keep their cheap tier; cache-aware
  switch economics; expected-conversation-length model
- Live dashboard: per-session savings strip (auto-updating), session history,
  cumulative savings, model-mix migration, RCT panel with bootstrap CIs,
  escalation netting
- Chat playground with pre-execution model selection and per-message savings
- claude.ai browser extension (advisory)
- Golden-set tuning pipeline (Batch API fan-out, position-debiased judging,
  confidence-gate calibration) + shadow-traffic corpus exporter
- `modelpilot` CLI: gateway / demo / report / share
