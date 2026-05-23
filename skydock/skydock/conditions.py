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
    wind_dir_rad: float            # 0 = wind blowing east, pi/2 = blowing north
    weather_clear: bool
    is_daylight: bool
    hour_of_day: float
    traffic_factor: float = 1.0    # diurnal rush-hour modulation, multiplies trigger / density


def _traffic_factor_for_hour(hour: float) -> float:
    """Commuter rush pattern. Two peaks (morning + evening) with a midday dip."""
    if 7.0 <= hour < 9.0:
        return 1.6
    if 9.0 <= hour < 11.0:
        return 1.0
    if 11.0 <= hour < 14.0:
        return 0.7
    if 14.0 <= hour < 16.0:
        return 1.0
    if 16.0 <= hour < 18.5:
        return 1.6
    return 0.5


class ConditionsModel:
    """Generates time-varying conditions. Weather is resampled once per sim hour
    using elapsed sim time (not wall-clock hour-of-day), so multi-day sims
    correctly cycle through new weather instead of locking to day-1's roll.
    """

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
        self._next_weather_resample_t_s = 3600.0
        # Wind direction drifts slowly over the day around a base bearing.
        self._wind_dir_base_rad = rng.uniform(0.0, 2 * math.pi)
        # Gust state (AR(1) impulse process).
        self._gust_mag_mph: float = 0.0
        self._last_gust_check_t: float = 0.0

    def current(self, t_s: float) -> Conditions:
        hour = (self.sim.start_hour + t_s / 3600.0) % 24.0
        # Diurnal wind: peaks mid-afternoon.
        diurnal = math.sin(math.pi * max(0.0, (hour - 6.0) / 12.0))
        wind = self.cfg.wind_mph_base + self.cfg.wind_mph_amplitude * max(0.0, diurnal)
        wind += self.rng.gauss(0, 1.5)
        wind = max(0.0, wind)

        # Resample weather hourly using elapsed time so day-2+ cycles correctly.
        while t_s >= self._next_weather_resample_t_s:
            self._weather_clear = self.rng.random() < self.cfg.weather_clear_prob
            self._next_weather_resample_t_s += 3600.0

        # Gust state (AR(1) decay + occasional impulses).
        gap = t_s - self._last_gust_check_t
        if gap > 0:
            decay = self.cfg.gust_decay_per_second ** gap
            self._gust_mag_mph *= decay
            # Independent gust trigger; cumulative prob over the gap.
            p_no_gust = (1.0 - self.cfg.gust_prob_per_second) ** gap
            if self.rng.random() > p_no_gust:
                impulse = self.rng.uniform(
                    self.cfg.gust_magnitude_mph_min,
                    self.cfg.gust_magnitude_mph_max,
                )
                self._gust_mag_mph = max(self._gust_mag_mph, impulse)
            self._last_gust_check_t = t_s
        wind += self._gust_mag_mph

        is_day = self.world.daylight_start_hour <= hour <= self.world.daylight_end_hour
        # Slow ±30° wander over the day around a base bearing.
        wander = math.sin(t_s / 3600.0 * 0.6) * math.radians(30)
        wind_dir = (self._wind_dir_base_rad + wander) % (2 * math.pi)
        return Conditions(
            wind_mph=wind,
            wind_dir_rad=wind_dir,
            weather_clear=self._weather_clear,
            is_daylight=is_day,
            hour_of_day=hour,
            traffic_factor=_traffic_factor_for_hour(hour),
        )
