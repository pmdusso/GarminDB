"""Aerobic decoupling (Hr:speed) and efficiency factor from per-second streams.

Reads the ``activity_records`` table (hr + speed are already imported) for
OUTDOOR cycling rides and computes, per long ride, the efficiency factor
(speed/HR) and the aerobic decoupling between the first and second half of the
analysed (moving, warmup-trimmed) portion. No power is required.

Validity: the metric is only meaningful for steady, sub-threshold efforts, so
indoor/virtual rides (simulated speed) are excluded, warmup and stopped samples
are trimmed, and a light steadiness gate drops interval-like rides. Numbers are
labelled accordingly for the clinical reader.

Definition (TrainingPeaks/Runalyze): EF = speed/HR over a window;
decoupling % = (EF_first_half - EF_second_half) / EF_first_half * 100.
< 5% strong aerobic durability; 5-10% moderate; > 10% above aerobic threshold
or insufficient endurance.
"""

import logging
import os
import sqlite3
import statistics
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Sequence, Tuple

from .models import Insight, InsightSeverity

logger = logging.getLogger(__name__)

MIN_MOVING_TIME_S = 3600       # >= 60 min outdoor ride (user decision)
WARMUP_TRIM_S = 600            # drop first 10 min (warmup drift confounder)
STOP_SPEED = 1.0              # speed <= this is "stopped" (kmph or mph)
MIN_ANALYZED_S = 1200         # need >= 20 min analysable after trimming
STEADY_CV_MAX = 0.35         # speed coefficient-of-variation gate (heuristic)
GPS_MIN_FRACTION = 0.5       # outdoor guard: >=50% of samples carry GPS
INDOOR_SUBSPORTS = ("indoor_cycling", "virtual_activity")
RECENT_WINDOW_DAYS = 90
DECOUPLE_GOOD = 5.0          # < 5% strong aerobic durability
DECOUPLE_HIGH = 10.0         # > 10% above aerobic threshold / low endurance


@dataclass
class RideDecoupling:
    """One outdoor ride's Hr:speed decoupling result."""

    activity_id: str
    date: date
    moving_time_s: float
    distance_km: Optional[float]
    ef_first: float              # speed/HR, first half (cleaned, moving)
    ef_second: float             # speed/HR, second half
    decoupling_pct: float        # (ef_first - ef_second) / ef_first * 100
    ef_overall: float            # speed/HR over the whole analysed portion
    speed_cv: float              # coefficient of variation of speed
    sample_count: int            # analysed samples (after trim/stop drop)
    steady: bool                 # passed the steadiness gate


@dataclass
class DecouplingResult:
    """Output of DecouplingAnalyzer.analyze()."""

    period_start: date
    period_end: date
    rides: List[RideDecoupling] = field(default_factory=list)  # steady, date desc
    monthly_decoupling: List[Tuple[str, Optional[float]]] = field(default_factory=list)
    monthly_ef: List[Tuple[str, Optional[float]]] = field(default_factory=list)
    eligible_count: int = 0      # outdoor cycling >=60min with analysable hr+speed
    analyzed_count: int = 0      # eligible AND passed the steadiness gate
    skipped_unsteady: int = 0    # eligible but too variable (interval-like)
    insights: List[Insight] = field(default_factory=list)


@dataclass
class PaHrRide:
    """One ride's power:HR (Pa:Hr) decoupling result."""

    activity_id: str
    date: date
    moving_time_s: float
    indoor: bool
    ef_first: float              # power/HR, first half
    ef_second: float             # power/HR, second half
    decoupling_pct: float        # (ef_first - ef_second) / ef_first * 100
    ef_overall: float            # power/HR over the analysed portion (W/bpm)
    avg_power: float             # mean power over the analysed portion (W)
    sample_count: int
    steady: Optional[bool]       # True/False outdoors; None = ungated (indoor)


