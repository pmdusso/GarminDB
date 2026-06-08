# test/test_performance_renderer.py
from datetime import date, datetime
from garmindb.presentation.markdown.performance_renderer import PerformancePresenter
from garmindb.analysis.performance_report import PerformanceReport, ScorecardRow
from garmindb.analysis.performance_targets import PerformanceTargets
from garmindb.analysis.report_state import MetricDelta


def _report():
    return PerformanceReport(
        generated_at=datetime(2026, 6, 8, 12, 0, 0),
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        targets=PerformanceTargets(ftp_watts=325, weight_target_kg=80, wkg_target=4.0,
                                   race_name="L'Etape Campos do Jordao", race_date="2026-09-27"),
        scorecard=[
            ScorecardRow("W/kg", "3,81", "4,0", "-0,19",
                         MetricDelta(3.81, 3.71, 0.10)),
            ScorecardRow("Peso", "84,5 kg", "80 kg", "4,5", MetricDelta(84.5, 85.3, -0.8)),
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
