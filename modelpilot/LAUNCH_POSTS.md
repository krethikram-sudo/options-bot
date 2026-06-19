# Outlay — launch / marketing posts (Show HN · Reddit · LinkedIn)

Drafts to share Outlay + the free estimator. **Rules of the road:** value-first; disclose you're the
founder; invite critique; **sell Outlay (attribution + forecasting), never routing** ("route to a cheaper
model / pay a cut of savings" is parked — off-message); no fake accuracy %; lead people to the *free,
no-signup estimator/tour*, not a hard signup. Strategy/sequencing: `MARKETING_PLAN.md`.

Links:
- Estimator (no signup, nothing sent): https://outlay-ai.com/#estimate
- Product tour (2 min): https://outlay-ai.com/tour
- Site: https://outlay-ai.com/ · Security: https://outlay-ai.com/security · Docs: https://outlay-ai.com/docs
- Request a pilot: https://app.outlay-ai.com/pilot-request

---

## 1) Show HN  (audience: eng / AI builders)

**Title:** Show HN: Outlay – map your Claude spend to the work that drove it, and forecast it

**Body:**

Most teams' AI bill is one big number on the Anthropic invoice. When finance asks "which teams and
projects is this going to, and what will it be next quarter?", there's no clean answer — so spend grows
unmanaged until someone panics and says "cut it."

Outlay answers the prior question. It connects **read-only** to two things you already have — your tracker
(GitHub Issues / Jira / Linear) and your AI-usage data (Anthropic Admin API, Cursor, or Claude Code
transcripts) — and:

- maps every dollar to the **ticket / epic / team / engineer** that drove it, reconciled to the invoice;
- **forecasts the quarter** bottom-up from your open backlog, as a range;
- **estimates planned work** — prices an epic from its requirements/design docs before you build it;
- holds it to **budgets** with pace alerts *before* overspend.

The part I actually care about: it's **not a proxy or gateway**. Your app keeps calling Anthropic directly
with your key; Outlay is never in the request path. It reads **metadata only** — model, token counts,
timestamps, ticket IDs — **never prompt text or outputs**, and never your API key. Setup is ~30 minutes
(two read-only tokens), no SDK, no code change, and it's reversible (revoke the tokens and it's gone).

Honest caveats, because this space has earned skepticism:
- **Forecasts are back-tested leave-one-out on your own closed tickets** and shown with the sample size —
  no marketing accuracy %. Under ~12 closed tickets it says "directional," not a number.
- **Attribution coverage varies** with how your work is tracked; unattributable spend is reconciled to the
  invoice, never dropped.
