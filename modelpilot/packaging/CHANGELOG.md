# Changelog

Versioning: **integer** bumps (1.0, 2.0) are breaking changes you should
re-validate against; **decimal** bumps (0.2, 0.3) are features, router
retunes, and fixes that are safe to take.

## 0.16.0 — 2026-06-14

- **Privacy-safe performance telemetry (`modelpilot telemetry`), opt-in.** Lets a
  customer share AGGREGATE performance metrics so you can improve the product
  without ever receiving sensitive data. Guarantees enforced in code: no prompt
  text, outputs, or keys — only per-category counts/rates/avg-confidence/
  incident-rate, routing + savings totals, catch-all rate, holdout quality rates,
  version/env, and an anonymous per-deployment id; numbers are coarsened. Off by
  default; `--preview` prints the exact JSON before anything sends; uploads only
  to an explicit `--url` / `MODELPILOT_TELEMETRY_URL`. `--with-phrases` optionally
  adds catch-all n-gram *signals* to guide router recall, but only phrases seen in
  ≥`--min-docs` distinct prompts (k-anonymity), stopworded, with no example text,
  and only if prompt capture was enabled. A test enforces the no-prompt-text
  guarantee.

## 0.15.0 — 2026-06-14

- **Licensing change: the gateway now requires a valid license in EVERY mode**
  (guidance and autopilot alike; shadow too) — guidance is no longer free. Only
  `modelpilot demo --offline` (synthetic, no real traffic) runs without a key.
  `cmd_gateway` checks `MODELPILOT_LICENSE` before starting in any mode. Landing
  page, bundled site, and `validate_local.sh` updated accordingly (the validation
  script now requires `MODELPILOT_LICENSE`).

## 0.14.0 — 2026-06-14

- **Per-segment starter packs (`packs/`).** Drop-in policies that give a new
  customer a good fit on day one, before their own `learn-rules`/`learn-floors`
  accumulate: `doc-extraction`, `support`, `coding` (aggressive cheap-tier on
  bulk classify/extract/codegen) and `legal`, `healthcare` (conservative —
  Opus→Sonnet only, never Haiku, with an embedded compliance `profile`). Load
  with `MODELPILOT_POLICY=packs/<segment>.json` (rules + gates + floors + profile
  apply together). These encode the domain-judgment phrasings deliberately kept
  out of the global router, so they only apply when a customer opts into their
  segment; all guardrails (structured-output floor, economics veto, holdout,
  learn-floors validation) still apply. A test (`test_packs.py`) guarantees every
  shipped pack is valid and routes as intended. Packs ship via migrate/publish.

## 0.13.0 — 2026-06-14

- **Default autopilot gate lowered 0.8 → 0.7 (behavior change).** The golden set
  shows false-downgrade is **0% at every gate ≥0.60**, so the 0.8 default was
  over-conservative — it stranded schema-enforced extraction (which lands at
  confidence 0.75, floored to Sonnet) just below the gate, so our best-fit
  segment (document extraction) captured almost nothing at defaults. At 0.7 it
  routes, with no golden-set quality cost. Measured on the ICP segment harness:
  routed-down rose from 11→18 of 35 and est. savings 25%→33%, golden-set
  false-downgrade still 0.0%. `MODELPILOT_CONFIDENCE` still overrides.
  - Profile `risk_tolerance` realigned to the new default: conservative 0.8 /
    balanced 0.7 / aggressive 0.6.
  - Live auto-tune loosen floor lowered 0.7 → 0.6 so proven-safe categories can
    still be loosened *below* the new default (golden-safe at 0.6).

## 0.12.0 — 2026-06-14

