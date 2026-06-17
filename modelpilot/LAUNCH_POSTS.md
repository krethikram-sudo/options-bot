# ModelPilot — launch posts (Show HN / r/LocalLLaMA / r/SaaS)

Drafts to share the product + the free estimator. Voice + claims pulled from
`GTM_PLAN.md` / `PILOT_OUTREACH.md`. **Rules of the road:** value-first, disclose
you're the founder, invite critique, never headline a savings % we can't back
("typically 20–40%, measured on your traffic" — not a marketing number). Lead
people to the *free, no-signup estimator*, not a hard signup, until Stripe is live.

Links:
- Estimator (no signup, nothing sent): https://modelpilot.pages.dev/estimator.html
- Honest guide (5 real levers): https://modelpilot.pages.dev/cut-claude-costs.html
- Site: https://modelpilot.pages.dev/

---

## 1) Show HN

**Title:** Show HN: ModelPilot – cut your Claude bill, and we prove the savings on your own traffic

**Body:**

Most teams send every request to the flagship model (Opus/Fable) out of caution and quietly overpay. A lot of real traffic — classification, extraction, short Q&A, summarization, simple drafting — is handled just as well by a cheaper model. The risk is a silent quality regression on the requests you downgrade, so people don't bother.

ModelPilot is a drop-in proxy that routes each request to the cheapest model that's *good enough*, keeps your hard reasoning on the top model, and — the part I actually care about — **measures the savings against a held-out control arm on your own traffic**, so the number is real instead of a marketing %.

How it works:
- One-line setup: point your SDK's `ANTHROPIC_BASE_URL` at the client.
- A small local classifier labels each request and picks the cheapest model that clears a quality floor; genuinely hard tasks (complex code, debugging, math, agents, open-ended analysis) stay on the top model.
- In the default self-hosted mode, **your API key and prompts never leave your environment** — the routing decision is local; only category labels + token counts (never prompt text) are used. The thin client is publishable and inspectable.
- Billing is **a share of realized savings** (20%). No savings, no bill.

Honest caveats, because this space has earned skepticism:
- **Savings depend on your traffic mix.** Typically 20–40% for mixed workloads; ~$0 if you're already on the cheapest tier. The estimator under-promises on purpose.
- **You may not need us.** AWS Bedrock has intra-family routing; prompt caching and the Batch API are first-party and free; if you're technical and on Bedrock, start there. We do the routing + caching + batch + the quality measurement for you and bill only on what we prove — that's the pitch, not "we have a secret router."
- It's early access. I'd genuinely rather hear "this is wrong because X."

Free estimator, no signup, runs entirely in your browser (nothing is sent anywhere): https://modelpilot.pages.dev/estimator.html

And an honest guide to the five real levers (most of which you can do yourself, for free): https://modelpilot.pages.dev/cut-claude-costs.html

Happy to answer anything — especially the hard questions about measuring savings honestly and avoiding quality regressions.

---

## 2) r/LocalLLaMA

**Title:** I built a drop-in that cuts your Claude *API* bill and proves the savings on your own traffic — prompts never leave your box, the client is open to inspect

**Body:**

This crowd already knows the cheapest token is the one you run yourself, so let me be upfront: this is for teams who, for whatever reason, *are* on the Claude API and want to stop overpaying on it — not a pitch against local models. If self-hosting covers your workload, do that.

For everyone still paying API bills: most teams route everything to the flagship out of caution. A big share of real traffic doesn't need it, but nobody downgrades because a silent quality drop is scary. ModelPilot routes each request to the cheapest model that's *provably* good enough, keeps hard reasoning on the top model, and measures the result against a held-out control arm so the savings are real, not asserted.

What I think this sub will actually care about:
- **Privacy by architecture.** In self-hosted mode the proxy runs on your box; your **API key and prompt text never reach us**. The router classifies locally and only ever sends category labels + token counts upstream — never prompt content. The thin client is publishable, so you can read exactly what it does instead of trusting me.
- **No over-claiming.** Typically 20–40% on mixed traffic, measured per-customer; ~0 if you're already cheap. The whole category lost trust by inflating numbers — I'm trying hard not to.
- **Quality floor.** Hard categories (complex code, debugging, math, agents, analysis) never get downgraded; the routing runs against a 0%-false-downgrade discipline on a held-out set.
- **Pay only on realized savings** (no savings, no bill).

Free estimator, no signup, 100% client-side (nothing leaves the page): https://modelpilot.pages.dev/estimator.html

I'd love this community to **poke holes in the approach** — especially the "is the cheap model actually good enough" measurement and the privacy model. Tell me where it's wrong.

---

## 3) r/SaaS (founder / building-in-public)

**Title:** I spent weeks researching the "AI cost optimization" space before building — here's what I found, and the bet I'm making

**Body:**

I'm building ModelPilot (cut your Claude API bill by routing each request to the cheapest good-enough model). Before writing much code I did a deep dive on the whole routing/gateway market, and the findings reshaped the product — sharing them because they're useful whatever you're building in AI infra:

- **The technique commoditizes fast.** "Route to a cheaper model" is becoming a free feature — the open-source routers are good, and the cloud providers ship it natively (AWS Bedrock intra-family routing, prompt caching, the Batch API). Competing on "we have a better router" is a treadmill.
- **The category lost trust by over-claiming.** Everyone advertises a big savings % computed against the most expensive model. Buyers (rightly) don't believe it.
- **Nobody actually *proves* savings, and nobody bills on them.** Competitors charge markup, seats, or logs. The savings-share model that's normal in cloud FinOps (you only pay a cut of verified savings) basically doesn't exist in AI yet.

So the bet I'm making isn't a clever router — it's **honesty as the product**: we run a held-out control arm on your own traffic to *prove* the savings, keep your hard tasks on the top model, never let your prompts leave your environment, and **you pay only a share of what we actually save (no savings, no bill).** The optimization is table stakes; verified savings + skin-in-the-game pricing is the thing.

Open question I'd love this sub's take on: **does pay-on-realized-savings build trust faster than it creates friction** (customers do have to let you measure)? I went with it because it forces us to be honest, but I'm genuinely unsure if it slows the first sale.

Free estimator (no signup, nothing sent), if you're curious what your own bill could drop to: https://modelpilot.pages.dev/estimator.html

Roast the pricing model — that's the part I'm least sure about.

---

## Posting notes
- **Order/timing:** estimator + guide + these can go out *now* (no signup needed). Hold the hard "sign up & route real traffic" CTA until Stripe is live (post-entity).
- **Disclose** you're the founder in every post (HN/Reddit require it; it also builds trust).
- **HN:** post "Show HN" in the morning ET on a weekday; reply fast to every comment for the first 2 hours.
- **r/LocalLLaMA & r/SaaS:** check each sub's self-promo rules first; lead with value, don't drop-and-run. Better still: comment helpfully on existing "my Claude bill is huge" threads and link the estimator only where relevant.
- **Don't** paste a specific headline % ("we save 40%"); keep it "typically 20–40%, measured on your traffic."
- Adjacent venues to reuse these for: Hacker News, Indie Hackers, lobste.rs, dev.to, r/ClaudeAI, r/OpenAI, the FinOps Foundation community.