- **We're not yet SOC-2 / HIPAA certified** — the "prompts never leave your environment" guarantee is a
  property of the architecture (we're not in the path), and I'll say exactly where we are if you ask.
- It's early — onboarding is a free, read-only, ~2-week design-partner pilot. I'd genuinely rather hear
  "this is wrong because X."

See it in 2 minutes (no signup, nothing sent): https://outlay-ai.com/#estimate · full tour:
https://outlay-ai.com/tour

Happy to answer anything — especially on attributing agentic spend honestly and the forecast back-testing.

---

## 2) r/LLMDevs · r/ClaudeAI  (audience: eng / AI)

**Title:** I built a read-only way to see your Claude spend mapped to tickets and forecast it — no proxy,
prompts never leave your box

**Body:**

If your Claude bill is climbing and you can't say *which* projects, teams, or tickets are driving it,
you're not alone — the invoice is one number, and most "AI cost" tools want to sit in your request path to
fix that. Outlay doesn't.

It connects **read-only** to your tracker + your provider's usage data and maps spend to the actual work
(ticket/epic/team/engineer), forecasts the quarter from your open backlog, and prices planned epics before
you build them. What this sub will care about:

- **Not a proxy.** Your calls go to Anthropic directly with your key; we're never in the path. **Metadata
  only** — token counts, model, ticket IDs — **never prompt content or outputs**. Remove it anytime;
  nothing about your traffic changes.
- **No over-claiming.** Forecasts are back-tested on your own closed tickets and shown with n; cache-aware
  costs so agentic workloads aren't overstated 5–10×.
- **Read-only + ~30-min setup.** Two tokens, no SDK, no code change.

Free 2-min estimator (client-side, nothing sent): https://outlay-ai.com/#estimate · tour:
https://outlay-ai.com/tour

I'd love this community to **poke holes** — especially the agentic-spend → ticket attribution and the
forecast back-testing. Tell me where it's wrong. (Founder here, onboarding free design-partner pilots.)

---

## 3) r/FinOps · r/SaaS  (audience: finance / FinOps / founders)

**Title:** AI is quietly becoming a COGS line you can't forecast — here's how I think about LLM unit
economics

**Body:**

I'm building Outlay (map your AI spend to the work that drove it, then forecast it). Before that, the
finance problem I kept hearing: **LLM spend is now a real, growing cost line that no one can attribute or
forecast.** It hits gross margin, it's lumpy, and "what will it be next quarter" gets a shrug.

A few things I've come to believe, useful whatever you're building:

- **You can't do unit economics on a single invoice number.** If you can't split AI spend by product/team/
  customer, you can't reason about margin or defend pricing.
- **Forecasts have to be defensible.** A number you take to the board should be back-tested on your *own*
  history and carry its sample size — not a vendor's marketing %.
- **The tooling shouldn't require data egress.** Mapping and forecasting spend only needs *metadata*
  (token counts, ticket IDs) — not your prompts. Anything that proxies your traffic is solving the wrong
  problem and adding risk.

So Outlay reads your tracker + usage data **read-only, metadata only**, maps spend to work, and forecasts
it by scope — gross-margin-by-product and a board-grade forecast, ~30 min of eng time to connect, nothing
in the request path.

Open question I'd love this sub's take on: **is "AI COGS / LLM unit economics" landing as a real finance
problem yet at your company, or still buried in an eng budget?** Genuinely trying to calibrate.

Free estimator if you're curious what your own bill breaks down to: https://outlay-ai.com/#estimate

---

## 4) LinkedIn — founder posts (audience: FINANCE first; the economic buyer)

**Post A — the COGS framing (lead with this):**
> Your AI bill is becoming a COGS line — and most finance teams can't forecast it.
>
> "How much will Claude cost us next quarter?" is now a real budgeting question, and the honest answer at
> most companies is a shrug, because the Anthropic invoice is one number with no attribution to products,
> teams, or customers.
>
> A few things I've learned building in this space:
> • You can't do unit economics on a single invoice line. Without attribution there's no margin-by-product.
> • A forecast you take to the board has to be back-tested on your *own* data and carry its sample size.
> • You don't need to proxy anyone's AI traffic to do this — it's a *metadata* problem (token counts,
>   ticket IDs), not a prompt-content problem.
>
> That's what we're building at Outlay: read-only, metadata-only spend attribution + forecasting. Maps your
> AI spend to the work that drove it and forecasts it by scope — ~30 min to connect, nothing in your
> request path.
>
> Curious how others are handling this — is AI COGS a tracked line for you yet, or still buried in an eng
> budget? 2-min look: outlay-ai.com  #FinOps #AI #LLM #gtm

**Post B — the bill-shock newsjack (publish the day Anthropic pricing news hits):**
> {Headline of the day, e.g. "Uber burned its 2026 AI budget by April."} The pattern is always the same:
> AI spend grows faster than anyone's watching, then a panic to "cut it" — before anyone can even say where
> it's going.
>
> Cutting a bill you can't break down is guessing. Step one is visibility: map the spend to the teams and
> projects driving it, and forecast it before the invoice. (Read-only, metadata only — you don't have to
> route your traffic through anyone to get the answer.)
>
> If your AI line just got more expensive, the 2-min version of what that breakdown looks like:
> outlay-ai.com/#estimate

**Post C — build-in-public / proof (once a pilot allows an anonymized result):**
> We mapped a real team's Claude spend to their roadmap. {1–2 honest, anonymized findings — e.g. "X% of
> spend was on one work-type nobody had flagged"; "the quarter forecast came within Y% back-tested."} No
> prompts ever left their environment — metadata only. This is the whole pitch: see it, forecast it, then
> decide. outlay-ai.com

---

## Posting notes
- **Timing:** estimator + tour + these can go out **now** (no signup needed). Keep the CTA at "request a
  pilot" / "try the estimator" until Stripe-live (post-entity).
- **Disclose** you're the founder every time (HN/Reddit require it; builds trust).
- **HN:** Show HN Tue–Thu morning ET; reply fast for the first 2 hours.
- **Reddit:** check each sub's self-promo rules; better to comment helpfully on existing "my Claude bill is
  huge" threads and link the estimator only where relevant than to drop-and-run.
- **LinkedIn:** finance angle (Post A) is the highest-fit for the economic buyer; it also warms the exact
  people you're cold-emailing — post it *before/while* you run the Tier-1 outbound.
- **Never** headline a savings or accuracy number we can't back; "back-tested on your own data, shown with
  the sample size."
- Adjacent venues to reuse: Hacker News, Indie Hackers, lobste.rs, dev.to, r/ClaudeAI, the **FinOps
  Foundation** community.
