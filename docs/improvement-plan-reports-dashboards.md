# GarminDB Improvement Plan: Layered Architecture for Multi-Platform Health Analytics

## Executive Summary

This document outlines a plan to evolve the GarminDB project into a **layered architecture** that cleanly separates:

1. **Data Layer** - Garmin data ingestion and storage (existing GarminDB)
2. **Analysis Layer** - Reusable health analytics and insights engine
3. **Presentation Layer** - Multiple outputs (Notebooks, Markdown, Web App)

This architecture enables:
- **Reusability**: Same analysis logic across all presentation formats
- **Scalability**: Easy to add new frontends (web app for friends!)
- **Maintainability**: Changes in one layer don't affect others
- **Testability**: Each layer can be tested independently

---

## Architecture Vision

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         PRESENTATION LAYER                                   │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Jupyter    │  │   Markdown   │  │   Web App    │  │   CLI        │    │
│  │   Notebooks  │  │   Reports    │  │   (FastAPI)  │  │   Output     │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘    │
│         │                 │                 │                 │             │
│         └─────────────────┴────────┬────────┴─────────────────┘             │
│                                    │                                        │
│                          ┌─────────▼─────────┐                              │
│                          │   Presentation    │                              │
│                          │   Adapters        │                              │
│                          │   (Formatters)    │                              │
│                          └─────────┬─────────┘                              │
└────────────────────────────────────┼────────────────────────────────────────┘
                                     │
┌────────────────────────────────────┼────────────────────────────────────────┐
│                          ANALYSIS LAYER                                      │
│                                    │                                        │
│                          ┌─────────▼─────────┐                              │
│                          │   Analysis API    │                              │
│                          │   (Domain Logic)  │                              │
│                          └─────────┬─────────┘                              │
│                                    │                                        │
│  ┌──────────────┐  ┌──────────────┼──────────────┐  ┌──────────────┐       │
│  │    Sleep     │  │    Recovery  │   Stress     │  │   Activity   │       │
│  │   Analyzer   │  │   Analyzer   │   Analyzer   │  │   Analyzer   │       │
│  └──────┬───────┘  └──────┬───────┴──────┬───────┘  └──────┬───────┘       │
│         │                 │              │                 │                │
│         └─────────────────┴──────┬───────┴─────────────────┘                │
│                                  │                                          │
│                        ┌─────────▼─────────┐                                │
│                        │   Data Models     │                                │
│                        │   (DTOs/Entities) │                                │
│                        └─────────┬─────────┘                                │
└──────────────────────────────────┼──────────────────────────────────────────┘
                                   │
┌──────────────────────────────────┼──────────────────────────────────────────┐
│                           DATA LAYER                                         │
│                                  │                                          │
│                        ┌─────────▼─────────┐                                │
│                        │   Repository      │                                │
│                        │   Interface       │                                │
│                        └─────────┬─────────┘                                │
│                                  │                                          │
│  ┌──────────────┐  ┌─────────────┼─────────────┐  ┌──────────────┐         │
│  │   GarminDB   │  │  Garmin     │  Summary    │  │  Monitoring  │         │
│  │   (SQLite)   │  │  Activities │  DB         │  │  DB          │         │
│  └──────────────┘  └─────────────┴─────────────┘  └──────────────┘         │
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────┐          │
│  │              Garmin Connect API (Download/Sync)               │          │
│  └──────────────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Layer Responsibilities

| Layer | Responsibility | Examples |
|-------|----------------|----------|
| **Data** | Data access, storage, sync with Garmin | SQLite DBs, API download, FIT parsing |
| **Analysis** | Business logic, calculations, insights | Sleep quality score, recovery metrics, trends |
| **Presentation** | Format and display results | Markdown, HTML, JSON API, Jupyter widgets |

### Key Principle: Dependency Direction

```
Presentation → Analysis → Data
     ↓             ↓         ↓
  (knows)      (knows)   (knows nothing)
```

Each layer only knows about the layer below it. The Data layer has no knowledge of how data will be displayed.

---

## Research Findings

### Current Landscape

#### 1. Garmin Data Visualization Projects

