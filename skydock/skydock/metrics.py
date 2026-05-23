"""Rolling KPI aggregator — feeds both the live dashboard and end-of-run reports."""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field


@dataclass
class Metrics:
    missions_started: int = 0
    missions_succeeded: int = 0
    missions_aborted: int = 0
    abort_reasons: Counter = field(default_factory=Counter)
    scenes_by_class: Counter = field(default_factory=Counter)
    trigger_types: Counter = field(default_factory=Counter)
    triggers_skipped_drone_busy: int = 0
    triggers_skipped_outside_envelope: int = 0
    delivered_quality_scores: list[float] = field(default_factory=list)

    def on_mission_start(self, trigger_type: str) -> None:
        self.missions_started += 1
        self.trigger_types[trigger_type] += 1

    def on_mission_success(self, scene_class: str) -> None:
        self.missions_succeeded += 1
        self.scenes_by_class[scene_class] += 1

    def on_mission_abort(self, reason: str) -> None:
        self.missions_aborted += 1
        self.abort_reasons[reason] += 1

    def on_delivery(self, quality: float) -> None:
        self.delivered_quality_scores.append(quality)

    def success_rate(self) -> float:
        if self.missions_started == 0:
            return 0.0
        return self.missions_succeeded / self.missions_started

    def avg_delivered_quality(self) -> float:
        if not self.delivered_quality_scores:
            return 0.0
        return sum(self.delivered_quality_scores) / len(self.delivered_quality_scores)
