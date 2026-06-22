# Finance UX — simplify to consolidated views + personalization

*Design proposal (research-backed) for making the finance experience easier to follow:
start consolidated, let users deep-dive or change the view, and let them customize it to
their preference. This is a proposal to react to — no code changes yet.*

---

## 1. Where the finance UX is today

After the last few rounds, the finance persona has four Analyze destinations —
**Summary · Spend · Budgets · Programs** — plus the Overview home. It's content-rich and
the data is good, but the *navigation* has grown:

- **Two near-duplicate landing pages.** The Overview and the new Summary both open with
  the attention panel + KPIs + roll-ups. A finance user has to learn which is "home."
- **Long, stacked pages.** Overview alone stacks: trial banner → attention panel → 4 KPIs
  → trust callout → unit economics → trend → movers → forecast → explore. It's a scroll.
- **One-size layout.** Every finance user sees the same cards in the same order. A CFO who
  only cares about "are we on budget?" and a FinOps analyst who lives in per-team
  chargeback get the identical page.
- **No saved context.** You can't say "always land me on last quarter, grouped by team"
  or pin the three numbers you check daily.

The goal: **one opinionated, consolidated home → drill or switch the lens → personalize.**

---

## 2. What "elegant" looks like — patterns from leading platforms

Distilled from FinOps tools (CloudZero, Cloudability), observability (Datadog, Grafana),
CFO spend tools (Ramp, Brex), and BI (Tableau, Amplitude):