@dataclass
class PaHrResult:
    """Output of DecouplingAnalyzer.analyze_pahr()."""

    period_start: date
    period_end: date
    rides: List[PaHrRide] = field(default_factory=list)        # reported, date desc
    monthly_decoupling: List[Tuple[str, Optional[float]]] = field(default_factory=list)
    monthly_ef: List[Tuple[str, Optional[float]]] = field(default_factory=list)
    eligible_count: int = 0      # cycling >=60min with analysable power+hr
    analyzed_count: int = 0      # reported (steady outdoors or ungated indoors)
    skipped_unsteady: int = 0    # outdoor rides dropped by the steadiness gate
    insights: List[Insight] = field(default_factory=list)


class DecouplingAnalyzer:
    """Compute Hr:speed decoupling + EF for outdoor cycling rides from the DB."""

    def __init__(self, db_dir: str):
        self._db_dir = db_dir

    def _query(self, db_name: str, sql: str, params: Sequence = ()) -> List[tuple]:
        """Run a read-only query; return [] on any DB problem (never raise)."""
        path = os.path.join(self._db_dir, db_name)
        if not os.path.exists(path):
            return []
        try:
            con = sqlite3.connect(path)
            try:
                return con.execute(sql, params).fetchall()
            finally:
                con.close()
        except sqlite3.Error as e:
            logger.warning("Decoupling query failed on %s: %s", db_name, e)
            return []

    @staticmethod
    def _clean(recs: List[tuple]) -> Tuple[List[Tuple[float, float, float]], float]:
        """Parse records into (elapsed_s, hr, speed); trim warmup + stops.

        Returns (samples, gps_fraction). Samples carry hr>0 and speed>STOP_SPEED,
        with the first WARMUP_TRIM_S seconds removed. gps_fraction is the share of
        raw rows carrying a position (an outdoor guard against simulated speed).
        """
        t0 = None
        gps = 0
        total = 0
        samples: List[Tuple[float, float, float]] = []
        for ts, hr, speed, lat in recs:
            total += 1
            if lat is not None:
                gps += 1
            day = _parse_dt(ts)
            if day is None or hr is None or speed is None:
                continue
            if t0 is None:
                t0 = day
            elapsed = (day - t0).total_seconds()
            if elapsed < WARMUP_TRIM_S:
                continue
            if float(speed) <= STOP_SPEED or float(hr) <= 0:
                continue
            samples.append((elapsed, float(hr), float(speed)))
        gps_fraction = (gps / total) if total else 0.0
        return samples, gps_fraction

    @staticmethod
    def _decoupling(
        samples: List[Tuple[float, float, float]],
    ) -> Optional[Tuple[float, float, float, float, float]]:
        """Return (ef_first, ef_second, decoupling_pct, ef_overall, speed_cv)."""
        if len(samples) < 2:
            return None
        t_first, t_last = samples[0][0], samples[-1][0]
        if t_last - t_first < MIN_ANALYZED_S:
            return None
        mid = t_first + (t_last - t_first) / 2.0
        first = [(h, s) for e, h, s in samples if e < mid]
        second = [(h, s) for e, h, s in samples if e >= mid]
        if not first or not second:
            return None
        ef1 = _ef(first)
        ef2 = _ef(second)
        all_pairs = [(h, s) for _, h, s in samples]
        ef_all = _ef(all_pairs)
        if not ef1 or not ef2 or not ef_all:
            return None
        decoup = (ef1 - ef2) / ef1 * 100.0
        speeds = [s for _, _, s in samples]
        mean_sp = sum(speeds) / len(speeds)
        cv = (statistics.pstdev(speeds) / mean_sp) if mean_sp > 0 else 0.0
        return ef1, ef2, decoup, ef_all, cv

    def _ride_decoupling(self, activity_id, ride_date, moving_s, dist_km):
        """Load + analyse one ride; None if not analysable (data/GPS/length)."""
        recs = self._query(
            "garmin_activities.db",
            "SELECT timestamp, hr, speed, position_lat FROM activity_records "
            "WHERE activity_id = ? ORDER BY record",
            (activity_id,),
        )
        samples, gps_fraction = self._clean(recs)
        if gps_fraction < GPS_MIN_FRACTION:
            return None  # likely indoor/virtual despite the sub_sport label
        computed = self._decoupling(samples)
        if computed is None:
            return None
        ef1, ef2, decoup, ef_all, cv = computed
        return RideDecoupling(
            activity_id=str(activity_id), date=ride_date, moving_time_s=moving_s,
            distance_km=dist_km, ef_first=round(ef1, 4), ef_second=round(ef2, 4),
            decoupling_pct=round(decoup, 1), ef_overall=round(ef_all, 4),
            speed_cv=round(cv, 3), sample_count=len(samples),
            steady=cv <= STEADY_CV_MAX,
        )

    def analyze(self, start_date: date, end_date: date) -> "DecouplingResult":
        """Build a DecouplingResult for outdoor cycling rides in the period."""
        rows = self._query(
            "garmin_activities.db",
            "SELECT activity_id, start_time, moving_time, distance, sub_sport "
            "FROM activities WHERE sport = 'cycling' "
            "AND date(start_time) >= ? AND date(start_time) <= ?",
            (start_date.isoformat(), end_date.isoformat()),
        )
        analysed: List[RideDecoupling] = []
        for aid, start_time, moving_time, distance, sub_sport in rows:
            if (sub_sport or "") in INDOOR_SUBSPORTS:
                continue
            moving_s = _parse_hms(moving_time)
            if moving_s < MIN_MOVING_TIME_S:
                continue
            ride_date = _parse_dt(start_time)
            if ride_date is None:
                continue
            rd = self._ride_decoupling(
                aid, ride_date.date(), moving_s,
                float(distance) if distance is not None else None)
            if rd is not None:
                analysed.append(rd)

        steady = sorted((r for r in analysed if r.steady),
                        key=lambda r: r.date, reverse=True)
        result = DecouplingResult(
            period_start=start_date, period_end=end_date, rides=steady,
            monthly_decoupling=_monthly(steady, "decoupling_pct", start_date, end_date),
            monthly_ef=_monthly(steady, "ef_overall", start_date, end_date, nd=4),
            eligible_count=len(analysed),
            analyzed_count=len(steady),
            skipped_unsteady=len(analysed) - len(steady),
        )
        result.insights = self._insights(result, end_date)
        return result

    @staticmethod
    def _insights(result: "DecouplingResult", end_date: date) -> List[Insight]:
        recent = [r for r in result.rides
                  if (end_date - r.date).days <= RECENT_WINDOW_DAYS]
        if not recent:
            return []
        mean_dc = sum(r.decoupling_pct for r in recent) / len(recent)
        if mean_dc < DECOUPLE_GOOD:
            sev, msg = (InsightSeverity.POSITIVE,
                        "Desacoplamento FC:velocidade baixo (<5%) nas pedaladas "
                        "longas recentes: boa durabilidade aeróbica.")
        elif mean_dc <= DECOUPLE_HIGH:
            sev, msg = (InsightSeverity.INFO,
                        "Desacoplamento FC:velocidade moderado (5-10%): limite "
                        "aeróbico ou fadiga nas pedaladas longas.")
        else:
            sev, msg = (InsightSeverity.WARNING,
                        "Desacoplamento FC:velocidade alto (>10%): esforço acima "
                        "do limiar aeróbico ou endurance insuficiente.")
        return [Insight(
            title="Durabilidade aeróbica (FC:velocidade)",
            description=(f"{msg} Média {mean_dc:.1f}% em {len(recent)} pedal(is) "
                         "outdoor >=60 min (estável; aquecimento e paradas "
                         "removidos)."),
            severity=sev, category="endurance",
            data_points={"mean_decoupling_pct": round(mean_dc, 1),
                         "rides": len(recent)},
            recommendations=["Validar com esforço estável sub-limiar; "
                             "EF crescente ao longo dos meses = ganho aeróbico"],
        )]

    # -- Pa:Hr (power:HR) decoupling -- includes indoor (power is real) ------ #

    @staticmethod
    def _clean_power(recs, indoor):
        """Parse records into (elapsed_s, hr, power) + the speed CV for the gate.

        Keeps zero-power coasting (real load); trims warmup; drops hr<=0 / power
        None. Outdoors, drops true stops (speed<=STOP_SPEED) and returns the
        speed coefficient of variation for the steadiness gate. Indoors there is
        no real speed, so the gate is skipped (speed_cv=None).
        """
        t0 = None
        samples = []
        speeds = []
        for ts, hr, power, speed in recs:
            day = _parse_dt(ts)
            if day is None or hr is None or power is None:
                continue
            if t0 is None:
                t0 = day
            elapsed = (day - t0).total_seconds()
            if elapsed < WARMUP_TRIM_S or float(hr) <= 0:
                continue
            if not indoor and speed is not None and float(speed) <= STOP_SPEED:
                continue  # true stop (outdoor): HR elevated but not moving
            samples.append((elapsed, float(hr), float(power)))
            if speed is not None:
                speeds.append(float(speed))
        speed_cv = None
        if not indoor and len(speeds) > 1:
            mean_sp = sum(speeds) / len(speeds)
            if mean_sp > 0:
                speed_cv = statistics.pstdev(speeds) / mean_sp
        return samples, speed_cv

    def _pahr_ride(self, activity_id, ride_date, moving_s, indoor):
        recs = self._query(
            "garmin_activities.db",
            "SELECT timestamp, hr, power, speed FROM activity_records "
            "WHERE activity_id = ? ORDER BY record",
            (activity_id,),
        )
        samples, speed_cv = self._clean_power(recs, indoor)
        computed = self._decoupling(samples)
        if computed is None:
            return None
        ef1, ef2, decoup, ef_all, _ = computed
        avg_power = sum(p for _, _, p in samples) / len(samples)
        steady = None if (indoor or speed_cv is None) else (speed_cv <= STEADY_CV_MAX)
        return PaHrRide(
            activity_id=str(activity_id), date=ride_date, moving_time_s=moving_s,
            indoor=indoor, ef_first=round(ef1, 4), ef_second=round(ef2, 4),
            decoupling_pct=round(decoup, 1), ef_overall=round(ef_all, 4),
            avg_power=round(avg_power, 1), sample_count=len(samples), steady=steady,
        )

    def _has_power_column(self) -> bool:
        """True if activity_records carries the SP1 power column (post-rebuild)."""
        cols = self._query("garmin_activities.db",
                           "PRAGMA table_info(activity_records)")
        return any(c[1] == "power" for c in cols)

    def analyze_pahr(self, start_date: date, end_date: date) -> "PaHrResult":
        """Build a PaHrResult (power:HR decoupling) for cycling rides in period.

        Includes indoor/trainer rides (power is meter-measured even indoors);
        each ride is labelled indoor/outdoor. Outdoor rides pass the speed-CV
        steadiness gate; indoor rides are reported ungated (steady=None).
        """
        if not self._has_power_column():
            logger.info("activity_records has no power column yet (pre-SP1 "
                        "rebuild); Pa:Hr is empty until garmindb_cli.py "
                        "--rebuild_db is run.")
            return PaHrResult(period_start=start_date, period_end=end_date)
        rows = self._query(
            "garmin_activities.db",
            "SELECT activity_id, start_time, moving_time, sub_sport "
            "FROM activities WHERE sport = 'cycling' "
            "AND date(start_time) >= ? AND date(start_time) <= ?",
            (start_date.isoformat(), end_date.isoformat()),
        )
        analysed: List[PaHrRide] = []
        for aid, start_time, moving_time, sub_sport in rows:
            if _parse_hms(moving_time) < MIN_MOVING_TIME_S:
                continue
            ride_date = _parse_dt(start_time)
            if ride_date is None:
                continue
            indoor = (sub_sport or "") in INDOOR_SUBSPORTS
            rd = self._pahr_ride(aid, ride_date.date(),
                                 _parse_hms(moving_time), indoor)
            if rd is not None:
                analysed.append(rd)

        reported = sorted((r for r in analysed if r.steady is not False),
                          key=lambda r: r.date, reverse=True)
        result = PaHrResult(
            period_start=start_date, period_end=end_date, rides=reported,
            monthly_decoupling=_monthly(reported, "decoupling_pct", start_date, end_date),
            monthly_ef=_monthly(reported, "ef_overall", start_date, end_date, nd=4),
            eligible_count=len(analysed),
            analyzed_count=len(reported),
            skipped_unsteady=len(analysed) - len(reported),
        )
        result.insights = self._pahr_insights(result, end_date)
        return result

    @staticmethod
    def _pahr_insights(result: "PaHrResult", end_date: date) -> List[Insight]:
        recent = [r for r in result.rides
                  if (end_date - r.date).days <= RECENT_WINDOW_DAYS]
        if not recent:
            return []
        mean_dc = sum(r.decoupling_pct for r in recent) / len(recent)
        if mean_dc < DECOUPLE_GOOD:
            sev, msg = (InsightSeverity.POSITIVE,
                        "Desacoplamento potência:FC baixo (<5%): boa durabilidade "
                        "aeróbica nas pedaladas longas recentes.")
        elif mean_dc <= DECOUPLE_HIGH:
            sev, msg = (InsightSeverity.INFO,
                        "Desacoplamento potência:FC moderado (5-10%): limite "
                        "aeróbico ou fadiga nas pedaladas longas.")
        else:
            sev, msg = (InsightSeverity.WARNING,
                        "Desacoplamento potência:FC alto (>10%): esforço acima do "
                        "limiar aeróbico ou endurance insuficiente.")
        return [Insight(
            title="Durabilidade aeróbica (potência:FC)",
            description=(f"{msg} Média {mean_dc:.1f}% em {len(recent)} pedal(is) "
                         ">=60 min com potência (indoor e outdoor; aquecimento "
                         "removido)."),
            severity=sev, category="endurance",
            data_points={"mean_pahr_decoupling_pct": round(mean_dc, 1),
                         "rides": len(recent)},
            recommendations=["Pa:Hr usa potência medida; vale indoor e outdoor. "
                             "Queda do desacoplamento ao longo dos meses = ganho."],
        )]


