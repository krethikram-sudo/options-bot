# ModelPilot — Running TODO (founder)

Living checklist. Claude keeps this current as we work. Last updated: **2026-06-18 (eve)**.
(Detailed legal/terms analysis lives in `modelpilot/LAUNCH_CHECKLIST.md`; this is the
short, prioritized running list.)

Live URLs:
- Marketing: https://modelpilot.pages.dev/
- Console (admin + customer): https://modelpilot-console-prod.fly.dev/  (admin → `/admin`)
- Brain: https://modelpilot-brain-prod.fly.dev/  (health: `/health`)

> **▶️ RESUME HERE next session:** Launch blocker #1 (deploy) DONE — console + brain deployed,
> Fly billing card added (2026-06-16, per founder). Remaining launch path: **(2) founder track —
> form entity → live Stripe → $99 price**, **(3) security — rotate leaked key, SMTP, admin password**,
> **(4) counsel review**. Everything is committed/pushed. **Two quick ops steps now queued (see Security):
> `fly deploy` the console (to ship the 2026-06-18 guidance-billing + funnel + feedback changes) and flip
> on Cloudflare Web Analytics.**
>
> **PROGRESS 2026-06-17:** Nav decluttered. Deep competitor research added
> (`MARKET_STUDY_2026.md`, `TOKEN_OPTIMIZATION_THESIS.md`, + proof/billing audit): durable
> angle = the independent **proven-savings referee** with savings-based billing; control-arm
> measurement is the only uncontested piece (savings-share billing itself is copyable from cloud
> FinOps — ProsperOps/Zesty/nOps). Shipped router **v0.37.0** (long-document summarization now
> floors Sonnet — fixes a smoke-test-found false-downgrade; CI green). Ran a full **smoke test,
> offline + LIVE**: signup→billing lifecycle all pass; **live measured ~40.7% savings, 4/5
> switches judged non-inferior**, and the control-arm flagged one Haiku extraction as degraded
> (the measurement working as intended). Vendor Anthropic credits **refilled**; golden-set
> judge-upgrade batch submitted (81 `synthetic_heuristic` → `ai_judge`, in progress).
>
> **STRATEGY (2026-06-16, after deep competitor + market research):** ICP re-cut to the
> **"spend-maturity moment"** (Claude-heavy teams with a real, growing, finance-visible bill and no one
> to fix it) — NOT "small/non-tech startups" (they're on $20 seats, unmonetizable). Lead with
> **done-for-you + proof + pay-on-savings**; privacy is the trust-unlock, regulated = premium expansion.
> See revised `ICP.md` + `GTM_PLAN.md` (bill-shock motion) + `COMPETITIVE.md` (2026-06-16). **#1 next
> business action: validate willingness-to-pay — 5–10 bill-shock pilots before investing further.**

---

## 🆕 Outlay (active brand/site)

Outlay = the spend-attribution + forecasting product; ModelPilot routing is the embedded
optimization engine within it. Marketing site rebranded to **Outlay** and moved to the brand domain.

- [x] Site live on **https://outlay-ai.com** (Cloudflare Pages custom domain; registered at Cloudflare,
      apex + www CNAME → `modelpilot.pages.dev`). Canonical/OG flipped to outlay-ai.com, extensionless
      clean URLs, `modelpilot.pages.dev/*` 301 → outlay-ai.com. (PRs #8, #9.)
- [ ] **Swap site email CTAs → `hello@outlay-ai.com`.** Set up **Cloudflare Email Routing** on the
      `outlay-ai.com` zone (inbound forward to personal inbox; for *sending as* hello@, add a Gmail
      "Send mail as" via a free SMTP relay or move to Workspace/Fastmail). Once verified, Claude swaps
      every `mailto:krethikram@gmail.com` across `modelpilot/site/**` → `hello@outlay-ai.com` in one PR
      (keeping the prefilled subject lines). **Founder: reply "email is live" when ready.**
- [ ] **Send the design-partner outreach** (`OUTLAY_PILOT_OUTREACH.md`) — 3–5 pilots; the real
      validation gap is end-to-end ticket coverage + a measured forecast-accuracy number on a real team.

---

## ✅ Done

### 2026-06-19 — Outlay product built into the console
- [x] **Spend dashboard, backlog estimator, budgets** (`/app/outlay`, `/app/outlay/estimate`,
      `/app/outlay/budgets`) — the engine (`outlay/`) wrapped for the web app via `outlay_app.py`;
      reuses the console's auth/accounts/billing. Estimator runs off a serialized `_model` so it works
      after either an upload or a live sync. (PRs #21–26.)
- [x] **Live connectors** — pull read-only from GitHub Issues / Jira / Linear + the Anthropic Admin
      API (`/app/outlay/connect` → "Sync now"); engine transport seam keeps it offline-testable. (#27.)
- [x] **Connector tokens encrypted at rest** — Fernet keyed off `CONSOLE_SECRET` (`secret_box.py`),
      `enc:`-prefixed, graceful passthrough if `cryptography` absent. A DB leak no longer exposes keys. (#28.)
- [x] **Scheduled auto-sync** — per-connection Off/Daily/Weekly; due connections re-synced by
      `_run_due_syncs` (resilient per-account). Drive it with an in-process loop (`OUTLAY_AUTOSYNC_EVERY_MIN`)
      or an external scheduler hitting `POST /internal/outlay/sync-due` with `OUTLAY_CRON_TOKEN`. +tests (99 pass).
- [x] **Cursor usage source** — second AI-spend connector alongside the Anthropic Admin API
      (`CursorAdminClient`); a team can connect either or both and `sync` merges the usage events.
      Cursor admin key encrypted at rest like the rest. +tests (103 pass). Catches seats running
      premium models on trivial work even when they're in Cursor, not the API.
- [x] **Per-project / epic budgets** — budgets now scope to `overall | team | class | project`. Project
      spend rolls up by ticket-key prefix (`PROJ-123 → PROJ`); the budgets page shows a "Spend by project"
      pick-list so you know which keys to budget. Scope is validated server-side. +tests (106 pass).
- [x] **Dashboard polish — trend + sync status.** Each genuine refresh (run/sync/auto-sync) appends a
      spend snapshot (`outlay_history`); the Spend dashboard now shows a "↑/↓ % vs last sync" delta on the
      AI-spend KPI, an inline SVG sparkline of recent spend, and a "Last refreshed · cadence" status line.
      Estimate re-saves don't pollute history. +tests (108 pass).
  - **Outlay product loop is feature-complete for a pilot.** Remaining is deployment + go-to-market
    (below). **Needs `fly deploy` to go live.**

### 2026-06-18
- [x] **Guidance is now trial-only; paid = autopilot (billable) only.** Verified guidance/free-tier can
      never bill (three guards: guidance never applies switches → 0 realized savings; `report_usage`
      refuses non-paid plans; refuses savings≤0). Enforced: `update_settings` rejects guidance when paid,
      `convert_to_paid` flips to autopilot, `entitlement` treats paid as autopilot, UI hides guidance for
      paid. +test.
- [x] **Legal docs revised (3 passes) + Google-Doc'd for counsel.** Delaware governing law; §10 indemnity =
      no representation about Anthropic's indemnity; hosted-gateway carve-outs ("processed in memory… not
      persisted") across all six docs; liability-cap split flagged; AUP Usage-Policy suspension right.
      Code audit confirmed "not persisted" holds (no prompt/body logging in the request path). Pending:
      founder (subprocessor vendor names, entity/signatures) + attorney (SCC Module 2 annexes, CA
      enforceability). Package: `LEGAL_REVIEW_PACKAGE.md`.
- [x] **Removed proprietary "Routes to" / "Typically routed" columns** from the public savings tables
      (landing + where-we-save); kept Work type + Cut vs Opus. Full detail stays internal.
- [x] **Launch-post drafts** — `LAUNCH_POSTS.md` (Show HN / r/LocalLLaMA / r/SaaS), honest + value-first,
      lead with the free no-signup estimator.
- [x] **Golden-set judge upgrade (safe partial merge).** Batch (243) succeeded; AI judge wanted to
      downgrade 24 protected/hard prompts to Haiku/Sonnet on single-output grades → **held those for human
      review** (`needs_human_review` + `ai_judge_suggested` in `labels.jsonl`), upgraded 57 rows to
      `ai_judge`. Gate still 0% false-downgrade (cov 60.7%, acc 77.3%). *The 24 held rows are the worklist
      for the human-label pass below.*
- [x] **Product metrics + feedback (console).** `activation_funnel()` (signed-up → set-up → routed →
      proven savings → paid) on the admin overview; dashboard thumbs/comment widget + `/app/feedback`;
      cancel-reason captured on delete (feedback NOT cascade-deleted → churn reasons survive); admin
      "Recent feedback" panel. +test; console suite 79 passed. **Needs `fly deploy` to go live.**
- [x] **Privacy-clean marketing analytics — disclosed.** Privacy Policy now covers cookieless, no-PII
      analytics. **Enable via Cloudflare Pages → Web Analytics toggle** (zero code/token). ⬇️ see ops.

### 2026-06-17
- [x] **Nav UX decluttered** — top nav trimmed 9→6 links, link-text no longer wraps (static + Astro).
- [x] **Deep competitor + market research** — `MARKET_STUDY_2026.md` (neutral landscape; 5 acquisitions
      in 12mo; routing/caching commoditizing), `TOKEN_OPTIMIZATION_THESIS.md` (academic review across 5
      technique families; edge ≠ a token trick), + a competitor proof/billing audit. Net: durable angle is
      the **independent proven-savings referee** + savings-based billing; control-arm measurement is the
      only uncontested piece (savings-share billing is copyable from cloud FinOps).
- [x] **Router v0.37.0** — long-document summarization now floors at Sonnet (context-size promotion);
      +3 golden long-summary rows; full suite 210 passed; `modelpilot-ci` green.
- [x] Console deployed to Fly (`modelpilot-console-prod`), admin login working.
- [x] Brain deployed to Fly (`modelpilot-brain-prod`), healthy, wired to console via `CONSOLE_URL`.
- [x] Customer landing CTAs repointed to the live console (free `.fly.dev` route).
- [x] Sign out returns users to the public landing page (`LANDING_URL`, default pages.dev). **Live.**
- [x] Customers can delete their account (Settings → Danger zone; cascade-deletes all data,
      cancels Stripe sub, email-confirm required, owner-only). **Needs `fly deploy` to go live.**
- [x] Stripe billing migrated to the Meter Events API; convert-to-paid logs errors (not swallowed).
- [x] **Stripe TEST mode verified** — real Checkout + card collection + paid conversion works.
- [x] **Core end-to-end smoke test PASSED** — real Claude traffic → gateway → hosted brain routed
      57% → savings metered to the console; dashboard shows requests/routed + baseline-vs-actual.
      (Dollar value sub-cent on trivial test traffic — pipeline proven, magnitude needs real volume.)
- [x] Anthropic terms verified for the BYOK proxy; customer disclosures added (Terms §10 + docs).
- [x] Hero headline: "Cut your Claude bill through model optimization."
- [x] Dashboard $/tokens toggle (customer + admin): "equivalent tokens saved" view (savings $
      expressed as Opus-4.8-equivalent tokens, ~$15/1M blended, clearly labeled).
- [x] Landing page de-vibecoded: SVG icons, honest "example" labels, Space Grotesk + mono
      eyebrows, Apple-style scroll animations (staggered reveals both directions, hero parallax,
      count-up, hover-lift).
- [x] Dashboard leads with **% bill reduction** (early-confidence metric) + $/tokens detail.
- [x] Console restyled to match the brand: balanced dark canvas + light cards, Space Grotesk,
      violet accents, page-wide entrance animations + hover transitions.
- [x] Signed-in IA redesign: **left sidebar**, 6 tabs -> 4 (Home/Setup/Settings/Billing),
      **setup-first** routing (new customers -> Setup; set-up -> Home), onboarding welcome.
- [x] Free-trial enforcement: app-wide countdown + escalating banners + sidebar pill; console
      gated to Billing once the trial ends unconverted (routing already stops via entitlement).
- [x] 2FA: opt-in email one-time-code (Settings enroll + login challenge); SMS scaffolded via
      Twilio (`TWILIO_*`) when you add a provider.
      (All console UI/auth changes need a `fly deploy` to go live.)
- [x] **ICP/GTM doc** (`modelpilot/ICP.md`) — sharp ICP, target verticals, qualifying questions,
      per-vertical messaging, moat-hardening (SOC-2/HIPAA/on-prem). Internal-only (in migrate list).
- [x] **Zero-collection moat decision** (`FLEET_LEARNING.md`): do NOT build cross-customer data
      collection (asterisk on the privacy promise + data-processor liability). Cold-start comes from a
      self-owned eval corpus instead; per-customer tuning stays 100% local. ICP.md moat #4 reframed.
- [x] **Cold-start from our own data**: golden set 69→**147** prompts (synthetic ICP + naturalistic
      general traffic, no real PII/PHI). Gate 0.60: coverage ~60%, accuracy ~79%, **false-downgrade 0%**.
      Naturalistic (non-telegraphed) phrasings keep it an honest test, not teaching-to-the-test; the one
      issue it surfaced was an over-conservative label on our side, corrected. CALIBRATION v0.3;
      `label_source` provenance added.
  - [x] **Upgrade new-prompt labels `synthetic_heuristic` → `ai_judge`** — DONE 2026-06-18 (safe partial
        merge). Batch of 243 succeeded; the AI judge wanted to downgrade 24 protected/hard prompts to
        Haiku/Sonnet on single-output grades, so those were HELD on conservative labels and flagged
        `needs_human_review` + `ai_judge_suggested`; 57 rows upgraded to `ai_judge`. Gate still 0%
        false-downgrade (150 rows; cov 60.7%, acc 77.3%). **The 24 held rows feed the human-label pass ↓.**
  - [ ] **Human-label the open-ended slice** (the real trust gap): run `scripts/build_label_worksheet.py`
        → fill the 53 open-ended-category rows → `--apply` (sets `label_source: human`). Then the
        open-ended floors can be trusted/lowered. Keep growing toward 300–1000 via this + consented
        shadow traffic (never synthetic-only). **This one is yours/a labeler's — I can't fake human labels.**
- [x] **Self-optimize tier: evaluation + decision tooling** (`modelpilot/SELF_OPTIMIZE_EVAL.md`).
      Measured uplift from tuning on own data: ~35% more savings (realistic) / up to ~51% (ceiling),
      i.e. coverage 56%→~77%. Break-even: pays for itself above ~$300–500/mo savings. Personalized
      PAYG-vs-Self-optimize panel on the console billing page (uses the customer's real savings; shows
      rate-cut-only worst case + tuning-uplift range); "Which tier?" explainer on the site pricing
      section. Learned floors now **gated** to self_optimize/managed at `/api/policy` so the
      differentiation is real. Honest: uplift is illustrative; exact figure measured per-customer (RCT).
- [x] **/compare pages** — honest comparisons vs gateways & routers (`compare.html`,
      `compare-openrouter.html`, `compare-martian.html`), cross-linked; lead with the privacy wedge.
- [x] **/healthcare vertical landing page** (`modelpilot/site/healthcare.html`) — PHI-never-leaves
      messaging, honest "not yet certified / ask us about a BAA" stance; linked from landing privacy
      section. SOC-2/HIPAA readiness checklist added to `LAUNCH_CHECKLIST.md` (founder/auditor path).
- [x] **Quality is now first-class on the dashboard** — top-grid "Quality preserved" card (measured
      non-inferiority rate when available, else "Protected" via floor + auto-escalation with live
      escalation counts). Makes the #1 autopilot objection ("will it degrade my outputs?") visible.
- [x] **Gradual autopilot rollout ramp** — `autopilot_pct` setting (10/25/50/100%); brain honors it
      as a canary gate (held-back switches stay recommendations, not auto-applied). Build trust, then
      ramp to 100%. Surfaced under Routing mode on dashboard + Settings.
- [x] **Savings levers beyond model choice** — routing brain emits advisory opportunities: prompt
      caching (large uncached reused prefix) + Batch API (latency-tolerant traffic), with honest
      server-side economics (`pricing.cache_savings` / `batch_savings`). (Skipped max_tokens — billing
      is on actual output, not the cap, so trimming it doesn't cut normal cost.)

## 🔜 Next (in progress)
- [x] **Deployed the latest console + brain** (2026-06-16) — account deletion, quality dashboard,
      autopilot ramp, savings/caching cards, billing decision panel, `/api/policy` tier gate, loading
      bar, always-on console all now live. (Delete the stuck "bypass-paid" test account if still present.)
- [ ] **Confirm the leaked Anthropic API key is rotated** — if the smoke test used a fresh key and
      the old one was deleted in the Anthropic console, this is done; otherwise rotate it.
- [x] **Smoke test (offline + LIVE) PASSED — 2026-06-17.** Offline: real router decisions on a
      22-prompt ICP basket + full console lifecycle (signup→entitlement→metering→convert) all green;
      golden eval 0% false-downgrade. **Live (real Claude): ~40.7% MEASURED savings on a real sample,
      4/5 switches judged non-inferior by Opus; control-arm flagged one Haiku extraction as degraded.**
      Harnesses: `scripts/smoke_icp.py`, `smoke_console.py`, `smoke_live.py`. Next: a larger real
      sample (or a customer's traffic) for a statistically solid number.
- [ ] **Stripe LIVE mode — GATED on the entity.** Set up the *live* Stripe account under the
      **company** (entity + EIN + business bank account), NOT personal/SSN — commingling weakens the
      liability veil and complicates taxes. So: form entity → EIN → business bank → activate Stripe
      live (redo the 3 keys with `sk_live_…`). Do this only after the entity exists.
- [ ] **Rotate the leaked Anthropic API key** (pasted in an earlier session — treat as compromised).
- [ ] **Self-optimize $99/mo + 15% — Stripe price setup (Thursday).** Two prices:
      (1) the **metered price @ $0.01/unit** → `STRIPE_PRICE_ID` (we report the bill in cents with the
      tier rate applied in code, so one price bills 20% PAYG / 15% subscription tiers — do NOT use
      $0.20); (2) the **flat $99/mo** price → `STRIPE_SELFOPT_PRICE_ID` (else only the metered 15% is
      charged, not the $99). Billing code audited + fixed 2026-06-16: tier rate now actually charged
      (was 20% flat), inline meter push marks rows so the sync backstop can't double-bill, and sync
      only bills post-conversion (no trial-period over-billing). Tests cover all three.
- [ ] **Managed pricing still TBD** (research suggests ~$499/mo + 15%). Decide, then set
      `STRIPE_MANAGED_PRICE_ID` and replace "coming soon" on the Managed card.
- [ ] **Guardrail "compare" mode against trial overspend + keep its compute on the customer's box.**
      `modelpilot compare [--judge]` runs each prompt **~2–3× on the customer's own Anthropic key**
      (baseline arm + routed arm + judge ≈ a few $ per 20 prompts), so unbounded use during the free
      trial runs up *their* bill and sours the trial.
      (a) **Restrict during trial:** cap prompts-per-run + runs-per-day (or require explicit confirmation
          of the estimated spend before it runs), surfaced honestly in the CLI/console.
      (b) **Keep compute + cost on the customer's system with THEIR key:** `compare.api_run_fn` already
          uses the customer key and the judge pins to the real API via env `ANTHROPIC_API_KEY` — confirm/
          enforce that env is always the customer's key on their own box, never our hosted infra/vendor
          key (consistent with BYOK + prompts-never-leave-the-box).

## 🏛️ Legal / corporate
- [ ] **Form the entity — DECISION: Delaware C-corp via Stripe Atlas** ("might raise later" → C-corp
      avoids a costly conversion). **Scheduled for Thu 2026-06-18.** Full step-by-step in
      `modelpilot/ENTITY_FORMATION.md`. Atlas bundles C-corp + EIN + business bank + live Stripe in one
      flow (clears most of launch #2). ⏰ **Watch the 83(b) election — hard 30-day deadline after stock
      issuance.** Confirm equity/tax specifics with a CPA. **Trademark "ModelPilot" already checked —
      clear/not taken.**
- [ ] Counsel review of legal templates (Terms / Privacy / AUP / MSA / DPA); set governing law + venue.
- [x] Trademark knockout "ModelPilot" — checked, clear/not taken (2026-06-16). Optional next: file the
      USPTO word mark to lock it in (https://www.uspto.gov/trademarks).
- [ ] Get written Anthropic confirmation of the BYOK-proxy model (enterprise comfort; optional).

## 💳 Finance / ops
- [ ] Stripe Tax / sales-tax nexus review (with CPA).
- [ ] Tech E&O + cyber-liability insurance before real production traffic.

## ⚙️ Vendor ops
- [x] **Vendor Anthropic API account topped up** (refilled 2026-06-17). Was blocking our
      *internal* model use — golden-set judge labeling, smoke tests, any vendor-side eval. Does NOT
      block customer routing (that's BYOK — customers use their own key). Tie this to rotating the
      leaked key + moving billing to the business card once the entity exists.

## 🔒 Security / go-live
- [x] **Fly.io billing** — card added (2026-06-16); console deployed **always-on**
      (`min_machines_running = 1`, `auto_stop = off`) so the signed-in UX has no cold-start lag.
      Brain stays scale-to-zero (fails open). TODO: move Fly billing to the business card once the
      entity exists.
- [ ] Verify `CONSOLE_SECRET` is a **stable** Fly secret (don't rotate casually — it logs everyone out).
- [ ] **Configure SMTP** (`SMTP_*` Fly secrets) — REQUIRED for 2FA codes, password resets, and budget
      alerts to actually send (without it they're only logged in dev). See `console/FLY_DEPLOY.md`.
      Optional: `TWILIO_*` for SMS 2FA.
- [ ] Change any seeded/default admin password; confirm strong admin credentials.
- [ ] **`fly deploy` the console** to ship the 2026-06-18 changes (guidance-trial-only billing policy,
      activation funnel + feedback widget + cancel-reason, hidden-guidance-for-paid UI). They're committed
      but not live until deployed.
- [ ] **Enable Cloudflare Web Analytics** on the Pages project (Dashboard → Web Analytics → add the site).
      Cookieless, no token in repo; the Privacy Policy disclosure is already in place.
- [ ] (Optional) Custom domain `app.modelpilot.app` via `fly certs add` — currently on free `.fly.dev`.

## 🧩 Product (optional / later)
- [ ] **Tuning model = Option A (metadata-only), chosen for the moat.** Per-customer tuning is driven by
      traffic metadata (labels, token counts, outcomes) — never prompt content — and ALL routing/tuning
      IP stays server-side (the shipped client carries none of it; leak-audit-enforced in
      `scripts/build_client.sh`). So customers can't take the codebase and DIY. **Option B** (ship a
      *licensed* on-box judge that tunes on actual prompt content, staying local) is a possible future
      upgrade — only if worth the added surface; defended by license + brain entitlement + updates, not
      secrecy. Site/console copy now reflects Option A.
- [x] **Realize the savings opportunities (surfacing)** — gateway emits per-request
      `x-modelpilot-opportunity-*` headers + records to the ledger; metering reports aggregate
      `opportunity_saved` to the console; dashboard shows an "Additional potential savings" callout.
      Advisory/estimated, never billed.
- [x] **Opt-in auto-apply of prompt caching** (`MODELPILOT_AUTO_CACHE=1`) — gateway adds an ephemeral
      cache breakpoint to large reusable system prompts, capturing the caching opportunity automatically.
      Conservative (no-op if already cached / no sizable system / below a safe size floor); compatible
      with tools/structured output; `x-modelpilot-cache-applied` header. Off by default.
- [x] **Caching savings: measured & shown free, never billed** (founder decision: "show but don't bill").
      Exact $ from real usage tokens (`pricing.realized_cache_savings`), credited only when WE applied
      caching; rolls up to a "Caching savings captured" goodwill line on the dashboard. Only model-routing
      savings (control-arm proven) bill. (Mechanism exists to bill it later at any rate if desired.)
- [ ] End-to-end smoke test: sign up (test acct) → Connect gateway → send traffic → see savings on dashboard.
- [ ] `ingest/` opt-in telemetry service (optional; deploys like the brain on port 8500).
