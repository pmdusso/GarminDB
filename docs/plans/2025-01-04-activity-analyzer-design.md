# ActivityAnalyzer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a comprehensive activity analyzer that provides training load management (TSB/ATL/CTL), intensity distribution, and performance trend insights.

**Architecture:** Two-axis analysis - Axis A handles load management (TSB, Monotony, Strain) while Axis B tracks quality/performance (intensity distribution via training_effect, efficiency trends via velocity/HR). Uses 42-day lookback buffer for accurate CTL calculation.

**Key Design Decisions:**
- TSB requires continuous daily data (fill zeros for rest days to preserve decay)
- Efficiency Index uses velocity/HR (higher = fitter, more intuitive)
- Confidence Score based on load volume, not activity count
- Monotony/Strain require minimum 7 days (return None if < 7 days)

**Tech Stack:** Python dataclasses, SQLAlchemy queries via HealthRepository, exponential weighted averages for TSB.

---

## Data Structures

### New Models (add to models.py)

```python
@dataclass
class TrainingStressMetrics:
    """Training load metrics using TSB model."""
    atl: float                    # Acute Training Load (7-day EMA) - Fatigue
    ctl: float                    # Chronic Training Load (42-day EMA) - Fitness
    tsb: float                    # Training Stress Balance (CTL - ATL) - Form
    monotony: Optional[float]     # Mean / StdDev (None if < 7 days)
    strain: float                 # Weekly Load × Monotony (0.0 if monotony is None)
    confidence_score: float       # Real load / Total load (0-1.0, based on volume)


@dataclass
class SportSummary:
    """Per-sport activity breakdown."""
    name: str
    count: int
    total_distance_km: float
    total_duration_hours: float
    avg_speed_kmh: Optional[float] = None     # km per hour
    avg_hr: Optional[float] = None
    max_training_effect: float = 0.0
    efficiency_index: Optional[float] = None  # velocity / HR ratio (higher = fitter)
```

### Updated ActivityAnalysisResult

```python
@dataclass
class ActivityAnalysisResult:
    """Complete activity analysis result."""

    period_start: date
    period_end: date

    # Totals
    total_activities: int
    total_duration_hours: float
    total_distance_km: float
    total_calories: int

    # Load Management (Axis A)
    training_stress: TrainingStressMetrics
    daily_load_series: Dict[date, float] = field(default_factory=dict)

    # Sport Breakdown
    sport_summaries: Dict[str, SportSummary] = field(default_factory=dict)

    # Intensity Distribution (Axis B)
    avg_aerobic_effect: float = 0.0
    avg_anaerobic_effect: float = 0.0
    intensity_distribution: Dict[str, float] = field(default_factory=dict)
    # Keys: "Recovery", "Base", "Improving", "Highly Improving", "Overreaching"

    # Trends
    weekly_volume_trend: TrendDirection = TrendDirection.STABLE

    # Insights
    insights: List[Insight] = field(default_factory=list)
```

---

## Core Calculations

### Load Estimation (when training_load is missing)

```python
LOAD_FACTORS = {
    "running": 0.8,      # 60 min run = 48 load
    "cycling": 0.6,      # 60 min cycle = 36 load
    "walking": 0.3,      # 60 min walk = 18 load
    "swimming": 0.9,     # 60 min swim = 54 load
    "strength_training": 0.5,
    "default": 0.5
}

def estimate_load(activity: ActivityRecord) -> tuple[float, bool]:
    """Returns (load, is_estimated)."""
    if activity.training_load:
        return (activity.training_load, False)

    factor = LOAD_FACTORS.get(activity.sport.lower(), LOAD_FACTORS["default"])
    duration_min = activity.duration.total_seconds() / 60
    return (duration_min * factor, True)
```

### TSB Calculation (Exponential Moving Averages)

**CRITICAL:** Daily loads must be continuous (include rest days as 0.0) for proper decay calculation.

