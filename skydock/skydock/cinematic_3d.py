"""Cinematic 3D rendering mode — true 3D scene with Axes3D plus a BEV
"footage" inset showing what the drone is actually capturing.

A successor to cinematic.py (which uses a pseudo-3D isometric projection):
this module renders the scene in real 3D space using matplotlib's
mpl_toolkits.mplot3d. Altitude is a real z-coordinate, the camera angle
is configurable, and the BEV inset gives the viewer a literal view of
the drone's captured footage.

Trade-off: matplotlib 3D is markedly slower than 2D. Plan for ~5-10x
render time vs cinematic.py. Use shorter sim windows accordingly.
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle as MplCircle, Polygon as MplPolygon
from mpl_toolkits.mplot3d.art3d import Poly3DCollection, Line3DCollection

if TYPE_CHECKING:
    from .simulation import Simulation, VehicleUnit


# Visual palette — shared with the 2D cinematic mode.
BG_COLOR = "#0a0e1a"
GROUND_COLOR = "#111827"
ROAD_COLOR = "#1f2937"
LANE_COLOR = "#374151"
ACCENT = "#60a5fa"
DRONE_COLOR = "#f5a524"
FOV_COLOR = "#f5a524"
TEXT_COLOR = "#e5e7eb"
TEXT_DIM = "#9ca3af"

# 3D drawing parameters.
VEHICLE_LENGTH_M = 22.0
VEHICLE_WIDTH_M = 10.0
VEHICLE_HEIGHT_M = 5.0
DRONE_ARM_M = 6.0

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


def _box_faces(cx: float, cy: float, cz: float,
               length: float, width: float, height: float,
               heading_rad: float = 0.0) -> list[list[tuple[float, float, float]]]:
    """Return the 6 face polygons of a rotated rectangular box centred at
    (cx, cy, cz) with the given dimensions and yaw heading."""
    cos_h = math.cos(heading_rad)
    sin_h = math.sin(heading_rad)
    hl, hw, hh = length / 2, width / 2, height / 2
    # 8 corners in local coords, then rotated.
    corners = []
    for dx, dy, dz in [
        (-hl, -hw, -hh), (hl, -hw, -hh), (hl, hw, -hh), (-hl, hw, -hh),
        (-hl, -hw, hh), (hl, -hw, hh), (hl, hw, hh), (-hl, hw, hh),
    ]:
        x = dx * cos_h - dy * sin_h + cx
        y = dx * sin_h + dy * cos_h + cy
        z = dz + cz
        corners.append((x, y, z))
    # 6 faces — bottom, top, front, back, left, right
    faces = [
        [corners[0], corners[1], corners[2], corners[3]],  # bottom
        [corners[4], corners[5], corners[6], corners[7]],  # top
        [corners[0], corners[1], corners[5], corners[4]],  # -y side
        [corners[2], corners[3], corners[7], corners[6]],  # +y side
        [corners[1], corners[2], corners[6], corners[5]],  # +x side (front)
        [corners[3], corners[0], corners[4], corners[7]],  # -x side (back)
    ]
    return faces


def _disc_polygon(cx: float, cy: float, cz: float, radius: float,
                  n_segs: int = 24) -> list[tuple[float, float, float]]:
    """Horizontal disc polygon (single face) for rotors and shadow."""
    pts = []
    for i in range(n_segs):
        theta = 2 * math.pi * i / n_segs
        pts.append((cx + radius * math.cos(theta),
                    cy + radius * math.sin(theta),
                    cz))
    return pts


class Cinematic3DRenderer:
    def __init__(self, sim: "Simulation"):
        self.sim = sim
        self.cfg = sim.cfg

        # Camera-follow state (data coords).
        wcfg = self.cfg.world
        self.cam_x = wcfg.width_m * 0.5
        self.cam_y = wcfg.height_m * 0.5
        self.cam_extent = 400.0
        # 3D view angle — azim slowly orbits for cinematic feel.
        self.view_elev = 28.0
        self.view_azim_base = -65.0
        self.view_azim_phase = 0.0

        self.fig = plt.figure(figsize=(13.5, 7.5), facecolor=BG_COLOR)
        self.ax3d = self.fig.add_axes([0.0, 0.0, 0.72, 1.0], projection="3d",
                                       facecolor=BG_COLOR)
        # BEV inset (the drone's "footage") in the top-right.
        self.ax_bev = self.fig.add_axes([0.74, 0.55, 0.24, 0.40],
                                          facecolor="#1c1f25")
        self.ax_bev.set_xticks([])
        self.ax_bev.set_yticks([])
        for sp in self.ax_bev.spines.values():
            sp.set_color(DRONE_COLOR)
            sp.set_linewidth(1.5)

        self._setup_3d_axes()
        self._draw_static_world()
        self._init_dynamic_artists()
        self._init_overlays()

        # Tracking state for event detection (each frame, diff against prior).
        self._prev_missions_started = 0
        self._prev_completed_count = 0
        self._prev_pipeline_completed = 0
        self._prev_mission_stages: dict[str, str] = {}
        self._event_log: list[str] = []
        self._max_log_lines = 8

        # Deliverable popup state
        self._popup_t_remaining = 0.0
        self._last_popup_text = ""

    # -- 3D axes config ------------------------------------------------------

    def _setup_3d_axes(self):
        ax = self.ax3d
        ax.set_facecolor(BG_COLOR)
        # Hide pane backgrounds / grid lines for a cleaner cinematic look.
        for axis in (ax.xaxis, ax.yaxis, ax.zaxis):
            axis.pane.set_facecolor(BG_COLOR)
            axis.pane.set_edgecolor(BG_COLOR)
            axis.set_pane_color((0.04, 0.06, 0.10, 1.0))
            for tick in axis.get_ticklines():
                tick.set_visible(False)
            for label in axis.get_ticklabels():
                label.set_visible(False)
        ax.grid(False)
        ax.set_xlabel("")
        ax.set_ylabel("")
        ax.set_zlabel("")
        ax.view_init(elev=self.view_elev, azim=self.view_azim_base)

    def _draw_static_world(self):
        """Ground plane + corridor segments — drawn once."""
        ax = self.ax3d
        wcfg = self.cfg.world
        # Large ground plane at z=0 covering well beyond the world bounds.
        margin = max(wcfg.width_m, wcfg.height_m) * 0.5
        ground = [[
            (-margin, -margin, 0.0),
            (wcfg.width_m + margin, -margin, 0.0),
            (wcfg.width_m + margin, wcfg.height_m + margin, 0.0),
            (-margin, wcfg.height_m + margin, 0.0),
        ]]
        ax.add_collection3d(Poly3DCollection(
            ground, facecolors=GROUND_COLOR, edgecolors="none", zsort="min",
        ))

        # Corridor segments — render each segment as a thick road strip
        # (Poly3DCollection of a rectangular ribbon).
        road_z = 0.05
        for corridor in self.sim.corridors:
            wps = corridor.waypoints
            ribbon = []
            road_half_width = 10.0
            for i in range(len(wps)):
                a = wps[i]
                b = wps[(i + 1) % len(wps)]
                dx, dy = b.x - a.x, b.y - a.y
                seg_len = math.hypot(dx, dy)
                if seg_len < 1e-6:
                    continue
                # Perpendicular unit vector for road width
                nx, ny = -dy / seg_len, dx / seg_len
                segment = [
                    (a.x - nx * road_half_width, a.y - ny * road_half_width, road_z),
                    (a.x + nx * road_half_width, a.y + ny * road_half_width, road_z),
                    (b.x + nx * road_half_width, b.y + ny * road_half_width, road_z),
                    (b.x - nx * road_half_width, b.y - ny * road_half_width, road_z),
                ]
                ribbon.append(segment)
            if ribbon:
                ax.add_collection3d(Poly3DCollection(
                    ribbon, facecolors=ROAD_COLOR, edgecolors="none",
                ))
            # Dashed centerline — render as 3D lines
            line_segs = []
            for i in range(len(wps)):
                a = wps[i]
                b = wps[(i + 1) % len(wps)]
                line_segs.append([(a.x, a.y, road_z + 0.05),
                                   (b.x, b.y, road_z + 0.05)])
            if line_segs:
                ax.add_collection3d(Line3DCollection(
                    line_segs, colors=LANE_COLOR, linewidths=1.0,
                    linestyles=(0, (4, 6)),
                ))

    def _init_dynamic_artists(self):
        """Per-vehicle and drone collections we'll re-populate each frame.

        Each 3D collection is initialised with a single near-origin placeholder
        face/segment — matplotlib's add_collection3d auto-scaling errors on
        truly-empty collections."""
        dummy_face = [[(0, 0, 0), (0.01, 0, 0), (0.01, 0.01, 0), (0, 0.01, 0)]]
        dummy_segs = [[(0, 0, 0), (0.01, 0, 0)]]

        self.unit_state = []
        for unit in self.sim.units:
            # Vehicle: chassis box + cabin box (two Poly3DCollections).
            chassis = Poly3DCollection(dummy_face, facecolors=ACCENT,
                                         edgecolors="#1e3a8a", linewidths=0.6)
            cabin = Poly3DCollection(dummy_face, facecolors="#1e3a8a",
                                      edgecolors="none")
            self.ax3d.add_collection3d(chassis)
            self.ax3d.add_collection3d(cabin)

            # Drone body + 4 rotor discs.
            drone_body = Poly3DCollection(dummy_face, facecolors=DRONE_COLOR,
                                            edgecolors="#7c2d12", linewidths=0.6)
            rotors = [Poly3DCollection(dummy_face, facecolors=DRONE_COLOR,
                                         edgecolors="none", alpha=0.85)
                      for _ in range(4)]
            for r in rotors:
                self.ax3d.add_collection3d(r)
            self.ax3d.add_collection3d(drone_body)

            # Drone arms (lines from body to each rotor)
            arms = Line3DCollection(dummy_segs, colors="#7c2d12", linewidths=1.4)
            self.ax3d.add_collection3d(arms)

            # Shadow disc on ground
            shadow = Poly3DCollection(dummy_face, facecolors=(0, 0, 0, 0.35),
                                        edgecolors="none")
            self.ax3d.add_collection3d(shadow)

            # FOV cone — 12 lines from drone to perimeter samples on the ground
            fov_lines = Line3DCollection(dummy_segs, colors=FOV_COLOR,
                                           linewidths=0.8, alpha=0.6)
            self.ax3d.add_collection3d(fov_lines)
            fov_disc = Poly3DCollection(dummy_face,
                                          facecolors=(0.96, 0.65, 0.14, 0.18),
                                          edgecolors=FOV_COLOR, linewidths=0.6)
            self.ax3d.add_collection3d(fov_disc)

            # Scene agent markers — small boxes (vehicles), vertical lines (peds)
            scene_veh = Poly3DCollection(dummy_face, facecolors="#7ab0d4",
                                            edgecolors="none", alpha=0.9)
            scene_ped = Line3DCollection(dummy_segs, colors="#9ee37d",
                                            linewidths=2.5)
            scene_cyc = Poly3DCollection(dummy_face, facecolors="#e5b85a",
                                            edgecolors="none", alpha=0.9)
            self.ax3d.add_collection3d(scene_veh)
            self.ax3d.add_collection3d(scene_ped)
            self.ax3d.add_collection3d(scene_cyc)

            self.unit_state.append({
                "chassis": chassis,
                "cabin": cabin,
                "drone_body": drone_body,
                "rotors": rotors,
                "arms": arms,
                "shadow": shadow,
                "fov_lines": fov_lines,
                "fov_disc": fov_disc,
                "scene_veh": scene_veh,
                "scene_ped": scene_ped,
                "scene_cyc": scene_cyc,
            })

    def _init_overlays(self):
        """Figure-anchored text overlays — match the 2D cinematic mode."""
        self.stage_label = self.fig.text(
            0.03, 0.93, "", color=TEXT_DIM, fontsize=14,
            family="monospace", fontweight="bold", zorder=20,
        )
        self.alt_label = self.fig.text(
            0.03, 0.89, "", color=TEXT_DIM, fontsize=10,
            family="monospace", zorder=20,
        )
        self.scenario_label = self.fig.text(
            0.03, 0.85, "", color=TEXT_DIM, fontsize=10,
            family="monospace", zorder=20,
        )
        self.capture_stats = self.fig.text(
            0.03, 0.815, "", color=TEXT_DIM, fontsize=9,
            family="monospace", zorder=20,
        )
        self.brand_label = self.fig.text(
            0.03, 0.06, "skydock", color=ACCENT, fontsize=15,
            family="monospace", fontweight="bold", zorder=20,
        )
        self.subtitle = self.fig.text(
            0.03, 0.03, "vehicle-deployed drone · 3D simulation + BEV footage",
            color=TEXT_DIM, fontsize=9, family="monospace", zorder=20,
        )
        self.counter_label = self.fig.text(
            0.71, 0.93, "", color=TEXT_DIM, fontsize=10,
            family="monospace", ha="right", zorder=20,
        )
        self.trigger_label = self.fig.text(
            0.71, 0.89, "", color=TEXT_DIM, fontsize=10,
            family="monospace", ha="right", zorder=20,
        )
        self.clock_label = self.fig.text(
            0.71, 0.06, "", color=TEXT_DIM, fontsize=10,
            family="monospace", ha="right", zorder=20,
        )
        # Event log — anchored to figure, in the bottom-right area.
        self.log_header = self.fig.text(
            0.98, 0.50, "event log", color=ACCENT, fontsize=10,
            family="monospace", ha="right", va="top", fontweight="bold",
            zorder=30,
        )
        self.log_body = self.fig.text(
            0.98, 0.47, "", color=TEXT_COLOR, fontsize=9,
            family="monospace", ha="right", va="top", zorder=30,
            linespacing=1.5,
            bbox=dict(facecolor="#0a0e1a", edgecolor="#1f2937",
                      linewidth=0.8, boxstyle="round,pad=0.6", alpha=0.92),
        )
        # BEV inset title
        self.bev_title = self.fig.text(
            0.74, 0.96, "▣ drone camera (BEV)", color=DRONE_COLOR,
            fontsize=10, family="monospace", fontweight="bold", zorder=30,
        )
        # Deliverable popup
        self.deliverable_popup = self.fig.text(
            0.36, 0.50, "", color="#9ee37d", fontsize=14,
            family="monospace", fontweight="bold", ha="center", va="center",
            zorder=40,
            bbox=dict(facecolor="#0a0e1a", edgecolor="#9ee37d",
                      linewidth=1.5, boxstyle="round,pad=0.6", alpha=0.95),
        )
        self.deliverable_popup.set_visible(False)

    # -- per-frame --------------------------------------------------------

    def _focal_unit(self):
        for u in self.sim.units:
            if u.active_mission is not None and u.active_mission.is_active:
                return u
        return self.sim.units[0]

    def _update_camera(self, focal):
        """Smoothly track the focal unit; slowly orbit azimuth."""
        if focal.active_mission is not None and focal.drone.is_airborne:
            tx = (focal.vehicle.x + focal.drone.x) / 2
            ty = (focal.vehicle.y + focal.drone.y) / 2
            te = 240.0 + focal.drone.altitude_m * 1.5
        else:
            tx, ty = focal.vehicle.x, focal.vehicle.y
            te = 320.0
        lerp = 0.10
        self.cam_x += (tx - self.cam_x) * lerp
        self.cam_y += (ty - self.cam_y) * lerp
        self.cam_extent += (te - self.cam_extent) * lerp

        half = self.cam_extent
        self.ax3d.set_xlim(self.cam_x - half, self.cam_x + half)
        self.ax3d.set_ylim(self.cam_y - half, self.cam_y + half)
        # Cap z so altitude is visible but not dominant.
        self.ax3d.set_zlim(0, max(140.0, focal.drone.altitude_m * 1.5 + 40))

        # Slow azimuth orbit
        self.view_azim_phase += 0.4
        self.ax3d.view_init(
            elev=self.view_elev,
            azim=self.view_azim_base + 8 * math.sin(self.view_azim_phase * math.pi / 180),
        )

    def _update_vehicle(self, state, unit):
        v = unit.vehicle
        faces = _box_faces(
            v.x, v.y, VEHICLE_HEIGHT_M / 2,
            VEHICLE_LENGTH_M, VEHICLE_WIDTH_M, VEHICLE_HEIGHT_M,
            heading_rad=v.heading_rad,
        )
        state["chassis"].set_verts(faces)
        # Cabin: smaller box on top of chassis
        cabin_faces = _box_faces(
            v.x - 2.0 * math.cos(v.heading_rad),
            v.y - 2.0 * math.sin(v.heading_rad),
            VEHICLE_HEIGHT_M + 1.4,
            VEHICLE_LENGTH_M * 0.5, VEHICLE_WIDTH_M * 0.8, 2.8,
            heading_rad=v.heading_rad,
        )
        state["cabin"].set_verts(cabin_faces)

    def _update_drone(self, state, unit, t_s):
        d = unit.drone
        v = unit.vehicle
        airborne = d.is_airborne
        if not airborne:
            x = v.x
            y = v.y
            z = VEHICLE_HEIGHT_M + 4.0
            arm = DRONE_ARM_M * 0.6
        else:
            x, y, z = d.x, d.y, max(0.0, d.altitude_m)
            arm = DRONE_ARM_M

        # Body: small box
        body = _box_faces(x, y, z, arm * 0.8, arm * 0.8, arm * 0.3)
        state["drone_body"].set_verts(body)

        # Arms + rotors at 4 corners
        rotor_offsets = [(arm, arm), (arm, -arm), (-arm, arm), (-arm, -arm)]
        arm_lines = []
        for i, (dx, dy) in enumerate(rotor_offsets):
            arm_lines.append([(x, y, z), (x + dx, y + dy, z)])
            disc_pts = _disc_polygon(x + dx, y + dy, z + 0.2, arm * 0.55,
                                       n_segs=16)
            state["rotors"][i].set_verts([disc_pts])
            # "Spin" effect — small radius wobble per frame
            spin = 0.85 + 0.4 * abs(math.sin(t_s * 8.0))
            disc_pts_spun = _disc_polygon(x + dx, y + dy, z + 0.2,
                                           arm * 0.55 * spin, n_segs=16)
            state["rotors"][i].set_verts([disc_pts_spun])
        state["arms"].set_segments(arm_lines)

        # Shadow: dark disc on ground; grows with altitude
        if airborne and z > 1.0:
            shadow_r = 5.0 + z * 0.07
            shadow_pts = _disc_polygon(x, y, 0.06, shadow_r, n_segs=20)
            state["shadow"].set_verts([shadow_pts])
            shadow_alpha = max(0.08, 0.4 - z * 0.0028)
            state["shadow"].set_facecolor((0, 0, 0, shadow_alpha))
        else:
            state["shadow"].set_verts([])

        # FOV cone during capture
        capturing = (unit.active_mission is not None
                     and unit.active_mission.is_capturing)
        if capturing and z > 5.0:
            r = d.coverage_radius_m
            # 12 lines from drone down to ground circle samples
            n = 12
            cone_lines = []
            disc_pts = []
            for i in range(n):
                theta = 2 * math.pi * i / n
                gx = x + r * math.cos(theta)
                gy = y + r * math.sin(theta)
                cone_lines.append([(x, y, z), (gx, gy, 0.1)])
                disc_pts.append((gx, gy, 0.1))
            state["fov_lines"].set_segments(cone_lines)
            state["fov_disc"].set_verts([disc_pts])
        else:
            state["fov_lines"].set_segments([])
            state["fov_disc"].set_verts([])

    def _update_scene_agents(self, state, unit, t_s):
        scene = unit.active_scene
        capturing = (unit.active_mission is not None
                     and unit.active_mission.is_capturing
                     and scene is not None)
        if not capturing:
            state["scene_veh"].set_verts([])
            state["scene_ped"].set_segments([])
            state["scene_cyc"].set_verts([])
            return

        positions = scene.positions_now(t_s)
        veh_boxes = []
        cyc_boxes = []
        ped_lines = []
        for aid, cls, ax_, ay_ in positions:
            if cls == "passenger_vehicle":
                veh_boxes.extend(_box_faces(ax_, ay_, 1.0, 5.0, 2.0, 1.6))
            elif cls == "pedestrian":
                ped_lines.append([(ax_, ay_, 0.1), (ax_, ay_, 1.8)])
            else:  # cyclist
                cyc_boxes.extend(_box_faces(ax_, ay_, 0.8, 2.5, 1.0, 1.4))
        state["scene_veh"].set_verts(veh_boxes)
        state["scene_ped"].set_segments(ped_lines)
        state["scene_cyc"].set_verts(cyc_boxes)

    def _update_bev_inset(self, focal, t_s):
        """The drone-camera "footage": top-down view of the FOV during capture."""
        ax = self.ax_bev
        ax.clear()
        ax.set_facecolor("#1c1f25")
        for sp in ax.spines.values():
            sp.set_color(DRONE_COLOR)
            sp.set_linewidth(1.5)
        ax.set_xticks([])
        ax.set_yticks([])

        m = focal.active_mission
        scene = focal.active_scene
        capturing = (m is not None and m.is_capturing and scene is not None)
        if not capturing:
            ax.text(0.5, 0.5, "no capture\nstandby",
                    transform=ax.transAxes, ha="center", va="center",
                    color=TEXT_DIM, fontsize=9, family="monospace")
            return

        d = focal.drone
        r = d.coverage_radius_m
        ax.set_xlim(scene.center_x - r * 1.1, scene.center_x + r * 1.1)
        ax.set_ylim(scene.center_y - r * 1.1, scene.center_y + r * 1.1)
        ax.set_aspect("equal")

        # Road background — find the corridor segments that overlap the FOV
        for corridor in self.sim.corridors:
            wps = corridor.waypoints
            for i in range(len(wps)):
                a = wps[i]
                b = wps[(i + 1) % len(wps)]
                # Draw thick road line
                ax.plot([a.x, b.x], [a.y, b.y], color="#2a2f37",
                        linewidth=14, solid_capstyle="round", zorder=1)
                ax.plot([a.x, b.x], [a.y, b.y], color="#4b5563",
                        linewidth=0.8, linestyle=(0, (4, 6)), zorder=2)

        # FOV circle
        fov_patch = MplCircle((d.x, d.y), r, fill=False,
                                edgecolor=DRONE_COLOR, linewidth=1.5, zorder=8)
        ax.add_patch(fov_patch)

        # Drone position crosshair
        ax.plot(d.x, d.y, "+", color=DRONE_COLOR, markersize=14,
                markeredgewidth=2, zorder=9)

        # Agent visibility for this frame
        in_fov = set()
        if focal.capture_frame_idx > 0:
            last_frame = focal.capture_frame_idx - 1
            for aid, frames in scene.visibility.items():
                if last_frame in frames:
                    in_fov.add(aid)

        positions = scene.positions_now(t_s)
        for aid, cls, x, y in positions:
            color = {"passenger_vehicle": "#7ab0d4",
                     "pedestrian": "#9ee37d",
                     "cyclist": "#e5b85a"}.get(cls, "#888888")
            marker = {"passenger_vehicle": "s",
                      "pedestrian": "o",
                      "cyclist": "^"}.get(cls, "o")
            size = {"passenger_vehicle": 70,
                    "pedestrian": 22,
                    "cyclist": 38}.get(cls, 22)
            if aid in in_fov:
                ax.scatter([x], [y], s=size * 1.4, c=color, marker=marker,
                           edgecolors="white", linewidths=0.8, zorder=10)
            else:
                ax.scatter([x], [y], s=size * 0.8, c=color, marker=marker,
                           edgecolors="none", alpha=0.5, zorder=7)

        # Live readout on the inset
        n_seen = len(in_fov)
        n_total = len(scene.agents)
        ax.text(0.04, 0.96, f"alt {d.altitude_m:.0f}m  ·  {n_seen}/{n_total} agents",
                transform=ax.transAxes, color=TEXT_COLOR,
                fontsize=8, family="monospace", va="top", zorder=20)
        ax.text(0.04, 0.04, m.scene_class.replace("_", " "),
                transform=ax.transAxes, color=DRONE_COLOR,
                fontsize=8, family="monospace", va="bottom", zorder=20)

    # -- event log -----------------------------------------------------------

    def _format_log_time(self, t_s: float) -> str:
        h = int(t_s // 3600)
        m = int((t_s % 3600) // 60)
        s = int(t_s % 60)
        return f"{h:02d}:{m:02d}:{s:02d}"

    def _push_log(self, t_s, kind, detail):
        line = f"[{self._format_log_time(t_s)}]  {kind:<10s} {detail}"
        self._event_log.append(line)
        if len(self._event_log) > self._max_log_lines:
            self._event_log = self._event_log[-self._max_log_lines:]

    def _emit_events(self, t_s):
        sim = self.sim
        n_started = sim.metrics.missions_started
        if n_started > self._prev_missions_started:
            for u in sim.units:
                m = u.active_mission
                if m is not None and m.is_active and m.mission_id not in self._prev_mission_stages:
                    self._push_log(t_s, "TRIGGER",
                                   f"{m.trigger.type}·{m.scene_class.replace('_','-')}")
                    self._prev_mission_stages[m.mission_id] = m.stage
            self._prev_missions_started = n_started

        for u in sim.units:
            m = u.active_mission
            if m is None or not m.is_active:
                continue
            prev = self._prev_mission_stages.get(m.mission_id, "")
            if prev != m.stage:
                if m.stage == "CAPTURING":
                    n = len(u.active_scene.agents) if u.active_scene else 0
                    self._push_log(t_s, "CAPTURE",
                                   f"{n:>2d} agents · {m.scene_class.replace('_','-')}")
                self._prev_mission_stages[m.mission_id] = m.stage

        completed = sim.completed_missions
        if len(completed) > self._prev_completed_count:
            for new in completed[self._prev_completed_count:]:
                short = new.mission_id.replace("skydock-mission-", "")
                if new.stage == "DONE":
                    q = new.quality_score_from_scene or 0.0
                    self._push_log(t_s, "✓ CAPTURED", f"scenario_{short}  q={q:.0f}")
                elif new.stage == "ABORTED":
                    reason = (new.aborted_reason or "unknown").replace("_", " ")
                    self._push_log(t_s, "✗ ABORTED", reason)
            self._prev_completed_count = len(completed)

        n_pipe = len(sim.pipeline.completed)
        if n_pipe > self._prev_pipeline_completed:
            for job in sim.pipeline.completed[self._prev_pipeline_completed:]:
                short = job.mission.mission_id.replace("skydock-mission-", "")
                if job.delivered:
                    self._push_log(t_s, "→ DELIVERED", f"scenario_{short}.xosc")
                else:
                    self._push_log(t_s, "  rejected", f"scenario_{short} (low quality)")
            self._prev_pipeline_completed = n_pipe

        self.log_body.set_text("\n".join(self._event_log))

    def _check_for_deliverable(self, t_s, frame_dt):
        # Re-uses the popup state set by _emit_events via completed list.
        # We use the same logic from the 2D version: when missions_completed
        # grew, set the popup; otherwise count down.
        completed = self.sim.completed_missions
        if completed and self._popup_t_remaining <= 0 and self._prev_completed_count == len(completed):
            # No new completions just landed; just fade
            pass

        if self._popup_t_remaining > 0:
            self.deliverable_popup.set_visible(True)
            self.deliverable_popup.set_text(self._last_popup_text)
            self._popup_t_remaining -= frame_dt / max(
                1.0, self.cfg.animation.speed_multiplier / self.cfg.animation.fps
            )
        else:
            self.deliverable_popup.set_visible(False)

    def _update_overlays(self, focal, t_s):
        m = focal.active_mission
        if m is not None and m.is_active:
            label = STAGE_LABEL.get(m.stage, m.stage)
            color = STAGE_COLOR.get(m.stage, TEXT_DIM)
            self.stage_label.set_text(f"▲ {label}")
            self.stage_label.set_color(color)
            self.alt_label.set_text(
                f"alt {focal.drone.altitude_m:5.1f} m  ·  batt {focal.drone.battery_pct:4.1f}%"
            )
            self.alt_label.set_color(TEXT_COLOR)
            self.trigger_label.set_text(
                f"trigger · {m.trigger.type}  @  {m.scene_class.replace('_',' ')}"
            )
        else:
            self.stage_label.set_text("◇ STANDBY")
            self.stage_label.set_color(TEXT_DIM)
            self.alt_label.set_text("awaiting trigger")
            self.alt_label.set_color(TEXT_DIM)
            self.trigger_label.set_text("")

        scene = focal.active_scene
        capturing = (m is not None and m.is_capturing and scene is not None)
        if capturing:
            self.scenario_label.set_text(
                f"scenario · {scene.scene_class.replace('_',' ')}"
            )
            self.scenario_label.set_color(STAGE_COLOR["CAPTURING"])
            n_veh = sum(1 for a in scene.agents if a.cls == "passenger_vehicle")
            n_ped = sum(1 for a in scene.agents if a.cls == "pedestrian")
            n_cyc = sum(1 for a in scene.agents if a.cls == "cyclist")
            n_fov = 0
            if focal.capture_frame_idx > 0:
                last_frame = focal.capture_frame_idx - 1
                for aid, frames in scene.visibility.items():
                    if last_frame in frames:
                        n_fov += 1
            self.capture_stats.set_text(
                f"tracking {n_fov:>2d}/{len(scene.agents):>2d} agents  ·  "
                f"{n_veh} veh · {n_ped} ped · {n_cyc} cyc"
            )
            self.capture_stats.set_color(TEXT_COLOR)
        else:
            self.scenario_label.set_text("")
            self.capture_stats.set_text("")

        delivered = sum(1 for j in self.sim.pipeline.completed if j.delivered)
        self.counter_label.set_text(
            f"{self.sim.metrics.missions_succeeded} ok / "
            f"{self.sim.metrics.missions_started} total  ·  "
            f"delivered {delivered}"
        )
        h = int(t_s // 3600)
        mi = int((t_s % 3600) // 60)
        s = int(t_s % 60)
        self.clock_label.set_text(f"t+{h:02d}:{mi:02d}:{s:02d}")

    def update(self, frame_idx: int):
        sim = self.sim
        cfg = sim.cfg
        sim_dt_per_frame = cfg.animation.speed_multiplier / cfg.animation.fps
        target_t = sim.t_s + sim_dt_per_frame
        while sim.t_s < target_t and sim.t_s < sim.duration_s:
            sim.step()

        focal = self._focal_unit()
        self._update_camera(focal)
        for state, unit in zip(self.unit_state, sim.units):
            self._update_vehicle(state, unit)
            self._update_drone(state, unit, sim.t_s)
            self._update_scene_agents(state, unit, sim.t_s)
        self._update_bev_inset(focal, sim.t_s)
        self._emit_events(sim.t_s)
        self._update_overlays(focal, sim.t_s)
        return []


def run_cinematic3d(sim: "Simulation", save_path: str | None = None) -> None:
    cfg = sim.cfg
    fps = cfg.animation.fps
    speedup = cfg.animation.speed_multiplier
    sim_dt_per_frame = speedup / fps
    total_frames = int((cfg.simulation.duration_hours * 3600.0) / sim_dt_per_frame)

    renderer = Cinematic3DRenderer(sim)
    anim = FuncAnimation(
        renderer.fig, renderer.update,
        frames=total_frames, interval=1000.0 / fps,
        blit=False, repeat=False,
    )

    if save_path:
        anim.save(save_path, fps=fps, dpi=85)
        print(f"saved 3D cinematic to {save_path}")
    else:
        plt.show()
