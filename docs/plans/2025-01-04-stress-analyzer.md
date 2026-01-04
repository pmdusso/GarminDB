# StressAnalyzer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement StressAnalyzer following the validated design document.

**Architecture:** Repository pattern, dataclass DTOs, MetricSummary/Insight models.

**Tech Stack:** Python 3.12, dataclasses, existing GarminDB infrastructure

---

## Task 1: Add New Data Classes to models.py

**Files:**
- Modify: `garmindb/analysis/models.py`

**Step 1: Add StressLoadMetric dataclass**

Add after the existing `Insight` class:

```python
@dataclass
class StressLoadMetric:
    """Stress load calculated as area under the curve."""
    period_minutes: int
    total_load: float
    avg_intensity: float
    peak_load_hour: Optional[time] = None
```

**Step 2: Add HourlyStressPattern dataclass**

```python
@dataclass
class HourlyStressPattern:
    """Stress pattern for a specific hour of day."""
    hour: int
    avg_stress: float
    sample_count: int
    category_distribution: Dict[str, float] = field(default_factory=dict)
```

**Step 3: Add PostActivityStressPattern dataclass**

```python
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
```

**Step 4: Update StressAnalysisResult with new fields**

Add these fields to the existing StressAnalysisResult:

```python
# After existing fields, add:
stress_load: Optional['StressLoadMetric'] = None
hourly_patterns: List['HourlyStressPattern'] = field(default_factory=list)
weekday_avg: Dict[str, float] = field(default_factory=dict)
post_activity_patterns: List['PostActivityStressPattern'] = field(default_factory=list)
avg_recovery_time_minutes: Optional[float] = None
recovery_efficiency: Optional[float] = None
personal_baseline: float = 25.0
```

**Step 5: Run flake8**

```bash
python -m flake8 garmindb/analysis/models.py --max-line-length=100
```

**Step 6: Commit**

```bash
git add garmindb/analysis/models.py
git commit -m "feat(models): add stress analysis data classes"
```

---

## Task 2: Update Analysis Module Exports

**Files:**
- Modify: `garmindb/analysis/__init__.py`

**Step 1: Add imports for new classes**

```python
from .models import (
    # ... existing imports ...
    StressLoadMetric,
    HourlyStressPattern,
    PostActivityStressPattern,
)
```

**Step 2: Update __all__ list**

Add to __all__:
```python
"StressLoadMetric",
"HourlyStressPattern",
"PostActivityStressPattern",
```

**Step 3: Run flake8 and commit**

```bash
python -m flake8 garmindb/analysis/__init__.py --max-line-length=100
git add garmindb/analysis/__init__.py
git commit -m "feat(analysis): export stress data classes"
```

---

## Task 3: Create StressAnalyzer - Core Structure

**Files:**
- Create: `garmindb/analysis/stress_analyzer.py`

**Step 1: Create file with imports and class skeleton**

```python
"""Stress analysis: patterns, load, and recovery.

Analyzes stress data to identify temporal patterns, calculate
cumulative stress load, and measure post-activity recovery efficiency.
"""

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from typing import Dict, List, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from garmindb.data.repositories.base import HealthRepository
    from garmindb.data.models import StressRecord, ActivityRecord

from .models import (
    StressAnalysisResult,
    StressLoadMetric,
    HourlyStressPattern,
    PostActivityStressPattern,
    MetricSummary,
    Insight,
    InsightSeverity,
    TrendDirection,
)


class StressAnalyzer:
    """Analyzes stress patterns: distribution, load, and recovery."""

    # Configuration
    BASELINE_DAYS = 14
    BASELINE_PERCENTILE = 25
    BASELINE_HOUR_START = 0
    BASELINE_HOUR_END = 6
    RECOVERY_WINDOW_HOURS = 2
    RECOVERY_THRESHOLD_BUFFER = 5
    GAP_CAP_MINUTES = 15

    def __init__(self, repository: 'HealthRepository'):
        """Initialize with health data repository."""
        self._repository = repository
```

**Step 2: Run flake8**

