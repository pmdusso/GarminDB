# test/test_longitudinal_report.py
"""Tests for the longitudinal anamnesis report builder, screen and renderer."""

import os
import sqlite3
from datetime import date, datetime, timedelta

from garmindb.analysis.longitudinal_report import (
    LongitudinalReportBuilder,
    _ewma_series,
    _month_keys,
    _parse_date,
    _parse_hms,
    _sparkline,
    _ym,
)
from garmindb.analysis.performance_targets import PerformanceTargets
from garmindb.presentation.markdown.longitudinal_renderer import (
    LongitudinalPresenter,
)

GEN = datetime(2026, 6, 8, 12, 0, 0)


# --------------------------------------------------------------------------- #
# Synthetic DB builders
# --------------------------------------------------------------------------- #

def _write_garmin_db(db_dir, *, attrs=None, daily=None, sleep=None, weight=None):
    """daily: {date: {rhr, stress_avg, bb_max, bb_min}}; sleep: {date: (hms, score)};
    weight: {date: kg}; attrs: {key: value}."""
    con = sqlite3.connect(os.path.join(db_dir, "garmin.db"))
    con.execute("CREATE TABLE attributes (timestamp TEXT, key TEXT, value TEXT)")
    for k, v in (attrs or {}).items():
        con.execute("INSERT INTO attributes VALUES (?,?,?)",
                    ("2026-06-08 00:00:00", k, str(v)))
    con.execute("CREATE TABLE daily_summary "
                "(day TEXT, rhr INTEGER, stress_avg INTEGER, "
                "bb_max INTEGER, bb_min INTEGER)")
    for d, vals in (daily or {}).items():
        con.execute("INSERT INTO daily_summary VALUES (?,?,?,?,?)",
                    (f"{d} 00:00:00", vals.get("rhr"), vals.get("stress_avg"),
                     vals.get("bb_max"), vals.get("bb_min")))
    con.execute("CREATE TABLE sleep (day TEXT, total_sleep TEXT, score INTEGER)")
    for d, (hms, score) in (sleep or {}).items():
        con.execute("INSERT INTO sleep VALUES (?,?,?)", (f"{d} 00:00:00", hms, score))
    con.execute("CREATE TABLE weight (day TEXT, weight FLOAT)")
    for d, kg in (weight or {}).items():
        con.execute("INSERT INTO weight VALUES (?,?)", (f"{d} 00:00:00", kg))
    con.commit()
    con.close()


def _write_activities_db(db_dir, activities):
    """activities: list of dicts with id, day, sport, km, moving, ascent,
    load, te, cal, and optional cyc_vo2 / run_vo2."""
    con = sqlite3.connect(os.path.join(db_dir, "garmin_activities.db"))
    con.execute("CREATE TABLE activities "
                "(activity_id TEXT, start_time TEXT, sport TEXT, distance FLOAT, "
                "moving_time TEXT, ascent FLOAT, training_load FLOAT, "
                "training_effect FLOAT, calories INTEGER)")
    con.execute("CREATE TABLE cycle_activities (activity_id TEXT, vo2_max FLOAT)")
    con.execute("CREATE TABLE steps_activities (activity_id TEXT, vo2_max FLOAT)")
    for a in activities:
        aid = str(a["id"])
        con.execute("INSERT INTO activities VALUES (?,?,?,?,?,?,?,?,?)",
                    (aid, f"{a['day']} 10:00:00", a.get("sport", "cycling"),
                     a.get("km", 0.0), a.get("moving", "01:00:00"),
                     a.get("ascent", 0.0), a.get("load"), a.get("te"),
                     a.get("cal", 0)))
        if a.get("cyc_vo2") is not None:
            con.execute("INSERT INTO cycle_activities VALUES (?,?)",
                        (aid, a["cyc_vo2"]))
        if a.get("run_vo2") is not None:
            con.execute("INSERT INTO steps_activities VALUES (?,?)",
                        (aid, a["run_vo2"]))
    con.commit()
    con.close()


