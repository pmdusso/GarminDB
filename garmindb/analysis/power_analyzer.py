# garmindb/analysis/power_analyzer.py
"""Cycling power analysis from raw Garmin activity JSONs.

Power data is NOT imported into the GarminDB tables, but the per-activity
JSON summaries (~/HealthData/FitFiles/Activities/activity_*.json) carry
Garmin's pre-computed power fields (normPower, maxAvgPower_<seconds>,
powerTimeInZone_<n>). This analyzer reads those at report time.
"""

import glob
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from .models import Insight, InsightSeverity

# Durations (seconds) shown on the power curve.
CURVE_DURATIONS = [5, 60, 300, 1200, 3600]
DURATION_LABELS = {5: "5s", 60: "1min", 300: "5min", 1200: "20min", 3600: "60min"}

CYCLING_TYPES = {
    "cycling", "virtual_ride", "road_biking", "indoor_cycling",
    "gravel_cycling", "mountain_biking",
}


@dataclass
class PowerRide:
    """One ride's parsed power summary."""

    date: date
    sport: str
    avg_power: Optional[float]
    norm_power: Optional[float]
    peak_power: Dict[int, float]          # duration_s -> best avg watts
    power_time_in_zone: Dict[int, float]  # zone (1..7) -> seconds


@dataclass
class PowerAnalysisResult:
    """Output of PowerAnalyzer.analyze()."""

    period_start: date
    period_end: date
    configured_ftp: Optional[float]
    estimated_ftp: Optional[float]        # best 20-min recent * 0.95
    best_20min_recent: Optional[float]
    best_20min_alltime: Optional[float]
    power_curve_recent: Dict[int, float]
    power_curve_alltime: Dict[int, float]
    power_zone_distribution: Dict[int, float]  # zone -> percent of time
    rides_with_power: int
    total_rides: int
    ftp_needs_test: bool
    insights: List[Insight] = field(default_factory=list)


class PowerAnalyzer:
    """Reads activity JSONs and computes power curve, FTP, zone mix."""

    RECENT_WINDOW_DAYS = 90

    def __init__(self, activities_dir: str, configured_ftp: Optional[float] = None):
        """Args:
            activities_dir: Folder with activity_*.json files.
            configured_ftp: User's declared FTP (authoritative if set).
        """
        self._dir = activities_dir
        self._ftp = configured_ftp

    @staticmethod
    def _parse_ride(data) -> Optional["PowerRide"]:
        """Parse one activity JSON payload into a PowerRide, or None.

        Returns None for non-cycling activities or cycling rides with no
        power data. Accepts either a dict or a 1-element list payload.
        """
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            return None
        sport = (data.get("activityType") or {}).get("typeKey", "")
        if sport not in CYCLING_TYPES:
            return None

        peak = {}
        for d in CURVE_DURATIONS:
            val = data.get(f"maxAvgPower_{d}")
            if val is not None:
                peak[d] = float(val)
        if not peak and data.get("normPower") is None:
            return None  # cycling ride but no usable power

        zones = {}
        for z in range(1, 8):
            val = data.get(f"powerTimeInZone_{z}")
            if val is not None:
                zones[z] = float(val)

        start = (data.get("startTimeLocal") or "")[:10]
        try:
            ride_date = datetime.strptime(start, "%Y-%m-%d").date()
        except ValueError:
            return None

        return PowerRide(
            date=ride_date,
            sport=sport,
            avg_power=data.get("avgPower"),
            norm_power=data.get("normPower"),
            peak_power=peak,
            power_time_in_zone=zones,
        )

    def _best_curve(self, rides: List["PowerRide"]) -> Dict[int, float]:
        """Best (max) average power per duration across rides."""
        curve: Dict[int, float] = {}
        for d in CURVE_DURATIONS:
            vals = [r.peak_power[d] for r in rides if d in r.peak_power]
            if vals:
                curve[d] = max(vals)
        return curve
