# test/test_power_analyzer_analyze.py
import json
import os
from datetime import date
from garmindb.analysis.power_analyzer import PowerAnalyzer


def _write_ride(folder, activity_id, day, **fields):
    payload = {
        "activityType": {"typeKey": "cycling"},
        "startTimeLocal": f"{day} 10:00:00",
    }
    payload.update(fields)
    with open(os.path.join(folder, f"activity_{activity_id}.json"), "w") as f:
        json.dump(payload, f)


def test_analyze_builds_result(tmp_path):
    folder = str(tmp_path)
    _write_ride(folder, 1, "2026-05-20", maxAvgPower_1200=290, maxAvgPower_3600=250,
                powerTimeInZone_1=600.0, powerTimeInZone_2=1400.0)
    _write_ride(folder, 2, "2026-06-01", maxAvgPower_1200=305, maxAvgPower_3600=240,
                powerTimeInZone_2=1000.0, powerTimeInZone_3=500.0)

    analyzer = PowerAnalyzer(folder, configured_ftp=325)
    result = analyzer.analyze(date(2026, 5, 1), date(2026, 6, 7))

    assert result.rides_with_power == 2
    assert result.best_20min_recent == 305
    assert result.estimated_ftp == round(305 * 0.95)
    assert result.configured_ftp == 325
    # configured (325) > observed best-20min (305) -> recommend a test
    assert result.ftp_needs_test is True
    # zone distribution sums to ~100
    assert abs(sum(result.power_zone_distribution.values()) - 100.0) < 0.1
    # an FTP-test insight should be present
    assert any("FTP" in i.title for i in result.insights)


def test_analyze_empty_dir(tmp_path):
    analyzer = PowerAnalyzer(str(tmp_path), configured_ftp=325)
    result = analyzer.analyze(date(2026, 5, 1), date(2026, 6, 7))
    assert result.rides_with_power == 0
    assert result.best_20min_recent is None
    assert result.ftp_needs_test is False
