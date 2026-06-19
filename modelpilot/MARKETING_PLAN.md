# Outlay — marketing / demand-gen plan (design-partner stage)

> **Stage reality check.** The goal right now is **3–5 design-partner pilots + a proof number**
> (attribution coverage and a measured forecast-accuracy figure on a real team), **not** broad demand-gen.
> So marketing should be **lightweight, founder-led, and value-first** — content that creates pull toward
> the free estimator/tour and lends credibility to the 1:1 outbound. Hold the expensive, scale-y channels
> (paid ads, a big Product Hunt push) until there's (a) a proof point to point at and (b) self-serve
> onboarding. Until Stripe-live + entity, every CTA is "request a pilot" / "try the estimator," never a
> hard paywalled signup.

## The hook (everything points here)
- **Free estimator / value teaser:** https://outlay-ai.com/#estimate — no signup, nothing sent.
- **Product tour:** https://outlay-ai.com/tour — the full product in 2 minutes.
- **Pilot request:** https://app.outlay-ai.com/pilot-request
- Lead with the *question*, not the product: **"Can you break your Claude bill down by team/project and
  forecast next quarter?"** Most can't — that's the wedge.

## Channels — do now (cheap, founder-led, value-first)

| Channel | Audience | Why now | Asset |
|---|---|---|---|
| **LinkedIn — founder posts** | **Finance** (CFO/VP Fin/FinOps) + eng leaders | Best fit for the *economic buyer*; "AI is a COGS line" thought-leadership warms the exact ICP and makes outbound land | `LAUNCH_POSTS.md` → LinkedIn drafts |
| **Show HN** | Eng / AI builders | One well-timed post drives a spike of the right technical audience; value-first + honest does well on HN | `LAUNCH_POSTS.md` → Show HN |
| **Reddit** — r/LLMDevs, r/ClaudeAI, r/FinOps, r/SaaS | Eng + FinOps | Warmest cold audience; comment helpfully on "my Claude bill is huge" threads, link the estimator only where relevant | `LAUNCH_POSTS.md` → Reddit + the bill-shock thread kit |
| **Bill-shock newsjacking** | Everyone | When Anthropic pricing news hits, publish a take + the estimator the same day — timely, sharable | Short LinkedIn/X post + estimator |
| **Communities** | Eng + FinOps | Anthropic Discord / Claude dev forums; **FinOps Foundation** community (finance-native, on-topic) | value-first posture |
| **X/Twitter — build-in-public** | AI-eng + founders | Low cost; "here's how we think about LLM unit economics" + pilot learnings | short threads |
| **Content/SEO seeds** | Inbound (durable) | A couple of honest explainers ("how to attribute LLM spend to work", "forecasting your AI bill", "LLM unit economics for finance") rank for a category with little good content | `/docs`, blog posts |

## Channels — do later (after a proof point + self-serve)
- **Product Hunt** — needs self-serve onboarding and a crisp demo; a PH launch into "request a pilot" wastes the spike. Revisit post-Stripe.
- **Paid ads** (LinkedIn to finance titles at Claude-using cos; Google for "LLM cost / AI FinOps") — works, but premature pre-entity and pre-proof; you'd be paying to send people to a pilot form.
- **Webinar / public teardown** — "we mapped a real team's Claude spend and forecast it" — gold, but needs a pilot that'll let us anonymize and show it.
- **Marketplace/integration listings** (GitHub Marketplace, Anthropic ecosystem lists) — once the connector UX is self-serve.

## Positioning discipline (applies to every post)
- **Sell Outlay, not routing.** Attribution + forecasting + estimate + budgets. Do **not** mention "route
  to a cheaper model / pay a cut of savings" — that's parked and off-message.
- **Two buyer angles, same product:** *finance* = COGS/margin/forecast/board; *eng* = spend-by-ticket/
  team, forecast-from-backlog, no proxy/no SDK. Pick per channel (LinkedIn→finance, HN→eng).
- **Privacy is the trust unlock:** read-only, metadata only, prompts/keys never leave your environment,
  not in the call path. Say it early.
- **Radical honesty** (this category lost trust by over-claiming): no fake accuracy %; "back-tested on
  your own data, shown with the sample size"; **not yet SOC-2/HIPAA** stated plainly.
- **Disclose you're the founder** in every post (HN/Reddit require it; it builds trust). Invite critique.

## Sequencing (a sane 2-week cadence — no big-bang)
1. **Week 1:** publish 1 LinkedIn founder post (finance angle) + start commenting helpfully in 2–3
   bill-shock threads with the estimator. Warm the ICP before the cold outbound lands.
2. **Week 1–2:** run the Tier-1 outbound (finance + eng, multi-threaded) — see `OUTLAY_OUTREACH_BATCH1*`.
3. **Week 2:** Show HN (Tue–Thu morning ET) leading with the free estimator; be present in comments for
   the first 2 hours. Cross-post value-first to r/LLMDevs / r/ClaudeAI where rules allow.
4. **Ongoing:** newsjack the next Anthropic pricing moment; turn each pilot learning into a post.
5. **Trigger to escalate:** once you have **one proof number** + self-serve onboarding → Product Hunt,
   paid pilots, and the public teardown.

## Measurement (keep it honest + light)
- Cloudflare Web Analytics (cookieless, already disclosed) — enable it (one toggle) to see which channels
  drive estimator/tour views and pilot-request starts.
- The real metric at this stage is **pilot conversations booked**, not traffic. Track in `pilot_tracker.csv`.

## Existing assets to reuse
- `LAUNCH_POSTS.md` — Outlay-reframed Show HN / Reddit / LinkedIn drafts.
- `OUTLAY_OUTREACH_BATCH1.md` / `_FINANCE.md` — 1:1 outbound (eng + finance personas).
- `/compare`, `/healthcare`, `/security`, `/docs` — landing pages to link from posts by audience.
