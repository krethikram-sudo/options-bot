# ModelPilot — Running TODO (founder)

Living checklist. Claude keeps this current as we work. Last updated: **2026-06-15 (eve)**.
(Detailed legal/terms analysis lives in `modelpilot/LAUNCH_CHECKLIST.md`; this is the
short, prioritized running list.)

Live URLs:
- Marketing: https://modelpilot.pages.dev/
- Console (admin + customer): https://modelpilot-console-prod.fly.dev/  (admin → `/admin`)
- Brain: https://modelpilot-brain-prod.fly.dev/  (health: `/health`)

> **▶️ RESUME HERE next session:** Launch blocker #1 (deploy) DONE — console + brain deployed,
> Fly billing card added (2026-06-16, per founder). Remaining launch path: **(2) founder track —
> form entity → live Stripe → $99 price**, **(3) security — rotate leaked key, SMTP, admin password**,
> **(4) counsel review**. Everything is committed/pushed.

---

## ✅ Done
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
  - [ ] **Upgrade new-prompt labels from `synthetic_heuristic` → `ai_judge`** via the canonical
        pipeline (`python -m modelpilot.goldenset.build submit/collect/judge/label` on the 78 new
        prompts). ATTEMPTED 2026-06-16: batch generation succeeded (234 outputs) but the **judge step
        failed — vendor Anthropic account out of credits**. Corpus kept its honest `synthetic_heuristic`
        labels (147 rows: 69 seed-judge + 78 synthetic; still 0% false-downgrade). Re-run after topping
        up credits — it's just `judge` + `label`.
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
- [ ] (Optional) Re-run the smoke test with realistic traffic to see a meaningful savings $ figure.
- [ ] **Stripe LIVE mode — GATED on the entity.** Set up the *live* Stripe account under the
      **company** (entity + EIN + business bank account), NOT personal/SSN — commingling weakens the
      liability veil and complicates taxes. So: form entity → EIN → business bank → activate Stripe
      live (redo the 3 keys with `sk_live_…`). Do this only after the entity exists.
- [ ] **Rotate the leaked Anthropic API key** (pasted in an earlier session — treat as compromised).
- [ ] **Self-optimize priced at $99/mo + 15%** (live on the site/console). To actually CHARGE the $99:
      create a **$99/mo recurring price in Stripe** and set the `STRIPE_SELFOPT_PRICE_ID` Fly secret —
      checkout then bills $99/mo + the metered 15%. (Until then, upgrading records the tier + bills the
      15% metered piece; the $99 isn't collected.)
- [ ] **Managed pricing still TBD** (research suggests ~$499/mo + 15%). Decide, then set
      `STRIPE_MANAGED_PRICE_ID` and replace "coming soon" on the Managed card.

## 🏛️ Legal / corporate
- [ ] **Form the entity — S-corp.** Note: "S-corp" is a *tax election*, not an entity type — usually
      an LLC (or C-corp) that elects S-corp tax treatment. Confirm with a CPA: LLC + S-election for a
      bootstrapped solo founder, **or** Delaware C-corp if raising VC (S-corp can't take VC/foreign
      owners). Then: EIN → business bank account → keep finances separate.
- [ ] Counsel review of legal templates (Terms / Privacy / AUP / MSA / DPA); set governing law + venue.
- [ ] Trademark knockout-search "ModelPilot"; file a word mark if clear.
- [ ] Get written Anthropic confirmation of the BYOK-proxy model (enterprise comfort; optional).

## 💳 Finance / ops
- [ ] Stripe Tax / sales-tax nexus review (with CPA).
- [ ] Tech E&O + cyber-liability insurance before real production traffic.

## ⚙️ Vendor ops
- [ ] **Top up the vendor Anthropic API account** (out of credits as of 2026-06-16). Blocks our
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