def _ef(pairs: List[Tuple[float, float]]) -> Optional[float]:
    """Efficiency factor = mean(speed) / mean(HR) for (hr, speed) pairs."""
    if not pairs:
        return None
    mean_hr = sum(h for h, _ in pairs) / len(pairs)
    if mean_hr <= 0:
        return None
    return (sum(s for _, s in pairs) / len(pairs)) / mean_hr


def _monthly(rides, attr, start, end, nd=1):
    """Monthly mean of one RideDecoupling attribute over [start, end]."""
    buckets = {}
    for r in rides:
        buckets.setdefault(_ym(r.date), []).append(getattr(r, attr))
    return [(ym, round(sum(buckets[ym]) / len(buckets[ym]), nd)
             if ym in buckets else None)
            for ym in _month_keys(start, end)]


def _parse_dt(value) -> Optional[datetime]:
    """Parse a DB timestamp ('YYYY-MM-DD HH:MM:SS[.ffffff]') to datetime."""
    if value is None:
        return None
    text = str(value).strip().replace("T", " ")
    if not text:
        return None
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _parse_hms(value) -> float:
    """Parse an 'HH:MM:SS[.ffffff]' TIME string to seconds (0.0 if blank)."""
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    parts = text.split(":")
    try:
        if len(parts) == 3:
            return int(parts[0]) * 3600 + int(parts[1]) * 60 + float(parts[2])
        return float(text)
    except ValueError:
        return 0.0


def _ym(day: date) -> str:
    return f"{day.year:04d}-{day.month:02d}"


def _month_keys(start: date, end: date) -> List[str]:
    """Ordered 'YYYY-MM' keys from start's month to end's month inclusive."""
    keys: List[str] = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        keys.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return keys
