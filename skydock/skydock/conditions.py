"""Time-of-day, weather, and wind model. Feeds pre-flight check probability."""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

from .config import ConditionsConfig, SimulationConfig, WorldConfig


@dataclass
class Conditions:
    """Snapshot of environmental state at a given sim time."""
    wind_mph: float
    weather_clear: bool
    is_daylight: bool
    hour_of_day: float


class ConditionsModel:
    """Generates time-varying conditions. Weather is sampled once per sim hour."""

    def __init__(
        self,
        cond_cfg: ConditionsConfig,
        world_cfg: WorldConfig,
        sim_cfg: SimulationConfig,
        rng: random.Random,
    ):
        self.cfg = cond_cfg
        self.world = world_cfg
        self.sim = sim_cfg
        self.rng = rng
        self._weather_clear = rng.random() < cond_cfg.weather_clear_prob
        self._next_weather_resample_hour = sim_cfg.start_hour + 1.0

    def current(self, t_s: float) -> Conditions:
        hour = (self.sim.start_hour + t_s / 3600.0) % 24.0
        # Diurnal wind: peaks mid-afternoon.
        diurnal = math.sin(math.pi * max(0.0, (hour - 6.0) / 12.0))
        wind = self.cfg.wind_mph_base + self.cfg.wind_mph_amplitude * max(0.0, diurnal)
        wind += self.rng.gauss(0, 1.5)
        wind = max(0.0, wind)

        if hour >= self._next_weather_resample_hour:
            self._weather_clear = self.rng.random() < self.cfg.weather_clear_prob
            self._next_weather_resample_hour = math.floor(hour) + 1.0

        is_day = self.world.daylight_start_hour <= hour <= self.world.daylight_end_hour
        return Conditions(
            wind_mph=wind,
            weather_clear=self._weather_clear,
            is_daylight=is_day,
            hour_of_day=hour,
        )
