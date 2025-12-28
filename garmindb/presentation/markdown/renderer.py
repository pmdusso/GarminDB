"""Markdown renderer for health analysis results."""

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from garmindb.analysis.models import (
        SleepAnalysisResult,
        StressAnalysisResult,
        ActivityAnalysisResult,
        HealthReport,
        MetricSummary,
        Insight,
    )

# Handle both package imports and direct imports for testing
try:
    from ..base import Presenter
except ImportError:
    from base import Presenter


class MarkdownPresenter(Presenter):
    """Renders analysis results as LLM-friendly Markdown."""

    def __init__(self, include_metadata: bool = True):
        """Initialize presenter."""
        self.include_metadata = include_metadata

    def render_report(self, report: "HealthReport") -> str:
        """Render complete health report as Markdown."""
        sections = []

        if self.include_metadata:
            sections.append(self._render_metadata(report))

        sections.append(
            f"# Health Report: {report.period_start} to {report.period_end}"
        )
        generated = report.generated_at.strftime('%Y-%m-%d %H:%M')
        sections.append(f"\n*Generated: {generated}*\n")

        if report.sleep:
            sections.append(self.render_sleep(report.sleep))

        if report.stress:
            sections.append(self._render_stress(report.stress))

        if report.activities:
            sections.append(self._render_activities(report.activities))

        if report.key_insights:
            sections.append(self._render_insights_section(report.key_insights))

        return "\n\n".join(sections)

    def render_sleep(self, result: "SleepAnalysisResult") -> str:
        """Render sleep analysis section."""
        lines = []
        lines.append("## Sleep Analysis")
        lines.append(
            f"\n*Period: {result.period_start} to {result.period_end}*\n"
        )

        lines.append("### Summary\n")
        lines.append("| Metric | Current | 7-day Avg | Trend |")
        lines.append("|--------|---------|-----------|-------|")

        metrics = [
            result.avg_total_sleep, result.avg_deep_sleep, result.avg_rem_sleep
        ]
        for metric in metrics:
            lines.append(self._metric_row(metric))

        lines.append(
            f"\n**Sleep Consistency Score:** "
            f"{result.sleep_consistency_score:.0f}/100\n"
        )

        if result.best_sleep_day or result.worst_sleep_day:
            lines.append("### Patterns\n")
            if result.best_sleep_day:
                lines.append(f"- **Best Sleep Day:** {result.best_sleep_day}")
            if result.worst_sleep_day:
                lines.append(
                    f"- **Worst Sleep Day:** {result.worst_sleep_day}"
                )
            lines.append("")

        if result.insights:
            lines.append("### Insights\n")
            for insight in result.insights:
                lines.append(self._render_insight(insight))

        return "\n".join(lines)

    def _render_metadata(self, report: "HealthReport") -> str:
        """Render YAML frontmatter for LLM context."""
        return f"""---
report_type: health_analysis
generated: {report.generated_at.isoformat()}
period_start: {report.period_start}
period_end: {report.period_end}
data_source: garmin_connect
format_version: "1.0"
---"""

    def _metric_row(self, metric: "MetricSummary") -> str:
        """Render a metric as a table row."""
        current = f"{metric.current_value:.1f} {metric.unit}"
        if metric.average_7d:
            avg_7d = f"{metric.average_7d:.1f} {metric.unit}"
        else:
            avg_7d = "---"
        trend = metric.trend_icon
        return f"| {metric.name} | {current} | {avg_7d} | {trend} |"

    def _render_insight(self, insight: "Insight") -> str:
        """Render a single insight."""
        lines = []
        icon = insight.severity_icon
        lines.append(f"#### {icon} {insight.title}\n")
        lines.append(f"{insight.description}\n")

        if insight.recommendations:
            lines.append("**Recommendations:**")
            for rec in insight.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)

    def _render_insights_section(self, insights: List["Insight"]) -> str:
        """Render key insights section."""
        lines = ["## Key Insights\n"]
        for insight in insights:
            lines.append(self._render_insight(insight))
        return "\n".join(lines)

    def _render_stress(self, result: "StressAnalysisResult") -> str:
        """Render stress analysis section."""
        lines = []
        lines.append("## Stress Analysis")
        period = f"{result.period_start} to {result.period_end}"
        lines.append(f"\n*Period: {period}*\n")
        lines.append("### Distribution\n")
        lines.append(f"- **Low Stress:** {result.low_stress_percent:.1f}%")
        med_stress = result.medium_stress_percent
        lines.append(f"- **Medium Stress:** {med_stress:.1f}%")
        lines.append(f"- **High Stress:** {result.high_stress_percent:.1f}%")

        if result.insights:
            lines.append("\n### Insights\n")
            for insight in result.insights:
                lines.append(self._render_insight(insight))

        return "\n".join(lines)

    def _render_activities(self, result: "ActivityAnalysisResult") -> str:
        """Render activities analysis section."""
        lines = []
        lines.append("## Activity Summary")
        period = f"{result.period_start} to {result.period_end}"
        lines.append(f"\n*Period: {period}*\n")
        lines.append(f"- **Total Activities:** {result.total_activities}")
        duration = result.total_duration_hours
        lines.append(f"- **Total Duration:** {duration:.1f} hours")
        distance = result.total_distance_km
        lines.append(f"- **Total Distance:** {distance:.1f} km")
        lines.append(f"- **Total Calories:** {result.total_calories:,}")

        if result.activities_by_sport:
            lines.append("\n### By Sport\n")
            for sport, count in sorted(result.activities_by_sport.items()):
                lines.append(f"- **{sport}:** {count}")

        return "\n".join(lines)
