# Site redesign — running worklist

The visual leveling-up of the marketing site, page by page. The Playwright loop
works **in the web session too** — Chromium is preinstalled at `/opt/pw-browsers`,
so `npx playwright screenshot` and a small node script (reducedMotion:'reduce' to
defeat the scroll-reveal) render real screenshots. Design against `docs/BRAND.md`;
screenshot desktop + mobile and eyeball before committing.

**Workflow per page:** shoot current → list specific fixes against BRAND.md →
apply → re-shoot desktop + mobile → diff visually → commit. One PR per page (or
small batch) so regressions are easy to bisect.

---

## Already shipped (baseline, no visual change)
- [x] Self-hosted Inter; Google Fonts removed from all 9 pages; font preload.
- [x] `<main>` landmark + skip-to-content link on all 9 pages.
- [x] Clickable logo home (was a dead `<span>` on the landing page).
- [x] `docs/BRAND.md` design spec.

## Global — do once, affects every page
- [x] **Mobile nav.** Accessible checkbox-driven hamburger across all 9 pages
      (#167) — frosted dropdown, X morph, keyboard + Esc + close-on-navigate.
- [x] **`og:image`.** On-brand 1200×630 social card shipped (`/og-image.png`),
      wired to `og:image` + `twitter:image` (summary_large_image) on all 9 pages.
      Source template: `modelpilot/site/og/card.html` (noindex). Regenerate:
      serve the site dir, then `node` a Playwright shot of `/og/card.html` at
      1200×630 → `modelpilot/site/og-image.png`.
- [ ] **Consistency pass:** confirm spacing rhythm, button sizes, eyebrow casing,
      and card shadows match BRAND.md across pages (they share `outlay.css`, so
      fix at the class level, not per page).
- [ ] **Reduced-motion + keyboard:** re-verify the scroll-reveal and any new nav
      are `prefers-reduced-motion`-safe and tab/Esc-operable.
- [ ] Token cleanup: standardize `--mut` vs `--muted` (site vs console) noted in
      BRAND.md.

---

## Per-page visual goals

### `index.html` — landing (in progress)
Hero is strong; tighten the rest.
- [x] Compare section restructured from flat text → 3 category cards (it was the
      one all-text section; now matches the page's card rhythm).
- [ ] Still to check: hero panel cards at mobile width, `.herogrid` reflow at
      940px, the dense compatbar wrapping, section vertical rhythm, and the live
      "count-up" stat on first paint.

### `platform.html` — "Cost it right, plan it, take it anywhere" ✓
Page is strong (the "costed two ways" comparison and the 6-card grid read well).
- [x] Added a numbered jump-nav (`.pillnav`, reusable) under the flat hero —
      maps the h1's three clauses to the #math / #estimate / #data sections, so
      the long page has wayfinding and the hero isn't bare text.

### `security.html` — "Governance without shipping us your prompts" ✓
- [x] Pulled the "what never leaves / what we see" story out of stacked prose
      into a side-by-side: a green "stays in your environment" card vs a neutral
      "metadata only" card — the security contrast is now instant.
- [x] Mobile flow fix (global): the read-only flow diagram now stacks vertically
      with down-arrows below 560px (also helps platform + docs).
- Architecture + data-handling prose left as-is (reviewers want the detail).

### `compare.html` — category positioning ✓
- [x] Mobile table readability: the green "Outlay" win column was the last column
      and off-screen on mobile. Added a scroll hint naming it, plus a sticky
      feature-label column so row context stays pinned while scrolling to reach
      the highlighted column. Desktop table unchanged.
- Per-category prose below the table left as-is (detail reads fine).

### `accuracy.html` — "How accurate — honestly"
Credibility page. Goals: make the "two questions" split obvious, present the
measured-error ranges as instrument-like (not marketing), keep the honest tone
visually restrained.

### `pilot.html` — design-partner pilot
Conversion page. Goals: the 4-step timeline, the "fit if…" checklist, and a
single strong CTA. Tighten to feel like a focused offer.

### `healthcare.html` — vertical landing (PHI)
Goals: lead with the compliance-review framing, honest-on-certifications note
styled as a `.note`, and the economics section. Mirror the landing structure
but shorter.

### `tour.html` — product tour
Most visual page (5 narrative steps). Goals: each step gets a strong mock/panel
(reuse `.pcard`), consistent left/right alternation, smooth scroll rhythm.

### `docs/index.html`
Lower priority. Goals: readable prose width, code-block styling, doc-nav pills.

---

## Suggested order (buyer's path)
1. `index` → 2. `platform` → 3. `security` → 4. `compare` → 5. `accuracy`
→ 6. `pilot` / `healthcare` → 7. `tour` → 8. `docs`

Do the **global mobile-nav** fix first — it affects every page you'll screenshot.
