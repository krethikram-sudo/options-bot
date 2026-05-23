"""Cloud data pipeline (spec 9.2) — upload, process, score, deliver."""
from __future__ import annotations

import random
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from .config import PipelineConfig, ProbabilityConfig
from .deliverable import emit_scenario_package
from .mission import Mission


@dataclass
class PipelineJob:
    mission: Mission
    received_at_s: float
    finish_at_s: float
    quality_score: float
    delivered: bool = False
    failed_reason: Optional[str] = None
    package_path: Optional[Path] = None


class DataPipeline:
    """Async job processor — jobs finish when sim time passes their finish timestamp."""

    def __init__(
        self,
        pipe_cfg: PipelineConfig,
        prob_cfg: ProbabilityConfig,
        rng: random.Random,
        emit_packages_to: Path | str | None = None,
    ):
        self.cfg = pipe_cfg
        self.prob = prob_cfg
        self.rng = rng
        self.emit_dir = Path(emit_packages_to) if emit_packages_to else None
        self.queue: list[PipelineJob] = []
        self.completed: list[PipelineJob] = []
        self.delivered_count: int = 0
        self.rejected_count: int = 0
        self.upload_failed_count: int = 0

    def enqueue(self, mission: Mission, t_s: float) -> PipelineJob:
        process_min = self.rng.uniform(
            self.cfg.process_minutes_min, self.cfg.process_minutes_max
        )
        finish_at = t_s + process_min * 60.0
        # Quality scoring — clipped 0..100.
        quality = self.rng.gauss(self.cfg.quality_mean, self.cfg.quality_std)
        quality = max(0.0, min(100.0, quality))
        job = PipelineJob(
            mission=mission,
            received_at_s=t_s,
            finish_at_s=finish_at,
            quality_score=quality,
        )
        self.queue.append(job)
        return job

    def step(self, t_s: float) -> list[PipelineJob]:
        finished: list[PipelineJob] = []
        remaining: list[PipelineJob] = []
        for job in self.queue:
            if t_s >= job.finish_at_s:
                if self.rng.random() >= self.prob.upload_success:
                    job.failed_reason = "upload_failed"
                    self.upload_failed_count += 1
                elif job.quality_score < self.cfg.quality_threshold:
                    job.failed_reason = "quality_below_threshold"
                    self.rejected_count += 1
                else:
                    job.delivered = True
                    self.delivered_count += 1
                    if self.emit_dir is not None:
                        job.package_path = emit_scenario_package(
                            job.mission, job.quality_score, self.emit_dir, self.rng,
                        )
                self.completed.append(job)
                finished.append(job)
            else:
                remaining.append(job)
        self.queue = remaining
        return finished

    def in_flight(self) -> int:
        return len(self.queue)

    def avg_quality(self) -> float:
        delivered = [j.quality_score for j in self.completed if j.delivered]
        if not delivered:
            return 0.0
        return sum(delivered) / len(delivered)