```bash
python -m flake8 garmindb/analysis/stress_analyzer.py --max-line-length=100
```

---

## Task 4: Implement Stress Load Calculation

**Files:**
- Modify: `garmindb/analysis/stress_analyzer.py`

**Step 1: Add _calculate_stress_load method**

```python
def _calculate_stress_load(
    self,
    stress_records: List['StressRecord'],
    start: datetime,
    end: datetime
) -> StressLoadMetric:
    """Calculate stress load as area under the curve.

    Stress Load = Σ(stress_level × duration_minutes) / 60
    Single pass O(n), caps gaps at 15 minutes.
    """
    filtered = [
        r for r in stress_records
        if start <= r.timestamp <= end and r.stress_level > 0
    ]

    if not filtered:
        return StressLoadMetric(
            period_minutes=0,
            total_load=0.0,
            avg_intensity=0.0,
        )

    filtered.sort(key=lambda r: r.timestamp)

    total_load = 0.0
    weighted_sum = 0.0
    total_minutes = 0.0
    hourly_loads: Dict[int, float] = defaultdict(float)

    for i in range(len(filtered) - 1):
        current = filtered[i]
        next_record = filtered[i + 1]

        if current.stress_level <= 0:
            continue

        delta_seconds = (next_record.timestamp - current.timestamp).total_seconds()
        delta_minutes = min(delta_seconds / 60, self.GAP_CAP_MINUTES)

        load = current.stress_level * delta_minutes / 60
        total_load += load
        weighted_sum += current.stress_level * delta_minutes
        total_minutes += delta_minutes
        hourly_loads[current.timestamp.hour] += load

    avg_intensity = weighted_sum / total_minutes if total_minutes > 0 else 0
    peak_hour = max(hourly_loads, key=hourly_loads.get) if hourly_loads else None

    return StressLoadMetric(
        period_minutes=int(total_minutes),
        total_load=round(total_load, 1),
        avg_intensity=round(avg_intensity, 1),
        peak_load_hour=time(peak_hour) if peak_hour is not None else None,
    )
```

**Step 2: Run flake8**

---

## Task 5: Implement Baseline and Pattern Calculations

**Files:**
- Modify: `garmindb/analysis/stress_analyzer.py`

**Step 1: Add _calculate_personal_baseline method**

```python
def _calculate_personal_baseline(
    self,
    stress_records: List['StressRecord'],
    end_date: date
) -> float:
    """Calculate personal stress baseline from resting periods.

    Uses 25th percentile of stress during 00:00-06:00 over 14 days.
    """
    baseline_start = datetime.combine(
        end_date - timedelta(days=self.BASELINE_DAYS),
        time.min
    )

    resting_values = [
        r.stress_level for r in stress_records
        if r.timestamp >= baseline_start
        and self.BASELINE_HOUR_START <= r.timestamp.hour < self.BASELINE_HOUR_END
        and r.stress_level > 0
    ]

    if not resting_values:
        return 25.0

    resting_values.sort()
    idx = min(
        len(resting_values) - 1,
        max(0, len(resting_values) * self.BASELINE_PERCENTILE // 100)
    )
    return float(resting_values[idx])
```

**Step 2: Add _calculate_hourly_patterns method**

```python
def _calculate_hourly_patterns(
    self,
    stress_records: List['StressRecord']
) -> List[HourlyStressPattern]:
    """Calculate average stress for each hour of day."""
    hourly_data: Dict[int, List[int]] = defaultdict(list)

    for record in stress_records:
        if record.stress_level > 0:
            hourly_data[record.timestamp.hour].append(record.stress_level)

    patterns = []
    for hour in range(24):
        values = hourly_data.get(hour, [])
        if values:
            avg = sum(values) / len(values)
            dist = self._calculate_category_dist(values)
        else:
            avg = 0.0
            dist = {}

        patterns.append(HourlyStressPattern(
            hour=hour,
            avg_stress=round(avg, 1),
            sample_count=len(values),
            category_distribution=dist,
        ))

    return patterns
```

