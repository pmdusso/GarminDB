"""Data Transfer Objects (DTOs) for health data.

These dataclasses provide a clean interface between the data layer
and the analysis layer, decoupling from SQLAlchemy models.
"""

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Optional


@dataclass
class SleepRecord:
    """Sleep data for a single night."""

    date: date
    total_sleep: timedelta
    deep_sleep: timedelta
    light_sleep: timedelta
    rem_sleep: timedelta
    awake_time: timedelta
    sleep_score: Optional[int] = None
    bedtime: Optional[time] = None
    wake_time: Optional[time] = None

    @property
    def total_hours(self) -> float:
        """Total sleep in hours."""
        return self.total_sleep.total_seconds() / 3600

    @property
    def deep_sleep_percent(self) -> float:
        """Deep sleep as percentage of total."""
        if self.total_sleep.total_seconds() == 0:
            return 0.0
        deep_secs = self.deep_sleep.total_seconds()
        total_secs = self.total_sleep.total_seconds()
        return (deep_secs / total_secs) * 100

    @property
    def rem_sleep_percent(self) -> float:
        """REM sleep as percentage of total."""
        if self.total_sleep.total_seconds() == 0:
            return 0.0
        rem_secs = self.rem_sleep.total_seconds()
        total_secs = self.total_sleep.total_seconds()
        return (rem_secs / total_secs) * 100


@dataclass
class HeartRateRecord:
    """Heart rate measurement."""

    timestamp: datetime
    heart_rate: int
    resting_hr: Optional[int] = None


@dataclass
class StressRecord:
    """Stress level measurement."""

    timestamp: datetime
    stress_level: int  # 0-100

    @property
    def stress_category(self) -> str:
        """Categorize stress level."""
        if self.stress_level <= 25:
            return "low"
        elif self.stress_level <= 50:
            return "medium"
        elif self.stress_level <= 75:
            return "high"
        else:
            return "very_high"


@dataclass
class BodyBatteryRecord:
    """Body battery measurement."""

    timestamp: datetime
    level: int  # 0-100
    charged: Optional[int] = None
    drained: Optional[int] = None


@dataclass
class ActivityRecord:
    """Single activity record."""

    activity_id: str
    name: Optional[str]
    sport: str
    start_time: datetime
    duration: timedelta
    distance: Optional[float] = None  # km
    calories: Optional[int] = None
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    training_effect: Optional[float] = None
    anaerobic_effect: Optional[float] = None
    training_load: Optional[int] = None

    @property
    def pace_per_km(self) -> Optional[timedelta]:
        """Calculate pace per km for distance activities."""
        if not self.distance or self.distance <= 0:
            return None
        seconds_per_km = self.duration.total_seconds() / self.distance
        return timedelta(seconds=seconds_per_km)


@dataclass
class DailySummaryRecord:
    """Daily aggregated health summary."""

    date: date
    resting_hr: Optional[int] = None
    stress_avg: Optional[int] = None
    bb_max: Optional[int] = None
    bb_min: Optional[int] = None
    bb_charged: Optional[int] = None  # Overnight recharge amount
    steps: Optional[int] = None
    floors: Optional[int] = None
    distance: Optional[float] = None  # km
    calories_active: Optional[int] = None
    calories_total: Optional[int] = None
    sleep_avg: Optional[timedelta] = None
    intensity_mins: Optional[int] = None
