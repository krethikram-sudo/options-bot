# Outlay — validation trail

The most important thing we've learned. Recorded so the reasoning survives the
chat it came from. Date: 2026-06-18.

## The bet under test

Outlay's moat is the **branch → ticket join**: resolve the git branch an AI
agent runs on back to the ticket it belongs to, so spend attributes to planned
work. The make-or-break metric is **ticket coverage** — the fraction of real
spend that resolves to a real ticket.

## Test 1 — dogfood on our own repo (real spend, real transcripts)

`python -m outlay.dogfood --repo krethikram-sudo/options-bot`

```
TICKET COVERAGE: 0%   (events=6534, tickets touched=0, issues=0)
```

- **Ingestion validated at scale:** 6,534 real Claude Code events parsed.
- **Join produced 0%**, for two independent structural reasons:
  1. `gitBranch` was `HEAD` for **all 11,874** transcript entries — the
     detached-HEAD state of Claude Code on the **web/remote**. No branch signal.
  2. `issues=0` — this repo uses `TODO.md`, not GitHub Issues. Nothing to join to.
- **Takeaway:** branch-based inference silently dies in detached-HEAD / remote /
  CI-agent contexts — a *growing* slice of how AI coding happens.

## Tests 2–4 — join-convention audits on public repos

`python -m outlay.audit` measures, across real repos, the fraction of merged
PRs that reference an issue (the attribution path that survives forks AND
detached HEAD). It validates the *precondition* (can the join fire), not
end-to-end spend coverage.

| Sample | Joinable | Read |
|---|---|---|
| Content/list repos (`public-apis`, `awesome-*`) | **36%** | noise — not software teams |
| SaaS product/starter repos | **49%** | sharply bimodal: 0% or 70–100% |
| Sentry org — GitHub-issue-managed SDKs (`sentry-python`, `sentry-go`) | **80–90%** | mechanism works great when GitHub *is* the tracker |
| Sentry org — flagship product repo (`getsentry/sentry`) | **30%** | undercounted — internal work tracked in Jira/Linear, not GitHub issues |

## Conclusions (evidence-backed)

1. **Passive branch/PR inference cannot be the *primary* attribution path.**
   Three real datasets agree: it returns 0% in detached-HEAD/no-tracker cases and
   varies 0–100% by team hygiene.
2. **Where GitHub Issues is the tracker + hygiene exists, inference is excellent
   (60–90%).** The mechanism is sound; it just can't be the foundation.
3. **Where the tracker is Jira/Linear (most of the enterprise ICP), GitHub-issue
   inference structurally undercounts** (the flagship-vs-SDK split proves it).
   This is why the Jira/Linear planner adapters + live pullers exist.
4. **The robust foundation is explicit task-tagging** — the launcher/wrapper/CI/
   proxy declares the ticket (`outlay/tag.py`), with branch/PR inference and
   the Jira/Linear join as complements/fallbacks. Detached-HEAD is recoverable
   via the CI PR-branch env (`GITHUB_HEAD_REF`) and commit-message trailers.

## Implications for product & GTM

- **Architecture:** explicit tagging is now the primary path; passive inference
  is the zero-config bonus. (`tag.py` ships this.)
- **Easiest first ICP:** high-discipline teams already on GitHub Issues — they
  get value on day one with **no instrumentation** (they're the 70–100% cluster).
- **Enterprise expansion:** Jira/Linear teams via the planner join + explicit
  tagging; do not rely on GitHub-issue parsing for them.
- **Still unproven:** end-to-end spend attribution on a real team. Public data
  de-risked the *mechanism*; it is not a substitute for a design partner's real
  agent telemetry joined to their tracker. **That remains the #1 validation gap.**