**Step 3: Add _calculate_weekday_patterns method**

```python
def _calculate_weekday_patterns(
    self,
    stress_records: List['StressRecord']
) -> Dict[str, float]:
    """Calculate average stress by day of week."""
    weekday_data: Dict[str, List[int]] = defaultdict(list)
    weekdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday',
                'Friday', 'Saturday', 'Sunday']

    for record in stress_records:
        if record.stress_level > 0:
            day_name = weekdays[record.timestamp.weekday()]
            weekday_data[day_name].append(record.stress_level)

    return {
        day: round(sum(values) / len(values), 1) if values else 0.0
        for day, values in weekday_data.items()
    }
```

**Step 4: Add helper _calculate_category_dist**

```python
def _calculate_category_dist(self, values: List[int]) -> Dict[str, float]:
    """Calculate distribution across stress categories."""
    if not values:
        return {}

    total = len(values)
    low = sum(1 for v in values if v <= 25) / total
    medium = sum(1 for v in values if 26 <= v <= 50) / total
    high = sum(1 for v in values if 51 <= v <= 75) / total
    very_high = sum(1 for v in values if v > 75) / total

    return {
        'low': round(low * 100, 1),
        'medium': round(medium * 100, 1),
        'high': round(high * 100, 1),
        'very_high': round(very_high * 100, 1),
    }
```

**Step 5: Run flake8**

---

## Task 6: Implement Post-Activity Recovery Analysis

**Files:**
- Modify: `garmindb/analysis/stress_analyzer.py`

**Step 1: Add _analyze_post_activity_recovery method**

```python
def _analyze_post_activity_recovery(
    self,
    activity: 'ActivityRecord',
    stress_records: List['StressRecord'],
    baseline: float
) -> PostActivityStressPattern:
    """Analyze stress recovery in 2h window after activity."""
    activity_end = activity.start_time + activity.duration
    window_end = activity_end + timedelta(hours=self.RECOVERY_WINDOW_HOURS)
    pre_start = activity.start_time - timedelta(minutes=30)

    # Pre-activity stress (30min before)
    pre_stress = [
        r.stress_level for r in stress_records
        if pre_start <= r.timestamp < activity.start_time
        and r.stress_level > 0
    ]
    pre_avg = sum(pre_stress) / len(pre_stress) if pre_stress else baseline

    # Post-activity stress (2h after)
    post_stress = [
        r for r in stress_records
        if activity_end <= r.timestamp <= window_end
        and r.stress_level > 0
    ]

    if not post_stress:
        return PostActivityStressPattern(
            activity_id=activity.activity_id,
            activity_sport=activity.sport,
            activity_end_time=activity_end,
            pre_activity_stress=round(pre_avg, 1),
            peak_post_stress=0.0,
            stress_load_2h=0.0,
        )

    peak_post = max(r.stress_level for r in post_stress)
    recovery_target = baseline + self.RECOVERY_THRESHOLD_BUFFER

    # Find recovery time
    recovery_time = None
    for record in sorted(post_stress, key=lambda r: r.timestamp):
        if record.stress_level <= recovery_target:
            delta = record.timestamp - activity_end
            recovery_time = int(delta.total_seconds() / 60)
            break

    # Calculate stress load in 2h window
    load_2h = self._calculate_stress_load(
        stress_records, activity_end, window_end
    ).total_load

    return PostActivityStressPattern(
        activity_id=activity.activity_id,
        activity_sport=activity.sport,
        activity_end_time=activity_end,
        pre_activity_stress=round(pre_avg, 1),
        peak_post_stress=float(peak_post),
        stress_load_2h=load_2h,
        recovery_time_minutes=recovery_time,
    )
```

**Step 2: Add _calculate_recovery_efficiency method**

