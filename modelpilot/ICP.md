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
- Hobbyists / <$2k-mo spend (savings too small under % billing; low revenue).
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
4. **Privacy-safe cross-customer calibration** → routing quality others can't match.

## Bottom line
Win the regulated + security-conscious, Claude-heavy beachhead. Lead every conversation with
**"route without ever seeing your prompts."** Use the beachhead to earn certs, embeddedness, and
calibration data — that's what converts the wedge into a durable moat. Don't chase the general
dev market with the privacy card face-down.
