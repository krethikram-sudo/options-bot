"""Regression + property tests for the physical layer.

Intended for a drone/AV engineer reading the repo who wants to verify
the sim's mechanics are sound. Each test asserts a quantitative property
that would be obvious-to-an-engineer; failures indicate a real model bug.

Run with:
    python -m unittest tests.test_physical_layer -v
"""
from __future__ import annotations

import math
import random
import unittest

from skydock.config import Config
from skydock.dock import DockConfig, latch_success_probability
from skydock.physics import FlightDynamics
from skydock.scene import (
    SceneGenerator, TrafficScene,
    agents_in_footprint, fov_footprint_radius_m,
)
from skydock.simulation import Simulation


class FlightDynamicsTests(unittest.TestCase):
    """Verify drone physics behaves like a physical body."""

    def test_drone_climbs_to_target_altitude(self):
        body = FlightDynamics()
        body.target_x = body.target_y = 0.0
        body.target_z = 80.0
        for _ in range(40):    # 40s
            body.step(dt=1.0, wind_mph=0.0, wind_dir_rad=0.0)
        # Should be near target altitude, with small residual velocity.
        self.assertGreater(body.z, 78.0)
        self.assertLess(body.z, 82.0)
        self.assertLess(abs(body.vz), 1.0)

    def test_max_climb_rate_bounded(self):
        body = FlightDynamics()
        body.target_z = 1000.0   # far above max
        # Step once.
        body.step(dt=1.0, wind_mph=0.0, wind_dir_rad=0.0)
        # vz should be at most max_vertical_speed_mps.
        self.assertLessEqual(body.vz, body.max_vertical_speed_mps + 0.01)

    def test_wind_pushes_drone_horizontally(self):
        body = FlightDynamics()
        body.snap_to(0.0, 0.0, 80.0)
        body.target_x = body.target_y = 0.0
        body.target_z = 80.0
        # 20 mph due east.
        for _ in range(15):
            body.step(dt=1.0, wind_mph=20.0, wind_dir_rad=0.0)
        # Drone should have drifted east (positive x).
        self.assertGreater(body.x, 0.5,
            f"expected east drift, got x={body.x:.2f}")

    def test_precision_landing_below_10m(self):
        """Below 10m AGL, controller gain doubles and wind coupling halves."""
        wind_body = FlightDynamics()
        wind_body.snap_to(0.0, 0.0, 80.0)
        wind_body.target_x = wind_body.target_y = 0.0
        wind_body.target_z = 80.0
        # First, drift at high altitude in 15mph wind.
        for _ in range(10):
            wind_body.step(dt=1.0, wind_mph=15.0, wind_dir_rad=0.0)
        high_alt_drift = abs(wind_body.x)

        # Now same wind at low altitude.
        low_body = FlightDynamics()
        low_body.snap_to(0.0, 0.0, 5.0)
        low_body.target_x = low_body.target_y = 0.0
        low_body.target_z = 5.0
        for _ in range(10):
            low_body.step(dt=1.0, wind_mph=15.0, wind_dir_rad=0.0)
        low_alt_drift = abs(low_body.x)

        self.assertLess(low_alt_drift, high_alt_drift,
            "Precision-mode (z<10m) should reduce wind drift vs cruise mode")

    def test_thrust_effort_is_higher_when_climbing(self):
        hover = FlightDynamics()
        hover.snap_to(0.0, 0.0, 80.0)
        climbing = FlightDynamics()
        climbing.snap_to(0.0, 0.0, 0.0)
        climbing.target_z = 80.0
        climbing.step(dt=1.0, wind_mph=0.0, wind_dir_rad=0.0)
        self.assertGreater(climbing.thrust_effort_fraction(),
                            hover.thrust_effort_fraction(),
                            "Active climb should require more thrust than hover")


class DockLatchTests(unittest.TestCase):
    """The dock latch model should reward good geometry and punish bad."""

    def setUp(self):
        self.cfg = DockConfig()

    def test_perfect_landing_high_probability(self):
        p = latch_success_probability(
            self.cfg,
            drone_x=100.0, drone_y=100.0, drone_vz=-0.3,
            dock_x=100.0, dock_y=100.0,
            vehicle_speed_mph=0.0, wind_mph=4.0,
            base_recovery_prob=0.99,
        )
        self.assertGreater(p, 0.95,
            f"on-target gentle landing should be ≥95% latch, got {p:.2%}")

    def test_misalignment_reduces_probability(self):
        on_target = latch_success_probability(
            self.cfg, drone_x=0.0, drone_y=0.0, drone_vz=-0.5,
            dock_x=0.0, dock_y=0.0,
            vehicle_speed_mph=0.0, wind_mph=4.0, base_recovery_prob=0.99,
        )
        off_target = latch_success_probability(
            self.cfg, drone_x=3.0, drone_y=0.0, drone_vz=-0.5,
            dock_x=0.0, dock_y=0.0,
            vehicle_speed_mph=0.0, wind_mph=4.0, base_recovery_prob=0.99,
        )
        self.assertLess(off_target, on_target,
            "3m misalignment should reduce latch probability")

    def test_vehicle_motion_violates_envelope(self):
        moving = latch_success_probability(
            self.cfg, drone_x=0.0, drone_y=0.0, drone_vz=-0.3,
            dock_x=0.0, dock_y=0.0,
            vehicle_speed_mph=12.0,    # well over §1.2 V1 5mph limit
            wind_mph=4.0, base_recovery_prob=0.99,
        )
        self.assertLess(moving, 0.6,
            "Vehicle moving > 5mph during landing should drop latch P below 60%")

    def test_extreme_misalignment_definite_miss(self):
        p = latch_success_probability(
            self.cfg, drone_x=20.0, drone_y=0.0, drone_vz=-0.3,
            dock_x=0.0, dock_y=0.0,
            vehicle_speed_mph=0.0, wind_mph=4.0, base_recovery_prob=0.99,
        )
        self.assertEqual(p, 0.0,
            "Drone 20m off-target should have zero latch probability")