```python
def _calculate_recovery_efficiency(
    self,
    patterns: List[PostActivityStressPattern]
) -> Optional[float]:
    """Calculate overall recovery efficiency score (0-100).

    Efficiency = 100 - (avg_recovery_time / 120) * 100
    Activities with no recovery count as 120 min (worst case).
    """
    if not patterns:
        return None

    recovery_times = []
    for p in patterns:
        if p.recovery_time_minutes is not None:
            recovery_times.append(p.recovery_time_minutes)
        else:
            recovery_times.append(120)  # Worst case

    avg_recovery = sum(recovery_times) / len(recovery_times)
    efficiency = max(0, 100 - (avg_recovery / 120) * 100)

    return round(efficiency, 1)
```

**Step 3: Run flake8**

---

## Task 7: Implement Main analyze() Method

**Files:**
- Modify: `garmindb/analysis/stress_analyzer.py`

**Step 1: Add analyze method**

```python
def analyze(
    self,
    start_date: date,
    end_date: date
) -> StressAnalysisResult:
    """Analyze stress for a period.

    Returns comprehensive stress analysis including load,
    patterns, and post-activity recovery metrics.
    """
    # Fetch data with lookback for baseline
    data_start = start_date - timedelta(days=self.BASELINE_DAYS)

    stress_data = self._repository.get_stress_data(data_start, end_date)
    activities = self._repository.get_activities(start_date, end_date)

    # Filter to analysis period
    period_stress = [
        r for r in stress_data
        if start_date <= r.timestamp.date() <= end_date
    ]

    # Calculate baseline from full lookback
    baseline = self._calculate_personal_baseline(stress_data, end_date)

    # Calculate stress load
    stress_load = self._calculate_stress_load(
        period_stress,
        datetime.combine(start_date, time.min),
        datetime.combine(end_date, time.max)
    )

    # Calculate patterns
    hourly = self._calculate_hourly_patterns(period_stress)
    weekday = self._calculate_weekday_patterns(period_stress)

    # Analyze post-activity recovery
    post_activity = [
        self._analyze_post_activity_recovery(act, stress_data, baseline)
        for act in activities
    ]

    # Calculate distribution
    all_values = [r.stress_level for r in period_stress if r.stress_level > 0]
    category_dist = self._calculate_category_dist(all_values)

    # Calculate daily averages
    daily_avg = self._calculate_daily_averages(period_stress)

    # Calculate summary metrics
    avg_recovery = self._calculate_avg_recovery_time(post_activity)
    efficiency = self._calculate_recovery_efficiency(post_activity)

    # Build avg_stress MetricSummary
    avg_stress_value = sum(all_values) / len(all_values) if all_values else 0
    avg_stress = MetricSummary(
        name="Average Stress",
        current_value=round(avg_stress_value, 1),
        unit="",
        trend=TrendDirection.STABLE,
    )

    # Find peak and lowest times
    peak_time = self._find_peak_stress_time(hourly)
    lowest_time = self._find_lowest_stress_time(hourly)

    # Build result
    result = StressAnalysisResult(
        period_start=start_date,
        period_end=end_date,
        avg_stress=avg_stress,
        low_stress_percent=category_dist.get('low', 0),
        medium_stress_percent=category_dist.get('medium', 0),
        high_stress_percent=category_dist.get('high', 0) + category_dist.get('very_high', 0),
        peak_stress_time=peak_time,
        lowest_stress_time=lowest_time,
        daily_avg_stress=daily_avg,
        stress_load=stress_load,
        hourly_patterns=hourly,
        weekday_avg=weekday,
        post_activity_patterns=post_activity,
        avg_recovery_time_minutes=avg_recovery,
        recovery_efficiency=efficiency,
        personal_baseline=baseline,
    )

    # Generate insights
    result.insights = self._generate_insights(result)

    return result
```

**Step 2: Add helper methods**

