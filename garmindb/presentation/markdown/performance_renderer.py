# garmindb/presentation/markdown/performance_renderer.py
"""Render a PerformanceReport to Markdown."""

from typing import List, Optional

from garmindb.analysis.performance_report import PerformanceReport
from garmindb.analysis.report_state import MetricDelta


class PerformancePresenter:
    """Self-contained Markdown renderer for the performance report."""

    def __init__(self, include_metadata: bool = True):
        self._include_metadata = include_metadata

    def render(self, report: PerformanceReport) -> str:
        parts: List[str] = []
        if self._include_metadata:
            parts.append(self._frontmatter(report))
        parts.append(self._header(report))
        parts.append(self._readiness(report))
        parts.append(self._scorecard(report))
        parts.append(self._priorities(report))
        return "\n".join(p for p in parts if p).rstrip() + "\n"

    def _frontmatter(self, r: PerformanceReport) -> str:
        return (
            "---\n"
            "report_type: performance\n"
            f"generated: {r.generated_at.isoformat()}\n"
            f"period_start: {r.period_start}\n"
            f"period_end: {r.period_end}\n"
            f"race: {r.targets.race_name or ''}\n"
            "---\n"
        )

    def _header(self, r: PerformanceReport) -> str:
        race = r.targets.race_name or "prova-alvo"
        return (
            f"# 🎯 Performance — {r.period_start} a {r.period_end}\n\n"
            f"Meta: {race}"
            + (f" ({r.targets.race_date})" if r.targets.race_date else "")
            + f" · gerado {r.generated_at:%d/%m/%Y}\n"
        )

    def _readiness(self, r: PerformanceReport) -> str:
        return f"\n**PRONTIDÃO:** {r.readiness_light} {r.readiness_label}\n"

    @staticmethod
    def _delta_cell(delta: Optional[MetricDelta]) -> str:
        if delta is None or not delta.has_previous or delta.delta is None:
            return "baseline"
        arrow = "↑" if delta.delta > 0 else ("↓" if delta.delta < 0 else "→")
        return f"{arrow} {abs(delta.delta):.2f}".replace(".", ",")

    def _scorecard(self, r: PerformanceReport) -> str:
        lines = [
            "\n## Resumo Executivo\n",
            "| Métrica | Agora | Meta | Gap | Δ |",
            "|---|---|---|---|---|",
        ]
        for row in r.scorecard:
            lines.append(
                f"| {row.label} | {row.current} | {row.target} | "
                f"{row.gap} | {self._delta_cell(row.delta)} |"
            )
        return "\n".join(lines) + "\n"

    def _priorities(self, r: PerformanceReport) -> str:
        if not r.priorities:
            return ""
        lines = ["\n## Prioridades agora\n"]
        for i, p in enumerate(r.priorities, 1):
            lines.append(f"{i}. {p}")
        return "\n".join(lines) + "\n"
