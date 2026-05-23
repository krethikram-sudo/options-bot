# Skydock simulation

A discrete-time, full-system simulation of the **Skydock MVP** — drones
mounted on host vehicles that auto-deploy to capture aerial (BEV)
footage of road scenarios as training data for autonomous-vehicle
companies.

The sim implements the simulation hooks defined in the MVP spec v0.1
plus the operational-risk and customer-funnel layers, wired together
into a full-system model (§9.4):

- **§9.1 Operations** — trigger arrivals, pre-flight checks, mission
  state machine (launch → climb → capture → return → land), per-stage
  stochastic aborts, multi-vehicle fleet on heterogeneous corridors.
- **§9.2 Data pipeline** — upload, processing latency, quality
  scoring, customer-delivery threshold, per-scenario deliverable-
  package emission (metadata + agent tracks + OpenSCENARIO).
- **§9.3 Unit economics** — revenue per delivered scenario, variable
  costs (cloud, drone wear), labor and vehicle opex (per-vehicle),
  gross margin.
- **§7.1 Failure cascades** — drone flyaway, dock damage, battery
  degradation. Units go offline; downtime tracked.
- **§4.1-4.3 Customer funnel** *(opt-in)* — prospect arrivals (Poisson
  by month), pilot conversion gated by recent delivered quality,
  volume-tiered pricing, cash balance, runway.

It produces a live matplotlib animation of an N-vehicle fleet driving
city-block / suburban / highway corridors, deploying drones at scene
waypoints, and a side-panel dashboard of mission counters, failure
breakdown, recent-mission timeline, a running P&L, and optionally a
customer funnel state panel.

## Quick start

```bash
pip install -r requirements.txt

# Headless run, default config, print a report.
python run.py

# Live animation.
python run.py --animate

# Save the animation to gif/mp4.
python run.py --save out.gif

# Multi-vehicle fleet (uniform corridor).
python run.py --animate --vehicles 3

# Heterogeneous corridors — one vehicle per type.
python run.py --animate --vehicles 3 \
    --set host_vehicles.corridor_types=urban_dense,suburban,highway_mix

# Multi-month run with customer funnel enabled — pilots, runway, etc.
python run.py --vehicles 3 \
    --set simulation.duration_hours=2160 \
    --set customer_funnel.enabled=true

# Emit per-scenario deliverable packages (spec §3.2-3.4):
#   metadata.json + agent_tracks.json + scenario.xosc per delivered scenario.
python run.py --emit-packages out/scenarios

# Tweak parameters without editing yaml.
python run.py --animate \
    --set simulation.duration_hours=4 \
    --set trigger.poisson_rate_per_hour=6 \
    --set probabilities.pre_flight_pass=0.95
```

## Calibrate against spec targets

```bash
# Compare v0 defaults vs month-6 maturity priors against spec §6.1 / §1.5.
python calibrate.py --seeds 16 --both
```

Reports mean / p10 / p90 for each KPI with pass/fail per spec target.
Month-6 overrides represent operational improvements (tighter
checklist, faster flight profiles, weather-day rescheduling) and let
you see how far the v0 defaults are from the spec targets.

## Parameter sweep

```bash
# Default grid: fleet size × trigger rate × pre-flight pass probability,
# 5 seeds each. Writes CSV, summary JSON, and a marginal-effects plot.
python sweep.py --workers 4

# Custom grid (replace any axis).
python sweep.py --workers 4 \
    --sweep host_vehicles.count=1,2,3,5,8 \
    --sweep economics.price_per_scenario_usd=100,150,200 \
    --seeds 8
```

The sweep produces `out/sweep/sweep.csv`, `sweep_summary.json` with
mean/p10/p90 per config, and `sweep_plot.png` with marginal-effect
boxplots (one column per varying parameter).

## Layout