```python
def _calculate_daily_averages(
    self,
    stress_records: List['StressRecord']
) -> Dict[date, float]:
    """Calculate daily stress averages."""
    daily_data: Dict[date, List[int]] = defaultdict(list)

    for record in stress_records:
        if record.stress_level > 0:
            daily_data[record.timestamp.date()].append(record.stress_level)

    return {
        day: round(sum(values) / len(values), 1)
        for day, values in daily_data.items()
    }

def _calculate_avg_recovery_time(
    self,
    patterns: List[PostActivityStressPattern]
) -> Optional[float]:
    """Calculate average recovery time across activities."""
    times = [p.recovery_time_minutes for p in patterns if p.recovery_time_minutes]
    return round(sum(times) / len(times), 1) if times else None

def _find_peak_stress_time(
    self,
    hourly: List[HourlyStressPattern]
) -> Optional[time]:
    """Find hour with highest average stress."""
    if not hourly:
        return None
    peak = max(hourly, key=lambda h: h.avg_stress)
    return time(peak.hour) if peak.avg_stress > 0 else None

def _find_lowest_stress_time(
    self,
    hourly: List[HourlyStressPattern]
) -> Optional[time]:
    """Find hour with lowest average stress."""
    valid = [h for h in hourly if h.sample_count > 0]
    if not valid:
        return None
    lowest = min(valid, key=lambda h: h.avg_stress)
    return time(lowest.hour)
```

**Step 3: Run flake8**

---

## Task 8: Implement Insights Generation

**Files:**
- Modify: `garmindb/analysis/stress_analyzer.py`

**Step 1: Add _generate_insights method**

```python
def _generate_insights(
    self,
    result: StressAnalysisResult
) -> List[Insight]:
    """Generate stress insights based on analysis."""
    insights = []

    # High cumulative stress
    if result.stress_load and result.stress_load.total_load > 500:
        insights.append(Insight(
            title="High Cumulative Stress",
            description=(
                f"Your stress load of {result.stress_load.total_load:.0f} points "
                "indicates sustained elevated stress levels."
            ),
            severity=InsightSeverity.WARNING,
            category="stress",
            data_points={"stress_load": result.stress_load.total_load},
            recommendations=[
                "Incorporate relaxation techniques",
                "Review workload and commitments",
                "Prioritize recovery activities",
            ],
        ))

    # Recovery efficiency
    if result.recovery_efficiency is not None:
        if result.recovery_efficiency < 50:
            insights.append(Insight(
                title="Poor Stress Recovery",
                description=(
                    f"Recovery efficiency of {result.recovery_efficiency:.0f}% "
                    "suggests your body is struggling to normalize after activities."
                ),
                severity=InsightSeverity.WARNING,
                category="stress",
                data_points={"recovery_efficiency": result.recovery_efficiency},
                recommendations=[
                    "Reduce training intensity temporarily",
                    "Focus on sleep quality",
                    "Consider active recovery sessions",
                ],
            ))
        elif result.recovery_efficiency >= 80:
            insights.append(Insight(
                title="Excellent Stress Resilience",
                description=(
                    f"Recovery efficiency of {result.recovery_efficiency:.0f}% "
                    "indicates strong autonomic nervous system recovery."
                ),
                severity=InsightSeverity.POSITIVE,
                category="stress",
            ))

    # Occupational stress detection
    if result.weekday_avg:
        workdays = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday']
        weekend = ['Saturday', 'Sunday']

        workday_avg = sum(
            result.weekday_avg.get(d, 0) for d in workdays
        ) / len(workdays)
        weekend_avg = sum(
            result.weekday_avg.get(d, 0) for d in weekend
        ) / len(weekend)

        if weekend_avg > 0 and workday_avg > weekend_avg * 1.45:
            insights.append(Insight(
                title="Occupational Stress Pattern",
                description=(
                    f"Weekday stress ({workday_avg:.0f}) is 45%+ higher "
                    f"than weekends ({weekend_avg:.0f})."
                ),
                severity=InsightSeverity.INFO,
                category="stress",
                data_points={
                    "workday_avg": workday_avg,
                    "weekend_avg": weekend_avg,
                },
            ))

    # Incomplete recovery alerts
    for pattern in result.post_activity_patterns:
        if pattern.recovery_time_minutes is None and pattern.peak_post_stress > 0:
            insights.append(Insight(
                title=f"Incomplete Recovery After {pattern.activity_sport}",
                description=(
                    "Stress did not return to baseline within 2 hours "
                    f"after your {pattern.activity_sport} session."
                ),
                severity=InsightSeverity.ALERT,
                category="stress",
                data_points={
                    "activity": pattern.activity_sport,
                    "peak_stress": pattern.peak_post_stress,
                },
                recommendations=[
                    "Consider reducing intensity next session",
                    "Ensure adequate fueling post-workout",
                ],
            ))

    return insights
```

