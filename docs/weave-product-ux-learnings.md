# Product & UX learnings from Weave (workweave.dev) — applied to Outlay

Weave (WorkWeave Inc, YC W25, $4.2M seed) is an adjacent company on the **same data substrate** as
Outlay — it joins engineering work (GitHub PRs + AI tools + trackers) to a metric — but measures the
**opposite axis**: engineering *output/productivity* (the "Weave Hour"), where Outlay measures *cost*.
They are two halves of AI ROI: Weave is the numerator (work delivered), Outlay the denominator
(what it cost). This doc captures what's worth borrowing for Outlay's product and UX, and how each maps
to a concrete build. (Source basis: their marketing, YC/Product Hunt, and the open-source Cursor MCP
plugin — their app itself is gated.)

> **Strategic frame:** Weave owns "output," Outlay owns "cost." The contested high ground is the
> **ratio — cost per unit of delivered work**. Outlay is uniquely positioned to own it.

## The seven learnings → Outlay moves

| # | What Weave does well | Outlay move | Status |
|---|---|---|---|
| 1 | **One trust-anchored hero metric** — the "Weave Hour" ("how long would an expert take?"), positioned against "useless story points," with a published **94% correlation** validation | A single hero unit: **cost per shipped unit of work** ($/ticket, $/feature) — the one number the whole product ladders to | **building** (`cost_per_unit`) |
| 2 | **Validation is a feature** — they lead with the correlation number, not hide the metric is model-estimated | Surface the **fidelity tier** (per-dollar join confidence) + **forecast back-test error** as a credibility headline, not a footnote | planned |
| 3 | **Fluid drill-down** — CTO dashboard → team → individual in a few clicks, same metric at every altitude | Make **total → team → ticket → PR** the central interaction (same $ at each level) | planned |
| 4 | **Metrics where work happens** — an **MCP server / Cursor plugin** exposes metrics (incl. tool cost) via natural-language chat *in the editor* | Ship an **Outlay MCP server** over the engine: cost-per-PR/ticket, forecast, commitment, opportunities — usable from Claude/Cursor. Developer distribution. | **building** (`mcp_server`) |
| 5 | **NL analytics agent ("Wooly")** — ask questions, get grounded, cited answers | "**Ask your spend**" — comes largely for free once the MCP server is exposed to any MCP client (Claude/Cursor); the model queries Outlay's tools | **building** (via #4) |
| 6 | **Opinionated comparison-content engine** — "vs Swarmia / DORA / Pluralsight," "build vs buy," "essential dashboards"; owns comparison SEO | Public **comparison pages** from the battlecards (vs account-level invoices / vs cost dashboards / vs DIY) | planned |
| 7 | **Obsessive time-to-value** — "up and running in <1h, insights in 24–48h" | Instrument onboarding for **first attributed dollar in <24h**; show a live partial result while the sync runs | planned |

## What NOT to copy
Weave's core is **measuring individual engineers** — inherently sensitive (surveillance/ranking), which
is why they ship FAQ-for-managers content defending it. Outlay's posture is the opposite and
better-defended: **dollars and budgets, not people; read-only; metadata-only; team/cost-center
altitude.** Lean into that contrast — but keep *per-engineer spend* views scoped to the engineer's own
data; aggregate to team/program for leadership so cost attribution never reads as performance ranking.

## Build order (highest leverage first)
1. **MCP server** (#4, enables #5) — cheapest path to developer distribution, exactly how Weave spread
   (25% of new YC companies). Wraps the existing CLI/engine; stdlib-only, stdio JSON-RPC.
2. **Hero metric** (#1) — gives the product a spine: cost per unit of delivered work.
3. **Validation surfacing** (#2) — turns our honesty primitives (fidelity, back-test) into a visible edge.
4. **Comparison pages** (#6) — the battlecards are 80% of the copy already.
5. **Drill-down** (#3) and **time-to-value** (#7) — larger console UX work, sequenced after.
