"""End-of-run text report (for headless mode)."""
from __future__ import annotations

from .simulation import Simulation


def print_report(sim: Simulation) -> None:
    m = sim.metrics
    e = sim.economics.ledger
    delivered = sum(1 for j in sim.completed_jobs if j.delivered)

    n_units = len(sim.units)
    print()
    print("=" * 60)
    print(f"Skydock simulation report  ({sim.cfg.simulation.duration_hours:.1f}h, {n_units} vehicle{'s' if n_units != 1 else ''})")
    print("=" * 60)

    print("\nOperations (spec 9.1)")
    print(f"  missions triggered ......... {m.missions_started}")
    print(f"  missions succeeded ......... {m.missions_succeeded}")
    print(f"  missions aborted ........... {m.missions_aborted}")
    print(f"  triggers skipped (busy) .... {m.triggers_skipped_drone_busy}")
    print(f"  triggers skipped (envelope)  {m.triggers_skipped_outside_envelope}")
    if m.missions_started:
        print(f"  success rate ............... {m.success_rate() * 100:.1f}%")
    if n_units > 1 and delivered:
        print(f"  delivered per vehicle ...... {delivered / n_units:.1f}")

    if m.abort_reasons:
        print("\n  Abort reasons:")
        for reason, count in m.abort_reasons.most_common():
            print(f"    {reason:.<28} {count}")

    if m.trigger_types:
        print("\n  Trigger mix:")
        total = sum(m.trigger_types.values())
        for ttype, count in m.trigger_types.most_common():
            print(f"    {ttype:.<28} {count}  ({count/total*100:.0f}%)")

    if m.scenes_by_class:
        print("\n  Scenes captured by class:")
        for cls, count in m.scenes_by_class.most_common():
            print(f"    {cls:.<28} {count}")

    if m.drone_lost_events or m.dock_damage_events:
        print("\n  Failure cascades (spec §7.1):")
        print(f"    drones lost (flyaway)....... {m.drone_lost_events}")
        print(f"    dock damage events.......... {m.dock_damage_events}")
        total_downtime_hours = (
            m.drone_lost_events * sim.cfg.failure_cascades.drone_replacement_hours
            + m.dock_damage_events * sim.cfg.failure_cascades.dock_repair_hours
        )
        print(f"    aggregated downtime......... {total_downtime_hours:.1f} h")

    print("\nData pipeline (spec 9.2)")
    print(f"  delivered scenarios ........ {delivered}")
    print(f"  rejected (quality) ......... {sim.pipeline.rejected_count}")
    print(f"  failed uploads ............. {sim.pipeline.upload_failed_count}")
    print(f"  avg delivered quality ...... {m.avg_delivered_quality():.1f}")

    print("\nEconomics (spec 9.3)")
    print(f"  revenue .................... ${e.revenue_usd:,.2f}")
    print(f"  variable costs ............. ${e.total_variable_cost:,.2f}")
    print(f"  operator + vehicle ......... ${e.operator_cost_usd + e.vehicle_cost_usd:,.2f}")
    print(f"  overhead ................... ${e.overhead_cost_usd:,.2f}")
    print(f"  gross profit ............... ${e.gross_profit:,.2f}")
    if e.revenue_usd > 0:
        print(f"  gross margin ............... {e.gross_margin * 100:.1f}%")

    if sim.funnel is not None:
        s = sim.funnel.state()
        runway_str = "∞ (cash-flow positive)" if s.runway_months == float("inf") else f"{s.runway_months:.1f} months"
        print("\nCustomer funnel (spec §4.1-4.3)")
        print(f"  prospects (active / total).. {s.prospects_active} / {s.prospects_lifetime}")
        print(f"  pilots (active / fulfilled). {s.pilots_active} / {s.pilots_fulfilled}")
        print(f"  scenarios committed ........ {s.scenarios_committed}")
        print(f"  scenarios delivered ........ {s.scenarios_delivered_to_pilots}  (unsold: {s.scenarios_unsold})")
        print(f"  pilot revenue .............. ${s.revenue_usd:,.2f}")
        print(f"  monthly revenue rate ....... ${s.monthly_revenue_rate_usd:,.2f}")
        print(f"  cash balance ............... ${s.cash_usd:,.2f}")
        print(f"  monthly burn ............... ${s.monthly_burn_usd:,.2f}")
        print(f"  runway ..................... {runway_str}")
        if sim.funnel.pilots:
            print("\n  Pilots signed:")
            for p in sim.funnel.pilots:
                state = "fulfilled" if p.is_fulfilled else "active"
                print(f"    {p.name:<22} {p.scenarios_delivered:>4d}/{p.scenarios_committed:<4d} "
                      f"@ ${p.price_per_scenario:.0f}  [{state}]")
    print()
