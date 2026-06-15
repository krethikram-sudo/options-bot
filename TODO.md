# ModelPilot — Running TODO (founder)

Living checklist. Claude keeps this current as we work. Last updated: **2026-06-15 (eve)**.
(Detailed legal/terms analysis lives in `modelpilot/LAUNCH_CHECKLIST.md`; this is the
short, prioritized running list.)

Live URLs:
- Marketing: https://modelpilot.pages.dev/
- Console (admin + customer): https://modelpilot-console-prod.fly.dev/  (admin → `/admin`)
- Brain: https://modelpilot-brain-prod.fly.dev/  (health: `/health`)

> **▶️ RESUME HERE next session:** Core loop is proven end-to-end (gateway → brain routed 57% →
> metered to console → dashboard shows baseline-vs-actual). Remaining: confirm the leaked Anthropic
> key is rotated, deploy the account-deletion feature, and (founder track) form the entity to unlock
> live Stripe. Everything is committed/pushed.

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

## 🔜 Next (in progress)
- [ ] **Deploy the account-deletion feature** — `cd ~/options-bot && git pull && fly deploy`
      (then delete the stuck "bypass-paid" test account).
- [ ] **Confirm the leaked Anthropic API key is rotated** — if the smoke test used a fresh key and
      the old one was deleted in the Anthropic console, this is done; otherwise rotate it.
- [ ] (Optional) Re-run the smoke test with realistic traffic to see a meaningful savings $ figure.
- [ ] **Stripe LIVE mode — GATED on the entity.** Set up the *live* Stripe account under the
      **company** (entity + EIN + business bank account), NOT personal/SSN — commingling weakens the
      liability veil and complicates taxes. So: form entity → EIN → business bank → activate Stripe
      live (redo the 3 keys with `sk_live_…`). Do this only after the entity exists.
- [ ] **Rotate the leaked Anthropic API key** (pasted in an earlier session — treat as compromised).
- [ ] **Set the subscription $ for Self-optimize & Managed** (pricing research running). Tier model is
      built end-to-end in the console: (1) Pay-as-you-go = 20% of savings; (2) Self-optimize =
      subscription + 15% (unlocks local tuning); (3) Managed = subscription + 15%. To go live on the
      subscription: create two flat monthly Stripe prices and set `STRIPE_SELFOPT_PRICE_ID` /
      `STRIPE_MANAGED_PRICE_ID` Fly secrets — then update the "pricing coming soon" copy on the
      landing with the numbers. (Metered 20%/15%-of-savings already works.)

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

## 🔒 Security / go-live
- [ ] **Fly.io billing** — free trial ended; add a card (fly.io/dashboard → Billing) to keep
      `modelpilot-console-prod` + `modelpilot-brain-prod` alive. Both are now **scale-to-zero**
      (`fly deploy` each to apply) → ~$0 compute when idle + ~$0.30/mo volumes. Move Fly billing to
      the business card once the entity exists.
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
- [ ] End-to-end smoke test: sign up (test acct) → Connect gateway → send traffic → see savings on dashboard.
- [ ] `ingest/` opt-in telemetry service (optional; deploys like the brain on port 8500).
