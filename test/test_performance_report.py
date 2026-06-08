# test/test_performance_report.py
from datetime import date, datetime
from garmindb.analysis.performance_report import PerformanceReportBuilder
from garmindb.analysis.performance_targets import PerformanceTargets
from garmindb.analysis.models import (
    ActivityAnalysisResult, TrainingStressMetrics, RecoveryAnalysisResult,
    SleepAnalysisResult, StressAnalysisResult, MetricSummary, Insight,
    InsightSeverity, TrendDirection,
)


class _StubRepo:
    def get_weight_series(self, s, e):
        return [(date(2026, 5, 3), 84.0), (date(2026, 5, 27), 85.0)]


def _activity_result():
    r = ActivityAnalysisResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        total_activities=20, total_duration_hours=24.8,
        total_distance_km=509.0, total_calories=15000,
        training_stress=TrainingStressMetrics(
            atl=62.0, ctl=76.0, tsb=13.0, monotony=0.6, strain=247.0,
            confidence_score=0.9),
    )
    return r


def _recovery_result(score):
    return RecoveryAnalysisResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        recovery_score=score, recovery_trend=TrendDirection.STABLE,
        rhr_summary=MetricSummary("RHR", 55.0, "bpm"),
        body_battery_summary=MetricSummary("BB", 45.0, "%"),
        training_load_summary=MetricSummary("Load", 2000.0, "TSS"),
        rhr_baseline=50.0, rhr_deviation=5.0, weekly_tss=2000.0,
        insights=[Insight("Elevated RHR", "RHR up", InsightSeverity.WARNING, "recovery")],
    )


def _sleep_result():
    return SleepAnalysisResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        avg_total_sleep=MetricSummary("Sleep", 7.1, "hours"),
        avg_deep_sleep=MetricSummary("Deep", 16.0, "%"),
        avg_rem_sleep=MetricSummary("REM", 17.0, "%"),
        sleep_consistency_score=50.0,
    )


def _stress_result():
    return StressAnalysisResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        avg_stress=MetricSummary("Stress", 32.0, ""),
        low_stress_percent=47.0, medium_stress_percent=34.0, high_stress_percent=19.0,
    )


def _build(monkeypatch, recovery_score=60, last_metrics=None):
    import garmindb.analysis.performance_report as mod
    monkeypatch.setattr(mod, "_run_power", lambda d, ftp, s, e: _power_stub(ftp))
    monkeypatch.setattr(mod, "_run_activity", lambda repo, s, e: _activity_result())
    monkeypatch.setattr(mod, "_run_recovery", lambda repo, s, e: _recovery_result(recovery_score))
    monkeypatch.setattr(mod, "_run_sleep", lambda repo, s, e: _sleep_result())
    monkeypatch.setattr(mod, "_run_stress", lambda repo, s, e: _stress_result())
    monkeypatch.setattr(mod, "get_latest_vo2max", lambda d, s, e: 56.0)
    builder = PerformanceReportBuilder(
        repository=_StubRepo(), db_dir="/tmp/db", activities_dir="/tmp/acts",
        targets=PerformanceTargets(ftp_watts=325, weight_target_kg=80, wkg_target=4.0,
                                   race_name="L'Etape", race_date="2026-09-27"),
        last_metrics=last_metrics,
    )
    return builder.build(date(2026, 5, 9), date(2026, 6, 7),
                         datetime(2026, 6, 8, 12, 0, 0))


def _power_stub(ftp):
    from garmindb.analysis.power_analyzer import PowerAnalysisResult
    return PowerAnalysisResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        configured_ftp=ftp, estimated_ftp=267, best_20min_recent=281,
        best_20min_alltime=319, power_curve_recent={1200: 281},
        power_curve_alltime={1200: 319}, power_zone_distribution={2: 100.0},
        rides_with_power=12, total_rides=12, ftp_needs_test=True, insights=[],
    )


def test_builds_wkg_and_scorecard(monkeypatch):
    report = _build(monkeypatch)
    # current weight = mean(84, 85) = 84.5; wkg = 325 / 84.5
    assert round(report.current_weight_kg, 1) == 84.5
    assert round(report.wkg_current, 2) == round(325 / 84.5, 2)
    labels = [row.label for row in report.scorecard]
    assert "W/kg" in labels and "FTP" in labels and "Peso" in labels


def test_readiness_light_from_recovery_score(monkeypatch):
    assert _build(monkeypatch, recovery_score=80).readiness_light == "🟢"
    assert _build(monkeypatch, recovery_score=60).readiness_light == "🟡"
    assert _build(monkeypatch, recovery_score=40).readiness_light == "🔴"


def test_priorities_lead_with_severe_insights(monkeypatch):
    report = _build(monkeypatch)
    assert len(report.priorities) >= 1
    # the WARNING recovery insight must outrank any INFO/POSITIVE
    assert "Elevated RHR" in report.priorities[0]


def test_deltas_present_with_prior(monkeypatch):
    last = {"metrics": {"wkg": 3.7}}
    report = _build(monkeypatch, last_metrics=last)
    assert report.deltas["wkg"].has_previous is True
