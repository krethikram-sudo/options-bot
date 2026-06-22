# Scope — real-time program budget pacing (plan-vs-actual, in-flight)

*Goal: while a program is running, tell the customer accurately whether its compute spend is
**tracking to its initial forecast / budget or not** — a live variance signal and honest flags,
not just an end-of-period guess. Grounded in an audit of the current code (`console/outlay_app.py`
program functions + `console/store.py` program/history schema).*

---

## 1. What we want (the user's ask, restated)
At any moment mid-program: *"Are we where the forecast said we'd be by now, and at this rate will we
finish under budget?"* — surfaced as **on-track / at-risk / off-track** flags with the numbers
behind them (how far ahead/behind plan, projected end spend, projected breach date).

## 2. What exists today — and why it's not enough
- **`program_statuses()` / `_pace_status()`** project end-of-period spend by straight-lining the
  **recent sync-window** run-rate: `projected = spent / window × period`. A recent spike over-projects;
  a quiet week under-projects. It's a single noisy extrapolation, not a plan-vs-actual comparison.
- **`_program_timeline()`** walks month buckets comparing a **linear** cumulative projection to a
  **pro-rated slice of the cap** (`limit × elapsed_fraction`). So the implicit "plan" is just the
  budget cap spread evenly — there is **no real forecast baseline**, and "where we *are*" is a
  projection, not measured actuals.
- **No per-program spend history.** `outlay_history` is **account-level total** only
  (`ts, total_usd, forecast_usd, breakdown`). We can't reconstruct a given program's *actual
  cumulative spend over time* from it (the `breakdown` JSON keeps only top-N team/class slices).
- **No stored forecast.** `outlay_programs` has `limit_usd`, `period_days`, `start_ts`, `end_ts`,
  `members` — but no planned-spend curve.

**Net:** we compare a noisy projection to an assumed-linear cap. To do what the user wants we need
**(a) a real forecast baseline** and **(b) a measured per-program actual time-series**, then compute
the variance between them.

## 3. The model (plain-language earned-value)
For a program at time *now*:

| Quantity | Definition |
|---|---|
| **Planned-to-date (PV)** | The forecast curve evaluated at *now* — where the plan said cumulative spend should be. |
| **Actual-to-date (AC)** | Measured cumulative spend at the latest sync (from the new per-program time-series). |
| **Pace variance** | `AC − PV` ($ and %). Positive ⇒ spending faster than forecast. |
| **Burn rate** | Smoothed recent `Δspend/Δtime` (last N snapshots, to dampen single-sync spikes). |
| **Projected end (EAC)** | `AC + burn_rate × remaining_time` (run-rate EAC), cross-checked with the proportional `AC / elapsed_fraction`. |
| **Projected breach date** | The date the extrapolated actual curve crosses `limit_usd` — an interpolated **date**, not just "this month." |
| **Variance at completion** | `EAC − forecast_total` (vs. plan) and `EAC − limit_usd` (vs. the hard cap). |

**Status (real-time):** `on-track` (within tolerance, EAC ≤ cap) · `ahead/under-pace` · `at-risk`
(AC materially > PV, or EAC nearing cap) · `off-track` (EAC > cap → projected breach + date).
Tolerances configurable (e.g. warn >10% over plan; alert when projected to breach).

## 4. Data-model changes
1. **Per-program actual time-series** — new table:
   ```
   outlay_program_history(account_id, program_id, ts, spent_usd)   -- one row per program per sync
   ```
   Written in the sync path right where `outlay_history` is written today (`store.py:~1290`), reusing
   the same retention/purge plumbing. This is the substrate for AC-to-date and burn rate.
2. **Forecast = the budget (resolved).** From the customer's point of view the forecast total *is* the
   program budget (`limit_usd`) — we do **not** ask for a second number. The "plan" is the budget
   *time-phased* over the program: **linear by default** (`PV(now) = limit_usd × elapsed_fraction`).
   The only optional sophistication (Phase 2) is a non-linear **curve shape** for programs that ramp —
   an optional `forecast_curve TEXT` (JSON) added later; **no new field in the MVP**.

