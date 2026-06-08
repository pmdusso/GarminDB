"""Performance report model + builder.

Aggregates power (JSON), training load / recovery / sleep / stress
(existing analyzers via the repository), weight and VO2max, applies
targets, and computes a scorecard, readiness light, deltas and priorities.
"""

import logging
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional

from .models import (
    ActivityAnalysisResult, RecoveryAnalysisResult, SleepAnalysisResult,
    StressAnalysisResult, Insight, InsightSeverity,
)
from .power_analyzer import PowerAnalysisResult, PowerAnalyzer
from .performance_targets import PerformanceTargets
from .report_state import MetricDelta, compute_deltas
from .db_metrics import get_latest_vo2max

logger = logging.getLogger(__name__)

# Canonical scorecard metric keys. Hoisted to module level so the snapshot and
# the scorecard share a single source of truth — a rename here updates both and
# can never silently drop a Δ column.
METRIC_WKG = "wkg"
METRIC_FTP = "ftp"
METRIC_WEIGHT = "weight"
METRIC_VO2MAX = "vo2max"
METRIC_CTL = "ctl"
METRIC_TSB = "tsb"

# Severity ranking for prioritisation (lower = more urgent).
_SEVERITY_RANK = {
    InsightSeverity.ALERT: 0,
    InsightSeverity.WARNING: 1,
    InsightSeverity.INFO: 2,
    InsightSeverity.POSITIVE: 3,
}


# Thin indirections so tests can monkeypatch each analyzer independently.
def _run_power(activities_dir, ftp, start, end) -> PowerAnalysisResult:
    return PowerAnalyzer(activities_dir, ftp).analyze(start, end)


def _run_activity(repository, start, end) -> ActivityAnalysisResult:
    from .activity_analyzer import ActivityAnalyzer
    return ActivityAnalyzer(repository).analyze(start, end)


def _run_recovery(repository, start, end) -> RecoveryAnalysisResult:
    from .recovery_analyzer import RecoveryAnalyzer
    return RecoveryAnalyzer(repository).analyze(start, end)


def _run_sleep(repository, start, end) -> SleepAnalysisResult:
    from .sleep_analyzer import SleepAnalyzer
    return SleepAnalyzer(repository).analyze(start, end)


def _run_stress(repository, start, end) -> StressAnalysisResult:
    from .stress_analyzer import StressAnalyzer
    return StressAnalyzer(repository).analyze(start, end)


@dataclass
class ScorecardRow:
    """One row of the executive scorecard."""

    label: str
    current: str           # formatted, e.g. "3,81"
    target: str            # formatted or "—"
    gap: str               # formatted or "—"
    delta: Optional[MetricDelta] = None


@dataclass
class PerformanceReport:
    """Complete performance report payload for rendering."""

    generated_at: datetime
    period_start: date
    period_end: date
    targets: PerformanceTargets

    scorecard: List[ScorecardRow]
    readiness_light: str
    readiness_label: str
    priorities: List[str]

    power: PowerAnalysisResult
    activity: ActivityAnalysisResult
    recovery: RecoveryAnalysisResult
    sleep: SleepAnalysisResult
    stress: StressAnalysisResult

    current_weight_kg: Optional[float]
    wkg_current: Optional[float]
    ftp_used: Optional[float]
    vo2max: Optional[float]

    deltas: Dict[str, MetricDelta]
    metric_snapshot: Dict[str, float] = field(default_factory=dict)


