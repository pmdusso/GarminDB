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


def _recovery_result(score, days_analyzed=14):
    return RecoveryAnalysisResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        recovery_score=score, recovery_trend=TrendDirection.STABLE,
        rhr_summary=MetricSummary("RHR", 55.0, "bpm"),
        body_battery_summary=MetricSummary("BB", 45.0, "%"),
        training_load_summary=MetricSummary("Load", 2000.0, "TSS"),
        rhr_baseline=50.0, rhr_deviation=5.0, weekly_tss=2000.0,
        insights=[Insight("Elevated RHR", "RHR up", InsightSeverity.WARNING, "recovery")],
        days_analyzed=days_analyzed,
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


def _build(monkeypatch, recovery_score=60, last_metrics=None, recovery_days=14):
    import garmindb.analysis.performance_report as mod
    monkeypatch.setattr(mod, "_run_power", lambda d, ftp, s, e: _power_stub(ftp))
    monkeypatch.setattr(mod, "_run_activity", lambda repo, s, e: _activity_result())
    monkeypatch.setattr(
        mod, "_run_recovery",
        lambda repo, s, e: _recovery_result(recovery_score, recovery_days))
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
    # current weight = most recent weigh-in = 85.0 (series sorted ascending);
    # wkg = 325 / 85.0
    assert round(report.current_weight_kg, 1) == 85.0
    assert round(report.wkg_current, 2) == round(325 / 85.0, 2)
    labels = [row.label for row in report.scorecard]
    assert "W/kg" in labels and "FTP" in labels and "Peso" in labels


def test_empty_weight_series_yields_no_wkg_and_dash_cell(monkeypatch):
    class _EmptyRepo(_StubRepo):
        def get_weight_series(self, s, e):
            return []

    import garmindb.analysis.performance_report as mod
    monkeypatch.setattr(mod, "_run_power", lambda d, ftp, s, e: _power_stub(ftp))
    monkeypatch.setattr(mod, "_run_activity", lambda repo, s, e: _activity_result())
    monkeypatch.setattr(mod, "_run_recovery", lambda repo, s, e: _recovery_result(60))
    monkeypatch.setattr(mod, "_run_sleep", lambda repo, s, e: _sleep_result())
    monkeypatch.setattr(mod, "_run_stress", lambda repo, s, e: _stress_result())
    monkeypatch.setattr(mod, "get_latest_vo2max", lambda d, s, e: 56.0)
    builder = PerformanceReportBuilder(
        repository=_EmptyRepo(), db_dir="/tmp/db", activities_dir="/tmp/acts",
        targets=PerformanceTargets(ftp_watts=325, weight_target_kg=80, wkg_target=4.0,
                                   race_name="L'Etape", race_date="2026-09-27"),
        last_metrics=None,
    )
    report = builder.build(date(2026, 5, 9), date(2026, 6, 7),
                           datetime(2026, 6, 8, 12, 0, 0))
    assert report.current_weight_kg is None
    assert report.wkg_current is None
    wkg_row = next(row for row in report.scorecard if row.label == "W/kg")
    assert wkg_row.current == "—"


def test_readiness_light_from_recovery_score(monkeypatch):
    assert _build(monkeypatch, recovery_score=80).readiness_light == "🟢"
    assert _build(monkeypatch, recovery_score=60).readiness_light == "🟡"
    assert _build(monkeypatch, recovery_score=40).readiness_light == "🔴"


def test_readiness_no_data_is_neutral_not_fake_yellow(monkeypatch):
    # When the recovery analyzer saw no data (days_analyzed == 0), the neutral
    # fallback score (50) must NOT be presented as a colored directive. Readiness
    # becomes ⚪ "dados insuficientes" instead of a fabricated 🟡.
    report = _build(monkeypatch, recovery_score=50, recovery_days=0)
    assert report.readiness_light == "⚪"
    assert "insuficientes" in report.readiness_label


def test_priorities_lead_with_severe_insights(monkeypatch):
    report = _build(monkeypatch)
    assert len(report.priorities) >= 1
    # the WARNING recovery insight must outrank any INFO/POSITIVE
    assert "Elevated RHR" in report.priorities[0]


def test_deltas_present_with_prior(monkeypatch):
    last = {"metrics": {"wkg": 3.7}}
    report = _build(monkeypatch, last_metrics=last)
    assert report.deltas["wkg"].has_previous is True


