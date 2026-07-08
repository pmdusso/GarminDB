"""Treinos dashboard DTO builder tests.

Hermetic SQLite fixtures mirror the BloodB Treinos contract without reading the
user's real Garmin DBs.
"""

import datetime as dt
import json
import sqlite3
from pathlib import Path

from garmindb.analysis.treinos_dashboard import build_dashboard


TODAY = dt.date(2026, 7, 7)
END = TODAY.isoformat()
GROUPS = {"cardiovascular", "metabolismo", "carga-performance", "recuperacao-sono"}


def _mk_dbs(root: Path):
    garmin = sqlite3.connect(root / "garmin.db")
    garmin.executescript("""
        CREATE TABLE resting_hr (day TEXT, resting_heart_rate REAL);
        CREATE TABLE daily_summary (
            day TEXT, spo2_avg REAL, spo2_min REAL, rr_waking_avg REAL,
            calories_total REAL, calories_active REAL, calories_bmr REAL,
            hydration_intake REAL, hydration_goal REAL, steps REAL,
            stress_avg REAL, bb_charged REAL, bb_max REAL, bb_min REAL
        );
        CREATE TABLE weight (day TEXT, weight REAL);
        CREATE TABLE sleep (
            day TEXT, total_sleep TEXT, deep_sleep TEXT, rem_sleep TEXT,
            light_sleep TEXT, score REAL, qualifier TEXT, start TEXT
        );
        CREATE TABLE hrv (
            day TEXT, weekly_avg REAL, last_night_avg REAL, status TEXT,
            baseline_low REAL, baseline_upper REAL
        );
        CREATE TABLE training_readiness (
            day TEXT, timestamp TEXT, score REAL, level TEXT,
            feedback_short TEXT, recovery_time REAL
        );
    """)
    for i in range(10):
        day = (TODAY - dt.timedelta(days=i)).isoformat()
        day_dt = f"{day} 00:00:00.000000"
        garmin.execute("INSERT INTO resting_hr VALUES (?, ?)", (day, 50 + i % 3))
        garmin.execute(
            "INSERT INTO daily_summary VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (day_dt, 96, 92, 14.2, 2900, 800, 2100, 2000, 3000,
             9000 + i, 32, 70, 95, 20),
        )
        garmin.execute("INSERT INTO weight VALUES (?, ?)", (day, 84.0 - i * 0.1))
        garmin.execute(
            "INSERT INTO sleep VALUES (?,?,?,?,?,?,?,?)",
            (day, "07:30:00", "01:10:00", "01:40:00", "04:40:00",
             82, "GOOD", f"{day} 23:10:00"),
        )
        garmin.execute(
            "INSERT INTO hrv VALUES (?,?,?,?,?,?)",
            (day, 52, 50 + i % 5, "BALANCED", 45, 60),
        )
    garmin.execute(
        "INSERT INTO training_readiness VALUES (?,?,?,?,?,?)",
        (END, f"{END} 07:00:00", 78, "HIGH", "READY", 12),
    )
    garmin.commit()
    garmin.close()

    summary = sqlite3.connect(root / "garmin_summary.db")
    summary.execute("CREATE TABLE days_summary (day TEXT, rhr_avg REAL)")
    for i in range(10):
        day_dt = f"{(TODAY - dt.timedelta(days=i)).isoformat()} 00:00:00.000000"
        summary.execute("INSERT INTO days_summary VALUES (?, ?)", (day_dt, 51 + i % 3))
    summary.commit()
    summary.close()

    activities = sqlite3.connect(root / "garmin_activities.db")
    activities.executescript("""
        CREATE TABLE activities (
            activity_id TEXT, start_time TEXT, sport TEXT, distance REAL,
            moving_time TEXT, training_load REAL, training_effect REAL,
            anaerobic_training_effect REAL, max_hr REAL, start_lat REAL,
            start_long REAL, name TEXT, description TEXT
        );
        CREATE TABLE cycle_activities (activity_id TEXT, vo2_max REAL);
    """)
    for i in range(6):
        day = (TODAY - dt.timedelta(days=i * 2)).isoformat()
        activities.execute(
            "INSERT INTO activities VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (f"act{i}", f"{day} 06:30:00", "cycling", 40.0, "01:30:00",
             120.0, 3.4, 1.1, 168, -30.0, -51.0, "Secret ride", "Route home"),
        )
        activities.execute("INSERT INTO cycle_activities VALUES (?, ?)", (f"act{i}", 51.0))
    activities.commit()
    activities.close()


def test_build_dashboard_returns_treinos_v2_contract(tmp_path):
    _mk_dbs(tmp_path)
    config = tmp_path / "treinos-config.json"
    config.write_text(json.dumps({
        "ftp_history": [{"date": "2026-01-01", "ftp": 325}],
        "ftp_target": 320,
        "weight_target": [80, 82],
        "wkg_target": 4.0,
        "sleep_target_h": 7.5,
        "birth_date": "1988-03-11",
    }))

    dashboard = build_dashboard(
        db_dir=str(tmp_path),
        config_path=str(config),
        period_end=END,
    )

    assert set(dashboard) == GROUPS
    for group in dashboard.values():
        assert group["period_end"] == END
        assert isinstance(group["hero"], list)
        assert isinstance(group["insights"], list)
        assert group["main_chart"]["x"]
        assert all(len(day) == 10 and " " not in day for day in group["main_chart"]["x"])
        for series in group["main_chart"]["series"]:
            assert len(series["values"]) == len(group["main_chart"]["x"])

    assert dashboard["carga-performance"]["zones"]
    assert dashboard["carga-performance"]["scorecard"]
    assert dashboard["recuperacao-sono"]["main_chart"]["target"] == 7.5


def test_build_dashboard_payload_excludes_activity_pii(tmp_path):
    _mk_dbs(tmp_path)
    dashboard = build_dashboard(db_dir=str(tmp_path), period_end=END)
    dump = json.dumps(dashboard, ensure_ascii=False)

    assert "Secret ride" not in dump
    assert "Route home" not in dump
    assert "-51.0" not in dump
    assert "start_lat" not in dump
    assert "start_long" not in dump
    assert "description" not in dump


def test_build_dashboard_empty_db_gracefully_returns_four_groups(tmp_path):
    (tmp_path / "garmin.db").touch()
    (tmp_path / "garmin_summary.db").touch()
    (tmp_path / "garmin_activities.db").touch()

    dashboard = build_dashboard(db_dir=str(tmp_path), period_end=END)

    assert set(dashboard) == GROUPS
    for group in dashboard.values():
        assert group["hero"] == []
        assert group["main_chart"] is None
        assert group["charts"] == []
        assert group["insights"] == []
