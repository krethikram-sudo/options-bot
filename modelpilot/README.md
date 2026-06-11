# ModelPilot (working name)

**One-liner:** A model-routing copilot for enterprise AI spend. It reads each prompt (and its
conversation context), tells you the cheapest Claude model that will do the job well, optionally
switches the model for you, and proves the savings with statistically honest numbers.

## The problem

Enterprises burn AI budget faster than planned because every request defaults to the biggest,
most expensive model. Most requests don't need it. With current Claude pricing
(June 2026, per million tokens):

| Model | Input | Output | Typical role |
|---|---|---|---|
| Claude Fable 5 (`claude-fable-5`) | $10.00 | $50.00 | Frontier — hardest reasoning |
| Claude Opus 4.8 (`claude-opus-4-8`) | $5.00 | $25.00 | Long-horizon agentic, complex work |
| Claude Sonnet 4.6 (`claude-sonnet-4-6`) | $3.00 | $15.00 | Workhorse — most production tasks |
| Claude Haiku 4.5 (`claude-haiku-4-5`) | $1.00 | $5.00 | Classification, extraction, simple Q&A |

A correctly routed Opus→Haiku request costs ~80% less. Opus→Sonnet, ~40% less. If even a third
of an org's traffic is over-modeled (it's usually more), the savings are a line item the CFO
notices.

## What the product does

1. **Per-prompt model guidance**, based on the prompt text *and* the chat context (conversation
   length, what model handled earlier turns, whether a cached prefix exists, task category).
2. **Two operating modes:**
   - **Advise (Mode 1):** surfaces the recommendation; the user/team takes the action.
   - **Autopilot (Mode 2):** rewrites the model on the request automatically, within
     admin-configured guardrails.
3. **Live savings ticker** in both modes — tokens and dollars saved per request and cumulative,
   computed against a defensible counterfactual baseline.
4. **A results dashboard** that proves value statistically (randomized holdout + counterfactual
   ledger), not just with a vanity number.

## The make-or-break problem

The recommendation must be right. One visible quality regression from a downgrade costs more
trust than a hundred correct downgrades earn. The entire tuning methodology
(`ROUTER_TUNING_PLAN.md`) is built around an asymmetric objective: **never downgrade unless
confident the cheaper model is non-inferior for this prompt; when unsure, do nothing.**

## Phase 0 implementation (this folder)

A working gateway + router v0 + ledger + report lives here:

| File | What it is |
|---|---|
| `gateway.py` | FastAPI drop-in proxy — shadow / advise / autopilot modes |
| `router.py` | Session-context-aware classifier (follow-ups inherit session difficulty; mechanical tasks keep their cheap tier) + cache-aware economics layer + optional Haiku-4.5 second opinion |
| `pricing.py` | Price table, cost math, `net_switch_benefit` (the cache-trap guard) |
| `taxonomy.py` | Task categories and the category→model-floor policy table |
| `ledger.py` | SQLite counterfactual ledger (no prompt text stored) |
| `report.py` | Savings report CLI — Layer-1 estimates, escalation netting, RCT arm comparison with bootstrap CIs |
| `compare.py` | Side-by-side proof harness: routed vs all-baseline on the same prompts, HTML report with costs + outputs + non-inferiority verdicts (`modelpilot compare`) |
| `site/` | Static landing page — deployed to GitHub Pages from the published beta repo (`pages.yml`) |
| `dashboard.py` | Web dashboard at `/modelpilot/dashboard` (+ `/modelpilot/stats` JSON) — headline cards, cumulative savings curve, model-mix migration, RCT panel; server-rendered SVG, zero JS/CDN deps |
| `continuation.py` | Expected-remaining-conversation model (mean residual life over observed session lengths) feeding the cache-switch economics |
| `goldenset/` | Tuning pipeline: Batch API fan-out, position-debiased non-inferiority judge, cheapest-non-inferior labeling, router evaluation + confidence-gate tuning |
| `tests/` | 41 tests covering pricing, routing, modes, holdout, feedback, golden-set pipeline, continuation model, dashboard |

### Two-minute demo

```bash
python -m modelpilot.demo --offline        # no API key, no spend
python -m modelpilot.demo                  # real API (needs ANTHROPIC_API_KEY), < $1
```

Spawns a gateway in autopilot on :8401, replays a mixed workload through it,
prints every routing decision live (switches, below-gate advice, holdout
control requests), then leaves the dashboard up at
`http://127.0.0.1:8401/modelpilot/dashboard?days=0`. Flags: `--mode`,
`--prompts`, `--fresh`, `--max-tokens`.

### Using it with your Claude account

| Surface | How | Modes |
|---|---|---|
| **API keys** | Point `base_url` at the gateway | shadow / advise / autopilot |
| **Claude Code (subscription)** | The installer's `claude()` wrapper already routes it; the gateway forwards OAuth headers. For real routing: `MODELPILOT_MODE=autopilot ./scripts/install_modelpilot_gateway.sh` | all three |
| **claude.ai web chat** | Load `modelpilot/extension/` as an unpacked browser extension — a chip shows the recommended model + est. value before you send, using the visible conversation for session-context routing | advisory (Mode 1) only in v0; auto-switching the picker needs a ToS review |

Flat-rate subscription surfaces report *API-equivalent usage value* — the
win is rate-limit headroom, not a smaller bill. Dollar savings live on the
API surface.

### Quickstart