def _build_no_ftp(monkeypatch):
    """Build with no configured FTP so the estimated FTP fallback is used."""
    import garmindb.analysis.performance_report as mod
    monkeypatch.setattr(mod, "_run_power", lambda d, ftp, s, e: _power_stub(ftp))
    monkeypatch.setattr(mod, "_run_activity", lambda repo, s, e: _activity_result())
    monkeypatch.setattr(mod, "_run_recovery", lambda repo, s, e: _recovery_result(60))
    monkeypatch.setattr(mod, "_run_sleep", lambda repo, s, e: _sleep_result())
    monkeypatch.setattr(mod, "_run_stress", lambda repo, s, e: _stress_result())
    monkeypatch.setattr(mod, "get_latest_vo2max", lambda d, s, e: 56.0)
    builder = PerformanceReportBuilder(
        repository=_StubRepo(), db_dir="/tmp/db", activities_dir="/tmp/acts",
        targets=PerformanceTargets(ftp_watts=None, weight_target_kg=80,
                                   wkg_target=4.0, race_name="L'Etape",
                                   race_date="2026-09-27"),
        last_metrics=None,
    )
    return builder.build(date(2026, 5, 9), date(2026, 6, 7),
                         datetime(2026, 6, 8, 12, 0, 0))


def test_ftp_falls_back_to_estimated_when_unconfigured(monkeypatch):
    # No configured FTP -> the builder must fall back to the power analyzer's
    # estimated_ftp (267 W from the stub) for both ftp_used and the scorecard.
    report = _build_no_ftp(monkeypatch)
    assert report.ftp_used == 267
    ftp_row = next(row for row in report.scorecard if row.label == "FTP")
    assert ftp_row.current == "267 W"


def _insight(title, severity, category):
    return Insight(title, f"{title} detail", severity, category)


def _stub_with_insights(*insights):
    """A minimal analyzer-result stand-in carrying only an insights list."""
    class _R:
        def __init__(self, ins):
            self.insights = list(ins)
    return _R(insights)


def test_priorities_rank_by_severity_drop_positive_and_cap_three(monkeypatch):
    # One ALERT, two WARNING, one POSITIVE across the analyzers. Priorities
    # must be capped at 3, the ALERT must lead, and the POSITIVE must drop.
    import garmindb.analysis.performance_report as mod
    alert = _insight("Overtraining risk", InsightSeverity.ALERT, "recovery")
    warn1 = _insight("Elevated RHR", InsightSeverity.WARNING, "recovery")
    warn2 = _insight("Poor sleep", InsightSeverity.WARNING, "sleep")
    good = _insight("Great form", InsightSeverity.POSITIVE, "activity")

    monkeypatch.setattr(mod, "_run_power",
                        lambda d, ftp, s, e: _stub_with_insights())
    monkeypatch.setattr(mod, "_run_activity",
                        lambda repo, s, e: _stub_with_insights(good))
    monkeypatch.setattr(mod, "_run_recovery",
                        lambda repo, s, e: _stub_with_insights(alert, warn1))
    monkeypatch.setattr(mod, "_run_sleep",
                        lambda repo, s, e: _stub_with_insights(warn2))
    monkeypatch.setattr(mod, "_run_stress",
                        lambda repo, s, e: _stub_with_insights())

    priorities = mod.PerformanceReportBuilder._priorities(
        [_stub_with_insights(),
         _stub_with_insights(good),
         _stub_with_insights(alert, warn1),
         _stub_with_insights(warn2),
         _stub_with_insights()])

    assert len(priorities) == 3
    # The ALERT leads and carries its 🚨 emoji.
    assert priorities[0].startswith("🚨")
    assert "Overtraining risk" in priorities[0]
    # The two WARNINGs follow, each with the ⚠️ emoji.
    assert all("⚠️" in p for p in priorities[1:])
    # The POSITIVE insight is dropped by the cap-3.
    assert all("Great form" not in p for p in priorities)


def test_readiness_score_boundaries(monkeypatch):
    # Boundary scan with days_analyzed > 0: 49->🔴, 50->🟡, 69->🟡, 70->🟢.
    assert _build(monkeypatch, recovery_score=49).readiness_light == "🔴"
    assert _build(monkeypatch, recovery_score=50).readiness_light == "🟡"
    assert _build(monkeypatch, recovery_score=69).readiness_light == "🟡"
    assert _build(monkeypatch, recovery_score=70).readiness_light == "🟢"