class FOVTests(unittest.TestCase):
    """Camera footprint and agent-in-footprint computation."""

    def test_footprint_scales_with_altitude(self):
        f50 = fov_footprint_radius_m(50.0, fov_diag_deg=80.0)
        f100 = fov_footprint_radius_m(100.0, fov_diag_deg=80.0)
        # Should approximately double.
        self.assertAlmostEqual(f100 / f50, 2.0, places=2,
            msg="Footprint radius should scale linearly with altitude")

    def test_agents_inside_footprint_detected(self):
        # 1 agent at origin, 1 agent 50m east, 1 agent 200m east.
        positions = [
            ("a1", "passenger_vehicle", 0.0, 0.0),
            ("a2", "pedestrian", 50.0, 0.0),
            ("a3", "cyclist", 200.0, 0.0),
        ]
        # Drone at origin, altitude 80m → footprint radius ~67m.
        visible = agents_in_footprint(
            drone_x=0.0, drone_y=0.0,
            footprint_radius_m=fov_footprint_radius_m(80.0),
            agents_positions=positions,
        )
        self.assertIn("a1", visible)
        self.assertIn("a2", visible)
        self.assertNotIn("a3", visible,
            "Agent 200m away should not be inside a 67m footprint")


class SceneTests(unittest.TestCase):
    """Traffic scene generation + traffic light + culling."""

    def test_traffic_light_stops_vehicle_at_red(self):
        gen = SceneGenerator(random.Random(1), area_radius_m=90.0)
        scene = gen.generate("intersection_signalized", 0.0, 0.0, t_s=0.0)
        # Pick a vehicle and confirm it hits the stop line during red phase.
        veh = next(a for a in scene.agents if a.cls == "passenger_vehicle"
                   and abs(math.cos(a.heading_rad)) > 0.9   # E-W traveller
                   and math.cos(a.heading_rad) > 0          # east-bound
                   and a.x0 < -10.0)
        # During EW-red half (second half of cycle), east-bound shouldn't cross stop line.
        red_t = scene.cycle_period_s * 0.75   # firmly in NS-green / EW-red phase
        positions = scene.positions_now(red_t)
        for aid, cls, x, y in positions:
            if aid == veh.agent_id:
                self.assertLessEqual(x, -scene._STOP_LINE_M + 0.5,
                    f"East-bound vehicle should be stopped at red, got x={x:.1f}")
                return
        self.fail(f"Could not find vehicle {veh.agent_id} in positions")

    def test_traffic_light_lets_vehicle_through_on_green(self):
        gen = SceneGenerator(random.Random(1), area_radius_m=90.0)
        scene = gen.generate("intersection_signalized", 0.0, 0.0, t_s=0.0)
        veh = next(a for a in scene.agents if a.cls == "passenger_vehicle"
                   and abs(math.cos(a.heading_rad)) > 0.9
                   and math.cos(a.heading_rad) > 0
                   and a.x0 < -20.0)
        # Pass enough time at green that the vehicle should have crossed.
        green_t = scene.cycle_period_s * 0.20   # firmly in EW-green
        # Allow some travel time from initial position.
        positions = scene.positions_now(green_t)
        for aid, cls, x, y in positions:
            if aid == veh.agent_id:
                expected_x = veh.x0 + math.cos(veh.heading_rad) * veh.speed_mps * green_t
                # Should have advanced (not stopped).
                self.assertGreater(x, veh.x0,
                    "East-bound vehicle on green should have moved")

    def test_lane_offsets_realistic(self):
        gen = SceneGenerator(random.Random(2), area_radius_m=90.0)
        scene = gen.generate("intersection_signalized", 0.0, 0.0, t_s=0.0)
        # Vehicles travelling east-west should be off the centreline by ~3.5m.
        ew_vehicles = [a for a in scene.agents if a.cls == "passenger_vehicle"
                       and abs(math.cos(a.heading_rad)) > 0.9]
        for v in ew_vehicles:
            self.assertGreater(abs(v.y0), 2.0,
                f"E-W vehicle at y0={v.y0:.1f} should be in a lane (offset≥2m)")
            self.assertLess(abs(v.y0), 5.0,
                f"E-W vehicle at y0={v.y0:.1f} should be within a lane width")


class SimulationIntegrationTests(unittest.TestCase):
    """End-to-end smoke tests on a short sim."""

    def test_short_sim_produces_outputs(self):
        cfg = Config()
        cfg.simulation.duration_hours = 4.0
        cfg.simulation.seed = 7
        cfg.host_vehicles.count = 1
        sim = Simulation(cfg)
        sim.run_headless()
        # Should produce some missions in 4 operating hours.
        self.assertGreater(sim.metrics.missions_started, 0,
            "4-hour sim should trigger at least one mission")
        # No exceptions, mission state machine completes.
        for m in sim.completed_missions:
            self.assertIn(m.stage, ("DONE", "ABORTED"),
                f"Mission {m.mission_id} ended in unexpected state {m.stage}")

    def test_operating_seconds_tracked(self):
        cfg = Config()
        cfg.simulation.duration_hours = 11.0   # one full operating day
        cfg.simulation.seed = 7
        sim = Simulation(cfg)
        sim.run_headless()
        # Operating hours should be ≤ duration and > 0.
        op_h = sim.operating_seconds / 3600.0
        self.assertGreater(op_h, 9.0)
        self.assertLessEqual(op_h, 11.0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