```bash
pip install -r modelpilot/requirements.txt

# Start the gateway in shadow mode (nothing altered, everything scored)
MODELPILOT_MODE=shadow uvicorn modelpilot.gateway:app --port 8400

# Point your app at it — one line:
#   client = anthropic.Anthropic(base_url="http://localhost:8400")

# After traffic has flowed, print the would-have-saved report:
python -m modelpilot.report --db modelpilot.db
```

Modes: `MODELPILOT_MODE=shadow|advise|autopilot`; autopilot's confidence gate is
`MODELPILOT_CONFIDENCE` (default 0.8). Advise mode returns
`x-modelpilot-recommended-model` / `x-modelpilot-est-net-benefit-usd` headers on
every response.

### Autopilot trust machinery

- **Randomized holdout:** `MODELPILOT_HOLDOUT_PCT` (default 0.10) keeps a
  session-randomized control arm on the baseline model; the report compares
  arms with bootstrap CIs once both have 30+ requests. Send `x-session-id` to
  pin a conversation to one arm (otherwise the first message is hashed).
- **Feedback / escalation valve:** every response carries
  `x-modelpilot-request-id`. POST `/modelpilot/feedback` with
  `{"request_id", "signal": "negative"}` to flag a bad routed answer, and
  resend the request with `x-modelpilot-retry-of: <id>` — the retry bypasses
  routing (runs exactly what you asked for) and its cost is charged against
  reported savings.

### Corpus v1 from real traffic (capture + export)

Prompt text is never stored by default. To build the next golden set from
real shadow traffic, opt in on the gateway, then export:

```bash
# on the gateway: sample 25% of requests into the captures table
MODELPILOT_MODE=shadow MODELPILOT_CAPTURE_PCT=0.25 python -m uvicorn modelpilot.gateway:app --port 8400

# later: stratified, deduped corpus (filename must stay prompts.jsonl)
python -m modelpilot.goldenset.export_corpus --db modelpilot.db \
    --out goldenset_data/live/prompts.jsonl --per-category 40
# REVIEW THE FILE FOR PII/SECRETS, then run the pipeline on it:
python -m modelpilot.goldenset.build submit --workdir goldenset_data/live
```

Calibration v0 results and the per-category analysis live in
`goldenset_data/CALIBRATION.md`.

### Golden-set tuning pipeline

```bash
# prompts.jsonl rows: {"id", "prompt", "category"?, "expected"?}
python -m modelpilot.goldenset.build submit  --workdir gs/   # fan out via Batch API (50% off)
python -m modelpilot.goldenset.build collect --workdir gs/   # when the batch ends
python -m modelpilot.goldenset.build judge   --workdir gs/   # position-debiased non-inferiority
python -m modelpilot.goldenset.build label   --workdir gs/   # cheapest non-inferior model
python -m modelpilot.goldenset.evaluate --labels gs/labels.jsonl
```

`evaluate` sweeps the confidence gate and recommends the lowest threshold whose
false-downgrade rate meets the ≤2% safety target — that number goes into
`MODELPILOT_CONFIDENCE`.

Run tests: `python -m pytest modelpilot/tests/`

## Shipping the beta (publish workflow)

This folder is the **dev home** (inside the private monorepo, next to the
internal strategy docs). Customers get a separate, clean repo assembled by:

```bash
./scripts/publish_modelpilot.sh /tmp/modelpilot-beta \
    git@github.com:YOUR_ORG/modelpilot.git
```

The script copies an explicit **allowlist** (package, tests, extension,
installer, customer docs, packaging/) — internal docs can't leak by
construction — runs the test suite against the assembled repo, and pushes.
Customer-facing files live in `packaging/` (landing README, pyproject,
LICENSE, CHANGELOG, CI, issue templates). The publish dry-run also runs in
this repo's CI (`.github/workflows/modelpilot-ci.yml`) so a broken publish
is caught on every push.

Iteration loop: develop + calibrate here → `publish_modelpilot.sh` → beta
repo → customers report via issue templates + `modelpilot share` →
captured corpora recalibrate the router → republish.

## Docs in this folder

| Doc | Contents |
|---|---|
| `PRODUCT_DESIGN.md` | Architecture, deployment surfaces (API gateway vs. browser extension), Mode 1/Mode 2 mechanics, savings math, the prompt-cache trap, MVP phasing |
| `ROUTER_TUNING_PLAN.md` | How the router gets accurate and stays accurate: golden dataset, LLM-judge labeling, model choices, asymmetric loss, online feedback loop, drift handling |
| `SAVINGS_DASHBOARD.md` | How we prove it: counterfactual ledger, randomized holdout, replay sampling, dashboard views, the monthly CFO report |

## Strategic posture (short version)

- **Start with the API gateway for enterprises** — that's where Mode 2 is technically clean,
  where spend concentrates, and where measurement is airtight. The claude.ai browser extension
  is a Phase-3 companion, not the wedge.
- **Sell with the shadow-mode report:** deploy in advisory/observe-only mode for two weeks, then
  show "here is the $X you would have saved, with zero quality risk taken." The proof artifact
  *is* the sales motion.
- **Defensibility:** Anthropic (or OpenAI) could ship native routing. Our moat is
  (a) cross-provider neutrality (Claude first, OpenAI/Gemini next), (b) enterprise governance —
  per-team policies, audit trails, budget alerts, and (c) the measurement layer — nobody trusts
  the vendor to grade its own homework on savings.
