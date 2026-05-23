"""Matplotlib animation — multi-vehicle map view + live stats dashboard.

Layout:
    +-----------------------------+----------------------+
    |                             |  Time / conditions   |
    |        MAP                  |----------------------|
    |  (N vehicles + drones +     |  Mission counters    |
    |   capture footprint)        |----------------------|
    |                             |  Failure breakdown   |
    |-----------------------------|----------------------|
    |  Mission timeline strip     |  Unit economics      |
    +-----------------------------+----------------------+
"""
from __future__ import annotations

from typing import TYPE_CHECKING

import matplotlib.pyplot as plt
from matplotlib.animation import FuncAnimation
from matplotlib.patches import Circle

if TYPE_CHECKING:
    from .simulation import Simulation, SimSnapshot, VehicleUnit


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

    fig = plt.figure(figsize=(15, 9), facecolor="#0e0f12")
    gs = fig.add_gridspec(
        nrows=5,
        ncols=2,
        width_ratios=[3.0, 1.2],
        height_ratios=[1, 1, 1, 1, 0.5],
        wspace=0.08,
        hspace=0.45,
    )
    ax_map = fig.add_subplot(gs[0:4, 0])
    ax_timeline = fig.add_subplot(gs[4, 0])
    ax_time = fig.add_subplot(gs[0, 1])
    ax_counts = fig.add_subplot(gs[1, 1])
    ax_aborts = fig.add_subplot(gs[2, 1])
    ax_econ = fig.add_subplot(gs[3:5, 1])

    for ax in (ax_map, ax_timeline, ax_time, ax_counts, ax_aborts, ax_econ):
        ax.set_facecolor("#16181d")
        for spine in ax.spines.values():
            spine.set_color("#3a3f47")
        ax.tick_params(colors="#9ca3af", labelsize=8)

    _setup_map(ax_map, sim)
    _setup_timeline(ax_timeline)

    # Per-unit artists, indexed by unit position.
    unit_artists = []
    for unit in sim.units:
        v_dot = ax_map.plot([], [], "o", color=unit.color, markersize=9, zorder=5)[0]
        d_dot = ax_map.plot([], [], "^", color="#f5a524", markersize=11, zorder=6,
                            markeredgecolor=unit.color, markeredgewidth=1.5)[0]
        tether = ax_map.plot([], [], "-", color="#f5a524", alpha=0.4, linewidth=1)[0]
        trail = ax_map.plot([], [], "-", color="#f5a524", alpha=0.5, linewidth=1.5)[0]
        coverage = Circle((0, 0), 0, fill=True, color="#f5a524", alpha=0.0, zorder=3)
        ax_map.add_patch(coverage)
        unit_artists.append({
            "vehicle_dot": v_dot,
            "drone_dot": d_dot,
            "tether": tether,
            "trail": trail,
            "coverage": coverage,
            "trail_xs": [],
            "trail_ys": [],
        })

    state = {
        "units": unit_artists,
        "ax_timeline": ax_timeline,
        "ax_time": ax_time,
        "ax_counts": ax_counts,
        "ax_aborts": ax_aborts,
        "ax_econ": ax_econ,
    }

    def update(frame_idx: int):
        # Advance sim by sim_dt_per_frame seconds, in dt-sized steps.
        target_t = sim.t_s + sim_dt_per_frame
        while sim.t_s < target_t and sim.t_s < sim.duration_s:
            sim.step()

        snap = sim.snapshot()
        _update_map(state, snap, cfg)
        _update_timeline(state["ax_timeline"], snap, sim)
        _update_panels(state, snap)
        # Return all updatable artists for blit (we use blit=False but anyway).
        artists = []
        for ua in state["units"]:
            artists.extend([ua["vehicle_dot"], ua["drone_dot"], ua["tether"],
                            ua["trail"], ua["coverage"]])
        return artists

    fig.suptitle(
        "Skydock — vehicle-deployed drone simulation",
        color="#e5e7eb",
        fontsize=14,
        y=0.97,
    )

    anim = FuncAnimation(
        fig,
        update,
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


# -- map ----------------------------------------------------------------

_CORRIDOR_TINT = {
    "urban_dense": "#4b5563",
    "suburban": "#3f5b48",
    "highway_mix": "#5b4a39",
}


def _setup_map(ax, sim: "Simulation") -> None:
    cfg = sim.cfg.world
    ax.set_xlim(0, cfg.width_m)
    ax.set_ylim(0, cfg.height_m)
    ax.set_aspect("equal")
    title = ("Operating corridor" if len(sim.corridors) == 1
             else f"Operating corridors ({len(sim.corridors)})")
    ax.set_title(title, color="#e5e7eb", fontsize=10, pad=6, loc="left")
    ax.set_xticks([])
    ax.set_yticks([])

    for corridor in sim.corridors:
        tint = _CORRIDOR_TINT.get(corridor.corridor_type, "#4b5563")
        wps = corridor.waypoints
        xs = [w.x for w in wps] + [wps[0].x]
        ys = [w.y for w in wps] + [wps[0].y]
        ax.plot(xs, ys, color=tint, linewidth=8, alpha=0.35, solid_capstyle="round")
        ax.plot(xs, ys, color="#9ca3af", linewidth=1, alpha=0.6,
                linestyle=(0, (4, 6)))
        for w in wps:
            ax.plot(w.x, w.y, "s", color="#586173", markersize=5, alpha=0.85)
            ax.annotate(
                w.label.replace("_", " "),
                xy=(w.x, w.y),
                xytext=(7, 7),
                textcoords="offset points",
                color="#9ca3af",
                fontsize=6,
                alpha=0.75,
            )
        # Corridor label in the centre of its bbox.
        x0, y0, x1, y1 = corridor.bbox
        ax.text(
            (x0 + x1) / 2, y1 - (y1 - y0) * 0.04,
            corridor.corridor_type.replace("_", " "),
            color="#9ca3af", fontsize=9, ha="center", va="top", alpha=0.7,
        )


def _update_map(state, snap: "SimSnapshot", cfg) -> None:
    trail_max = int(cfg.animation.trail_length_s * cfg.animation.fps)
    for unit, art in zip(snap.units, state["units"]):
        v, d = unit.vehicle, unit.drone
        # Dim offline vehicles (drone lost / dock damaged) so it's obvious which units are out.
        if unit.is_offline(snap.t_s):
            art["vehicle_dot"].set_color("#4a4f57")
            art["vehicle_dot"].set_markeredgecolor("#6b7280")
            art["vehicle_dot"].set_markeredgewidth(1.5)
        else:
            art["vehicle_dot"].set_color(unit.color)
            art["vehicle_dot"].set_markeredgewidth(0)
        art["vehicle_dot"].set_data([v.x], [v.y])
        if d.is_airborne:
            art["drone_dot"].set_data([d.x], [d.y])
            art["tether"].set_data([v.x, d.x], [v.y, d.y])
            art["trail_xs"].append(d.x)
            art["trail_ys"].append(d.y)
            if len(art["trail_xs"]) > trail_max:
                art["trail_xs"] = art["trail_xs"][-trail_max:]
                art["trail_ys"] = art["trail_ys"][-trail_max:]
            art["trail"].set_data(art["trail_xs"], art["trail_ys"])
        else:
            art["drone_dot"].set_data([], [])
            art["tether"].set_data([], [])
            if art["trail_xs"]:
                # Fade trail by trimming a few points per frame.
                art["trail_xs"] = art["trail_xs"][:-1]
                art["trail_ys"] = art["trail_ys"][:-1]
                art["trail"].set_data(art["trail_xs"], art["trail_ys"])

        cov = art["coverage"]
        if unit.active_mission is not None and unit.active_mission.is_capturing:
            cov.center = (d.x, d.y)
            cov.set_radius(d.coverage_radius_m)
            cov.set_alpha(0.18)
        else:
            cov.set_alpha(0.0)


# -- mission timeline ---------------------------------------------------

def _setup_timeline(ax) -> None:
    ax.set_facecolor("#16181d")
    ax.set_title("Recent missions", color="#e5e7eb", fontsize=10, pad=4, loc="left")
    ax.set_xticks([])
    ax.set_yticks([])
    ax.set_ylim(0, 1)


def _update_timeline(ax, snap: "SimSnapshot", sim: "Simulation") -> None:
    ax.clear()
    _setup_timeline(ax)
    history = sim.completed_missions[-40:]
    if not history:
        ax.text(0.5, 0.5, "no completed missions yet",
                transform=ax.transAxes, ha="center", va="center",
                color="#6b7280", fontsize=9)
        return
    ax.set_xlim(0, max(40, len(history)))
    for i, m in enumerate(history):
        color = "#9ee37d" if m.stage == "DONE" else _abort_color(m.aborted_reason or "")
        ax.add_patch(plt.Rectangle((i, 0.15), 0.85, 0.7, color=color, alpha=0.85))


# -- side panels --------------------------------------------------------

def _update_panels(state, snap: "SimSnapshot") -> None:
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


def _draw_time_panel(ax, snap: "SimSnapshot") -> None:
    _panel_setup(ax, "Time & conditions")
    cond = snap.conditions
    operating = "✓ daylight" if cond.is_daylight else "✗ off-hours"
    weather = "clear" if cond.weather_clear else "weather"
    n_units = len(snap.units)
    online = sum(1 for u in snap.units if not u.is_offline(snap.t_s))
    active_now = sum(1 for u in snap.units if u.active_mission is not None)
    avg_batt = sum(u.drone.battery_pct for u in snap.units) / n_units
    avg_capacity = sum(u.drone.battery_capacity_pct for u in snap.units) / n_units
    lines = [
        f"sim time     {_format_hours(snap.t_s)}",
        f"hour of day  {cond.hour_of_day:5.2f}",
        f"status       {operating}",
        f"wind         {cond.wind_mph:5.1f} mph",
        f"weather      {weather}",
        f"online       {online}/{n_units}",
        f"missions now {active_now}",
        f"avg battery  {avg_batt:5.1f}%",
        f"avg capacity {avg_capacity:5.1f}%",
    ]
    ax.text(
        0.04, 0.95, "\n".join(lines),
        transform=ax.transAxes, color="#e5e7eb",
        fontsize=9, family="monospace", va="top",
    )


def _draw_counts_panel(ax, snap: "SimSnapshot") -> None:
    _panel_setup(ax, "Mission counters")
    m = snap.metrics
    delivered = sum(1 for j in snap.pipeline.completed if j.delivered)
    avg_q = m.avg_delivered_quality()
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
        transform=ax.transAxes, color="#e5e7eb",
        fontsize=9, family="monospace", va="top",
    )


