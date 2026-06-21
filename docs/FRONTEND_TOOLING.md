# Frontend / UI tooling for Claude

This repo's web surface is intentionally **zero-build**: hand-written HTML + a
shared `modelpilot/site/outlay.css` for the marketing/legal site, and
server-rendered HTML (Python f-strings) in `console/web.py`. Keep it that way —
the no-dependency front end is part of the privacy story. The tooling below makes
Claude better at design *within* that constraint; none of it adds a runtime
dependency to the app.

## The point: give Claude eyes

By default Claude edits HTML/CSS blind. The single biggest quality lever is a
**visual loop** — render a page, screenshot it, look, iterate.

### Playwright MCP (browser control)
Configured in `.mcp.json` (project scope, so it's available to anyone who opens
this repo in Claude Code). It lets Claude open a page, screenshot it, check it at
mobile/tablet/desktop widths, click through flows, and read computed styles.

- **Local Claude Code:** works out of the box — `npx @playwright/mcp` manages its
  own Chromium. Run `/mcp` in Claude Code to confirm it connected.
- **Claude Code on the web:** the default network policy in this environment
  **blocks the Playwright browser-binary download** (pip/npm indexes are
  reachable, the browser CDN and apt mirrors are not). To use the visual loop in
  *web* sessions, either pick a network policy that allows the Playwright
  download host, or pre-install Chromium in the environment's setup script /
  image. See https://code.claude.com/docs/en/claude-code-on-the-web.

### Design happens in code
There's no external design tool — UI is designed directly with Claude in HTML/CSS.
The source of truth for look-and-feel is **`docs/BRAND.md`** (tokens, type scale,
spacing, components, voice), extracted from `outlay.css` + the console CSS. Point
Claude at it when building or restyling a page so output stays consistent.

## Non-MCP fallback: `tools/shoot.py`
A dev-only screenshot script for anywhere a Playwright browser is installed
(handy in CI or when you don't want the MCP). Renders full-page shots at desktop
+ mobile widths into `screenshots/` (gitignored):

```bash
pip install playwright && playwright install chromium      # once
python3 -m http.server 8000 --directory modelpilot/site &  # serve static site
python3 tools/shoot.py http://localhost:8000/legal/terms.html http://localhost:8000/index.html
```

## Recommended next steps (not yet wired)
- **Brand spec** — done: see `docs/BRAND.md` (keep it updated as the system evolves).
- **Visual-regression snapshots** on key pages (pricing, legal, overview) so a
  CSS tweak can't silently break a page.
- **Lighthouse / axe** passes for performance + accessibility (the console
  already targets WCAG — see the coachmark engine in `web.py`).
