"""Tests for the Hr:speed aerobic-decoupling analyzer (SP2a).

Synthetic garmin_activities.db with per-second activity_records. Rides are built
deterministically so the efficiency-factor / decoupling math is exact: warmup is
trimmed (first 600 s), so the analysed window is [600 s, T); the HR break is
placed at the analysed midpoint, giving a known first-vs-second EF ratio.
"""

import os
import sqlite3
from datetime import date, datetime, timedelta

from types import SimpleNamespace

from garmindb.analysis.decoupling_analyzer import (
    DecouplingAnalyzer, DecouplingResult, RideDecoupling, PaHrResult, _ef,
)
from garmindb.presentation.markdown.longitudinal_renderer import (
    LongitudinalPresenter,
)


def _db(tmp_path):
    con = sqlite3.connect(os.path.join(str(tmp_path), "garmin_activities.db"))
    con.execute(
        "CREATE TABLE activities (activity_id TEXT, start_time TEXT, sport TEXT, "
        "sub_sport TEXT, moving_time TEXT, distance FLOAT)")
    con.execute(
        "CREATE TABLE activity_records (activity_id TEXT, record INTEGER, "
        "timestamp TEXT, hr INTEGER, speed FLOAT, position_lat FLOAT, "
        "power INTEGER)")
    return con


def _hms(seconds):
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}.000000"


def _add_ride(con, aid, day, *, minutes=70, sub_sport="generic", gps=True,
              hr_fn=None, speed_fn=None, power_fn=None):
    """Insert one ride: activities row + per-second records (1 Hz)."""
    secs = minutes * 60
    start = datetime(day.year, day.month, day.day, 9, 0, 0)
    con.execute(
        "INSERT INTO activities VALUES (?,?,?,?,?,?)",
        (str(aid), start.strftime("%Y-%m-%d %H:%M:%S"), "cycling", sub_sport,
         _hms(secs), 35.0))
    hr_fn = hr_fn or (lambda e, t: 145)
    speed_fn = speed_fn or (lambda e, t: 30.0)
    rows = []
    for i in range(secs):
        ts = (start + timedelta(seconds=i)).strftime("%Y-%m-%d %H:%M:%S")
        lat = -30.05 if gps else None
        power = power_fn(i, secs) if power_fn else None
        rows.append((str(aid), i, ts, hr_fn(i, secs), speed_fn(i, secs), lat,
                     power))
    con.executemany("INSERT INTO activity_records VALUES (?,?,?,?,?,?,?)", rows)
    con.commit()


def _ramp_hr(low, high):
    """HR = low before the analysed midpoint, high after (warmup=600 s trimmed)."""
    def fn(e, total):
        mid = 600 + (total - 600) / 2.0
        return low if e < mid else high
    return fn


# --------------------------------------------------------------------------- #
# Pure-math helpers
# --------------------------------------------------------------------------- #

def test_ef_helper():
    assert _ef([(140, 28.0), (140, 32.0)]) == 30.0 / 140
    assert _ef([]) is None
    assert _ef([(0, 30.0)]) is None


def test_decoupling_math_exact():
    # speed 30 constant; HR 140 then 160 at the analysed midpoint.
    # ef1=30/140, ef2=30/160 -> decoupling = (160-140)/160 = 12.5%.
    samples = [(e, 140.0 if e < 2400 else 160.0, 30.0)
               for e in range(600, 4200)]
    ef1, ef2, dc, ef_all, cv = DecouplingAnalyzer._decoupling(samples)
    assert abs(dc - 12.5) < 0.2
    assert cv == 0.0
    assert ef1 > ef2


# --------------------------------------------------------------------------- #
# Full analyze() over a synthetic DB
# --------------------------------------------------------------------------- #

def test_outdoor_steady_ride_decoupling(tmp_path):
    con = _db(tmp_path)
    _add_ride(con, 1, date(2026, 5, 20), hr_fn=_ramp_hr(140, 160))
    con.close()
    r = DecouplingAnalyzer(str(tmp_path)).analyze(date(2026, 1, 1),
                                                  date(2026, 6, 7))
    assert isinstance(r, DecouplingResult)
    assert r.eligible_count == 1 and r.analyzed_count == 1
    ride = r.rides[0]
    assert abs(ride.decoupling_pct - 12.5) < 0.3
    assert ride.steady is True
    assert ride.ef_first > ride.ef_second