## 5. Engine changes (`outlay_app.py`)
- New `program_pacing(program, program_history, now) -> dict` returning the §3 quantities + status.
- Re-point `program_statuses()` to use **AC from the time-series** (not the single-point projection)
  and **PV from the forecast baseline** (not the pro-rated cap). Keep `_pace_status` as a fallback for
  programs with too little history.
- `_program_timeline()` gains a **third series**: planned (forecast) alongside actual + cap — so the
  month view shows plan vs. actual vs. ceiling, and the breach marker comes from the actual
  extrapolation.
- **Burn-rate smoothing** over the last N snapshots to avoid spike-driven false alarms.

## 6. Surfacing (UX)
- **Program card:** a pacing strip — *"$320k actual vs $280k planned to date (▲14% over forecast) ·
  projected end $1.18M vs $1.0M budget · projected to exceed on Mar 12"* + a small **plan-vs-actual
  sparkline** (two lines + the cap).
- **Attention panels (business + eng):** auto-flag off-pace programs — *"Platform is pacing 18% over
  forecast; at this rate it exceeds budget by ~$42k on Mar 12."* Reuses the existing `_finance_attention`
  / `_eng_attention` mechanism.
- **Anomaly auto-flag:** a sync where actual jumps materially above the forecast curve → a flagged event
  (ties into the existing anomaly webhook/Slack/SOC plumbing).
- **Quarterly/summary view:** per-program variance-at-completion roll-up.

## 7. Accuracy & honesty guardrails (per CLAUDE.md — claims stay substantiated)
- **Don't flag too early.** Projections are unstable when little has elapsed / few snapshots exist.
  Gate confident flags behind a minimum (e.g. ≥2 snapshots **and** ≥15% elapsed); before that, show
  *"gathering baseline."*
- Label projections as **estimates** and show the basis (elapsed %, burn window, # snapshots).
- Keep **forecast total** and **hard cap** visually distinct — they're different lines.
- Programs already running before this ships won't have full history; **best-effort backfill** from
  `outlay_history` where the program scope is `overall`, otherwise start the series fresh and improve
  as syncs accrue (state this in-product).

> **Status — MVP (P0 + P1) BUILT.** Per-program time-series (`outlay_program_history`) written on
> every sync; `program_pacing()` engine (actual-to-date vs. linear plan, smoothed burn rate, blended
> EAC, interpolated projected-breach **date**, min-data "gathering baseline" gating); program-card
> pacing strip + plan-vs-actual bars; pacing drives the headline status and enriches the business +
> engineering attention flags. P2/P3 below remain.

## 8. Phasing & rough effort
| Phase | Scope | Effort |
|---|---|---|
| **P0 — substrate + engine** | `outlay_program_history` table + write on sync; `forecast_usd` field (default=cap); `program_pacing()` with actual-vs-linear-forecast + status; min-data gating. | **~2–3 days** |
| **P1 — surfacing** | Program-card pacing strip + plan-vs-actual sparkline; auto-flags in business+eng attention panels; interpolated projected-breach **date**. | **~2–3 days** |
| **P2 — richer forecast** | Customer-entered **monthly** forecast curve (non-linear); smoothed burn-rate EAC variants; quarterly variance report; confidence framing. | **~1 week** |
| **P3 — alerting tie-in** | Off-pace → existing alert/webhook/Slack; optional pacing-based enforcement. | **~2–3 days** |

**MVP = P0 + P1 (~1 week):** accurate, real-time *actual-vs-forecast* pacing with honest flags and a
projected breach date — the heart of the request.

## 9. Decisions
1. **Forecast definition — RESOLVED:** the forecast total = the program **budget** (`limit_usd`); no
   second number. The plan is the budget **time-phased linearly** for the MVP; an optional non-linear
   **curve shape** (not a different total) is the only Phase-2 forecast sophistication.
2. **Backfill vs. fresh start** for programs already running (recommend: best-effort backfill from
   `outlay_history` where scope is `overall`, otherwise start the series fresh and improve as syncs accrue).
3. **EAC basis:** proportional (`AC/elapsed`) vs. recent run-rate vs. blended (recommend blended+smoothed).
