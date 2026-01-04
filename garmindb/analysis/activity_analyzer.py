"""Activity analysis: training load, intensity distribution, sport summaries.

This module analyzes activity data to provide training load management
(TSB/ATL/CTL), intensity distribution, and performance insights.
"""

from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple, TYPE_CHECKING

if TYPE_CHECKING:
    from garmindb.data.repositories.base import HealthRepository
    from garmindb.data.models import ActivityRecord

from .models import (
    ActivityAnalysisResult,
    TrainingStressMetrics,
    SportSummary,
    Insight,
    InsightSeverity,
    TrendDirection,
)


# Load estimation factors by sport (load per minute)
LOAD_FACTORS: Dict[str, float] = {
    "running": 0.8,
    "cycling": 0.6,
    "walking": 0.3,
    "swimming": 0.9,
    "strength_training": 0.5,
    "hiking": 0.5,
    "yoga": 0.2,
    "default": 0.5,
}

# Intensity categories based on Training Effect
INTENSITY_CATEGORIES: Dict[str, Tuple[float, float]] = {
    "Recovery": (0.0, 1.9),
    "Base": (2.0, 2.9),
    "Improving": (3.0, 3.9),
    "Highly Improving": (4.0, 4.4),
    "Overreaching": (4.5, 5.0),
}


