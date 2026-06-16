# Entity formation — Delaware C-corp via Stripe Atlas (founder checklist)

Decision (2026-06-16): **Delaware C-corp**, formed via **Stripe Atlas**. Rationale: "might
raise later" → C-corp now avoids a costly LLC→C-corp conversion; VCs/institutional/foreign
investors can't invest in an LLC/S-corp. Atlas bundles C-corp + EIN + business bank + Stripe,
which also clears the downstream launch-#2 items in one flow.

**Not legal/tax advice.** Atlas gives you the scaffolding; still run the equity/tax specifics
(83(b), reasonable salary, franchise-tax method) past a CPA and, if you add cofounders/equity,
a startup attorney.

## Before you start
- [ ] **Trademark knockout-search "ModelPilot"** first (USPTO TESS + a web/domain check) — the
      legal entity name is sticky. If "ModelPilot, Inc." is risky/taken, form under a clear name and
      run "ModelPilot" as the brand/DBA. (This is also a standalone launch TODO.)
- [ ] Have ready: legal name + address, your SSN/ITIN (US founder). **Non-US founder?** Atlas still
      gets an EIN without an SSN — it just takes longer; start early.

## Step 1 — File via Stripe Atlas (atlas.stripe.com, ~$500 + DE fees)
- [ ] Choose **C Corporation**, Delaware.
- [ ] Company name (per knockout above).
- [ ] **Shares: accept Atlas's default 10,000,000 authorized at par $0.00001.** This is deliberate —
      it keeps the DE franchise tax low under the **assumed-par-value method**. (The naive method on
      10M shares can produce a ~$75–85k franchise-tax bill; the assumed-par method makes it ~$400.
      Atlas sets this up correctly — don't change it.)
- [ ] Issue founder shares to yourself. Even solo, consider standard **4-year vesting / 1-year cliff**
      — clean optics for a future raise (optional for solo; ask if unsure).
- [ ] Atlas provides a **Delaware registered agent** (year 1 included).

## Step 2 — The 83(b) election ⏰ (HARD 30-DAY DEADLINE — do not miss)
- [ ] If your founder stock has **any vesting**, file an **83(b) election within 30 days** of the
      stock issuance date. Atlas prompts + pre-fills it, but **you must mail it to the IRS** (certified
      mail, keep the receipt + a copy). Missing this can create a large future tax bill. If unsure
      whether it applies, confirm with the CPA *this week*, not later.

## Step 3 — EIN (Atlas)
- [ ] Atlas obtains the **EIN** automatically after incorporation (days; longer without an SSN).

## Step 4 — Business bank account
- [ ] Open the **business bank account** Atlas offers (e.g. Mercury) using the EIN + formation docs.
- [ ] **Keep finances separate** — no personal/business commingling (preserves the liability shield).

## Step 5 — Live Stripe (this is launch blocker #2's payoff)
- [ ] Activate the **live Stripe account** Atlas links to the new entity (swap `sk_live_…`).
- [ ] In Stripe: create the **$99/mo recurring price** for Self-optimize → set the
      `STRIPE_SELFOPT_PRICE_ID` Fly secret (otherwise Self-optimize bills only the 15% metered piece).
- [ ] (Later) decide Managed price (~$499/mo) → `STRIPE_MANAGED_PRICE_ID`.
- [ ] Re-do the 3 Stripe keys with live values; set the live webhook secret.

## Step 6 — Move billing onto the business card
- [ ] Move **Fly.io billing** and the **vendor Anthropic account** onto the business card/bank.

## Ongoing C-corp obligations (so they don't surprise you)
- [ ] **DE franchise tax + annual report** due **March 1** every year (use the assumed-par method).
- [ ] Registered agent renews annually (Atlas year 1 free, then a fee).
- [ ] C-corp pays **reasonable salary** (payroll) once you take money out — CPA sets this up; differs
      from the LLC/S-corp pass-through you'd have had.
- [ ] Counsel review of the customer legal templates (separate launch TODO) now that there's an entity
      to be the contracting party + set governing law/venue.

## What this unblocks
Entity → EIN → bank → live Stripe → $99 price = **launch blocker #2 done**. Then remaining launch
path is #3 (rotate leaked key, SMTP, admin pw) and #4 (counsel review).
