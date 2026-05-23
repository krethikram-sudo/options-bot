"""Matplotlib animation — map view + live stats dashboard.

Layout:
    +----------------------------+--------------------+
    |                            |  Time / conditions |
    |        MAP                 |--------------------|
    |  (vehicle + drone +        |  Mission counters  |
    |   capture footprint)       |--------------------|
    |                            |  Abort reasons     |
    |                            |--------------------|
    |                            |  P&L              |
    +----------------------------+--------------------+
"""
from __future__ import annotations

import math
from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle, Rectangle

if TYPE_CHECKING:
    from .simulation import Simulation


_ABORT_COLORS = {
    "wind_too_high": "#d97757",
    "weather": "#7ab0d4",
    "low_battery": "#e5b85a",
    "launch_mechanical": "#b86b8c",
    "dock_latch_fail": "#9c7ad9",
    "pre_flight_check": "#888888",
    "upload_failed": "#666666",
    "quality_below_threshold": "#aaaaaa",
}


def _abort_color(reason: str) -> str:
    return _ABORT_COLORS.get(reason, "#cccccc")


def _format_hours(t_s: float) -> str:
    hours = t_s / 3600.0
    h = int(hours)
    m = int((hours - h) * 60)
    return f"{h:02d}:{m:02d}"


def run_animation(sim: "Simulation", save_path: str | None = None) -> None:
    cfg = sim.cfg
    fps = cfg.animation.fps
    speedup = cfg.animation.speed_multiplier
    sim_dt_per_frame = speedup / fps
    total_frames = int((cfg.simulation.duration_hours * 3600.0) / sim_dt_per_frame)

    fig = plt.figure(figsize=(15, 8), facecolor="#0e0f12")
    gs = fig.add_gridspec(
        nrows=4,
        ncols=2,
        width_ratios=[3.0, 1.2],
        height_ratios=[1, 1, 1, 1],
        wspace=0.08,
        hspace=0.35,
    )
    ax_map = fig.add_subplot(gs[:, 0])
    ax_time = fig.add_subplot(gs[0, 1])
    ax_counts = fig.add_subplot(gs[1, 1])
    ax_aborts = fig.add_subplot(gs[2, 1])
    ax_econ = fig.add_subplot(gs[3, 1])

    for ax in (ax_map, ax_time, ax_counts, ax_aborts, ax_econ):
        ax.set_facecolor("#16181d")
        for spine in ax.spines.values():
            spine.set_color("#3a3f47")
        ax.tick_params(colors="#9ca3af", labelsize=8)

    _setup_map(ax_map, sim)

    state = {
        "vehicle_dot": ax_map.plot([], [], "o", color="#9ee37d", markersize=9, zorder=5)[0],
        "drone_dot": ax_map.plot([], [], "^", color="#f5a524", markersize=12, zorder=6)[0],
        "drone_tether": ax_map.plot([], [], "-", color="#f5a524", alpha=0.4, linewidth=1)[0],
        "drone_trail": ax_map.plot([], [], "-", color="#f5a524", alpha=0.5, linewidth=1.5)[0],
        "coverage": Circle((0, 0), 0, fill=True, color="#f5a524", alpha=0.0, zorder=3),
        "trail_xs": [],
        "trail_ys": [],
        "ax_time": ax_time,
        "ax_counts": ax_counts,
        "ax_aborts": ax_aborts,
        "ax_econ": ax_econ,
    }
    ax_map.add_patch(state["coverage"])

    def init():
        return (
            state["vehicle_dot"],
            state["drone_dot"],
            state["drone_tether"],
            state["drone_trail"],
            state["coverage"],
        )

    def update(frame_idx: int):
        # Advance sim by sim_dt_per_frame seconds, in dt-sized steps.
        target_t = sim.t_s + sim_dt_per_frame
        while sim.t_s < target_t and sim.t_s < sim.duration_s:
            sim.step()

        snap = sim.snapshot()
        _update_map(state, snap, cfg)
        _update_panels(state, snap, cfg)
        return (
            state["vehicle_dot"],
            state["drone_dot"],
            state["drone_tether"],
            state["drone_trail"],
            state["coverage"],
        )

    fig.suptitle(
        "Skydock — vehicle-deployed drone simulation",
        color="#e5e7eb",
        fontsize=14,
        y=0.97,
    )

    anim = FuncAnimation(
        fig,
        update,
        init_func=init,
        frames=total_frames,
        interval=1000.0 / fps,
        blit=False,
        repeat=False,
    )

    if save_path:
        anim.save(save_path, fps=fps, dpi=110)
        print(f"saved animation to {save_path}")
    else:
        plt.show()