class ActivityAnalyzer:
    """Analyzes activity data for training load and performance insights.

    Provides two-axis analysis:
    - Axis A: Load Management (TSB, Monotony, Strain)
    - Axis B: Quality/Performance (Intensity, Efficiency)

    Uses 42-day lookback buffer for accurate CTL calculation.
    """

    # TSB calculation windows
    ATL_WINDOW = 7   # Acute Training Load (Fatigue)
    CTL_WINDOW = 42  # Chronic Training Load (Fitness)

    # Minimum days for meaningful monotony calculation
    MIN_MONOTONY_DAYS = 7

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
    ) -> ActivityAnalysisResult:
        """Analyze activities for a period.

        Fetches activities with lookback buffer for TSB calculations,
        then computes training load, intensity distribution, and insights.

        Args:
            start_date: Start of analysis period (inclusive)
            end_date: End of analysis period (inclusive)

        Returns:
            ActivityAnalysisResult with metrics and insights
        """
        # Fetch activities with lookback buffer for CTL calculation
        lookback_start = start_date - timedelta(days=self.CTL_WINDOW)
        all_activities = self._repository.get_activities(lookback_start, end_date)

        # Filter to analysis period
        period_activities = [
            a for a in all_activities
            if start_date <= a.start_time.date() <= end_date
        ]

        # Return empty result if no activities
        if not period_activities:
            return self._empty_result(start_date, end_date)

        # Build continuous daily load series (include zeros for rest days)
        daily_loads, confidence_score = self._build_daily_loads(
            all_activities, lookback_start, end_date
        )

        # Calculate TSB metrics
        training_stress = self._calculate_tsb_metrics(
            daily_loads, start_date, end_date, confidence_score
        )

        # Build sport summaries
        sport_summaries = self._build_sport_summaries(period_activities)

        # Calculate intensity distribution
        intensity_dist = self._calculate_intensity_distribution(period_activities)
        avg_aerobic, avg_anaerobic = self._calculate_avg_effects(period_activities)

        # Calculate totals
        total_activities = len(period_activities)
        total_duration = sum(
            a.duration.total_seconds() / 3600 for a in period_activities
        )
        total_distance = sum(
            a.distance or 0 for a in period_activities
        )
        total_calories = sum(
            a.calories or 0 for a in period_activities
        )

        # Calculate weekly volume trend
        volume_trend = self._calculate_volume_trend(daily_loads, end_date)

        # Filter daily_loads to analysis period only
        period_daily_loads = {
            d: load for d, load in daily_loads.items()
            if start_date <= d <= end_date
        }

        # Build result
        result = ActivityAnalysisResult(
            period_start=start_date,
            period_end=end_date,
            total_activities=total_activities,
            total_duration_hours=round(total_duration, 1),
            total_distance_km=round(total_distance, 1),
            total_calories=total_calories,
            training_stress=training_stress,
            daily_load_series=period_daily_loads,
            sport_summaries=sport_summaries,
            avg_aerobic_effect=avg_aerobic,
            avg_anaerobic_effect=avg_anaerobic,
            intensity_distribution=intensity_dist,
            weekly_volume_trend=volume_trend,
        )

        # Generate insights
        result.insights.extend(self._generate_insights(result, daily_loads, end_date))

        return result

    def _empty_result(self, start_date: date, end_date: date) -> ActivityAnalysisResult:
        """Return empty result when no activities found."""
        return ActivityAnalysisResult(
            period_start=start_date,
            period_end=end_date,
            total_activities=0,
            total_duration_hours=0.0,
            total_distance_km=0.0,
            total_calories=0,
        )

    def _estimate_load(
        self,
        activity: 'ActivityRecord'
    ) -> Tuple[float, bool]:
        """Estimate training load for an activity.

        Uses actual training_load if available, otherwise estimates
        based on sport type and duration.

        Args:
            activity: ActivityRecord to estimate load for

        Returns:
            Tuple of (load_value, is_estimated)
        """
        if activity.training_load is not None and activity.training_load > 0:
            return (float(activity.training_load), False)

        # Check for valid duration before estimating
        if activity.duration is None:
            return (0.0, True)

        # Estimate based on sport and duration
        sport_lower = activity.sport.lower() if activity.sport else "default"
        factor = LOAD_FACTORS.get(sport_lower, LOAD_FACTORS["default"])
        duration_min = activity.duration.total_seconds() / 60
        return (duration_min * factor, True)

    def _build_daily_loads(
        self,
        activities: List['ActivityRecord'],
        start_date: date,
        end_date: date
    ) -> Tuple[Dict[date, float], float]:
        """Build continuous daily load series with zeros for rest days.

        Args:
            activities: All activities in the period
            start_date: Start of period (including lookback)
            end_date: End of period

        Returns:
            Tuple of (daily_loads dict, confidence_score)
        """
        # Initialize all days with zero
        daily_loads: Dict[date, float] = {}
        current = start_date
        while current <= end_date:
            daily_loads[current] = 0.0
            current += timedelta(days=1)

        # Track real vs estimated load volume
        total_load = 0.0
        real_load = 0.0

        # Populate with activity loads
        for activity in activities:
            day = activity.start_time.date()
            if day in daily_loads:
                load, is_estimated = self._estimate_load(activity)
                daily_loads[day] += load
                total_load += load
                if not is_estimated:
                    real_load += load

        # Calculate confidence score (based on load volume)
        confidence_score = real_load / total_load if total_load > 0 else 1.0

        return daily_loads, confidence_score

    def _calculate_ema(self, values: List[float], window: int) -> float:
        """Calculate exponential moving average.

        Args:
            values: Ordered list of values (oldest to newest)
            window: EMA window size

        Returns:
            EMA value
        """
        if not values:
            return 0.0

        alpha = 2 / (window + 1)
        ema = values[0]
        for value in values[1:]:
            ema = alpha * value + (1 - alpha) * ema
        return ema

    def _calculate_tsb_metrics(
        self,
        daily_loads: Dict[date, float],
        start_date: date,
        end_date: date,
        confidence_score: float
    ) -> TrainingStressMetrics:
        """Calculate TSB metrics (ATL, CTL, TSB, Monotony, Strain).

        Args:
            daily_loads: Complete daily load series (with lookback)
            start_date: Start of analysis period
            end_date: End of analysis period
            confidence_score: Real vs estimated load ratio

        Returns:
            TrainingStressMetrics with all calculated values
        """
        # Get ordered list of loads up to end_date
        sorted_dates = sorted(d for d in daily_loads.keys() if d <= end_date)
        loads = [daily_loads[d] for d in sorted_dates]

        # Calculate ATL and CTL using EMA
        atl = self._calculate_ema(loads, self.ATL_WINDOW)
        ctl = self._calculate_ema(loads, self.CTL_WINDOW)
        tsb = ctl - atl

        # Calculate monotony and strain for analysis period only
        period_loads = [
            daily_loads[d] for d in sorted_dates
            if start_date <= d <= end_date
        ]

        monotony = self._calculate_monotony(period_loads)
        last_7_loads = period_loads[-7:] if len(period_loads) >= 7 else period_loads
        weekly_load = sum(last_7_loads)
        strain = self._calculate_strain(weekly_load, monotony)

        return TrainingStressMetrics(
            atl=round(atl, 1),
            ctl=round(ctl, 1),
            tsb=round(tsb, 1),
            monotony=round(monotony, 2) if monotony is not None else None,
            strain=round(strain, 0),
            confidence_score=round(confidence_score, 2),
        )

    def _calculate_monotony(self, daily_loads: List[float]) -> Optional[float]:
        """Calculate training monotony (Mean / StdDev).

        Higher monotony = more repetitive training (risk of staleness).
        A value of None indicates insufficient data.
        A very high value (>10) indicates highly monotonous training.

        Args:
            daily_loads: List of daily load values

        Returns:
            Monotony value or None if insufficient data (< 7 days)
        """
        if len(daily_loads) < self.MIN_MONOTONY_DAYS:
            return None

        mean = sum(daily_loads) / len(daily_loads)
        if mean == 0:
            return 0.0

        variance = sum((x - mean) ** 2 for x in daily_loads) / len(daily_loads)
        std_dev = variance ** 0.5

        # When std_dev is zero (all identical loads), monotony is maximal
        # Cap at 10.0 to avoid infinity issues
        if std_dev == 0:
            return 10.0
        return mean / std_dev

    def _calculate_strain(
        self,
        weekly_load: float,
        monotony: Optional[float]
    ) -> float:
        """Calculate training strain (Weekly Load x Monotony).

        Args:
            weekly_load: Sum of daily loads for the week
            monotony: Calculated monotony value

        Returns:
            Strain value (0.0 if monotony is None)
        """
        if monotony is None:
            return 0.0
        return weekly_load * monotony

    def _build_sport_summaries(
        self,
        activities: List['ActivityRecord']
    ) -> Dict[str, SportSummary]:
        """Build per-sport summary statistics.

        Args:
            activities: Activities in the analysis period

        Returns:
            Dict mapping sport name to SportSummary
        """
        # Group activities by sport
        sport_activities: Dict[str, List['ActivityRecord']] = {}
        for activity in activities:
            sport = activity.sport or "Unknown"
            if sport not in sport_activities:
                sport_activities[sport] = []
            sport_activities[sport].append(activity)

        # Build summaries
        summaries: Dict[str, SportSummary] = {}
        for sport, acts in sport_activities.items():
            count = len(acts)
            total_distance = sum(a.distance or 0 for a in acts)
            total_duration = sum(
                a.duration.total_seconds() / 3600
                for a in acts if a.duration is not None
            )

            # Calculate averages
            avg_speed = None
            if total_duration > 0 and total_distance > 0:
                avg_speed = total_distance / total_duration

            hr_values = [a.avg_hr for a in acts if a.avg_hr]
            avg_hr = sum(hr_values) / len(hr_values) if hr_values else None

            te_values = [a.training_effect for a in acts if a.training_effect]
            max_te = max(te_values) if te_values else 0.0

            # Calculate efficiency index (velocity / HR)
            efficiency = None
            if avg_speed and avg_hr and avg_hr > 0:
                efficiency = (avg_speed / avg_hr) * 100

            summaries[sport] = SportSummary(
                name=sport,
                count=count,
                total_distance_km=round(total_distance, 1),
                total_duration_hours=round(total_duration, 1),
                avg_speed_kmh=round(avg_speed, 1) if avg_speed else None,
                avg_hr=round(avg_hr, 0) if avg_hr else None,
                max_training_effect=round(max_te, 1),
                efficiency_index=round(efficiency, 2) if efficiency else None,
            )

        return summaries

    def _categorize_intensity(self, training_effect: float) -> str:
        """Categorize activity intensity based on training effect.

        Args:
            training_effect: Aerobic training effect value (0-5)

        Returns:
            Intensity category name
        """
        for category, (low, high) in INTENSITY_CATEGORIES.items():
            if low <= training_effect <= high:
                return category
        return "Base"  # Default for out-of-range values

    def _calculate_intensity_distribution(
        self,
        activities: List['ActivityRecord']
    ) -> Dict[str, float]:
        """Calculate intensity distribution based on training effect.

        Args:
            activities: Activities in the analysis period

        Returns:
            Dict mapping intensity category to percentage (0-100)
        """
        # Initialize all categories
        distribution: Dict[str, int] = {cat: 0 for cat in INTENSITY_CATEGORIES}

        # Count activities with training effect
        activities_with_te = [a for a in activities if a.training_effect is not None]
        if not activities_with_te:
            return {cat: 0.0 for cat in INTENSITY_CATEGORIES}

        # Categorize each activity
        for activity in activities_with_te:
            category = self._categorize_intensity(activity.training_effect)
            distribution[category] += 1

        # Convert to percentages
        total = len(activities_with_te)
        return {
            cat: round((count / total) * 100, 1)
            for cat, count in distribution.items()
        }

    def _calculate_avg_effects(
        self,
        activities: List['ActivityRecord']
    ) -> Tuple[float, float]:
        """Calculate average aerobic and anaerobic training effects.

        Args:
            activities: Activities in the analysis period

        Returns:
            Tuple of (avg_aerobic_effect, avg_anaerobic_effect)
        """
        aerobic_values = [
            a.training_effect for a in activities
            if a.training_effect is not None
        ]
        anaerobic_values = [
            a.anaerobic_effect for a in activities
            if a.anaerobic_effect is not None
        ]

        avg_aerobic = (
            sum(aerobic_values) / len(aerobic_values)
            if aerobic_values else 0.0
        )
        avg_anaerobic = (
            sum(anaerobic_values) / len(anaerobic_values)
            if anaerobic_values else 0.0
        )

        return round(avg_aerobic, 1), round(avg_anaerobic, 1)

    def _calculate_volume_trend(
        self,
        daily_loads: Dict[date, float],
        end_date: date
    ) -> TrendDirection:
        """Calculate weekly volume trend.

        Compares current week to previous week.

        Args:
            daily_loads: Daily load series
            end_date: End date of analysis period

        Returns:
            TrendDirection (IMPROVING/DECLINING/STABLE)
        """
        # Get current and previous week loads
        current_week_start = end_date - timedelta(days=6)
        prev_week_start = current_week_start - timedelta(days=7)

        current_week = sum(
            daily_loads.get(d, 0)
            for d in (current_week_start + timedelta(days=i) for i in range(7))
        )
        prev_week = sum(
            daily_loads.get(d, 0)
            for d in (prev_week_start + timedelta(days=i) for i in range(7))
        )

        if prev_week == 0:
            return TrendDirection.STABLE

        percent_change = ((current_week - prev_week) / prev_week) * 100

        if percent_change > 10:
            return TrendDirection.IMPROVING
        elif percent_change < -10:
            return TrendDirection.DECLINING
        return TrendDirection.STABLE

    def _generate_insights(
        self,
        result: ActivityAnalysisResult,
        daily_loads: Dict[date, float],
        end_date: date
    ) -> List[Insight]:
        """Generate activity insights based on analysis results.

        Args:
            result: Current analysis result
            daily_loads: Full daily load series (with lookback)
            end_date: End date of analysis period

        Returns:
            List of Insight objects
        """
        insights: List[Insight] = []

        # 1. Consistency insight (volume spike)
        consistency_insight = self._check_consistency(daily_loads, end_date)
        if consistency_insight:
            insights.append(consistency_insight)

        # 2. Intensity balance insight
        balance_insight = self._check_intensity_balance(result.intensity_distribution)
        if balance_insight:
            insights.append(balance_insight)

        # 3. Confidence warning
        if result.training_stress and result.training_stress.confidence_score < 0.7:
            insights.append(Insight(
                title="Limited Training Load Data",
                description=(
                    f"Only {result.training_stress.confidence_score:.0%} of training "
                    f"load data is from actual device measurements. TSB metrics may "
                    f"be less accurate."
                ),
                severity=InsightSeverity.INFO,
                category="activity",
                data_points={
                    "confidence_score": result.training_stress.confidence_score
                },
                recommendations=[
                    "Ensure activities sync properly with Garmin Connect",
                    "Check that training load is enabled on your device",
                ],
            ))

        # 4. TSB form insight
        if result.training_stress:
            tsb = result.training_stress.tsb
            if tsb > 25:
                insights.append(Insight(
                    title="Peak Freshness",
                    description=(
                        f"TSB of {tsb:.0f} indicates you're well-rested. "
                        f"Great time for a key workout or race."
                    ),
                    severity=InsightSeverity.POSITIVE,
                    category="activity",
                    data_points={"tsb": tsb},
                ))
            elif tsb < -30:
                insights.append(Insight(
                    title="High Fatigue Load",
                    description=(
                        f"TSB of {tsb:.0f} indicates significant fatigue. "
                        f"Consider reducing training volume."
                    ),
                    severity=InsightSeverity.WARNING,
                    category="activity",
                    data_points={"tsb": tsb},
                    recommendations=[
                        "Plan a recovery day or easy session",
                        "Prioritize sleep and nutrition",
                    ],
                ))

        return insights

    def _check_consistency(
        self,
        daily_loads: Dict[date, float],
        end_date: date
    ) -> Optional[Insight]:
        """Check for training volume consistency (>20% change).

        Args:
            daily_loads: Daily load series
            end_date: End date of analysis

        Returns:
            Insight if volume spike detected, None otherwise
        """
        current_week_start = end_date - timedelta(days=6)
        prev_week_start = current_week_start - timedelta(days=7)

        current_week_load = sum(
            daily_loads.get(current_week_start + timedelta(days=i), 0)
            for i in range(7)
        )
        prev_week_load = sum(
            daily_loads.get(prev_week_start + timedelta(days=i), 0)
            for i in range(7)
        )

        if prev_week_load == 0:
            return None

        percent_change = abs(current_week_load - prev_week_load) / prev_week_load * 100

        if percent_change > 20:
            increased = current_week_load > prev_week_load
            direction = "increased" if increased else "decreased"
            return Insight(
                title="Training Volume Spike",
                description=(
                    f"Weekly training load {direction} by {percent_change:.0f}%. "
                    f"Rapid changes above 20% increase injury risk."
                ),
                severity=InsightSeverity.WARNING,
                category="activity",
                data_points={
                    "percent_change": percent_change,
                    "current_week_load": current_week_load,
                    "previous_week_load": prev_week_load,
                },
                recommendations=[
                    "Limit weekly load increases to 10% or less",
                    "Include rest days between high-intensity sessions",
                ],
            )
        return None

    def _check_intensity_balance(
        self,
        intensity_distribution: Dict[str, float]
    ) -> Optional[Insight]:
        """Check for intensity imbalance using a polarized training model.

        Criteria:
        - ALERT: High Intensity (Highly Improving + Overreaching) > 30%
        - WARNING: Low Intensity (Recovery + Base) < 50%
        """
        high_intensity_pct = sum(
            intensity_distribution.get(cat, 0)
            for cat in ["Highly Improving", "Overreaching"]
        )
        low_intensity_pct = sum(
            intensity_distribution.get(cat, 0)
            for cat in ["Recovery", "Base"]
        )
        moderate_intensity_pct = intensity_distribution.get("Improving", 0)

        if high_intensity_pct > 30:
            return Insight(
                title="High Intensity Imbalance",
                description=(
                    f"{high_intensity_pct:.0f}% of your training is at maximum intensity. "
                    f"This significantly increases injury and overtraining risk."
                ),
                severity=InsightSeverity.ALERT,
                category="activity",
                data_points={"high_intensity_percent": high_intensity_pct},
                recommendations=[
                    "Reduce the number of anaerobic or threshold sessions",
                    "Replace one hard session with a very easy recovery run",
                    "Monitor HRV and resting HR closely"
                ],
            )
        
        if low_intensity_pct < 50 and (high_intensity_pct + moderate_intensity_pct) > 50:
            return Insight(
                title="Lack of Base Training",
                description=(
                    f"Only {low_intensity_pct:.0f}% of your training is low-intensity. "
                    "You are spending too much time in the 'moderate' zone, which "
                    "can lead to stagnation without building a strong aerobic base."
                ),
                severity=InsightSeverity.WARNING,
                category="activity",
                data_points={"low_intensity_percent": low_intensity_pct},
                recommendations=[
                    "Increase the proportion of easy (Zone 2) sessions",
                    "Focus on consistency over intensity for a few weeks",
                    "Target an 80/20 intensity distribution"
                ],
            )
            
        return None
