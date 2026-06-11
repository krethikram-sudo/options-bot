# ModelPilot for Claude — browser extension (v0, advisory)

Brings the ModelPilot experience to **claude.ai with your regular Claude
account**: as you type a prompt, a chip appears telling you which model the
prompt actually needs and the estimated usage value saved if you pick it —
informed by the visible conversation (session-context routing), before you
hit send.

```
you type on claude.ai ──► content script (draft + visible transcript)
                              │
                              ▼ (background worker)
                    local ModelPilot gateway :8400  /modelpilot/preview
                              │
                              ▼
        💡 chip: "claude-haiku-4-5 is enough — est. $0.004 saved if you switch"
```

## Why advisory-only (v0)

claude.ai has no public API for the chat UI, so:

- **Mode 1 (this extension):** read the composer, suggest. Safe.
- **Mode 2 (auto-switching the model picker)** would be DOM automation of
  Anthropic's app — brittle against UI changes and needs a ToS review before
  we ship it. Deliberately not in v0.
- **Money framing:** consumer/Team plans are flat-rate, so the chip reports
  *usage value* (API-equivalent $) — what it buys you is rate-limit headroom
  (more Opus/Fable budget left for the work that needs it), not a smaller bill.
  Dollar savings live on the API/Claude Code surfaces.

## Install (Chrome / Edge / Brave / Arc)

1. Gateway must be running on your machine (`./scripts/install_modelpilot_gateway.sh`).
2. Open `chrome://extensions`, enable **Developer mode** (top right).
3. **Load unpacked** → select this `modelpilot/extension/` folder.
4. Open claude.ai, start typing — the chip appears bottom-right after a pause.

Nothing leaves your machine except what already did: the draft text goes only
to your local gateway (127.0.0.1), which scores it locally and stores nothing.

## Known limitations (claude.ai's DOM changes without notice)

- Composer/transcript/model-picker detection is heuristic with fallbacks; if
  the chip stops appearing or reads the wrong model after a claude.ai update,
  the selectors in `content.js` need a refresh — report what you see.
- The transcript reader is best-effort; when it can't find messages, routing
  falls back to the draft alone (you lose follow-up inheritance, never safety).
- Firefox/Safari need manifest tweaks (not yet done).
