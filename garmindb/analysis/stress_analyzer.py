"""Stress analysis: patterns, load calculation, and recovery efficiency.

This module analyzes stress data to identify patterns, calculate cumulative
stress load (AUC), and measure post-activity recovery efficiency.
"""

from datetime import date, datetime
from typing import List, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from garmindb.data.repositories.base import HealthRepository

from .models import (
    StressAnalysisResult,
    StressLoadMetric,
    HourlyStressPattern,
    PostActivityStressPattern,
    Insight,
)


class StressAnalyzer:
    """Analyzes stress patterns, load, and recovery efficiency.

    The analyzer computes:
    - Stress Load: Cumulative stress as area under the curve (AUC)
    - Personal Baseline: 25th percentile of resting stress (00:00-06:00)
    - Hourly Patterns: Average stress by hour of day
    - Weekday Patterns: Average stress by day of week
    - Post-Activity Recovery: Time to return to baseline after activities

    Attributes:
        BASELINE_DAYS: Days to use for baseline calculation
        BASELINE_PERCENTILE: Percentile for baseline (robust to outliers)
        BASELINE_HOURS: Hour range for resting baseline (0-6 = night)
        RECOVERY_WINDOW_HOURS: Post-activity monitoring window
        RECOVERY_THRESHOLD_BUFFER: Buffer above baseline for recovery target
        GAP_CAP_MINUTES: Max interpolation gap for stress load
    """

    # Baseline configuration
    BASELINE_DAYS = 14
    BASELINE_PERCENTILE = 25
    BASELINE_HOURS = (0, 6)  # 00:00-06:00 for resting baseline

    # Recovery configuration
    RECOVERY_WINDOW_HOURS = 2
    RECOVERY_THRESHOLD_BUFFER = 5  # baseline + 5

    # Stress load configuration
    GAP_CAP_MINUTES = 15  # Max interpolation gap

    # Stress category thresholds (Garmin scale)
    STRESS_LOW_MAX = 25
    STRESS_MEDIUM_MAX = 50
    STRESS_HIGH_MAX = 75

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
    ) -> StressAnalysisResult:
        """Analyze stress patterns for a period.

        Fetches stress data and activities, then computes:
        - Distribution (low/medium/high percentages)
        - Stress Load (AUC-based cumulative metric)
        - Hourly and weekday patterns
        - Post-activity recovery patterns
        - Recovery efficiency score

        Args:
            start_date: Start of analysis period (inclusive)
            end_date: End of analysis period (inclusive)

        Returns:
            StressAnalysisResult with metrics, patterns, and insights
        """
        from datetime import time, timedelta
        from .models import MetricSummary, TrendDirection

        # Fetch data with lookback buffer for baseline calculation
        lookback_start = start_date - timedelta(days=self.BASELINE_DAYS)
        stress_records = self._repository.get_stress_data(
            lookback_start, end_date
        )
        activities = self._repository.get_activities(start_date, end_date)

        # Filter to analysis period for most calculations
        period_records = [
            r for r in stress_records
            if start_date <= r.timestamp.date() <= end_date
        ]

        # Calculate personal baseline (uses full lookback period)
        personal_baseline = self._calculate_personal_baseline(
            stress_records, end_date
        )

        # Filter valid stress values for distribution/average
        valid_values = [
            r.stress_level for r in period_records
            if r.stress_level is not None and r.stress_level > 0
        ]

        # Calculate distribution percentages
        if valid_values:
            low_count = sum(
                1 for v in valid_values if v <= self.STRESS_LOW_MAX
            )
            med_count = sum(
                1 for v in valid_values
                if self.STRESS_LOW_MAX < v <= self.STRESS_MEDIUM_MAX
            )
            high_count = sum(
                1 for v in valid_values if v > self.STRESS_MEDIUM_MAX
            )
            total = len(valid_values)
            low_pct = round(low_count / total * 100, 1)
            med_pct = round(med_count / total * 100, 1)
            high_pct = round(high_count / total * 100, 1)
            avg_stress = sum(valid_values) / len(valid_values)
        else:
            low_pct = med_pct = high_pct = 0.0
            avg_stress = 0.0

        # Calculate 7-day and 30-day averages for trend
        recent_7d = [
            r.stress_level for r in period_records
            if r.stress_level is not None
            and r.stress_level > 0
            and r.timestamp.date() > end_date - timedelta(days=7)
        ]
        recent_30d = [
            r.stress_level for r in period_records
            if r.stress_level is not None
            and r.stress_level > 0
            and r.timestamp.date() > end_date - timedelta(days=30)
        ]
        avg_7d = sum(recent_7d) / len(recent_7d) if recent_7d else None
        avg_30d = sum(recent_30d) / len(recent_30d) if recent_30d else None

        # Determine trend
        trend = TrendDirection.STABLE
        if avg_7d is not None and avg_30d is not None:
            diff = avg_7d - avg_30d
            if diff > 3:
                trend = TrendDirection.DECLINING  # Higher stress is declining
            elif diff < -3:
                trend = TrendDirection.IMPROVING

        # Create avg_stress MetricSummary
        avg_stress_summary = MetricSummary(
            name="Average Stress",
            current_value=round(avg_stress, 1),
            unit="",
            average_7d=round(avg_7d, 1) if avg_7d else None,
            average_30d=round(avg_30d, 1) if avg_30d else None,
            min_value=min(valid_values) if valid_values else None,
            max_value=max(valid_values) if valid_values else None,
            trend=trend,
        )

        # Calculate stress load for period
        start_dt = datetime.combine(start_date, time.min)
        end_dt = datetime.combine(end_date, time.max)
        stress_load = self._calculate_stress_load(
            period_records, start_dt, end_dt
        )

        # Calculate patterns
        hourly_patterns = self._calculate_hourly_patterns(period_records)
        weekday_avg = self._calculate_weekday_averages(period_records)

        # Find peak and lowest stress times from hourly patterns
        active_patterns = [p for p in hourly_patterns if p.sample_count > 0]
        peak_stress_time = None
        lowest_stress_time = None
        if active_patterns:
            peak_pattern = max(active_patterns, key=lambda p: p.avg_stress)
            lowest_pattern = min(active_patterns, key=lambda p: p.avg_stress)
            peak_stress_time = time(hour=peak_pattern.hour)
            lowest_stress_time = time(hour=lowest_pattern.hour)

        # Analyze post-activity recovery
        post_activity_patterns = self._analyze_post_activity_recovery(
            activities, stress_records, personal_baseline
        )
        recovery_efficiency = self._calculate_recovery_efficiency(
            post_activity_patterns
        )

        # Calculate average recovery time
        recovery_times = [
            p.recovery_time_minutes for p in post_activity_patterns
            if p.recovery_time_minutes is not None
        ]
        avg_recovery_time = (
            sum(recovery_times) / len(recovery_times)
            if recovery_times else None
        )

        # Calculate daily averages for charts
        daily_avg: Dict[date, float] = {}
        for d in range((end_date - start_date).days + 1):
            current_date = start_date + timedelta(days=d)
            day_values = [
                r.stress_level for r in period_records
                if r.stress_level is not None
                and r.stress_level > 0
                and r.timestamp.date() == current_date
            ]
            if day_values:
                daily_avg[current_date] = round(
                    sum(day_values) / len(day_values), 1
                )

        # Build result
        result = StressAnalysisResult(
            period_start=start_date,
            period_end=end_date,
            avg_stress=avg_stress_summary,
            low_stress_percent=low_pct,
            medium_stress_percent=med_pct,
            high_stress_percent=high_pct,
            peak_stress_time=peak_stress_time,
            lowest_stress_time=lowest_stress_time,
            insights=[],  # Will be populated by _generate_insights
            daily_avg_stress=daily_avg,
            stress_load=stress_load,
            hourly_patterns=hourly_patterns,
            weekday_avg=weekday_avg,
            post_activity_patterns=post_activity_patterns,
            avg_recovery_time_minutes=avg_recovery_time,
            recovery_efficiency=recovery_efficiency,
            personal_baseline=personal_baseline,
        )

        # Generate insights
        result.insights.extend(self._generate_insights(result))

        return result

    def _calculate_stress_load(
        self,
        stress_records: List,
        start_dt: datetime,
        end_dt: datetime
    ) -> StressLoadMetric:
        """Calculate stress load as area under the curve.

        Stress Load = sum(stress_level * duration_minutes) / 60

        Single pass O(n) algorithm that:
        - Caps gaps at GAP_CAP_MINUTES to avoid inflating load
        - Filters out invalid readings (stress <= 0)
        - Tracks peak load hour

        Args:
            stress_records: List of StressRecord DTOs
            start_dt: Start datetime for calculation
            end_dt: End datetime for calculation

        Returns:
            StressLoadMetric with total load, avg intensity, peak hour
        """
        from datetime import time

        # Filter valid records in time range
        valid_records = [
            r for r in stress_records
            if r.stress_level is not None
            and r.stress_level > 0
            and start_dt <= r.timestamp <= end_dt
        ]

        if not valid_records:
            return StressLoadMetric(
                period_minutes=0,
                total_load=0.0,
                avg_intensity=0.0,
                peak_load_hour=None
            )

        # Sort by timestamp
        valid_records.sort(key=lambda r: r.timestamp)

        total_load = 0.0
        total_weighted_stress = 0.0
        total_minutes = 0.0
        hourly_load: Dict[int, float] = {}

        for i, record in enumerate(valid_records):
            # Calculate duration to next record (or use 1 minute for last)
            if i < len(valid_records) - 1:
                next_ts = valid_records[i + 1].timestamp
                duration = (next_ts - record.timestamp).total_seconds() / 60.0
                # Cap gaps at GAP_CAP_MINUTES
                duration = min(duration, self.GAP_CAP_MINUTES)
            else:
                duration = 1.0  # Last record: assume 1 minute

            # Accumulate load
            stress_contribution = record.stress_level * duration
            total_load += stress_contribution
            total_weighted_stress += stress_contribution
            total_minutes += duration

            # Track hourly load
            hour = record.timestamp.hour
            load = hourly_load.get(hour, 0.0) + stress_contribution
            hourly_load[hour] = load

        # Normalize load to "stress points" (divide by 60)
        total_load = total_load / 60.0

        # Calculate average intensity
        avg_intensity = (
            total_weighted_stress / total_minutes
            if total_minutes > 0 else 0.0
        )

        # Find peak load hour
        peak_hour = None
        if hourly_load:
            peak_hour_int = max(hourly_load, key=hourly_load.get)
            peak_hour = time(hour=peak_hour_int)

        return StressLoadMetric(
            period_minutes=int(total_minutes),
            total_load=round(total_load, 1),
            avg_intensity=round(avg_intensity, 1),
            peak_load_hour=peak_hour
        )

    def _calculate_personal_baseline(
        self,
        stress_records: List,
        end_date: date
    ) -> float:
        """Calculate personal stress baseline.

        Uses 25th percentile of resting stress (00:00-06:00) over
        BASELINE_DAYS. More robust than mean - not skewed by outliers.

        Args:
            stress_records: List of StressRecord DTOs
            end_date: End date for baseline period

        Returns:
            Personal baseline stress level (default 25.0 if insufficient data)
        """
        from datetime import timedelta

        # Calculate baseline period
        baseline_start = end_date - timedelta(days=self.BASELINE_DAYS)

        # Filter to resting hours (00:00-06:00) in baseline period
        start_hour, end_hour = self.BASELINE_HOURS
        resting_values = [
            r.stress_level for r in stress_records
            if r.stress_level is not None
            and r.stress_level > 0
            and baseline_start <= r.timestamp.date() <= end_date
            and start_hour <= r.timestamp.hour < end_hour
        ]

        if len(resting_values) < 10:  # Need minimum data
            return 25.0  # Default baseline

        # Calculate 25th percentile
        resting_values.sort()
        idx = int(len(resting_values) * self.BASELINE_PERCENTILE / 100)
        idx = max(0, min(idx, len(resting_values) - 1))

        return float(resting_values[idx])

    def _calculate_hourly_patterns(
        self,
        stress_records: List
    ) -> List[HourlyStressPattern]:
        """Calculate average stress by hour of day.

        Groups stress readings by hour and computes:
        - Average stress per hour
        - Sample count
        - Category distribution (low/medium/high percentages)

        Args:
            stress_records: List of StressRecord DTOs

        Returns:
            List of HourlyStressPattern for hours 0-23
        """
        # Initialize hourly buckets
        hourly_data: Dict[int, List[int]] = {h: [] for h in range(24)}

        # Group valid records by hour
        for record in stress_records:
            if record.stress_level is not None and record.stress_level > 0:
                hour = record.timestamp.hour
                hourly_data[hour].append(record.stress_level)

        patterns = []
        for hour in range(24):
            values = hourly_data[hour]
            if not values:
                patterns.append(HourlyStressPattern(
                    hour=hour,
                    avg_stress=0.0,
                    sample_count=0,
                    category_distribution={}
                ))
                continue

            # Calculate average
            avg_stress = sum(values) / len(values)

            # Calculate category distribution
            low_count = sum(1 for v in values if v <= self.STRESS_LOW_MAX)
            med_count = sum(
                1 for v in values
                if self.STRESS_LOW_MAX < v <= self.STRESS_MEDIUM_MAX
            )
            high_count = sum(1 for v in values if v > self.STRESS_MEDIUM_MAX)
            total = len(values)

            category_dist = {
                "low": round(low_count / total * 100, 1),
                "medium": round(med_count / total * 100, 1),
                "high": round(high_count / total * 100, 1),
            }

            patterns.append(HourlyStressPattern(
                hour=hour,
                avg_stress=round(avg_stress, 1),
                sample_count=len(values),
                category_distribution=category_dist
            ))

        return patterns

    def _calculate_weekday_averages(
        self,
        stress_records: List
    ) -> Dict[str, float]:
        """Calculate average stress by day of week.

        Args:
            stress_records: List of StressRecord DTOs

        Returns:
            Dict mapping weekday name to average stress
        """
        weekday_names = [
            "Monday", "Tuesday", "Wednesday", "Thursday",
            "Friday", "Saturday", "Sunday"
        ]
        weekday_data: Dict[int, List[int]] = {i: [] for i in range(7)}

        # Group valid records by weekday
        for record in stress_records:
            if record.stress_level is not None and record.stress_level > 0:
                weekday = record.timestamp.weekday()
                weekday_data[weekday].append(record.stress_level)

        # Calculate averages
        result = {}
        for i, name in enumerate(weekday_names):
            values = weekday_data[i]
            if values:
                result[name] = round(sum(values) / len(values), 1)
            else:
                result[name] = 0.0

        return result

    def _analyze_post_activity_recovery(
        self,
        activities: List,
        stress_records: List,
        baseline: float
    ) -> List[PostActivityStressPattern]:
        """Analyze stress recovery after activities.

        For each activity, analyzes stress in RECOVERY_WINDOW_HOURS window:
        - Pre-activity stress (30min before)
        - Peak post-activity stress
        - Stress load in recovery window
        - Time to return to baseline + RECOVERY_THRESHOLD_BUFFER

        Args:
            activities: List of activity DTOs with end times
            stress_records: List of StressRecord DTOs
            baseline: Personal stress baseline

        Returns:
            List of PostActivityStressPattern for each activity
        """
        from datetime import timedelta

        if not activities or not stress_records:
            return []

        # Sort stress records by timestamp for efficient lookup
        sorted_stress = sorted(stress_records, key=lambda r: r.timestamp)
        recovery_target = baseline + self.RECOVERY_THRESHOLD_BUFFER

        patterns = []
        for activity in activities:
            # Calculate activity end time
            has_start = hasattr(activity, 'start_time')
            has_duration = hasattr(activity, 'duration')
            if not has_start or not has_duration:
                continue
            if activity.start_time is None or activity.duration is None:
                continue

            end_time = activity.start_time + activity.duration

            # Define time windows
            pre_start = end_time - timedelta(minutes=30)
            post_end = end_time + timedelta(hours=self.RECOVERY_WINDOW_HOURS)

            # Get pre-activity stress (30min before)
            pre_stress_values = [
                r.stress_level for r in sorted_stress
                if r.stress_level is not None
                and r.stress_level > 0
                and pre_start <= r.timestamp < end_time
            ]
            pre_activity_stress = (
                sum(pre_stress_values) / len(pre_stress_values)
                if pre_stress_values else baseline
            )

            # Get post-activity stress records
            post_records = [
                r for r in sorted_stress
                if r.stress_level is not None
                and r.stress_level > 0
                and end_time <= r.timestamp <= post_end
            ]

            if not post_records:
                continue  # No data to analyze

            # Find peak post-activity stress
            peak_post_stress = max(r.stress_level for r in post_records)

            # Calculate stress load in recovery window
            recovery_load = self._calculate_stress_load(
                post_records,
                end_time,
                post_end
            )

            # Find time to recovery (when stress <= baseline + 5)
            recovery_time = None
            for record in post_records:
                if record.stress_level <= recovery_target:
                    delta = record.timestamp - end_time
                    recovery_time = int(delta.total_seconds() / 60)
                    break

            # Get activity info
            activity_id = str(getattr(activity, 'activity_id', 'unknown'))
            sport = getattr(activity, 'sport', 'unknown')
            if hasattr(sport, 'name'):
                sport = sport.name

            patterns.append(PostActivityStressPattern(
                activity_id=activity_id,
                activity_sport=str(sport),
                activity_end_time=end_time,
                pre_activity_stress=round(pre_activity_stress, 1),
                peak_post_stress=float(peak_post_stress),
                stress_load_2h=recovery_load.total_load,
                recovery_time_minutes=recovery_time
            ))

        return patterns

    def _calculate_recovery_efficiency(
        self,
        patterns: List[PostActivityStressPattern]
    ) -> Optional[float]:
        """Calculate recovery efficiency score.

        Efficiency = 100 - (avg_recovery_time / 120) * 100

        Activities with no recovery (None) count as 120 min (worst case).
        Score 0-100 where 100 = immediate recovery.

        Args:
            patterns: List of PostActivityStressPattern

        Returns:
            Recovery efficiency score (0-100), or None if no activities
        """
        if not patterns:
            return None

        # Calculate average recovery time (None = 120 min worst case)
        max_recovery = self.RECOVERY_WINDOW_HOURS * 60  # 120 minutes
        recovery_times = [
            p.recovery_time_minutes if p.recovery_time_minutes is not None
            else max_recovery
            for p in patterns
        ]

        avg_recovery = sum(recovery_times) / len(recovery_times)

        # Efficiency = 100 - (avg_time / 120) * 100
        efficiency = 100 - (avg_recovery / max_recovery) * 100
        return round(max(0, min(100, efficiency)), 1)

    def _generate_insights(
        self,
        result: StressAnalysisResult
    ) -> List[Insight]:
        """Generate actionable insights from analysis.

        Insight conditions:
        - stress_load.total_load > 500/day: "High Cumulative Stress" (WARNING)
        - recovery_efficiency < 50: "Poor Stress Recovery" (WARNING)
        - recovery_efficiency >= 80: "Excellent Resilience" (POSITIVE)
        - weekday_avg[workdays] > weekend * 1.45: "Occupational Stress" (INFO)
        - peak_stress_time in 09:00-17:00: "Work Hours Stress Peak" (INFO)
        - avg_recovery_time > 90: "Slow Autonomic Recovery" (WARNING)
        - Any activity with recovery_time = None: "Incomplete Recovery" (ALERT)

        Args:
            result: Partially populated StressAnalysisResult

        Returns:
            List of Insight objects
        """
        from .models import InsightSeverity

        insights = []
        days_in_period = (result.period_end - result.period_start).days + 1

        # High Cumulative Stress (> 500 stress points per day average)
        if result.stress_load and result.stress_load.total_load > 0:
            daily_avg_load = result.stress_load.total_load / days_in_period
            if daily_avg_load > 500:
                insights.append(Insight(
                    title="High Cumulative Stress",
                    description=(
                        f"Average daily stress load of {daily_avg_load:.0f} "
                        "points is elevated."
                    ),
                    severity=InsightSeverity.WARNING,
                    category="stress",
                    data_points={"daily_avg_load": daily_avg_load},
                    recommendations=[
                        "Schedule regular breaks during high-stress hours",
                        "Practice breathing exercises",
                        "Consider reducing commitments if possible"
                    ]
                ))

        # Recovery Efficiency insights
        if result.recovery_efficiency is not None:
            eff = result.recovery_efficiency
            if eff < 50:
                insights.append(Insight(
                    title="Poor Stress Recovery",
                    description=f"Recovery efficiency of {eff:.0f}% is low.",
                    severity=InsightSeverity.WARNING,
                    category="stress",
                    data_points={"efficiency": eff},
                    recommendations=[
                        "Ensure adequate sleep before activities",
                        "Consider reducing training intensity",
                        "Allow more rest between sessions"
                    ]
                ))
            elif eff >= 80:
                insights.append(Insight(
                    title="Excellent Stress Resilience",
                    description=f"Recovery efficiency: {eff:.0f}%.",
                    severity=InsightSeverity.POSITIVE,
                    category="stress",
                    data_points={"efficiency": eff},
                    recommendations=[]
                ))

        # Occupational Stress Detection
        if result.weekday_avg:
            workday_names = [
                "Monday", "Tuesday", "Wednesday", "Thursday", "Friday"
            ]
            weekend_names = ["Saturday", "Sunday"]
            workday_vals = [
                result.weekday_avg.get(d, 0) for d in workday_names
                if result.weekday_avg.get(d, 0) > 0
            ]
            weekend_vals = [
                result.weekday_avg.get(d, 0) for d in weekend_names
                if result.weekday_avg.get(d, 0) > 0
            ]
            if workday_vals and weekend_vals:
                workday_avg = sum(workday_vals) / len(workday_vals)
                weekend_avg = sum(weekend_vals) / len(weekend_vals)
                if weekend_avg > 0 and workday_avg > weekend_avg * 1.45:
                    desc = (
                        f"Weekday stress ({workday_avg:.0f}) > "
                        f"weekend ({weekend_avg:.0f})."
                    )
                    insights.append(Insight(
                        title="Occupational Stress Detected",
                        description=desc,
                        severity=InsightSeverity.INFO,
                        category="stress",
                        data_points={
                            "workday_avg": workday_avg,
                            "weekend_avg": weekend_avg
                        },
                        recommendations=[
                            "Review work-life balance",
                            "Take micro-breaks during work hours"
                        ]
                    ))

        # Work Hours Stress Peak
        if result.peak_stress_time:
            peak_hour = result.peak_stress_time.hour
            if 9 <= peak_hour <= 17:
                peak_time_str = result.peak_stress_time.strftime('%H:%M')
                insights.append(Insight(
                    title="Work Hours Stress Peak",
                    description=f"Peak stress at {peak_time_str}.",
                    severity=InsightSeverity.INFO,
                    category="stress",
                    data_points={"peak_hour": peak_hour},
                    recommendations=[
                        "Schedule demanding tasks during lower-stress periods",
                        "Take a walk during peak stress hours"
                    ]
                ))

        # Slow Autonomic Recovery
        avg_rec = result.avg_recovery_time_minutes
        if avg_rec is not None and avg_rec > 90:
            insights.append(Insight(
                title="Slow Autonomic Recovery",
                description=f"Average recovery time: {avg_rec:.0f} min.",
                severity=InsightSeverity.WARNING,
                category="stress",
                data_points={"avg_recovery_min": avg_rec},
                recommendations=[
                    "Prioritize sleep quality",
                    "Consider recovery-focused activities (yoga, meditation)",
                    "Reduce training load temporarily"
                ]
            ))

        # Incomplete Recovery After Activity
        incomplete = [
            p for p in result.post_activity_patterns
            if p.recovery_time_minutes is None
        ]
        if incomplete:
            sports = list(set(p.activity_sport for p in incomplete))
            count = len(incomplete)
            insights.append(Insight(
                title="Incomplete Post-Activity Recovery",
                description=f"{count} activities without full recovery.",
                severity=InsightSeverity.ALERT,
                category="stress",
                data_points={
                    "count": len(incomplete),
                    "sports": sports
                },
                recommendations=[
                    "Monitor for signs of overtraining",
                    "Ensure adequate nutrition post-activity",
                    "Consider longer cool-down periods"
                ]
            ))

        return insights
