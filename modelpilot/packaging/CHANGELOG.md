# Changelog

Versioning: **integer** bumps (1.0, 2.0) are breaking changes you should
re-validate against; **decimal** bumps (0.2, 0.3) are features, router
retunes, and fixes that are safe to take.

## 0.35.0 — 2026-06-16

- **Opt-in caching auto-apply (`MODELPILOT_AUTO_CACHE=1`).** Beyond *recommending*
  prompt caching, the gateway can now capture it for you: when a large reusable
  system prompt isn't already cached, it adds an ephemeral cache breakpoint so
  repeated calls bill cached reads at ~10% of input price. Off by default; conservative
  (no-op if caching is already present, if there's no sizable system prompt, or below a
  safe size floor that stays above the ~1024-token cache minimum). Compatible with
  tools/structured output — caching the prefix doesn't change model behavior, only
  billing/latency. Tunable floor via `MODELPILOT_AUTO_CACHE_MIN_CHARS` (default 6000).
  Sets an `x-modelpilot-cache-applied` response header when it acts.

## 0.34.0 — 2026-06-16

- **Savings opportunities are now surfaced and reported.** When the routing brain
  spots savings beyond model choice (an uncached reusable prefix, or latency-tolerant
  traffic that could use the Batch API), the gateway now: (1) returns it inline per
  request as `x-modelpilot-opportunity-<type>-usd` response headers, and (2) records
  the per-request estimate in the local ledger and reports the aggregate to the
  console (`opportunity_saved`) so it shows up as "Additional potential savings" on
  your dashboard. Advisory only — estimates never bill; nothing mutates your requests.
  Privacy unchanged: counts + dollars only, no prompt content.

## 0.33.0 — 2026-06-16

- **Savings levers beyond model choice.** New pricing helpers quantify two
  optimizations the router can recommend on top of cheaper-model routing:
  `cache_savings()` (dollars saved by caching a large reusable prefix across turns
  — cached reads bill at ~10% of input price) and `batch_savings()` (50% off
  latency-tolerant traffic via the Batch API). Estimates only; nothing mutates your
  requests. Honest by omission: no `max_tokens` "savings" lever, because billing is
  on actual output tokens, not the cap.

## 0.32.0 — 2026-06-14

- **Semantic caching (opt-in, more savings).** Beyond exact-match, near-duplicate
  requests (same model) now serve a cached response when their embeddings are within
  a cosine threshold — big for RAG/agent apps with reworded-but-equivalent prompts.
  Pluggable + privacy-preserving: embeddings come from an endpoint *you* configure
  (`MODELPILOT_EMBED_URL`, OpenAI-compatible) and the cache stays on your box; off
  unless `MODELPILOT_SEMANTIC_CACHE=1`. `x-modelpilot-cache: HIT-SEMANTIC`. New
  `cache.SemanticCache` + `cosine` (stdlib) in the publishable thin-client closure.

## 0.31.0 — 2026-06-14

- **Full-gateway request-path parity.** The full gateway (`gateway.py`, with the
  local ledger/dashboard) now uses the same reliability + caching as the thin
  client: retry transient failures (429/5xx/529, Retry-After, backoff), fall back
  to the original model on a routed model's failure, and serve identical
  non-streaming requests from an exact-match cache at $0 (`MODELPILOT_CACHE=1`).
  Honest accounting: a fallback to the original model is recorded as not-applied
  (zero savings) so the ledger stays accurate. Shared `retry.py`/`cache.py`; both
  client types now behave identically.

## 0.30.0 — 2026-06-14

- **Exact-match response cache (P1, more savings).** Opt-in (`MODELPILOT_CACHE=1`):
  identical, non-streaming requests return a stored response instantly at **zero
  upstream cost**, keyed on the caller's original request body. Entirely in-process
  and on your machine (cached responses never leave your box). TTL + capacity
  bounded (`MODELPILOT_CACHE_TTL`, `MODELPILOT_CACHE_MAX`); responses carry
  `x-modelpilot-cache: HIT|MISS`. New `modelpilot/cache.py` (commodity); in the
  publishable thin-client closure (leak audit clean) + the publish allowlist.
- **Black-and-white redesign.** The landing pages, docs/security/legal site, and
  the customer + admin console were recolored from green to a classy monochrome
  palette (near-black ink, white/grey surfaces, black primary actions) — simpler
  and more modern. No behavior change.

## 0.29.0 — 2026-06-14

