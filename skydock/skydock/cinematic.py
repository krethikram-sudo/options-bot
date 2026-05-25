"""Cinematic rendering mode — follow-camera, tilted isometric view focused on
the launch→fly→land sequence.

A complement to animation.py: where animation.py is the analytical dashboard
(useful for inspecting state and economics), this module renders a polished,
video-like clip suitable for embedding on a landing page. One vehicle's
mission cycle becomes the focal point; altitude is rendered as a vertical
screen offset against an isometric ground plane.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, FancyBboxPatch, Polygon

if TYPE_CHECKING:
    from .simulation import Simulation, VehicleUnit


# Visual constants tuned to match the website palette.
BG_COLOR = "#0a0e1a"
GROUND_COLOR = "#111827"
ROAD_COLOR = "#1f2937"
LANE_COLOR = "#374151"
ACCENT = "#60a5fa"     # vehicles
DRONE_COLOR = "#f5a524"
FOV_COLOR = "#f5a524"
TEXT_COLOR = "#e5e7eb"
TEXT_DIM = "#9ca3af"
SHADOW = (0.0, 0.0, 0.0, 0.35)

# Isometric tilt — y axis is compressed, altitude becomes vertical offset.
TILT_Y_SCALE = 0.62
ALT_TO_SCREEN = 1.6    # 1 m altitude → 1.6 m visual offset on the y axis

STAGE_LABEL = {
    "PRE_FLIGHT": "PRE-FLIGHT",
    "LAUNCHING": "LAUNCH",
    "CLIMBING": "CLIMB",
    "CAPTURING": "CAPTURE",
    "RETURNING": "RETURN",
    "LANDING": "LAND",
}
STAGE_COLOR = {
    "PRE_FLIGHT": "#9ca3af",
    "LAUNCHING": "#f5a524",
    "CLIMBING": "#f5a524",
    "CAPTURING": "#9ee37d",
    "RETURNING": "#7ab0d4",
    "LANDING": "#7ab0d4",
}


def _project_y(world_y: float, altitude_m: float = 0.0) -> float:
    """World y + altitude → screen y under the isometric tilt."""
    return world_y * TILT_Y_SCALE + altitude_m * ALT_TO_SCREEN


def _car_polygon(cx: float, cy: float, heading_rad: float,
                 length_m: float = 18.0, width_m: float = 8.0):
    """Return (chassis_xy, cabin_xy, windshield_xy) polygon vertices in world
    coords, oriented by heading. Sizes are exaggerated vs reality so the car
    reads at corridor scale."""
    cos_h, sin_h = math.cos(heading_rad), math.sin(heading_rad)
    # Chassis: rectangle, long axis = heading
    chassis = [
        (-length_m / 2, -width_m / 2),
        (length_m / 2, -width_m / 2),
        (length_m / 2, width_m / 2),
        (-length_m / 2, width_m / 2),
    ]
    # Cabin: smaller rectangle, offset slightly toward the back
    cabin = [
        (-length_m * 0.35, -width_m * 0.4),
        (length_m * 0.15, -width_m * 0.4),
        (length_m * 0.15, width_m * 0.4),
        (-length_m * 0.35, width_m * 0.4),
    ]
    # Windshield: trapezoid at the front of the cabin
    windshield = [
        (length_m * 0.05, -width_m * 0.35),
        (length_m * 0.18, -width_m * 0.28),
        (length_m * 0.18, width_m * 0.28),
        (length_m * 0.05, width_m * 0.35),
    ]

    def transform(pts):
        out = []
        for px, py in pts:
            x = px * cos_h - py * sin_h + cx
            y = px * sin_h + py * cos_h + cy
            out.append((x, _project_y(y, 0.0)))
        return out

    return transform(chassis), transform(cabin), transform(windshield)


def _drone_shape(cx: float, cy: float, altitude_m: float, arm_m: float = 6.0):
    """Quadcopter as a body circle + 4 arms + 4 rotor circles. Returns
    a dict of (xy, radius) tuples ready for direct rendering."""
    sy = _project_y(cy, altitude_m)
    # Arms point in 4 diagonals
    rotor_offsets = [
        (arm_m, arm_m),
        (arm_m, -arm_m),
        (-arm_m, arm_m),
        (-arm_m, -arm_m),
    ]
    rotors = []
    arms = []
    for dx, dy in rotor_offsets:
        rx = cx + dx
        ry = sy + dy * TILT_Y_SCALE
        arms.append([(cx, sy), (rx, ry)])
        rotors.append(((rx, ry), arm_m * 0.55))
    body = ((cx, sy), arm_m * 0.5)
    return body, arms, rotors


class CinematicRenderer:
    def __init__(self, sim: "Simulation"):
        self.sim = sim
        self.cfg = sim.cfg

        # Camera state — interpolated frame-to-frame
        wcfg = self.cfg.world
        self.cam_x = wcfg.width_m * 0.5
        self.cam_y = wcfg.height_m * 0.5
        self.cam_extent = max(wcfg.width_m, wcfg.height_m) * 0.4

        # Mission counter for the on-screen overlay
        self.completed_count = 0
        self.last_completed_seen = 0

        self.fig, self.ax = self._build_figure()
        self._setup_static_layers()
        self._init_dynamic_layers()

    # -- figure setup --------------------------------------------------------

    def _build_figure(self):
        fig = plt.figure(figsize=(13, 7), facecolor=BG_COLOR)
        ax = fig.add_axes([0.0, 0.0, 1.0, 1.0])
        ax.set_facecolor(BG_COLOR)
        ax.set_xticks([])
        ax.set_yticks([])
        for spine in ax.spines.values():
            spine.set_visible(False)
        return fig, ax

    def _setup_static_layers(self):
        """Draw the ground + corridor once — they don't change."""
        sim = self.sim
        ax = self.ax

        # Ground plane shadow gradient — a single dark rect that covers the
        # extent of the world, slightly lighter than the page background.
        wcfg = self.cfg.world
        ax.add_patch(plt.Rectangle(
            (-wcfg.width_m * 0.2, _project_y(-wcfg.height_m * 0.2, 0.0)),
            wcfg.width_m * 1.4,
            _project_y(wcfg.height_m * 1.4, 0.0),
            facecolor=GROUND_COLOR, edgecolor="none", zorder=0,
        ))

        # Corridors: thick line for road + dashed centerline.
        for corridor in sim.corridors:
            wps = corridor.waypoints
            xs = [w.x for w in wps] + [wps[0].x]
            ys = [_project_y(w.y, 0.0) for w in wps] + [_project_y(wps[0].y, 0.0)]
            ax.plot(xs, ys, color=ROAD_COLOR, linewidth=22, alpha=1.0,
                    solid_capstyle="round", solid_joinstyle="round", zorder=1)
            ax.plot(xs, ys, color=LANE_COLOR, linewidth=1.5, alpha=0.7,
                    linestyle=(0, (6, 8)), zorder=2)
            for w in wps:
                ax.plot(w.x, _project_y(w.y, 0.0), "o",
                        color="#4b5563", markersize=4, alpha=0.6, zorder=2)

    def _init_dynamic_layers(self):
        """Per-vehicle and per-drone artists, kept across frames."""
        self.unit_artists = []
        for unit in self.sim.units:
            # Vehicle chassis polygons
            chassis = Polygon([(0, 0)], closed=True, facecolor=ACCENT,
                              edgecolor="#1e3a8a", linewidth=1.0, zorder=5)
            cabin = Polygon([(0, 0)], closed=True, facecolor="#1e3a8a",
                            edgecolor="none", zorder=6)
            windshield = Polygon([(0, 0)], closed=True, facecolor="#0a0e1a",
                                 edgecolor=ACCENT, linewidth=0.5, zorder=7)
            for p in (chassis, cabin, windshield):
                self.ax.add_patch(p)
            # Shadow under drone (ground projection)
            shadow = Polygon([(0, 0)], closed=True, facecolor=SHADOW,
                             edgecolor="none", zorder=3)
            self.ax.add_patch(shadow)
            # Drone body + rotors
            drone_body = Circle((0, 0), 0.0, facecolor=DRONE_COLOR,
                                edgecolor="#7c2d12", linewidth=0.8, zorder=10)
            self.ax.add_patch(drone_body)
            rotors = [Circle((0, 0), 0.0, facecolor=DRONE_COLOR,
                             edgecolor=DRONE_COLOR, alpha=0.85, zorder=10)
                      for _ in range(4)]
            for r in rotors:
                self.ax.add_patch(r)
            # Drone arms
            arms = [self.ax.plot([], [], "-", color="#7c2d12",
                                  linewidth=1.4, alpha=0.95, zorder=9)[0]
                    for _ in range(4)]
            # FOV cone — two side lines + ground circle (only visible during capture)
            fov_left = self.ax.plot([], [], "-", color=FOV_COLOR,
                                     linewidth=1.0, alpha=0.0, zorder=4)[0]
            fov_right = self.ax.plot([], [], "-", color=FOV_COLOR,
                                      linewidth=1.0, alpha=0.0, zorder=4)[0]
            # Projected ellipse on the ground (tilt squashes the y-axis), so
            # we render it as a Polygon rather than a true Circle.
            fov_circle = Polygon([(0, 0)], closed=True,
                                  facecolor=FOV_COLOR, edgecolor="none",
                                  alpha=0.0, zorder=3)
            self.ax.add_patch(fov_circle)
            # Altitude tether (faint dashed line from vehicle to drone)
            tether = self.ax.plot([], [], "--", color=DRONE_COLOR,
                                   linewidth=0.6, alpha=0.0, zorder=4)[0]
            # Scene agents — drawn on the ground during a capture so a viewer
            # can see WHAT the drone is recording: cars, pedestrians, cyclists.
            scene_vehicles = self.ax.scatter([], [], s=42, c="#7ab0d4",
                                              marker="s", alpha=0.0,
                                              edgecolors="none", zorder=4)
            scene_peds = self.ax.scatter([], [], s=22, c="#9ee37d",
                                          marker="o", alpha=0.0,
                                          edgecolors="none", zorder=4)
            scene_cyclists = self.ax.scatter([], [], s=28, c="#e5b85a",
                                              marker="^", alpha=0.0,
                                              edgecolors="none", zorder=4)
            # Bright halo over agents currently inside the drone's FOV.
            scene_visible = self.ax.scatter([], [], s=80, c="none",
                                             marker="o", alpha=0.0,
                                             edgecolors=DRONE_COLOR,
                                             linewidths=1.2, zorder=8)
            self.unit_artists.append({
                "chassis": chassis,
                "cabin": cabin,
                "windshield": windshield,
                "shadow": shadow,
                "drone_body": drone_body,
                "rotors": rotors,
                "arms": arms,
                "fov_left": fov_left,
                "fov_right": fov_right,
                "fov_circle": fov_circle,
                "tether": tether,
                "scene_vehicles": scene_vehicles,
                "scene_peds": scene_peds,
                "scene_cyclists": scene_cyclists,
                "scene_visible": scene_visible,
            })

        # On-screen overlays
        self.stage_label = self.ax.text(
            0.04, 0.92, "", transform=self.ax.transAxes,
            color=TEXT_DIM, fontsize=13, family="monospace",
            fontweight="bold", zorder=20,
        )
        self.alt_label = self.ax.text(
            0.04, 0.86, "", transform=self.ax.transAxes,
            color=TEXT_DIM, fontsize=10, family="monospace", zorder=20,
        )
        self.brand_label = self.ax.text(
            0.04, 0.05, "skydock", transform=self.ax.transAxes,
            color=ACCENT, fontsize=14, family="monospace",
            fontweight="bold", zorder=20,
        )
        self.subtitle = self.ax.text(
            0.04, 0.02, "vehicle-deployed drone mission cycle",
            transform=self.ax.transAxes,
            color=TEXT_DIM, fontsize=9, family="monospace", zorder=20,
        )
        self.counter_label = self.ax.text(
            0.96, 0.92, "", transform=self.ax.transAxes,
            color=TEXT_DIM, fontsize=11, family="monospace",
            ha="right", zorder=20,
        )
        # Trigger info — appears top-right under the counter when a mission starts.
        self.trigger_label = self.ax.text(
            0.96, 0.86, "", transform=self.ax.transAxes,
            color=TEXT_DIM, fontsize=10, family="monospace",
            ha="right", zorder=20,
        )
        self.clock_label = self.ax.text(
            0.96, 0.05, "", transform=self.ax.transAxes,
            color=TEXT_DIM, fontsize=10, family="monospace",
            ha="right", zorder=20,
        )
        # Scenario label + agent counts — left side, below alt/batt, only
        # visible during capture.
        self.scenario_label = self.ax.text(
            0.04, 0.80, "", transform=self.ax.transAxes,
            color=TEXT_DIM, fontsize=11, family="monospace",
            zorder=20,
        )
        self.capture_stats = self.ax.text(
            0.04, 0.75, "", transform=self.ax.transAxes,
            color=TEXT_DIM, fontsize=10, family="monospace",
            zorder=20,
        )
        # Deliverable popup — center, fades in for ~3 sec after a mission
        # completes successfully.
        self.deliverable_popup = self.ax.text(
            0.5, 0.50, "", transform=self.ax.transAxes,
            color="#9ee37d", fontsize=15, family="monospace",
            fontweight="bold", ha="center", va="center",
            zorder=21,
            bbox=dict(facecolor="#0a0e1a", edgecolor="#9ee37d",
                      linewidth=1.5, boxstyle="round,pad=0.6",
                      alpha=0.95),
        )
        self.deliverable_popup.set_visible(False)
        self._popup_t_remaining = 0.0
        # Legend in the bottom-right corner so viewers know what the colored
        # ground markers mean during capture.
        self.legend_label = self.ax.text(
            0.96, 0.10, "■ vehicle    ● pedestrian    ▲ cyclist",
            transform=self.ax.transAxes,
            color=TEXT_DIM, fontsize=9, family="monospace",
            ha="right", zorder=20, alpha=0.0,
        )
        # Running event log — right side, mid-height. Anchored to the
        # *figure* (not the axes) so the camera pan/zoom can't displace it.
        # Backed by a translucent panel so it stays readable over any
        # content underneath.
        self.log_header = self.fig.text(
            0.96, 0.78, "event log", color=ACCENT,
            fontsize=10, family="monospace",
            ha="right", va="top", fontweight="bold", zorder=30,
        )
        self.log_body = self.fig.text(
            0.96, 0.745, "", color=TEXT_COLOR,
            fontsize=9, family="monospace",
            ha="right", va="top", zorder=30,
            linespacing=1.5,
            bbox=dict(facecolor="#0a0e1a", edgecolor="#1f2937",
                      linewidth=0.8, boxstyle="round,pad=0.6",
                      alpha=0.92),
        )
        self._event_log: list[str] = []
        self._max_log_lines = 8
        # Tracking state for event detection (each frame, diff against prior).
        self._prev_missions_started = 0
        self._prev_completed_count = 0
        self._prev_pipeline_completed = 0
        self._prev_mission_stages: dict[str, str] = {}

        # Track most-recent completed mission for the deliverable popup.
        self._last_completed_count = 0
        self._last_popup_text = ""

    # -- per-frame update ----------------------------------------------------

    def _focal_unit(self) -> "VehicleUnit":
        """Pick the unit to focus the camera on this frame. Prefer the one
        with an active mission; if none, fall back to the first unit."""
        for u in self.sim.units:
            if u.active_mission is not None and u.active_mission.is_active:
                return u
        return self.sim.units[0]

    def _update_camera(self, focal: "VehicleUnit"):
        """Smoothly lerp camera toward the focal unit."""
        if focal.active_mission is not None and focal.drone.is_airborne:
            target_cx = (focal.vehicle.x + focal.drone.x) / 2
            target_cy = (focal.vehicle.y + focal.drone.y) / 2
            # Tighter framing during action — extent shrinks when there's a mission
            target_extent = 320.0 + focal.drone.altitude_m * 2.0
        else:
            target_cx = focal.vehicle.x
            target_cy = focal.vehicle.y
            target_extent = 380.0
        lerp = 0.08
        self.cam_x += (target_cx - self.cam_x) * lerp
        self.cam_y += (target_cy - self.cam_y) * lerp
        self.cam_extent += (target_extent - self.cam_extent) * lerp
        # Apply view limits — use _project_y for the y axis
        half = self.cam_extent
        self.ax.set_xlim(self.cam_x - half, self.cam_x + half)
        # Y extent needs to accommodate both ground projection and altitude.
        # Bias upward so altitude has room.
        y_center = _project_y(self.cam_y, 30.0)  # bias up by ~30m altitude
        y_half = half * 0.55
        self.ax.set_ylim(y_center - y_half, y_center + y_half)

    def _update_vehicle(self, art: dict, unit: "VehicleUnit"):
        v = unit.vehicle
        chassis, cabin, windshield = _car_polygon(
            v.x, v.y, v.heading_rad,
            length_m=22.0, width_m=10.0,
        )
        art["chassis"].set_xy(chassis)
        art["cabin"].set_xy(cabin)
        art["windshield"].set_xy(windshield)

    def _update_drone(self, art: dict, unit: "VehicleUnit", t_s: float):
        d = unit.drone
        v = unit.vehicle
        airborne = d.is_airborne
        alt = max(0.0, d.altitude_m)

        # When DOCKED, sit the drone on top of the vehicle (small visible perch)
        if not airborne:
            body_x = v.x
            body_y_world = v.y
            body_alt = 4.0  # perched on top of dock
            arm_size = 4.0
        else:
            body_x = d.x
            body_y_world = d.y
            body_alt = alt
            arm_size = 6.0

        body, arms, rotors = _drone_shape(body_x, body_y_world, body_alt,
                                           arm_m=arm_size)
        art["drone_body"].set_center(body[0])
        art["drone_body"].set_radius(body[1])

        # Rotor "spin" effect: alternate frame-to-frame rotor radius
        spin_factor = 0.8 + 0.5 * abs(math.sin(t_s * 8.0))
        for arm_line, arm_pts in zip(art["arms"], arms):
            xs = [p[0] for p in arm_pts]
            ys = [p[1] for p in arm_pts]
            arm_line.set_data(xs, ys)
        for rotor_patch, (center, radius) in zip(art["rotors"], rotors):
            rotor_patch.set_center(center)
            rotor_patch.set_radius(radius * spin_factor if airborne else radius * 0.6)
            rotor_patch.set_alpha(0.95 if airborne else 0.6)

        # Shadow on ground beneath drone — only when airborne
        if airborne and alt > 1.0:
            # Shadow grows softer + larger with altitude
            shadow_r = 6.0 + alt * 0.08
            shadow_alpha = max(0.08, 0.35 - alt * 0.0025)
            # Approximate ellipse with a polygon (matplotlib Polygon doesn't auto-ellipse)
            shadow_pts = []
            n = 16
            for i in range(n):
                theta = 2 * math.pi * i / n
                sx = body_x + shadow_r * math.cos(theta)
                sy = body_y_world + shadow_r * 0.5 * math.sin(theta)
                shadow_pts.append((sx, _project_y(sy, 0.0)))
            art["shadow"].set_xy(shadow_pts)
            art["shadow"].set_alpha(shadow_alpha)
        else:
            art["shadow"].set_alpha(0.0)

        # Tether dashed line vehicle → drone (only when airborne, faint)
        if airborne:
            tx = [v.x, body_x]
            ty = [_project_y(v.y, 0.0), _project_y(body_y_world, body_alt)]
            art["tether"].set_data(tx, ty)
            art["tether"].set_alpha(0.25)
        else:
            art["tether"].set_alpha(0.0)

        # FOV cone — visible during capture
        capturing = (unit.active_mission is not None
                     and unit.active_mission.is_capturing)
        if capturing and alt > 5.0:
            r = d.coverage_radius_m
            # Two side lines from drone body down to ground circle edges
            screen_drone_y = _project_y(body_y_world, body_alt)
            screen_ground_y = _project_y(body_y_world, 0.0)
            art["fov_left"].set_data([body_x - r, body_x],
                                      [screen_ground_y, screen_drone_y])
            art["fov_right"].set_data([body_x + r, body_x],
                                       [screen_ground_y, screen_drone_y])
            art["fov_left"].set_alpha(0.55)
            art["fov_right"].set_alpha(0.55)
            # Ground circle (rendered as projected ellipse via polygon)
            n = 32
            circle_pts = []
            for i in range(n):
                theta = 2 * math.pi * i / n
                cx_pt = body_x + r * math.cos(theta)
                cy_pt = body_y_world + r * math.sin(theta)
                circle_pts.append((cx_pt, _project_y(cy_pt, 0.0)))
            art["fov_circle"].set_xy(circle_pts)
            art["fov_circle"].set_alpha(0.20)
        else:
            art["fov_left"].set_alpha(0.0)
            art["fov_right"].set_alpha(0.0)
            art["fov_circle"].set_alpha(0.0)

    def _render_scene_agents(self, art: dict, unit: "VehicleUnit", t_s: float):
        """During capture, plot the agents in the scene as ground markers so
        viewers can see WHAT is being captured. Outside capture, hide them."""
        scene = unit.active_scene
        capturing = (unit.active_mission is not None
                     and unit.active_mission.is_capturing
                     and scene is not None)
        if not capturing:
            for k in ("scene_vehicles", "scene_peds", "scene_cyclists",
                     "scene_visible"):
                art[k].set_offsets([[float("nan"), float("nan")]])
                art[k].set_alpha(0.0)
            return

        # Agents in FOV right now (per the last recorded capture frame).
        in_fov: set[str] = set()
        if unit.capture_frame_idx > 0:
            last_frame = unit.capture_frame_idx - 1
            for aid, frames in scene.visibility.items():
                if last_frame in frames:
                    in_fov.add(aid)

        positions = scene.positions_now(t_s)
        veh_xy, ped_xy, cyc_xy, vis_xy = [], [], [], []
        for aid, cls, x, y in positions:
            sy = _project_y(y, 0.0)
            if cls == "passenger_vehicle":
                veh_xy.append((x, sy))
            elif cls == "pedestrian":
                ped_xy.append((x, sy))
            else:
                cyc_xy.append((x, sy))
            if aid in in_fov:
                vis_xy.append((x, sy))

        for key, xys, alpha in (
            ("scene_vehicles", veh_xy, 0.95),
            ("scene_peds", ped_xy, 0.85),
            ("scene_cyclists", cyc_xy, 0.90),
            ("scene_visible", vis_xy, 0.85),
        ):
            if xys:
                art[key].set_offsets(xys)
                art[key].set_alpha(alpha)
            else:
                art[key].set_offsets([[float("nan"), float("nan")]])
                art[key].set_alpha(0.0)

    def _check_for_deliverable(self, t_s: float, frame_dt: float):
        """If a mission just completed (DONE or ABORTED), set up the popup."""
        completed = self.sim.completed_missions
        if len(completed) > self._last_completed_count:
            # One or more missions completed since last frame.
            newest = completed[-1]
            if newest.stage == "DONE":
                q = newest.quality_score_from_scene or 0.0
                short_id = newest.mission_id.replace("skydock-mission-", "")
                self._last_popup_text = (
                    f"✓ DELIVERED  scenario_{short_id}.xosc\n"
                    f"   quality {q:.0f}  ·  {newest.scene_class.replace('_',' ')}"
                )
                self.deliverable_popup.set_color("#9ee37d")
                # Update bbox edge color too.
                bbox = self.deliverable_popup.get_bbox_patch()
                if bbox is not None:
                    bbox.set_edgecolor("#9ee37d")
                self._popup_t_remaining = 3.0
            elif newest.stage == "ABORTED":
                reason = (newest.aborted_reason or "unknown").replace("_", " ")
                self._last_popup_text = f"✗ ABORTED  {reason}"
                self.deliverable_popup.set_color("#d97757")
                bbox = self.deliverable_popup.get_bbox_patch()
                if bbox is not None:
                    bbox.set_edgecolor("#d97757")
                self._popup_t_remaining = 2.0
            self._last_completed_count = len(completed)

        # Fade the popup out as its timer runs.
        if self._popup_t_remaining > 0:
            self.deliverable_popup.set_visible(True)
            self.deliverable_popup.set_text(self._last_popup_text)
            # Use real-time-ish fade — frame_dt is sim seconds per frame, but
            # the popup feels right keyed to frame count.
            self._popup_t_remaining -= frame_dt / max(1.0,
                self.cfg.animation.speed_multiplier / self.cfg.animation.fps)
        else:
            self.deliverable_popup.set_visible(False)

    def _format_log_time(self, t_s: float) -> str:
        hrs = int(t_s // 3600)
        mins = int((t_s % 3600) // 60)
        secs = int(t_s % 60)
        return f"{hrs:02d}:{mins:02d}:{secs:02d}"

    def _push_log(self, t_s: float, kind: str, detail: str):
        """Append an event line to the log; keep only the last N visible."""
        ts = self._format_log_time(t_s)
        line = f"[{ts}]  {kind:<10s} {detail}"
        self._event_log.append(line)
        if len(self._event_log) > self._max_log_lines:
            self._event_log = self._event_log[-self._max_log_lines:]

    def _emit_events(self, t_s: float):
        """Detect state transitions vs last frame, log them."""
        sim = self.sim

        # New triggers — mission started count grew.
        n_started = sim.metrics.missions_started
        if n_started > self._prev_missions_started:
            new_missions = n_started - self._prev_missions_started
            for u in sim.units:
                m = u.active_mission
                if m is not None and m.is_active:
                    # Only log if we haven't logged this one before — track by
                    # mission_id in _prev_mission_stages.
                    if m.mission_id not in self._prev_mission_stages:
                        self._push_log(
                            t_s, "TRIGGER",
                            f"{m.trigger.type}·{m.scene_class.replace('_','-')}",
                        )
                        self._prev_mission_stages[m.mission_id] = m.stage
            self._prev_missions_started = n_started

        # Stage transitions on active missions — log when entering CAPTURING.
        for u in sim.units:
            m = u.active_mission
            if m is None or not m.is_active:
                continue
            prev = self._prev_mission_stages.get(m.mission_id, "")
            if prev != m.stage:
                if m.stage == "CAPTURING":
                    n_agents = len(u.active_scene.agents) if u.active_scene else 0
                    self._push_log(
                        t_s, "CAPTURE",
                        f"{n_agents:>2d} agents · {m.scene_class.replace('_','-')}",
                    )
                self._prev_mission_stages[m.mission_id] = m.stage

        # Mission completions — DONE or ABORTED.
        completed = sim.completed_missions
        if len(completed) > self._prev_completed_count:
            for new in completed[self._prev_completed_count:]:
                short_id = new.mission_id.replace("skydock-mission-", "")
                if new.stage == "DONE":
                    q = new.quality_score_from_scene or 0.0
                    self._push_log(
                        t_s, "✓ CAPTURED",
                        f"scenario_{short_id}  q={q:.0f}",
                    )
                elif new.stage == "ABORTED":
                    reason = (new.aborted_reason or "unknown").replace("_", " ")
                    self._push_log(t_s, "✗ ABORTED", reason)
            self._prev_completed_count = len(completed)

        # Pipeline deliveries — when a scenario finishes processing.
        n_pipeline_done = len(sim.pipeline.completed)
        if n_pipeline_done > self._prev_pipeline_completed:
            for job in sim.pipeline.completed[self._prev_pipeline_completed:]:
                short_id = job.mission.mission_id.replace("skydock-mission-", "")
                if job.delivered:
                    self._push_log(
                        t_s, "→ DELIVERED",
                        f"scenario_{short_id}.xosc",
                    )
                else:
                    self._push_log(
                        t_s, "  rejected",
                        f"scenario_{short_id} (low quality)",
                    )
            self._prev_pipeline_completed = n_pipeline_done

        # Render the current log into the body text artist. Newest at the
        # bottom (matches a terminal scroll), padded to keep right-alignment.
        self.log_body.set_text("\n".join(self._event_log))

    def _update_overlays(self, focal: "VehicleUnit", t_s: float):
        m = focal.active_mission
        if m is not None and m.is_active:
            label = STAGE_LABEL.get(m.stage, m.stage)
            color = STAGE_COLOR.get(m.stage, TEXT_DIM)
            self.stage_label.set_text(f"▲ {label}")
            self.stage_label.set_color(color)
            alt_str = f"alt {focal.drone.altitude_m:5.1f} m  ·  batt {focal.drone.battery_pct:4.1f}%"
            self.alt_label.set_text(alt_str)
            self.alt_label.set_color(TEXT_COLOR)

            # Trigger info — what made the drone launch?
            trig = m.trigger
            self.trigger_label.set_text(
                f"trigger · {trig.type}  @  {m.scene_class.replace('_',' ')}"
            )
            self.trigger_label.set_color(TEXT_DIM)
        else:
            self.stage_label.set_text("◇ STANDBY")
            self.stage_label.set_color(TEXT_DIM)
            self.alt_label.set_text("awaiting trigger")
            self.alt_label.set_color(TEXT_DIM)
            self.trigger_label.set_text("")

        # Scenario + capture stats — only visible during CAPTURE.
        scene = focal.active_scene
        capturing = (m is not None and m.is_capturing and scene is not None)
        if capturing:
            self.scenario_label.set_text(
                f"scenario · {scene.scene_class.replace('_',' ')}"
            )
            self.scenario_label.set_color(STAGE_COLOR["CAPTURING"])
            # Live agent counts.
            n_veh = sum(1 for a in scene.agents if a.cls == "passenger_vehicle")
            n_ped = sum(1 for a in scene.agents if a.cls == "pedestrian")
            n_cyc = sum(1 for a in scene.agents if a.cls == "cyclist")
            n_in_fov = 0
            if focal.capture_frame_idx > 0:
                last_frame = focal.capture_frame_idx - 1
                for aid, frames in scene.visibility.items():
                    if last_frame in frames:
                        n_in_fov += 1
            n_total = len(scene.agents)
            self.capture_stats.set_text(
                f"tracking {n_in_fov:>2d}/{n_total:>2d} agents  ·  "
                f"{n_veh} veh · {n_ped} ped · {n_cyc} cyc"
            )
            self.capture_stats.set_color(TEXT_COLOR)
            self.legend_label.set_alpha(0.9)
        else:
            self.scenario_label.set_text("")
            self.capture_stats.set_text("")
            self.legend_label.set_alpha(0.0)

        delivered = sum(1 for j in self.sim.pipeline.completed if j.delivered)
        self.counter_label.set_text(
            f"missions {self.sim.metrics.missions_succeeded} ok / "
            f"{self.sim.metrics.missions_started} total  ·  "
            f"delivered {delivered}"
        )
        hrs = int(t_s // 3600)
        mins = int((t_s % 3600) // 60)
        secs = int(t_s % 60)
        self.clock_label.set_text(f"t+{hrs:02d}:{mins:02d}:{secs:02d}")

    def update(self, frame_idx: int):
        sim = self.sim
        cfg = sim.cfg
        sim_dt_per_frame = cfg.animation.speed_multiplier / cfg.animation.fps
        target_t = sim.t_s + sim_dt_per_frame
        while sim.t_s < target_t and sim.t_s < sim.duration_s:
            sim.step()

        focal = self._focal_unit()
        self._update_camera(focal)
        for art, unit in zip(self.unit_artists, sim.units):
            self._update_vehicle(art, unit)
            self._update_drone(art, unit, sim.t_s)
            self._render_scene_agents(art, unit, sim.t_s)
        self._emit_events(sim.t_s)
        self._update_overlays(focal, sim.t_s)
        self._check_for_deliverable(sim.t_s, sim_dt_per_frame)
        return []


def run_cinematic(sim: "Simulation", save_path: str | None = None) -> None:
    cfg = sim.cfg
    fps = cfg.animation.fps
    speedup = cfg.animation.speed_multiplier
    sim_dt_per_frame = speedup / fps
    total_frames = int((cfg.simulation.duration_hours * 3600.0) / sim_dt_per_frame)

    renderer = CinematicRenderer(sim)
    anim = FuncAnimation(
        renderer.fig,
        renderer.update,
        frames=total_frames,
        interval=1000.0 / fps,
        blit=False,
        repeat=False,
    )

    if save_path:
        anim.save(save_path, fps=fps, dpi=90)
        print(f"saved cinematic animation to {save_path}")
    else:
        plt.show()
