# test/test_power_analyzer_phase1.py
"""Phase 1 power tests: indoor/outdoor split, gate, peak, NP, W/kg inputs."""

import json
import os
from datetime import date

from garmindb.analysis.power_analyzer import PowerAnalyzer


# --------------------------------------------------------------------------- #
# Task 1 — classification / duration / exclude / sanity
# --------------------------------------------------------------------------- #

def test_parse_ride_classifies_indoor_by_type():
    data = {"activityType": {"typeKey": "indoor_cycling"},
            "startTimeLocal": "2026-05-20 10:00:00", "maxAvgPower_1200": 250}
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None and ride.is_indoor is True


def test_parse_ride_classifies_indoor_by_manufacturer():
    # typeKey "cycling" but a TACX trainer -> indoor (356 such rides exist).
    data = {"activityType": {"typeKey": "cycling"}, "manufacturer": "TACX",
            "startTimeLocal": "2026-05-20 10:00:00", "maxAvgPower_1200": 250}
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None and ride.is_indoor is True


def test_parse_ride_classifies_outdoor():
    data = {"activityType": {"typeKey": "road_biking"}, "manufacturer": "GARMIN",
            "startTimeLocal": "2026-05-20 10:00:00", "maxAvgPower_1200": 300,
            "duration": 5400.0}
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None
    assert ride.is_indoor is False
    assert ride.duration_s == 5400.0


def test_parse_ride_honors_exclude_flag():
    data = {"activityType": {"typeKey": "cycling"},
            "startTimeLocal": "2026-05-20 10:00:00", "maxAvgPower_1200": 250,
            "excludeFromPowerCurveReports": True}
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None and ride.exclude is True


def test_parse_ride_sanity_drops_impossible_curve():
    # best-20min (27) below ride average (72) is physically impossible -> exclude.
    data = {"activityType": {"typeKey": "cycling"},
            "startTimeLocal": "2026-05-20 10:00:00",
            "avgPower": 72.0, "maxAvgPower_1200": 27}
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None and ride.exclude is True


def _write(folder, aid, day, *, indoor=False, **fields):
    payload = {
        "activityType": {"typeKey": "indoor_cycling" if indoor else "road_biking"},
        "manufacturer": "TACX" if indoor else "GARMIN",
        "startTimeLocal": f"{day} 10:00:00",
    }
    payload.update(fields)
    with open(os.path.join(folder, f"activity_{aid}.json"), "w") as f:
        json.dump(payload, f)


# --------------------------------------------------------------------------- #
# Task 2 — separate curves + per-env eFTP + peak 5s
# --------------------------------------------------------------------------- #

def test_separate_indoor_outdoor_curves_and_peak(tmp_path):
    folder = str(tmp_path)
    _write(folder, 1, "2026-05-10", indoor=True, maxAvgPower_1200=260,
           maxAvgPower_5=700, duration=3600.0)
    _write(folder, 2, "2026-05-12", indoor=False, maxAvgPower_1200=300,
           maxAvgPower_5=820, duration=5400.0)
    analyzer = PowerAnalyzer(folder, configured_ftp=325)
    r = analyzer.analyze(date(2026, 1, 1), date(2026, 6, 7))
    assert r.curve_indoor[1200] == 260
    assert r.curve_outdoor[1200] == 300
    assert r.eftp_indoor == round(260 * 0.95)
    assert r.eftp_outdoor == round(300 * 0.95)
    assert r.peak_5s == 820            # best 5-s across all (outdoor here)


def test_excluded_ride_is_dropped_from_curves(tmp_path):
    folder = str(tmp_path)
    _write(folder, 1, "2026-05-12", indoor=False, maxAvgPower_1200=300,
           duration=5400.0)
    _write(folder, 2, "2026-05-13", indoor=False, maxAvgPower_1200=999,
           excludeFromPowerCurveReports=True, duration=5400.0)
    analyzer = PowerAnalyzer(folder, configured_ftp=325)
    r = analyzer.analyze(date(2026, 1, 1), date(2026, 6, 7))
    assert r.curve_outdoor[1200] == 300     # the 999 W excluded ride is ignored