def test_indoor_and_short_and_nogps_excluded(tmp_path):
    con = _db(tmp_path)
    _add_ride(con, 1, date(2026, 5, 20), sub_sport="indoor_cycling")  # indoor
    _add_ride(con, 2, date(2026, 5, 21), sub_sport="virtual_activity")  # virtual
    _add_ride(con, 3, date(2026, 5, 22), minutes=30)                   # too short
    _add_ride(con, 4, date(2026, 5, 23), gps=False)                    # no GPS
    con.close()
    r = DecouplingAnalyzer(str(tmp_path)).analyze(date(2026, 1, 1),
                                                  date(2026, 6, 7))
    assert r.eligible_count == 0
    assert r.rides == []


def test_unsteady_ride_gated_out(tmp_path):
    con = _db(tmp_path)
    # Speed alternates 10/50 (mean 30, cv ~0.67) -> fails the steadiness gate.
    _add_ride(con, 1, date(2026, 5, 20),
              speed_fn=lambda e, t: 10.0 if (e // 1) % 2 == 0 else 50.0)
    con.close()
    r = DecouplingAnalyzer(str(tmp_path)).analyze(date(2026, 1, 1),
                                                  date(2026, 6, 7))
    assert r.eligible_count == 1
    assert r.analyzed_count == 0
    assert r.skipped_unsteady == 1
    assert r.rides == []


def test_positive_insight_for_low_decoupling(tmp_path):
    con = _db(tmp_path)
    _add_ride(con, 1, date(2026, 5, 20), hr_fn=_ramp_hr(140, 145))  # ~3.4%
    con.close()
    r = DecouplingAnalyzer(str(tmp_path)).analyze(date(2026, 1, 1),
                                                  date(2026, 6, 7))
    assert r.rides[0].decoupling_pct < 5.0
    assert any(i.severity.value == "positive" for i in r.insights)
    # monthly trend carries the May bucket.
    assert ("2026-05", r.rides[0].decoupling_pct) in r.monthly_decoupling


def test_empty_db_is_safe(tmp_path):
    r = DecouplingAnalyzer(str(tmp_path)).analyze(date(2026, 1, 1),
                                                  date(2026, 6, 7))
    assert r.eligible_count == 0 and r.rides == [] and r.insights == []


# --------------------------------------------------------------------------- #
# Longitudinal (--anamnesis) rendering of the decoupling block
# --------------------------------------------------------------------------- #

def _result_with_ride(dc_pct, **kw):
    ride = RideDecoupling(
        activity_id="1", date=date(2026, 5, 20), moving_time_s=5400,
        distance_km=45.0, ef_first=0.214, ef_second=0.198, decoupling_pct=dc_pct,
        ef_overall=0.206, speed_cv=0.12, sample_count=4200, steady=True)
    return DecouplingResult(
        period_start=date(2026, 1, 1), period_end=date(2026, 6, 7),
        rides=[ride], monthly_decoupling=[("2026-05", dc_pct)],
        monthly_ef=[("2026-05", 0.206)], **kw)


def test_longitudinal_presenter_renders_decoupling():
    res = _result_with_ride(7.5, eligible_count=2, analyzed_count=1,
                            skipped_unsteady=1)
    md = LongitudinalPresenter(include_metadata=False)._decoupling(
        SimpleNamespace(decoupling=res))
    assert "FC:velocidade" in md
    assert "7.5%" in md and "2026-05" in md
    assert "variabilidade alta" in md


def test_longitudinal_presenter_decoupling_absent_is_empty():
    md = LongitudinalPresenter(include_metadata=False)._decoupling(
        SimpleNamespace(decoupling=None))
    assert md == ""


# --------------------------------------------------------------------------- #
# SP2b: Pa:Hr (power:HR) decoupling
# --------------------------------------------------------------------------- #

def test_pahr_outdoor_decoupling(tmp_path):
    con = _db(tmp_path)
    # constant 200 W, HR ramps 140->160 at the analysed midpoint -> 12.5%.
    _add_ride(con, 1, date(2026, 5, 20), hr_fn=_ramp_hr(140, 160),
              power_fn=lambda e, t: 200)
    con.close()
    r = DecouplingAnalyzer(str(tmp_path)).analyze_pahr(date(2026, 1, 1),
                                                       date(2026, 6, 7))
    assert isinstance(r, PaHrResult)
    assert r.eligible_count == 1 and r.analyzed_count == 1
    ride = r.rides[0]
    assert abs(ride.decoupling_pct - 12.5) < 0.3
    assert ride.indoor is False and ride.steady is True
    assert abs(ride.avg_power - 200) < 1


def test_pahr_includes_indoor_ungated(tmp_path):
    con = _db(tmp_path)
    _add_ride(con, 1, date(2026, 5, 21), sub_sport="indoor_cycling", gps=False,
              hr_fn=_ramp_hr(140, 160), power_fn=lambda e, t: 200)
    con.close()
    r = DecouplingAnalyzer(str(tmp_path)).analyze_pahr(date(2026, 1, 1),
                                                       date(2026, 6, 7))
    assert r.eligible_count == 1 and r.analyzed_count == 1
    assert r.rides[0].indoor is True
    assert r.rides[0].steady is None          # ungated indoors


def test_pahr_no_power_ride_excluded(tmp_path):
    con = _db(tmp_path)
    _add_ride(con, 1, date(2026, 5, 20))      # power_fn=None -> NULL power
    con.close()
    r = DecouplingAnalyzer(str(tmp_path)).analyze_pahr(date(2026, 1, 1),
                                                       date(2026, 6, 7))
    assert r.eligible_count == 0 and r.rides == []


def test_pahr_outdoor_unsteady_gated_out(tmp_path):
    con = _db(tmp_path)
    _add_ride(con, 1, date(2026, 5, 20), power_fn=lambda e, t: 200,
              speed_fn=lambda e, t: 10.0 if e % 2 == 0 else 50.0)
    con.close()
    r = DecouplingAnalyzer(str(tmp_path)).analyze_pahr(date(2026, 1, 1),
                                                       date(2026, 6, 7))
    assert r.eligible_count == 1 and r.analyzed_count == 0
    assert r.skipped_unsteady == 1 and r.rides == []


def test_pahr_keeps_zero_power_coasting(tmp_path):
    con = _db(tmp_path)
    # Alternate 200 W / 0 W (coasting) while moving -> zeros are kept as load.
    _add_ride(con, 1, date(2026, 5, 20),
              power_fn=lambda e, t: 200 if e % 2 == 0 else 0)
    con.close()
    r = DecouplingAnalyzer(str(tmp_path)).analyze_pahr(date(2026, 1, 1),
                                                       date(2026, 6, 7))
    assert r.eligible_count == 1
    # avg ~100 W proves coasting zeros were retained, not dropped.
    assert 80 < r.rides[0].avg_power < 120


def _pahr_result(dc_pct, indoor=False, **kw):
    from garmindb.analysis.decoupling_analyzer import PaHrRide
    ride = PaHrRide(
        activity_id="1", date=date(2026, 5, 20), moving_time_s=5400,
        indoor=indoor, ef_first=1.43, ef_second=1.25, decoupling_pct=dc_pct,
        ef_overall=1.34, avg_power=210.0, sample_count=4200,
        steady=(None if indoor else True))
    return PaHrResult(
        period_start=date(2026, 1, 1), period_end=date(2026, 6, 7),
        rides=[ride], monthly_decoupling=[("2026-05", dc_pct)],
        monthly_ef=[("2026-05", 1.34)], **kw)


def test_longitudinal_presenter_renders_pahr_with_indoor():
    res = _pahr_result(7.5, indoor=True, eligible_count=1, analyzed_count=1)
    md = LongitudinalPresenter(include_metadata=False)._pahr(
        SimpleNamespace(pahr=res))
    assert "potência:FC" in md
    assert "7.5%" in md and "2026-05" in md and "indoor" in md
    assert "210 W" in md


def test_longitudinal_presenter_pahr_absent_is_empty():
    md = LongitudinalPresenter(include_metadata=False)._pahr(
        SimpleNamespace(pahr=None))
    assert md == ""


def test_pahr_short_circuits_when_no_power_column(tmp_path):
    # Pre-SP1-rebuild DB: activity_records lacks a power column -> Pa:Hr returns
    # empty cleanly (no per-ride query flood, no crash).
    import sqlite3
    con = sqlite3.connect(os.path.join(str(tmp_path), "garmin_activities.db"))
    con.execute("CREATE TABLE activities (activity_id TEXT, start_time TEXT, "
                "sport TEXT, sub_sport TEXT, moving_time TEXT, distance FLOAT)")
    con.execute("CREATE TABLE activity_records (activity_id TEXT, record INTEGER, "
                "timestamp TEXT, hr INTEGER, speed FLOAT, position_lat FLOAT)")
    con.execute("INSERT INTO activities VALUES (?,?,?,?,?,?)",
                ("1", "2026-05-20 09:00:00", "cycling", "generic",
                 "01:10:00.000000", 35.0))
    con.commit()
    con.close()
    r = DecouplingAnalyzer(str(tmp_path)).analyze_pahr(date(2026, 1, 1),
                                                       date(2026, 6, 7))
    assert r.eligible_count == 0 and r.rides == [] and r.insights == []
