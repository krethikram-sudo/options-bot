# Skydock simulation

A discrete-time, full-system simulation of the **Skydock MVP** — drones
mounted on host vehicles that auto-deploy to capture aerial (BEV)
footage of road scenarios as training data for autonomous-vehicle
companies.

The sim implements the three "simulation hooks" defined in the MVP
spec v0.1:

- **9.1 Operations** — trigger arrivals, pre-flight checks, mission
  state machine (launch → climb → capture → return → land), and
  per-stage stochastic abort modes.
- **9.2 Data pipeline** — upload, processing latency, quality
  scoring, customer-delivery threshold.
- **9.3 Unit economics** — revenue per delivered scenario, variable
  costs (cloud, drone wear), labor and vehicle opex, gross margin.

It produces a live matplotlib animation of one or more host vehicles
driving a corridor, deploying their drone at interesting scenes, and a
side-panel dashboard of mission counters, abort reasons, and a running
P&L.

## Quick start

```bash
pip install -r requirements.txt

# Headless run, default config, print a report.
python run.py

# Live animation.
python run.py --animate

# Save the animation to mp4 (requires ffmpeg on PATH).
python run.py --save out.mp4

# Tweak parameters without editing yaml.
python run.py --animate \
    --set simulation.duration_hours=4 \
    --set trigger.poisson_rate_per_hour=6 \
    --set probabilities.pre_flight_pass=0.95
```

## Layout

```
skydock/
├── default_config.yaml      # all tunable parameters with comments
├── run.py                   # CLI entry
└── skydock/
    ├── config.py            # YAML + CLI override loader
    ├── world.py             # operating corridor geometry
    ├── vehicle.py           # host vehicle (route follower)
    ├── drone.py             # drone physical state
    ├── triggers.py          # Poisson + waypoint + hard-brake triggers (spec 1.3)
    ├── conditions.py        # diurnal wind + weather + daylight
    ├── mission.py           # mission state machine (spec 1.1)
    ├── pipeline.py          # cloud upload/process/quality (spec 9.2)
    ├── economics.py         # revenue + costs (spec 9.3)
    ├── metrics.py           # rolling KPI aggregation
    ├── simulation.py        # orchestrator
    ├── animation.py         # matplotlib live view
    └── report.py            # end-of-run text report
```

## Configuration

All parameters live in `default_config.yaml`. The file's comments cite
the spec section each parameter feeds. Override individual values with
`--set section.key=value` (repeatable) without editing the YAML.

Key knobs worth sweeping for the v0 sim:

| Parameter | Effect |
|---|---|
| `trigger.poisson_rate_per_hour` | Mission attempt frequency |
| `probabilities.pre_flight_pass` | Operational reliability |
| `conditions.wind_mph_amplitude` | Afternoon abort-by-wind risk |
| `mission.capture_seconds_min/max` | Capture duration spread |
| `pipeline.quality_mean/std` | Customer-deliverable rate |
| `economics.price_per_scenario_usd` | Revenue per delivered scenario |
| `host_vehicles.count` | (v0 supports 1; multi-vehicle planned) |

## Spec mapping

| Spec section | Module |
|---|---|
| 1.1 Mission profile | `skydock/mission.py` |
| 1.2 Operational envelope | `skydock/conditions.py`, `skydock/simulation.py` (envelope gate) |
| 1.3 Trigger types | `skydock/triggers.py` |
| 1.4 Mission abort conditions | `skydock/mission.py::_pass_pre_flight` |
| 3.5 Scene taxonomy | `skydock/world.py::WAYPOINT_LABELS` |
| 4.3 Unit economics | `skydock/economics.py` |
| 6.1 Technical metrics | `skydock/metrics.py` |
| 9.1 Operations sim hooks | `skydock/simulation.py`, `skydock/mission.py` |
| 9.2 Pipeline sim hooks | `skydock/pipeline.py` |
| 9.3 Economics sim hooks | `skydock/economics.py` |
| 9.4 Full-system sim | `skydock/simulation.py` (wires the three together) |

## What v0 deliberately doesn't model yet

- Multiple host vehicles operating concurrently
- Moving-vehicle launch/recovery (V2 envelope)
- ML-based scene anomaly trigger
- BVLOS / regulatory waiver gating
- Customer-pipeline / acquisition funnel (spec 9.3 sub-loop)
- Realistic drone flight dynamics (it's a state-machine, not a quadrotor sim)

These are the obvious next iterations once v0 surfaces real questions.

## License

TBD.
