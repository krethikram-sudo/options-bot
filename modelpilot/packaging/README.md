# ModelPilot <sub>beta</sub>

**Cut your Claude API bill 30–50% without touching your code — and see the proof live.**

ModelPilot is a drop-in gateway for the Claude API. It reads each request (and
its conversation context), routes it to the cheapest model that's provably good
enough, and shows you exactly what you saved — per prompt, per session, and
verified with a built-in randomized holdout. Hard work is never downgraded.

```
your app ──► ModelPilot gateway ──► api.anthropic.com
                  │
                  ├── classification prompt?  → claude-haiku-4-5   (~90% cheaper)
                  ├── complex refactor?       → stays on the big model
                  └── every request           → savings ledger + live dashboard
```

## Two-minute proof (no API key, no spend)

```bash
pip install "modelpilot @ git+https://github.com/YOUR_ORG/modelpilot.git"
modelpilot demo --offline
```

Watch routing decisions scroll, then open the printed dashboard URL — or open
`/modelpilot/chat` and type your own prompts: the chip shows which model was
selected for each prompt *before generation*, then the realized saving.

## Production-shaped setup (5 minutes)

```bash
# 1. Run the gateway (start in shadow mode: zero risk, full measurement)
modelpilot gateway --mode shadow --port 8400

# 2. Point your app at it — one line. Your API key stays in YOUR app;
#    the gateway forwards it and never stores it.
#    Python:      anthropic.Anthropic(base_url="http://localhost:8400")
#    TypeScript:  new Anthropic({ baseURL: "http://localhost:8400" })
#    Claude Code / any SDK:  ANTHROPIC_BASE_URL=http://localhost:8400

# 3. After traffic flows, see what routing would have saved:
open http://localhost:8400/modelpilot/dashboard
modelpilot report --days 7
```

**Modes** (progressive trust):

| Mode | What it does | When |
|---|---|---|
| `shadow` | Nothing changes; every request is scored and a would-have-saved ledger accumulates | Start here |
| `advise` | Adds `x-modelpilot-recommended-model` / savings headers to responses | When the shadow report looks right |
| `autopilot` | Rewrites the model when confidence clears the gate; includes a randomized holdout so savings are *measured*, and an escalation valve (`x-modelpilot-retry-of`) whose re-run costs are charged against the savings number | When you're ready |

## What makes the routing trustworthy

- **Downgrade-only, confidence-gated, do-no-harm default** — when unsure, it
  doesn't touch your request. Calibrated against a golden dataset with a
  ≤2% false-downgrade target.
- **Session-aware** — `"why?"` after a hard debugging exchange stays on the
  big model; `"extract the fixes as JSON"` over the same transcript drops to
  Haiku. No prompt is routed as an independent decision.
- **Cache-aware economics** — prompt caches are model-scoped; ModelPilot
  prices the cache rewrite before any mid-conversation switch and vetoes
  switches that would cost more than they save.
- **Honest accounting** — escalation re-runs and estimates vs. RCT-verified
  numbers are clearly separated on the dashboard. The system shows you its
  misses.

## Privacy & security

- Binds to `127.0.0.1` only. Your API keys pass through and are never stored.
- The ledger stores token counts, model names, and routing metadata —
  **no prompt text, no responses** — unless you explicitly enable sampled
  capture for tuning (`--capture`, default 0).
- `modelpilot share` produces a redacted diagnostics summary (counts and
  dollars only) for support.

## Also in the box

- **Live chat playground** at `/modelpilot/chat` — autopilot routing with
  per-message savings, great for evaluating quality yourself
- **Browser extension** (`extension/`) — advisory model recommendations on
  claude.ai as you type (see `extension/README.md`)
- **macOS launchd installer** (`scripts/install_modelpilot_gateway.sh`) —
  always-on gateway + a `claude` wrapper that routes Claude Code through it
- **Tuning pipeline** (`modelpilot/goldenset/`) — calibrate the router on
  your own traffic
- **Testing guide** (`docs/TESTING.md`) — prompts that exercise every routing
  behavior

## Beta expectations & feedback

This is a beta: the router is heuristic-v0 calibrated on seed data and tuned
per-deployment on your traffic; expect conservative routing (missed savings,
not quality risk) until calibration runs on your workload.

- 🐛 **Found a routing miss?** Open an issue with the chip text and
  `modelpilot share` output (no prompt text needed).
- 💡 Feature requests and questions → GitHub issues.

## License

Beta evaluation license — internal evaluation only, see [LICENSE](LICENSE).
