# Site redesign — running worklist

The visual leveling-up of the marketing site, page by page. **Do this in local
Claude Code** so the Playwright loop is live (render → screenshot → iterate);
the web container can't install a browser. Design against `docs/BRAND.md`;
screenshot with `tools/shoot.py` (desktop + mobile) and eyeball before committing.

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
- [ ] **Mobile nav (highest priority).** `outlay.css:50` hides `.navlinks` below
      860px with no replacement — mobile gets only logo + Sign in. Add a
      zero-JS-or-tiny-JS hamburger that reveals the links. Verify at 390px.
- [ ] **`og:image`.** Points at `favicon.svg`; social cards need a real
      1200×630 PNG (generate one on-brand: navy bg, green accent, the product
      panel). Update `og:image`/`twitter:image` on every page; switch
      `twitter:card` to `summary_large_image`.
- [ ] **Consistency pass:** confirm spacing rhythm, button sizes, eyebrow casing,
      and card shadows match BRAND.md across pages (they share `outlay.css`, so
      fix at the class level, not per page).
- [ ] **Reduced-motion + keyboard:** re-verify the scroll-reveal and any new nav
      are `prefers-reduced-motion`-safe and tab/Esc-operable.
- [ ] Token cleanup: standardize `--mut` vs `--muted` (site vs console) noted in
      BRAND.md.

---

## Per-page visual goals

### `index.html` — landing (start here)
Hero is strong; tighten the rest. Check: hero panel cards at mobile width
(two stacked `.pcard`s), `.herogrid` reflow at 940px, the dense compatbar
wrapping, section vertical rhythm, and CTA hierarchy (primary vs ghost). Make
sure the live "count-up" stat reads well on first paint.

### `platform.html` — "Cost it right, plan it, take it anywhere"
Feature-heavy. Goals: clear visual grouping of the three pillars, the
"costed two ways" comparison legibility, and the `#math` cache-cost callout.

### `security.html` — "Governance without shipping us your prompts"
Trust page → make it feel auditable and calm. Goals: the "what never leaves /
what we see" two-column contrast, the read-only architecture diagram/flow, and
scannable data-handling list.

### `compare.html` — category positioning
Comparison tables are the core. Goals: table readability at mobile (horizontal
scroll affordance), the "us" column highlight, and the per-category cards.

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
