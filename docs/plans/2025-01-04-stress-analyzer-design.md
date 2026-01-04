# StressAnalyzer Design Document

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement StressAnalyzer to analyze stress patterns, calculate stress load (AUC), and measure post-activity recovery efficiency.

**Architecture:** Follows existing analyzer pattern (SleepAnalyzer, RecoveryAnalyzer). Uses Repository for data access, produces StressAnalysisResult with MetricSummary and Insight objects.

**Tech Stack:** Python 3.12, dataclasses, existing GarminDB infrastructure

---

## 1. Data Structures

### 1.1 New DTOs (add to `analysis/models.py`)

```python
@dataclass
class StressLoadMetric:
    """Stress load calculated as area under the curve."""
    period_minutes: int
    total_load: float            # Σ(stress × duration) / 60
    avg_intensity: float         # Weighted average by time
    peak_load_hour: Optional[time] = None

@dataclass
class HourlyStressPattern:
    """Stress pattern for a specific hour of day."""
    hour: int                    # 0-23
    avg_stress: float
    sample_count: int
    category_distribution: Dict[str, float] = field(default_factory=dict)

@dataclass
class PostActivityStressPattern:
    """Post-activity stress recovery pattern."""
    activity_id: str
    activity_sport: str
    activity_end_time: datetime
    pre_activity_stress: float   # 30min before
    peak_post_stress: float      # Peak in 2h window
    stress_load_2h: float        # Stress Load in 2h post
    recovery_time_minutes: Optional[int] = None  # Time to baseline+5
```

### 1.2 Updated StressAnalysisResult

Add these fields to the existing StressAnalysisResult:

```python
@dataclass
class StressAnalysisResult:
    # Existing fields
    period_start: date
    period_end: date
    avg_stress: MetricSummary
    low_stress_percent: float
    medium_stress_percent: float
    high_stress_percent: float
    peak_stress_time: Optional[time] = None
    lowest_stress_time: Optional[time] = None
    insights: List[Insight] = field(default_factory=list)
    daily_avg_stress: Dict[date, float] = field(default_factory=dict)

    # NEW fields
    stress_load: Optional[StressLoadMetric] = None
    hourly_patterns: List[HourlyStressPattern] = field(default_factory=list)
    weekday_avg: Dict[str, float] = field(default_factory=dict)
    post_activity_patterns: List[PostActivityStressPattern] = field(default_factory=list)
    avg_recovery_time_minutes: Optional[float] = None
    recovery_efficiency: Optional[float] = None  # 0-100
    personal_baseline: float = 25.0
```

---

## 2. Logic & Heuristics

### 2.1 Configuration Constants

```python
BASELINE_DAYS = 14
BASELINE_PERCENTILE = 25
BASELINE_HOURS = (0, 6)        # 00:00-06:00 for resting baseline
RECOVERY_WINDOW_HOURS = 2
RECOVERY_THRESHOLD_BUFFER = 5  # baseline + 5
GAP_CAP_MINUTES = 15           # Max interpolation gap
```

### 2.2 Stress Load Calculation (O(n))

```python
def _calculate_stress_load(self, stress_records, start, end) -> StressLoadMetric:
    """
    Stress Load = Σ(stress_level × duration_minutes) / 60

    - Single pass O(n)
    - Caps gaps at 15 minutes to avoid hallucinating load
    - Filters out invalid readings (stress <= 0)
    """
```

### 2.3 Personal Baseline

```python
def _calculate_personal_baseline(self, stress_records, end_date) -> float:
    """
    Uses 25th percentile of resting stress (00:00-06:00) over 14 days.
    More robust than mean - not skewed by outliers.
    """
```

### 2.4 Post-Activity Recovery

```python
def _analyze_post_activity_recovery(self, activity, stress_records, baseline) -> PostActivityStressPattern:
    """
    Analyzes stress in 2h window after activity ends.
    Recovery = time until stress <= baseline + 5
    If no recovery within 2h, recovery_time_minutes = None (systemic fatigue signal)
    """
```

### 2.5 Recovery Efficiency Score

```python
def _calculate_recovery_efficiency(self, patterns: List[PostActivityStressPattern]) -> float:
    """
    Efficiency = 100 - (avg_recovery_time / 120) * 100

    - Activities with no recovery (None) count as 120 min (worst case)
    - Score 0-100 where 100 = immediate recovery
    """
```

---

## 3. Insights Generation

| Condition | Insight | Severity |
|-----------|---------|----------|
| stress_load.total_load > 500/day | "High Cumulative Stress" | WARNING |
| recovery_efficiency < 50 | "Poor Stress Recovery" | WARNING |
| recovery_efficiency >= 80 | "Excellent Resilience" | POSITIVE |
| weekday_avg[workdays] > weekend * 1.45 | "Occupational Stress Detected" | INFO |
| peak_stress_time in 09:00-17:00 | "Work Hours Stress Peak" | INFO |
| avg_recovery_time > 90 | "Slow Autonomic Recovery" | WARNING |
| Any activity with recovery_time = None | "Incomplete Recovery After {sport}" | ALERT |

---

## 4. Integration

### 4.1 HealthAnalyzer

```python
class HealthAnalyzer:
    def __init__(self, repository):
        self.sleep = SleepAnalyzer(repository)
        self.recovery = RecoveryAnalyzer(repository)
        self.stress = StressAnalyzer(repository)  # NEW
```

### 4.2 HealthReport

The existing `stress: Optional[StressAnalysisResult]` field will be populated.

### 4.3 MarkdownPresenter

Add `_render_stress()` method showing:
- Stress Load (total points)
- Personal Baseline
- Distribution (low/medium/high %)
- Recovery Efficiency
- Peak/Lowest stress times

---

## 5. Files to Modify/Create

| File | Action |
|------|--------|
| `garmindb/analysis/models.py` | Add 3 new dataclasses, update StressAnalysisResult |
| `garmindb/analysis/stress_analyzer.py` | CREATE - Full analyzer implementation |
| `garmindb/analysis/__init__.py` | Export new classes |
| `garmindb/analysis/health_analyzer.py` | Add StressAnalyzer integration |
| `garmindb/presentation/markdown/renderer.py` | Add stress rendering |
| `test/test_stress_analyzer.py` | CREATE - Unit tests |

---

## 6. Validation Criteria

1. **Stress Load accuracy**: Manual calculation on sample data matches analyzer output
2. **Recovery detection**: Activities followed by stress drop are correctly identified
3. **Baseline stability**: Baseline doesn't change dramatically day-to-day
4. **Performance**: 30-day analysis with ~50k stress records completes in < 2 seconds
5. **Integration**: HealthReport.stress is populated and renders correctly

---

## 7. Notes & Constraints

- **Night shift workers**: Baseline calculation assumes 00:00-06:00 is rest period. Document this limitation.
- **Garmin special values**: Filter out stress <= 0 (invalid readings, "too active to measure")
- **Gap handling**: Cap interpolation at 15 minutes to avoid inflating load during watch-off periods
