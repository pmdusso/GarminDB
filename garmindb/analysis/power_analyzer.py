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

# Moderate publication-gate thresholds (user decision 2026-06-09).
GATE_RECENCY_DAYS = 42        # 6 weeks
GATE_MIN_CANDIDATES = 3       # >=3 rides carrying maxAvgPower_1200 in window
GATE_MIN_IF = 0.90           # IF = normPower / configured FTP
EFTP_MULTIPLIER = 0.95       # best 20-min * 0.95

# Rider-relative plausibility ceiling for the 5 s neuromuscular peak: a best
# 5 s above this multiple of the rider's own best 1-min power is almost always
# a trainer/dropout spike (real data: a 1448 W indoor spike), not a sprint.
# Such 5 s values are dropped and the next-best plausible 5 s is used instead.
PEAK_5S_TO_1MIN_RATIO = 2.2

CYCLING_TYPES = {
    "cycling", "virtual_ride", "road_biking", "indoor_cycling",
    "gravel_cycling", "mountain_biking",
}

# Indoor detection: explicit indoor sport types OR a trainer-app manufacturer.
# GPS presence does NOT separate them (TACX rides carry simulated GPS).
_INDOOR_TYPES = {"indoor_cycling", "virtual_ride"}
_INDOOR_MANUFACTURERS = {"TACX", "THE_SUFFERFEST", "TRAINER_ROAD", "VIRTUALTRAINING"}


def _is_indoor(type_key: str, manufacturer) -> bool:
    if type_key in _INDOOR_TYPES:
        return True
    return str(manufacturer or "").upper() in _INDOOR_MANUFACTURERS


@dataclass
class PowerRide:
    """One ride's parsed power summary."""

    date: date
    sport: str
    avg_power: Optional[float]
    norm_power: Optional[float]
    peak_power: Dict[int, float]          # duration_s -> best avg watts
    power_time_in_zone: Dict[int, float]  # zone (1..7) -> seconds
    is_indoor: bool = False               # trainer/virtual vs outdoor power-meter
    duration_s: Optional[float] = None    # timer seconds (NP>=30min gate)
    # Set by excludeFromPowerCurveReports or the sanity check below. NOTE: the
    # legacy all-rides curve (power_curve_recent/alltime) intentionally stays
    # unfiltered for back-compat; only the indoor/outdoor curves filter this.
    exclude: bool = False


