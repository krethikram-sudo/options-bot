# ModelPilot — Running TODO (founder)

Living checklist. Claude keeps this current as we work. Last updated: **2026-06-15**.
(Detailed legal/terms analysis lives in `modelpilot/LAUNCH_CHECKLIST.md`; this is the
short, prioritized running list.)

Live URLs:
- Marketing: https://modelpilot.pages.dev/
- Console (admin + customer): https://modelpilot-console-prod.fly.dev/  (admin → `/admin`)
- Brain: https://modelpilot-brain-prod.fly.dev/  (health: `/health`)

---

## ✅ Done
- [x] Console deployed to Fly (`modelpilot-console-prod`), admin login working.
- [x] Brain deployed to Fly (`modelpilot-brain-prod`), healthy, wired to console via `CONSOLE_URL`.
- [x] Customer landing CTAs repointed to the live console (free `.fly.dev` route).
- [x] Anthropic terms verified for the BYOK proxy; customer disclosures added (Terms §10 + docs).
- [x] Hero headline: "Cut your Claude bill through model optimization."

## 🔜 Next (in progress)
- [ ] **Stripe activation — TEST mode now** (free, reversible; no entity/bank needed). Create a
      metered ($0.20/unit, sum) price → set `STRIPE_SECRET_KEY` / `STRIPE_PRICE_ID` /
      `STRIPE_WEBHOOK_SECRET` Fly secrets → test convert-to-paid with card `4242…`. **Open question:**
      does Stripe show legacy *usage-records* or the new *meter* flow? If meter-only, Claude updates
      `console/stripe_billing.py` to the Meter Events API.
- [ ] **Stripe LIVE mode — GATED on the entity.** Set up the *live* Stripe account under the
      **company** (entity + EIN + business bank account), NOT personal/SSN — commingling weakens the
      liability veil and complicates taxes. So: form entity → EIN → business bank → activate Stripe
      live (redo the 3 keys with `sk_live_…`). Do this only after the entity exists.
- [ ] **Rotate the leaked Anthropic API key** (pasted in an earlier session — treat as compromised).

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
- [ ] Verify `CONSOLE_SECRET` is a **stable** Fly secret (don't rotate casually — it logs everyone out).
- [ ] Change any seeded/default admin password; confirm strong admin credentials.
- [ ] (Optional) Custom domain `app.modelpilot.app` via `fly certs add` — currently on free `.fly.dev`.

## 🧩 Product (optional / later)
- [ ] End-to-end smoke test: sign up (test acct) → Connect gateway → send traffic → see savings on dashboard.
- [ ] `ingest/` opt-in telemetry service (optional; deploys like the brain on port 8500).
