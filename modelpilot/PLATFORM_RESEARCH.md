# Platform research — tablestakes + landing UX (INTERNAL)

Competitive research to drive the build roadmap and the landing rebuild, grounded
in current (June 2026) findings on direct comparables — **Helicone, OpenRouter,
Portkey, LiteLLM, Cloudflare AI Gateway, Langfuse** — plus dev-infra SaaS
baselines (**Stripe, Clerk, Linear, PlanetScale, Vercel, Resend**). Sourced from
each vendor's docs/changelog/status pages (most block scrapers, so figures are as
reported by indexed pages — re-verify exact prices/certs before quoting publicly).

## Market context that matters
- **Helicone was acquired by Mintlify (Mar 2026) and is in maintenance mode** —
  no roadmap; Mintlify is pointing users to alternatives. A live **migration
  opportunity**: target Helicone's observability+gateway users.
- **Portkey was acquired by Palo Alto Networks (Apr 2026)** and **open-sourced its
  gateway (MIT)**. Heavier enterprise-security push.
- Everyone else (OpenRouter, LiteLLM, Cloudflare, Langfuse) is a multi-provider
  breadth play. **Nobody bills on delivered savings** — they bill per-request,
  per-log, per-seat, or a credit markup (OpenRouter ~5%, Cloudflare unified
  billing 5%). **Our "pay 20% of what we save you" is genuinely differentiated.**

## Where ModelPilot is strong (lean in)
- **Privacy / no-prompt-data + publishable thin client** is squarely on-trend:
  self-host/data-stays-in-your-infra is a recurring moat (LiteLLM, Helicone,
  Langfuse OSS, Portkey hybrid/air-gapped). We go further: prompts never leave the
  box even in the hosted product.
- **Honest, proven savings** (non-inferiority, RCT holdout, measured on your own
  traffic) vs. competitors' generic "save up to X%."
- **Pay-on-savings billing** — unique, trust-building.
- Already have: hosted console, trial, savings dashboard w/ per-category + proof,
  modes, Stripe usage billing, admin w/ per-customer tuning + audit + bulk +
  auto-approve.

---

## PART 1 — Tablestakes gaps (prioritized), with who does it well

### P0 — credibility blockers (build next)
1. **Docs site + per-framework quickstarts + thin SDKs.** Every credible platform
   leads with docs and first-class SDKs (Clerk, Linear, OpenRouter, Portkey,
   LiteLLM all ship Python/TS SDKs + copy-paste quickstarts). We have inline
   Connect text only. Build `/docs`: 5-minute quickstart (Python + TS), env
   reference, architecture/privacy page, FAQ. Highest adoption leverage.
2. **API keys with scoping + rotation + per-key budget.** The universal primitive:
   Portkey/LiteLLM "virtual keys" (budget + rate limit + model allow-list),
   OpenRouter "provisioning keys" (programmatic CRUD, per-key spend limit w/
   daily/weekly/monthly reset), Clerk's sellable API-Keys product (scopes + instant
   revocation), PlanetScale scoped service tokens, **zero-downtime rotation via
   multiple active keys** (Clerk). Replace "deployment id = credential" with named,
   revocable, scoped keys.
3. **Spend caps that BLOCK + spend alerts.** Cloudflare **Spend Limits** (Jun 2026)
   — dollar budgets that 429 when exceeded, *or* fall back to a cheaper model
   (perfect fit for us). Portkey budget limits auto-expire a key; OpenRouter per-key
   caps; LiteLLM hard+soft budgets. **Notable gap in PlanetScale & Clerk (alerts
   only, no hard cap)** → we can win here. Add per-deployment monthly cap + email
   alert at X%, with "over budget → route cheaper" as a signature move.
4. **Privacy-safe request logging / observability.** Helicone/Langfuse are
   fundamentally logs+traces; OpenRouter "Broadcast" and Cloudflare export **OTLP**
   with a **privacy mode** that excludes prompt/response content. Our differentiator:
   **metadata-only logs by default** (ts, model in/out, category, tokens, cost,
   latency, routed/applied, escalation) — "observability without shipping us your
   prompts." Offer an OTel export.
5. **Status page + uptime.** All comparables publish one (status.helicone.ai,
   status.portkey.ai, cloudflarestatus, planetscalestatus, linearstatus). Non-
   negotiable for a request-path proxy. Stand one up; publish uptime history.