1. **Ship opinionated defaults, then allow personalization.** The consensus anti-pattern is
   a blank/configurable canvas; the winning pattern is a *meaningful out-of-the-box view*
   that works before anyone configures anything — with personalization layered on top.
   [[B2B SaaS dashboards]](https://upsolve.ai/blog/personalized-dashboards-for-saas)
   [[opinionated defaults]](https://www.orbix.studio/blogs/saas-dashboard-design-b2b-optimization-guide)

2. **Overview-to-detail, in an F-pattern.** Primary KPIs on top (seen first), a trend band
   in the middle (where things are heading), granular tables at the bottom (for those who
   dig). Increase granularity as you scroll, never cram detail into a summary card.
   [[layout patterns]](https://www.datawirefra.me/blog/dashboard-layout-patterns)
   [[KPI scorecards]](https://www.datacamp.com/tutorial/dashboard-design-tutorial)

3. **Progressive disclosure + hierarchical drill-down.** Show the headline; let users click
   a number to see what drives it (spend → team → ticket). "Context links" wire every
   summary metric to its detail view rather than showing everything at once.
   [[Datadog context links]](https://docs.datadoghq.com/dashboards/guide/context-links/)

4. **Role-based default + per-user override (hybrid).** Different roles get purpose-built
   default views (exec vs analyst), and each user can still personalize. This combination —
   not permission toggles on one layout — is the repeated recommendation.
   [[role-based vs personalized]](https://www.plgos.com/blogs/7-smart-tools-to-automate-role-based-dashboards-in-saas)

5. **Lenses + saved views.** Datadog's *template variables* let one dashboard be re-sliced
   (by team, period, scope) from a dropdown; selections can be saved as named **views**, and
   **tabs** group sections so viewers jump straight to what they need. Switch context without
   rebuilding the page. [[template variables / saved views]](https://docs.datadoghq.com/dashboards/template_variables/)

6. **Pin / reorder / hide, with a persistent layout.** Drag-and-drop widgets, pin favorite
   KPIs, resize, and have the layout persist across sessions — the Datadog/Grafana model.
   [[Datadog dashboards]](https://www.datadoghq.com/product/platform/dashboards/)

---

## 3. Proposed direction for Outlay finance

Four moves, in priority order:

### (a) Collapse to ONE consolidated **Finance Home**
Merge Overview + Summary into a single opinionated home laid out F-pattern:

```
┌─ Needs your attention ──────────────────────────────────────────────┐
│  • Program "Q2 Platform" is over — $78.6k vs $60k cap · breach Jun  ▸ │   ← act first
└──────────────────────────────────────────────────────────────────────┘
┌─ Spend ──┐ ┌─ Projected ─┐ ┌─ Over budget ─┐ ┌─ Allocated ─┐            ← KPI scorecard
│ $78.6k   │ │ $100.4k     │ │ 1 program     │ │ 9 teams     │             (top row)
└──────────┘ └─────────────┘ └───────────────┘ └─────────────┘
┌─ Spend trend (this quarter) ───────────────────────────────────────┐    ← trend band
│  ╱╲___╱                                          ↑ 12% vs last sync │     (middle)
└─────────────────────────────────────────────────────────────────────┘
┌─ By team / cost-center ──┐  ┌─ Programs & budgets ──┐  ┌─ Forecast ──┐   ← consolidated
│ growth   $11.5k   ▸      │  │ Q2 Platform  over  ▸  │  │ $21.9k open │     summary cards,
│ payments $10.8k   ▸      │  │ Growth       ok    ▸  │  │ band ▸      │     each "drill in ▸"
│ … see all ▸              │  │ … manage ▸            │  └─────────────┘     (bottom)
└──────────────────────────┘  └───────────────────────┘
```

- The attention panel stays the top, action-first band.
- Budgets and Programs become **summary cards on Home** with "drill in ▸"; the full
  Budgets/Programs pages remain as the deep views (no capability lost, less nav).
- Result: finance nav shrinks from **Summary · Spend · Budgets · Programs** to
  **Home · Spend · Governance** (Budgets+Programs under one "Governance" deep view), or
  even **Home · Spend** with everything else reachable by drilling from Home.

### (b) Add a **lens bar** (period + grouping) at the top of Home
One control row that re-slices every card without leaving the page:

`Period: [ This quarter ▾ ]   Group by: [ Team ▾ ]   Compare: [ vs last quarter ▾ ]`

Mirrors Datadog template variables. Changing "Period → Last quarter" re-renders the KPIs,
trend, and breakdowns. "Group by → Work type / Project / Person" swaps the breakdown axis.

### (c) **Saved views** (named lenses)
Let a user save a configured lens as a named view and switch via a dropdown/tabs:
*"My quarter view"*, *"Board readout"*, *"Platform team deep-dive"*. One becomes their
default landing. (Role default exists out of the box; saved views are the personal layer.)

### (d) **Personalization layer** — pin / reorder / hide
On Home, a quiet "Customize" affordance lets a user **pin** the KPIs they check daily to
the top, **reorder** or **hide** cards they don't use, and pick their **default view**.
Stored per (account, member); resets to the opinionated default anytime. This is the
Datadog/Grafana persistent-layout model, scoped down to a fixed card set (not a blank
canvas — keeps it safe and on-brand).

---

## 4. Three concrete setups (phased — increasing ambition)

| | **Setup 1 — Consolidated Home** | **Setup 2 — + Lenses & Saved Views** | **Setup 3 — Customizable board** |
|---|---|---|---|
| **What** | Merge Overview+Summary into one F-pattern Home; Budgets/Programs become drill-in summary cards; trim nav | Add the lens bar (period/group/compare) + named saved views + default-view picker | Pin / reorder / hide cards; per-user persisted layout; "set primary KPI" |
| **Personalization** | None (opinionated default only) | Saved views per user | Full per-user layout |
| **Storage** | none | `dashboard_views` table (per member: name + lens JSON) | `dashboard_layout` (per member: order/pinned/hidden JSON) |
| **Effort** | Low — mostly recompose existing components | Medium — new lens state + view CRUD + re-slice plumbing | Higher — drag/reorder UI + layout persistence |
| **Risk** | Low | Medium | Medium-high |
| **Payoff** | Big clarity win immediately; one obvious home | Power users self-serve different questions | Sticky, "my dashboard" ownership |

**Recommended sequence:** ship **Setup 1** first (the biggest legibility win for the least
risk — it directly answers "start with consolidated views"), then **Setup 2** (lenses +
saved views = "change their view"), then **Setup 3** (pin/reorder = "customize per
preference") once we see which cards people actually live in.

---

## 5. Personalization data model (for Setup 2–3)

Small and self-contained, mirroring the existing per-(account, member) persona store:

```
dashboard_prefs(account_id, member_id,
                default_view TEXT,            -- saved-view id or 'default'
                layout JSON,                  -- {order:[...], pinned:[...], hidden:[...]}
                primary_kpi TEXT)
dashboard_views(id, account_id, member_id,
                name TEXT, lens JSON)         -- {period, group_by, compare, scope}
```

Defaults are computed (role-based) when no row exists — so nothing breaks for existing
users and the opinionated default is always the fallback.

---

## 6. Open questions for you

1. **How far to go now?** Setup 1 only, or commit to the phased 1→2→3?
2. **Nav shape:** `Home · Spend · Governance` (Budgets+Programs merged) vs keep them
   separate but demoted to drill targets?
3. **Customization depth:** saved *views* (lenses) are usually enough for finance; do you
   want full pin/reorder/hide (Setup 3), or is that over-building for the buyer?
4. **Default lens:** quarter-to-date grouped by team — is that the right out-of-box CFO view?

---

## Sources
- FinOps dashboards & drill-down — [CloudZero](https://www.cloudzero.com/blog/finops-dashboards/), [Algomox unified dashboard](https://www.algomox.com/resources/blog/unified_cloud_cost_dashboard_finops/)
- Datadog dashboards — [template variables / saved views](https://docs.datadoghq.com/dashboards/template_variables/), [context links](https://docs.datadoghq.com/dashboards/guide/context-links/), [platform](https://www.datadoghq.com/product/platform/dashboards/)
- CFO spend dashboards — [Fintech Brainfood: the CFO dashboard](https://www.fintechbrainfood.com/p/the-cfo-dashboard), [Brex expense management guide](https://www.brex.com/spend-trends/expense-management/expense-management-guide)
- B2B SaaS dashboard design & personalization — [Orbix optimization guide](https://www.orbix.studio/blogs/saas-dashboard-design-b2b-optimization-guide), [Upsolve personalized dashboards](https://upsolve.ai/blog/personalized-dashboards-for-saas), [role-based dashboards](https://www.plgos.com/blogs/7-smart-tools-to-automate-role-based-dashboards-in-saas)
- Overview-to-detail / KPI layout — [datawireframe layout patterns](https://www.datawirefra.me/blog/dashboard-layout-patterns), [DataCamp dashboard design](https://www.datacamp.com/tutorial/dashboard-design-tutorial)
