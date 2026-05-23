"""End-of-run text report (for headless mode)."""
from __future__ import annotations

from .simulation import Simulation


def print_report(sim: Simulation) -> None:
    m = sim.metrics
    e = sim.economics.ledger
    delivered = sum(1 for j in sim.completed_jobs if j.delivered)

    print()
    print("=" * 60)
    print(f"Skydock simulation report  ({sim.cfg.simulation.duration_hours:.1f}h simulated)")
    print("=" * 60)

    print("\nOperations (spec 9.1)")
    print(f"  missions triggered ......... {m.missions_started}")
    print(f"  missions succeeded ......... {m.missions_succeeded}")
    print(f"  missions aborted ........... {m.missions_aborted}")
    print(f"  triggers skipped (busy) .... {m.triggers_skipped_drone_busy}")
    print(f"  triggers skipped (envelope)  {m.triggers_skipped_outside_envelope}")
    if m.missions_started:
        print(f"  success rate ............... {m.success_rate() * 100:.1f}%")

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
    print()
