# test/test_performance_renderer.py
from datetime import date, datetime
from garmindb.presentation.markdown.performance_renderer import PerformancePresenter
from garmindb.analysis.performance_report import PerformanceReport, ScorecardRow
from garmindb.analysis.performance_targets import PerformanceTargets
from garmindb.analysis.power_analyzer import PowerAnalysisResult
from garmindb.analysis.report_state import MetricDelta
from garmindb.analysis.decoupling_analyzer import (
    DecouplingResult, RideDecoupling, PaHrResult, PaHrRide)


def _power(recent_ride_count, total_rides, skipped_files=0):
    return PowerAnalysisResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        configured_ftp=325, estimated_ftp=290, best_20min_recent=305,
        best_20min_alltime=305, power_curve_recent={}, power_curve_alltime={},
        power_zone_distribution={}, recent_ride_count=recent_ride_count,
        total_rides=total_rides, ftp_needs_test=False,
        skipped_files=skipped_files,
    )


def _report():
    return PerformanceReport(
        generated_at=datetime(2026, 6, 8, 12, 0, 0),
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        targets=PerformanceTargets(ftp_watts=325, weight_target_kg=80, wkg_target=4.0,
                                   race_name="L'Etape Campos do Jordao", race_date="2026-09-27"),
        scorecard=[
            ScorecardRow("W/kg", "3,81", "4,0", "-0,19",
                         MetricDelta(3.81, 3.71)),
            ScorecardRow("Peso", "84,5 kg", "80 kg", "4,5", MetricDelta(84.5, 85.3)),
        ],
        readiness_light="🟡", readiness_label="recuperação parcial",
        priorities=["⚠️ Elevated RHR: RHR up", "ℹ️ Confirme FTP: teste"],
        power=None, activity=None, recovery=None, sleep=None, stress=None,
        current_weight_kg=84.5, wkg_current=3.81, ftp_used=325, vo2max=56,
        deltas={}, metric_snapshot={},
    )


def test_render_contains_header_and_goal():
    md = PerformancePresenter().render(_report())
    assert "# " in md
    assert "L'Etape Campos do Jordao" in md
    assert "PRONTIDÃO" in md.upper() or "Prontidão" in md


def test_render_scorecard_table_and_priorities():
    md = PerformancePresenter().render(_report())
    assert "W/kg" in md and "3,81" in md and "4,0" in md
    assert "| Métrica" in md  # scorecard table header
    assert "Elevated RHR" in md


def test_render_delta_arrows():
    md = PerformancePresenter().render(_report())
    # W/kg improved (+0.10 toward target) -> up arrow; Peso decreased -> down
    assert "↑" in md and "↓" in md


def test_no_metadata_flag_skips_frontmatter():
    md = PerformancePresenter(include_metadata=False).render(_report())
    assert not md.startswith("---")


def _report_with_rows(rows):
    return PerformanceReport(
        generated_at=datetime(2026, 6, 8, 12, 0, 0),
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        targets=PerformanceTargets(ftp_watts=325, weight_target_kg=80, wkg_target=4.0,
                                   race_name="L'Etape", race_date="2026-09-27"),
        scorecard=rows,
        readiness_light="🟡", readiness_label="recuperação parcial",
        priorities=[],
        power=None, activity=None, recovery=None, sleep=None, stress=None,
        current_weight_kg=None, wkg_current=None, ftp_used=325, vo2max=56,
        deltas={}, metric_snapshot={},
    )


def test_delta_cell_no_previous_reads_baseline():
    # current present, no previous -> first run baseline.
    rows = [ScorecardRow("W/kg", "3,81", "4,0", "-0,19", MetricDelta(3.81, None))]
    md = PerformancePresenter(include_metadata=False).render(_report_with_rows(rows))
    assert "baseline" in md
    assert "sem dado" not in md


def test_delta_cell_absent_current_reads_sem_dado():
    # current is "—" (no data this run) -> must read "sem dado", not "baseline".
    rows = [ScorecardRow("VO2max", "—", "—", "—", None)]
    md = PerformancePresenter(include_metadata=False).render(_report_with_rows(rows))
    assert "sem dado" in md
    assert "baseline" not in md


def test_delta_cell_absent_current_with_stale_previous_reads_sem_dado():
    # Even if a previous baseline exists, an absent current means no data now.
    rows = [ScorecardRow("VO2max", "—", "—", "—", MetricDelta(56.0, 56.0))]
    md = PerformancePresenter(include_metadata=False).render(_report_with_rows(rows))
    assert "sem dado" in md


def _report_with_power(power):
    r = _report()
    r.power = power
    return r


