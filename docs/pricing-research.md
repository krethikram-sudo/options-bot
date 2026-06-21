# How to price Outlay — a B2B SaaS pricing primer + recommendation

*Researched June 2026. Written for a founder new to B2B SaaS pricing. Outlay =
metadata-only AI/LLM spend attribution + forecasting + budget governance, with an
optional opt-in enforcement gateway (route-down / hard caps). Today's stated
model: "20% of realized savings."*

---

## TL;DR recommendation

**Don't price purely on "% of savings."** It's a great *story* and a great *add-on*,
but as your only model it underprices the always-on value you deliver (attribution,
forecasting, budgets, chargeback, governance) and pays you **$0 when a customer
doesn't turn on enforcement** — which most won't on day one.

**Recommended model: a hybrid.**
1. **Primary — a tiered platform fee based on "AI spend under management."** This is
   the FinOps-industry norm and bills for the visibility/governance value whether or
   not the customer enforces anything. Anchor around **2–4% of the AI spend Outlay
   watches**, sold as **predictable flat bands** (not a live percentage), so finance
   buyers and government can budget it.
2. **Add-on — keep "20% of realized savings"** as an *opt-in* line tied to the
   enforcement gateway, where savings are real and you caused them. This is your
   "we only win when you win" hook to disarm skeptical buyers and land pilots.
3. **Avoid per-seat.** Your buyers are a handful of finance/eng leaders plus
   read-only viewers; per-seat caps your value and discourages the team-wide
   visibility that makes you sticky.

---

## The five models, and which fit Outlay

| Model | How it works | Market reality | Fit for Outlay |
|---|---|---|---|
| **Per-seat** | $/user/month | Still #1 (57% of SaaS, down from 64%); median **$45/user/mo** | ❌ Poor — few decision-makers, value isn't per-head, punishes adding viewers |
| **Usage / spend-based** | $ scales with a usage metric (here: AI $ under management) | Fastest-growing (43% of models, +8pts); UBP firms grow **10–15pts faster**, NRR >120% | ✅ Strong — your value scales with their AI spend |
| **Value / outcome (% of savings)** | % of measured savings | 15–35% of delivered savings (nOps, Cast AI 15–20%, ProsperOps) | ⚠️ Great *aligned add-on*, risky as the *only* model (see below) |
| **Flat tiers** | Fixed $/month bands | Common entry model ($500–$5k+/mo) | ✅ Use as the *packaging* of the spend-based fee (predictability) |
| **Hybrid (platform fee + usage/outcome)** | Base + variable | **61% of SaaS by 2025**; the default for scaling B2B | ✅✅ **Recommended** |