```python
def _build_continuous_daily_loads(
    activities: List[ActivityRecord],
    start_date: date,
    end_date: date
) -> Dict[date, float]:
    """Build daily load series with zeros for rest days."""
    # Initialize all days with zero
    daily_loads = {}
    current = start_date
    while current <= end_date:
        daily_loads[current] = 0.0
        current += timedelta(days=1)

    # Populate with actual activity loads
    for activity in activities:
        day = activity.start_time.date()
        if day in daily_loads:
            load, _ = estimate_load(activity)
            daily_loads[day] += load

    return daily_loads


def calculate_ema(daily_loads: List[float], window: int) -> float:
    """Calculate exponential moving average."""
    alpha = 2 / (window + 1)
    ema = daily_loads[0] if daily_loads else 0
    for load in daily_loads[1:]:
        ema = alpha * load + (1 - alpha) * ema
    return ema

# ATL = EMA(7 days)
# CTL = EMA(42 days)
# TSB = CTL - ATL
```

### Monotony & Strain

**Note:** Requires minimum 7 days for meaningful calculation. Return None/0.0 for shorter periods.

```python
def calculate_monotony(weekly_loads: List[float]) -> Optional[float]:
    """Monotony = Mean / StdDev (higher = more repetitive).

    Returns None if fewer than 7 data points (insufficient for meaningful analysis).
    """
    if not weekly_loads or len(weekly_loads) < 7:
        return None
    mean = sum(weekly_loads) / len(weekly_loads)
    variance = sum((x - mean) ** 2 for x in weekly_loads) / len(weekly_loads)
    std_dev = variance ** 0.5
    return mean / std_dev if std_dev > 0 else 0.0

def calculate_strain(weekly_load: float, monotony: Optional[float]) -> float:
    """Strain = Weekly Load × Monotony."""
    if monotony is None:
        return 0.0
    return weekly_load * monotony
```

### Intensity Distribution (Training Effect based)

```python
INTENSITY_CATEGORIES = {
    "Recovery": (0.0, 1.9),      # TE 0-1.9
    "Base": (2.0, 2.9),          # TE 2.0-2.9
    "Improving": (3.0, 3.9),     # TE 3.0-3.9
    "Highly Improving": (4.0, 4.4),  # TE 4.0-4.4
    "Overreaching": (4.5, 5.0),  # TE 4.5-5.0
}

def categorize_intensity(training_effect: float) -> str:
    for category, (low, high) in INTENSITY_CATEGORIES.items():
        if low <= training_effect <= high:
            return category
    return "Base"  # default
```

### Efficiency Index

**Design:** Uses velocity/HR (km/h per bpm). Higher value = fitter (more distance per heartbeat).

```python
def calculate_efficiency_index(avg_speed_kmh: float, avg_hr: float) -> Optional[float]:
    """Efficiency = velocity / HR (higher = better fitness).

    Measures km/h per heartbeat. A fitter athlete covers more distance
    at the same heart rate, resulting in a higher efficiency index.
    """
    if avg_hr <= 0 or avg_speed_kmh <= 0:
        return None
    return (avg_speed_kmh / avg_hr) * 100  # Scale for readability
```

---

## Insights Generation

### 1. Consistency Insight (Volume Change)

```python
def check_consistency(current_week_load: float, prev_week_load: float) -> Optional[Insight]:
    if prev_week_load == 0:
        return None

    percent_change = abs(current_week_load - prev_week_load) / prev_week_load * 100

    if percent_change > 20:
        direction = "increased" if current_week_load > prev_week_load else "decreased"
        return Insight(
            title="Training Volume Spike",
            description=f"Weekly training load {direction} by {percent_change:.0f}%. "
                       f"Rapid changes above 20% increase injury risk.",
            severity=InsightSeverity.WARNING,
            category="activity",
            data_points={
                "percent_change": percent_change,
                "current_week_load": current_week_load,
                "previous_week_load": prev_week_load
            },
            recommendations=[
                "Limit weekly load increases to 10% or less",
                "Include rest days between high-intensity sessions"
            ]
        )
    return None
```

### 2. Intensity Balance Insight