def _write_monitoring_db(db_dir, hrv):
    """hrv: {date: last_night_average}."""
    con = sqlite3.connect(os.path.join(db_dir, "garmin_monitoring.db"))
    con.execute("CREATE TABLE monitoring_hrv_status "
                "(timestamp TEXT, last_night_average FLOAT)")
    for d, v in (hrv or {}).items():
        con.execute("INSERT INTO monitoring_hrv_status VALUES (?,?)",
                    (f"{d} 07:00:00", v))
    con.commit()
    con.close()


def _builder(db_dir, start, end, targets=None):
    return LongitudinalReportBuilder(
        db_dir=str(db_dir), targets=targets or PerformanceTargets(),
        start_date=start, end_date=end, generated_at=GEN,
    )


# --------------------------------------------------------------------------- #
# Module-level helpers
# --------------------------------------------------------------------------- #

def test_parse_hms_handles_formats():
    assert _parse_hms("02:30:00") == 9000
    assert _parse_hms("00:00:00") == 0
    assert _parse_hms("01:00:00.500000") == 3600.5
    assert _parse_hms("45:30") == 45 * 60 + 30
    assert _parse_hms(None) == 0.0
    assert _parse_hms("") == 0.0


def test_parse_date_handles_formats():
    assert _parse_date("2026-05-30 10:00:00.000000") == date(2026, 5, 30)
    assert _parse_date("2026-05-30 10:00:00") == date(2026, 5, 30)
    assert _parse_date("2026-05-30") == date(2026, 5, 30)
    assert _parse_date(datetime(2026, 5, 30, 9)) == date(2026, 5, 30)
    assert _parse_date(None) is None
    assert _parse_date("not-a-date") is None


def test_ym_and_month_keys():
    assert _ym(date(2026, 3, 7)) == "2026-03"
    assert _month_keys(date(2025, 11, 1), date(2026, 2, 15)) == \
        ["2025-11", "2025-12", "2026-01", "2026-02"]


def test_ewma_series_matches_alpha_math():
    # window=1 -> alpha=1 -> EMA tracks the latest value exactly.
    s = _ewma_series({date(2025, 1, 1): 0.0, date(2025, 1, 2): 10.0}, window=1)
    assert s[date(2025, 1, 1)] == 0.0
    assert s[date(2025, 1, 2)] == 10.0
    # Constant input -> constant EMA regardless of window.
    flat = {date(2025, 1, 1) + timedelta(days=i): 100.0 for i in range(50)}
    out = _ewma_series(flat, window=42)
    assert abs(out[date(2025, 1, 1) + timedelta(days=49)] - 100.0) < 1e-9


def test_sparkline_levels_and_gaps():
    assert _sparkline([1, 2, 3]) == "▁▄█"
    assert _sparkline([5, 5, 5]) == "▁▁▁"      # zero span -> all lowest
    assert _sparkline([1, None, 3]) == "▁·█"   # None -> dot
    assert _sparkline([]) == ""


# --------------------------------------------------------------------------- #
# Volume / totals
# --------------------------------------------------------------------------- #

def test_distance_summed_as_km_not_meters(tmp_path):
    # Regression guard: activities.distance is already in km; summing must NOT
    # divide by 1000. Two 50 km + 100 km rides in a month -> 150 km, not 0.15.
    _write_garmin_db(str(tmp_path))
    _write_activities_db(str(tmp_path), [
        {"id": 1, "day": "2025-03-05", "km": 50.0, "moving": "02:00:00"},
        {"id": 2, "day": "2025-03-20", "km": 100.0, "moving": "04:00:00"},
    ])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 3, 1), date(2025, 3, 31)).build()
    march = next(v for v in report.volume if v.ym == "2025-03")
    assert march.distance_km == 150.0
    assert march.hours == 6.0
    assert march.activities == 2


