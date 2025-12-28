"""Sleep data analyzer."""

from datetime import date
from typing import List, Dict, Optional
from collections import defaultdict
import statistics

from garmindb.data.repositories.base import HealthRepository
from garmindb.data.models import SleepRecord
from .models import (
    SleepAnalysisResult,
    MetricSummary,
    Insight,
    TrendDirection,
    InsightSeverity,
)


class SleepAnalyzer:
    """Analyzes sleep data and generates insights."""

    RECOMMENDED_SLEEP_MIN = 7.0
    RECOMMENDED_SLEEP_MAX = 9.0
    RECOMMENDED_DEEP_PERCENT = 15.0
    RECOMMENDED_REM_PERCENT = 20.0

    def __init__(self, repository: HealthRepository):
        """Initialize with a health data repository."""
        self.repository = repository

    def analyze(self, start_date: date, end_date: date) -> SleepAnalysisResult:
        """Run complete sleep analysis for the given period."""
        sleep_data = self.repository.get_sleep_data(start_date, end_date)

        if not sleep_data:
            return self._empty_result(start_date, end_date)

        avg_total = self._calc_metric_summary(
            "Total Sleep",
            [r.total_hours for r in sleep_data],
            "hours"
        )
        avg_deep = self._calc_metric_summary(
            "Deep Sleep",
            [r.deep_sleep_percent for r in sleep_data],
            "%"
        )
        avg_rem = self._calc_metric_summary(
            "REM Sleep",
            [r.rem_sleep_percent for r in sleep_data],
            "%"
        )

        consistency = self._calc_consistency(sleep_data)
        best_day, worst_day = self._find_best_worst_days(sleep_data)
        insights = self._generate_insights(
            sleep_data, avg_total, avg_deep, avg_rem
        )

        daily_total = {r.date: r.total_hours for r in sleep_data}
        daily_deep = {r.date: r.deep_sleep_percent for r in sleep_data}

        return SleepAnalysisResult(
            period_start=start_date,
            period_end=end_date,
            avg_total_sleep=avg_total,
            avg_deep_sleep=avg_deep,
            avg_rem_sleep=avg_rem,
            sleep_consistency_score=consistency,
            best_sleep_day=best_day,
            worst_sleep_day=worst_day,
            insights=insights,
            daily_total_hours=daily_total,
            daily_deep_percent=daily_deep,
        )

    def _empty_result(
        self, start_date: date, end_date: date
    ) -> SleepAnalysisResult:
        """Create empty result for periods with no data."""
        empty_metric = MetricSummary(name="", current_value=0, unit="")
        return SleepAnalysisResult(
            period_start=start_date,
            period_end=end_date,
            avg_total_sleep=empty_metric,
            avg_deep_sleep=empty_metric,
            avg_rem_sleep=empty_metric,
            sleep_consistency_score=0,
        )

    def _calc_metric_summary(
        self, name: str, values: List[float], unit: str
    ) -> MetricSummary:
        """Calculate summary statistics for a metric."""
        if not values:
            return MetricSummary(name=name, current_value=0, unit=unit)

        current = values[-1]
        avg_all = statistics.mean(values)
        avg_7d = statistics.mean(values[-7:]) if len(values) >= 7 else avg_all

        trend = TrendDirection.STABLE
        if len(values) >= 14:
            recent = statistics.mean(values[-7:])
            previous = statistics.mean(values[-14:-7])
            if previous:
                change_pct = (recent - previous) / previous * 100
            else:
                change_pct = 0
            if change_pct > 5:
                trend = TrendDirection.IMPROVING
            elif change_pct < -5:
                trend = TrendDirection.DECLINING

        return MetricSummary(
            name=name,
            current_value=current,
            unit=unit,
            average_7d=avg_7d,
            average_30d=avg_all,
            min_value=min(values),
            max_value=max(values),
            trend=trend,
        )

    def _calc_consistency(self, data: List[SleepRecord]) -> float:
        """Calculate sleep consistency score (0-100)."""
        if len(data) < 3:
            return 50.0
        hours = [r.total_hours for r in data]
        std_dev = statistics.stdev(hours)
        score = max(0, 100 - (std_dev * 25))
        return round(score, 1)

    def _find_best_worst_days(
        self, data: List[SleepRecord]
    ) -> tuple[Optional[str], Optional[str]]:
        """Find best and worst sleep days of the week."""
        day_totals: Dict[str, List[float]] = defaultdict(list)
        for record in data:
            day_name = record.date.strftime("%A")
            day_totals[day_name].append(record.total_hours)

        if not day_totals:
            return None, None

        day_averages = {
            day: statistics.mean(hours) for day, hours in day_totals.items()
        }
        best = max(day_averages, key=day_averages.get)
        worst = min(day_averages, key=day_averages.get)
        return best, worst

    def _generate_insights(
        self,
        data: List[SleepRecord],
        avg_total: MetricSummary,
        avg_deep: MetricSummary,
        avg_rem: MetricSummary,
    ) -> List[Insight]:
        """Generate actionable insights from sleep data."""
        insights = []
        avg_hours = avg_total.average_7d or avg_total.current_value

        if avg_hours < self.RECOMMENDED_SLEEP_MIN:
            insights.append(Insight(
                title="Sleep Debt Detected",
                description=(
                    f"Average sleep of {avg_hours:.1f}h is below the "
                    f"recommended {self.RECOMMENDED_SLEEP_MIN}-"
                    f"{self.RECOMMENDED_SLEEP_MAX}h range."
                ),
                severity=InsightSeverity.WARNING,
                category="sleep",
                data_points={
                    "avg_sleep": avg_hours,
                    "recommended_min": self.RECOMMENDED_SLEEP_MIN,
                },
                recommendations=[
                    "Try going to bed 30 minutes earlier",
                    "Limit caffeine after 2pm",
                    "Reduce screen time 1 hour before bed",
                ],
            ))
        elif avg_hours > self.RECOMMENDED_SLEEP_MAX:
            insights.append(Insight(
                title="Oversleeping Pattern",
                description=(
                    f"Average sleep of {avg_hours:.1f}h exceeds the "
                    "recommended range."
                ),
                severity=InsightSeverity.INFO,
                category="sleep",
                recommendations=[
                    "Consider a consistent wake time",
                    "Evaluate sleep quality vs quantity",
                ],
            ))
        else:
            insights.append(Insight(
                title="Healthy Sleep Duration",
                description=(
                    f"Average sleep of {avg_hours:.1f}h is within the "
                    "recommended range."
                ),
                severity=InsightSeverity.POSITIVE,
                category="sleep",
            ))

        avg_deep_pct = avg_deep.average_7d or avg_deep.current_value
        if avg_deep_pct < self.RECOMMENDED_DEEP_PERCENT:
            insights.append(Insight(
                title="Low Deep Sleep",
                description=(
                    f"Deep sleep of {avg_deep_pct:.1f}% is below the "
                    f"recommended {self.RECOMMENDED_DEEP_PERCENT}%."
                ),
                severity=InsightSeverity.WARNING,
                category="sleep",
                recommendations=[
                    "Exercise regularly but not close to bedtime",
                    "Maintain a cool bedroom temperature",
                    "Limit alcohol which disrupts deep sleep",
                ],
            ))

        avg_rem_pct = avg_rem.average_7d or avg_rem.current_value
        if avg_rem_pct < self.RECOMMENDED_REM_PERCENT:
            insights.append(Insight(
                title="Low REM Sleep",
                description=(
                    f"REM sleep of {avg_rem_pct:.1f}% is below the "
                    f"recommended {self.RECOMMENDED_REM_PERCENT}%."
                ),
                severity=InsightSeverity.INFO,
                category="sleep",
                recommendations=[
                    "Maintain consistent sleep schedule",
                    "Avoid alcohol before bed",
                ],
            ))

        if avg_total.trend == TrendDirection.DECLINING:
            insights.append(Insight(
                title="Declining Sleep Trend",
                description=(
                    "Your sleep duration has been decreasing over "
                    "the past 2 weeks."
                ),
                severity=InsightSeverity.WARNING,
                category="sleep",
                recommendations=[
                    "Review recent schedule changes",
                    "Consider sleep environment adjustments",
                ],
            ))

        return insights
