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


# --------------------------------------------------------------------------- #
# Task 3 — publication gate + headline eFTP
# --------------------------------------------------------------------------- #

def _hard_outdoor(folder, aid, day, best20):
    # NP just above 0.90 * 325 = 292.5 -> IF >= 0.90 (a genuinely hard ride).
    _write(folder, aid, day, indoor=False, maxAvgPower_1200=best20,
           normPower=295.0, duration=3600.0)


def test_gate_publishes_outdoor_when_moderate_rule_met(tmp_path):
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    _hard_outdoor(folder, 1, "2026-05-20", 300)
    _hard_outdoor(folder, 2, "2026-05-27", 305)
    _hard_outdoor(folder, 3, "2026-06-02", 298)
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    assert r.gate.published is True
    assert r.gate.source_env == "outdoor"
    assert r.gate.candidate_count == 3
    assert r.eftp_measured == round(305 * 0.95)     # best candidate * 0.95
    assert r.eftp_source == "outdoor"
    assert r.eftp_date == date(2026, 5, 27)


def test_gate_fails_with_too_few_candidates(tmp_path):
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    _hard_outdoor(folder, 1, "2026-05-20", 300)
    _hard_outdoor(folder, 2, "2026-05-27", 305)      # only 2 < 3
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    assert r.gate.published is False
    assert r.eftp_measured is None
    assert "configurado" in r.gate.reason.lower()


def test_gate_fails_on_stale_efforts(tmp_path):
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    for i, day in enumerate(("2026-01-10", "2026-01-12", "2026-01-15"), 1):
        _hard_outdoor(folder, i, day, 300)           # all > 42 days old
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    assert r.gate.published is False
    assert r.gate.recency_ok is False


def test_gate_falls_back_to_indoor_label(tmp_path):
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    # 3 hard INDOOR rides, no qualifying outdoor -> indoor headline, labelled.
    for i, day in enumerate(("2026-05-20", "2026-05-27", "2026-06-02"), 1):
        _write(folder, i, day, indoor=True, maxAvgPower_1200=300,
               normPower=295.0, duration=3600.0)
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    assert r.gate.published is True
    assert r.gate.source_env == "indoor"
    assert r.eftp_source == "indoor"


# --------------------------------------------------------------------------- #
# Task 4 — NP variability (>=30min) + gate-aware insight
# --------------------------------------------------------------------------- #

def test_np_variability_uses_only_long_rides(tmp_path):
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    # Long ride: counts. avg 200, NP 220 -> ratio 1.10.
    _write(folder, 1, "2026-05-20", indoor=False, maxAvgPower_1200=290,
           avgPower=200.0, normPower=220.0, duration=3600.0)
    # Short ride: NP must be ignored (duration < 1800s).
    _write(folder, 2, "2026-05-21", indoor=False, maxAvgPower_1200=280,
           avgPower=150.0, normPower=300.0, duration=600.0)
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    assert r.np_long_ride_count == 1
    assert abs(r.np_variability_ratio - 1.10) < 0.01


def test_gate_insight_present_when_published(tmp_path):
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    for i, day in enumerate(("2026-05-20", "2026-05-27", "2026-06-02"), 1):
        _write(folder, i, day, indoor=False, maxAvgPower_1200=305,
               normPower=295.0, duration=3600.0)
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    gate_insights = [i for i in r.insights if "Potência de campo" in i.title]
    assert gate_insights                                   # gate insight present
    assert not any("FTP" in i.title for i in gate_insights)   # title stays collision-free


def test_gate_fails_on_soft_rides_if_below_threshold(tmp_path):
    # 3 recent rides in-window with 20-min data, but NP well below 0.90*325
    # (soft Z2 block) -> if_ok False -> gate does not publish.
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    for i, day in enumerate(("2026-05-20", "2026-05-27", "2026-06-02"), 1):
        _write(folder, i, day, indoor=False, maxAvgPower_1200=240,
               normPower=200.0, duration=3600.0)   # 200/325 = 0.615 < 0.90
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    assert r.gate.candidate_count == 3
    assert r.gate.recency_ok is True
    assert r.gate.if_ok is False
    assert r.gate.published is False
    assert r.eftp_measured is None


def test_np_variability_none_when_no_long_rides(tmp_path):
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    # Only a short (<1800s) ride -> no long-ride NP sample -> ratio None.
    _write(folder, 1, "2026-05-20", indoor=False, maxAvgPower_1200=280,
           avgPower=150.0, normPower=300.0, duration=600.0)
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    assert r.np_variability_ratio is None
    assert r.np_long_ride_count == 0