- **Fallbacks & retries (P1 reliability).** The thin-client proxy now retries
  transient upstream failures (429/5xx/529, honoring `Retry-After`, capped
  exponential backoff) and — on a routed (cheaper) model's failure — **falls back
  to the model the caller originally requested**, so routing never costs you
  reliability. Configurable: `MODELPILOT_MAX_RETRIES` (default 2),
  `MODELPILOT_FALLBACK` (default on). Works for streaming (retry before relaying)
  and non-streaming; `x-modelpilot-decision` records each retry/fallback. New
  `modelpilot/retry.py` (commodity, stdlib) holds the decision logic; added to the
  publishable thin-client closure (leak audit clean) and the publish allowlist.

## 0.28.0 — 2026-06-14

- **Privacy-safe request logs (P0 observability).** Opt-in per-request **metadata
  only** — timestamps, requested/routed model, category, token counts, cost,
  realized savings, status, routed/escalated flags. **Prompt text and outputs
  never leave your box** (the `/api/logs` endpoint also rejects any payload with
  prompt/output/secret keys, 422). The console stores them; the dashboard adds a
  **Logs** page with a recent-requests table and **CSV export**.
- **OTel export to your own collector.** `modelpilot/logs.py` ships new ledger rows
  incrementally (rowid marker, restart-safe) to the console (`MODELPILOT_LOGS=1`)
  and/or emits **OTLP/HTTP JSON trace spans** to `MODELPILOT_OTEL_ENDPOINT` — one
  span per request, metadata attributes only. Runs as a background task on the
  gateway or via `modelpilot logs --watch`. Off by default. `ledger.rows_since`
  exposes the metadata cursor. (Full-gateway feature — it reads the local ledger;
  in the customer-package allowlist.)

## 0.27.0 — 2026-06-14

- **Docs site (P0).** A real, hosted docs experience at `/docs` (served from the
  Cloudflare Pages site): Quickstart (5-minute install → configure → point your SDK
  → modes), a full Configuration env-var reference, an SDKs page (Python + TS +
  curl), and an Architecture & Privacy page (request flow, what-leaves-the-box
  table, quality guards). Shared sidebar/design matching the landing. "Docs" linked
  from both landings.
- **Thin Python SDK.** `modelpilot/sdk.py` (commodity, ships in the client):
  `from modelpilot import anthropic_client` returns an `anthropic.Anthropic`
  pre-pointed at the local proxy (reads `ANTHROPIC_API_KEY` + `MODELPILOT_PROXY_URL`);
  plus `async_anthropic_client` and `proxy_url`. One line instead of hand-setting the
  base URL. TS usage documented (same one-line `baseURL` pattern). Added to the
  publishable thin-client closure (leak audit clean) and the full-package allowlist.

## 0.26.0 — 2026-06-14

- **API keys (P0 tablestakes).** Customers create named, per-deployment API keys in
  the console (Connect page) — shown once, sha256-hashed at rest, revocable, with
  last-used tracking. The gateway authenticates to the console with
  `MODELPILOT_API_KEY` (sent as `Authorization: Bearer …`) on metering, policy, and
  proposal calls; the machine endpoints resolve the key to the deployment and 401 a
  bad/revoked key. Backward compatible — deployment_id still works when no key is sent.
- **Spend budgets + alerts (P0 tablestakes).** Set a monthly spend budget + alert
  threshold in Settings; the dashboard shows a spend-vs-budget bar, and the console
  emails the account at the warn threshold and again if it goes over (once each per
  cycle, via the metering path). Off by default (budget 0 = no cap).
- Client wiring (`brain_client`, `metering`, `proposals`) sends the bearer key when
  `MODELPILOT_API_KEY` is set. (Console-side features are vendor-internal.)

## 0.25.0 — 2026-06-14

- **Live policy refresh (no restart).** Both the thin client and the full gateway
  now re-fetch admin-approved floors + rules from the console in the background
  (`MODELPILOT_POLICY_REFRESH`, default 300s) and apply them on the fly — the thin
  client updates its rule set; the gateway rebuilds its classifier (floors + rules).
  Approving a customer's tuning takes effect within minutes, no redeploy. Tasks are
  off the request path and cancelled cleanly on shutdown.
- **Bulk review queue (admin).** A new cross-customer `/admin/proposals` queue lists
  every pending tuning proposal with its evidence; tick any subset (select-all
  included) and **approve or reject in bulk** with one optional note attributed to
  each (audit trail). The overview's "Tuning to review" card links straight to it,
  and "Review" is in the admin nav.

## 0.24.0 — 2026-06-14

