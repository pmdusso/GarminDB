# test/test_performance_power_phase1.py
"""Phase 1: measured power flows into the --performance report + renderer."""

from datetime import date

from garmindb.analysis.power_analyzer import PowerAnalysisResult, PowerGate
from garmindb.presentation.markdown.performance_renderer import (
    PerformancePresenter,
)


def _power_with_eftp():
    # published is a derived @property: candidate_count>=3 + recency_ok + if_ok.
    gate = PowerGate(source_env="outdoor", candidate_count=3,
                     recency_ok=True, if_ok=True,
                     newest_effort_date=date(2026, 5, 27),
                     reason="eFTP medido outdoor")
    return PowerAnalysisResult(
        period_start=date(2026, 1, 1), period_end=date(2026, 6, 7),
        configured_ftp=325, estimated_ftp=289, best_20min_recent=305,
        best_20min_alltime=305, power_curve_recent={1200: 305},
        power_curve_alltime={5: 820, 1200: 305}, power_zone_distribution={2: 60.0, 4: 40.0},
        recent_ride_count=3, total_rides=3, ftp_needs_test=False,
        curve_outdoor={5: 820, 1200: 305}, curve_indoor={1200: 260},
        eftp_outdoor=290, eftp_indoor=247, peak_5s=820,
        gate=gate, eftp_measured=290, eftp_source="outdoor",
        eftp_date=date(2026, 5, 27),
    )


def test_renderer_shows_both_ftps_gap_wkg_and_zones():
    md = PerformancePresenter.render_power_block(_power_with_eftp(), wkg_measured=3.72)
    assert "FTP configurado" in md and "325" in md
    assert "eFTP medido" in md and "290" in md
    assert "3,72" in md                      # measured W/kg (paired weight)
    assert "820" in md                       # 5s neuromuscular peak
    assert "outdoor" in md
    assert "Zonas de potência" in md         # zone distribution surfaced (was dropped)
    assert "Gap vs configurado: -35 W" in md  # 290 - 325 = -35


def _power_gate_declined():
    # candidate_count < 3 -> published property is False (gate declines).
    gate = PowerGate(source_env=None, candidate_count=1, recency_ok=True,
                     if_ok=False, newest_effort_date=date(2026, 5, 27),
                     reason="FTP configurado (não testado nestes dados: "
                            "1<3 pedais com 20-min; sem esforço duro (IF<0,90))")
    return PowerAnalysisResult(
        period_start=date(2026, 1, 1), period_end=date(2026, 6, 7),
        configured_ftp=325, estimated_ftp=None, best_20min_recent=None,
        best_20min_alltime=None, power_curve_recent={},
        power_curve_alltime={1200: 290}, power_zone_distribution={},
        recent_ride_count=2, total_rides=5, ftp_needs_test=False,
        curve_outdoor={1200: 290}, curve_indoor={},
        gate=gate, eftp_measured=None, eftp_source=None, eftp_date=None,
    )


def test_render_power_block_gate_declined_is_honest():
    # The data-honesty headline path: no published eFTP -> show the configured
    # FTP labelled as such + the gate reason, and NEVER a measured number/W·kg.
    md = PerformancePresenter.render_power_block(_power_gate_declined(),
                                                 wkg_measured=None)
    assert "FTP configurado" in md and "325" in md
    assert "não publicado" in md                 # decline branch rendered
    assert "1<3 pedais" in md                     # the gate reason is surfaced
    assert "W·kg medido" not in md                # no fabricated measured W/kg
    assert "eFTP medido: 2" not in md             # no bare measured eFTP number


def test_gate_published_is_derived_not_stored():
    # published reflects the gate conditions; flipping if_ok flips published.
    pub = PowerGate(source_env="outdoor", candidate_count=3, recency_ok=True,
                    if_ok=True, newest_effort_date=date(2026, 5, 27), reason="x")
    assert pub.published is True
    declined = PowerGate(source_env=None, candidate_count=3, recency_ok=True,
                         if_ok=False, newest_effort_date=None, reason="x")
    assert declined.published is False


def test_dc_label_boundaries():
    # Pin the strong/moderate/high thresholds at exactly 5.0% and 10.0% so an
    # off-by-one (< vs <=) can't silently misclassify a clinical category.
    f = PerformancePresenter._dc_label
    assert f(4.99) == "🟢 forte"
    assert f(5.0) == "🟡 moderado"
    assert f(7.5) == "🟡 moderado"
    assert f(10.0) == "🟡 moderado"
    assert f(10.01) == "🔴 alto"


def test_weight_near_medians_within_window():
    from garmindb.analysis.performance_report import _weight_near

    class _Repo:
        def get_weight_series(self, start, end):
            return [(date(2026, 5, 20), 79.0), (date(2026, 5, 27), 77.0)]

    assert _weight_near(_Repo(), date(2026, 5, 24)) == 78.0    # median(77, 79)
    assert _weight_near(_Repo(), None) is None
    assert _weight_near(object(), date(2026, 5, 24)) is None    # no get_weight_series
