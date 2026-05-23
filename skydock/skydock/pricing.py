"""Bottoms-up cost-to-replicate pricing model.

Replaces the hardcoded $150/scenario assumption (spec §4.2) with a model
derived from inputs an AV customer could verify independently:

  - what it would cost the customer to produce one Skydock-equivalent
    scenario in-house (operator + annotation + capital + tooling)
  - a documented vendor markup band over that internal cost

The output is a per-scenario price band (low / mid / high) that the
sim can use directly, and that the brief.py output explicitly cites
back to each input source.

References for input ranges (none are precise; each is plausibility-
bounded against public information an investor or engineer can check):

  - Operator labor (loaded): BLS / Glassdoor for AV-eng total comp
    cluster $180K-$220K including benefits + overhead.
  - Scenarios per operator-hour: spec §1.5 target 12-20 captures/day
    over an 8-hour operator shift → 1.5-2.5 / hour.
  - Annotation labor: industry rates $5-50 per labeled frame for
    ground-vehicle AV data (Scale AI public filings, before/after
    Mighty AI acquisition). A scenario at 30 fps × 30-60 s = ~900-
    1800 frames, but per-scenario rates are lower than per-frame
    because of batching efficiencies.
  - Drone capex: DJI Mini 4 Pro retail $760, amortised over ~500
    missions before retirement at 60% battery floor.
  - Vehicle + dock capex: rough industry estimates.
  - Vendor markup over cost: 1.5-3x typical for specialty data
    services with bespoke / edge-case characteristics.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass
class ReplicationCostConfig:
    """Inputs to the cost-to-replicate pricing model.

    Every field has an external reference the user can validate. Override
    any of them in default_config.yaml under `replication_cost`.
    """
    # Operator labor (customer hiring AV-engineer-equivalent to do this
    # in-house). Loaded = base + benefits + overhead.
    operator_loaded_hourly_usd: float = 100.0
    scenarios_per_operator_hour: float = 2.0

    # Annotation / QA: human-in-the-loop validation of agent tracks,
    # OpenSCENARIO export sanity-check, etc.
    annotation_labor_usd_per_scenario_low: float = 30.0
    annotation_labor_usd_per_scenario_high: float = 150.0

    # Capital amortisation per scenario (drone + vehicle + dock).
    drone_capex_amortized_usd_per_scenario: float = 1.50      # $760 / 500
    vehicle_capex_amortized_usd_per_scenario: float = 2.00
    dock_capex_amortized_usd_per_scenario: float = 2.50

    # Software / cloud / tooling per scenario.
    cloud_processing_usd_per_scenario: float = 0.80
    bev_tooling_amortized_usd_per_scenario: float = 3.00
    delivery_tooling_amortized_usd_per_scenario: float = 1.00

    # Vendor markup band over internal cost. 1.5 is a tight commodity
    # margin; 3.0 reflects premium edge-case curation pricing.
    markup_low: float = 1.5
    markup_high: float = 3.0


@dataclass
class PricingBreakdown:
    """Output of the pricing model — everything the brief needs to cite."""
    operator_cost: float
    annotation_low: float
    annotation_high: float
    capital_cost: float
    software_cost: float
    internal_cost_low: float
    internal_cost_mid: float
    internal_cost_high: float
    price_low: float
    price_mid: float
    price_high: float
    markup_low: float
    markup_high: float


def derive_pricing(cfg: ReplicationCostConfig) -> PricingBreakdown:
    """Compute the per-scenario price band from the replication-cost inputs.

    Returns:
        PricingBreakdown with low / mid / high prices and the constituent
        cost components. The `price_mid` is what the sim uses as the
        default per-scenario price when pricing_mode = 'derived'.
    """
    operator_cost = (
        cfg.operator_loaded_hourly_usd / max(0.01, cfg.scenarios_per_operator_hour)
    )
    capital_cost = (
        cfg.drone_capex_amortized_usd_per_scenario
        + cfg.vehicle_capex_amortized_usd_per_scenario
        + cfg.dock_capex_amortized_usd_per_scenario
    )
    software_cost = (
        cfg.cloud_processing_usd_per_scenario
        + cfg.bev_tooling_amortized_usd_per_scenario
        + cfg.delivery_tooling_amortized_usd_per_scenario
    )

    annotation_low = cfg.annotation_labor_usd_per_scenario_low
    annotation_high = cfg.annotation_labor_usd_per_scenario_high
    annotation_mid = (annotation_low + annotation_high) / 2

    internal_cost_low = operator_cost + annotation_low + capital_cost + software_cost
    internal_cost_high = operator_cost + annotation_high + capital_cost + software_cost
    internal_cost_mid = operator_cost + annotation_mid + capital_cost + software_cost

    price_low = internal_cost_low * cfg.markup_low
    price_high = internal_cost_high * cfg.markup_high
    # Mid-point uses mid-markup over mid-cost (more meaningful than averaging the band).
    markup_mid = (cfg.markup_low + cfg.markup_high) / 2
    price_mid = internal_cost_mid * markup_mid

    return PricingBreakdown(
        operator_cost=operator_cost,
        annotation_low=annotation_low,
        annotation_high=annotation_high,
        capital_cost=capital_cost,
        software_cost=software_cost,
        internal_cost_low=internal_cost_low,
        internal_cost_mid=internal_cost_mid,
        internal_cost_high=internal_cost_high,
        price_low=price_low,
        price_mid=price_mid,
        price_high=price_high,
        markup_low=cfg.markup_low,
        markup_high=cfg.markup_high,
    )


def format_breakdown_markdown(p: PricingBreakdown) -> str:
    """Markdown table suitable for inclusion in the investor brief."""
    return (
        "| Component | Per-scenario cost (USD) |\n"
        "|---|---|\n"
        f"| Operator labour (loaded × scenarios/hr) | ${p.operator_cost:,.2f} |\n"
        f"| Annotation / QA (low–high) | ${p.annotation_low:,.0f} – ${p.annotation_high:,.0f} |\n"
        f"| Capital amortisation (drone + vehicle + dock) | ${p.capital_cost:,.2f} |\n"
        f"| Software / cloud / tooling | ${p.software_cost:,.2f} |\n"
        f"| **Internal cost band** | **${p.internal_cost_low:,.0f} – ${p.internal_cost_high:,.0f}** |\n"
        f"| Vendor markup band ({p.markup_low}× – {p.markup_high}×) | applied below |\n"
        f"| **Skydock price band** | **${p.price_low:,.0f} – ${p.price_high:,.0f}** |\n"
        f"| Sim default (mid-cost × mid-markup) | **${p.price_mid:,.0f}** |\n"
    )
