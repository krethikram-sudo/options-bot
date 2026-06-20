"""Cost-fidelity proof — the substantiated, on-your-own-data case for Outlay.

The most common way naive spend trackers get the number wrong is to multiply
*all* input-side tokens by the base input rate. On an agentic coding workload
that re-sends a large cached prefix every turn, cache-read tokens dominate the
count — and they bill at ~0.1x. Collapsing them into base-rate input inflates
the reported bill several-fold.

This module quantifies that gap on a set of real `UsageEvent`s: the cache-aware
("Outlay") cost vs. the naive token-count cost, plus the token mix that explains
the difference. It's deliberately conservative — the naive baseline is the
*charitable* one (it still counts cache tokens, just at the wrong rate); a
tracker that ignores cache tokens entirely would be wrong in the other
direction. The point isn't a strawman, it's that on cache-heavy workloads the
costing model is the whole ballgame.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import UsageEvent
from .pricing import cost_usd, rate_for


@dataclass
class ModelFidelity:
    """Per-model slice of the cost-fidelity comparison."""

    model: str
    events: int = 0
    outlay_usd: float = 0.0
    naive_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0


@dataclass
class CostFidelity:
    """Cache-aware (correct) vs naive token-count costing over real usage.

    `naive_usd` prices every input-side token (base input + cache read + cache
    write) at the model's base input rate — the canonical mistake. `outlay_usd`
    is the cache-aware cost. The ratio is how badly the naive number misleads.
    """

    events: int = 0
    outlay_usd: float = 0.0
    naive_usd: float = 0.0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    by_model: dict[str, ModelFidelity] = field(default_factory=dict)

    @property
    def input_side_tokens(self) -> int:
        return self.input_tokens + self.cache_read_tokens + self.cache_write_tokens

    @property
    def cache_read_share(self) -> float:
        """Fraction of input-side tokens that are cache reads — the driver of the gap."""
        tot = self.input_side_tokens
        return self.cache_read_tokens / tot if tot else 0.0

    @property
    def overstatement_usd(self) -> float:
        return self.naive_usd - self.outlay_usd

    @property
    def inflation_factor(self) -> float:
        """How many times larger the naive number is (naive / correct)."""
        return self.naive_usd / self.outlay_usd if self.outlay_usd else 0.0

    def as_dict(self) -> dict:
        return {
            "events": self.events,
            "outlay_usd": round(self.outlay_usd, 2),
            "naive_usd": round(self.naive_usd, 2),
            "overstatement_usd": round(self.overstatement_usd, 2),
            "inflation_factor": round(self.inflation_factor, 2),
            "cache_read_share": round(self.cache_read_share, 4),
            "tokens": {
                "input": self.input_tokens,
                "output": self.output_tokens,
                "cache_read": self.cache_read_tokens,
                "cache_write": self.cache_write_tokens,
            },
            "by_model": {
                m: {
                    "events": mf.events,
                    "outlay_usd": round(mf.outlay_usd, 2),
                    "naive_usd": round(mf.naive_usd, 2),
                    "inflation_factor": round(mf.naive_usd / mf.outlay_usd, 2) if mf.outlay_usd else 0.0,
                }
                for m, mf in sorted(self.by_model.items(), key=lambda kv: kv[1].outlay_usd, reverse=True)
            },
        }


def _naive_event_usd(event: UsageEvent) -> float:
    """Cost if every input-side token were billed at the base input rate."""
    r = rate_for(event.model)
    input_side = event.input_tokens + event.cache_read_tokens + event.cache_write_tokens
    return (input_side * r.input_per_m + event.output_tokens * r.output_per_m) / 1_000_000.0


def cost_fidelity(events) -> CostFidelity:
    """Quantify the cache-aware vs naive costing gap over `events`."""
    cf = CostFidelity()
    for e in events:
        mf = cf.by_model.setdefault(e.model, ModelFidelity(model=e.model))
        oc, nc = cost_usd(e), _naive_event_usd(e)
        cf.events += 1
        cf.outlay_usd += oc
        cf.naive_usd += nc
        cf.input_tokens += e.input_tokens
        cf.output_tokens += e.output_tokens
        cf.cache_read_tokens += e.cache_read_tokens
        cf.cache_write_tokens += e.cache_write_tokens
        mf.events += 1
        mf.outlay_usd += oc
        mf.naive_usd += nc
        mf.input_tokens += e.input_tokens
        mf.output_tokens += e.output_tokens
        mf.cache_read_tokens += e.cache_read_tokens
        mf.cache_write_tokens += e.cache_write_tokens
    return cf


def format_cost_fidelity(cf: CostFidelity) -> str:
    """A terminal-friendly summary of the cost-fidelity proof."""
    if not cf.events:
        return "Cost fidelity: no usage events to compare."
    lines = [
        "COST FIDELITY  —  cache-aware vs naive token-count costing",
        f"  Outlay (correct):   ${cf.outlay_usd:,.2f}",
        f"  Naive token-count:  ${cf.naive_usd:,.2f}",
        f"  Inflation:          {cf.inflation_factor:.1f}x  "
        f"(naive overstates by ${cf.overstatement_usd:,.0f})",
        f"  Cache-read share:   {cf.cache_read_share:.0%} of input-side tokens "
        f"({cf.cache_read_tokens:,} of {cf.input_side_tokens:,})",
        f"  Events:             {cf.events:,}",
    ]
    return "\n".join(lines)