**Step 2: Run flake8 and commit**

```bash
python -m flake8 garmindb/analysis/stress_analyzer.py --max-line-length=100
git add garmindb/analysis/stress_analyzer.py
git commit -m "feat(analysis): implement StressAnalyzer"
```

---

## Task 9: Integrate with HealthAnalyzer

**Files:**
- Modify: `garmindb/analysis/health_analyzer.py`

**Step 1: Add import**

```python
from .stress_analyzer import StressAnalyzer
```

**Step 2: Add StressAnalyzer to __init__**

```python
def __init__(self, repository: HealthRepository):
    self.repository = repository
    self.sleep = SleepAnalyzer(repository)
    self.recovery = RecoveryAnalyzer(repository)
    self.stress = StressAnalyzer(repository)  # NEW
```

**Step 3: Update generate_report method**

```python
def generate_report(self, start_date, end_date) -> HealthReport:
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
```

**Step 4: Run flake8 and commit**

```bash
python -m flake8 garmindb/analysis/health_analyzer.py --max-line-length=100
git add garmindb/analysis/health_analyzer.py
git commit -m "feat(health): integrate StressAnalyzer"
```

---

## Task 10: Update MarkdownPresenter

**Files:**
- Modify: `garmindb/presentation/markdown/renderer.py`

**Step 1: Add StressAnalysisResult to TYPE_CHECKING imports**

Already present, but ensure it's there.

**Step 2: Add stress rendering call in render_report**

```python
if report.stress:
    sections.append(self._render_stress(report.stress))
```

**Step 3: Implement _render_stress method**

```python
def _render_stress(self, result: "StressAnalysisResult") -> str:
    """Render stress analysis section."""
    lines = []
    lines.append("## Stress Analysis")
    period = f"{result.period_start} to {result.period_end}"
    lines.append(f"\n*Period: {period}*\n")

    # Key metrics
    if result.stress_load:
        lines.append(f"**Stress Load:** {result.stress_load.total_load:.0f} pts")
    lines.append(f"**Personal Baseline:** {result.personal_baseline:.0f}\n")

    # Distribution
    lines.append("### Distribution\n")
    lines.append(f"- **Low (0-25):** {result.low_stress_percent:.1f}%")
    lines.append(f"- **Medium (26-50):** {result.medium_stress_percent:.1f}%")
    lines.append(f"- **High (51-100):** {result.high_stress_percent:.1f}%\n")

    # Recovery metrics
    if result.recovery_efficiency is not None:
        lines.append("### Recovery Metrics\n")
        lines.append(f"- **Recovery Efficiency:** {result.recovery_efficiency:.0f}/100")
        if result.avg_recovery_time_minutes:
            avg_time = result.avg_recovery_time_minutes
            lines.append(f"- **Avg Recovery Time:** {avg_time:.0f} min")
        lines.append("")

    # Peak times
    if result.peak_stress_time:
        peak = result.peak_stress_time.strftime('%H:%M')
        lines.append(f"**Peak Stress Hour:** {peak}")
    if result.lowest_stress_time:
        lowest = result.lowest_stress_time.strftime('%H:%M')
        lines.append(f"**Lowest Stress Hour:** {lowest}")
    lines.append("")

    # Insights
    if result.insights:
        lines.append("### Insights\n")
        for insight in result.insights:
            lines.append(self._render_insight(insight))

    return "\n".join(lines)
```

**Step 4: Run flake8 and commit**

```bash
python -m flake8 garmindb/presentation/markdown/renderer.py --max-line-length=100
git add garmindb/presentation/markdown/renderer.py
git commit -m "feat(presentation): add stress rendering"
```

