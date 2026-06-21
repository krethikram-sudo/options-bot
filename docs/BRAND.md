# Outlay — brand & UI spec

The single source of truth for look-and-feel. Extracted from
`modelpilot/site/outlay.css` (marketing/legal/docs) and the `:root` block in
`console/web.py` (the app). Both surfaces share one token system — keep them in
sync. When building or restyling a page, follow this; if you intentionally
diverge, update this doc in the same change.

**North star:** a *financial control panel* — calm, instrument-like, dense but
legible. Money is the subject, so the palette behaves like a ledger: green =
healthy / savings, amber = caution, red = over budget, navy = authority/depth.
Honest and substantiated over flashy (estimates are labeled estimates).

---

## Color tokens

| Token | Hex | Use |
|---|---|---|
| `--ink` | `#0b0f17` | Headings, primary text & numbers on light |
| `--body` | `#3a4252` | Body copy |
| `--mut` / `--muted` | `#6b7280` | Secondary text, captions, labels |
| `--faint` | `#9aa1ad` | Tertiary text, sub-labels, disabled |
| `--line` | `#e4e7ec` | Default borders, card edges, dividers |
| `--line2` | `#eef1f5` | Lighter inner dividers (table rows) |
| `--bg` | `#ffffff` | Page background, cards |
| `--paper` | `#f6f8fa` | Subtle fills, table headers, notes |
| `--paper2` | `#eef1f5` | Code chips, inline tints |
| `--navy` | `#13203a` | Dark sections (hero/final/footer), code blocks |
| `--navy2` | `#1c2c4d` | Footer bg, code accents |
| `--grn` | `#0f6b4f` | **Brand / primary accent** (buttons, money-positive) |
| `--grn-d` | `#0a4f3a` | Links, link hover, primary-button hover, green text |
| `--grn-l` | `#e7f1ec` | Green tints (icon chips, badges, highlighted cells) |
| `--amber` / `--warn` | `#b45309` | Caution, projections, warnings |
| `--amber-l` | `#fbf0df` | Amber tint (warn notes/tags) |
| `--red` / `--bad` | `#b3261e` | Over-budget, errors, destructive |
| `--red-l` | `#f8e7e4` | Red tint |
| `--gold` | `#9a7b27` | Rare accent |

**On dark (navy) surfaces** text goes light (`#dbe2ef`, `#fff`) and green
brightens for contrast: `#6ee7b7` (brand dot), `#5fd0a0` (hero emphasis),
`#7fdcb4` (links/eyebrow). Dark sections carry a faint radial green glow
(`radial-gradient(... rgba(15,107,79,.18), transparent)`).

> Accent aliases: `--accent`/`--accent-d` == `--grn`/`--grn-d`. There's a minor
> token drift — the site uses `--mut`, the console defines both `--mut` and
> `--muted`. Prefer `--mut` in new site CSS; either works in the console.

---

## Typography

- **Display & sans:** Inter (`--disp`/`--sans`, same family) with a system
  fallback stack. Distinguish display by weight + tracking, not a second face.
- **Mono:** `ui-monospace, SFMono-Regular, Menlo` (`--mono`) — eyebrows, labels,
  table headers, code, nav-group headings.
- **Body base:** 16.5px / line-height 1.6, `font-feature-settings:"cv05","ss01"`,
  antialiased. Console body is denser at 14px.
- **Headings:** weight 600 (700 for brand/hero/stats), line-height 1.1,
  letter-spacing −0.018em to −0.033em (tighter as size grows).
- **Numbers:** tabular lining figures (`.num` → `font-variant-numeric:tabular-nums
  lining-nums`). Always use for money/metrics so columns align.

**Type scale**

| Context | Marketing site | Console (app) |
|---|---|---|
| Hero H1 | 58 → 44 → 36px (responsive) | — |
| Page/section H1·H2 | page H1 42, section H2 38 | H1 27, H2 18 |
| Big stat | `.bignum` 40 | `.stat` 30 |
| Card/sub H3 | 18–25px | — |
| Body | 15.5–16.5px | 14px |
| Small / caption | 12–14px | `.small` 13px |
| Eyebrow / label | 11.5–12px mono, uppercase, tracking .04–.12em | `.label` 12px mono |