@dataclass
class PowerGate:
    """Verdict of the eFTP publication gate (data-honesty for a clinician)."""

    published: bool
    source_env: Optional[str]            # "outdoor" | "indoor" | None
    candidate_count: int                 # qualifying rides in the recency window
    recency_ok: bool
    if_ok: bool
    newest_effort_date: Optional[date]
    reason: str                          # human-readable verdict (pt-BR)


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
    recent_ride_count: int                 # rides with power in the last 90 days
    total_rides: int
    ftp_needs_test: bool
    skipped_files: int = 0                 # corrupt/unreadable JSONs ignored
    curve_indoor: Dict[int, float] = field(default_factory=dict)   # all-time
    curve_outdoor: Dict[int, float] = field(default_factory=dict)  # all-time
    eftp_indoor: Optional[float] = None    # indoor best-20 * 0.95 (ungated)
    eftp_outdoor: Optional[float] = None   # outdoor best-20 * 0.95 (ungated)
    peak_5s: Optional[float] = None        # best PLAUSIBLE maxAvgPower_5 (neuromuscular)
    peak_5s_dropped: int = 0               # 5 s readings dropped as spikes (ratio cap)
    gate: Optional["PowerGate"] = None
    eftp_measured: Optional[float] = None  # gated headline eFTP
    eftp_source: Optional[str] = None      # "outdoor" | "indoor" | None
    eftp_date: Optional[date] = None       # date of the qualifying 20-min effort
    np_variability_ratio: Optional[float] = None  # mean(NP/avg) over long rides, indoor+outdoor mixed
    np_long_ride_count: int = 0            # rides with duration >= 1800s
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

        avg = data.get("avgPower")
        best20 = peak.get(1200)
        # Sanity: a 20-min best below the whole-ride average is impossible
        # (malformed export). Honor Garmin's own exclude flag too.
        exclude = bool(data.get("excludeFromPowerCurveReports"))
        if avg is not None and best20 is not None and float(best20) < float(avg):
            exclude = True

        return PowerRide(
            date=ride_date,
            sport=sport,
            avg_power=avg,
            norm_power=data.get("normPower"),
            peak_power=peak,
            power_time_in_zone=zones,
            is_indoor=_is_indoor(sport, data.get("manufacturer")),
            duration_s=(float(data["duration"])
                        if data.get("duration") is not None else None),
            exclude=exclude,
        )

    def _best_curve(self, rides: List["PowerRide"]) -> Dict[int, float]:
        """Best (max) average power per duration across rides."""
        curve: Dict[int, float] = {}
        for d in CURVE_DURATIONS:
            vals = [r.peak_power[d] for r in rides if d in r.peak_power]
            if vals:
                curve[d] = max(vals)
        return curve

    @staticmethod
    def _neuromuscular_peak(
        rides: List["PowerRide"],
    ) -> Tuple[Optional[float], int]:
        """Best plausible 5 s power + count of dropped spike readings.

        A 5 s peak above PEAK_5S_TO_1MIN_RATIO x the rider's own best 1-min
        power is almost always a trainer/dropout spike, not a sprint. Drop such
        values and return the next-best plausible 5 s. With no 1-min reference
        the ratio cannot be applied, so the raw best 5 s is returned unfiltered.
        """
        fives = sorted((r.peak_power[5] for r in rides if 5 in r.peak_power),
                       reverse=True)
        if not fives:
            return None, 0
        best_1min = max((r.peak_power[60] for r in rides if 60 in r.peak_power),
                        default=None)
        if not best_1min:
            return fives[0], 0
        ceiling = PEAK_5S_TO_1MIN_RATIO * best_1min
        plausible = [v for v in fives if v <= ceiling]
        dropped = len(fives) - len(plausible)
        return (plausible[0] if plausible else None), dropped

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

    def _gate_env(
        self, rides_env: List["PowerRide"], end_date: date, env: str,
    ) -> Tuple["PowerGate", Optional[float], Optional[date]]:
        """Evaluate the moderate publication gate for one environment.

        Returns the verdict plus (eftp, eftp_date) when it publishes.
        """
        window_start = end_date - timedelta(days=GATE_RECENCY_DAYS)
        candidates = [
            r for r in rides_env
            if not r.exclude and 1200 in r.peak_power
            and window_start <= r.date <= end_date
        ]
        count = len(candidates)
        newest = max((r.date for r in candidates), default=None)
        recency_ok = newest is not None
        # IF = NP / configured FTP on at least one candidate (a genuinely hard
        # near-threshold block). Needs a configured FTP to anchor IF.
        if_ok = bool(self._ftp) and any(
            r.norm_power and (r.norm_power / self._ftp) >= GATE_MIN_IF
            for r in candidates
        )
        published = count >= GATE_MIN_CANDIDATES and recency_ok and if_ok
        eftp = eftp_date = None
        if published:
            best = max(candidates, key=lambda r: r.peak_power[1200])
            eftp = round(best.peak_power[1200] * EFTP_MULTIPLIER)
            eftp_date = best.date
            reason = (f"eFTP medido {env}: melhor 20-min x {EFTP_MULTIPLIER:g}, "
                      f"{count} pedais na janela de {GATE_RECENCY_DAYS} dias")
        else:
            bits = []
            if count < GATE_MIN_CANDIDATES:
                bits.append(f"{count}<{GATE_MIN_CANDIDATES} pedais com 20-min")
            if not recency_ok:
                bits.append(f"sem esforço nos últimos {GATE_RECENCY_DAYS} dias")
            if not if_ok:
                bits.append("sem esforço duro (IF<0,90)")
            reason = ("FTP configurado (não testado nestes dados: "
                      + "; ".join(bits) + ")")
        gate = PowerGate(
            published=published, source_env=(env if published else None),
            candidate_count=count, recency_ok=recency_ok, if_ok=if_ok,
            newest_effort_date=newest, reason=reason,
        )
        return gate, eftp, eftp_date

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

        usable = [r for r in all_rides if not r.exclude]
        indoor = [r for r in usable if r.is_indoor]
        outdoor = [r for r in usable if not r.is_indoor]
        curve_indoor = self._best_curve(indoor)
        curve_outdoor = self._best_curve(outdoor)
        eftp_indoor = (round(curve_indoor[1200] * 0.95)
                       if curve_indoor.get(1200) else None)
        eftp_outdoor = (round(curve_outdoor[1200] * 0.95)
                        if curve_outdoor.get(1200) else None)
        peak_5s, peak_5s_dropped = self._neuromuscular_peak(usable)

        out_gate, out_eftp, out_date = self._gate_env(outdoor, end_date, "outdoor")
        in_gate, in_eftp, in_date = self._gate_env(indoor, end_date, "indoor")
        if out_gate.published:
            gate, eftp_measured, eftp_source, eftp_date = \
                out_gate, out_eftp, "outdoor", out_date
        elif in_gate.published:
            gate, eftp_measured, eftp_source, eftp_date = \
                in_gate, in_eftp, "indoor", in_date
        else:
            # Neither published: surface the outdoor verdict if outdoor rides
            # exist, else the indoor verdict (so the reason is the relevant one).
            gate = out_gate if outdoor else in_gate
            eftp_measured = eftp_source = eftp_date = None

        long_recent = [
            r for r in recent
            if not r.exclude and r.duration_s and r.duration_s >= 1800
            and r.norm_power and r.avg_power and r.avg_power > 0
        ]
        np_ratios = [r.norm_power / r.avg_power for r in long_recent]
        np_variability_ratio = (round(sum(np_ratios) / len(np_ratios), 2)
                                if np_ratios else None)
        np_long_ride_count = len(long_recent)

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
            recent_ride_count=len(recent),
            total_rides=len(all_rides),
            ftp_needs_test=ftp_needs_test,
            skipped_files=skipped_files,
            curve_indoor=curve_indoor,
            curve_outdoor=curve_outdoor,
            eftp_indoor=eftp_indoor,
            eftp_outdoor=eftp_outdoor,
            peak_5s=peak_5s,
            peak_5s_dropped=peak_5s_dropped,
            gate=gate,
            eftp_measured=eftp_measured,
            eftp_source=eftp_source,
            eftp_date=eftp_date,
            np_variability_ratio=np_variability_ratio,
            np_long_ride_count=np_long_ride_count,
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
        gate = result.gate
        if gate is not None and gate.published and result.eftp_measured:
            src = "outdoor" if result.eftp_source == "outdoor" else \
                "indoor (~8-12% abaixo do outdoor)"
            insights.append(Insight(
                # Title carries no bare "FTP" token so it stays clear of the
                # ftp_needs_test title guards used by callers.
                title="Potência de campo estimada disponível",
                description=(
                    f"eFTP estimado {result.eftp_measured:.0f} W "
                    f"(fonte {src}; melhor 20-min x 0,95, "
                    f"{gate.candidate_count} pedais na janela de 6 semanas). "
                    "Estimativa de campo, não teste de laboratório."
                ),
                severity=InsightSeverity.INFO,
                category="power",
                data_points={"eftp_measured": result.eftp_measured,
                             "source": result.eftp_source},
                recommendations=["Comparar com a FTP configurada; "
                                 "revalidar com teste se divergirem"],
            ))
        return insights