class PerformanceReportBuilder:
    """Builds a PerformanceReport from data sources + targets."""

    def __init__(self, repository, db_dir, activities_dir, targets, last_metrics=None):
        self._repo = repository
        self._db_dir = db_dir
        self._acts_dir = activities_dir
        self._targets = targets
        self._last = last_metrics

    def build(self, start_date, end_date, generated_at) -> PerformanceReport:
        t = self._targets
        power = _run_power(self._acts_dir, t.ftp_watts, start_date, end_date)
        activity = _run_activity(self._repo, start_date, end_date)
        recovery = _run_recovery(self._repo, start_date, end_date)
        sleep = _run_sleep(self._repo, start_date, end_date)
        stress = _run_stress(self._repo, start_date, end_date)

        weight = self._current_weight(start_date, end_date)
        vo2max = get_latest_vo2max(self._db_dir, start_date, end_date)

        ftp_used = t.ftp_watts or power.estimated_ftp
        wkg = (ftp_used / weight) if (ftp_used and weight) else None

        ctl = activity.training_stress.ctl if activity.training_stress else None
        tsb = activity.training_stress.tsb if activity.training_stress else None

        snapshot = self._snapshot(wkg, ftp_used, weight, vo2max, ctl, tsb)
        deltas = compute_deltas(snapshot, self._last)

        scorecard = self._scorecard(wkg, ftp_used, weight, vo2max, ctl, tsb, deltas)
        light, label = self._readiness(recovery)
        priorities = self._priorities([power, activity, recovery, sleep, stress])

        return PerformanceReport(
            generated_at=generated_at, period_start=start_date, period_end=end_date,
            targets=t, scorecard=scorecard, readiness_light=light,
            readiness_label=label, priorities=priorities, power=power,
            activity=activity, recovery=recovery, sleep=sleep, stress=stress,
            current_weight_kg=weight, wkg_current=wkg, ftp_used=ftp_used,
            vo2max=vo2max, deltas=deltas, metric_snapshot=snapshot,
        )

    def _current_weight(self, start_date, end_date) -> Optional[float]:
        series = self._repo.get_weight_series(start_date, end_date)
        if not series:
            logger.debug("No weigh-ins in %s..%s; current weight is None",
                         start_date, end_date)
            return None
        # The series is sorted ascending, so the last entry is the most recent
        # weigh-in. "Agora" must reflect the latest value, not the window mean.
        return series[-1][1]

    @staticmethod
    def _snapshot(wkg, ftp, weight, vo2max, ctl, tsb) -> Dict[str, float]:
        raw = {METRIC_WKG: wkg, METRIC_FTP: ftp, METRIC_WEIGHT: weight,
               METRIC_VO2MAX: vo2max, METRIC_CTL: ctl, METRIC_TSB: tsb}
        return {k: float(v) for k, v in raw.items() if v is not None}

    def _scorecard(self, wkg, ftp, weight, vo2max, ctl, tsb, deltas) -> List[ScorecardRow]:
        t = self._targets

        def fmt(v, nd=1):
            return f"{v:.{nd}f}".replace(".", ",") if v is not None else "—"

        def gap(cur, tgt):
            if cur is None or tgt is None:
                return "—"
            return fmt(cur - tgt, 1 if abs(cur - tgt) >= 1 else 2)

        rows = [
            ScorecardRow("W/kg", fmt(wkg, 2), fmt(t.wkg_target, 1),
                         gap(wkg, t.wkg_target), deltas.get(METRIC_WKG)),
            ScorecardRow("FTP", fmt(ftp, 0) + " W", "—", "—", deltas.get(METRIC_FTP)),
            ScorecardRow("Peso", fmt(weight, 1) + " kg", fmt(t.weight_target_kg, 0) + " kg",
                         gap(weight, t.weight_target_kg), deltas.get(METRIC_WEIGHT)),
            ScorecardRow("VO2max", fmt(vo2max, 0), "—", "—", deltas.get(METRIC_VO2MAX)),
            ScorecardRow("Fitness (CTL)", fmt(ctl, 0), "—", "—", deltas.get(METRIC_CTL)),
            ScorecardRow("Forma (TSB)", fmt(tsb, 0), "—", "—", deltas.get(METRIC_TSB)),
        ]
        return rows

    @staticmethod
    def _readiness(recovery: RecoveryAnalysisResult):
        # When the recovery analyzer saw no data, recovery_score is a neutral
        # fallback (e.g. 50) — surfacing it as a colored directive fabricates a
        # recommendation. Emit a neutral ⚪ light instead.
        if getattr(recovery, "days_analyzed", 0) <= 0:
            logger.info("Recovery has no data (days_analyzed=0); readiness is neutral")
            return "⚪", "dados insuficientes para avaliar prontidão"
        score = recovery.recovery_score
        if score >= 70:
            return "🟢", "pronto para construir"
        if score >= 50:
            return "🟡", "recuperação parcial — module a carga"
        return "🔴", "recuperação baixa — priorize descanso"

    @staticmethod
    def _priorities(results) -> List[str]:
        insights: List[Insight] = []
        for r in results:
            insights.extend(getattr(r, "insights", []) or [])
        insights.sort(key=lambda i: _SEVERITY_RANK.get(i.severity, 9))
        return [f"{i.severity_icon} {i.title}: {i.description}" for i in insights[:3]]
