# MHBE demo runbook

How to run today's Maryland Health Connection (MHBE) demo. Deck:
`docs/mhbe-demo-deck.html` (open in a browser, press **F** for full-screen, arrow keys
to advance). Background: `docs/prospect-maryland-health-connection.md` +
`docs/soc2-stateramp-sequencing.md`.

## The one rule for this audience

**Lead with the architecture, not the features.** This is a state health exchange:
their first instinct is "what data does this touch?" Win that in the first 5 minutes
(deck slide 4 — metadata-only / no PHI / no FTI) and the rest of the demo lands. If you
open with dashboards, the compliance worry runs in the background the whole time.

Likely room: **CIO (Dr. Koshanam)** = technical fit · **Compliance/Privacy (Scott
Brennan)** = the gate · **CFO (Tony Armiger)** = the budget value. Speak to all three:
architecture for Brennan, the product for Koshanam, the budget governance for Armiger.

## Pre-demo checklist (do 30 min before)

1. **Pick the environment.**
   - *Preferred:* the deployed console at `https://app.outlay-ai.com`, signed into a
     **demo-flagged account** (your email in `DEMO_ACCOUNT_EMAILS`), with **sample data
     loaded** — more credible than localhost.
   - *Backup:* run locally — `CONSOLE_SECRET=… DEMO_ACCOUNT_EMAILS="*" python -m console.server`
     → `http://127.0.0.1:8700`, sign up, load sample data. (Verified working.)
2. **Smoke it first** so you don't demo on a broken deploy:
   `python scripts/preflight.py --base https://app.outlay-ai.com` — expect liveness ✓.
   Then sign in, **load sample data**, and click through every page once.
3. **Choose the "business" persona** when prompted (cleaner exec view; or "eng" if the
   room is technical). Set a real display name so the greeting reads well.
4. **Browser hygiene:** one clean window, ~110% zoom, close other tabs/notifications,
   have the deck in one tab and the app in another. Hide any demo-mode banners if you can.
5. Have the **leave-behind** ready: the prospect dossier + the SOC 2 sequencing plan
   (or a one-pager exported from them).

## Timing (a 30-minute slot)

| Min | Segment |
|---|---|
| 0–8 | Deck slides 1–5 (moment → what it does → **architecture** → "let's look") |
| 8–22 | Live demo (the click-path below) |
| 22–26 | Deck slides 9–11 (honest posture → fit → **the ask**) |
| 26–30 | Q&A / objection handling → agree next step |

If you only get 15 minutes: slides 1→4, a 6-minute demo (Overview → Spend → Governance),
then slide 11 (the ask). Architecture + the ask are non-negotiable; cut demo depth, not those.

## The live click-path (with talking track)

Open on **Overview (`/app`)**.

1. **Overview** — "This is the home screen — headline AI spend for the window, your
   budget status, and the forecast for open work. One glance: what's it costing, are we
   on budget, what's coming." Point at the spend KPI + the forecast card.

2. **Spend (`/app/outlay`)** — "Here's where every dollar went — by team and cost center,
   by work type, by ticket, by engineer." Scroll the attribution. Then point at the
   **coverage** line: "And we're honest about it — this is the share of spend that maps
   to a specific work item, and exactly how to lift it. We never inflate the number."
   Mention the **FOCUS-aligned CSV export** ("the artifact your finance team loads").

3. **Accuracy (`/app/outlay/accuracy`)** — *the trust moment.* "The #1 question is 'can I
   trust the forecast?' We don't answer with a vendor benchmark — we back-test on your own
   closed tickets, leave-one-out, and show you the measured error on your data. With the
   sample size, never hidden." This slide is what separates you from a dashboard.

4. **Estimate (`/app/outlay/estimate`)** — "Price planned work before it's built, against
   the model learned from your delivered work — so you can budget a program up front."

5. **Budgets / Programs / Governance (`/app/outlay/budgets`, `/app/outlay/governance`)** —
   "Now governance — the part a CFO cares about. Set a budget per program. We pace it in
   real time, project the breach date, and rate it on-track / watch / off-track from
   forecast-vs-actual on completed work. And it reaches you — weekly digest, monthly close
   pack, Slack, and a webhook to your SIEM — not just here."

6. **Security (`/app/security`)** — *close the loop on compliance, in-product.* "Everything
   I just showed runs on read-only, metadata-only access. Here's our Trust Center — SSO,
   SCIM, passkeys, audit-to-SIEM, retention and erasure, our AI transparency statement —
   and we're straight about what's still on the roadmap." Don't oversell; let it read.

Return to the deck for slides 9–11.

## Objection handling (they *will* ask)

- **"Do you ever see our prompts / PHI / member data?"**
  → "No — by design. Outlay is metadata-only: token counts, ticket IDs, work types,
  dollars. Prompts, outputs, and your API keys never leave your environment. There's no
  PHI, PII, or FTI in what we receive."

- **"Are you SOC 2 / StateRAMP / FedRAMP authorized?"**
  → "SOC 2 Type II is in progress; StateRAMP is on our roadmap. I'll be straight: we're
  not there yet. What makes a pilot workable *now* is the architecture — metadata-only and
  read-only puts us outside the data scope those frameworks govern. Happy to share our SOC 2
  timeline and our NIST 800-53 control mapping today." (Have `soc2-stateramp-sequencing.md`.)

- **"MARS-E / ARC-AMPE / IRS 1075 — how do you comply?"**
  → "Those govern systems that receive, store, or transmit member data and FTI. Outlay
  receives none of that, so the integration sits outside that boundary. For the controls
  that *do* apply to any vendor — access, audit, encryption, IR — we have them, and I can
  walk your team through the mapping."

- **"Where are you hosted?"**
  → "Today on Fly.io. For a government engagement that advances, the path is a re-host to a
  FedRAMP-authorized cloud — AWS GovCloud or Azure Government — which also gives FIPS-
  validated crypto and US-region residency. We gate that on a real deal; the metadata-only
  design means we can pilot before it."

- **"What does a pilot actually require from us?"**
  → "A read-only token to a work tracker and your AI usage/billing API, scoped to your
  dev/vendor environment. No installs, no production-system access, nothing in any request
  path. Two weeks to a real coverage + forecast-accuracy number."

- **"What does it cost?"**
  → "The pilot is free. Platform pricing we set with early customers — happy to talk
  structure, but the pilot is about proving the number first."

## The ask + next step (don't leave without one)

"Would a two-week, read-only, metadata-only pilot scoped to your development and vendor AI
usage be worth doing? You'd get attribution coverage and a measured forecast number on your
own work, with nothing for the security review to clear on data flow."

Then pin a concrete next step: a follow-up with Scott Brennan on the architecture +
control mapping, and identifying the dev/vendor data sources for the pilot. Send the
dossier + SOC 2 plan as the leave-behind.

## Do / don't

- **Do** name MARS-E / ARC-AMPE / 1075 yourself — it signals you understand their world.
- **Do** keep the coverage number honest on screen; their reviewers respect candor.
- **Don't** claim SOC 2 / StateRAMP / "HIPAA compliant." Say "in progress / on roadmap /
  out of scope by design." Overclaiming to a compliance officer is fatal.
- **Don't** imply Outlay touches member data, ever — that's the whole pitch.
- **Don't** demo on an unverified deploy — run `preflight.py` + load sample data first.
