# Changelog

## 0.1.0 (beta) — 2026-06-11

First beta release.

- Drop-in gateway for the Claude API with three modes: shadow (measure only),
  advise (recommendation headers), autopilot (confidence-gated routing with
  randomized holdout and escalation valve)
- Session-context-aware router: follow-ups inherit session difficulty;
  mechanical tasks over existing content keep their cheap tier; cache-aware
  switch economics; expected-conversation-length model
- Live dashboard: per-session savings strip (auto-updating), session history,
  cumulative savings, model-mix migration, RCT panel with bootstrap CIs,
  escalation netting
- Chat playground with pre-execution model selection and per-message savings
- claude.ai browser extension (advisory)
- Golden-set tuning pipeline (Batch API fan-out, position-debiased judging,
  confidence-gate calibration) + shadow-traffic corpus exporter
- `modelpilot` CLI: gateway / demo / report / share
