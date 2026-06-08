# test/test_db_metrics.py
import os
import sqlite3
from datetime import date
from garmindb.analysis.db_metrics import get_latest_vo2max


def _make_activities_db(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE activities (activity_id INTEGER, start_time TIMESTAMP)")
    con.execute("CREATE TABLE cycle_activities (activity_id INTEGER, vo2_max FLOAT)")
    con.executemany("INSERT INTO activities VALUES (?, ?)",
                    [(1, "2026-05-01 10:00:00"), (2, "2026-05-20 10:00:00"), (3, "2025-01-01 10:00:00")])
    con.executemany("INSERT INTO cycle_activities VALUES (?, ?)",
                    [(1, 55.0), (2, 56.0), (3, 50.0)])
    con.commit()
    con.close()


def test_returns_max_vo2max_in_range(tmp_path):
    db_dir = str(tmp_path)
    _make_activities_db(os.path.join(db_dir, "garmin_activities.db"))
    result = get_latest_vo2max(db_dir, date(2026, 1, 1), date(2026, 6, 1))
    assert result == 56.0


def test_returns_none_when_no_data(tmp_path):
    db_dir = str(tmp_path)
    _make_activities_db(os.path.join(db_dir, "garmin_activities.db"))
    assert get_latest_vo2max(db_dir, date(2030, 1, 1), date(2030, 12, 31)) is None


def test_returns_none_when_db_missing(tmp_path):
    assert get_latest_vo2max(str(tmp_path), date(2026, 1, 1), date(2026, 6, 1)) is None


def test_returns_none_when_schema_missing_table(tmp_path):
    # Old-schema / corrupt DB: the file exists but has no cycle_activities table.
    # The query must not raise; it must log a warning and return None so the
    # rest of the report (power/recovery/sleep) survives.
    db_dir = str(tmp_path)
    path = os.path.join(db_dir, "garmin_activities.db")
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE activities (activity_id INTEGER, start_time TIMESTAMP)")
    con.commit()
    con.close()
    assert get_latest_vo2max(db_dir, date(2026, 1, 1), date(2026, 6, 1)) is None