---

## Task 11: Add Unit Tests

**Files:**
- Create: `test/test_stress_analyzer.py`

**Step 1: Create test file**

```python
"""Tests for StressAnalyzer."""

import unittest
from datetime import date, timedelta


class TestStressAnalyzer(unittest.TestCase):
    """Test StressAnalyzer implementation."""

    @classmethod
    def setUpClass(cls):
        from garmindb import GarminConnectConfigManager
        from garmindb.data.repositories import SQLiteHealthRepository

        gc_config = GarminConnectConfigManager()
        db_params = gc_config.get_db_params()
        cls.repository = SQLiteHealthRepository(db_params)

    def test_analyzer_instantiation(self):
        from garmindb.analysis.stress_analyzer import StressAnalyzer
        analyzer = StressAnalyzer(self.repository)
        self.assertIsNotNone(analyzer)

    def test_analyze_returns_result(self):
        from garmindb.analysis.stress_analyzer import StressAnalyzer
        from garmindb.analysis.models import StressAnalysisResult

        analyzer = StressAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = analyzer.analyze(start_date, end_date)

        self.assertIsInstance(result, StressAnalysisResult)
        self.assertEqual(result.period_start, start_date)
        self.assertEqual(result.period_end, end_date)

    def test_stress_load_calculated(self):
        from garmindb.analysis.stress_analyzer import StressAnalyzer

        analyzer = StressAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = analyzer.analyze(start_date, end_date)

        self.assertIsNotNone(result.stress_load)
        self.assertGreaterEqual(result.stress_load.total_load, 0)

    def test_personal_baseline_in_range(self):
        from garmindb.analysis.stress_analyzer import StressAnalyzer

        analyzer = StressAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = analyzer.analyze(start_date, end_date)

        self.assertGreaterEqual(result.personal_baseline, 0)
        self.assertLessEqual(result.personal_baseline, 100)

    def test_hourly_patterns_complete(self):
        from garmindb.analysis.stress_analyzer import StressAnalyzer

        analyzer = StressAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = analyzer.analyze(start_date, end_date)

        self.assertEqual(len(result.hourly_patterns), 24)

    def test_distribution_sums_to_100(self):
        from garmindb.analysis.stress_analyzer import StressAnalyzer

        analyzer = StressAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = analyzer.analyze(start_date, end_date)

        total = (
            result.low_stress_percent +
            result.medium_stress_percent +
            result.high_stress_percent
        )
        self.assertAlmostEqual(total, 100, delta=1)


class TestStressAnalyzerInsights(unittest.TestCase):
    """Test StressAnalyzer insight generation."""

    @classmethod
    def setUpClass(cls):
        from garmindb import GarminConnectConfigManager
        from garmindb.data.repositories import SQLiteHealthRepository

        gc_config = GarminConnectConfigManager()
        db_params = gc_config.get_db_params()
        cls.repository = SQLiteHealthRepository(db_params)

    def test_insights_list_exists(self):
        from garmindb.analysis.stress_analyzer import StressAnalyzer

        analyzer = StressAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = analyzer.analyze(start_date, end_date)

        self.assertIsInstance(result.insights, list)

    def test_insights_have_required_fields(self):
        from garmindb.analysis.stress_analyzer import StressAnalyzer
        from garmindb.analysis.models import Insight

        analyzer = StressAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = analyzer.analyze(start_date, end_date)

        for insight in result.insights:
            self.assertIsInstance(insight, Insight)
            self.assertTrue(insight.title)
            self.assertEqual(insight.category, "stress")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run flake8 and commit**

```bash
python -m flake8 test/test_stress_analyzer.py --max-line-length=100
git add test/test_stress_analyzer.py
git commit -m "test: add StressAnalyzer unit tests"
```

---

## Validation Checklist

- [ ] All files pass flake8
- [ ] All files compile (py_compile)
- [ ] Tests pass
- [ ] HealthReport includes stress analysis
- [ ] MarkdownPresenter renders stress section
