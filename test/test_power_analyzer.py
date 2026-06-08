# test/test_power_analyzer.py
from datetime import date
from garmindb.analysis.power_analyzer import PowerAnalyzer, PowerRide


def test_parse_ride_extracts_power_fields():
    data = {
        "activityType": {"typeKey": "cycling"},
        "startTimeLocal": "2026-05-20 10:00:00",
        "avgPower": 200.0,
        "normPower": 230.0,
        "maxAvgPower_5": 600,
        "maxAvgPower_60": 400,
        "maxAvgPower_300": 320,
        "maxAvgPower_1200": 290,
        "maxAvgPower_3600": 250,
        "powerTimeInZone_1": 600.0,
        "powerTimeInZone_2": 1200.0,
    }
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None
    assert ride.date == date(2026, 5, 20)
    assert ride.sport == "cycling"
    assert ride.norm_power == 230.0
    assert ride.peak_power[1200] == 290
    assert ride.power_time_in_zone[1] == 600.0


def test_parse_ride_skips_non_cycling():
    data = {"activityType": {"typeKey": "running"}, "startTimeLocal": "2026-05-20 10:00:00"}
    assert PowerAnalyzer._parse_ride(data) is None


def test_parse_ride_skips_cycling_without_power():
    data = {"activityType": {"typeKey": "cycling"}, "startTimeLocal": "2026-05-20 10:00:00"}
    assert PowerAnalyzer._parse_ride(data) is None


def test_parse_ride_handles_list_payload():
    data = [{
        "activityType": {"typeKey": "virtual_ride"},
        "startTimeLocal": "2026-05-20 10:00:00",
        "maxAvgPower_1200": 280,
    }]
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None and ride.peak_power[1200] == 280


def test_best_curve_takes_max_per_duration():
    rides = [
        PowerRide(date(2026, 5, 1), "cycling", None, None, {1200: 280, 3600: 240}, {}),
        PowerRide(date(2026, 5, 2), "cycling", None, None, {1200: 305, 3600: 230}, {}),
    ]
    analyzer = PowerAnalyzer("/tmp/does-not-matter")
    curve = analyzer._best_curve(rides)
    assert curve[1200] == 305
    assert curve[3600] == 240
