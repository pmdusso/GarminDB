"""Main health analyzer entry point."""

from datetime import date, datetime, timedelta
from typing import Optional

from garmindb.data.repositories.base import HealthRepository
from .models import HealthReport, InsightSeverity
from .sleep_analyzer import SleepAnalyzer
from .recovery_analyzer import RecoveryAnalyzer
from .stress_analyzer import StressAnalyzer


class HealthAnalyzer:
    """Main entry point for health analysis.

    Coordinates individual analyzers and generates comprehensive reports.
    """

    def __init__(self, repository: HealthRepository):
        """Initialize with a health data repository."""
        self.repository = repository
        self.sleep = SleepAnalyzer(repository)
        self.recovery = RecoveryAnalyzer(repository)
        self.stress = StressAnalyzer(repository)

    def daily_report(self, day: Optional[date] = None) -> HealthReport:
        """Generate report for a single day."""
        target_day = day or date.today()
        return self.generate_report(target_day, target_day)

    def weekly_report(self, end_date: Optional[date] = None) -> HealthReport:
        """Generate report for the past 7 days."""
        end = end_date or date.today()
        start = end - timedelta(days=6)
        return self.generate_report(start, end)

    def monthly_report(self, end_date: Optional[date] = None) -> HealthReport:
        """Generate report for the past 30 days."""
        end = end_date or date.today()
        start = end - timedelta(days=29)
        return self.generate_report(start, end)

    def generate_report(
        self, start_date: date, end_date: date
    ) -> HealthReport:
        """Generate comprehensive health report for period."""
        sleep_result = self.sleep.analyze(start_date, end_date)
        recovery_result = self.recovery.analyze(start_date, end_date)
        stress_result = self.stress.analyze(start_date, end_date)
        key_insights = self._collect_key_insights(
            sleep_result, recovery_result, stress_result
        )

        return HealthReport(
            generated_at=datetime.now(),
            period_start=start_date,
            period_end=end_date,
            sleep=sleep_result,
            recovery=recovery_result,
            stress=stress_result,
            key_insights=key_insights,
            metadata={
                "version": "1.0",
                "analyzers": ["sleep", "recovery", "stress"],
            },
        )

    def _collect_key_insights(self, *analyses) -> list:
        """Collect most important insights from all analyses."""
        key_insights = []

        for analysis in analyses:
            if analysis and hasattr(analysis, 'insights'):
                for insight in analysis.insights:
                    if insight.severity in (
                        InsightSeverity.WARNING,
                        InsightSeverity.ALERT
                    ):
                        if insight not in key_insights:
                            key_insights.append(insight)

        return key_insights
