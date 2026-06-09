# test/test_longitudinal_clinical.py
"""Tests for Phase 0 clinical metrics in the longitudinal anamnesis report.

Covers the 'harvest what we already store' metrics: SpO2, resting respiration,
anaerobic Training Effect, the full HRV band (weekly average + status),
overnight Body Battery recharge, sleep architecture, and operational max HR.

The synthetic-DB writers create the FULL Phase-0 schema so each metric test
supplies only the rows it cares about. The builder reads these DBs exactly like
production; columns left empty degrade to 'no data', never crash.
"""

import os
import sqlite3
from datetime import date, datetime

from garmindb.analysis.longitudinal_report import LongitudinalReportBuilder
from garmindb.analysis.performance_targets import PerformanceTargets
from garmindb.presentation.markdown.longitudinal_renderer import (
    LongitudinalPresenter,
)

GEN = datetime(2026, 6, 8, 12, 0, 0)


def _write_garmin_db(db_dir, *, daily=None, sleep=None, attrs=None, weight=None):
    """daily: {date: {spo2_avg, rr_waking_avg, bb_charged, bb_max, bb_min, rhr,
    stress_avg}}. sleep: {date: {total, deep, light, rem, awake, avg_stress,
    avg_spo2, avg_rr, score}}. Values default to NULL when a key is absent."""
    con = sqlite3.connect(os.path.join(db_dir, "garmin.db"))
    con.execute("CREATE TABLE attributes (timestamp TEXT, key TEXT, value TEXT)")
    for k, v in (attrs or {}).items():
        con.execute("INSERT INTO attributes VALUES (?,?,?)",
                    ("2026-06-08 00:00:00", k, str(v)))
    con.execute(
        "CREATE TABLE daily_summary "
        "(day TEXT, rhr INTEGER, stress_avg INTEGER, bb_max INTEGER, "
        "bb_min INTEGER, bb_charged INTEGER, spo2_avg FLOAT, spo2_min FLOAT, "
        "rr_waking_avg FLOAT, rr_max FLOAT, rr_min FLOAT)")
    for d, v in (daily or {}).items():
        con.execute(
            "INSERT INTO daily_summary "
            "(day, rhr, stress_avg, bb_max, bb_min, bb_charged, spo2_avg, "
            "rr_waking_avg) VALUES (?,?,?,?,?,?,?,?)",
            (f"{d} 00:00:00", v.get("rhr"), v.get("stress_avg"), v.get("bb_max"),
             v.get("bb_min"), v.get("bb_charged"), v.get("spo2_avg"),
             v.get("rr_waking_avg")))
    con.execute(
        "CREATE TABLE sleep "
        "(day TEXT, total_sleep TEXT, deep_sleep TEXT, light_sleep TEXT, "
        "rem_sleep TEXT, awake TEXT, avg_spo2 FLOAT, avg_rr FLOAT, "
        "avg_stress FLOAT, score INTEGER)")
    for d, v in (sleep or {}).items():
        con.execute(
            "INSERT INTO sleep (day, total_sleep, deep_sleep, light_sleep, "
            "rem_sleep, awake, avg_spo2, avg_rr, avg_stress, score) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (f"{d} 00:00:00", v.get("total"), v.get("deep"), v.get("light"),
             v.get("rem"), v.get("awake"), v.get("avg_spo2"), v.get("avg_rr"),
             v.get("avg_stress"), v.get("score")))
    con.execute("CREATE TABLE weight (day TEXT, weight FLOAT)")
    for d, kg in (weight or {}).items():
        con.execute("INSERT INTO weight VALUES (?,?)", (f"{d} 00:00:00", kg))
    con.commit()
    con.close()


def _write_activities_db(db_dir, activities):
    """activities: list of {id, day, sport, km, moving, ascent, load, te,
    anaerobic_te, avg_hr, max_hr, cal}."""
    con = sqlite3.connect(os.path.join(db_dir, "garmin_activities.db"))
    con.execute(
        "CREATE TABLE activities "
        "(activity_id TEXT, start_time TEXT, sport TEXT, distance FLOAT, "
        "moving_time TEXT, ascent FLOAT, training_load FLOAT, "
        "training_effect FLOAT, anaerobic_training_effect FLOAT, "
        "avg_hr INTEGER, max_hr INTEGER, calories INTEGER)")
    con.execute("CREATE TABLE cycle_activities (activity_id TEXT, vo2_max FLOAT)")
    con.execute("CREATE TABLE steps_activities (activity_id TEXT, vo2_max FLOAT)")
    for a in activities:
        con.execute(
            "INSERT INTO activities (activity_id, start_time, sport, distance, "
            "moving_time, ascent, training_load, training_effect, "
            "anaerobic_training_effect, avg_hr, max_hr, calories) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(a["id"]), f"{a['day']} 10:00:00", a.get("sport", "cycling"),
             a.get("km", 0.0), a.get("moving", "01:00:00"), a.get("ascent", 0.0),
             a.get("load"), a.get("te"), a.get("anaerobic_te"),
             a.get("avg_hr"), a.get("max_hr"), a.get("cal", 0)))
    con.commit()
    con.close()


