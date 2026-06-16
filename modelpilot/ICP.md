# Ideal Customer Profile & GTM — ModelPilot (internal)

Drafted 2026-06-15. Internal (not on the publish allowlist). Pairs with
`COMPETITIVE.md` and `GTM_PLAN.md`.

## The core logic
Our hardest-to-copy edge — **routing without ever seeing the prompt** (local
classification; prompts/outputs/keys never leave the customer's system) — only
matters to buyers for whom **prompt egress is a dealbreaker**. So we aim the moat
at the segment where privacy is the *reason to buy*, not a nice-to-have. For
everyone else we'd be fighting OpenRouter/Martian on savings + breadth (their
turf). Win the privacy-sensitive, Claude-heavy beachhead first.

## Sharp ICP (one sentence)
A **Series A–C, AI-heavy company in a regulated/data-sensitive vertical (or
selling into enterprise), spending ~$5k+/mo on Claude, whose security review
blocks sending prompts to a third party.** For them the privacy architecture is
the unlock; pay-for-savings removes the last objection.

## Target segments (in priority order)
1. **Healthcare / health-tech** — PHI in prompts; HIPAA/BAA; can't transit a third party.
2. **Legal / legaltech** — privileged & confidential client data.
3. **Financial services / fintech** — PII, regulated data, hard vendor-risk review.
4. **Government / public-sector-adjacent** — data residency, no egress.
5. **B2B SaaS processing *their customers'* sensitive data through Claude** — they must
   promise *their* customers "your data never goes to a third party."
6. **Security-conscious AI-native scale-ups, $5k–$100k+/mo Claude spend** — CISO scrutinizes
   data flow; bill big enough that 20–40% savings is real money.

## Qualifying questions (use on every call)
- **Does "prompts leave our environment" block your security/procurement review?** (Yes = strong fit.)
- **Roughly how much do you spend on the Claude API per month?** (>$5k = real money at 20–40%.)
- **Are you Claude-heavy, or spread across many providers?** (Claude-heavy = fit; multi-provider = OpenRouter.)
- **Who owns this decision — eng/platform lead, or a security/compliance gate too?**
- **Do you have the team to build & maintain your own routing + eval pipeline?** (No = our value; Yes = sell convenience/Managed.)

## Anti-ICP (de-prioritize)
- Hobbyists / <$2k-mo spend (savings too small under % billing; low revenue). **Exception:** small
  *future-ICP* startups belong in the self-serve PLG funnel, not the trash — see "PLG / long-tail" below.
- Teams wanting multi-provider breadth (OpenRouter's game).
- Teams indifferent to data egress (privacy card face-down; weaker position).

## Messaging per vertical (lead line)
- **Healthcare:** "Cut your Claude bill without your PHI ever leaving your environment."
- **Legal:** "Lower Claude costs while privileged client data stays on your systems."
- **Fintech/FS:** "Model-cost optimization your security review will actually approve — prompts never leave your VPC."
- **B2B SaaS:** "Save on Claude *and* keep your promise to customers: their data never touches a third party."
- **AI scale-up:** "20–40% off your Claude bill, proven on your own traffic, with zero prompt egress."

## Pricing fit
Regulated/enterprise buyers value done-for-you + predictable line items → they're the
natural buyers of **Self-optimize ($99/mo + 15%)** and **Managed (+15%, ~$499/mo TBD)**.
Pay-only-for-savings + no prompt egress is the combination that gets through procurement.

## Hardening the moat (turn the wedge durable)
1. **Compliance proof** the privacy segment buys on: SOC-2 Type II, HIPAA/BAA readiness,
   pen-test summary, security questionnaire. (Today: not yet certified — gating for #1/#2/#3.)
2. **On-prem / VPC brain deploy** for the most paranoid enterprises (max privacy = max moat).
3. **Switching cost** via per-customer tuning embedded in their request path.
4. **Zero collection as the moat** → "the router that never collects anything; intelligence from
   architecture + our own eval corpus, not from harvesting you." (We explicitly do NOT build
   cross-customer data collection — it would put an asterisk on the privacy promise and make us a
   data processor with breach/re-id/consent liability. Cold-start comes from an expanded
   *self-owned* eval corpus instead. See `FLEET_LEARNING.md` → Decision.)

## PLG / long-tail: land small, grow into the ICP
Small startups are a **funnel, not a target segment.** The premise "they can't afford competitors"
is mostly false — routing has cheap/free floors (OpenRouter BYOK ~1M free req/mo then 5%; LiteLLM
free OSS; Cloudflare AI Gateway free tier). We don't win the small/privacy-indifferent dev on price,
and our moat is face-down for them. So don't chase them as a discount segment.

**But two real advantages let us serve the long tail profitably where sales-led rivals won't:**
1. **Risk-free, aligned billing** — no card, free trial, then *only a cut of realized savings* (no
   savings, no bill). A stronger *land* hook than any free tier: we pay for ourselves or you owe $0.
2. **Low marginal cost to serve** — BYOK (their key/compute), the brain is a cheap decision service,
   fail-open. A $500/mo account costs a sales-led competitor too much to bother with; it costs us ~$0
   if acquisition + support stay automated.

**The motion:** use $0-to-start, pay-on-savings as a **self-serve, product-led top-of-funnel to land
startups *on the path* to the ICP** — AI-native, already handling sensitive data, growing Claude spend.
Land tiny and risk-free now; when they hit their first enterprise security review and the bill grows,
**the privacy moat activates and they convert to the subscription tiers.** Land small → grow into the ICP.

**Guardrails (so the tail stays net-positive):**
- **100% self-serve under ~$5k/mo** — no human sales/support in the loop; the free trial + dashboard do the work.
- **Let the pre-sale estimator qualify** — walk away from zero-headroom accounts; don't burn effort.
- **Don't acquire the generic privacy-indifferent small dev** — no edge vs OpenRouter's free tier there.
- Watch that automated support cost (not infra) stays near zero; % billing on tiny spend only works hands-off.

## Bottom line
Win the regulated + security-conscious, Claude-heavy beachhead. Lead every conversation with
**"route without ever seeing your prompts."** Use the beachhead to earn certs, embeddedness, and
calibration data — that's what converts the wedge into a durable moat. Don't chase the general
dev market with the privacy card face-down.
