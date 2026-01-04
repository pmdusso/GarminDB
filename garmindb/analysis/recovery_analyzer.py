"""Recovery analysis: RHR, Body Battery, Training Load.

This module analyzes recovery metrics to assess overall recovery status
and identify potential overtraining or injury risk.
"""

from datetime import date, timedelta
from typing import List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from garmindb.data.repositories.base import HealthRepository

from .models import (
    RecoveryAnalysisResult,
    DailyReadinessResult,
    MetricSummary,
    Insight,
    InsightSeverity,
    TrendDirection,
)


class RecoveryAnalyzer:
    """Analyzes recovery metrics: RHR, Body Battery, Training Load.

    The analyzer computes a recovery score based on three components:
    - RHR deviation from baseline (40% weight)
    - Body Battery overnight recharge (35% weight)
    - Sleep quality score (25% weight)

    It also calculates the Acute:Chronic Workload Ratio (ACWR) to
    assess injury risk from training load.

    Attributes:
        RHR_BASELINE_DAYS: Days to use for RHR baseline calculation
        ACUTE_LOAD_DAYS: Days for acute training load (ATL)
        CHRONIC_LOAD_DAYS: Days for chronic training load (CTL)
    """

    # Configuration
    RHR_BASELINE_DAYS = 60
    ACUTE_LOAD_DAYS = 7
    CHRONIC_LOAD_DAYS = 28

    # Recovery score weights
    RHR_WEIGHT = 0.40
    BB_WEIGHT = 0.35
    SLEEP_WEIGHT = 0.25

    # ACWR risk thresholds
    ACWR_UNDERTRAINED = 0.8
    ACWR_OPTIMAL_MAX = 1.3
    ACWR_CAUTION_MAX = 1.5

    def __init__(self, repository: 'HealthRepository'):
        """Initialize with health data repository.

        Args:
            repository: HealthRepository implementation for data access.
        """
        self._repository = repository

    def analyze(
        self,
        start_date: date,
        end_date: date
    ) -> RecoveryAnalysisResult:
        """Analyze recovery for a period.

        Fetches historical data including lookback buffer for baseline
        calculations, then computes recovery metrics and insights.

        Args:
            start_date: Start of analysis period (inclusive)
            end_date: End of analysis period (inclusive)

        Returns:
            RecoveryAnalysisResult with scores, metrics, and insights
        """
        # Fetch data with lookback buffer for baseline calculation
        lookback_days = max(self.RHR_BASELINE_DAYS, self.CHRONIC_LOAD_DAYS)
        data_start = start_date - timedelta(days=lookback_days)

        daily_data = self._repository.get_daily_summaries(data_start, end_date)
        activities = self._repository.get_activities(data_start, end_date)
        sleep_data = self._repository.get_sleep_data(data_start, end_date)

        # Filter to period for analysis
        period_daily = [d for d in daily_data if start_date <= d.date <= end_date]
        period_activities = [
            a for a in activities
            if start_date <= a.start_time.date() <= end_date
        ]

        # Calculate RHR metrics
        rhr_baseline = self._calculate_rhr_baseline(daily_data, end_date)
        rhr_values = [d.resting_hr for d in period_daily if d.resting_hr]
        has_rhr_data = len(rhr_values) > 0
        rhr_current = sum(rhr_values) / len(rhr_values) if has_rhr_data else None
        # Only calculate deviation if we have both current data and baseline
        if has_rhr_data and rhr_baseline:
            rhr_deviation = rhr_current - rhr_baseline
        else:
            rhr_deviation = 0.0

        # Calculate Body Battery metrics
        bb_values = [d.bb_charged for d in period_daily if d.bb_charged]
        bb_avg = sum(bb_values) / len(bb_values) if bb_values else 50

        # Calculate Training Load metrics
        tss_values = [
            a.training_load for a in period_activities
            if a.training_load is not None
        ]
        weekly_tss = sum(tss_values) if tss_values else 0
        acwr = self._calculate_acute_chronic_ratio(activities, end_date)

        # Calculate recovery score
        sleep_scores = [
            s.sleep_score for s in sleep_data
            if start_date <= s.date <= end_date and s.sleep_score
        ]
        avg_sleep_score = (
            sum(sleep_scores) / len(sleep_scores) if sleep_scores else None
        )

        # Check if we have any meaningful data
        has_bb_data = len(bb_values) > 0
        has_sleep_data = len(sleep_scores) > 0
        has_any_data = has_rhr_data or has_bb_data or has_sleep_data

        if has_any_data:
            recovery_score = self._calculate_recovery_score(
                rhr_deviation, int(bb_avg), avg_sleep_score,
                has_rhr_data=has_rhr_data
            )
        else:
            recovery_score = 50  # Neutral score when no data

        # Determine trend
        recovery_trend = self._calculate_trend(daily_data, start_date, end_date)

        # Count recovery day categories
        high_days = sum(
            1 for d in period_daily
            if d.bb_charged and d.bb_charged >= 80
        )
        low_days = sum(
            1 for d in period_daily
            if d.bb_charged and d.bb_charged < 50
        )

        # Build metric summaries
        rhr_summary = MetricSummary(
            name="Resting Heart Rate",
            current_value=rhr_current if rhr_current is not None else 0.0,
            unit="bpm",
            average_7d=self._avg_last_n_days(daily_data, 7, 'resting_hr'),
            average_30d=self._avg_last_n_days(daily_data, 30, 'resting_hr'),
            min_value=min(rhr_values) if rhr_values else None,
            max_value=max(rhr_values) if rhr_values else None,
            trend=self._rhr_trend(rhr_deviation) if has_rhr_data else TrendDirection.STABLE,
        )

        bb_summary = MetricSummary(
            name="Body Battery Recharge",
            current_value=bb_avg,
            unit="%",
            average_7d=self._avg_last_n_days(daily_data, 7, 'bb_charged'),
            average_30d=self._avg_last_n_days(daily_data, 30, 'bb_charged'),
            min_value=min(bb_values) if bb_values else None,
            max_value=max(bb_values) if bb_values else None,
        )

        tss_summary = MetricSummary(
            name="Training Load",
            current_value=weekly_tss,
            unit="TSS",
            average_7d=weekly_tss,  # Already weekly
        )

        # Generate insights
        insights = self._generate_insights(
            rhr_deviation, rhr_baseline, bb_avg, acwr, recovery_score,
            has_rhr_data=has_rhr_data
        )

        return RecoveryAnalysisResult(
            period_start=start_date,
            period_end=end_date,
            recovery_score=recovery_score,
            recovery_trend=recovery_trend,
            rhr_summary=rhr_summary,
            body_battery_summary=bb_summary,
            training_load_summary=tss_summary,
            rhr_baseline=rhr_baseline,
            rhr_deviation=rhr_deviation,
            weekly_tss=weekly_tss,
            acute_chronic_ratio=acwr,
            insights=insights,
            days_analyzed=len(period_daily),
            high_recovery_days=high_days,
            low_recovery_days=low_days,
        )

    def daily_readiness(self, target_date: date) -> DailyReadinessResult:
        """Calculate readiness score for a specific day.

        Args:
            target_date: The date to calculate readiness for

        Returns:
            DailyReadinessResult with scores and recommendations
        """
        # Get data for the day and lookback for baseline
        lookback_start = target_date - timedelta(days=self.RHR_BASELINE_DAYS)

        daily_data = self._repository.get_daily_summaries(
            lookback_start, target_date
        )
        sleep_data = self._repository.get_sleep_data(
            target_date - timedelta(days=1), target_date
        )
        activities = self._repository.get_activities(
            target_date - timedelta(days=self.CHRONIC_LOAD_DAYS), target_date
        )

        # Get today's data
        today_data = next(
            (d for d in daily_data if d.date == target_date), None
        )
        yesterday_sleep = next(
            (s for s in sleep_data if s.date == target_date), None
        )

        # Calculate factors
        rhr_baseline = self._calculate_rhr_baseline(daily_data, target_date)
        current_rhr = today_data.resting_hr if today_data else None

        if rhr_baseline and current_rhr:
            rhr_deviation = current_rhr - rhr_baseline
            rhr_factor = max(0, min(1, 1 - (abs(rhr_deviation) / 20)))
        else:
            rhr_factor = 0.5

        if today_data and today_data.bb_charged:
            bb_factor = today_data.bb_charged / 100
        elif today_data and today_data.bb_max:
            bb_factor = today_data.bb_max / 100
        else:
            bb_factor = 0.5

        if yesterday_sleep and yesterday_sleep.sleep_score:
            sleep_factor = yesterday_sleep.sleep_score / 100
        else:
            sleep_factor = 0.7

        # Calculate activity factor from recent training load
        recent_tss = sum(
            a.training_load for a in activities
            if a.training_load and a.start_time.date() >= target_date - timedelta(days=3)
        )
        activity_factor = max(0, min(1, 1 - (recent_tss / 300)))

        # Calculate scores
        recovery_score = int(
            (rhr_factor * 0.3 + bb_factor * 0.4 + sleep_factor * 0.3) * 100
        )
        readiness_score = int(
            (recovery_score * 0.6 + activity_factor * 100 * 0.4)
        )

        # Determine recommended intensity
        if readiness_score >= 80:
            recommended = "intense"
        elif readiness_score >= 60:
            recommended = "moderate"
        elif readiness_score >= 40:
            recommended = "light"
        else:
            recommended = "rest"

        return DailyReadinessResult(
            analysis_date=target_date,
            recovery_score=recovery_score,
            readiness_score=readiness_score,
            sleep_factor=sleep_factor,
            stress_factor=1 - (
                today_data.stress_avg / 100
                if today_data and today_data.stress_avg else 0.3
            ),
            activity_factor=activity_factor,
            recommended_intensity=recommended,
            body_battery_morning=today_data.bb_max if today_data else None,
        )

    def _calculate_rhr_baseline(
        self,
        daily_data: List,
        end_date: date
    ) -> float:
        """Calculate RHR baseline from historical data.

        Uses the average of the lowest 25% of RHR values over the
        baseline period to establish a true resting baseline.

        Args:
            daily_data: List of DailySummaryRecord
            end_date: End date for baseline calculation

        Returns:
            Baseline RHR value in bpm
        """
        baseline_start = end_date - timedelta(days=self.RHR_BASELINE_DAYS)
        baseline_data = [
            d.resting_hr for d in daily_data
            if baseline_start <= d.date <= end_date and d.resting_hr
        ]

        if not baseline_data:
            return 0.0

        # Use average of lowest 25% for true baseline
        baseline_data.sort()
        n_lowest = max(1, len(baseline_data) // 4)
        return sum(baseline_data[:n_lowest]) / n_lowest

    def _calculate_recovery_score(
        self,
        rhr_deviation: float,
        bb_charged: int,
        sleep_score: Optional[int],
        has_rhr_data: bool = True
    ) -> int:
        """Calculate weighted recovery score.

        Formula:
            recovery_score = (RHR_component * 0.40 +
                            BB_component * 0.35 +
                            Sleep_component * 0.25)

        When RHR data is missing, weights are normalized across
        available components.

        Args:
            rhr_deviation: Beats per minute deviation from baseline
            bb_charged: Body battery overnight recharge (0-100)
            sleep_score: Sleep score if available (0-100)
            has_rhr_data: Whether RHR data is available

        Returns:
            Recovery score from 0-100
        """
        # BB component: direct mapping
        bb_component = max(0, min(100, bb_charged))

        # Sleep component: use score or neutral value
        sleep_component = sleep_score if sleep_score else 70

        if has_rhr_data:
            # RHR component: penalize deviation from baseline
            # 5 bpm deviation = -25 points
            rhr_component = max(0, min(100, 100 - abs(rhr_deviation) * 5))
            score = (
                rhr_component * self.RHR_WEIGHT +
                bb_component * self.BB_WEIGHT +
                sleep_component * self.SLEEP_WEIGHT
            )
        else:
            # Normalize weights when RHR is missing (BB=0.58, Sleep=0.42)
            total_weight = self.BB_WEIGHT + self.SLEEP_WEIGHT
            bb_weight = self.BB_WEIGHT / total_weight
            sleep_weight = self.SLEEP_WEIGHT / total_weight
            score = bb_component * bb_weight + sleep_component * sleep_weight

        return int(max(0, min(100, score)))

    def _calculate_acute_chronic_ratio(
        self,
        activities: List,
        end_date: date
    ) -> Optional[float]:
        """Calculate Acute:Chronic Workload Ratio.

        ACWR = ATL / CTL where:
        - ATL (Acute Training Load) = avg daily TSS over last 7 days
        - CTL (Chronic Training Load) = avg daily TSS over last 28 days

        Risk zones:
        - < 0.8: Undertrained
        - 0.8 - 1.3: Optimal
        - 1.3 - 1.5: Caution
        - > 1.5: High injury risk

        Args:
            activities: List of ActivityRecord
            end_date: End date for calculation

        Returns:
            ACWR ratio or None if insufficient data
        """
        acute_start = end_date - timedelta(days=self.ACUTE_LOAD_DAYS)
        chronic_start = end_date - timedelta(days=self.CHRONIC_LOAD_DAYS)

        # Calculate daily TSS for acute period
        acute_tss = [
            a.training_load for a in activities
            if a.training_load and acute_start <= a.start_time.date() <= end_date
        ]

        # Calculate daily TSS for chronic period
        chronic_tss = [
            a.training_load for a in activities
            if a.training_load and chronic_start <= a.start_time.date() <= end_date
        ]

        if not chronic_tss:
            return None

        atl = sum(acute_tss) / self.ACUTE_LOAD_DAYS
        ctl = sum(chronic_tss) / self.CHRONIC_LOAD_DAYS

        if ctl == 0:
            return None

        return round(atl / ctl, 2)

    def _calculate_trend(
        self,
        daily_data: List,
        start_date: date,
        end_date: date
    ) -> TrendDirection:
        """Determine recovery trend based on RHR and BB patterns."""
        period_data = [
            d for d in daily_data
            if start_date <= d.date <= end_date
        ]

        if len(period_data) < 7:
            return TrendDirection.STABLE

        # Split into first half and second half
        mid = len(period_data) // 2
        first_half = period_data[:mid]
        second_half = period_data[mid:]

        # Compare RHR averages
        first_rhr = [d.resting_hr for d in first_half if d.resting_hr]
        second_rhr = [d.resting_hr for d in second_half if d.resting_hr]

        if first_rhr and second_rhr:
            avg_first = sum(first_rhr) / len(first_rhr)
            avg_second = sum(second_rhr) / len(second_rhr)

            # Lower RHR = improving recovery
            if avg_second < avg_first - 2:
                return TrendDirection.IMPROVING
            elif avg_second > avg_first + 2:
                return TrendDirection.DECLINING

        return TrendDirection.STABLE

    def _rhr_trend(self, deviation: float) -> TrendDirection:
        """Determine trend based on RHR deviation."""
        if deviation < -2:
            return TrendDirection.IMPROVING
        elif deviation > 2:
            return TrendDirection.DECLINING
        return TrendDirection.STABLE

    def _avg_last_n_days(
        self,
        daily_data: List,
        n_days: int,
        field: str
    ) -> Optional[float]:
        """Calculate average of a field over last N days."""
        if not daily_data:
            return None

        sorted_data = sorted(daily_data, key=lambda d: d.date, reverse=True)
        values = []
        for d in sorted_data[:n_days]:
            val = getattr(d, field, None)
            if val is not None:
                values.append(val)

        return sum(values) / len(values) if values else None

    def _generate_insights(
        self,
        rhr_deviation: float,
        rhr_baseline: float,
        bb_avg: float,
        acwr: Optional[float],
        recovery_score: int,
        has_rhr_data: bool = True
    ) -> List[Insight]:
        """Generate recovery insights based on metrics.

        Args:
            rhr_deviation: RHR deviation from baseline
            rhr_baseline: Baseline RHR value
            bb_avg: Average body battery recharge
            acwr: Acute:Chronic workload ratio
            recovery_score: Overall recovery score
            has_rhr_data: Whether RHR data is available for the period

        Returns:
            List of Insight objects
        """
        insights = []

        # RHR insights - only generate if we have actual RHR data
        if has_rhr_data and rhr_deviation > 10:
            insights.append(Insight(
                title="Significantly Elevated RHR",
                description=(
                    f"Your resting heart rate is {rhr_deviation:.0f} bpm "
                    f"above your baseline of {rhr_baseline:.0f} bpm. "
                    "This suggests incomplete recovery."
                ),
                severity=InsightSeverity.ALERT,
                category="recovery",
                data_points={
                    "rhr_deviation": rhr_deviation,
                    "rhr_baseline": rhr_baseline,
                },
                recommendations=[
                    "Consider taking a rest day",
                    "Prioritize sleep quality",
                    "Check for signs of illness or overtraining",
                ],
            ))
        elif has_rhr_data and rhr_deviation > 5:
            insights.append(Insight(
                title="Elevated RHR",
                description=(
                    f"Your RHR is {rhr_deviation:.0f} bpm above baseline. "
                    "Monitor your recovery carefully."
                ),
                severity=InsightSeverity.WARNING,
                category="recovery",
                data_points={"rhr_deviation": rhr_deviation},
                recommendations=[
                    "Consider reducing training intensity",
                    "Ensure adequate sleep",
                ],
            ))
        elif has_rhr_data and rhr_deviation < -3:
            insights.append(Insight(
                title="Excellent RHR Recovery",
                description=(
                    f"Your RHR is {abs(rhr_deviation):.0f} bpm below baseline. "
                    "You're well recovered!"
                ),
                severity=InsightSeverity.POSITIVE,
                category="recovery",
            ))

        # Body Battery insights
        if bb_avg < 30:
            insights.append(Insight(
                title="Low Overnight Recharge",
                description=(
                    f"Average overnight recharge is only {bb_avg:.0f}%. "
                    "Your body isn't recovering fully during sleep."
                ),
                severity=InsightSeverity.WARNING,
                category="recovery",
                data_points={"bb_charged_avg": bb_avg},
                recommendations=[
                    "Improve sleep hygiene",
                    "Reduce evening stress",
                    "Avoid late workouts",
                ],
            ))
        elif bb_avg >= 80:
            insights.append(Insight(
                title="Excellent Recovery",
                description=(
                    f"Average overnight recharge of {bb_avg:.0f}% indicates "
                    "great recovery capacity."
                ),
                severity=InsightSeverity.POSITIVE,
                category="recovery",
            ))

        # ACWR insights
        if acwr is not None:
            if acwr > self.ACWR_CAUTION_MAX:
                insights.append(Insight(
                    title="High Injury Risk",
                    description=(
                        f"Your ACWR of {acwr:.2f} indicates rapid training "
                        "load increase. This is associated with higher injury risk."
                    ),
                    severity=InsightSeverity.ALERT,
                    category="recovery",
                    data_points={"acwr": acwr},
                    recommendations=[
                        "Reduce training volume by 20-30%",
                        "Focus on recovery activities",
                        "Gradual load progression (10% rule)",
                    ],
                ))
            elif acwr > self.ACWR_OPTIMAL_MAX:
                insights.append(Insight(
                    title="Training Load Caution",
                    description=(
                        f"ACWR of {acwr:.2f} is elevated. "
                        "Be mindful of recovery between sessions."
                    ),
                    severity=InsightSeverity.WARNING,
                    category="recovery",
                    data_points={"acwr": acwr},
                ))
            elif acwr < self.ACWR_UNDERTRAINED:
                insights.append(Insight(
                    title="Training Load Below Optimal",
                    description=(
                        f"ACWR of {acwr:.2f} suggests training load "
                        "may be too low for optimal adaptation."
                    ),
                    severity=InsightSeverity.INFO,
                    category="recovery",
                    data_points={"acwr": acwr},
                    recommendations=[
                        "Gradually increase training volume",
                        "Add intensity or duration progressively",
                    ],
                ))

        return insights