```python
def check_intensity_balance(intensity_distribution: Dict[str, float]) -> Optional[Insight]:
    high_intensity_pct = sum(
        intensity_distribution.get(cat, 0)
        for cat in ["Improving", "Highly Improving", "Overreaching"]
    )

    if high_intensity_pct > 80:
        return Insight(
            title="Intensity Imbalance Alert",
            description=f"{high_intensity_pct:.0f}% of your training is high-intensity. "
                       f"This pattern increases burnout and overtraining risk.",
            severity=InsightSeverity.ALERT,
            category="activity",
            data_points={"high_intensity_percent": high_intensity_pct},
            recommendations=[
                "Add more low-intensity recovery sessions",
                "Target 80/20 distribution (80% easy, 20% hard)"
            ]
        )
    elif high_intensity_pct > 70:
        return Insight(
            title="High Intensity Training",
            description=f"{high_intensity_pct:.0f}% of your training is high-intensity. "
                       f"Consider adding more recovery sessions.",
            severity=InsightSeverity.WARNING,
            category="activity",
            data_points={"high_intensity_percent": high_intensity_pct},
            recommendations=["Include 2-3 easy sessions per week"]
        )
    return None
```

### 3. Efficiency Gains Insight

```python
def check_efficiency_gains(
    current_sport_summary: SportSummary,
    previous_sport_summary: SportSummary
) -> Optional[Insight]:
    """Compare efficiency between periods for same sport."""
    if not (current_sport_summary.efficiency_index and
            previous_sport_summary.efficiency_index):
        return None

    current_eff = current_sport_summary.efficiency_index
    prev_eff = previous_sport_summary.efficiency_index

    # Higher efficiency index = better (more speed per heartbeat)
    improvement_pct = (current_eff - prev_eff) / prev_eff * 100

    if improvement_pct >= 5:
        return Insight(
            title=f"Efficiency Improvement in {current_sport_summary.name}",
            description=f"Your {current_sport_summary.name} efficiency improved by "
                       f"{improvement_pct:.0f}% - covering more distance at the same heart rate.",
            severity=InsightSeverity.POSITIVE,
            category="activity",
            data_points={
                "improvement_percent": improvement_pct,
                "current_efficiency": current_eff,
                "previous_efficiency": prev_eff
            },
            recommendations=[]
        )
    return None
```

---

## Implementation Tasks

### Task 1: Add Data Models

**Files:**
- Modify: `garmindb/analysis/models.py`

**Steps:**
1. Add `TrainingStressMetrics` dataclass after `PostActivityStressPattern`
2. Add `SportSummary` dataclass after `TrainingStressMetrics`
3. Update `ActivityAnalysisResult` with new fields
4. Update `__init__.py` exports

**Commit:** `feat(analysis): add activity analyzer data models`

---

### Task 2: Create ActivityAnalyzer Core Structure

**Files:**
- Create: `garmindb/analysis/activity_analyzer.py`

**Steps:**
1. Create skeleton with `__init__`, `analyze()` method signature
2. Add LOAD_FACTORS constant
3. Add INTENSITY_CATEGORIES constant
4. Import dependencies

**Commit:** `feat(analysis): add ActivityAnalyzer skeleton`

---

### Task 3: Implement Load Estimation

**Files:**
- Modify: `garmindb/analysis/activity_analyzer.py`

**Steps:**
1. Implement `_estimate_load()` method returning (load, is_estimated)
2. Implement `_build_continuous_daily_loads()` (include zeros for rest days)
3. Calculate confidence_score based on **load volume** (not activity count):
   - `confidence = real_load_sum / total_load_sum`
   - A 200 TSS estimated workout impacts confidence more than a 10 TSS walk

**Commit:** `feat(analysis): implement load estimation with confidence scoring`

---

### Task 4: Implement TSB Calculations

**Files:**
- Modify: `garmindb/analysis/activity_analyzer.py`

**Steps:**
1. Implement `_calculate_ema()` helper
2. Implement `_calculate_tsb_metrics()` returning TrainingStressMetrics
3. Handle 42-day lookback buffer automatically

**Commit:** `feat(analysis): implement TSB/ATL/CTL calculations`