- **Router recall pass (behavior change), driven by ICP segment testing.** A new
  per-segment routing harness (`scripts/segment_eval.py`, internal) showed the
  global classifier was dropping common real-world phrasings into the
  conservative catch-alls — forfeiting savings — for our target workloads.
  Added cheap-tier-safe markers: `classification` now catches fixed-answer cues
  (`yes/no`, `pass/fail`, one-word answers); `extraction` catches data-shaping
  cues (bare `parse`, "into rows/columns/a table/a spreadsheet"); `codegen_simple`
  adds the `utility` noun. Measured on the golden set: **false-downgrade stays
  0.0% at every gate ≥0.60 and coverage is unchanged (56.5%)** — pure recall, no
  quality cost. On the ICP segment set, catch-alls dropped 15→11 and routed-down
  rose 8→11 at the default gate. Domain-judgment phrasings (legal redlines,
  compliance nuance, creative drafting) are intentionally left to per-customer
  rules/floors, where they're validated on the customer's own traffic.

## 0.11.2 — 2026-06-14

- **Fix: `compare` judge/run now bypass any `ANTHROPIC_BASE_URL`.** The judge is
  an internal grading call and must hit the real API directly — not be routed
  through the customer's own gateway. If `ANTHROPIC_BASE_URL` was left pointing at
  the proxy (e.g. from wiring an app), the judge previously tried to reach it and
  failed with a connection error. Both `compare`'s run and judge clients now pin
  `https://api.anthropic.com`.

## 0.11.1 — 2026-06-14

- **Fix: a judge error no longer crashes `modelpilot compare --judge`.** The LLM
  judge now falls back gracefully when the installed Anthropic SDK doesn't accept
  the `output_config` structured-output parameter (older SDKs): it re-asks for
  JSON in the prompt and parses it robustly. And if any individual verdict still
  fails, `compare` degrades that verdict to "unjudged" and surfaces the error,
  instead of aborting the whole run — the cost comparison is always produced.
  (Found via `validate_local.sh` on a real key.)

## 0.11.0 — 2026-06-14

- **Per-customer deployment profile (Track B) — route to the customer's utility,
  not a generic one.** A profile (`MODELPILOT_PROFILE=profile.json`, or a
  `profile` object in `MODELPILOT_POLICY`) makes routing fit enterprise reality:
  - `allowed_models` / `blocked_models` — compliance: never route to a model the
    customer hasn't approved; a blocked cheap model falls back to the
    next-cheapest *permitted* tier rather than forfeiting the switch.
  - `min_model` — a customer-set quality floor: never route below this tier,
    whatever the heuristics or learned floors say.
  - `price_overrides` — negotiated / committed-use rates, merged into the price
    table at startup so the economics AND every savings number (ledger,
    dashboard, digest, compare) reflect the customer's actual bill. Single-tenant
    by design (one local gateway = one customer), so this needs no plumbing.
  - `risk_tolerance` (conservative / balanced / aggressive) → the autopilot
    confidence gate, or an explicit `gate`.
  Validate/print it with `modelpilot profile`. Routing constraints are enforced
  in `router.recommend`; the structured-output/tool guard still applies on top.

## 0.10.0 — 2026-06-14

- **Closed-loop per-customer floor learning (Track A) — the deepest savings
  lever.** Auto-tuning adjusts the per-category *gate* and rules fix
  *classification*, but both worked within each category's globally fixed
  *floor* (the cheapest tier it can route to). `modelpilot learn-floors` now
  closes the loop between our proof and our control: for each category it samples
  this deployment's OWN captured prompts, runs them on the next-cheaper tier vs.
  the baseline, judges non-inferiority, and lowers the floor only where the
  cheaper model holds up on the customer's data (default ≥95% non-inferior over
  ≥8 judged prompts). Re-run as captures accumulate and a floor walks down one
  safe step at a time; any category that fails the bar keeps its floor.
  - Floors flow into routing via a new `category_floors` policy
    (`MODELPILOT_FLOORS=policy.json`, or a `category_floors` key in
    `MODELPILOT_POLICY`); `taxonomy.floor_tier` and the router/rule classifiers
    honor them. A learned floor only ever *lowers* the global default, and the
    universal structured-output/tool guard still floors brittle calls to Sonnet
    on top — so a lowered floor can't break a structured call.
  - Active testing costs API calls, so this is a periodic command, never the hot
    path; `--offline` renders the shape with no spend. The dashboard's conversion
    panel notes how many categories have a learned floor.

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