def test_year_and_sport_totals(tmp_path):
    _write_garmin_db(str(tmp_path))
    _write_activities_db(str(tmp_path), [
        {"id": 1, "day": "2025-02-01", "sport": "cycling", "km": 40.0,
         "moving": "01:30:00", "ascent": 500, "cal": 800},
        {"id": 2, "day": "2025-02-02", "sport": "running", "km": 10.0,
         "moving": "01:00:00", "ascent": 100, "cal": 600},
        {"id": 3, "day": "2025-06-01", "sport": "cycling", "km": 60.0,
         "moving": "02:00:00", "ascent": 700, "cal": 1000},
    ])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 12, 31)).build()
    y2025 = next(y for y in report.year_totals if y.year == 2025)
    assert y2025.activities == 3
    assert y2025.distance_km == 110.0
    assert y2025.calories == 2400
    sports = {s.sport: s for s in report.sport_totals_by_year[2025]}
    assert sports["cycling"].count == 2
    assert sports["cycling"].distance_km == 100.0
    assert sports["running"].count == 1


# --------------------------------------------------------------------------- #
# Physiology series
# --------------------------------------------------------------------------- #

def _spread_days(start, months, value_fn, key="rhr"):
    """Build a daily dict: 5 days per month, value from value_fn(ym)."""
    daily = {}
    y, m = start.year, start.month
    for _ in range(months):
        for d in range(1, 6):
            daily[date(y, m, d).isoformat()] = {key: value_fn(f"{y:04d}-{m:02d}")}
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return daily


def test_rhr_series_monthly_mean_and_current(tmp_path):
    daily = _spread_days(date(2025, 1, 1), 6,
                         lambda ym: 50 if ym < "2025-06" else 56)
    _write_garmin_db(str(tmp_path), daily=daily)
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 6, 30)).build()
    rhr = report.series["rhr"]
    assert rhr.points[0] == ("2025-01", 50.0)
    assert rhr.current == 56.0
    assert rhr.better == "down"


def test_weight_current_is_median_rejecting_outlier(tmp_path):
    # Last reading (87.25) is an outlier vs the surrounding cluster ~84-86;
    # the robust "current" weight is the median of the recent 45 days.
    weight = {
        "2026-05-07": 84.6, "2026-05-10": 85.7, "2026-05-11": 85.8,
        "2026-05-27": 84.6, "2026-05-30": 87.25,
    }
    _write_garmin_db(str(tmp_path), weight=weight)
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2026, 1, 1), date(2026, 5, 31)).build()
    assert report.athlete.weight_kg == 85.7   # median of the 5 readings


# --------------------------------------------------------------------------- #
# Load metrics (unit-level)
# --------------------------------------------------------------------------- #

def test_acwr_band(tmp_path):
    b = _builder(tmp_path, date(2026, 1, 1), date(2026, 1, 28))
    flat = {b._end - timedelta(days=i): 100.0 for i in range(28)}
    assert b._acwr(flat) == 1.0
    spike = {b._end - timedelta(days=i): (200.0 if i < 7 else 50.0)
             for i in range(28)}
    assert b._acwr(spike) > 1.5


def test_monotony_none_when_no_variation(tmp_path):
    b = _builder(tmp_path, date(2026, 1, 1), date(2026, 1, 28))
    flat = {b._end - timedelta(days=i): 100.0 for i in range(28)}
    assert b._monotony(flat) is None     # std 0 -> undefined
    varied = {b._end - timedelta(days=i): (0.0 if i % 2 else 100.0)
              for i in range(28)}
    assert b._monotony(varied) is not None


# --------------------------------------------------------------------------- #
# Red-flag screen
# --------------------------------------------------------------------------- #

def _autonomic_decline_dbs(tmp_path):
    """Stable then declining: HRV high->low and stress low->high in last 2 mo."""
    rhr_daily = _spread_days(date(2025, 1, 1), 12, lambda ym: 50, key="rhr")
    # add stress to the same daily dict
    for d in rhr_daily:
        ym = d[:7]
        rhr_daily[d]["stress_avg"] = 28 if ym < "2025-11" else 35
        rhr_daily[d]["bb_max"] = 80
        rhr_daily[d]["bb_min"] = 25
    hrv = {}
    y, m = 2025, 1
    for _ in range(12):
        for d in range(1, 6):
            ym = f"{y:04d}-{m:02d}"
            hrv[date(y, m, d).isoformat()] = 72 if ym < "2025-11" else 55
        m += 1
        if m > 12:
            m, y = 1, y + 1
    _write_garmin_db(str(tmp_path), daily=rhr_daily)
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), hrv)