| Project | Approach | Pros | Cons |
|---------|----------|------|------|
| [Garmin-Grafana](https://github.com/arpanghosh8453/garmin-grafana) | InfluxDB + Grafana | Real-time dashboards, self-hosted | Requires Docker, InfluxDB infrastructure |
| [GarminDB](https://github.com/tcgoetz/GarminDB) (current) | SQLite + Jupyter | Lightweight, portable | Notebooks are not Git-friendly, hard to share |
| [garminconnect](https://pypi.org/project/garminconnect/) | Python API wrapper | Direct API access | No visualization, just data fetching |

#### 2. Report Generation Approaches

| Tool | Type | LLM-Friendly | Git-Friendly |
|------|------|--------------|--------------|
| [mkreports](https://github.com/hhoeflin/mkreports) | Pure Python → Markdown | Yes | Yes |
| [Quarto](https://quarto.org/) | Code + Markdown → HTML/PDF | Moderate | Yes |
| [marimo](https://marimo.io/) | Reactive Python notebooks | Yes (stored as .py) | Yes |
| Jupyter Notebooks | Interactive notebooks | No (JSON + base64) | No |

#### 3. Why Markdown is Optimal for LLMs

Based on research from [Webex Developers](https://developer.webex.com/blog/boosting-ai-performance-the-power-of-llm-friendly-content-in-markdown) and [Wetrocloud](https://medium.com/@wetrocloud/why-markdown-is-the-best-format-for-llms-aa0514a409a7):

- **Hierarchical Structure**: Headings (`#`, `##`, `###`) provide contextual cues
- **Token Efficiency**: Lighter than JSON/XML, more room for meaningful data
- **Semantic Clarity**: Lists, tables, and sections reduce ambiguity
- **Universal Compatibility**: Works with any LLM without preprocessing

---

## Detailed Layer Design

### Layer 1: Data Layer (Existing - Minor Refactoring)

The Data Layer already exists in GarminDB. We need to add a **Repository Pattern** to abstract database access.

#### 1.1 Repository Interface

```python
# garmindb/data/repositories/base.py
from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional

class HealthRepository(ABC):
    """Abstract interface for health data access"""

    @abstractmethod
    def get_sleep_data(self, start: date, end: date) -> List[SleepRecord]:
        pass

    @abstractmethod
    def get_heart_rate_data(self, start: date, end: date) -> List[HeartRateRecord]:
        pass

    @abstractmethod
    def get_stress_data(self, start: date, end: date) -> List[StressRecord]:
        pass

    @abstractmethod
    def get_activities(self, start: date, end: date) -> List[ActivityRecord]:
        pass

    @abstractmethod
    def get_body_battery(self, start: date, end: date) -> List[BodyBatteryRecord]:
        pass
```

#### 1.2 SQLite Implementation

```python
# garmindb/data/repositories/sqlite_repository.py
from garmindb.garmindb import GarminDb, Sleep, MonitoringHeartRate
from .base import HealthRepository

class SQLiteHealthRepository(HealthRepository):
    """SQLite implementation of health data repository"""

    def __init__(self, db_params: dict):
        self.db_params = db_params
        self._garmin_db = None

    @property
    def garmin_db(self):
        if not self._garmin_db:
            self._garmin_db = GarminDb(self.db_params)
        return self._garmin_db

    def get_sleep_data(self, start: date, end: date) -> List[SleepRecord]:
        raw_data = Sleep.get_for_period(self.garmin_db, start, end)
        return [SleepRecord.from_db_row(row) for row in raw_data]
```

#### 1.3 Data Transfer Objects (DTOs)

```python
# garmindb/data/models.py
from dataclasses import dataclass
from datetime import date, time, timedelta
from typing import Optional

@dataclass
class SleepRecord:
    date: date
    total_sleep: timedelta
    deep_sleep: timedelta
    light_sleep: timedelta
    rem_sleep: timedelta
    awake_time: timedelta
    sleep_score: Optional[int] = None

    @classmethod
    def from_db_row(cls, row) -> 'SleepRecord':
        """Convert database row to DTO"""
        return cls(
            date=row.day,
            total_sleep=row.total_sleep,
            deep_sleep=row.deep_sleep,
            # ... etc
        )

@dataclass
class HeartRateRecord:
    timestamp: datetime
    heart_rate: int
    resting_hr: Optional[int] = None

@dataclass
class StressRecord:
    timestamp: datetime
    stress_level: int  # 0-100

@dataclass
class ActivityRecord:
    activity_id: str
    name: str
    sport: str
    start_time: datetime
    duration: timedelta
    distance: Optional[float] = None
    calories: Optional[int] = None
    avg_hr: Optional[int] = None
    training_effect: Optional[float] = None
```

---

### Layer 2: Analysis Layer (New)

The Analysis Layer contains all business logic and is **completely independent of presentation**.

#### 2.1 Module Structure

```
garmindb/
├── analysis/
│   ├── __init__.py
│   ├── base.py              # Base analyzer class
│   ├── models.py            # Analysis result models
│   ├── sleep_analyzer.py    # Sleep analysis logic
│   ├── recovery_analyzer.py # Recovery/readiness analysis
│   ├── stress_analyzer.py   # Stress patterns analysis
│   ├── activity_analyzer.py # Activity/training analysis
│   ├── trends_analyzer.py   # Trend detection & forecasting
│   └── insights.py          # Cross-domain insights engine
```

#### 2.2 Analysis Result Models

```python
# garmindb/analysis/models.py
from dataclasses import dataclass, field
from datetime import date
from typing import List, Optional, Dict, Any
from enum import Enum

class TrendDirection(Enum):
    IMPROVING = "improving"
    DECLINING = "declining"
    STABLE = "stable"

class InsightSeverity(Enum):
    INFO = "info"
    WARNING = "warning"
    ALERT = "alert"
    POSITIVE = "positive"

@dataclass
class MetricSummary:
    """Summary of a single metric"""
    current_value: float
    previous_value: Optional[float]
    average_7d: Optional[float]
    average_30d: Optional[float]
    trend: TrendDirection
    percent_change: Optional[float] = None
    unit: str = ""

@dataclass
class Insight:
    """A single actionable insight"""
    title: str
    description: str
    severity: InsightSeverity
    category: str  # sleep, stress, recovery, activity
    data_points: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)

@dataclass
class SleepAnalysis:
    """Complete sleep analysis result"""
    period_start: date
    period_end: date

    # Metrics
    avg_total_sleep: MetricSummary
    avg_deep_sleep: MetricSummary
    avg_rem_sleep: MetricSummary
    sleep_consistency: float  # 0-100 score

    # Patterns
    best_sleep_day: str  # e.g., "Saturday"
    worst_sleep_day: str
    optimal_bedtime: time

    # Insights
    insights: List[Insight] = field(default_factory=list)

    # Raw data for charts
    daily_data: List[Dict] = field(default_factory=list)

@dataclass
class RecoveryAnalysis:
    """Recovery and readiness analysis"""
    date: date

    # Scores
    recovery_score: int  # 0-100
    readiness_score: int  # 0-100
    body_battery_morning: int

    # Factors
    sleep_quality_factor: float
    stress_factor: float
    activity_factor: float
    hrv_factor: Optional[float]

    # Recommendation
    recommended_training: str  # "rest", "light", "moderate", "intense"
    insights: List[Insight] = field(default_factory=list)

@dataclass
class HealthReport:
    """Complete health report combining all analyses"""
    generated_at: datetime
    period_start: date
    period_end: date

    # Component analyses
    sleep: Optional[SleepAnalysis] = None
    recovery: Optional[RecoveryAnalysis] = None
    stress: Optional[StressAnalysis] = None
    activities: Optional[ActivityAnalysis] = None

    # Cross-domain insights
    key_insights: List[Insight] = field(default_factory=list)

    # Metadata for LLM context
    metadata: Dict[str, Any] = field(default_factory=dict)
```

#### 2.3 Analyzer Classes

```python
# garmindb/analysis/sleep_analyzer.py
from datetime import date, timedelta
from typing import List
from ..data.repositories.base import HealthRepository
from .models import SleepAnalysis, MetricSummary, Insight, TrendDirection

class SleepAnalyzer:
    """Analyzes sleep data and generates insights"""

    def __init__(self, repository: HealthRepository):
        self.repository = repository

    def analyze(self, start: date, end: date) -> SleepAnalysis:
        """Run complete sleep analysis for period"""
        sleep_data = self.repository.get_sleep_data(start, end)

        if not sleep_data:
            return self._empty_analysis(start, end)

        return SleepAnalysis(
            period_start=start,
            period_end=end,
            avg_total_sleep=self._calc_total_sleep_summary(sleep_data),
            avg_deep_sleep=self._calc_deep_sleep_summary(sleep_data),
            avg_rem_sleep=self._calc_rem_sleep_summary(sleep_data),
            sleep_consistency=self._calc_consistency(sleep_data),
            best_sleep_day=self._find_best_day(sleep_data),
            worst_sleep_day=self._find_worst_day(sleep_data),
            optimal_bedtime=self._calc_optimal_bedtime(sleep_data),
            insights=self._generate_insights(sleep_data),
            daily_data=self._prepare_chart_data(sleep_data),
        )

    def _calc_total_sleep_summary(self, data: List) -> MetricSummary:
        """Calculate total sleep metrics with trend"""
        values = [d.total_sleep.total_seconds() / 3600 for d in data]
        current = values[-1] if values else 0
        avg_7d = sum(values[-7:]) / min(7, len(values)) if values else 0
        avg_30d = sum(values) / len(values) if values else 0

        trend = self._detect_trend(values)

        return MetricSummary(
            current_value=current,
            previous_value=values[-2] if len(values) > 1 else None,
            average_7d=avg_7d,
            average_30d=avg_30d,
            trend=trend,
            unit="hours"
        )

    def _generate_insights(self, data: List) -> List[Insight]:
        """Generate actionable insights from sleep data"""
        insights = []

        # Check for sleep debt
        avg_sleep = sum(d.total_sleep.total_seconds() for d in data) / len(data) / 3600
        if avg_sleep < 7:
            insights.append(Insight(
                title="Sleep Debt Detected",
                description=f"Average sleep of {avg_sleep:.1f}h is below recommended 7-9h",
                severity=InsightSeverity.WARNING,
                category="sleep",
                recommendations=[
                    "Try going to bed 30 minutes earlier",
                    "Limit screen time 1 hour before bed",
                    "Keep consistent sleep schedule on weekends"
                ]
            ))

        # Check deep sleep percentage
        # ... more insight logic

        return insights
```

#### 2.4 Main Analysis API

```python
# garmindb/analysis/__init__.py
from datetime import date
from typing import Optional
from ..data.repositories.base import HealthRepository
from .models import HealthReport
from .sleep_analyzer import SleepAnalyzer
from .recovery_analyzer import RecoveryAnalyzer
from .stress_analyzer import StressAnalyzer
from .activity_analyzer import ActivityAnalyzer

class HealthAnalyzer:
    """Main entry point for health analysis"""

    def __init__(self, repository: HealthRepository):
        self.repository = repository
        self.sleep = SleepAnalyzer(repository)
        self.recovery = RecoveryAnalyzer(repository)
        self.stress = StressAnalyzer(repository)
        self.activity = ActivityAnalyzer(repository)

    def daily_report(self, day: date) -> HealthReport:
        """Generate daily health report"""
        return self.generate_report(day, day)

    def weekly_report(self, end_date: Optional[date] = None) -> HealthReport:
        """Generate weekly health report"""
        end = end_date or date.today()
        start = end - timedelta(days=7)
        return self.generate_report(start, end)

    def generate_report(self, start: date, end: date) -> HealthReport:
        """Generate comprehensive health report for period"""
        return HealthReport(
            generated_at=datetime.now(),
            period_start=start,
            period_end=end,
            sleep=self.sleep.analyze(start, end),
            recovery=self.recovery.analyze(end),  # Recovery is point-in-time
            stress=self.stress.analyze(start, end),
            activities=self.activity.analyze(start, end),
            key_insights=self._cross_domain_insights(start, end),
            metadata=self._build_metadata()
        )
```

---

### Layer 3: Presentation Layer (Multiple Outputs)

The Presentation Layer converts analysis results into various output formats.

#### 3.1 Module Structure

```
garmindb/
├── presentation/
│   ├── __init__.py
│   ├── base.py              # Base presenter interface
│   ├── markdown/
│   │   ├── __init__.py
│   │   ├── renderer.py      # Markdown rendering
│   │   ├── charts.py        # Static chart generation
│   │   └── templates/       # Markdown templates
│   ├── web/
│   │   ├── __init__.py
│   │   ├── api.py           # FastAPI REST endpoints
│   │   ├── schemas.py       # Pydantic response schemas
│   │   └── static/          # Web assets
│   ├── notebook/
│   │   ├── __init__.py
│   │   └── widgets.py       # Jupyter widget helpers
│   └── cli/
│       ├── __init__.py
│       └── output.py        # CLI formatted output
```

#### 3.2 Presenter Interface

```python
# garmindb/presentation/base.py
from abc import ABC, abstractmethod
from ..analysis.models import HealthReport, SleepAnalysis

class Presenter(ABC):
    """Base interface for all presenters"""

    @abstractmethod
    def render_report(self, report: HealthReport) -> str:
        """Render complete health report"""
        pass

    @abstractmethod
    def render_sleep(self, analysis: SleepAnalysis) -> str:
        """Render sleep analysis section"""
        pass
```

#### 3.3 Markdown Presenter

```python
# garmindb/presentation/markdown/renderer.py
from ..base import Presenter
from ...analysis.models import HealthReport, SleepAnalysis, MetricSummary
from .charts import ChartGenerator

class MarkdownPresenter(Presenter):
    """Renders analysis results as Markdown"""

    def __init__(self, include_charts: bool = True, chart_dir: str = "./charts"):
        self.include_charts = include_charts
        self.chart_gen = ChartGenerator(output_dir=chart_dir)

    def render_report(self, report: HealthReport) -> str:
        """Render complete health report as Markdown"""
        sections = []

        # Header with metadata
        sections.append(self._render_header(report))

        # Executive summary
        sections.append(self._render_summary(report))

        # Individual sections
        if report.sleep:
            sections.append(self.render_sleep(report.sleep))
        if report.recovery:
            sections.append(self._render_recovery(report.recovery))
        if report.stress:
            sections.append(self._render_stress(report.stress))
        if report.activities:
            sections.append(self._render_activities(report.activities))

        # Key insights
        sections.append(self._render_insights(report.key_insights))

        return "\n\n".join(sections)

    def render_sleep(self, analysis: SleepAnalysis) -> str:
        """Render sleep analysis section"""
        md = ["## Sleep Analysis"]
        md.append(f"\n*Period: {analysis.period_start} to {analysis.period_end}*\n")

        # Summary table
        md.append("### Summary")
        md.append(self._metric_table([
            ("Total Sleep", analysis.avg_total_sleep),
            ("Deep Sleep", analysis.avg_deep_sleep),
            ("REM Sleep", analysis.avg_rem_sleep),
        ]))

        # Patterns
        md.append("\n### Patterns")
        md.append(f"- **Best Sleep Day**: {analysis.best_sleep_day}")
        md.append(f"- **Optimal Bedtime**: {analysis.optimal_bedtime}")
        md.append(f"- **Consistency Score**: {analysis.sleep_consistency}/100")

        # Chart
        if self.include_charts:
            chart_path = self.chart_gen.sleep_chart(analysis.daily_data)
            md.append(f"\n![Sleep Trends]({chart_path})")

        # Insights
        if analysis.insights:
            md.append("\n### Insights")
            for insight in analysis.insights:
                md.append(self._render_single_insight(insight))

        return "\n".join(md)

    def _metric_table(self, metrics: List[tuple]) -> str:
        """Render metrics as markdown table"""
        lines = ["| Metric | Current | 7-day Avg | Trend |",
                 "|--------|---------|-----------|-------|"]
        for name, metric in metrics:
            trend_icon = {"improving": "↑", "declining": "↓", "stable": "→"}
            lines.append(
                f"| {name} | {metric.current_value:.1f} {metric.unit} | "
                f"{metric.average_7d:.1f} {metric.unit} | "
                f"{trend_icon.get(metric.trend.value, '?')} |"
            )
        return "\n".join(lines)

    def _render_header(self, report: HealthReport) -> str:
        """Render LLM-friendly header with metadata"""
        return f"""---
report_type: health_analysis
generated: {report.generated_at.isoformat()}
period: {report.period_start} to {report.period_end}
data_source: garmin_connect
---

# Health Report: {report.period_start} to {report.period_end}

*Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M')}*"""
```

#### 3.4 Web API Presenter (FastAPI)

```python
# garmindb/presentation/web/api.py
from fastapi import FastAPI, Query
from datetime import date, timedelta
from pydantic import BaseModel
from typing import List, Optional

from ...analysis import HealthAnalyzer
from ...analysis.models import HealthReport
from ...data.repositories.sqlite_repository import SQLiteHealthRepository

app = FastAPI(title="GarminDB Health API", version="1.0.0")

# Dependency injection
def get_analyzer():
    from garmindb import GarminConnectConfigManager
    config = GarminConnectConfigManager()
    repo = SQLiteHealthRepository(config.get_db_params())
    return HealthAnalyzer(repo)

# Pydantic response models
class MetricResponse(BaseModel):
    current_value: float
    average_7d: Optional[float]
    trend: str
    unit: str

class SleepResponse(BaseModel):
    total_sleep: MetricResponse
    deep_sleep: MetricResponse
    rem_sleep: MetricResponse
    consistency_score: float
    insights: List[dict]

class HealthReportResponse(BaseModel):
    period_start: date
    period_end: date
    sleep: Optional[SleepResponse]
    # ... other sections

# Endpoints
@app.get("/api/health/daily", response_model=HealthReportResponse)
async def get_daily_report(
    day: date = Query(default=None, description="Date for report (default: today)")
):
    """Get daily health report"""
    analyzer = get_analyzer()
    report = analyzer.daily_report(day or date.today())
    return _convert_to_response(report)

@app.get("/api/health/weekly", response_model=HealthReportResponse)
async def get_weekly_report(
    end_date: date = Query(default=None)
):
    """Get weekly health report"""
    analyzer = get_analyzer()
    return _convert_to_response(analyzer.weekly_report(end_date))

@app.get("/api/sleep/analysis")
async def get_sleep_analysis(
    start: date = Query(...),
    end: date = Query(...)
):
    """Get detailed sleep analysis"""
    analyzer = get_analyzer()
    analysis = analyzer.sleep.analyze(start, end)
    return analysis

@app.get("/api/health/insights")
async def get_insights(days: int = Query(default=7, ge=1, le=90)):
    """Get actionable health insights"""
    analyzer = get_analyzer()
    end = date.today()
    start = end - timedelta(days=days)
    report = analyzer.generate_report(start, end)
    return {"insights": report.key_insights}
```

#### 3.5 Notebook Helper

```python
# garmindb/presentation/notebook/widgets.py
from IPython.display import display, Markdown, HTML
import matplotlib.pyplot as plt
from ...analysis.models import HealthReport, SleepAnalysis

class NotebookPresenter:
    """Helper for displaying analysis in Jupyter notebooks"""

    def display_report(self, report: HealthReport):
        """Display full report in notebook"""
        display(Markdown(f"# Health Report: {report.period_start} to {report.period_end}"))

        if report.sleep:
            self.display_sleep(report.sleep)
        # ... other sections

    def display_sleep(self, analysis: SleepAnalysis):
        """Display sleep analysis with interactive charts"""
        display(Markdown("## Sleep Analysis"))

        # Summary metrics
        self._display_metrics_table(analysis)

        # Interactive chart
        fig, ax = plt.subplots(figsize=(12, 6))
        self._plot_sleep_trends(ax, analysis.daily_data)
        plt.show()

        # Insights as callouts
        for insight in analysis.insights:
            self._display_insight_card(insight)
```

---

## Updated Module Structure

```
garmindb/
├── __init__.py
├── data/                      # DATA LAYER
│   ├── __init__.py
│   ├── models.py              # DTOs (SleepRecord, etc.)
│   ├── repositories/
│   │   ├── __init__.py
│   │   ├── base.py            # Repository interface
│   │   └── sqlite.py          # SQLite implementation
│   └── sync/                  # Garmin sync (existing)
│       └── ...
│
├── analysis/                  # ANALYSIS LAYER
│   ├── __init__.py            # Main HealthAnalyzer
│   ├── models.py              # Analysis result models
│   ├── sleep_analyzer.py
│   ├── recovery_analyzer.py
│   ├── stress_analyzer.py
│   ├── activity_analyzer.py
│   └── insights.py
│
├── presentation/              # PRESENTATION LAYER
│   ├── __init__.py
│   ├── base.py                # Presenter interface
│   ├── markdown/
│   │   ├── renderer.py
│   │   └── charts.py
│   ├── web/
│   │   ├── api.py             # FastAPI app
│   │   └── schemas.py
│   ├── notebook/
│   │   └── widgets.py
│   └── cli/
│       └── output.py
│
├── garmindb/                  # EXISTING (refactor gradually)
│   └── ...
│
└── scripts/
    └── garmindb_cli.py        # Add report commands
```

---

## Future: Web Application for Friends

With the layered architecture in place, creating a web app becomes straightforward.

### Web App Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            FRONTEND (React/Vue)                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Dashboard   │  │   Sleep      │  │  Activities  │  │   Compare    │    │
│  │   Overview   │  │   Analysis   │  │   History    │  │   Friends    │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
                              REST API / GraphQL
                                     │
┌─────────────────────────────────────────────────────────────────────────────┐
│                         BACKEND (FastAPI)                                    │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │    Auth      │  │   Health     │  │   Social     │  │   Export     │    │
│  │   (OAuth)    │  │   Endpoints  │  │   Features   │  │   (PDF/MD)   │    │
│  └──────────────┘  └──────────────┘  └──────────────┘  └──────────────┘    │
│                                     │                                        │
│                          ┌──────────▼──────────┐                            │
│                          │   Analysis Layer    │ ◄── Reused from CLI!       │
│                          │   (HealthAnalyzer)  │                            │
│                          └──────────┬──────────┘                            │
│                                     │                                        │
│                          ┌──────────▼──────────┐                            │
│                          │   Data Layer        │                            │
│                          │   (Repository)      │                            │
│                          └─────────────────────┘                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                     │
┌─────────────────────────────────────────────────────────────────────────────┐
│                              DATABASE                                        │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐                      │
│  │  User SQLite │  │  Friend's    │  │   Shared     │                      │
│  │  (local)     │  │   SQLite     │  │   PostgreSQL │                      │
│  └──────────────┘  └──────────────┘  └──────────────┘                      │
│                              or                                              │
│                    Central PostgreSQL with user data                         │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Social Features

```python
# Future: garmindb/presentation/web/social.py
from fastapi import APIRouter, Depends
from typing import List

router = APIRouter(prefix="/social", tags=["social"])

@router.get("/friends/{friend_id}/comparison")
async def compare_with_friend(
    friend_id: str,
    metric: str,  # sleep, stress, activities
    period: int = 7  # days
):
    """Compare your metrics with a friend"""
    my_analysis = get_my_analysis(period)
    friend_analysis = get_friend_analysis(friend_id, period)

    return {
        "my_data": my_analysis,
        "friend_data": friend_analysis,
        "comparison": generate_comparison(my_analysis, friend_analysis)
    }

@router.get("/leaderboard")
async def get_leaderboard(
    metric: str = "steps",
    period: str = "week"
):
    """Get weekly leaderboard among friends"""
    pass

@router.post("/challenges")
async def create_challenge(challenge: ChallengeCreate):
    """Create a fitness challenge with friends"""
    pass
```

### Deployment Options

| Option | Pros | Cons | Best For |
|--------|------|------|----------|
| **Local + Tailscale** | Free, private, simple | Each friend needs setup | Tech-savvy friends |
| **Docker + VPS** | Full control, one instance | Monthly cost (~$5-10) | Small group |
| **Fly.io/Railway** | Easy deploy, auto-scaling | Usage-based cost | Growing group |
| **Self-hosted + Cloudflare Tunnel** | Free hosting, secure | Needs always-on server | Home server owners |

---

## Revised Implementation Phases

### Phase 1: Foundation (Week 1-2)
**Goal: Create the layered architecture skeleton**

- [ ] Create `data/models.py` with DTOs
- [ ] Create `data/repositories/base.py` interface
- [ ] Create `data/repositories/sqlite.py` implementation
- [ ] Write tests for repository layer

### Phase 2: Analysis Layer (Week 2-4)
**Goal: Port notebook logic to analyzers**

- [ ] Create `analysis/models.py` with result types
- [ ] Implement `SleepAnalyzer` (port from `custom_sleep_analysis.ipynb`)
- [ ] Implement `RecoveryAnalyzer` (port from `custom_recovery_analysis.ipynb`)
- [ ] Implement `StressAnalyzer` (port from `custom_stress_analysis.ipynb`)
- [ ] Implement `ActivityAnalyzer`
- [ ] Create `HealthAnalyzer` main entry point
- [ ] Write tests for all analyzers

### Phase 3: Markdown Presenter (Week 4-5)
**Goal: Generate LLM-friendly reports**

- [ ] Create `presentation/markdown/renderer.py`
- [ ] Create `presentation/markdown/charts.py` for static charts
- [ ] Add CLI commands: `garmindb_cli.py --report daily|weekly|monthly`
- [ ] Test with Claude/GPT for LLM compatibility

### Phase 4: Notebook Integration (Week 5-6)
**Goal: Update notebooks to use new architecture**

- [ ] Create `presentation/notebook/widgets.py`
- [ ] Refactor existing notebooks to use `HealthAnalyzer`
- [ ] Keep notebooks for interactive exploration
- [ ] Document notebook usage

### Phase 5: Web API (Week 6-8)
**Goal: REST API for future web app**

- [ ] Create FastAPI app in `presentation/web/api.py`
- [ ] Implement health endpoints
- [ ] Add authentication (optional for local use)
- [ ] Create OpenAPI documentation

### Phase 6: Web Frontend (Future)
**Goal: Web dashboard for friends**

- [ ] Choose frontend framework (React/Vue/Svelte)
- [ ] Create dashboard components
- [ ] Implement friend comparison features
- [ ] Deploy to hosting platform

---

## Usage Examples After Implementation

### CLI Usage

```bash
# Generate daily markdown report
garmindb_cli.py --report daily --output ~/Reports/daily.md

# Generate weekly report for specific dates
garmindb_cli.py --report weekly --start 2025-01-01 --end 2025-01-07

# Generate LLM-ready report (extra metadata)
garmindb_cli.py --report weekly --format llm --output report.md
```

### Python Usage

```python
from garmindb.data.repositories import SQLiteHealthRepository
from garmindb.analysis import HealthAnalyzer
from garmindb.presentation.markdown import MarkdownPresenter

# Setup
repo = SQLiteHealthRepository(db_params)
analyzer = HealthAnalyzer(repo)

# Generate analysis
report = analyzer.weekly_report()

# Render as markdown
presenter = MarkdownPresenter()
markdown = presenter.render_report(report)

# Save or send to LLM
with open("weekly_report.md", "w") as f:
    f.write(markdown)
```

### Notebook Usage

```python
from garmindb.analysis import HealthAnalyzer
from garmindb.presentation.notebook import NotebookPresenter

analyzer = HealthAnalyzer(repo)
presenter = NotebookPresenter()

# Display interactive report in notebook
report = analyzer.weekly_report()
presenter.display_report(report)

# Or get specific analysis
sleep = analyzer.sleep.analyze(start, end)
presenter.display_sleep(sleep)
```

### Web API Usage

```bash
# Get daily report
curl http://localhost:8000/api/health/daily?day=2025-01-15

# Get sleep analysis
curl "http://localhost:8000/api/sleep/analysis?start=2025-01-01&end=2025-01-15"

# Get insights
curl http://localhost:8000/api/health/insights?days=7
```

---

## Technical Considerations

### Dependencies to Add

```toml
# pyproject.toml additions
[project.optional-dependencies]
reports = [
    "jinja2>=3.0",      # Template rendering
    "tabulate>=0.9",    # Table formatting
    "rich>=13.0",       # Terminal output (optional)
]
```

### Configuration

```json
// ~/.GarminDb/GarminConnectConfig.json additions
{
    "reports": {
        "output_dir": "~/HealthData/Reports",
        "default_format": "markdown",
        "include_charts": true,
        "chart_style": "seaborn",
        "llm_metadata": true
    }
}
```

---

## Success Metrics

1. **All core notebooks converted** to report modules
2. **CLI integration** working for all report types
3. **LLM compatibility** validated with Claude/GPT
4. **Test coverage** for report generation
5. **Documentation** updated

---

## Resources

### Research Sources

- [mkreports - Markdown Data Analysis Reports](https://github.com/hhoeflin/mkreports)
- [marimo - AI-native Python notebooks](https://marimo.io/)
- [Garmin-Grafana Project](https://github.com/arpanghosh8453/garmin-grafana)
- [Why Markdown is Best for LLMs](https://medium.com/@wetrocloud/why-markdown-is-the-best-format-for-llms-aa0514a409a7)
- [LLM-Friendly Content in Markdown](https://developer.webex.com/blog/boosting-ai-performance-the-power-of-llm-friendly-content-in-markdown)
- [Python Data Visualization Libraries 2025](https://www.anaconda.com/topics/data-visualization-examples)
- [Automating Data Analysis Reporting](https://medium.com/@shouke.wei/from-scripts-to-reports-automating-data-analysis-reporting-in-python-0f7778363331)

### Related Projects

- [GarminDB Original](https://github.com/tcgoetz/GarminDB)
- [garminconnect API](https://pypi.org/project/garminconnect/)
- [Medical LLMs Practical Guide](https://github.com/AI-in-Health/MedLLMsPracticalGuide)

---

## Next Steps

### Immediate (This Week)
1. [ ] Review and approve this architecture plan
2. [ ] Decide on implementation priority (start with Phase 1 or jump to specific feature)

### Phase 1 Start
3. [ ] Create `garmindb/data/` module structure
4. [ ] Implement Repository interface and SQLite implementation
5. [ ] Create DTO models (SleepRecord, HeartRateRecord, etc.)

### Proof of Concept
6. [ ] Implement `SleepAnalyzer` as first analyzer
7. [ ] Create basic `MarkdownPresenter`
8. [ ] Generate first LLM-compatible report
9. [ ] Test with Claude for interpretation

### Future Considerations
- Evaluate [marimo](https://marimo.io/) as Jupyter replacement for interactive work
- Consider [mkreports](https://github.com/hhoeflin/mkreports) patterns for report generation
- Plan web app architecture for friend sharing

---

*Document created: 2025-12-27*
*Last updated: 2025-12-27*
*Architecture: Layered (Data → Analysis → Presentation)*