---

## Spacing, shape & elevation

- **Container:** `--max` 1140px, side padding 24px. Prose/legal column 760px.
- **Section rhythm (marketing):** 84px vertical; content pages 64px top.
- **Radius:** 6px buttons · 8px chips/inputs/step-numbers · 10–14px cards &
  panels · 999px pills/tags/badges.
- **Borders:** 1px `--line` is the default separator everywhere; cards are white
  on a 1px line (not shadow-only).
- **Shadows:** soft, navy-tinted, large blur + heavy negative spread (so they
  read as depth, not drop-shadow). Reference values:
  - Card/panel rest: `0 24px 50px -40px rgba(19,32,58,.32)`
  - Hover lift: `translateY(-2px)` + `0 18px 40px -32px rgba(19,32,58,.4)`
  - Primary button hover: `0 6px 16px -10px rgba(11,79,58,.5)`

---

## Components (canonical patterns)

- **Buttons** `.btn`: radius 6, padding 13×22, weight 600, 15.5px, `.lg` bumps it.
  - `.primary` green → darker on hover; `.ghost` transparent + `--line` border;
    `.onnavy` white-on-dark for dark sections.
- **Cards** `.card`/`.owner`/`.lstep`: white, 1px `--line`, radius 10, padding 24,
  hover lift. Icon chip = 40px, radius 10, `--grn-l` bg + `--grn-d` stroke icon.
- **Eyebrow** `.eyebrow`: mono uppercase, tracking .12em, muted — the small label
  above section headings.
- **Tags/badges** `.tag` (pill): semantic tints — `.ok` green, `.warn` amber,
  `.over` red, `.ex` neutral. Tiny uppercase mono.
- **Tables** `.wt`/`.cmp`: mono uppercase muted headers on `--paper`; rows split by
  `--line2`; the "us"/savings column gets `--grn-l` bg and `--grn-d` weight.
- **Notes/callouts** `.note`: paper card; `.note.warn` amber tint. Used for the
  legal "template/draft" banners.
- **Dark sections** `.navysec`/`.hero`/`.final`/`footer`: navy bg + radial green
  glow, light text, brightened green accents.
- **Icons:** inline SVG, 1.7 stroke-width, round caps/joins, `currentColor` —
  never icon fonts (zero-dependency).

---

## Motion

- **Easing:** `--ease: cubic-bezier(.22,.61,.36,1)`. Interaction transitions
  .18–.25s; reveals .55s.
- **Scroll reveal** `.reveal`: fade + `translateY(12px)`; progress bars animate
  `scaleX(0→1)`. **Always gated by `@media (prefers-reduced-motion:reduce)`**
  (already wired) — keep new motion behind it too.
- **Hover:** cards/owners/steps lift 2px. Keep motion subtle; this is a finance
  tool, not a consumer splash page.

---

## Voice & tone

- Plain, precise, finance-credible. Sentence case in the product.
- Claims are substantiated and bounded — "estimates measured from your data, not
  guarantees," ranges over single hero numbers, "no prompt content leaves your
  box." Never over-promise savings or accuracy.
- Founder-direct and concrete; explain the *why* in a muted sub-line rather than
  marketing adjectives.

---

## Accessibility & quality bar

- Maintain AA contrast (the ink/body/mut ramp on white is built for it; check any
  new color on tinted backgrounds).
- Respect `prefers-reduced-motion` (above).
- Keep the front end **zero-dependency** — no JS framework, no icon fonts, no web
  fonts beyond the Inter/system stack. It's part of the privacy story.
- The console already targets WCAG 2.2 (see the coachmark engine in `web.py`);
  hold new interactive UI to keyboard-operable, Esc-dismissable standards.
