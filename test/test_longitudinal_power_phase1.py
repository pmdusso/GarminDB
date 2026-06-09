# test/test_longitudinal_power_phase1.py
"""Phase 1: real power replaces the 'no power data' falsehood in --anamnesis."""

import json
import os
import sqlite3
from datetime import date, datetime

from garmindb.analysis.longitudinal_report import LongitudinalReportBuilder
from garmindb.analysis.performance_targets import PerformanceTargets
from garmindb.presentation.markdown.longitudinal_renderer import (
    LongitudinalPresenter,
)

GEN = datetime(2026, 6, 8, 12, 0, 0)


def _min_garmin_db(db_dir):
    con = sqlite3.connect(os.path.join(db_dir, "garmin.db"))
    con.execute("CREATE TABLE attributes (timestamp TEXT, key TEXT, value TEXT)")
    con.execute("CREATE TABLE weight (day TEXT, weight FLOAT)")
    con.execute("INSERT INTO weight VALUES (?,?)", ("2026-05-25 00:00:00", 78.0))
    con.commit()
    con.close()


def _hard_ride(folder, aid, day, best20):
    payload = {"activityType": {"typeKey": "road_biking"}, "manufacturer": "GARMIN",
               "startTimeLocal": f"{day} 10:00:00", "maxAvgPower_1200": best20,
               "normPower": 295.0, "duration": 3600.0,
               "powerTimeInZone_2": 1800.0, "powerTimeInZone_4": 600.0}
    with open(os.path.join(folder, f"activity_{aid}.json"), "w") as f:
        json.dump(payload, f)


def _builder(db_dir, acts_dir, start, end, targets):
    return LongitudinalReportBuilder(
        db_dir=str(db_dir), targets=targets, start_date=start, end_date=end,
        generated_at=GEN, activities_dir=str(acts_dir))


def test_anamnesis_publishes_measured_eftp(tmp_path):
    db = tmp_path / "db"
    db.mkdir()
    acts = tmp_path / "acts"
    acts.mkdir()
    _min_garmin_db(str(db))
    for i, d in enumerate(("2026-05-20", "2026-05-27", "2026-06-02"), 1):
        _hard_ride(str(acts), i, d, 305)
    targets = PerformanceTargets(ftp_watts=325, wkg_target=4.0)
    report = _builder(db, acts, date(2026, 1, 1), date(2026, 6, 7), targets).build()
    md = LongitudinalPresenter().render(report)
    assert "Não há dados de potência" not in md       # falsehood removed
    assert "eFTP medido" in md
    assert "290" in md                                  # 305 * 0.95


def test_anamnesis_no_power_files_is_honest_not_false(tmp_path):
    db = tmp_path / "db"
    db.mkdir()
    acts = tmp_path / "acts"
    acts.mkdir()              # empty
    _min_garmin_db(str(db))
    targets = PerformanceTargets(ftp_watts=325)
    report = _builder(db, acts, date(2026, 1, 1), date(2026, 6, 7), targets).build()
    md = LongitudinalPresenter().render(report)
    # No rides -> honest "configured, untested", NOT the blanket "no power data".
    assert "Não há dados de potência" not in md   # the falsehood must not reappear
    assert "configurad" in md.lower()
