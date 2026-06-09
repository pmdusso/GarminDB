# test/test_power_analyzer_phase1.py
"""Phase 1 power tests: indoor/outdoor split, gate, peak, NP, W/kg inputs."""

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
