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

    assert result.recent_ride_count == 2
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
    assert result.recent_ride_count == 0
    assert result.best_20min_recent is None
    assert result.ftp_needs_test is False
    assert result.skipped_files == 0


def test_analyze_skips_corrupt_files_and_counts_them(tmp_path):
    folder = str(tmp_path)
    # A valid cycling ride with power.
    _write_ride(folder, 1, "2026-05-20", maxAvgPower_1200=290,
                powerTimeInZone_2=1400.0)
    # A cycling ride WITHOUT power data (parsed but not counted).
    _write_ride(folder, 2, "2026-05-21")
    # A running activity (not cycling, not counted, not skipped).
    with open(os.path.join(folder, "activity_3.json"), "w") as f:
        json.dump({"activityType": {"typeKey": "running"},
                   "startTimeLocal": "2026-05-22 10:00:00"}, f)
    # A malformed JSON file -> must be skipped and counted, not crash.
    with open(os.path.join(folder, "activity_4.json"), "w") as f:
        f.write("{not json")

    analyzer = PowerAnalyzer(folder, configured_ftp=325)
    result = analyzer.analyze(date(2026, 5, 1), date(2026, 6, 7))

    # Only the one valid cycling-with-power ride is counted.
    assert result.total_rides == 1
    assert result.recent_ride_count == 1
    # Exactly one unreadable file was skipped.
    assert result.skipped_files == 1


def test_ftp_needs_test_false_when_configured_below_best_20min(tmp_path):
    # Configured FTP (250) is BELOW the observed best-20min (300): the number
    # is conservative, no test is recommended and no FTP insight is emitted.
    folder = str(tmp_path)
    _write_ride(folder, 1, "2026-05-20", maxAvgPower_1200=300,
                powerTimeInZone_2=1400.0)

    analyzer = PowerAnalyzer(folder, configured_ftp=250)
    result = analyzer.analyze(date(2026, 5, 1), date(2026, 6, 7))

    assert result.best_20min_recent == 300
    assert result.ftp_needs_test is False
    assert not any("FTP" in i.title for i in result.insights)


def test_ftp_needs_test_false_when_no_20min_data(tmp_path):
    # A high configured FTP (400) but NO 20-min effort on disk: best_20min_recent
    # is None. ftp_needs_test must be False and analyze() must not raise on the
    # None-best path.
    folder = str(tmp_path)
    # A cycling ride with power, but only a 1-hour effort (no maxAvgPower_1200).
    _write_ride(folder, 1, "2026-05-20", maxAvgPower_3600=240,
                powerTimeInZone_2=1400.0)

    analyzer = PowerAnalyzer(folder, configured_ftp=400)
    result = analyzer.analyze(date(2026, 5, 1), date(2026, 6, 7))

    assert result.best_20min_recent is None
    assert result.estimated_ftp is None
    assert result.ftp_needs_test is False
    assert not any("FTP" in i.title for i in result.insights)