def test_render_coverage_line():
    # A report on a partial sample must disclose its coverage.
    md = PerformancePresenter().render(_report_with_power(_power(2, 40)))
    assert "Cobertura" in md
    # New wording: total all-time rides vs recent 90-day count, no misleading fraction.
    assert "40 pedais com potência no histórico" in md
    assert "2 nos últimos 90 dias" in md


def test_render_coverage_includes_skipped_files():
    md = PerformancePresenter().render(_report_with_power(_power(2, 40, skipped_files=3)))
    assert "Cobertura" in md
    assert "3 arquivos ilegíveis ignorados" in md


def test_render_coverage_no_skipped_files_omits_phrase():
    md = PerformancePresenter().render(_report_with_power(_power(2, 40, skipped_files=0)))
    assert "ilegíveis" not in md


def test_render_zero_power_warning():
    # Rides exist but none has power -> warn the meter likely was not recording.
    md = PerformancePresenter().render(_report_with_power(_power(0, 40)))
    assert "Cobertura" in md
    # New wording: 40 all-time, 0 in the last 90 days.
    assert "40 pedais com potência no histórico" in md
    assert "0 nos últimos 90 dias" in md
    # An explicit warning about the power meter not recording.
    assert "medidor de potência" in md.lower() or "power meter" in md.lower()


def test_render_no_coverage_when_power_missing():
    # If the report carries no power block, no coverage line is emitted.
    r = _report()
    r.power = None
    md = PerformancePresenter().render(r)
    assert "Cobertura" not in md


def test_render_ftp_scorecard_cell_from_estimate():
    # When FTP came from the estimate, the builder formats it as "267 W"; the
    # renderer must surface that cell verbatim in the scorecard table.
    rows = [ScorecardRow("FTP", "267 W", "—", "—", None)]
    md = PerformancePresenter(include_metadata=False).render(_report_with_rows(rows))
    assert "| FTP | 267 W |" in md


def test_render_priority_severity_emoji_prefixes():
    # Priorities arrive pre-formatted with a severity emoji prefix; the renderer
    # must preserve the 🚨 (ALERT) and ⚠️ (WARNING) markers in order.
    r = _report()
    r.priorities = [
        "🚨 Overtraining risk: back off",
        "⚠️ Elevated RHR: RHR up",
        "⚠️ Poor sleep: short nights",
    ]
    md = PerformancePresenter(include_metadata=False).render(r)
    assert "## Prioridades agora" in md
    assert "1. 🚨 Overtraining risk" in md
    assert "2. ⚠️ Elevated RHR" in md
    assert "3. ⚠️ Poor sleep" in md


def _ride(dc_pct, day=date(2026, 5, 20)):
    return RideDecoupling(
        activity_id="1", date=day, moving_time_s=5400, distance_km=45.0,
        ef_first=0.214, ef_second=0.198, decoupling_pct=dc_pct, ef_overall=0.206,
        speed_cv=0.12, sample_count=4200, steady=True)


def test_render_decoupling_section_present():
    r = _report()
    r.decoupling = DecouplingResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        rides=[_ride(12.5)], eligible_count=1, analyzed_count=1)
    md = PerformancePresenter(include_metadata=False).render(r)
    assert "Durabilidade aeróbica" in md
    assert "12.5%" in md and "🔴 alto" in md
    assert "indoor é" in md  # honesty caveat present


def test_render_decoupling_absent_emits_nothing():
    md = PerformancePresenter(include_metadata=False).render(_report())
    assert "Durabilidade aeróbica" not in md


def test_render_decoupling_unsteady_note():
    r = _report()
    r.decoupling = DecouplingResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        rides=[_ride(4.2)], eligible_count=3, analyzed_count=1, skipped_unsteady=2)
    md = PerformancePresenter(include_metadata=False).render(r)
    assert "🟢 forte" in md
    assert "variabilidade alta" in md


def _pahr_ride(dc_pct, indoor=False, day=date(2026, 5, 20)):
    return PaHrRide(
        activity_id="1", date=day, moving_time_s=5400, indoor=indoor,
        ef_first=1.43, ef_second=1.25, decoupling_pct=dc_pct, ef_overall=1.34,
        avg_power=210.0, sample_count=4200,
        steady=(None if indoor else True))


def test_render_pahr_section_present_with_indoor_label():
    r = _report()
    r.pahr = PaHrResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        rides=[_pahr_ride(12.5, indoor=True)], eligible_count=1, analyzed_count=1)
    md = PerformancePresenter(include_metadata=False).render(r)
    assert "potência:FC" in md
    assert "indoor" in md and "210 W" in md
    assert "12.5%" in md and "🔴 alto" in md


def test_render_pahr_absent_emits_nothing():
    md = PerformancePresenter(include_metadata=False).render(_report())
    assert "potência:FC" not in md