def _setup_map(ax, sim: "Simulation") -> None:
    cfg = sim.cfg.world
    ax.set_xlim(0, cfg.width_m)
    ax.set_ylim(0, cfg.height_m)
    ax.set_aspect("equal")
    ax.set_title("Operating corridor", color="#e5e7eb", fontsize=10, pad=6)
    ax.set_xticks([])
    ax.set_yticks([])

    # Draw the route as a closed loop polyline.
    xs = [w.x for w in sim.waypoints] + [sim.waypoints[0].x]
    ys = [w.y for w in sim.waypoints] + [sim.waypoints[0].y]
    ax.plot(xs, ys, "-", color="#3a3f47", linewidth=2, alpha=0.7)

    for w in sim.waypoints:
        ax.plot(w.x, w.y, "o", color="#586173", markersize=5, alpha=0.8)
        ax.annotate(
            w.label.replace("_", " "),
            xy=(w.x, w.y),
            xytext=(8, 8),
            textcoords="offset points",
            color="#9ca3af",
            fontsize=7,
            alpha=0.8,
        )


def _update_map(state, snap, cfg) -> None:
    v = snap.vehicle
    d = snap.drone
    state["vehicle_dot"].set_data([v.x], [v.y])

    if d.is_airborne:
        state["drone_dot"].set_data([d.x], [d.y])
        state["drone_tether"].set_data([v.x, d.x], [v.y, d.y])
        state["trail_xs"].append(d.x)
        state["trail_ys"].append(d.y)
        # Keep trail bounded.
        max_pts = int(cfg.animation.trail_length_s * cfg.animation.fps)
        if len(state["trail_xs"]) > max_pts:
            state["trail_xs"] = state["trail_xs"][-max_pts:]
            state["trail_ys"] = state["trail_ys"][-max_pts:]
        state["drone_trail"].set_data(state["trail_xs"], state["trail_ys"])
    else:
        state["drone_dot"].set_data([], [])
        state["drone_tether"].set_data([], [])
        # Fade old trail by clearing slowly.
        if state["trail_xs"]:
            state["trail_xs"] = state["trail_xs"][:-1]
            state["trail_ys"] = state["trail_ys"][:-1]
            state["drone_trail"].set_data(state["trail_xs"], state["trail_ys"])

    cov = state["coverage"]
    if snap.active_mission is not None and snap.active_mission.is_capturing:
        cov.center = (d.x, d.y)
        cov.set_radius(d.coverage_radius_m)
        cov.set_alpha(0.18)
    else:
        cov.set_alpha(0.0)


def _update_panels(state, snap, cfg) -> None:
    _draw_time_panel(state["ax_time"], snap)
    _draw_counts_panel(state["ax_counts"], snap)
    _draw_aborts_panel(state["ax_aborts"], snap)
    _draw_econ_panel(state["ax_econ"], snap)


def _panel_setup(ax, title: str) -> None:
    ax.clear()
    ax.set_facecolor("#16181d")
    for spine in ax.spines.values():
        spine.set_color("#3a3f47")
    ax.tick_params(colors="#9ca3af", labelsize=8)
    ax.set_title(title, color="#e5e7eb", fontsize=10, pad=4, loc="left")
    ax.set_xticks([])
    ax.set_yticks([])


