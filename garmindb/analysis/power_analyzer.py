"""Cycling power analysis from raw Garmin activity JSONs.

Power data is NOT imported into the GarminDB tables, but the per-activity
JSON summaries (~/HealthData/FitFiles/Activities/activity_*.json) carry
Garmin's pre-computed power fields (normPower, maxAvgPower_<seconds>,
powerTimeInZone_<n>). This analyzer reads those at report time.
"""

import glob
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Tuple

from .models import Insight, InsightSeverity

logger = logging.getLogger(__name__)

# Durations (seconds) shown on the power curve.
CURVE_DURATIONS = [5, 60, 300, 1200, 3600]

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
    skipped_files: int = 0                 # corrupt/unreadable JSONs ignored
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

    def _load_rides(self) -> Tuple[List["PowerRide"], int]:
        """Glob the activities dir and parse all cycling rides with power.

        Returns the list of parsed rides plus a count of files that could
        not be read or decoded. Each unreadable file is logged at WARNING
        so a silently-corrupt JSON never understates FTP/W-kg/curve without
        a trace.
        """
        rides: List[PowerRide] = []
        skipped = 0
        if not os.path.isdir(self._dir):
            logger.warning("Activities dir does not exist: %s", self._dir)
            return rides, skipped
        for path in glob.glob(os.path.join(self._dir, "activity_*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError) as err:
                skipped += 1
                logger.warning("Skipping unreadable activity JSON %s: %s",
                               path, err)
                continue
            ride = self._parse_ride(data)
            if ride is not None:
                rides.append(ride)
        if skipped:
            logger.warning("Skipped %d unreadable activity JSON file(s) in %s",
                           skipped, self._dir)
        return rides, skipped

    @staticmethod
    def _zone_distribution(rides: List["PowerRide"]) -> Dict[int, float]:
        """Aggregate time-in-power-zone across rides into percentages."""
        totals: Dict[int, float] = {}
        for ride in rides:
            for zone, secs in ride.power_time_in_zone.items():
                totals[zone] = totals.get(zone, 0.0) + secs
        grand = sum(totals.values())
        if grand == 0:
            return {}
        return {z: round(secs / grand * 100, 1) for z, secs in sorted(totals.items())}

    def analyze(self, start_date: date, end_date: date) -> "PowerAnalysisResult":
        """Build a PowerAnalysisResult for the period.

        'recent' = last RECENT_WINDOW_DAYS before end_date (current form);
        'alltime' = every ride on disk (personal bests).
        """
        all_rides, skipped_files = self._load_rides()
        recent_start = end_date - timedelta(days=self.RECENT_WINDOW_DAYS)
        recent = [r for r in all_rides if recent_start <= r.date <= end_date]

        curve_recent = self._best_curve(recent)
        curve_all = self._best_curve(all_rides)
        best20_recent = curve_recent.get(1200)
        best20_all = curve_all.get(1200)
        est_ftp = round(best20_recent * 0.95) if best20_recent else None
        ftp_needs_test = bool(
            self._ftp and best20_recent and self._ftp > best20_recent
        )

        result = PowerAnalysisResult(
            period_start=start_date,
            period_end=end_date,
            configured_ftp=self._ftp,
            estimated_ftp=est_ftp,
            best_20min_recent=best20_recent,
            best_20min_alltime=best20_all,
            power_curve_recent=curve_recent,
            power_curve_alltime=curve_all,
            power_zone_distribution=self._zone_distribution(recent),
            rides_with_power=len(recent),
            total_rides=len(all_rides),
            ftp_needs_test=ftp_needs_test,
            skipped_files=skipped_files,
        )
        logger.debug(
            "Power analysis %s..%s: %d ride(s) total, %d recent with power, "
            "%d file(s) skipped",
            start_date, end_date, len(all_rides), len(recent), skipped_files,
        )
        result.insights = self._build_insights(result)
        return result

    def _build_insights(self, result: "PowerAnalysisResult") -> List[Insight]:
        """Generate power insights (FTP test recommendation, etc.)."""
        insights: List[Insight] = []
        if result.ftp_needs_test:
            insights.append(Insight(
                title="Confirme sua FTP com um teste",
                description=(
                    f"Sua FTP configurada ({result.configured_ftp:.0f} W) é maior "
                    f"que o melhor esforço de 20 min dos seus dados recentes "
                    f"({result.best_20min_recent:.0f} W). Um teste de FTP "
                    f"confirmaria o número atual."
                ),
                severity=InsightSeverity.INFO,
                category="power",
                data_points={
                    "configured_ftp": result.configured_ftp,
                    "best_20min_recent": result.best_20min_recent,
                },
                recommendations=[
                    "Faça um teste de 20 min ou rampa nas próximas 2 semanas",
                ],
            ))
        return insights
