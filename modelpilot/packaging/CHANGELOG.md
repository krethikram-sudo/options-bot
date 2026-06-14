# Changelog

Versioning: **integer** bumps (1.0, 2.0) are breaking changes you should
re-validate against; **decimal** bumps (0.2, 0.3) are features, router
retunes, and fixes that are safe to take.

## 0.9.0 — 2026-06-14

Two tracks of per-customer adaptability — making routing fit each customer's
own traffic instead of a global default.

- **Per-customer classification rules (feature C).** A new rule layer maps a
  customer's domain phrasing to a category (and optional tier floor), so their
  traffic stops landing in the conservative `conversation`/`unknown` catch-alls
  where savings leak. Rules are hand-authored (`MODELPILOT_RULES=rules.json`, or
  a `category_rules` list in `MODELPILOT_POLICY`) or proposed by the new
  `modelpilot learn-rules`, which mines catch-all captures for recurring topics
  and writes a scaffold to fill in. Safety preserved: a rule can make routing
  more precise but cannot bypass the quality guards — the economics veto, the
  follow-up/session-difficulty reconciliation, and a now-universal
  structured-output/tool floor (Sonnet) in `router.recommend` all still apply.
- **Prompt-level savings audit (feature D).** `modelpilot prompt-audit` finds
  savings *beyond* model choice from the ledger's token accounting: (1) uncached
  repeated context — multi-turn sessions re-sending a stable prefix with caching
  off, and the dollars `cache_control` would save; (2) context bloat — oversized
  input for tiny output, and the dollars from trimming. Estimates are
  deliberately conservative and the two buckets never double-count the same
  tokens. It only *recommends* — it never rewrites prompts. The headline also
  surfaces in `modelpilot digest` (Slack/email/print).

## 0.8.0 — 2026-06-14

- **Head-to-head vs. AWS Bedrock Intelligent Prompt Routing.** `modelpilot
  compare --bedrock-router <ARN>` adds a third arm: the same prompts run through
  a Bedrock prompt router alongside ModelPilot and the all-baseline arm. The
  report gains a "Head-to-head" table (savings %, routed cost, non-inferiority,
  routable model set, proof, lock-in) and a third output column per prompt, so
  "isn't this just Bedrock?" gets a measured answer. Each arm is priced at what
  you'd actually pay there — the Bedrock arm at Bedrock list prices for the model
  IPR selected (editable in `bedrock.py`), every other arm at first-party rates.
  The report states honestly that IPR routes only two *older* models per router
  and cannot route the current lineup (Fable 5 / Opus 4.x / Sonnet 4.6 /
  Haiku 4.5). Live runs need boto3 + AWS creds; `--offline --bedrock-router sim`
  renders the shape with no AWS account.

## 0.7.2 — 2026-06-14

- **Ed25519 license verification is now LIVE** — a public key is bundled at
  `modelpilot/license_pubkey.pem`, so the shipped client verifies tokens
  asymmetrically and the HMAC fallback is retired (HMAC tokens are now rejected).
  Tokens can only be minted with the private key.

## 0.7.1 — 2026-06-14

- **Unforgeable license keys (Ed25519).** The gate now supports asymmetric
  signing: once a public key is bundled (`modelpilot/license_pubkey.pem`), the
  shipped client can *verify* tokens but cannot *mint* them — only the holder of
  the private key can issue, and HMAC tokens are then rejected (no downgrade).
  Set up with `python -m modelpilot.license keygen` (run where `cryptography`
  works); the HMAC fallback stays active until a public key is present, so
  nothing breaks in the interim. Adds `cryptography` as a dependency.

## 0.7.0 — 2026-06-14

- **License gate for autopilot.** Autopilot now requires a valid license token
  (`MODELPILOT_LICENSE`); guidance and shadow run free so prospects can measure
  potential savings. Tokens are named (accountability) and expiring (revocation
  by lapse). Issue with `python -m modelpilot.license issue --licensee … --days …`.
  Honest scope: an HMAC-signed in-client gate is a deterrent + usage control for
  the beta, not unbreakable DRM — see `internal/SPLIT_ARCHITECTURE.md` for the
  server-side path that makes it real.
- **Strengthened LICENSE** into a proper proprietary beta-evaluation agreement
  (named licensee, no redistribution / reverse-engineering / derivative works,
  ownership, revocation, confidentiality, liability cap).

## 0.6.0 — 2026-06-14

- **Structured-output safety (behavior change).** Requests carrying a
  machine-enforced output contract — tool definitions, `output_config`/JSON
  schema, or `response_format` — are never auto-downgraded below Sonnet, so a
  cheaper model can't silently change the response *shape* and break brittle
  downstream parsing. (Addresses an external review's format-brittleness risk;
  golden-set false-downgrade stays 0%.)
- Landing page: published the measured router overhead (~0.05 ms/request, ≈3 ms
  on a 24k-token conversation) and elevated cache-awareness as the lead
  trust differentiator.

## 0.5.2 — 2026-06-14

Beta-tester feedback fixes:

- **Savings % no longer diluted by the guidance period.** Once autopilot is live,
  the dashboard panel and digest measure realized savings against the
  *autopilot-era* baseline (via `summary(mode="autopilot")`), so the headline
  doesn't appear to drop after switching from guidance. `summary()` gains a
  `mode` filter.
- **Digest all-time wording:** `--days 0` now reads "all time" instead of
  "0 days".
- **Demo table clarity:** columns relabeled `task (seed)` and `classified as`
  (they show the seed label vs the live classification — previously looked like
  misrouting).
- **Prerequisites up front** on the landing page and README: a billable
  Anthropic API key is required; subscriptions can't be optimized.

## 0.5.1 — 2026-06-14

- **"Savings rate over time" chart** on the dashboard — daily savings as % of
  baseline, so customers can watch the rate climb as continuous auto-tuning
  learns their traffic. (`_line_chart` gained a y-axis formatter.)

## 0.5.0 — 2026-06-14

- **Continuous auto-tuning (live, no restart).** In autopilot the gateway now
  re-derives its per-category policy from its own accumulating traffic every
  `MODELPILOT_AUTOTUNE_EVERY` requests (default 100) and applies it in place:
  categories that route safely at volume are loosened (down to a conservative
  0.7 gate) to capture more; any category that draws an escalation or negative
  feedback is tightened immediately. Manual `MODELPILOT_POLICY` entries still
  win; disable with `MODELPILOT_AUTOTUNE=0`. The dashboard's conversion panel
  shows what it has learned ("auto-tuned to your traffic: N categories…").
  This is the "gets better the more you use it" loop, now automatic rather than
  a manual `modelpilot tune` + restart.

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