def _draw_time_panel(ax, snap) -> None:
    _panel_setup(ax, "Time & conditions")
    cond = snap.conditions
    mission_stage = "—"
    if snap.active_mission is not None:
        mission_stage = snap.active_mission.stage
    operating = "✓ daylight" if cond.is_daylight else "✗ off-hours"
    weather = "clear" if cond.weather_clear else "weather"
    lines = [
        f"sim time     {_format_hours(snap.t_s)}",
        f"hour of day  {cond.hour_of_day:5.2f}",
        f"status       {operating}",
        f"wind         {cond.wind_mph:5.1f} mph",
        f"weather      {weather}",
        f"vehicle spd  {snap.vehicle.speed_mph:5.1f} mph",
        f"drone batt   {snap.drone.battery_pct:5.1f}%",
        f"mission      {mission_stage}",
    ]
    ax.text(
        0.04, 0.95, "\n".join(lines),
        transform=ax.transAxes,
        color="#e5e7eb",
        fontsize=9,
        family="monospace",
        va="top",
    )


def _draw_counts_panel(ax, snap) -> None:
    _panel_setup(ax, "Mission counters")
    m = snap.metrics
    delivered = sum(1 for j in snap.pipeline.completed if j.delivered)
    avg_q = snap.metrics.avg_delivered_quality()
    lines = [
        f"triggered    {m.missions_started:4d}",
        f"succeeded    {m.missions_succeeded:4d}",
        f"aborted      {m.missions_aborted:4d}",
        f"skipped busy {m.triggers_skipped_drone_busy:4d}",
        f"in pipeline  {snap.pipeline.in_flight():4d}",
        f"delivered    {delivered:4d}",
        f"rejected     {snap.pipeline.rejected_count:4d}",
        f"avg quality  {avg_q:5.1f}",
    ]
    ax.text(
        0.04, 0.95, "\n".join(lines),
        transform=ax.transAxes,
        color="#e5e7eb",
        fontsize=9,
        family="monospace",
        va="top",
    )


def _draw_aborts_panel(ax, snap) -> None:
    _panel_setup(ax, "Failure breakdown")
    reasons = snap.metrics.abort_reasons
    if not reasons:
        ax.text(
            0.5, 0.5, "no aborts yet",
            transform=ax.transAxes,
            ha="center", va="center",
            color="#6b7280", fontsize=9,
        )
        return
    items = reasons.most_common()
    labels = [r for r, _ in items]
    counts = [c for _, c in items]
    colors = [_abort_color(r) for r in labels]
    ax.barh(range(len(labels)), counts, color=colors)
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(
        [l.replace("_", " ") for l in labels],
        color="#9ca3af", fontsize=8,
    )
    ax.invert_yaxis()
    ax.tick_params(axis="x", colors="#9ca3af", labelsize=8)
    for spine in ax.spines.values():
        spine.set_color("#3a3f47")


def _draw_econ_panel(ax, snap) -> None:
    _panel_setup(ax, "Unit economics")
    e = snap.economics.ledger
    margin_pct = snap.economics.ledger.gross_margin * 100.0
    lines = [
        f"revenue      ${e.revenue_usd:8,.0f}",
        f"cloud cost   ${e.cloud_cost_usd:8,.2f}",
        f"drone wear   ${e.drone_wear_cost_usd:8,.2f}",
        f"operator     ${e.operator_cost_usd:8,.0f}",
        f"vehicle      ${e.vehicle_cost_usd:8,.2f}",
        f"overhead     ${e.overhead_cost_usd:8,.0f}",
        f"gross profit ${e.gross_profit:8,.0f}",
        f"gross margin {margin_pct:7.1f}%",
    ]
    ax.text(
        0.04, 0.95, "\n".join(lines),
        transform=ax.transAxes,
        color="#e5e7eb",
        fontsize=9,
        family="monospace",
        va="top",
    )