Sources: [Monetizely 2025 benchmark](https://www.getmonetizely.com/articles/saas-pricing-benchmark-study-2025-key-insights-from-100-companies-analyzed), [softwarepricing.com](https://softwarepricing.com/blog/saas-pricing-models/), [Flexera](https://www.flexera.com/blog/saas-management/from-seats-to-consumption-why-saas-pricing-has-entered-its-hybrid-era/).

## What comparable tools actually charge (your benchmarks)

**FinOps visibility / cost-management (closest analogues — they sell *seeing & governing* spend, like Outlay):**
- **CloudZero** — usage-based, **~$19/mo per $1,000 of cloud spend** (≈ **1.9% of spend**). [CloudZero](https://www.cloudzero.com/blog/finops-tools/)
- **Finout** — **$6,000/yr to manage $500k AWS spend (~1.2%)**, **$12,000/yr for $2M (~0.6%)** — note the **% drops as spend grows** (tiered). [CloudZero–Finout](https://www.cloudzero.com/blog/finout-pricing/)
- **Vantage** — a **% of managed cloud spend**. [Holori](https://holori.com/20-best-finops-and-cloud-cost-management-tools-in-2025/)
- Rule of thumb across the category: **fixed/visibility tools ≈ 1–3% of cloud spend/yr.**

**Cloud cost *optimizers* (they actually cut the bill — savings-share):**
- **Cast AI** — **15–20% of savings delivered.** [cybernews](https://cybernews.com/ai-tools/cast-ai-review/)
- **nOps** — gain-share, **% of realized savings, $0 if nothing saved**; visibility is a separate fixed fee on spend. [nOps](https://www.nops.io/saas/)
- **ProsperOps** — tiered **Savings Share** (≈25% illustrative); **caveat: early-termination clawback of unrealized share up to 12 months** — a real friction. [ProsperOps billing](https://help.prosperops.com/how-does-prosperops-bill)
- Category rule of thumb: **savings-share ≈ 15–35% of realized savings.**

**AI / LLM observability (adjacent, shows the AI-native entry points):**
- **Helicone** — **~$25–$79/mo** paid tiers. [particula](https://particula.tech/blog/helicone-vs-langfuse-vs-langsmith-llm-observability)
- **Langfuse** — **$29/mo + ~$20/seat + $1/GB** ingested (hybrid). [particula](https://particula.tech/blog/helicone-vs-langfuse-vs-langsmith-llm-observability)
- **Datadog LLM** — per-span **+ ~$120/day premium**; can add 40–200% to a Datadog bill (the "expensive incumbent" anchor). [Maxim](https://www.getmaxim.ai/articles/best-llm-cost-tracking-tools-in-2026/)

## Why not pure "% of savings" (even though it sounds perfect)

The story is fantastic — "we're free, we only take a cut of what we save you" — and you should keep it as an **opt-in add-on**. But as your *sole* model it has four problems for Outlay specifically:
1. **No enforcement → no revenue.** Your core console is *visibility + forecasting + budgets*, which is valuable but doesn't "save" a measurable dollar unless the customer also runs the route-down gateway. Bill only on savings and you give away the part most customers actually use first.
2. **Attribution disputes.** "Realized savings" is contestable — was it your route-down, their own decision, or just correct cache-aware accounting (your 7.5× insight is *accuracy*, not *savings you created*)? Disputes erode trust and slow renewals.
3. **Revenue is lumpy and hard to forecast** (yours *and* theirs), which hurts you when you raise money.
4. **Government/enterprise procurement often can't buy it.** Public-sector contracts favor **firm-fixed-price**; a variable %-of-savings line is hard to put on a PO (directly relevant to your Maryland thread). Offer a fixed annual there.

Savings-share is best as the **aligned hook that lands the deal**, not the whole P&L.

## A concrete starting structure for Outlay

Treat **"AI spend under management"** (the monthly AI/LLM $ Outlay attributes) as your value metric, and sell **flat bands** so the bill is predictable:

| Tier | AI spend watched / mo | Suggested platform fee | Notes |
|---|---|---|---|
| **Pilot** | any, 14 days | **Free** | Your read-only/metadata posture makes this near-zero-risk to grant; it's your trial |
| **Starter** | up to ~$25k | **$500–$900/mo** | Lands a team; ~2–3.5% effective |
| **Growth** | up to ~$100k | **$1,500–$2,500/mo** | % tapers as spend grows (like Finout) |
| **Scale** | up to ~$500k | **$4,000–$7,000/mo** | Annual, firm-fixed-price option for gov/enterprise |
| **Enterprise** | $500k+ | Custom | SSO/SCIM, SLAs, VPAT, on-prem-ish data terms |
| **Savings add-on** | — | **20% of *enforced* savings** | Opt-in, only when the gateway is on |

Numbers are starting anchors, not gospel — the point is the **shape**: predictable base that scales with their AI spend, plus an aligned savings upside. Start at the **higher** end; discounting down is easy, raising is hard.

## Practical advice for a first-timer

- **Price on value, not cost.** If Outlay gives finance control over a runaway six-figure line item, $1–2k/mo is trivial for them — don't anchor to your hosting bill.
- **Charge from day one (a pilot ≠ permanently free).** A paid pilot (even small) qualifies buyers far better than free.
- **Annual contracts** improve cash + retention; offer ~2 months free for annual.
- **Land-and-expand:** start one team, expand as more of their AI spend flows through you — usage-based naturally grows the account (that >120% NRR pattern).
- **Don't over-discount the savings-share to win logos** — it's your cleanest aligned-incentive story; keep it crisp (a round 20%).
- **Talk to 5–10 design-partner buyers** and literally ask "what would you expect to pay, and what would feel like a steal?" — your real pricing comes from them, this doc just frames the conversation.

### Sources
- [SaaS Pricing Benchmark 2025 — Monetizely](https://www.getmonetizely.com/articles/saas-pricing-benchmark-study-2025-key-insights-from-100-companies-analyzed)
- [SaaS pricing models — softwarepricing.com](https://softwarepricing.com/blog/saas-pricing-models/)
- [Hybrid pricing era — Flexera](https://www.flexera.com/blog/saas-management/from-seats-to-consumption-why-saas-pricing-has-entered-its-hybrid-era/)
- [FinOps tools guide — CloudZero](https://www.cloudzero.com/blog/finops-tools/)
- [Finout pricing breakdown — CloudZero](https://www.cloudzero.com/blog/finout-pricing/)
- [Cloud cost optimization for SaaS — nOps](https://www.nops.io/saas/)
- [Cast AI review/pricing — cybernews](https://cybernews.com/ai-tools/cast-ai-review/)
- [How ProsperOps bills — ProsperOps](https://help.prosperops.com/how-does-prosperops-bill)
- [LLM cost tracking tools — Maxim](https://www.getmaxim.ai/articles/best-llm-cost-tracking-tools-in-2026/)
- [Helicone vs Langfuse vs LangSmith — particula](https://particula.tech/blog/helicone-vs-langfuse-vs-langsmith-llm-observability)