6. **Security/compliance: page + DPA now, certs next.** SOC 2 Type II is the
   recurring enterprise gate (Portkey, Cloudflare, Langfuse, Clerk, Linear,
   PlanetScale all have it; several add **ISO 27001** and **HIPAA + BAA**).
   Pre-cert: publish a security page (data-flow diagram, "prompts never leave your
   box," encryption, retention, subprocessors) + a DPA + a Trust Center stub.
   Then pursue SOC 2 Type II → it unblocks deals.

### P1 — expected soon after
7. **Teams / orgs / RBAC.** Universal (Clerk/Linear/Portkey/LiteLLM orgs→members→
   roles). Today one account = one user. Add org model (owner/admin/member/billing).
8. **Fallbacks / retries / failover.** Portkey configs (fallback/load-balance/
   retry/circuit-breaker), OpenRouter auto-failover + `models[]` chains, Helicone
   5s health checks + provider rotation, Cloudflare retries (≤5, backoff), LiteLLM
   router. We fail open to upstream; add configurable retry + cheaper-model fallback
   on 429/5xx — also raises realized savings.
9. **Caching (exact → semantic).** Portkey & Helicone do **semantic** caching;
   Cloudflare/OpenRouter exact. A cache directly increases the savings we bill on.
   Add opt-in exact cache first; surface cache-hit savings.
10. **Webhooks.** Clerk (Svix-powered, HMAC-signed), Portkey, OpenRouter, PlanetScale
    (signed HMAC) all emit events. Emit: trial ending, budget threshold, weekly
    savings, escalation spike → Slack/tooling.
11. **Billing portal / invoices / transparency.** Stripe customer portal + PDF
    invoices + "how this bill was computed" line items (we already compute it).
12. **Audit log (account/security).** Portkey/Clerk/Linear/PlanetScale/Langfuse all
    have one (often Enterprise-gated; ~3-mo retention is common). We have a *proposal*
    audit trail; add account/security events (logins, key create/revoke, role change).
13. **Data export + retention controls.** Universal; export metering/savings (CSV/
    JSON) + configurable retention.

### P2 — scale / enterprise
14. **SSO (SAML/OIDC) + SCIM** — the enterprise gate above teams (WorkOS powers it
    for PlanetScale/others; Clerk/Linear/Portkey/LiteLLM all gate it to Enterprise).
15. **Per-key rate limiting**; **interactive playground / model-compare** (OpenRouter
    chat+compare, LiteLLM compare, Portkey studio) — keep prompt-data-safe.
16. **Multi-provider** (OpenAI/Gemini) — widens TAM but dilutes the honest,
    Claude-native, quality-proven positioning. Defer deliberately.

### Build order
`docs+SDKs → API keys → spend caps+alerts → metadata-only logs/OTel → status page →
security page+DPA → teams/RBAC → fallbacks → caching → webhooks → billing portal →
audit log → export/retention → SOC 2 → SSO/SCIM`.

### Pricing note
Many comparables have a **genuine free tier** (Cloudflare free core; Portkey/
Helicone/Langfuse free tiers; Clerk 50k MRU free), not just a trial. Our 7-day
trial is thinner. Consider a free metered tier (e.g., first $X of savings/month
free) to lower the top of funnel — and it costs us nothing since we only bill on
savings anyway.

---

## PART 2 — Landing page / website UX (drives the rebuild)

What the best dev-infra sites do (Stripe, Vercel, Resend, Linear, Supabase) and
the AI-gateway players, per 2026 best-practice research:
- **Lead with the product, not illustrations** — real UI, terminal/code, concrete
  numbers. *Let the product talk.*
- **Hero = code + result** (Resend's pattern): the actual call beside the rendered
  outcome. Ours: `pip install` + 2 lines of config beside a dashboard card reading
  "Saved $1,240 this month (31%)."
- **Dark, native-to-developers aesthetic** for hero/code (Betterstack/Vercel);
  crisp light content sections. Makes screenshots pop, reads premium/technical.
- **5-second clarity**: one headline (value prop), one subhead (why credible), one
  primary CTA, no jargon above the fold.
- **Proof shown honestly**: "typically 20–40%, measured on your own traffic," "0%
  false-downgrades on the golden set," "RCT holdout." Method beats hype for devs.
- **Trust signals**: logos/testimonials/security badges (use honest stand-ins —
  the method, the privacy guarantee, GitHub — until we have logos).
- **Pricing on the page, plainly.** Ours is a gift: "20% of savings — no savings,
  no bill." Centerpiece, not a footnote.
- **Repeat the same primary CTA** (Start free trial) at hero, after proof, and at
  the end; secondary = quickstart/docs for skeptics.
- **FAQ kills objections**: prompts/privacy (no), fail-open, bill computation,
  models, self-host, cancel.
- **Avoid**: vague AI hype, fake metrics, stock illustrations, walls of text,
  hidden pricing, weak CTAs, no privacy story.

### Recommended section order (implemented in the rebuild)
Nav · dark hero (headline + sub + dual CTA + terminal/result split + trust line) ·
trust strip (works with Claude API + 3 honest stat chips) · how-it-works (3 steps,
code) · proof (baseline-vs-actual, non-inferiority, RCT, on-your-own-traffic) ·
feature grid · privacy/security (data-flow) · pricing (single pay-on-savings card)
· FAQ · final dark CTA · footer.
