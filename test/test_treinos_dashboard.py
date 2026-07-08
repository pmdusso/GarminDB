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
        CREATE TABLE connect_metric_raw (
            metric TEXT, period_start TEXT, period_end TEXT, granularity TEXT,
            payload_json TEXT, imported_at TEXT,
            PRIMARY KEY (metric, period_start, period_end, granularity)
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
    training_status = {
        "mostRecentTrainingStatus": {
            "latestTrainingStatusData": {
                "device-123": {
                    "calendarDate": END,
                    "trainingStatus": 4,
                    "trainingStatusFeedbackPhrase": "MAINTAINING_2",
                    "acuteTrainingLoadDTO": {
                        "dailyTrainingLoadAcute": 1068,
                        "dailyTrainingLoadChronic": 841,
                        "dailyAcuteChronicWorkloadRatio": 1.2,
                    },
                },
            },
        },
        "mostRecentTrainingLoadBalance": {
            "metricsTrainingLoadBalanceDTOMap": {
                "device-123": {
                    "calendarDate": END,
                    "trainingBalanceFeedbackPhrase": "AEROBIC_LOW_SHORTAGE",
                    "monthlyLoadAerobicLow": 491.1952,
                    "monthlyLoadAerobicLowTargetMin": 526,
                    "monthlyLoadAerobicLowTargetMax": 1179,
                    "monthlyLoadAerobicHigh": 2031.7542,
                    "monthlyLoadAerobicHighTargetMin": 670,
                    "monthlyLoadAerobicHighTargetMax": 1323,
                    "monthlyLoadAnaerobic": 755.1016,
                    "monthlyLoadAnaerobicTargetMin": 217,
                    "monthlyLoadAnaerobicTargetMax": 652,
                },
            },
        },
    }
    endurance_score = {"calendarDate": END, "overallScore": 7422, "classification": 5}
    garmin.execute(
        "INSERT INTO connect_metric_raw VALUES (?,?,?,?,?,?)",
        ("training_status", END, END, "daily", json.dumps(training_status), f"{END} 08:00:00"),
    )
    garmin.execute(
        "INSERT INTO connect_metric_raw VALUES (?,?,?,?,?,?)",
        ("endurance_score", END, END, "daily", json.dumps(endurance_score), f"{END} 08:00:00"),
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


def test_carga_performance_uses_official_connect_metrics(tmp_path):
    _mk_dbs(tmp_path)

    carga = build_dashboard(db_dir=str(tmp_path), period_end=END)["carga-performance"]

    assert any(h["label"] == "Status Garmin" and h["value"] == "Mantendo" for h in carga["hero"])
    assert {"label": "Endurance Score", "current": 7422, "target": None, "unit": ""} in carga["scorecard"]
    assert any(i["title"] == "Foco de carga Garmin" and "aeróbica baixa" in i["body"] for i in carga["insights"])

    ts = carga["training_status"]
    assert ts["status"] == {"label": "Mantendo", "level": "good", "note": "oficial Garmin Connect"}
    assert ts["vo2max"] == {"value": 51.0, "unit": "ml/kg/min"}
    assert ts["acute_load"] == {
        "value": 1068, "chronic": 841, "ratio": 1.2,
        "band_low": 0.8, "band_high": 1.3, "level": "good",
    }
    assert ts["hrv"]["value_ms"] == 52
    assert ts["hrv"]["label_pt"] == "Equilibrado"
    assert ts["hrv"]["level"] == "good"
    load_focus = {row["label"]: row for row in ts["load_focus"]}
    assert load_focus["Aeróbico baixo"] == {
        "label": "Aeróbico baixo", "current": 491, "target_min": 526, "target_max": 1179,
    }
    assert load_focus["Aeróbico alto"] == {
        "label": "Aeróbico alto", "current": 2032, "target_min": 670, "target_max": 1323,
    }
    assert load_focus["Anaeróbico"] == {
        "label": "Anaeróbico", "current": 755, "target_min": 217, "target_max": 652,
    }

    scorecard_labels = {row["label"] for row in carga["scorecard"]}
    assert "VO2max bike" not in scorecard_labels
    assert "Aeróbico baixo" not in scorecard_labels
    assert "Aeróbico alto" not in scorecard_labels
    assert "Anaeróbico" not in scorecard_labels

    dump = json.dumps(carga, ensure_ascii=False)
    assert "device-123" not in dump


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


def test_training_status_panel_renders_with_hrv_only_data(tmp_path):
    """HRV-only data (no official status/load/VO2max) should still produce training_status panel."""
    _mk_dbs(tmp_path)

    # Strip out official Garmin metrics to test HRV-only case
    garmin = sqlite3.connect(tmp_path / "garmin.db")
    garmin.execute("DELETE FROM connect_metric_raw")
    garmin.commit()
    garmin.close()

    # Strip out VO2max to ensure vo2max_value is None
    activities = sqlite3.connect(tmp_path / "garmin_activities.db")
    activities.execute("DELETE FROM cycle_activities")
    activities.commit()
    activities.close()

    carga = build_dashboard(db_dir=str(tmp_path), period_end=END)["carga-performance"]

    # training_status should NOT be None even without official Garmin data
    assert carga["training_status"] is not None
    # HRV data should be present
    assert carga["training_status"]["hrv"] is not None
    assert carga["training_status"]["hrv"]["value_ms"] == 52
    assert carga["training_status"]["hrv"]["label_pt"] == "Equilibrado"
    # Official data should be absent
    assert carga["training_status"]["status"] is None
    assert carga["training_status"]["vo2max"] is None
    assert carga["training_status"]["acute_load"] is None