---

### Task 5: Implement Monotony & Strain

**Files:**
- Modify: `garmindb/analysis/activity_analyzer.py`

**Steps:**
1. Implement `_calculate_monotony()` method
2. Implement `_calculate_strain()` method
3. Integrate into TrainingStressMetrics

**Commit:** `feat(analysis): implement monotony and strain calculations`

---

### Task 6: Implement Sport Summaries

**Files:**
- Modify: `garmindb/analysis/activity_analyzer.py`

**Steps:**
1. Implement `_build_sport_summaries()` method
2. Calculate pace, HR averages per sport
3. Calculate efficiency_index for each sport

**Commit:** `feat(analysis): implement per-sport summaries with efficiency index`

---

### Task 7: Implement Intensity Distribution

**Files:**
- Modify: `garmindb/analysis/activity_analyzer.py`

**Steps:**
1. Implement `_categorize_intensity()` helper
2. Implement `_calculate_intensity_distribution()` method
3. Calculate avg_aerobic_effect and avg_anaerobic_effect

**Commit:** `feat(analysis): implement intensity distribution from training effect`

---

### Task 8: Implement Main analyze() Method

**Files:**
- Modify: `garmindb/analysis/activity_analyzer.py`

**Steps:**
1. Implement full `analyze()` method
2. Fetch activities from repository (with 42-day lookback)
3. Orchestrate all calculations
4. Build and return ActivityAnalysisResult

**Commit:** `feat(analysis): implement ActivityAnalyzer.analyze()`

---

### Task 9: Implement Insights Generation

**Files:**
- Modify: `garmindb/analysis/activity_analyzer.py`

**Steps:**
1. Implement `_check_consistency()` method
2. Implement `_check_intensity_balance()` method
3. Implement `_check_efficiency_gains()` method
4. Implement `_generate_insights()` orchestrator

**Commit:** `feat(analysis): implement activity insights generation`

---

### Task 10: Integrate with HealthAnalyzer

**Files:**
- Modify: `garmindb/analysis/health_analyzer.py`
- Modify: `garmindb/analysis/__init__.py`

**Steps:**
1. Import ActivityAnalyzer in health_analyzer.py
2. Add `self.activities = ActivityAnalyzer(repository)` to __init__
3. Call `activities.analyze()` in `generate_report()`
4. Export ActivityAnalyzer and new models from __init__.py

**Commit:** `feat(analysis): integrate ActivityAnalyzer with HealthAnalyzer`

---

### Task 11: Update MarkdownPresenter

**Files:**
- Modify: `garmindb/presentation/markdown/renderer.py`

**Steps:**
1. Update `_render_activities()` to show TrainingStressMetrics (ATL, CTL, TSB, Form)
2. Add intensity distribution with ASCII progress bars:
   ```
   Recovery:        [====      ]  40%
   Base:            [===       ]  30%
   Improving:       [==        ]  20%
   Highly Improving:[=         ]  10%
   ```
3. Add sport summaries table with efficiency index
4. Render activity insights
5. Show confidence score with warning if < 70%

**Commit:** `feat(presentation): render activity analysis in markdown`

---

### Task 12: Add Unit Tests

**Files:**
- Create: `test/test_activity_analyzer.py`

**Steps:**
1. Test load estimation with various sports
2. Test TSB calculations with known values
3. Test intensity distribution categorization
4. Test insight generation thresholds
5. Test confidence_score calculation

**Commit:** `test(analysis): add ActivityAnalyzer unit tests`

---

## Validation Checklist

- [ ] All flake8 checks pass (`make flake8`)
- [ ] Unit tests pass (`python -m pytest test/test_activity_analyzer.py -v`)
- [ ] Integration test with real Garmin data
- [ ] MarkdownPresenter produces valid output
- [ ] Confidence score accurately reflects estimated vs real load volume ratio
- [ ] daily_load_series includes zeros for rest days (TSB decay accuracy)
- [ ] Monotony/Strain return None/0.0 for periods < 7 days
- [ ] Efficiency index uses velocity/HR (higher = fitter)
