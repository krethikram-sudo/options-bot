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
pip install "modelpilot @ git+https://github.com/krethikram-sudo/modelpilot.git"
modelpilot demo --offline
```

Watch routing decisions scroll, then open the printed dashboard URL — or open
`/modelpilot/chat` and type your own prompts: the chip shows which model was
selected for each prompt *before generation*, then the realized saving.

## Production-shaped setup (5 minutes)

```bash
# 1. Start in GUIDANCE mode: zero behavior change, full measurement
modelpilot gateway --mode guidance --port 8400

# 2. Point your app at it — one line. Your API key stays in YOUR app;
#    the gateway forwards it and never stores it.
#    Python:      anthropic.Anthropic(base_url="http://localhost:8400")
#    TypeScript:  new Anthropic({ baseURL: "http://localhost:8400" })
#    Claude Code / any SDK:  ANTHROPIC_BASE_URL=http://localhost:8400

# 3. After traffic flows, the dashboard shows what autopilot WOULD save,
#    plus a side-by-side proof on your own prompts:
open http://localhost:8400/modelpilot/dashboard
modelpilot compare --from-captures --judge   # needs MODELPILOT_CAPTURE_PCT>0

# 4. Convinced? Capture it.
modelpilot gateway --mode autopilot --port 8400
```

**The recommended journey:** guidance → read the dashboard → autopilot.

| Mode | What it does | When |
|---|---|---|
| `guidance` | Nothing changes; every request is scored and the dashboard shows what autopilot would save | **Start here** |
| `autopilot` | Rewrites the model when confidence clears the gate; randomized holdout so savings are *measured*, and an escalation valve (`x-modelpilot-retry-of`) whose re-run costs are charged against the savings number | When the dashboard convinces you |
| `shadow` | Like guidance but emits no recommendation headers — pure measurement | Locked-down measurement only |

`guidance` is the customer-facing name for advise mode (both work).

**It improves with use — automatically.** In autopilot the gateway continuously
re-derives a per-category policy from *your own* traffic (every `MODELPILOT_AUTOTUNE_EVERY`
requests, default 100) and applies it live, no restart: it loosens routing on
categories that have proven safe on your workload and backs off any that caused an
escalation or negative feedback. The longer it runs, the more it saves. Disable with
`MODELPILOT_AUTOTUNE=0`; for a reviewable, pinned policy instead, run
`modelpilot tune --out policy.json` and start with `MODELPILOT_POLICY=policy.json`
(manual entries always override the learned ones).

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

## Prove it on your own prompts

```bash
modelpilot compare --prompts your_prompts.jsonl --judge
# routed 14/20 prompts · saved 61% ($1.87) · non-inferior 100%
# report: compare_report.html
```

Runs every prompt twice — ModelPilot's routing vs everything on the baseline
model — and produces one page with **costs and outputs side by side** plus a
position-debiased non-inferiority verdict per prompt. Savings you can audit
with your own eyes, not just a number. (`--offline` previews the report shape
with no spend.)

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
