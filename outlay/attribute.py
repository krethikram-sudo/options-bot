"""Attribution orchestration — turn raw events + work items into costed,
joined, classified `Attribution` rows, plus per-ticket rollups.

This is the spine the dashboard and forecast read from. It deliberately does
*not* drop unjoined spend: events that only reach TEAM or INVOICE fidelity still
appear (with `ticket_id=None`) so totals reconcile to the provider invoice. A
report that silently omits unattributable spend is the fastest way to lose a
finance owner's trust.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Optional

from .classify import classify
from .join import JoinEngine
from .models import Attribution, FidelityTier, TaskClass, UsageEvent, WorkItem
from .pricing import cost_usd


@dataclass
class TicketRollup:
    """Per-ticket spend summary."""

    ticket_id: str
    task_class: TaskClass
    status: str
    cost_usd: float = 0.0
    event_count: int = 0
    rework_iterations: int = 1   # distinct agent sessions seen for this ticket
    team_id: Optional[str] = None
    _sessions: set = field(default_factory=set, repr=False)


@dataclass
class AttributionResult:
    rows: list[Attribution]
    rollups: dict[str, TicketRollup]

    @property
    def total_cost(self) -> float:
        return sum(r.cost_usd for r in self.rows)

    def cost_by_fidelity(self) -> dict[FidelityTier, float]:
        out: dict[FidelityTier, float] = defaultdict(float)
        for r in self.rows:
            out[r.fidelity] += r.cost_usd
        return dict(out)

    @property
    def attributed_to_ticket(self) -> float:
        return sum(r.cost_usd for r in self.rows if r.ticket_id)

    @property
    def ticket_coverage(self) -> float:
        """Fraction of spend that reached a ticket — the headline trust metric."""
        total = self.total_cost
        return (self.attributed_to_ticket / total) if total else 0.0


def attribute(
    events: list[UsageEvent],
    work_items: list[WorkItem],
    engine: Optional[JoinEngine] = None,
) -> AttributionResult:
    """Run the full join+cost pass over a batch of events."""
    engine = engine or JoinEngine(work_items)
    class_by_ticket = {wi.ticket_id: classify(wi) for wi in work_items}
    status_by_ticket = {wi.ticket_id: wi.status for wi in work_items}
    team_by_ticket = {wi.ticket_id: wi.team_id for wi in work_items}

    # Pass 1: join every event.
    joined = [(ev, engine.join(ev)) for ev in events]

    # Session propagation — a coding-agent session (Claude Code / Cursor run)
    # works one ticket at a time, but only some of its events carry the branch or
    # explicit tag; the rest would fall to TEAM/INVOICE and lose the ticket. When
    # a session resolved to exactly ONE ticket (via CALL/BRANCH), lend it to that
    # session's otherwise-unticketed events at SESSION fidelity (honest: a tier
    # below BRANCH). Ambiguous sessions (>1 resolved ticket) are left untouched.
    session_tickets: dict[str, set[str]] = defaultdict(set)
    for ev, jr in joined:
        if ev.session_id and jr.ticket_id and jr.fidelity.has_ticket:
            session_tickets[ev.session_id].add(jr.ticket_id)
    session_ticket = {
        sid: next(iter(ts)) for sid, ts in session_tickets.items() if len(ts) == 1
    }

    rows: list[Attribution] = []
    rollups: dict[str, TicketRollup] = {}

    for ev, jr in joined:
        ticket_id, fidelity, team = jr.ticket_id, jr.fidelity, jr.team_id
        if ticket_id is None and ev.session_id in session_ticket:
            ticket_id = session_ticket[ev.session_id]
            fidelity = FidelityTier.SESSION
            team = team or team_by_ticket.get(ticket_id)

        tc = class_by_ticket.get(ticket_id, TaskClass.UNKNOWN) if ticket_id else TaskClass.UNKNOWN
        cost = cost_usd(ev)
        rows.append(
            Attribution(
                usage_event_id=ev.id,
                cost_usd=cost,
                fidelity=fidelity,
                model=ev.model,
                ts=ev.ts,
                ticket_id=ticket_id,
                team_id=team,
                user=jr.user,
                task_class=tc,
            )
        )

        if ticket_id:
            ru = rollups.get(ticket_id)
            if ru is None:
                ru = TicketRollup(
                    ticket_id=ticket_id,
                    task_class=tc,
                    status=status_by_ticket.get(ticket_id, "open"),
                    team_id=team,
                )
                rollups[ticket_id] = ru
            ru.cost_usd += cost
            ru.event_count += 1
            if ev.session_id:
                ru._sessions.add(ev.session_id)
            ru.rework_iterations = max(1, len(ru._sessions))

    return AttributionResult(rows=rows, rollups=rollups)