- **Approved rules now apply in the published thin client too (Track C, commodity).**
  `router_classify` gained a stdlib-only signal→category rule matcher (no
  tiers/floors — those stay server-side), so the thin client applies a customer's
  admin-approved rules locally before asking the brain. The client fetches its
  approved rules from the console at startup (`brain_client.fetch_policy`); rule
  hits still pass through follow-up reconciliation (a non-mechanical rule can't
  strand a hard follow-up). No prompt text leaves the box. Leak audit still clean.
- **Proposal audit trail.** Approving/rejecting a tuning proposal now records
  **who** decided, **when**, and an optional **note**; the customer detail page
  shows a "Tuning history" table. (`proposals.decided_by`/`note` columns, migrated
  in place for existing DBs.)

## 0.23.0 — 2026-06-14

- **Per-customer tuning, admin-reviewed (Tracks A + C in the console).** Gateways
  submit auto-derived tuning *proposals* — learned floors (Track A, judge-validated
  non-inferiority on the customer's own traffic) and classification rules (Track C)
  — to the console for approval. Only the proposal travels: a category + proposed
  tiers / rule spec + aggregate stats (samples, non-inferiority rate), never prompt
  text (`/api/proposals` rejects sensitive keys). Admins review each on the customer
  detail page (with the evidence) and **approve/reject**; the overview shows a
  pending-review count.
- **Approved policy flows back automatically.** `GET /api/policy` exposes a
  deployment's approved floors + rules. The **brain applies approved floors**
  per-account when routing (cached), and the **gateway loads approved floors + rules**
  at startup from the console — so an approval lowers that customer's floors/adds
  rules with no redeploy. Submit from the gateway with
  `modelpilot learn-floors --submit` / `modelpilot learn-rules --submit`
  (`modelpilot/proposals.py`; `learn_floors` now returns per-category review
  `details`).

## 0.22.0 — 2026-06-14

- **Customer dashboard: savings by task type + a quality-proof stat.** The web
  dashboard now shows per-category routed/escalation/savings (where the money
  comes from) and a non-inferiority rate — the share of side-by-side comparisons
  the judge rated non-inferior at the cheaper model. The gateway reports proof as
  aggregate counts only (`comparisons`, `non_inferior` on `/api/meter`; per-prompt
  side-by-side text stays on the local gateway dashboard). `ledger.proof_summary`
  now exposes `n_judged`/`n_ni`; `metering.py` reports the proof delta.
- **Multiple deployments per account.** Run ModelPilot across several apps/
  environments; each gets its own id and they roll up to one bill. Create/rename
  deployments on the Connect page.
- **Password reset (self-serve + admin).** Forgot-password → single-use,
  1-hour token → reset page. Pluggable email (`console/notify.py`: SMTP when
  configured, otherwise logged); no account enumeration. Admins can issue a reset
  link from the customer detail page.

## 0.21.0 — 2026-06-14

- **Full product through the web — new `console/` service (vendor-internal).** A
  server-rendered SaaS control plane: customers land → sign up → 7-day free trial
  → convert to a paid plan billed **20% of realized savings** (Stripe usage-based,
  graceful without keys). Signed-in customers get a dashboard (realized savings,
  baseline vs actual, current/projected bill), a **mode toggle**
  (shadow/guidance/autopilot), routing-policy settings (risk, quality floor,
  telemetry opt-in), connection instructions, and billing. **Admin** console:
  cross-customer revenue + savings (cycle + lifetime), per-customer drill-down
  (per-category routed/escalation/savings + auto-suggested tuning actions) to
  improve the product, and access management (extend trial, mark paid, suspend,
  set rate). Auth is stdlib PBKDF2 + HMAC-signed cookies. Tested end-to-end
  (`console/test_console.py`).
- **Mode is now server-authoritative.** The dashboard toggle writes the account
  mode; the brain reads it via the console's `/api/entitlement` and only
  auto-routes (`apply`) in autopilot — guidance/shadow recommend only. Brain falls
  back to its own license/trial when no `CONSOLE_URL` is set.
- **Usage metering for billing (`modelpilot/metering.py` + `modelpilot meter`).**
  The gateway reports the realized-savings delta from its ledger to the console
  (`/api/meter`) — aggregate dollars + counts only, restart-safe via a marker,
  rejected if it carries any prompt/output/secret keys. Runs as a background task
  when `MODELPILOT_CONSOLE_URL` + `MODELPILOT_DEPLOYMENT_ID` are set (or via the
  `modelpilot meter --watch` sidecar). Deployment id now prefers the
  console-issued `MODELPILOT_DEPLOYMENT_ID` so entitlement, mode, and billing all
  key off the same account.
- Landing pages link to the hosted signup/sign-in and state the 20%-of-savings
  pricing. `console/` ships Dockerfile + DEPLOY.md; brain gains `CONSOLE_URL`.

## 0.20.1 — 2026-06-14

- **Packaging fix for the router split.** `scripts/publish_modelpilot.sh` now
  ships the two new modules (`router_classify.py`, `client_proxy.py`) in the
  customer package allowlist — without `router_classify`, the assembled package's
  `router.py` couldn't import and the publish dry-run's in-place test suite
  failed. Also made `test_client_split.py` resolve the package dir from the
  import (not the test file path) so it passes in both the monorepo and the
  published `tests/`-as-sibling layout.

## 0.20.0 — 2026-06-14

- **Router split → a genuinely publishable thin client (IP stays server-side).**
  The classifier is now two modules: `modelpilot/router_classify.py` — commodity
  lexical classification only (category, confidence, features), stdlib-only, with
  **no** price table, capability floors, or switch economics — and
  `modelpilot/router.py`, which binds the floor/economics IP (taxonomy + pricing)
  on top and re-exports the classifier surface unchanged (gateway/rules/compare/
  tests need no edits). The floor policy is *injected* into the commodity
  classifier, so the thin client can classify (and detect session follow-ups)
  without ever seeing the floors. Behavior is identical: full test suite + golden
  set unchanged (false-downgrade still 0% at the shipped gate).
- **Thin-client proxy + build:** `modelpilot/client_proxy.py` is a minimal
  drop-in Claude API proxy that asks the hosted brain for each decision and fails
  open — it depends only on the publishable closure (router_classify +
  brain_client). `scripts/build_client.sh` carves the `modelpilot-client` package
  and **hard-fails on any IP leak** (forbidden modules/symbols + import-isolation
  check). New `test_client_split.py` locks the boundary in CI.

## 0.19.0 — 2026-06-14

- **Gateway wired to the hosted brain (split architecture, opt-in + fail-open).**
  Set `MODELPILOT_BRAIN_URL` and the gateway gets each routing decision from the
  brain — which enforces license/7-day-trial entitlement **server-side** — sending
  only category + numeric features (no prompt text). Any brain error falls back to
  local routing so customer traffic is never blocked; entitlement lapse passes
  traffic through unoptimized rather than breaking it. Off by default (fully local,
  unchanged). When a brain is configured, `modelpilot gateway` defers the startup
  entitlement check to the brain.
- **Deployable backend:** `brain/` and `ingest/` now ship Dockerfiles +
  requirements + `brain/DEPLOY.md` (Fly.io/Render/VM steps, volume at `/data`, and
  the `MODELPILOT_BRAIN_URL` / `MODELPILOT_TELEMETRY_URL` client config). Both
  services are vendor-side (not migrated/published to customers).

## 0.18.0 — 2026-06-14

- **Split architecture v1 (foundation for publishing a safe client).** Adds the
  client seam `modelpilot/brain_client.py`: it classifies locally and asks a
  hosted "routing brain" for the decision, sending ONLY a category label +
  numeric features — never prompt text, outputs, or keys (test-enforced) — and
  fails open (returns None → local routing) if the brain is unreachable, so our
  infra can never block customer traffic. The brain itself (`brain/`, vendor-side,
  NOT shipped) holds the routing policy (floors/economics/gate) and
  server-authoritative license + 7-day-trial enforcement keyed by deployment id
  (unforgeable — fixes the local-clock weakness), and refuses any request
  carrying sensitive keys. `brain_client` ships inert (active only if
  `MODELPILOT_BRAIN_URL` is set). Next: wire the gateway to it (fail-open) and
  carve a thin client package that omits the router — the artifact safe to
  publish.

## 0.17.0 — 2026-06-14

- **Free product: a built-in 7-day trial replaces the invite-only beta gate.**
  The gateway now runs on a valid license OR an active trial — full functionality
  (guidance + autopilot) free for 7 days, started automatically on first run
  (`license.trial_status`, a local clock at `~/.modelpilot/trial`). After the
  trial, a license is required. Self-serve, no backend; honest caveat — the
  local clock is a conversion funnel/deterrent, not DRM (server-issued licenses
  remain the unforgeable path). The offline `modelpilot demo` stays free anytime.
- **Landing page is now a public free-trial site** (no more password gate /
  `noindex`): "Start your free 7-day trial" CTA, trial-first how-to (no key for
  the first 7 days, license after), updated bundled site and `validate_local.sh`
  (no longer requires a license — runs on the trial).

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
