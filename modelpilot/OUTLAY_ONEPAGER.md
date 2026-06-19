# Outlay — see your AI spend mapped to work, forecast it, hold it to budget

*Outlay maps your Claude/AI spend to the tickets, epics, teams, and engineers that drove it, forecasts
the quarter from your open backlog, prices planned work before you build it, and holds it to budget — all
from **read-only** connections to the tracker and AI-usage data you already have. **Not a proxy, not a
gateway, no SDK, no app changes.** Prompts, outputs, and your API key **never reach us** — metadata only.*

---

## The offer (zero risk)
- **Free design-partner pilot**, ~2 weeks, no card.
- **~30-minute setup** — two read-only connections. Nothing installed in your app.
- **Read-only & reversible** — remove Outlay anytime; nothing about your traffic changes (it was never
  in the path).

## How the pilot works
1. **Request a pilot:** https://app.outlay-ai.com/pilot-request — we reply from hello@outlay-ai.com.
2. **Connect two read-only sources** on the **Connect** tab:
   - A **tracker** — GitHub Issues, Jira, or Linear (ticket/epic/team metadata).
   - **AI usage** — Anthropic Admin API, Cursor, or Claude Code transcripts (model, token counts,
     timestamps — never prompt content).
3. **Sync** on demand or on a daily/weekly schedule. Tokens are encrypted at rest.

## What you get
- **Spend mapped to ticket, epic, team & engineer** — your AI bill on the roadmap, reconciled to the invoice.
- **Forecast by scope** — the quarter projected bottom-up from open work, as a range.
- **Estimate planned work** — price an epic from its requirements/design docs *before* you build it, with
  a confidence band.
- **Budgets & pace alerts** — by overall / team / work-type / project, *before* overspend, not at month-end.
- **Measured accuracy** — every forecast back-tested leave-one-out on your own closed tickets, shown with
  the sample size.
- **CSV export** — ticket, work-type, and per-engineer spend, for finance.

## Privacy & security (built in)
- **Not in the path of your AI calls** — your app calls Anthropic directly with your key, as today.
- **Metadata only** — token counts, ticket IDs, timestamps, per-request cost. **Never prompts, outputs,
  or your API key.**
- **Read-only tokens**, encrypted at rest.
- **The honest part:** the "prompts never leave your environment" guarantee is a property of the
  architecture. We are **not yet SOC-2 or HIPAA certified** and won't claim what we don't hold. Need a BAA
  or our roadmap? Ask.

## Pricing
- **Pilots run free.** Platform pricing for ongoing budgeting & governance is set *with* design partners —
  influence over the roadmap and pricing is part of the deal.

## Quick FAQ
- **How much effort?** ~30 minutes — two read-only tokens. No rewrite, no SDK, no proxy.
- **Will it touch our prompts/data?** No — metadata only; we're not in the call path.
- **Lock-in?** None — revoke the read-only tokens and it's gone.
- **What if our spend is multi-model?** Attribution works on the Claude slice; we quantify the share first.

**See it (2 min, nothing sent):** https://outlay-ai.com/#estimate · **Full tour:** https://outlay-ai.com/tour
**Start a pilot:** https://app.outlay-ai.com/pilot-request · **Questions:** hello@outlay-ai.com
