"""Analysis result models.

These dataclasses represent the output of analyzers,
providing structured results that can be rendered by any presenter.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time
from typing import List, Optional, Dict, Any
from enum import Enum


class TrendDirection(Enum):
    """Direction of a metric trend."""
    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"


class InsightSeverity(Enum):
    """Severity level for insights."""
    INFO = "info"
    POSITIVE = "positive"
    WARNING = "warning"
    ALERT = "alert"


@dataclass
class MetricSummary:
    """Summary statistics for a single metric."""

    name: str
    current_value: float
    unit: str
    average_7d: Optional[float] = None
    average_30d: Optional[float] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    trend: TrendDirection = TrendDirection.STABLE
    percent_change: Optional[float] = None

    @property
    def trend_icon(self) -> str:
        """Get icon for trend direction."""
        icons = {
            TrendDirection.IMPROVING: "↑",
            TrendDirection.DECLINING: "↓",
            TrendDirection.STABLE: "→",
        }
        return icons.get(self.trend, "?")


@dataclass
class Insight:
    """An actionable insight derived from analysis."""

    title: str
    description: str
    severity: InsightSeverity
    category: str  # sleep, stress, recovery, activity
    data_points: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

    @property
    def severity_icon(self) -> str:
        """Get icon for severity level."""
        icons = {
            InsightSeverity.INFO: "ℹ️",
            InsightSeverity.POSITIVE: "✅",
            InsightSeverity.WARNING: "⚠️",
            InsightSeverity.ALERT: "🚨",
        }
        return icons.get(self.severity, "")


@dataclass
class StressLoadMetric:
    """Stress load calculated as area under the curve."""

    period_minutes: int
    total_load: float
    avg_intensity: float
    peak_load_hour: Optional[time] = None


@dataclass
class HourlyStressPattern:
    """Stress pattern for a specific hour of day."""

    hour: int
    avg_stress: float
    sample_count: int
    category_distribution: Dict[str, float] = field(default_factory=dict)


@dataclass
class PostActivityStressPattern:
    """Post-activity stress recovery pattern."""

    activity_id: str
    activity_sport: str
    activity_end_time: datetime
    pre_activity_stress: float
    peak_post_stress: float
    stress_load_2h: float
    recovery_time_minutes: Optional[int] = None


@dataclass
class SleepAnalysisResult:
    """Complete sleep analysis result."""

    period_start: date
    period_end: date

    # Summary metrics
    avg_total_sleep: MetricSummary
    avg_deep_sleep: MetricSummary
    avg_rem_sleep: MetricSummary
    sleep_consistency_score: float  # 0-100

    # Patterns
    best_sleep_day: Optional[str] = None  # e.g., "Saturday"
    worst_sleep_day: Optional[str] = None
    optimal_bedtime: Optional[time] = None

    # Generated insights
    insights: List[Insight] = field(default_factory=list)

    # Raw data for charts (date -> value)
    daily_total_hours: Dict[date, float] = field(default_factory=dict)
    daily_deep_percent: Dict[date, float] = field(default_factory=dict)


@dataclass
class StressAnalysisResult:
    """Complete stress analysis result."""

    period_start: date
    period_end: date

    # Summary metrics
    avg_stress: MetricSummary
    low_stress_percent: float
    medium_stress_percent: float
    high_stress_percent: float

    # Patterns
    peak_stress_time: Optional[time] = None
    lowest_stress_time: Optional[time] = None

    # Insights
    insights: List[Insight] = field(default_factory=list)

    # Raw data for charts
    daily_avg_stress: Dict[date, float] = field(default_factory=dict)

    # NEW: Stress Load (AUC-based cumulative metric)
    stress_load: Optional['StressLoadMetric'] = None

    # NEW: Temporal patterns
    hourly_patterns: List['HourlyStressPattern'] = field(default_factory=list)
    weekday_avg: Dict[str, float] = field(default_factory=dict)

    # NEW: Post-activity recovery analysis
    post_activity_patterns: List['PostActivityStressPattern'] = field(
        default_factory=list
    )
    avg_recovery_time_minutes: Optional[float] = None
    recovery_efficiency: Optional[float] = None  # 0-100

    # NEW: Personal baseline (25th percentile of resting stress)
    personal_baseline: float = 25.0


@dataclass
class DailyReadinessResult:
    """Daily recovery and readiness snapshot."""

    analysis_date: date

    # Scores (0-100)
    recovery_score: int
    readiness_score: int

    # Factors
    sleep_factor: float  # 0-1, contribution to recovery
    stress_factor: float
    activity_factor: float

    # Recommendation
    recommended_intensity: str  # "rest", "light", "moderate", "intense"

    # Optional fields
    body_battery_morning: Optional[int] = None

    # Insights
    insights: List[Insight] = field(default_factory=list)


@dataclass
class RecoveryAnalysisResult:
    """Result of recovery analysis for a period.

    Analyzes RHR trends, Body Battery patterns, and training load
    to assess overall recovery status and injury risk.
    """

    period_start: date
    period_end: date

    # Recovery Score (0-100)
    recovery_score: int
    recovery_trend: TrendDirection

    # Component Metrics
    rhr_summary: MetricSummary
    body_battery_summary: MetricSummary
    training_load_summary: MetricSummary

    # Specialized Recovery Metrics
    rhr_baseline: float
    rhr_deviation: float
    weekly_tss: float
    acute_chronic_ratio: Optional[float] = None

    # Insights
    insights: List[Insight] = field(default_factory=list)

    # Summary Statistics
    days_analyzed: int = 0
    high_recovery_days: int = 0
    low_recovery_days: int = 0


@dataclass
class ActivityAnalysisResult:
    """Activity/training analysis result."""

    period_start: date
    period_end: date

    # Counts
    total_activities: int

    # Metrics
    total_duration_hours: float
    total_distance_km: float
    total_calories: int

    # Optional/default fields
    activities_by_sport: Dict[str, int] = field(default_factory=dict)
    avg_training_effect: Optional[float] = None

    # Trends
    weekly_volume_trend: TrendDirection = TrendDirection.STABLE

    # Insights
    insights: List[Insight] = field(default_factory=list)


@dataclass
class HealthReport:
    """Complete health report combining all analyses."""

    generated_at: datetime
    period_start: date
    period_end: date

    # Component analyses (optional, may not all be present)
    sleep: Optional[SleepAnalysisResult] = None
    stress: Optional[StressAnalysisResult] = None
    recovery: Optional[RecoveryAnalysisResult] = None
    activities: Optional[ActivityAnalysisResult] = None

    # Cross-domain insights
    key_insights: List[Insight] = field(default_factory=list)

    # Metadata for LLM context
    metadata: Dict[str, Any] = field(default_factory=dict)
