# Ideal Customer Profile & GTM — ModelPilot (internal)

Drafted 2026-06-15. **Revised 2026-06-16** after deep competitor + market research
(see `COMPETITIVE.md` 2026-06-16 and the research synthesis). Internal (not on the
publish allowlist). Pairs with `COMPETITIVE.md` and `GTM_PLAN.md`.

## The strategy (2026-06-16 revision — what the research changed)
Two findings reshaped the ICP:
1. **Privacy is not the moat we thought.** "Route without ever seeing the prompt" is NOT unique —
   Not Diamond (client-side + fuzzy hash + VPC/local) and self-hosted LiteLLM/Portkey also keep data
   local; routing is being commoditized and given away **free** by AWS Bedrock (intra-Claude ~30%)
   and Anthropic's own caching (~90%) / Batch (50%). Privacy is now a **trust-unlock + premium
   wedge**, not the whole moat.
2. **The genuinely unique, defensible assets are pay-on-realized-savings billing + honest,
   control-arm proof.** And the underserved buyers who value a *done-for-you, zero-risk* version are
   **not** "small/non-tech companies that optimize nothing" (they're on $20 seats with nothing to
   route) — they're companies at a specific **spend-maturity moment**.

## Primary beachhead — the "spend-maturity moment" (post-prototype, pre-FinOps)
Target the **moment, not the company size**: a company that has **crossed into a real, growing,
finance-visible metered Claude bill (~$2k–50k/mo) but has not built cost discipline** — no FinOps
function, no ML-platform engineers, moving fast. They "optimize nothing" because cost *just* became
visible and they have no one to fix it. This group is:
- **Genuinely underserved** — incumbents chase the sophisticated; nobody serves the *just-got-the-bill*
  crowd well.
- **Monetizable** — real bill → real savings → 20% is meaningful (unlike the $20-seat tail).
- **A perfect fit for the model** — done-for-you + pay-on-savings + "your key never leaves your box"
  as the trust-unlock.
- **Catchable at a trigger** — **bill shock under finance/CFO scrutiny** is the documented moment they
  start to care. That's the demand signal to ride.

### Why NOT "small startups / non-tech that optimize nothing" (the rejected cut)
The research disqualified the literal version of that thesis: most of them use **$20 ChatGPT/Claude
seats** (a router has nothing to route); LLM spend is **power-law concentrated** away from them; the
pain isn't acute (~95% of GenAI pilots show no P&L impact; ~5–9% reach production); providers hand
them savings **free**; and ARPU (~$12–30/mo at 20% of a tiny bill) can't cover CAC/churn.
**"Optimizes nothing because spends nothing" = no business.** Qualify on the BILL, not the logo.

## Premium expansion — the regulated / security-gated subset
The *same* beachhead, filtered to buyers whose security review blocks prompt egress. Here privacy
moves from trust-unlock to the **reason to buy**, and they're the natural buyers of the subscription
tiers. This is the high-value **expansion** of the beachhead, not a separate company.

Segments (priority order):
1. **Healthcare / health-tech** — PHI in prompts; HIPAA/BAA; can't transit a third party.
2. **Legal / legaltech** — privileged & confidential client data.
3. **Financial services / fintech** — PII, regulated data, hard vendor-risk review.
4. **Government / public-sector-adjacent** — data residency, no egress.
5. **B2B SaaS processing *their customers'* sensitive data through Claude** — must promise *their*
   customers "your data never goes to a third party."

## Unifying ICP (one sentence)
**Claude-heavy enough to have a real, growing, finance-visible bill — but not sophisticated enough to
optimize it themselves.** Sell **done-for-you + proof + pay-on-savings**, with "your prompts never
leave your box" as the trust-unlock; the regulated subset is the premium tier.

## Qualifying questions (use on every call)
- **Do you have a *metered* Claude API bill that's growing and that finance has started asking
  about?** (Yes + ~$2k+/mo = core beachhead. $20 seats / no real bill = disqualify.)
