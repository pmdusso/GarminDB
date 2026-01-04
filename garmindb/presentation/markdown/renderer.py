"""Markdown renderer for health analysis results."""

from typing import List, TYPE_CHECKING

if TYPE_CHECKING:
    from garmindb.analysis.models import (
        SleepAnalysisResult,
        StressAnalysisResult,
        RecoveryAnalysisResult,
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

        if report.recovery:
            sections.append(self._render_recovery(report.recovery))

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

        # Summary Metrics
        lines.append("### Key Metrics\n")
        avg = result.avg_stress.current_value
        lines.append(f"- **Average Stress:** {avg:.1f}")
        if result.stress_load:
            load = result.stress_load.total_load
            lines.append(f"- **Total Stress Load:** {load:.0f} pts")
            peak = result.stress_load.peak_load_hour
            peak_str = peak.strftime('%H:%M') if peak else '---'
            lines.append(f"- **Peak Load Hour:** {peak_str}")
        baseline = result.personal_baseline
        lines.append(f"- **Personal Baseline:** {baseline:.1f} (resting)\n")

        # Distribution
        lines.append("### Distribution\n")
        low = result.low_stress_percent
        med = result.medium_stress_percent
        high = result.high_stress_percent
        lines.append(f"- **Low Stress:** {low:.1f}%")
        lines.append(f"- **Medium Stress:** {med:.1f}%")
        lines.append(f"- **High Stress:** {high:.1f}%\n")

        # Recovery Efficiency
        if result.recovery_efficiency is not None:
            lines.append("### Stress Resilience\n")
            eff = result.recovery_efficiency
            lines.append(f"- **Recovery Efficiency:** {eff:.0f}/100")
            if result.avg_recovery_time_minutes:
                avg_rec = result.avg_recovery_time_minutes
                lines.append(f"- **Avg Recovery Time:** {avg_rec:.0f} min")
            lines.append("")

        if result.insights:
            lines.append("### Insights\n")
            for insight in result.insights:
                lines.append(self._render_insight(insight))

        return "\n".join(lines)

    def _render_activities(self, result: "ActivityAnalysisResult") -> str:
        """Render activities analysis section."""
        lines = []
        lines.append("## Activity Summary")
        period = f"{result.period_start} to {result.period_end}"
        lines.append(f"\n*Period: {period}*\n")

        # Basic totals
        lines.append(f"- **Total Activities:** {result.total_activities}")
        duration = result.total_duration_hours
        lines.append(f"- **Total Duration:** {duration:.1f} hours")
        distance = result.total_distance_km
        lines.append(f"- **Total Distance:** {distance:.1f} km")
        lines.append(f"- **Total Calories:** {result.total_calories:,}")
        lines.append("")

        # Training Stress Metrics (TSB)
        if result.training_stress:
            ts = result.training_stress
            lines.append("### Training Load\n")
            lines.append(f"- **Fitness (CTL):** {ts.ctl:.0f}")
            lines.append(f"- **Fatigue (ATL):** {ts.atl:.0f}")
            tsb_label = self._tsb_form_label(ts.tsb)
            lines.append(f"- **Form (TSB):** {ts.tsb:.0f} ({tsb_label})")
            if ts.monotony is not None:
                lines.append(f"- **Monotony:** {ts.monotony:.2f}")
                lines.append(f"- **Strain:** {ts.strain:.0f}")
            if ts.confidence_score < 0.7:
                conf_pct = ts.confidence_score * 100
                lines.append(f"- **Data Confidence:** {conf_pct:.0f}% ⚠️")
            lines.append("")

        # Intensity Distribution with ASCII progress bars
        if result.intensity_distribution:
            lines.append("### Intensity Distribution\n")
            lines.append("```")
            categories = [
                "Recovery", "Base", "Improving",
                "Highly Improving", "Overreaching"
            ]
            for cat in categories:
                pct = result.intensity_distribution.get(cat, 0)
                bar = self._progress_bar(pct)
                lines.append(f"{cat:17s} {bar} {pct:5.1f}%")
            lines.append("```")
            lines.append("")

        # Training Effect averages
        if result.avg_aerobic_effect > 0:
            lines.append("### Training Effect\n")
            lines.append(f"- **Avg Aerobic Effect:** {result.avg_aerobic_effect:.1f}")
            if result.avg_anaerobic_effect > 0:
                anaerobic = result.avg_anaerobic_effect
                lines.append(f"- **Avg Anaerobic Effect:** {anaerobic:.1f}")
            lines.append("")

        # Sport Summaries table
        if result.sport_summaries:
            lines.append("### By Sport\n")
            lines.append("| Sport | Count | Distance | Duration | Efficiency |")
            lines.append("|-------|-------|----------|----------|------------|")
            for name, summary in sorted(result.sport_summaries.items()):
                dist = f"{summary.total_distance_km:.1f} km"
                dur = f"{summary.total_duration_hours:.1f} h"
                if summary.efficiency_index:
                    eff = f"{summary.efficiency_index:.1f}"
                else:
                    eff = "---"
                row = f"| {name} | {summary.count} | {dist} | {dur} | {eff} |"
                lines.append(row)
            lines.append("")

        # Insights
        if result.insights:
            lines.append("### Insights\n")
            for insight in result.insights:
                lines.append(self._render_insight(insight))

        return "\n".join(lines)

    def _progress_bar(self, percent: float, width: int = 10) -> str:
        """Create ASCII progress bar."""
        filled = int(percent / 100 * width)
        empty = width - filled
        return f"[{'=' * filled}{' ' * empty}]"

    def _tsb_form_label(self, tsb: float) -> str:
        """Get form label for TSB value."""
        if tsb > 25:
            return "peak form"
        elif tsb > 5:
            return "fresh"
        elif tsb >= -10:
            return "neutral"
        elif tsb >= -30:
            return "tired"
        else:
            return "fatigued"

    def _render_recovery(self, result: "RecoveryAnalysisResult") -> str:
        """Render recovery analysis section."""
        lines = []
        lines.append("## Recovery Analysis")
        period = f"{result.period_start} to {result.period_end}"
        lines.append(f"\n*Period: {period}*\n")

        # Recovery Score with trend
        if result.recovery_trend:
            trend_val = result.recovery_trend.value
        else:
            trend_val = "stable"
        score = result.recovery_score
        lines.append(f"**Recovery Score:** {score}/100 ({trend_val})\n")

        # Summary metrics table
        lines.append("### Key Metrics\n")
        lines.append("| Metric | Current | 7-day Avg | Trend |")
        lines.append("|--------|---------|-----------|-------|")
        lines.append(self._metric_row(result.rhr_summary))
        lines.append(self._metric_row(result.body_battery_summary))
        lines.append(self._metric_row(result.training_load_summary))
        lines.append("")

        # Recovery indicators
        lines.append("### Recovery Indicators\n")
        rhr_base = result.rhr_baseline
        lines.append(f"- **RHR Baseline:** {rhr_base:.0f} bpm")
        if result.rhr_deviation != 0:
            dev = result.rhr_deviation
            dev_str = f"+{dev:.1f}" if dev > 0 else f"{dev:.1f}"
            lines.append(f"- **RHR Deviation:** {dev_str} bpm from baseline")
        tss = result.weekly_tss
        lines.append(f"- **Weekly Training Load:** {tss:.0f} TSS")

        if result.acute_chronic_ratio is not None:
            acwr = result.acute_chronic_ratio
            risk = self._acwr_risk_label(acwr)
            lines.append(f"- **Acute:Chronic Ratio:** {acwr:.2f} ({risk})")

        lines.append("")

        # Summary statistics
        if result.days_analyzed > 0:
            lines.append("### Period Statistics\n")
            days = result.days_analyzed
            high_days = result.high_recovery_days
            low_days = result.low_recovery_days
            lines.append(f"- **Days Analyzed:** {days}")
            lines.append(f"- **High Recovery Days:** {high_days}")
            lines.append(f"- **Low Recovery Days:** {low_days}")
            lines.append("")

        # Insights
        if result.insights:
            lines.append("### Insights\n")
            for insight in result.insights:
                lines.append(self._render_insight(insight))

        return "\n".join(lines)

    def _acwr_risk_label(self, acwr: float) -> str:
        """Get risk label for ACWR value."""
        if acwr < 0.8:
            return "undertrained"
        elif acwr <= 1.3:
            return "optimal zone"
        elif acwr <= 1.5:
            return "elevated risk"
        else:
            return "high injury risk"