```
skydock/
├── default_config.yaml      # all tunable parameters with comments
├── run.py                   # interactive / save-to-file CLI
├── sweep.py                 # parameter sweep (marginal effects plot)
├── calibrate.py             # spec-target calibration vs v0/month-6 priors
└── skydock/
    ├── config.py            # YAML + CLI override loader
    ├── world.py             # multi-corridor geometry (urban/suburban/highway)
    ├── vehicle.py           # host vehicle (route follower)
    ├── drone.py             # drone state + battery capacity degradation
    ├── triggers.py          # Poisson + waypoint + hard-brake triggers (§1.3)
    ├── conditions.py        # diurnal wind + weather + daylight (multi-day)
    ├── mission.py           # mission state machine (§1.1) + cascade rolls
    ├── pipeline.py          # cloud upload / process / quality (§9.2)
    ├── deliverable.py       # metadata + tracks + xosc emission (§3.2-3.4)
    ├── economics.py         # revenue + costs (§9.3)
    ├── customer.py          # prospects + pilots + cash + runway (§4.1-4.3)
    ├── metrics.py           # rolling KPI aggregation
    ├── simulation.py        # multi-vehicle multi-corridor orchestrator (§9.4)
    ├── animation.py         # matplotlib live view + dashboard
    └── report.py            # end-of-run text report
```

## Configuration

All parameters live in `default_config.yaml`. The file's comments cite
the spec section each parameter feeds. Override individual values with
`--set section.key=value` (repeatable) without editing the YAML.

Key knobs:

| Parameter | Effect |
|---|---|
| `host_vehicles.count` | Fleet size — dominant lever on throughput |
| `host_vehicles.corridor_types` | Per-vehicle corridor type assignment |
| `trigger.poisson_rate_per_hour` | Mission attempt frequency (base) |
| `probabilities.pre_flight_pass` | Operational reliability |
| `conditions.wind_mph_amplitude` | Afternoon abort-by-wind risk |
| `mission.capture_seconds_min/max` | Capture duration spread |
| `pipeline.quality_mean/std` | Customer-deliverable rate |
| `economics.price_per_scenario_usd` | Revenue per delivered scenario (when funnel off) |
| `failure_cascades.*` | Flyaway / dock-damage / battery-degrade rates (§7.1) |
| `customer_funnel.enabled` | Toggle prospect→pilot→paid pipeline |
| `customer_funnel.prospect_arrival_per_month` | Lead-gen rate |
| `customer_funnel.starting_cash_usd` | Initial cash for runway calc |
| `simulation.emit_packages_to` | Directory for per-scenario deliverables |

## Deliverable packages

When `--emit-packages DIR` is set (or `simulation.emit_packages_to`
in the YAML), every delivered scenario produces:

```
DIR/{scenario_id}/
    metadata.json          # spec §3.3
    agent_tracks.json      # spec §3.4, synthesized agent trajectories
    scenario.xosc          # minimal OpenSCENARIO 2 stub
```

The agent tracks are synthetic (random ENU-frame trajectories under the
drone footprint), but the **shapes match the real deliverable** so the
package is suitable for showing prospective customers what they will
receive — before the hardware exists.

## Spec mapping

| Spec section | Module |
|---|---|
| §1.1 Mission profile | `skydock/mission.py` |
| §1.2 Operational envelope | `skydock/conditions.py`, `skydock/simulation.py` |
| §1.3 Trigger types | `skydock/triggers.py` |
| §1.4 Mission abort conditions | `skydock/mission.py::_pass_pre_flight` |
| §3.2-3.4 Deliverable schemas | `skydock/deliverable.py` |
| §3.5 Scene taxonomy | `skydock/world.py::WAYPOINT_SCENE_MIX` |
| §4.1-4.3 Customer funnel + pricing | `skydock/customer.py` |
| §5.4 Personnel (one operator/vehicle) | `skydock/economics.py::tick` |
| §6.1 / §1.5 Spec targets | `calibrate.py::TARGETS` |
| §7.1 Failure cascades | `skydock/mission.py::_resolve_landing`, `skydock/simulation.py::_step_unit` |
| §9.1 Operations sim hooks | `skydock/simulation.py`, `skydock/mission.py` |
| §9.2 Pipeline sim hooks | `skydock/pipeline.py` |
| §9.3 Economics sim hooks | `skydock/economics.py`, `skydock/customer.py` |
| §9.4 Full-system sim | `skydock/simulation.py` |

## What v0 deliberately doesn't model yet

- Moving-vehicle launch/recovery (V2 envelope, spec §1.2 row 1)
- ML-based scene anomaly trigger (V2, spec §1.3 trigger sources)
- BVLOS / regulatory waiver gating (spec §7.1 row 4)
- Realistic drone flight dynamics (it's a state-machine, not a quadrotor sim)
- Sales effort scaling — prospect rate is constant rather than ramping

These are the obvious next iterations once v0 surfaces real questions.

## License

TBD.
