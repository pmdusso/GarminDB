import sqlite3

from garmindb.analysis.treinos_report import build_carga_recuperacao_report, render_carga_recuperacao_markdown


def test_carga_recuperacao_report_combines_load_sleep_hrv_and_readiness(tmp_path):
    acts = sqlite3.connect(tmp_path / "garmin_activities.db")
    acts.executescript("""
        CREATE TABLE daily_training_load (
            day TEXT, sport TEXT, activities_count INTEGER, duration_hours REAL,
            distance_km REAL, load REAL, estimated_load_count INTEGER,
            aerobic_te_avg REAL, anaerobic_te_avg REAL
        );
    """)
    acts.execute("INSERT INTO daily_training_load VALUES (?,?,?,?,?,?,?,?,?)", ("2026-07-01", "cycling", 1, 1.0, 25.0, 100.0, 0, 3.0, 1.0))
    acts.execute("INSERT INTO daily_training_load VALUES (?,?,?,?,?,?,?,?,?)", ("2026-07-02", "running", 1, 0.5, 6.0, 80.0, 0, 2.5, 0.5))
    acts.commit()
    acts.close()

    garmin = sqlite3.connect(tmp_path / "garmin.db")
    garmin.executescript("""
        CREATE TABLE sleep (day TEXT, total_sleep TEXT, score REAL);
        CREATE TABLE training_readiness (
            day TEXT, timestamp TEXT, score REAL, level TEXT,
            feedback_short TEXT, recovery_time REAL
        );
    """)
    garmin.execute("INSERT INTO sleep VALUES (?,?,?)", ("2026-07-01", "07:30:00", 82))
    garmin.execute("INSERT INTO sleep VALUES (?,?,?)", ("2026-07-02", "05:20:00", 61))
    garmin.execute("INSERT INTO training_readiness VALUES (?,?,?,?,?,?)", ("2026-07-02", "2026-07-02 07:00:00", 42, "LOW", "LOW_SLEEP", 24))
    garmin.commit()
    garmin.close()

    mon = sqlite3.connect(tmp_path / "garmin_monitoring.db")
    mon.executescript("""
        CREATE TABLE monitoring_hrv_status (
            timestamp TEXT, weekly_average REAL, last_night_average REAL,
            baseline_low REAL, baseline_high REAL, status INTEGER
        );
    """)
    mon.execute("INSERT INTO monitoring_hrv_status VALUES (?,?,?,?,?,?)", ("2026-07-01 00:00:00", 50, 51, 45, 65, 4))
    mon.execute("INSERT INTO monitoring_hrv_status VALUES (?,?,?,?,?,?)", ("2026-07-02 00:00:00", 47, 43, 45, 65, 3))
    mon.commit()
    mon.close()

    report = build_carga_recuperacao_report(tmp_path, period_start="2026-07-01", period_end="2026-07-07")
    markdown = render_carga_recuperacao_markdown(report)

    assert report["period_start"] == "2026-07-01"
    assert report["weeks"][0]["load"] == 180.0
    assert report["weeks"][0]["sleep_avg_h"] == 6.42
    assert report["weeks"][0]["hrv_avg_ms"] == 47.0
    assert report["weeks"][0]["readiness_avg"] == 42.0
    assert report["weeks"][0]["risk"] == "warning"
    assert "Carga x Recuperação" in markdown
    assert "2026-06-29" in markdown