- **Who would fix the cost today — do you have FinOps or ML-platform engineers on it?** (No = our
  done-for-you value; Yes = they'll DIY or use free provider tools.)
- **Does "prompts leave our environment" block a security/procurement review?** (Yes = premium
  regulated subset; privacy becomes the reason to buy.)
- **Claude-heavy, or spread across many providers?** (Claude-heavy = fit; multi-provider = OpenRouter.)
- **Are you on the Anthropic API directly, or Bedrock?** (Bedrock buyers can flip on native ~30%
  intra-Claude routing — we must beat it on done-for-you breadth + proof, not the routing mechanic.)

## Anti-ICP (de-prioritize)
- **$20-seat / sub-$2k-mo metered spend** — nothing meaningful to route; ARPU can't cover cost.
- Teams with their own FinOps/ML-platform engineers — they DIY or use free provider tools.
- Teams wanting multi-provider breadth (OpenRouter's game).
- Bedrock-only buyers indifferent to proof/privacy — native routing is "good enough + free" for them.

## Messaging
**Lead line (core beachhead):** "Your Claude bill is growing and no one's minding it — we cut it for
you, prove the savings on your own traffic, and you pay only a share of what we save. Setup is a
one-line change; your prompts never leave your environment."

**Premium / regulated lead lines:**
- **Healthcare:** "Cut your Claude bill without your PHI ever leaving your environment."
- **Legal:** "Lower Claude costs while privileged client data stays on your systems."
- **Fintech/FS:** "Model-cost optimization your security review will approve — prompts never leave your VPC."
- **B2B SaaS:** "Save on Claude *and* keep your promise to customers: their data never touches a third party."

## The done-for-you motion (how we win the beachhead)
- **Sell the outcome, not the mechanic.** "We cut and control your Claude bill *for you*, prove it,
  you do nothing" — capture every lever (routing + caching + Batch + right-sizing), because the value
  to this buyer is *zero effort* and the native tools require code changes they won't make. (Model:
  **ProsperOps** in cloud FinOps — automated, % of savings, "zero effort, zero risk.")
- **Pricing = hybrid, not pure contingency.** Pay-on-savings is the **acquisition hook** (no card, no
  risk, "no savings → no bill"); a small **subscription floor** is the retention layer — exactly the
  built tiers (20% PAYG → $99/mo Self-optimize → Managed). Pure %-of-savings is fragile (Vendr/Tropic
  pivoted off it; willingness-to-pay collapses once savings look "easy").
- **Baseline is the #1 commercial risk** in every gain-share business — and our **control-arm
  measurement is the answer**: a transparent, defensible baseline. This is where "proof" stops being
  marketing and becomes the thing that *defends revenue*.
- **Distribution = self-serve PLG + partner/embedded only.** No paid outbound (can't pay back at this
  ARPU). Win the bill-shock moment via content/SEO + a genuinely zero-config trial + ecosystem/partner
  channels (accountants, MSPs, marketplaces). Keep support automated. (Full plan in `GTM_PLAN.md` →
  Bill-shock acquisition motion.)

## Hardening the moat (turn the wedge durable)
1. **Pay-on-savings + control-arm proof** as the brand — be the *honest, aligned* one in a category of
   inflated claims (RouterArena debunks "beats everyone"; LiteLLM's compliance was literally fake).
2. **Compliance the premium segment buys on:** SOC-2 Type II, HIPAA/BAA, pen-test, security
   questionnaire — now **table stakes** (peers have them), not a future nicety. Sequence to first
   pilots + the entity.
3. **Switching cost** via per-customer tuning embedded in the request path.
4. **On-prem / VPC brain deploy** for the most paranoid (max privacy = max moat for the premium tier).
5. **Zero collection as the moat** → "the router that never collects anything; intelligence from
   architecture + our own eval corpus, not from harvesting you." (We do NOT build cross-customer
   collection — see `FLEET_LEARNING.md` → Decision.)

## The honest go/no-go (timing bet)
This works only if enough companies are crossing from $20 seats into real metered bills *fast*, and
*before* providers fully internalize the savings. **The one validation that settles it:** find 5–10
companies at the "just got a painful Claude bill, no one to fix it" moment and see if they turn it on
and keep paying the 20%. If you can't find them, or WTP collapses once savings are visible, the thesis
is wrong → fall back to the regulated premium ICP (higher value, slower). **Fatal flaw to avoid:**
targeting "optimizes nothing because spends nothing." Qualify hard on a real, growing,
finance-visible bill.

## Bottom line
Win the **spend-maturity moment** — Claude-heavy teams with a real, growing bill and no one to fix it.
Lead with **done-for-you, proven, pay-only-for-savings**; use **"your prompts never leave your box"**
as the trust-unlock and the regulated subset as the premium expansion. Validate willingness-to-pay
before investing in anything else.