def test_convergence_alert_fires_on_hrv_and_stress(tmp_path):
    _autonomic_decline_dbs(tmp_path)
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 12, 31)).build()
    titles = [f.title for f in report.red_flags]
    assert any("VFC" in t for t in titles)
    assert any("Estresse" in t for t in titles)
    # Two out-of-band recovery markers -> contextual synthesis item, first,
    # framed as a warning (not an overtraining 'alert').
    assert report.red_flags[0].severity == "warning"
    assert "recuperação" in report.red_flags[0].title.lower()
    assert report.readiness_light == "🟡"


def test_no_flags_when_everything_stable(tmp_path):
    daily = {}
    y, m = 2025, 1
    for _ in range(12):
        for d in range(1, 6):
            daily[date(y, m, d).isoformat()] = {
                "rhr": 50, "stress_avg": 28, "bb_max": 80, "bb_min": 25}
        m += 1
        if m > 12:
            m, y = 1, y + 1
    sleep = {d: ("07:30:00", 82) for d in daily}
    hrv = {d: 70 for d in daily}
    _write_garmin_db(str(tmp_path), daily=daily, sleep=sleep)
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), hrv)
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 12, 31)).build()
    assert report.red_flags == []


# --------------------------------------------------------------------------- #
# Robustness + renderer
# --------------------------------------------------------------------------- #

def test_missing_dbs_do_not_crash(tmp_path):
    # No DB files at all: build must succeed with empty sections.
    report = _builder(tmp_path, date(2025, 1, 1), date(2026, 6, 8)).build()
    assert report.year_totals == []
    assert all(not s.values for s in report.series.values())
    # And the renderer must still produce a document.
    md = LongitudinalPresenter().render(report)
    assert "Anamnese esportiva" in md


def test_renderer_smoke_and_power_caveat(tmp_path):
    _write_garmin_db(
        str(tmp_path),
        attrs={"name": "Test Athlete", "year_of_birth": 1988,
               "gender": "Gender.male", "height": 1.91, "time_zone": "UTC"},
        weight={"2026-05-10": 85.0},
    )
    _write_activities_db(str(tmp_path), [
        {"id": 1, "day": "2025-03-05", "km": 50.0, "moving": "02:00:00",
         "load": 120, "te": 3.0, "cyc_vo2": 55},
    ])
    _write_monitoring_db(str(tmp_path), {"2025-03-05": 70})
    targets = PerformanceTargets(ftp_watts=325, weight_target_kg=80,
                                 wkg_target=4.0, race_name="Test Race",
                                 race_date="2026-09-27")
    report = _builder(tmp_path, date(2025, 1, 1), date(2026, 6, 8),
                      targets).build()
    md = LongitudinalPresenter().render(report)
    assert "# 🩺 Anamnese esportiva" in md
    assert "Painel clínico" in md
    assert "Sinais de alerta" in md
    assert "Procedência e limitações" in md
    # Data-honesty: no power data, FTP labelled as configured goal.
    assert "Não há dados de potência" in md
    assert "325 W" in md
    assert "masculino" in md       # sex translated


def test_days_and_weeks_to_race(tmp_path):
    targets = PerformanceTargets(race_date="2026-09-27")
    b = _builder(tmp_path, date(2025, 1, 1), date(2026, 6, 8), targets)
    days = (date(2026, 9, 27) - date(2026, 6, 8)).days
    assert b._days_to_race() == days       # 111
    report = b.build()
    assert report.days_to_race == days
    assert report.weeks_to_race == round(days / 7)   # 16, not floor 15