def _write_monitoring_db(db_dir, hrv=None):
    """hrv: {date: {last_night_average, weekly_average, baseline_low,
    baseline_high, status}}."""
    con = sqlite3.connect(os.path.join(db_dir, "garmin_monitoring.db"))
    con.execute(
        "CREATE TABLE monitoring_hrv_status "
        "(timestamp TEXT, weekly_average FLOAT, last_night FLOAT, "
        "last_night_average FLOAT, baseline_low FLOAT, baseline_high FLOAT, "
        "status INTEGER, reading_count INTEGER)")
    for d, v in (hrv or {}).items():
        con.execute(
            "INSERT INTO monitoring_hrv_status (timestamp, weekly_average, "
            "last_night_average, baseline_low, baseline_high, status) "
            "VALUES (?,?,?,?,?,?)",
            (f"{d} 07:00:00", v.get("weekly_average"),
             v.get("last_night_average"), v.get("baseline_low"),
             v.get("baseline_high"), v.get("status")))
    con.commit()
    con.close()


def _builder(db_dir, start, end, targets=None):
    return LongitudinalReportBuilder(
        db_dir=str(db_dir), targets=targets or PerformanceTargets(),
        start_date=start, end_date=end, generated_at=GEN,
    )


def _spread_daily(start, months, value_fn):
    """5 days per month, each day's dict = value_fn('YYYY-MM')."""
    out = {}
    y, m = start.year, start.month
    for _ in range(months):
        for d in range(1, 6):
            out[date(y, m, d).isoformat()] = value_fn(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


# --------------------------------------------------------------------------- #
# SpO2
# --------------------------------------------------------------------------- #

def test_spo2_series_monthly_mean_and_coverage_note(tmp_path):
    daily = _spread_daily(date(2025, 1, 1), 6,
                          lambda ym: {"spo2_avg": 97.0 if ym < "2025-04"
                                      else 94.0})
    _write_garmin_db(str(tmp_path), daily=daily)
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 6, 30)).build()
    spo2 = report.series["spo2"]
    assert spo2.points[0] == ("2025-01", 97.0)
    assert spo2.current == 94.0
    assert spo2.better == "up"
    # Coverage is declared, not implied: 30 measured days (6 months x 5 days).
    assert spo2.note is not None and "30 dias medidos" in spo2.note


def test_spo2_renders_in_respiratory_section(tmp_path):
    daily = _spread_daily(date(2025, 1, 1), 3, lambda ym: {"spo2_avg": 96.0})
    _write_garmin_db(str(tmp_path), daily=daily)
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 3, 31)).build()
    md = LongitudinalPresenter().render(report)
    assert "Respiratório" in md
    assert "SpO2" in md


def test_respiratory_section_absent_when_no_spo2_or_rr(tmp_path):
    _write_garmin_db(str(tmp_path), daily=_spread_daily(
        date(2025, 1, 1), 2, lambda ym: {"rhr": 50}))
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 2, 28)).build()
    md = LongitudinalPresenter().render(report)
    assert "Respiratório" not in md


# --------------------------------------------------------------------------- #
# Respiration
# --------------------------------------------------------------------------- #

def test_respiration_series_and_renders_with_spo2(tmp_path):
    daily = _spread_daily(
        date(2025, 1, 1), 4,
        lambda ym: {"spo2_avg": 96.0,
                    "rr_waking_avg": 13.0 if ym < "2025-03" else 16.0})
    _write_garmin_db(str(tmp_path), daily=daily)
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 4, 30)).build()
    rr = report.series["respiracao"]
    assert rr.points[0] == ("2025-01", 13.0)
    assert rr.current == 16.0
    assert rr.better == "down"          # rising resting RR is unfavourable
    assert rr.note is not None and "dias medidos" in rr.note
    md = LongitudinalPresenter().render(report)
    assert "FR repouso (rpm)" in md
