# RecoveryAnalyzer Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Implement a RecoveryAnalyzer that calculates recovery scores based on RHR, Body Battery, and Training Load.

**Architecture:** Follows existing layered architecture - reuses existing DTOs and repository methods with minimal additions.

**Tech Stack:** Python dataclasses, SQLite, existing HealthRepository pattern.

---

## Summary of Design Decisions

| Decision | Rationale |
|----------|-----------|
| Reuse `DailySummaryRecord` | Already contains resting_hr, bb_max, bb_min, stress_avg |
| Reuse `ActivityRecord` | Already contains training_load, training_effect |
| Add `bb_charged` to DTO | Only missing field needed for recovery analysis |
| No new repository methods | Use existing `get_daily_summaries()` and `get_activities()` |
| Rename existing class | `RecoveryAnalysisResult` → `DailyReadinessResult` |
| Two output types | Daily snapshot + Period report |

---

## Implementation Tasks

### Task 1: Update DailySummaryRecord DTO

**Files:**
- Modify: `garmindb/data/models.py`

**Changes:**
Add `bb_charged` field to existing `DailySummaryRecord`:

```python
@dataclass
class DailySummaryRecord:
    """Daily health summary."""
    date: date
    resting_hr: Optional[int] = None
    stress_avg: Optional[int] = None
    bb_max: Optional[int] = None
    bb_min: Optional[int] = None
    bb_charged: Optional[int] = None  # ADD THIS
    steps: Optional[int] = None
    floors: Optional[int] = None
    sleep_avg: Optional[timedelta] = None
```

---

### Task 2: Update SQLite Repository Query

**Files:**
- Modify: `garmindb/data/repositories/sqlite.py`

**Changes:**
Update `get_daily_summaries()` to include `bb_charged` column from database.

---

### Task 3: Rename Existing Analysis Result Class

**Files:**
- Modify: `garmindb/analysis/models.py`

**Changes:**
Rename `RecoveryAnalysisResult` → `DailyReadinessResult` (lines 127-142).

---

### Task 4: Add New RecoveryAnalysisResult Class

**Files:**
- Modify: `garmindb/analysis/models.py`

**Changes:**
Add new period-based result class:

```python
@dataclass
class RecoveryAnalysisResult:
    """Result of recovery analysis for a period."""
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
```

---

### Task 5: Implement RecoveryAnalyzer Class

**Files:**
- Create: `garmindb/analysis/recovery_analyzer.py`

**Implementation:**

```python
"""Recovery analysis: RHR, Body Battery, Training Load."""

from dataclasses import dataclass
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
    """Analyzes recovery metrics: RHR, Body Battery, Training Load."""

    # Configuration
    RHR_BASELINE_DAYS = 60
    ACUTE_LOAD_DAYS = 7
    CHRONIC_LOAD_DAYS = 28

    # Recovery score weights
    RHR_WEIGHT = 0.40
    BB_WEIGHT = 0.35
    SLEEP_WEIGHT = 0.25

    def __init__(self, repository: 'HealthRepository'):
        self._repository = repository

    def analyze(
        self,
        start_date: date,
        end_date: date
    ) -> RecoveryAnalysisResult:
        """Analyze recovery for a period."""
        # Fetch data with lookback buffer for baseline calculation
        lookback_days = max(self.RHR_BASELINE_DAYS, self.CHRONIC_LOAD_DAYS)
        data_start = start_date - timedelta(days=lookback_days)

        daily_data = self._repository.get_daily_summaries(data_start, end_date)
        activities = self._repository.get_activities(data_start, end_date)
        sleep_data = self._repository.get_sleep_data(data_start, end_date)

        # Calculate metrics...
        # (implementation details)

    def daily_readiness(self, target_date: date) -> DailyReadinessResult:
        """Calculate readiness score for a specific day."""
        # (implementation details)

    def _calculate_rhr_baseline(self, end_date: date) -> float:
        """60-day rolling average RHR."""
        pass

    def _calculate_recovery_score(
        self,
        rhr_deviation: float,
        bb_charged: int,
        sleep_score: Optional[int]
    ) -> int:
        """Weighted score: 40% RHR + 35% BB + 25% Sleep."""
        pass

    def _calculate_acute_chronic_ratio(
        self,
        activities: List
    ) -> Optional[float]:
        """ATL/CTL ratio for injury risk assessment."""
        pass

    def _generate_insights(self, ...) -> List[Insight]:
        """Generate recovery insights."""
        pass
```

---

### Task 6: Update Analysis Module Exports

**Files:**
- Modify: `garmindb/analysis/__init__.py`

**Changes:**
Export new classes:
```python
from .recovery_analyzer import RecoveryAnalyzer
from .models import RecoveryAnalysisResult, DailyReadinessResult
```

---

### Task 7: Integrate with HealthAnalyzer

**Files:**
- Modify: `garmindb/analysis/health_analyzer.py`

**Changes:**
Add RecoveryAnalyzer to HealthAnalyzer composition.

---

### Task 8: Add Tests

**Files:**
- Modify: `test/test_data_models.py` (add DailySummaryRecord.bb_charged test)
- Create or Modify: `test/test_recovery_analyzer.py`

---

### Task 9: Update MarkdownPresenter

**Files:**
- Modify: `garmindb/presentation/markdown/renderer.py`

**Changes:**
Add rendering for `RecoveryAnalysisResult`.

---

## Algorithm Details

### Recovery Score Calculation (0-100)

```
recovery_score = (
    RHR_component * 0.40 +
    BB_component * 0.35 +
    Sleep_component * 0.25
)

Where:
- RHR_component = 100 - (rhr_deviation_from_baseline * 5), clamped 0-100
- BB_component = bb_charged, clamped 0-100
- Sleep_component = sleep_score if available, else 70 (neutral)
```

### Acute:Chronic Workload Ratio

```
ACWR = ATL / CTL

Where:
- ATL = Average daily TSS over last 7 days
- CTL = Average daily TSS over last 28 days

Risk zones:
- < 0.8: Undertrained
- 0.8 - 1.3: Optimal
- 1.3 - 1.5: Caution
- > 1.5: High injury risk
```

### Insight Generation Rules

| Condition | Severity | Message |
|-----------|----------|---------|
| RHR > baseline + 5 | warning | "Elevated RHR suggests incomplete recovery" |
| RHR > baseline + 10 | critical | "Significantly elevated RHR - consider rest day" |
| BB charged < 30 | warning | "Low overnight recharge" |
| ACWR > 1.5 | critical | "High injury risk - reduce training load" |
| ACWR < 0.8 | info | "Training load below optimal" |

---

## Dependencies

- No new external dependencies required
- Uses existing: dataclasses, datetime, typing

---

*Document created: 2025-01-04*
*Validated by: Architecture Validator Agent*
