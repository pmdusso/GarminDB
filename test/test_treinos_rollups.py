import datetime as dt
import sqlite3

from garmindb.analysis.treinos_rollups import (
    daily_hrv_series,
    materialize_power_summary,
    materialize_training_load,
)


def test_training_load_rollup_is_idempotent_and_estimates_missing_load(tmp_path):
    db = sqlite3.connect(tmp_path / "garmin_activities.db")
    db.executescript("""
        CREATE TABLE activities (
            activity_id TEXT, start_time TEXT, sport TEXT, distance REAL,
            moving_time TEXT, elapsed_time TEXT, training_load REAL,
            training_effect REAL, anaerobic_training_effect REAL
        );
    """)
    db.execute(
        "INSERT INTO activities VALUES (?,?,?,?,?,?,?,?,?)",
        ("a1", "2026-07-01 06:00:00", "cycling", 20.0, "01:00:00", "01:05:00", 100.0, 3.0, 1.0),
    )
    db.execute(
        "INSERT INTO activities VALUES (?,?,?,?,?,?,?,?,?)",
        ("a2", "2026-07-01 18:00:00", "cycling", 10.0, "00:30:00", "00:32:00", None, 2.0, 0.5),
    )
    db.commit()
    db.close()

    materialize_training_load(tmp_path)
    materialize_training_load(tmp_path)

    db = sqlite3.connect(tmp_path / "garmin_activities.db")
    row = db.execute("SELECT * FROM daily_training_load").fetchone()
    count = db.execute("SELECT COUNT(*) FROM daily_training_load").fetchone()[0]
    db.close()

    assert count == 1
    assert row[0] == "2026-07-01"
    assert row[1] == "cycling"
    assert row[2] == 2
    assert row[3] == 1.5
    assert row[4] == 30.0
    assert row[5] == 118.0
    assert row[6] == 1
    assert row[7] == 2.5
    assert row[8] == 0.75


def test_power_summary_rollup_uses_activity_records_power(tmp_path):
    db = sqlite3.connect(tmp_path / "garmin_activities.db")
    db.executescript("""
        CREATE TABLE activities (
            activity_id TEXT, start_time TEXT, sport TEXT, moving_time TEXT
        );
        CREATE TABLE activity_records (
            activity_id TEXT, timestamp TEXT, power INTEGER
        );
    """)
    db.execute("INSERT INTO activities VALUES (?,?,?,?)", ("a1", "2026-07-02 07:00:00", "cycling", "00:05:00"))
    for i, power in enumerate([100, 200, 300, 400, 500], start=1):
        db.execute(
            "INSERT INTO activity_records VALUES (?,?,?)",
            ("a1", f"2026-07-02 07:00:0{i}", power),
        )
    db.commit()
    db.close()

    materialize_power_summary(tmp_path)

    db = sqlite3.connect(tmp_path / "garmin_activities.db")
    row = db.execute("SELECT activity_id, day, avg_power, max_power, best_5s, best_60s, sample_count FROM activity_power_summary").fetchone()
    db.close()

    assert row == ("a1", "2026-07-02", 300.0, 500, 300.0, None, 5)


def test_daily_hrv_series_prefers_monitoring_and_falls_back_to_garmin_hrv(tmp_path):
    mon = sqlite3.connect(tmp_path / "garmin_monitoring.db")
    mon.executescript("""
        CREATE TABLE monitoring_hrv_status (
            timestamp TEXT, weekly_average REAL, last_night_average REAL,
            baseline_low REAL, baseline_high REAL, status INTEGER
        );
    """)
    mon.execute(
        "INSERT INTO monitoring_hrv_status VALUES (?,?,?,?,?,?)",
        ("2023-01-01 00:00:00", 54.0, 55.0, 45.0, 65.0, 4),
    )
    mon.commit()
    mon.close()

    garmin = sqlite3.connect(tmp_path / "garmin.db")
    garmin.executescript("""
        CREATE TABLE hrv (
            day TEXT, weekly_avg REAL, last_night_avg REAL, status TEXT,
            baseline_low REAL, baseline_upper REAL
        );
    """)
    garmin.execute("INSERT INTO hrv VALUES (?,?,?,?,?,?)", ("2023-01-01", 40, 41, "LOW", 35, 50))
    garmin.execute("INSERT INTO hrv VALUES (?,?,?,?,?,?)", ("2024-01-01", 48, 49, "BALANCED", 42, 62))
    garmin.commit()
    garmin.close()

    rows = daily_hrv_series(tmp_path, dt.date(2023, 1, 1), dt.date(2024, 1, 1))

    assert [(r["day"], r["last_night_avg"], r["source"]) for r in rows] == [
        ("2023-01-01", 55.0, "monitoring"),
        ("2024-01-01", 49.0, "garmin"),
    ]