def _draw_aborts_panel(ax, snap: "SimSnapshot") -> None:
    _panel_setup(ax, "Failure breakdown")
    reasons = snap.metrics.abort_reasons
    if not reasons:
        ax.text(
            0.5, 0.5, "no aborts yet",
            transform=ax.transAxes, ha="center", va="center",
            color="#6b7280", fontsize=9,
        )
        return
    items = reasons.most_common(6)
    labels = [r for r, _ in items]
    counts = [c for _, c in items]
    colors = [_abort_color(r) for r in labels]
    ax.barh(range(len(labels)), counts, color=colors, height=0.55)
    # Give the largest bar 70% of the panel width so single-value bars don't fill it.
    ax.set_xlim(0, max(max(counts) * 1.4, 3))
    ax.set_yticks(range(len(labels)))
    ax.set_yticklabels(
        [l.replace("_", " ") for l in labels],
        color="#9ca3af", fontsize=8,
    )
    ax.invert_yaxis()
    ax.tick_params(axis="x", colors="#9ca3af", labelsize=7)
    for spine in ax.spines.values():
        spine.set_color("#3a3f47")
    # Annotate counts on the bars.
    for i, c in enumerate(counts):
        ax.text(c + 0.1, i, str(c), color="#e5e7eb",
                fontsize=8, va="center")


def _draw_econ_panel(ax, snap: "SimSnapshot") -> None:
    _panel_setup(ax, "Unit economics")
    e = snap.economics.ledger
    margin_pct = e.gross_margin * 100.0
    lines = [
        f"revenue       ${e.revenue_usd:9,.0f}",
        f"cloud cost    ${e.cloud_cost_usd:9,.2f}",
        f"drone wear    ${e.drone_wear_cost_usd:9,.2f}",
        f"operator      ${e.operator_cost_usd:9,.0f}",
        f"vehicle       ${e.vehicle_cost_usd:9,.2f}",
        f"overhead      ${e.overhead_cost_usd:9,.0f}",
        f"-------------------------",
        f"gross profit  ${e.gross_profit:9,.0f}",
        f"gross margin   {margin_pct:7.1f} %",
        f"delivered      {e.scenarios_delivered:9d}",
    ]
    ax.text(
        0.04, 0.95, "\n".join(lines),
        transform=ax.transAxes, color="#e5e7eb",
        fontsize=9, family="monospace", va="top",
    )
