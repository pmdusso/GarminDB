"""Longitudinal anamnesis report: month-by-month trends across a long span.

Unlike the single-window health/performance reports (which collapse a period to
one number per metric), this builder reads the SQLite DBs directly -- like
``db_metrics`` -- and produces a *time series* per metric plus cumulative
training totals, rolling baselines, and a rule-based red-flag screen. The target
reader is a sports-medicine clinician doing an anamnesis (longitudinal review).

Data-honesty notes (these matter -- the output goes to a doctor):
- There is NO power-meter data in these DBs. FTP / W-kg are CONFIGURED goals
  (``performance_targets.json``), not measurements, and are labelled as such.
- CTL/ATL/TSB use Garmin per-activity ``training_load`` as the load proxy and the
  same EWMA windows (ATL 7d, CTL 42d) as :class:`ActivityAnalyzer`, so the numbers
  stay consistent with the other reports.
- VO2max, HRV-status and stress are Garmin wrist/optical estimates -- screening
  trends, not diagnostic values.

Every DB read is defensive: a missing, locked or corrupt DB degrades the
affected section to "no data" instead of crashing the whole report.
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional, Sequence, Tuple

from .activity_analyzer import LOAD_FACTORS
from .performance_targets import PerformanceTargets

logger = logging.getLogger(__name__)

# EWMA windows -- kept identical to ActivityAnalyzer so CTL/ATL/TSB agree across
# reports (ATL = fatigue, CTL = fitness, TSB = form).
ATL_WINDOW = 7
CTL_WINDOW = 42

# How far before the reported span to start accumulating daily load so the
# 42-day CTL EWMA is well converged by the first reported month (~5-6x the CTL
# window keeps the earliest reported month free of seeding artefacts).
_LOAD_LOOKBACK_DAYS = 240

_SPARK_BLOCKS = "▁▂▃▄▅▆▇█"


# --------------------------------------------------------------------------- #
# Result models
# --------------------------------------------------------------------------- #

@dataclass
class MetricSeries:
    """A monthly time series for one physiological/training metric.

    ``points`` is ordered oldest->newest as (``YYYY-MM``, value|None). ``better``
    records the clinically favourable direction ("down"/"up"/"neutral") so the
    renderer can read a trend as good or bad rather than just up or down.
    """

    key: str
    label: str
    unit: str
    points: List[Tuple[str, Optional[float]]] = field(default_factory=list)
    better: str = "neutral"          # "up" | "down" | "neutral"
    baseline: Optional[float] = None     # personal baseline (chronic mean)
    baseline_low: Optional[float] = None
    baseline_high: Optional[float] = None
    decimals: int = 1
    note: Optional[str] = None

    @property
    def values(self) -> List[float]:
        """Non-null values, oldest->newest."""
        return [v for _, v in self.points if v is not None]

    @property
    def current(self) -> Optional[float]:
        for _, v in reversed(self.points):
            if v is not None:
                return v
        return None

    @property
    def first(self) -> Optional[float]:
        return self.values[0] if self.values else None

    @property
    def minimum(self) -> Optional[float]:
        return min(self.values) if self.values else None

    @property
    def maximum(self) -> Optional[float]:
        return max(self.values) if self.values else None

    @property
    def mean(self) -> Optional[float]:
        vals = self.values
        return sum(vals) / len(vals) if vals else None

    def direction(self) -> str:
        """Raw movement of the series: 'up' | 'down' | 'flat'.

        Compares the mean of the first third of the series to the mean of the
        last third (robust to single-month noise). 'flat' if the change is
        within 3% of the baseline magnitude.
        """
        vals = self.values
        if len(vals) < 4:
            return "flat"
        third = max(1, len(vals) // 3)
        early = sum(vals[:third]) / third
        late = sum(vals[-third:]) / third
        scale = abs(early) if early else 1.0
        delta = late - early
        if abs(delta) < 0.03 * scale:
            return "flat"
        return "up" if delta > 0 else "down"

    def verdict(self) -> str:
        """Clinical reading of the trend: 'good' | 'bad' | 'flat' | 'neutral'."""
        d = self.direction()
        if d == "flat" or self.better == "neutral":
            return "flat" if d == "flat" else "neutral"
        return "good" if d == self.better else "bad"

    def sparkline(self) -> str:
        return _sparkline([v for _, v in self.points])


@dataclass
class VolumeMonth:
    """Training volume for one calendar month."""

    ym: str
    activities: int
    distance_km: float
    hours: float
    ascent_m: float
    load_sum: float
    te_avg: Optional[float]


@dataclass
class SportTotal:
    sport: str
    count: int
    distance_km: float
    hours: float
    ascent_m: float


@dataclass
class YearTotals:
    year: int
    activities: int
    distance_km: float
    hours: float
    ascent_m: float
    calories: int
    days_active: int


@dataclass
class TrainingLoadMonth:
    """End-of-month fitness/fatigue/form snapshot from the daily-load EWMA."""

    ym: str
    ctl: float
    atl: float
    tsb: float


@dataclass
class RedFlag:
    """One triggered screening signal. Only out-of-band items become flags."""

    severity: str            # "alert" | "warning" | "info"
    title: str
    finding: str             # the data, e.g. "RHR +3.8 bpm acima da linha de base"
    detail: str              # interpretation + caveat
    recommendation: str

    @property
    def icon(self) -> str:
        return {"alert": "🚨", "warning": "⚠️", "info": "ℹ️"}.get(self.severity, "•")


@dataclass
class AthleteProfile:
    name: Optional[str]
    age: Optional[int]
    sex: Optional[str]
    height_m: Optional[float]
    weight_kg: Optional[float]
    vo2max_running: Optional[float]
    vo2max_cycling: Optional[float]
    timezone: Optional[str]

    @property
    def bmi(self) -> Optional[float]:
        if self.weight_kg and self.height_m:
            return self.weight_kg / (self.height_m ** 2)
        return None


@dataclass
class LongitudinalReport:
    """Full payload for the longitudinal/anamnesis renderer."""

    generated_at: datetime
    period_start: date
    period_end: date
    targets: PerformanceTargets
    athlete: AthleteProfile

    red_flags: List[RedFlag]
    readiness_light: str
    readiness_label: str
    series: Dict[str, MetricSeries]
    current_weight: Optional[float]
    volume: List[VolumeMonth]
    load: List[TrainingLoadMonth]
    current_load: Optional[TrainingLoadMonth]
    acwr: Optional[float]
    monotony: Optional[float]
    ctl_ramp_per_week: Optional[float]
    sport_totals_by_year: Dict[int, List[SportTotal]]
    year_totals: List[YearTotals]
    weeks_to_race: Optional[int]
    days_to_race: Optional[int]
    current_month_partial: bool
    confidence_score: Optional[float]


# --------------------------------------------------------------------------- #
# Builder
# --------------------------------------------------------------------------- #

class LongitudinalReportBuilder:
    """Builds a :class:`LongitudinalReport` straight from the SQLite DBs.

    Args:
        db_dir: Directory holding garmin.db / garmin_activities.db /
            garmin_monitoring.db (``db_params.db_path``).
        targets: Configured race/FTP/weight goals (for context, not measured).
        start_date: First day of the reported span (inclusive).
        end_date: Last day of the reported span (inclusive).
        generated_at: Timestamp stamped on the report.
    """

    def __init__(
        self,
        db_dir: str,
        targets: PerformanceTargets,
        start_date: date,
        end_date: date,
        generated_at: datetime,
    ):
        self._db_dir = db_dir
        self._targets = targets
        self._start = start_date
        self._end = end_date
        self._generated = generated_at

    # -- public ------------------------------------------------------------- #

    def build(self) -> LongitudinalReport:
        athlete = self._athlete_profile()

        activities = self._read_activities()
        volume = self._volume_by_month(activities)
        year_totals = self._year_totals(activities)
        sport_totals = self._sport_totals_by_year(activities)

        load_months, current_load, daily_loads, confidence = \
            self._training_load(activities)
        acwr = self._acwr(daily_loads)
        monotony = self._monotony(daily_loads)
        ramp = self._ctl_ramp(load_months)

        series: Dict[str, MetricSeries] = {}
        series["rhr"] = self._daily_series(
            "garmin.db", "daily_summary", "rhr", "day",
            key="rhr", label="FC de repouso", unit="bpm", better="down",
            decimals=0,
        )
        series["hrv"] = self._hrv_series()
        series["weight"] = self._weight_series()
        series["sleep"] = self._sleep_series()
        series["sleep_score"] = self._daily_series(
            "garmin.db", "sleep", "score", "day",
            key="sleep_score", label="Pontuação de sono", unit="/100",
            better="up", decimals=0,
        )
        series["stress"] = self._daily_series(
            "garmin.db", "daily_summary", "stress_avg", "day",
            key="stress", label="Estresse médio (Garmin)", unit="",
            better="down", decimals=0,
        )
        series["body_battery"] = self._daily_series(
            "garmin.db", "daily_summary", "bb_max", "day",
            key="body_battery", label="Body Battery (pico)", unit="",
            better="up", decimals=0,
        )
        series["spo2"] = self._daily_series(
            "garmin.db", "daily_summary", "spo2_avg", "day",
            key="spo2", label="SpO2 (saturação de O2)", unit="%", better="up",
            decimals=1,
            coverage_note=("relevante para aclimatação a altitude "
                           "(prova de montanha); estimativa óptica de pulso"),
        )
        series["respiracao"] = self._daily_series(
            "garmin.db", "daily_summary", "rr_waking_avg", "day",
            key="respiracao", label="Freq. respiratória (repouso)", unit="rpm",
            better="down", decimals=1,
            coverage_note=("FR de repouso elevada acompanha "
                           "estresse/doença/overreaching"),
        )
        series["vo2max_cycling"] = self._vo2max_series("cycle_activities")
        series["vo2max_running"] = self._vo2max_series("steps_activities")
        series["anaerobic_te"] = self._anaerobic_te_series()
        series["ctl"] = self._ctl_series(load_months)

        red_flags = self._screen(series, acwr, monotony, ramp,
                                 current_load, volume)
        light, label = self._readiness(red_flags, series)
        days = self._days_to_race()

        return LongitudinalReport(
            generated_at=self._generated,
            period_start=self._start,
            period_end=self._end,
            targets=self._targets,
            athlete=athlete,
            red_flags=red_flags,
            readiness_light=light,
            readiness_label=label,
            series=series,
            current_weight=athlete.weight_kg,
            volume=volume,
            load=load_months,
            current_load=current_load,
            acwr=acwr,
            monotony=monotony,
            ctl_ramp_per_week=ramp,
            sport_totals_by_year=sport_totals,
            year_totals=year_totals,
            weeks_to_race=(round(days / 7) if days is not None else None),
            days_to_race=days,
            current_month_partial=self._end.day < 25,
            confidence_score=confidence,
        )

    # -- db access ---------------------------------------------------------- #

    def _query(
        self, db_name: str, sql: str, params: Sequence = ()
    ) -> List[tuple]:
        """Run a read-only query; return [] on any DB problem (never raise)."""
        path = os.path.join(self._db_dir, db_name)
        if not os.path.exists(path):
            logger.warning("Longitudinal: %s not found; section degraded", path)
            return []
        con = None
        try:
            con = sqlite3.connect(path)
            return con.execute(sql, params).fetchall()
        except sqlite3.Error as e:
            logger.warning("Longitudinal query on %s failed (%s)", path, e)
            return []
        finally:
            if con is not None:
                con.close()

    # -- athlete ------------------------------------------------------------ #

    def _athlete_profile(self) -> AthleteProfile:
        rows = self._query("garmin.db", "SELECT key, value FROM attributes")
        attrs: Dict[str, str] = {}
        for k, v in rows:
            # attributes can carry duplicate keys across snapshots; first wins
            attrs.setdefault(k, v)

        def _f(key: str) -> Optional[float]:
            try:
                return float(attrs[key])
            except (KeyError, TypeError, ValueError):
                return None

        age = None
        yob = _f("year_of_birth")
        if yob:
            age = self._end.year - int(yob)

        sex = attrs.get("gender")
        if sex:
            sex = sex.split(".")[-1]  # "Gender.male" -> "male"

        return AthleteProfile(
            name=attrs.get("name"),
            age=age,
            sex=sex,
            height_m=_f("height"),
            weight_kg=self._latest_weight(),
            vo2max_running=_f("vo2max_running"),
            vo2max_cycling=_f("vo2max_cycling"),
            timezone=attrs.get("time_zone"),
        )

    def _latest_weight(self) -> Optional[float]:
        """Robust recent weight = median of weigh-ins in the last 45 days.

        A single latest reading can be an outlier (here the 2026-05-30 value of
        87.25 kg sits ~2.5 kg above the surrounding scale readings and equals the
        profile-config weight), which would skew BMI and W·kg. The median of the
        recent cluster is the honest "current" figure.
        """
        cutoff = (self._end - timedelta(days=45)).isoformat()
        rows = self._query(
            "garmin.db",
            "SELECT weight FROM weight WHERE weight IS NOT NULL "
            "AND date(day) >= ? AND date(day) <= ? ORDER BY day",
            (cutoff, self._end.isoformat()),
        )
        values = sorted(float(r[0]) for r in rows)
        if not values:
            rows = self._query(
                "garmin.db",
                "SELECT weight FROM weight WHERE weight IS NOT NULL "
                "ORDER BY day DESC LIMIT 1",
            )
            return float(rows[0][0]) if rows else None
        mid = len(values) // 2
        if len(values) % 2:
            return values[mid]
        return (values[mid - 1] + values[mid]) / 2

    # -- activities & volume ------------------------------------------------ #

    def _read_activities(self) -> List[dict]:
        """All activities from (start - load lookback) .. end, parsed to dicts."""
        lookback = (self._start - timedelta(days=_LOAD_LOOKBACK_DAYS)).isoformat()
        rows = self._query(
            "garmin_activities.db",
            "SELECT start_time, sport, distance, moving_time, ascent, "
            "training_load, training_effect, calories "
            "FROM activities WHERE date(start_time) >= ? AND date(start_time) <= ? "
            "ORDER BY start_time",
            (lookback, self._end.isoformat()),
        )
        out: List[dict] = []
        for start_time, sport, distance, moving, ascent, load, te, cal in rows:
            day = _parse_date(start_time)
            if day is None:
                continue
            out.append({
                "day": day,
                "sport": (sport or "unknown"),
                "km": float(distance) if distance is not None else 0.0,
                "hours": _parse_hms(moving) / 3600.0,
                "ascent": float(ascent) if ascent is not None else 0.0,
                "load": float(load) if load is not None else None,
                "te": float(te) if te is not None else None,
                "cal": int(cal) if cal is not None else 0,
            })
        return out

    def _in_span(self, activities: List[dict]) -> List[dict]:
        return [a for a in activities if self._start <= a["day"] <= self._end]

    def _volume_by_month(self, activities: List[dict]) -> List[VolumeMonth]:
        buckets: Dict[str, List[dict]] = {}
        for a in self._in_span(activities):
            buckets.setdefault(_ym(a["day"]), []).append(a)

        out: List[VolumeMonth] = []
        for ym in _month_keys(self._start, self._end):
            acts = buckets.get(ym, [])
            te_vals = [a["te"] for a in acts if a["te"] is not None]
            out.append(VolumeMonth(
                ym=ym,
                activities=len(acts),
                distance_km=round(sum(a["km"] for a in acts), 0),
                hours=round(sum(a["hours"] for a in acts), 1),
                ascent_m=round(sum(a["ascent"] for a in acts), 0),
                load_sum=round(sum(a["load"] or 0 for a in acts), 0),
                te_avg=round(sum(te_vals) / len(te_vals), 2) if te_vals else None,
            ))
        return out

    def _year_totals(self, activities: List[dict]) -> List[YearTotals]:
        buckets: Dict[int, List[dict]] = {}
        for a in self._in_span(activities):
            buckets.setdefault(a["day"].year, []).append(a)
        out: List[YearTotals] = []
        for year in sorted(buckets):
            acts = buckets[year]
            out.append(YearTotals(
                year=year,
                activities=len(acts),
                distance_km=round(sum(a["km"] for a in acts), 0),
                hours=round(sum(a["hours"] for a in acts), 1),
                ascent_m=round(sum(a["ascent"] for a in acts), 0),
                calories=int(sum(a["cal"] for a in acts)),
                days_active=len({a["day"] for a in acts}),
            ))
        return out

    def _sport_totals_by_year(
        self, activities: List[dict]
    ) -> Dict[int, List[SportTotal]]:
        buckets: Dict[int, Dict[str, List[dict]]] = {}
        for a in self._in_span(activities):
            buckets.setdefault(a["day"].year, {}).setdefault(
                a["sport"], []).append(a)
        out: Dict[int, List[SportTotal]] = {}
        for year, sports in buckets.items():
            totals = [
                SportTotal(
                    sport=sport,
                    count=len(acts),
                    distance_km=round(sum(a["km"] for a in acts), 0),
                    hours=round(sum(a["hours"] for a in acts), 1),
                    ascent_m=round(sum(a["ascent"] for a in acts), 0),
                )
                for sport, acts in sports.items()
            ]
            totals.sort(key=lambda s: s.count, reverse=True)
            out[year] = totals
        return out

    # -- training load (CTL/ATL/TSB) ---------------------------------------- #

    def _daily_load_map(
        self, activities: List[dict]
    ) -> Tuple[Dict[date, float], float]:
        """Continuous daily load (rest days = 0) plus a real/estimated ratio.

        Mirrors :meth:`ActivityAnalyzer._build_daily_loads`: use ``training_load``
        when present, else a sport-factor estimate from duration.
        """
        loads: Dict[date, float] = {}
        d = self._start - timedelta(days=_LOAD_LOOKBACK_DAYS)
        while d <= self._end:
            loads[d] = 0.0
            d += timedelta(days=1)

        total = 0.0
        real = 0.0
        for a in activities:
            if a["day"] not in loads:
                continue
            if a["load"] is not None and a["load"] > 0:
                value, is_real = a["load"], True
            else:
                factor = LOAD_FACTORS.get(a["sport"].lower(),
                                          LOAD_FACTORS["default"])
                value, is_real = a["hours"] * 60 * factor, False
            loads[a["day"]] += value
            total += value
            if is_real:
                real += value
        confidence = (real / total) if total > 0 else 1.0
        return loads, round(confidence, 2)

    def _training_load(
        self, activities: List[dict]
    ) -> Tuple[List[TrainingLoadMonth], Optional[TrainingLoadMonth],
               Dict[date, float], Optional[float]]:
        loads, confidence = self._daily_load_map(activities)
        # No training load anywhere -> "no data", not a flat zero series, and
        # confidence is meaningless (don't print "100% device-measured").
        if not any(v > 0 for v in loads.values()):
            return [], None, loads, None
        ctl = _ewma_series(loads, CTL_WINDOW)
        atl = _ewma_series(loads, ATL_WINDOW)

        months: List[TrainingLoadMonth] = []
        for ym in _month_keys(self._start, self._end):
            day = _last_day_present(loads, ym, self._end)
            if day is None:
                continue
            months.append(TrainingLoadMonth(
                ym=ym,
                ctl=round(ctl[day], 1),
                atl=round(atl[day], 1),
                tsb=round(ctl[day] - atl[day], 1),
            ))

        current = None
        if self._end in ctl:
            current = TrainingLoadMonth(
                ym=_ym(self._end),
                ctl=round(ctl[self._end], 1),
                atl=round(atl[self._end], 1),
                tsb=round(ctl[self._end] - atl[self._end], 1),
            )
        return months, current, loads, confidence

    def _acwr(self, loads: Dict[date, float]) -> Optional[float]:
        """Acute:chronic workload ratio (7-day load : average weekly 28-day)."""
        acute = sum(loads.get(self._end - timedelta(days=i), 0) for i in range(7))
        chronic28 = sum(
            loads.get(self._end - timedelta(days=i), 0) for i in range(28)
        )
        chronic_week = chronic28 / 4
        if chronic_week <= 0:
            return None
        return round(acute / chronic_week, 2)

    def _monotony(self, loads: Dict[date, float]) -> Optional[float]:
        """Foster monotony (mean/std of daily load) over the last 28 days."""
        window = [loads.get(self._end - timedelta(days=i), 0) for i in range(28)]
        mean = sum(window) / len(window)
        if mean == 0:
            return None
        var = sum((x - mean) ** 2 for x in window) / len(window)
        std = var ** 0.5
        if std == 0:
            return None
        return round(mean / std, 2)

    def _ctl_ramp(self, months: List[TrainingLoadMonth]) -> Optional[float]:
        """Average CTL change per week over the last ~8 weeks of the series."""
        if len(months) < 2:
            return None
        recent = months[-1].ctl
        prior = months[max(0, len(months) - 3)].ctl
        spanned_months = min(2, len(months) - 1)
        weeks = spanned_months * 4.345
        if weeks <= 0:
            return None
        return round((recent - prior) / weeks, 1)

    def _ctl_series(self, months: List[TrainingLoadMonth]) -> MetricSeries:
        # 'neutral': whether current CTL below an earlier peak is good or bad
        # depends on the macrocycle phase (deload/taper vs detraining), so the
        # renderer must not colour a CTL dip red on its own. Section 4 carries
        # the interpretation (ACWR/ramp/monotony) and the partial-month caveat.
        s = MetricSeries(
            key="ctl", label="Fitness (CTL)", unit="", better="neutral",
            decimals=0,
        )
        present = {m.ym: m.ctl for m in months}
        s.points = [(ym, present.get(ym)) for ym in _month_keys(self._start, self._end)]
        return s

    # -- physiology series -------------------------------------------------- #

    def _daily_series(
        self, db: str, table: str, col: str, day_col: str,
        *, key: str, label: str, unit: str, better: str, decimals: int,
        coverage_note: Optional[str] = None,
    ) -> MetricSeries:
        rows = self._query(
            db,
            f"SELECT {day_col}, {col} FROM {table} "
            f"WHERE date({day_col}) >= ? AND date({day_col}) <= ? "
            f"AND {col} IS NOT NULL",
            (self._start.isoformat(), self._end.isoformat()),
        )
        daily = {}
        for d, v in rows:
            day = _parse_date(d)
            if day is not None and v is not None:
                daily[day] = float(v)
        s = MetricSeries(key=key, label=label, unit=unit, better=better,
                         decimals=decimals)
        s.points = self._monthly_mean_points(daily, decimals)
        s.baseline, s.baseline_low, s.baseline_high = \
            self._baseline_band(daily, decimals)
        # Declare coverage explicitly when asked (data-honesty: the reader is a
        # clinician and must see how many days back a trend). Default None keeps
        # the existing callers (rhr/stress/etc.) unchanged.
        if coverage_note is not None and daily:
            s.note = f"{len(daily)} dias medidos no período — {coverage_note}"
        return s

    def _hrv_series(self) -> MetricSeries:
        # Only last_night_average is on the same scale as the displayed values.
        # Garmin's baseline_low/high columns are on a different/legacy scale
        # (~33-40 ms here vs ~50-76 ms nightly) and would print a band that does
        # not contain its own mean, so we derive the personal baseline from the
        # series itself (mean ± 1 SD over the chronic window), like the others.
        rows = self._query(
            "garmin_monitoring.db",
            "SELECT timestamp, last_night_average FROM monitoring_hrv_status "
            "WHERE date(timestamp) >= ? AND date(timestamp) <= ? "
            "AND last_night_average IS NOT NULL",
            (self._start.isoformat(), self._end.isoformat()),
        )
        daily = {}
        for ts, avg in rows:
            day = _parse_date(ts)
            if day is not None and avg is not None:
                daily[day] = float(avg)
        s = MetricSeries(key="hrv", label="VFC noturna (HRV)", unit="ms",
                         better="up", decimals=0)
        s.points = self._monthly_mean_points(daily, 0)
        s.baseline, s.baseline_low, s.baseline_high = self._baseline_band(daily, 0)
        s.note = (f"{len(daily)} noites medidas; VFC = média noturna rMSSD "
                  "(estimativa de pulso, não chest-strap)") if daily else None
        return s

    def _weight_series(self) -> MetricSeries:
        rows = self._query(
            "garmin.db",
            "SELECT day, weight FROM weight "
            "WHERE date(day) >= ? AND date(day) <= ? AND weight IS NOT NULL",
            (self._start.isoformat(), self._end.isoformat()),
        )
        daily = {}
        for d, w in rows:
            day = _parse_date(d)
            if day is not None and w is not None:
                daily[day] = float(w)
        s = MetricSeries(key="weight", label="Peso corporal", unit="kg",
                         better="neutral", decimals=1)
        s.points = self._monthly_mean_points(daily, 1)
        s.baseline = round(s.mean, 1) if s.mean is not None else None
        n = len(daily)
        s.note = (f"{n} pesagens no período (~{n / max(1, _span_months(self._start, self._end)):.0f}/mês) — "
                  "tendência direcional, não granular")
        return s

    def _sleep_series(self) -> MetricSeries:
        rows = self._query(
            "garmin.db",
            "SELECT day, total_sleep FROM sleep "
            "WHERE date(day) >= ? AND date(day) <= ? AND total_sleep IS NOT NULL",
            (self._start.isoformat(), self._end.isoformat()),
        )
        daily = {}
        for d, total in rows:
            day = _parse_date(d)
            if day is not None and total is not None:
                daily[day] = _parse_hms(total) / 3600.0
        s = MetricSeries(key="sleep", label="Sono total", unit="h",
                         better="up", decimals=1)
        s.points = self._monthly_mean_points(daily, 2)
        s.baseline = round(s.mean, 1) if s.mean is not None else None
        return s

    def _vo2max_series(self, table: str) -> MetricSeries:
        disc = "ciclismo" if table == "cycle_activities" else "corrida"
        rows = self._query(
            "garmin_activities.db",
            f"SELECT a.start_time, t.vo2_max FROM {table} t "
            "JOIN activities a ON t.activity_id = a.activity_id "
            "WHERE t.vo2_max IS NOT NULL "
            "AND date(a.start_time) >= ? AND date(a.start_time) <= ?",
            (self._start.isoformat(), self._end.isoformat()),
        )
        monthly: Dict[str, float] = {}
        for ts, v in rows:
            day = _parse_date(ts)
            if day is None or v is None:
                continue
            ym = _ym(day)
            monthly[ym] = max(monthly.get(ym, 0.0), float(v))  # best estimate/mo
        s = MetricSeries(
            key=f"vo2max_{disc}", label=f"VO2max estimado ({disc})",
            unit="mL/kg/min", better="up", decimals=0,
        )
        s.points = [
            (ym, round(monthly[ym], 0) if ym in monthly else None)
            for ym in _month_keys(self._start, self._end)
        ]
        return s

    def _anaerobic_te_series(self) -> MetricSeries:
        """Monthly MEAN anaerobic Training Effect (0-5) across activities.

        Unlike VO2max (best estimate per month), anaerobic TE is a per-session
        high-intensity dose, so the monthly mean is the meaningful summary.
        """
        rows = self._query(
            "garmin_activities.db",
            "SELECT start_time, anaerobic_training_effect FROM activities "
            "WHERE anaerobic_training_effect IS NOT NULL "
            "AND date(start_time) >= ? AND date(start_time) <= ?",
            (self._start.isoformat(), self._end.isoformat()),
        )
        monthly: Dict[str, List[float]] = {}
        for ts, v in rows:
            day = _parse_date(ts)
            if day is None or v is None:
                continue
            monthly.setdefault(_ym(day), []).append(float(v))
        s = MetricSeries(
            key="anaerobic_te", label="Training Effect anaeróbico",
            unit="", better="neutral", decimals=1)
        s.points = [
            (ym, round(sum(monthly[ym]) / len(monthly[ym]), 4)
             if ym in monthly else None)
            for ym in _month_keys(self._start, self._end)
        ]
        n = sum(len(v) for v in monthly.values())
        s.note = (f"{n} atividades com TE anaeróbico; escala 0–5 (estímulo de "
                  "alta intensidade), complementa o TE aeróbico") if n else None
        return s

    # -- series helpers ----------------------------------------------------- #

    def _monthly_mean_points(
        self, daily: Dict[date, float], decimals: int
    ) -> List[Tuple[str, Optional[float]]]:
        # Store at full-ish precision (4 dp) and let the renderer round ONCE to
        # `decimals` for display. Pre-rounding here to the display precision and
        # rounding again at render time double-rounds boundary values (e.g. a
        # 7.747 h mean -> 7.75 -> 7.8 instead of the correct 7.7).
        buckets: Dict[str, List[float]] = {}
        for day, v in daily.items():
            buckets.setdefault(_ym(day), []).append(v)
        points: List[Tuple[str, Optional[float]]] = []
        for ym in _month_keys(self._start, self._end):
            vals = buckets.get(ym)
            points.append((ym, round(sum(vals) / len(vals), 4)
                           if vals else None))
        return points

    def _baseline_band(
        self, daily: Dict[date, float], decimals: int
    ) -> Tuple[Optional[float], Optional[float], Optional[float]]:
        """Chronic baseline = mean ± 1 SD over [start, end-60d] (or all if short)."""
        cutoff = self._end - timedelta(days=60)
        chronic = [v for d, v in daily.items() if d <= cutoff] or list(daily.values())
        if not chronic:
            return None, None, None
        mean = sum(chronic) / len(chronic)
        var = sum((x - mean) ** 2 for x in chronic) / len(chronic)
        std = var ** 0.5
        # Full precision; the renderer rounds to `decimals` once for display and
        # the screen compares at display precision (see _screen) so a flag never
        # contradicts the band the reader sees.
        return round(mean, 4), round(mean - std, 4), round(mean + std, 4)

    # -- red-flag screen ---------------------------------------------------- #

    def _screen(
        self,
        series: Dict[str, MetricSeries],
        acwr: Optional[float],
        monotony: Optional[float],
        ramp: Optional[float],
        current_load: Optional[TrainingLoadMonth],
        volume: List[VolumeMonth],
    ) -> List[RedFlag]:
        # Uses the SAME 'current' value the panel shows (the latest month) and
        # the personal baseline BAND, so a flag can never contradict the
        # dashboard (e.g. flag "RHR up" while the panel marks RHR stable).
        flags: List[RedFlag] = []
        markers: List[str] = []   # recent recovery/autonomic markers that fired

        # 1. Resting-HR above the personal band (out of range, unfavourable).
        # Compared at DISPLAY precision so the flag never reads "55 vs 49-55".
        rhr = series.get("rhr")
        if (rhr and rhr.baseline_high is not None and rhr.current is not None
                and round(rhr.current, rhr.decimals)
                > round(rhr.baseline_high, rhr.decimals)):
            markers.append("FC de repouso")
            flags.append(RedFlag(
                severity="warning",
                title="FC de repouso acima da faixa pessoal",
                finding=(f"FC repouso atual {rhr.current:.0f} bpm vs faixa "
                         f"{rhr.baseline_low:.0f}–{rhr.baseline_high:.0f} bpm"),
                detail=("Elevação da FC de repouso acima da base é sinal de fadiga "
                        "acumulada. Confundidores: doença, calor, álcool, desidratação."),
                recommendation=("Cruzar com VFC e sono; reduzir carga se persistir "
                                "após descanso."),
            ))

        # 2. HRV below the personal band.
        hrv = series.get("hrv")
        if (hrv and hrv.baseline_low is not None and hrv.current is not None
                and hrv.baseline and round(hrv.current, hrv.decimals)
                < round(hrv.baseline_low, hrv.decimals)):
            pct = (hrv.current / hrv.baseline - 1) * 100
            markers.append("VFC")
            flags.append(RedFlag(
                severity="warning",
                title="VFC noturna abaixo da faixa pessoal",
                finding=(f"VFC atual {hrv.current:.0f} ms vs base {hrv.baseline:.0f} "
                         f"(faixa {hrv.baseline_low:.0f}–{hrv.baseline_high:.0f}; "
                         f"{pct:.0f}%)"),
                detail=("Redução do tônus parassimpático; em endurance deve ser lida "
                        "junto da FC de repouso e da performance. Estimativa de pulso."),
                recommendation=("Acompanhar 1–2 semanas; priorizar sono e recuperação."),
            ))

        # 2b. Stress above the personal band (not merely above the mean).
        stress = series.get("stress")
        if (stress and stress.baseline_high is not None
                and stress.current is not None
                and round(stress.current, stress.decimals)
                > round(stress.baseline_high, stress.decimals)):
            markers.append("estresse")
            flags.append(RedFlag(
                severity="info",
                title="Estresse médio acima da faixa pessoal",
                finding=(f"Estresse atual {stress.current:.0f} vs faixa "
                         f"{stress.baseline_low:.0f}–{stress.baseline_high:.0f}"),
                detail=("Escore de estresse do Garmin (derivado de VFC) acima da base "
                        "pessoal; marcador autonômico/psicológico de carga."),
                recommendation="Cruzar com sono e VFC; gerenciar estressores não-treino.",
            ))

        # 3. Body Battery ceiling declining (recent vs start of period).
        bb = series.get("body_battery")
        if bb and len(bb.values) >= 4 and bb.current is not None:
            early = bb.values[0]
            if early and bb.current <= 0.85 * early:
                markers.append("Body Battery")
                flags.append(RedFlag(
                    severity="warning",
                    title="Teto de Body Battery em queda",
                    finding=(f"Pico de Body Battery atual {bb.current:.0f} vs "
                             f"{early:.0f} no início do período"),
                    detail=("Pico de recarga noturna em declínio sugere recuperação "
                            "noturna incompleta / débito de recuperação."),
                    recommendation="Avaliar volume de sono e carga das últimas semanas.",
                ))

        # 4. Sleep below target (current month).
        sleep = series.get("sleep")
        if sleep and sleep.current is not None and sleep.current < 7.0:
            flags.append(RedFlag(
                severity="info",
                title="Sono abaixo do alvo",
                finding=f"Sono do mês atual {sleep.current:.1f} h (< 7 h)",
                detail=("Sono é o principal substrato de recuperação; déficit crônico "
                        "reduz adaptação e eleva risco de lesão/doença."),
                recommendation="Mirar ≥7–8 h e regularidade de horário.",
            ))

        # 5. Body weight loss rate (RED-S screen).
        weight = series.get("weight")
        if weight and weight.first and weight.current:
            drop_pct = (weight.first - weight.current) / weight.first * 100
            months = max(1, _span_months(self._start, self._end))
            per_month = drop_pct / months
            if per_month >= 1.0:
                flags.append(RedFlag(
                    severity="info",
                    title="Tendência de perda de peso",
                    finding=(f"{weight.first:.1f} → {weight.current:.1f} kg "
                             f"(−{drop_pct:.1f}% no período, ~{per_month:.1f}%/mês)"),
                    detail=("Triagem de RED-S / baixa disponibilidade energética. "
                            "Perda modesta e intencional ('peso de prova') é comum; "
                            "perda involuntária sob alta carga merece avaliação nutricional."),
                    recommendation=("Confirmar se é intencional; se não, investigar "
                                    "disponibilidade energética."),
                ))

        # 6. ACWR out of the safe band.
        if acwr is not None and (acwr > 1.5 or acwr < 0.8):
            sev = "warning" if acwr > 1.5 else "info"
            flags.append(RedFlag(
                severity=sev,
                title="Razão carga aguda:crônica fora da faixa",
                finding=f"ACWR (7d:28d) = {acwr:.2f}",
                detail=("Faixa de menor risco 0,8–1,3; >1,5 indica pico de carga "
                        "associado a maior risco de lesão/doença nos dias seguintes."),
                recommendation=("Suavizar progressão de carga semanal (≤10%)."
                                if acwr > 1.5 else
                                "Carga baixa relativa — ok se planejado (recuperação/taper)."),
            ))

        # 7. Training monotony high (Foster).
        if monotony is not None and monotony > 2.0:
            flags.append(RedFlag(
                severity="info",
                title="Monotonia de treino elevada",
                finding=f"Monotonia (28d) = {monotony:.2f} (>2,0)",
                detail=("Carga diária muito uniforme, com pouca variação duro/fácil; "
                        "associada a maior risco de overuse."),
                recommendation="Introduzir mais contraste (dias realmente fáceis + descanso).",
            ))

        # 8. CTL ramp rate too steep.
        if ramp is not None and ramp > 8:
            flags.append(RedFlag(
                severity="info",
                title="Rampa de fitness (CTL) acelerada",
                finding=f"CTL subindo ~{ramp:.1f}/semana (>8)",
                detail="Progressão de fitness rápida eleva risco se mantida.",
                recommendation="Vigiar recuperação; considerar semana de descarga.",
            ))

        # 9. Deeply negative TSB without taper context.
        if current_load is not None and current_load.tsb < -25:
            flags.append(RedFlag(
                severity="info",
                title="Forma (TSB) muito negativa",
                finding=f"TSB atual {current_load.tsb:.0f}",
                detail="Fadiga elevada relativa ao fitness; esperado em bloco de carga, "
                       "não em taper.",
                recommendation="Confirmar que há descarga planejada antes da prova.",
            ))

        # Synthesis: >=2 recent recovery markers out of band -> a single
        # contextualised top item. Crucially it is framed against the partial
        # current month (deload week) and a rising VO2max, so it does NOT assert
        # overtraining when the report's own panel shows performance improving.
        if len(markers) >= 2:
            vo2_up = any(series.get(k) and series[k].verdict() == "good"
                         for k in ("vo2max_cycling", "vo2max_running"))
            ctx = []
            if self._end.day < 25:
                ctx.append("o mês atual está incompleto (semana de baixo volume / "
                           "descarga)")
            if vo2_up:
                ctx.append("a aptidão aeróbica (VO2max) ainda está em tendência de alta")
            detail = ("Vários marcadores de recuperação fora da faixa ao mesmo tempo "
                      "podem indicar débito de recuperação / overreaching incipiente.")
            if ctx:
                detail += (" Porém, " + "; ".join(ctx)
                           + " — o que favorece a leitura de queda transitória de "
                           "descarga, e não de maladaptação.")
            flags.insert(0, RedFlag(
                severity="warning",
                title="Quadro recente de recuperação a vigiar",
                finding=("Marcadores fora da faixa no período recente: "
                         + ", ".join(markers)),
                detail=detail,
                recommendation=("Reavaliar quando o volume retomar (1–2 semanas); se a "
                                "VFC não recuperar com a retomada do treino, investigar "
                                "clinicamente."),
            ))

        return flags

    @staticmethod
    def _readiness(flags: List[RedFlag], series: Dict[str, MetricSeries]):
        """One-line overall verdict for the top of the panel (triage by colour)."""
        if any(f.severity == "alert" for f in flags):
            return "🔴", "sinais que pedem avaliação clínica — ver alertas"
        if any(f.severity == "warning" for f in flags):
            vo2_up = any(series.get(k) and series[k].verdict() == "good"
                         for k in ("vo2max_cycling", "vo2max_running"))
            if vo2_up:
                label = ("aptidão aeróbica em alta; sinais recentes de "
                         "recuperação a vigiar — reavaliar em 1–2 semanas")
                return "🟡", label
            return "🟡", "sinais recentes a vigiar — ver alertas"
        return "🟢", "métricas dentro das faixas pessoais habituais"

    # -- misc --------------------------------------------------------------- #

    def _days_to_race(self) -> Optional[int]:
        if not self._targets.race_date:
            return None
        try:
            race = datetime.strptime(self._targets.race_date, "%Y-%m-%d").date()
        except ValueError:
            return None
        return max(0, (race - self._end).days)


# --------------------------------------------------------------------------- #
# Module-level helpers
# --------------------------------------------------------------------------- #

def _parse_date(value) -> Optional[date]:
    """Parse a DB datetime/date value to a ``date`` (None if unparseable).

    DB timestamps are stored in LOCAL time (converted from UTC at import), so the
    leading ``YYYY-MM-DD`` is already the local calendar day we want to bucket by.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    head = text.replace("T", " ").split(" ")[0]  # date part of any datetime form
    try:
        return datetime.strptime(head, "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(text).date()
    except ValueError:
        return None


def _parse_hms(value) -> float:
    """Parse an 'HH:MM:SS[.ffffff]' TIME string to seconds (0.0 if blank)."""
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    try:
        parts = text.split(":")
        if len(parts) == 3:
            h, m, s = parts
            return int(h) * 3600 + int(m) * 60 + float(s)
        if len(parts) == 2:
            m, s = parts
            return int(m) * 60 + float(s)
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
            m = 1
            y += 1
    return keys


def _span_months(start: date, end: date) -> int:
    return (end.year - start.year) * 12 + (end.month - start.month) + 1


def _last_day_present(
    loads: Dict[date, float], ym: str, end: date
) -> Optional[date]:
    """Last day in ``loads`` belonging to month ``ym`` (capped at ``end``)."""
    year, month = int(ym[:4]), int(ym[5:7])
    candidate = None
    for d in loads:
        if d.year == year and d.month == month and d <= end:
            if candidate is None or d > candidate:
                candidate = d
    return candidate


def _ewma_series(daily: Dict[date, float], window: int) -> Dict[date, float]:
    """Day-by-day EWMA (α=2/(w+1)), seeded with the first value -- matches
    :meth:`ActivityAnalyzer._calculate_ema` but keeps the whole trajectory."""
    alpha = 2 / (window + 1)
    out: Dict[date, float] = {}
    ema: Optional[float] = None
    for d in sorted(daily):
        v = daily[d]
        ema = v if ema is None else alpha * v + (1 - alpha) * ema
        out[d] = ema
    return out


def _sparkline(values: Sequence[Optional[float]]) -> str:
    """Render a unicode block sparkline; gaps (None) become a low dot."""
    present = [v for v in values if v is not None]
    if not present:
        return ""
    lo, hi = min(present), max(present)
    span = hi - lo
    chars = []
    for v in values:
        if v is None:
            chars.append("·")
        elif span == 0:
            chars.append(_SPARK_BLOCKS[0])
        else:
            idx = int((v - lo) / span * (len(_SPARK_BLOCKS) - 1))
            chars.append(_SPARK_BLOCKS[idx])
    return "".join(chars)


def _num(value: Optional[float], decimals: int = 1) -> str:
    if value is None:
        return "—"
    return f"{value:.{decimals}f}".replace(".", ",")
