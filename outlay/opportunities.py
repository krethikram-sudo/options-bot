"""Advisory optimization opportunities — spec §3e. Read-only flags, not in-path.

From attributed usage, surface **candidate** ways to cut the bill that the customer
implements themselves (we never route or enforce here):

  - **Prompt-caching candidates** — spend paying full price for input that *may* be
    repeated context, where caching reads at a fraction of the input rate.
  - **Batch-API candidates** — spend in latency-tolerant work classes that could
    move to a batch lane priced well below synchronous.

The honesty bar: these are **candidates with an upper-bound potential**, not
asserted realized savings. Whether input is actually cacheable (repeated context)
and whether a workload can tolerate batch latency are the **customer's** call — we
surface the addressable base and the best-case number, clearly labeled, and let
them decide. Cheaper-*model* routing is handled separately by `recommend.py`.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import TaskClass
from .pricing import rate_for

if TYPE_CHECKING:
    from .attribute import AttributionResult
    from .models import UsageEvent

# Work classes that are *often* async-tolerant (no human waiting on the result).
# A default suggestion only — the customer confirms which of their workloads can
# actually tolerate batch latency.
_DEFAULT_ASYNC_CLASSES = (TaskClass.TEST, TaskClass.CHORE)
_BATCH_DISCOUNT = 0.50  # typical batch-API discount vs. synchronous; provider-dependent.


@dataclass
class CachingOpportunity:
    """A model whose uncached input spend is a prompt-caching candidate."""

    model: str
    uncached_input_usd: float       # addressable base — full-price input spend
    cache_utilization: float        # cache_read ÷ (uncached_input + cache_read) tokens
    cache_read_mult: float          # cached reads bill at this × the input rate
    potential_savings_usd: float    # UPPER BOUND: if all of it were repeated/cacheable context


@dataclass
class BatchOpportunity:
    """A work class whose spend is a batch-API candidate (if latency-tolerant)."""

    task_class: str
    spend_usd: float                # addressable base
    batch_discount: float
    potential_savings_usd: float    # UPPER BOUND: spend × discount, if it can move to batch


def caching_opportunities(events: "list[UsageEvent]", *,
                          min_usd: float = 1.0,
                          max_utilization: float = 0.5) -> list[CachingOpportunity]:
    """Flag models paying full price for input that may be cacheable.

    For each model we sum uncached input vs. cache-read tokens. A *low* cache
    utilization with a *material* uncached-input bill is the candidate signal. The
    potential is an explicit upper bound (all uncached input treated as cacheable
    repeated context); realistically only the repeated portion is — surfaced as a
    flag to investigate, not a promise.
    """
    by_model_in: dict[str, int] = defaultdict(int)
    by_model_cache: dict[str, int] = defaultdict(int)
    for e in events:
        by_model_in[e.model] += max(0, e.input_tokens)
        by_model_cache[e.model] += max(0, e.cache_read_tokens)

    out: list[CachingOpportunity] = []
    for model, uncached_tok in by_model_in.items():
        cache_tok = by_model_cache[model]
        denom = uncached_tok + cache_tok
        util = (cache_tok / denom) if denom > 0 else 0.0
        r = rate_for(model)
        uncached_usd = uncached_tok * r.input_per_m / 1_000_000.0
        if uncached_usd < min_usd or util >= max_utilization:
            continue
        potential = uncached_usd * (1.0 - r.cache_read_mult)
        out.append(CachingOpportunity(
            model=model,
            uncached_input_usd=round(uncached_usd, 2),
            cache_utilization=round(util, 4),
            cache_read_mult=r.cache_read_mult,
            potential_savings_usd=round(potential, 2),
        ))
    return sorted(out, key=lambda o: o.potential_savings_usd, reverse=True)


def batch_opportunities(result: "AttributionResult", *,
                        async_classes: tuple[TaskClass, ...] = _DEFAULT_ASYNC_CLASSES,
                        batch_discount: float = _BATCH_DISCOUNT,
                        min_usd: float = 1.0) -> list[BatchOpportunity]:
    """Flag spend in latency-tolerant work classes as batch-API candidates."""
    by_class: dict[TaskClass, float] = defaultdict(float)
    for row in result.rows:
        by_class[row.task_class] += row.cost_usd

    out: list[BatchOpportunity] = []
    for tc in async_classes:
        spend = by_class.get(tc, 0.0)
        if spend < min_usd:
            continue
        out.append(BatchOpportunity(
            task_class=tc.value,
            spend_usd=round(spend, 2),
            batch_discount=batch_discount,
            potential_savings_usd=round(spend * batch_discount, 2),
        ))
    return sorted(out, key=lambda o: o.potential_savings_usd, reverse=True)


def format_opportunities(caching: list[CachingOpportunity],
                         batch: list[BatchOpportunity]) -> str:
    """Human-readable advisory block for the CLI report."""
    lines = [
        "Optimization opportunities  (advisory — candidates to review, not realized savings)",
        "=" * 78,
    ]
    if not caching and not batch:
        lines.append("  No caching or batch candidates above the reporting threshold.")
        return "\n".join(lines)

    if caching:
        lines.append("  Prompt-caching candidates (full-price input that MAY be repeated context):")
        for o in caching:
            lines.append(
                f"    {o.model:<22} uncached input ${o.uncached_input_usd:,.0f} · "
                f"cache use {o.cache_utilization:.0%} → up to ${o.potential_savings_usd:,.0f} "
                f"if cacheable")
        lines.append("    (Upper bound: only the repeated-context portion is actually cacheable — measure it.)")
    if batch:
        if caching:
            lines.append("")
        lines.append("  Batch-API candidates (latency-tolerant classes, ~50% off if they can move):")
        for o in batch:
            lines.append(
                f"    {o.task_class:<22} ${o.spend_usd:,.0f} spend → up to "
                f"${o.potential_savings_usd:,.0f} at {o.batch_discount:.0%} off")
        lines.append("    (Confirm which of these workloads can tolerate batch latency before moving.)")
    return "\n".join(lines)
