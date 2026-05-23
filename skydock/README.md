# Skydock simulation

A discrete-time, full-system simulation of the **Skydock MVP** — drones
mounted on host vehicles that auto-deploy to capture aerial (BEV)
footage of road scenarios as training data for autonomous-vehicle
companies.

The sim implements the three "simulation hooks" defined in the MVP
spec v0.1, wired together into a full-system model (§9.4):

- **§9.1 Operations** — trigger arrivals, pre-flight checks, mission
  state machine (launch → climb → capture → return → land), and
  per-stage stochastic abort modes.
- **§9.2 Data pipeline** — upload, processing latency, quality
  scoring, customer-delivery threshold, deliverable-package emission.
- **§9.3 Unit economics** — revenue per delivered scenario, variable
  costs (cloud, drone wear), labor and vehicle opex (per-vehicle),
  gross margin.

It produces a live matplotlib animation of an N-vehicle fleet driving
a city-block corridor, deploying drones at scene waypoints, and a
side-panel dashboard of mission counters, failure breakdown, a recent-
mission timeline, and a running P&L.

## Quick start

```bash
pip install -r requirements.txt

# Headless run, default config, print a report.
python run.py

# Live animation.
python run.py --animate

# Save the animation to gif/mp4.
python run.py --save out.gif

# Multi-vehicle fleet.
python run.py --animate --vehicles 3

# Emit per-scenario deliverable packages (spec §3.2-3.4):
#   metadata.json + agent_tracks.json + scenario.xosc per delivered scenario.
python run.py --emit-packages out/scenarios

# Tweak parameters without editing yaml.
python run.py --animate \
    --set simulation.duration_hours=4 \
    --set trigger.poisson_rate_per_hour=6 \
    --set probabilities.pre_flight_pass=0.95
```

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
├── sweep.py                 # parameter sweep
└── skydock/
    ├── config.py            # YAML + CLI override loader
    ├── world.py             # city-block corridor geometry
    ├── vehicle.py           # host vehicle (route follower)
    ├── drone.py             # drone physical state
    ├── triggers.py          # Poisson + waypoint + hard-brake triggers (§1.3)
    ├── conditions.py        # diurnal wind + weather + daylight
    ├── mission.py           # mission state machine (§1.1)
    ├── pipeline.py          # cloud upload / process / quality (§9.2)
    ├── deliverable.py       # metadata + tracks + xosc emission (§3.2-3.4)
    ├── economics.py         # revenue + costs (§9.3)
    ├── metrics.py           # rolling KPI aggregation
    ├── simulation.py        # multi-vehicle orchestrator (§9.4)
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
| `trigger.poisson_rate_per_hour` | Mission attempt frequency |
| `probabilities.pre_flight_pass` | Operational reliability |
| `conditions.wind_mph_amplitude` | Afternoon abort-by-wind risk |
| `mission.capture_seconds_min/max` | Capture duration spread |
| `pipeline.quality_mean/std` | Customer-deliverable rate |
| `economics.price_per_scenario_usd` | Revenue per delivered scenario |
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
| §3.5 Scene taxonomy | `skydock/world.py::WAYPOINT_LABELS` |
| §4.3 Unit economics | `skydock/economics.py` |
| §5.4 Personnel (one operator/vehicle) | `skydock/economics.py::tick` |
| §6.1 Technical metrics | `skydock/metrics.py` |
| §9.1 Operations sim hooks | `skydock/simulation.py`, `skydock/mission.py` |
| §9.2 Pipeline sim hooks | `skydock/pipeline.py` |
| §9.3 Economics sim hooks | `skydock/economics.py` |
| §9.4 Full-system sim | `skydock/simulation.py` |

## What v0 deliberately doesn't model yet

- Moving-vehicle launch/recovery (V2 envelope, spec §1.2 row 1)
- ML-based scene anomaly trigger (V2, spec §1.3 trigger sources)
- BVLOS / regulatory waiver gating (spec §7.1 row 4)
- Customer-acquisition funnel (spec §9.3 sub-loop, deferred)
- Realistic drone flight dynamics (it's a state-machine, not a quadrotor sim)
- Per-corridor heterogeneity (all vehicles share one route in v0)

These are the obvious next iterations once v0 surfaces real questions.

## License

TBD.
