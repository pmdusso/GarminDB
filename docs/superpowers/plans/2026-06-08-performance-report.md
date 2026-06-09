# Performance Report Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a performance-oriented Markdown report (W/kg · FTP · VO2max · weight · TSB + recovery) that works as a standalone snapshot and tracks deltas across runs, reachable via `generate_report.py --performance`.

**Architecture:** Reuse the existing `data → analysis → presentation` stack. Add a `PowerAnalyzer` that reads raw activity JSONs (power is NOT in the DB), a `performance_targets.json` config, a delta-state file, a `PerformanceReportBuilder` orchestrator, and a self-contained `PerformancePresenter`. No DB schema changes.

**Tech Stack:** Python 3.12, stdlib `json`/`sqlite3`/`dataclasses`, SQLAlchemy models (existing), pytest. Run tests one file at a time from repo root: `.venv/bin/python3 -m pytest test/<file>.py -v` (the repo has two `models.py`, so running all tests together breaks imports — always run per-file).

**Conventions:** Reuse `Insight`/`InsightSeverity`/`TrendDirection`/`MetricSummary` from `garmindb/analysis/models.py`. Activity JSONs live in `<db_path parent>/FitFiles/Activities/activity_*.json`; DBs dir is `db_params.db_path` (e.g. `~/HealthData/DBs`).

---

## File structure

| File | Responsibility | New/Modify |
|---|---|---|
| `garmindb/analysis/db_metrics.py` | Read VO2max via sqlite3 (not exposed by SQLAlchemy models) | Create |
| `garmindb/data/repositories/sqlite.py` | Add `get_weight_series()` | Modify |
| `garmindb/analysis/performance_targets.py` | Load FTP / weight / W-kg / race targets | Create |
| `garmindb/analysis/report_state.py` | Persist key metrics; compute deltas | Create |
| `garmindb/analysis/power_analyzer.py` | Parse JSON power → curve, FTP, zones, insights | Create |
| `garmindb/analysis/performance_report.py` | `PerformanceReport` model + `PerformanceReportBuilder` orchestrator | Create |
| `garmindb/presentation/markdown/performance_renderer.py` | Render `PerformanceReport` → Markdown | Create |
| `scripts/generate_report.py` | Add `--performance` branch | Modify |
| `garmindb/analysis/__init__.py` | Export new public classes | Modify |
| `test/test_*.py` | Tests per module | Create |

---

## Task 1: VO2max reader (sqlite3)

**Files:**
- Create: `garmindb/analysis/db_metrics.py`
- Test: `test/test_db_metrics.py`

- [ ] **Step 1: Write the failing test**

```python
# test/test_db_metrics.py
import os
import sqlite3
from datetime import date
from garmindb.analysis.db_metrics import get_latest_vo2max


def _make_activities_db(path):
    con = sqlite3.connect(path)
    con.execute("CREATE TABLE activities (activity_id INTEGER, start_time TIMESTAMP)")
    con.execute("CREATE TABLE cycle_activities (activity_id INTEGER, vo2_max FLOAT)")
    con.executemany("INSERT INTO activities VALUES (?, ?)",
                    [(1, "2026-05-01 10:00:00"), (2, "2026-05-20 10:00:00"), (3, "2025-01-01 10:00:00")])
    con.executemany("INSERT INTO cycle_activities VALUES (?, ?)",
                    [(1, 55.0), (2, 56.0), (3, 50.0)])
    con.commit()
    con.close()


def test_returns_max_vo2max_in_range(tmp_path):
    db_dir = str(tmp_path)
    _make_activities_db(os.path.join(db_dir, "garmin_activities.db"))
    result = get_latest_vo2max(db_dir, date(2026, 1, 1), date(2026, 6, 1))
    assert result == 56.0


def test_returns_none_when_no_data(tmp_path):
    db_dir = str(tmp_path)
    _make_activities_db(os.path.join(db_dir, "garmin_activities.db"))
    assert get_latest_vo2max(db_dir, date(2030, 1, 1), date(2030, 12, 31)) is None


def test_returns_none_when_db_missing(tmp_path):
    assert get_latest_vo2max(str(tmp_path), date(2026, 1, 1), date(2026, 6, 1)) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m pytest test/test_db_metrics.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'garmindb.analysis.db_metrics'`

- [ ] **Step 3: Write minimal implementation**

```python
# garmindb/analysis/db_metrics.py
"""Read-only metric helpers that go straight to sqlite.

Some GarminDB tables (e.g. cycle_activities.vo2_max) are not exposed
through the SQLAlchemy DTO repository, so we read them directly.
"""

import os
import sqlite3
from datetime import date
from typing import Optional


def get_latest_vo2max(db_dir: str, start_date: date, end_date: date) -> Optional[float]:
    """Return the max cycling VO2max recorded in [start_date, end_date].

    Args:
        db_dir: Directory containing garmin_activities.db.
        start_date: Inclusive range start.
        end_date: Inclusive range end.

    Returns:
        Max vo2_max as float, or None if no data / db missing.
    """
    path = os.path.join(db_dir, "garmin_activities.db")
    if not os.path.exists(path):
        return None
    con = sqlite3.connect(path)
    try:
        row = con.execute(
            "SELECT MAX(ca.vo2_max) FROM cycle_activities ca "
            "JOIN activities a ON ca.activity_id = a.activity_id "
            "WHERE ca.vo2_max IS NOT NULL AND date(a.start_time) BETWEEN ? AND ?",
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchone()
    finally:
        con.close()
    return float(row[0]) if row and row[0] is not None else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest test/test_db_metrics.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add garmindb/analysis/db_metrics.py test/test_db_metrics.py
git commit -m "feat(analysis): add sqlite VO2max reader (db_metrics)"
```

---

## Task 2: Weight series accessor on the repository

**Files:**
- Modify: `garmindb/data/repositories/sqlite.py`
- Test: `test/test_weight_series.py`

- [ ] **Step 1: Write the failing test**

```python
# test/test_weight_series.py
from datetime import date
from garmindb.data.repositories.sqlite import SQLiteHealthRepository


class _Row:
    def __init__(self, day, weight):
        self.day = day
        self.weight = weight


def test_get_weight_series_maps_and_sorts(monkeypatch, tmp_path):
    repo = SQLiteHealthRepository({"db_type": "sqlite", "db_path": str(tmp_path)})

    rows = [_Row(date(2026, 5, 20), 84.6), _Row(date(2026, 5, 3), 83.9), _Row(date(2026, 5, 10), None)]

    import garmindb.data.repositories.sqlite as sqlite_mod

    class _FakeWeight:
        @staticmethod
        def get_for_period(db, start_ts, end_ts):
            return rows

    monkeypatch.setattr(sqlite_mod, "_import_weight_model", lambda: _FakeWeight, raising=False)
    # Force the lazy garmin_db property to a sentinel (not used by the fake)
    repo._garmin_db = object()

    series = repo.get_weight_series(date(2026, 5, 1), date(2026, 5, 31))
    assert series == [(date(2026, 5, 3), 83.9), (date(2026, 5, 20), 84.6)]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m pytest test/test_weight_series.py -v`
Expected: FAIL with `AttributeError: 'SQLiteHealthRepository' object has no attribute 'get_weight_series'`

- [ ] **Step 3: Write minimal implementation**

Add this module-level helper near the top of `garmindb/data/repositories/sqlite.py` (after the imports, before the class) so the test can monkeypatch it:

```python
def _import_weight_model():
    """Import the GarminDB Weight model (indirection for testability)."""
    from garmindb.garmindb import Weight
    return Weight
```

Add this method to `SQLiteHealthRepository` (after `get_daily_summaries`):

```python
    def get_weight_series(
        self, start_date: date, end_date: date
    ) -> List[tuple]:
        """Get (date, weight_kg) pairs for the range, ordered by date.

        Args:
            start_date: Inclusive range start.
            end_date: Inclusive range end.

        Returns:
            List of (date, float) tuples sorted ascending by date.
        """
        Weight = _import_weight_model()
        start_ts = self._to_datetime(start_date)
        end_ts = self._to_datetime_end(end_date)
        raw = Weight.get_for_period(self.garmin_db, start_ts, end_ts)

        series = []
        for row in raw:
            try:
                if row.weight is not None:
                    series.append((self._to_date(row.day), float(row.weight)))
            except Exception:
                continue
        return sorted(series, key=lambda t: t[0])
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest test/test_weight_series.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add garmindb/data/repositories/sqlite.py test/test_weight_series.py
git commit -m "feat(data): add get_weight_series to SQLite repository"
```

---

## Task 3: Performance targets config

**Files:**
- Create: `garmindb/analysis/performance_targets.py`
- Test: `test/test_performance_targets.py`

- [ ] **Step 1: Write the failing test**

```python
# test/test_performance_targets.py
import json
from garmindb.analysis.performance_targets import (
    PerformanceTargets,
    load_performance_targets,
)


def test_missing_file_returns_empty_defaults():
    t = load_performance_targets("/nonexistent/targets.json")
    assert isinstance(t, PerformanceTargets)
    assert t.ftp_watts is None
    assert t.wkg_target is None


def test_loads_values(tmp_path):
    p = tmp_path / "targets.json"
    p.write_text(json.dumps({
        "ftp_watts": 325,
        "weight_target_kg": 80,
        "wkg_target": 4.0,
        "race_name": "L'Etape Campos do Jordao",
        "race_date": "2026-09-27",
    }))
    t = load_performance_targets(str(p))
    assert t.ftp_watts == 325
    assert t.weight_target_kg == 80
    assert t.wkg_target == 4.0
    assert t.race_name == "L'Etape Campos do Jordao"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m pytest test/test_performance_targets.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'garmindb.analysis.performance_targets'`

- [ ] **Step 3: Write minimal implementation**

```python
# garmindb/analysis/performance_targets.py
"""Performance goal configuration (FTP, weight/W-kg targets, race)."""

import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class PerformanceTargets:
    """User-configured performance targets. All fields optional."""

    ftp_watts: Optional[float] = None
    weight_target_kg: Optional[float] = None
    wkg_target: Optional[float] = None
    race_name: Optional[str] = None
    race_date: Optional[str] = None


def load_performance_targets(path: Optional[str] = None) -> PerformanceTargets:
    """Load targets from JSON. Returns empty defaults if file is missing.

    Args:
        path: Path to performance_targets.json. Defaults to
            ~/.GarminDb/performance_targets.json.

    Returns:
        PerformanceTargets (empty if file absent).
    """
    if path is None:
        path = os.path.join(
            os.path.expanduser("~"), ".GarminDb", "performance_targets.json"
        )
    if not os.path.exists(path):
        return PerformanceTargets()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return PerformanceTargets(
        ftp_watts=data.get("ftp_watts"),
        weight_target_kg=data.get("weight_target_kg"),
        wkg_target=data.get("wkg_target"),
        race_name=data.get("race_name"),
        race_date=data.get("race_date"),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest test/test_performance_targets.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add garmindb/analysis/performance_targets.py test/test_performance_targets.py
git commit -m "feat(analysis): add performance targets config loader"
```

---

## Task 4: Delta state (persist metrics, compute deltas)

**Files:**
- Create: `garmindb/analysis/report_state.py`
- Test: `test/test_report_state.py`

- [ ] **Step 1: Write the failing test**

```python
# test/test_report_state.py
from garmindb.analysis.report_state import (
    MetricDelta,
    load_last_metrics,
    save_metrics,
    compute_deltas,
)


def test_save_and_load_roundtrip(tmp_path):
    path = str(tmp_path / "reports" / "last_metrics.json")
    save_metrics(path, {"wkg": 3.81, "ftp": 325.0}, "2026-06-08T12:00:00")
    loaded = load_last_metrics(path)
    assert loaded["metrics"]["wkg"] == 3.81
    assert loaded["generated"] == "2026-06-08T12:00:00"


def test_load_missing_returns_none(tmp_path):
    assert load_last_metrics(str(tmp_path / "nope.json")) is None


def test_compute_deltas_first_run_has_no_previous():
    deltas = compute_deltas({"wkg": 3.81}, None)
    assert deltas["wkg"].current == 3.81
    assert deltas["wkg"].previous is None
    assert deltas["wkg"].delta is None
    assert deltas["wkg"].has_previous is False


def test_compute_deltas_with_previous():
    last = {"metrics": {"wkg": 3.71}}
    deltas = compute_deltas({"wkg": 3.81}, last)
    assert deltas["wkg"].previous == 3.71
    assert round(deltas["wkg"].delta, 2) == 0.10
    assert deltas["wkg"].has_previous is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m pytest test/test_report_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'garmindb.analysis.report_state'`

- [ ] **Step 3: Write minimal implementation**

```python
# garmindb/analysis/report_state.py
"""Persist key report metrics between runs to compute deltas.

State file shape: {"generated": "<iso>", "metrics": {name: value, ...}}
"""

import json
import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class MetricDelta:
    """A metric's current value vs the previous report's value."""

    current: float
    previous: Optional[float]
    delta: Optional[float]  # current - previous, or None on first run

    @property
    def has_previous(self) -> bool:
        return self.previous is not None


def load_last_metrics(path: str) -> Optional[dict]:
    """Load the previous report's state, or None if absent."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_metrics(path: str, metrics: Dict[str, float], generated_iso: str) -> None:
    """Write the current report's key metrics for next time."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"generated": generated_iso, "metrics": metrics}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def compute_deltas(
    current: Dict[str, float], last: Optional[dict]
) -> Dict[str, MetricDelta]:
    """Compute per-metric deltas vs the previous report (None-safe)."""
    prev_metrics = (last or {}).get("metrics", {})
    result: Dict[str, MetricDelta] = {}
    for name, value in current.items():
        prev = prev_metrics.get(name)
        delta = (value - prev) if prev is not None else None
        result[name] = MetricDelta(current=value, previous=prev, delta=delta)
    return result
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest test/test_report_state.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add garmindb/analysis/report_state.py test/test_report_state.py
git commit -m "feat(analysis): add report delta-state persistence"
```

---

## Task 5: PowerAnalyzer — parsing, power curve, FTP

**Files:**
- Create: `garmindb/analysis/power_analyzer.py`
- Test: `test/test_power_analyzer.py`

- [ ] **Step 1: Write the failing test**

```python
# test/test_power_analyzer.py
from datetime import date
from garmindb.analysis.power_analyzer import PowerAnalyzer, PowerRide


def test_parse_ride_extracts_power_fields():
    data = {
        "activityType": {"typeKey": "cycling"},
        "startTimeLocal": "2026-05-20 10:00:00",
        "avgPower": 200.0,
        "normPower": 230.0,
        "maxAvgPower_5": 600,
        "maxAvgPower_60": 400,
        "maxAvgPower_300": 320,
        "maxAvgPower_1200": 290,
        "maxAvgPower_3600": 250,
        "powerTimeInZone_1": 600.0,
        "powerTimeInZone_2": 1200.0,
    }
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None
    assert ride.date == date(2026, 5, 20)
    assert ride.sport == "cycling"
    assert ride.norm_power == 230.0
    assert ride.peak_power[1200] == 290
    assert ride.power_time_in_zone[1] == 600.0


def test_parse_ride_skips_non_cycling():
    data = {"activityType": {"typeKey": "running"}, "startTimeLocal": "2026-05-20 10:00:00"}
    assert PowerAnalyzer._parse_ride(data) is None


def test_parse_ride_skips_cycling_without_power():
    data = {"activityType": {"typeKey": "cycling"}, "startTimeLocal": "2026-05-20 10:00:00"}
    assert PowerAnalyzer._parse_ride(data) is None


def test_parse_ride_handles_list_payload():
    data = [{
        "activityType": {"typeKey": "virtual_ride"},
        "startTimeLocal": "2026-05-20 10:00:00",
        "maxAvgPower_1200": 280,
    }]
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None and ride.peak_power[1200] == 280


def test_best_curve_takes_max_per_duration():
    rides = [
        PowerRide(date(2026, 5, 1), "cycling", None, None, {1200: 280, 3600: 240}, {}),
        PowerRide(date(2026, 5, 2), "cycling", None, None, {1200: 305, 3600: 230}, {}),
    ]
    analyzer = PowerAnalyzer("/tmp/does-not-matter")
    curve = analyzer._best_curve(rides)
    assert curve[1200] == 305
    assert curve[3600] == 240
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m pytest test/test_power_analyzer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'garmindb.analysis.power_analyzer'`

- [ ] **Step 3: Write minimal implementation**

```python
# garmindb/analysis/power_analyzer.py
"""Cycling power analysis from raw Garmin activity JSONs.

Power data is NOT imported into the GarminDB tables, but the per-activity
JSON summaries (~/HealthData/FitFiles/Activities/activity_*.json) carry
Garmin's pre-computed power fields (normPower, maxAvgPower_<seconds>,
powerTimeInZone_<n>). This analyzer reads those at report time.
"""

import glob
import json
import os
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from .models import Insight, InsightSeverity

# Durations (seconds) shown on the power curve.
CURVE_DURATIONS = [5, 60, 300, 1200, 3600]
DURATION_LABELS = {5: "5s", 60: "1min", 300: "5min", 1200: "20min", 3600: "60min"}

CYCLING_TYPES = {
    "cycling", "virtual_ride", "road_biking", "indoor_cycling",
    "gravel_cycling", "mountain_biking",
}


@dataclass
class PowerRide:
    """One ride's parsed power summary."""

    date: date
    sport: str
    avg_power: Optional[float]
    norm_power: Optional[float]
    peak_power: Dict[int, float]          # duration_s -> best avg watts
    power_time_in_zone: Dict[int, float]  # zone (1..7) -> seconds


@dataclass
class PowerAnalysisResult:
    """Output of PowerAnalyzer.analyze()."""

    period_start: date
    period_end: date
    configured_ftp: Optional[float]
    estimated_ftp: Optional[float]        # best 20-min recent * 0.95
    best_20min_recent: Optional[float]
    best_20min_alltime: Optional[float]
    power_curve_recent: Dict[int, float]
    power_curve_alltime: Dict[int, float]
    power_zone_distribution: Dict[int, float]  # zone -> percent of time
    rides_with_power: int
    total_rides: int
    ftp_needs_test: bool
    insights: List[Insight] = field(default_factory=list)


class PowerAnalyzer:
    """Reads activity JSONs and computes power curve, FTP, zone mix."""

    RECENT_WINDOW_DAYS = 90

    def __init__(self, activities_dir: str, configured_ftp: Optional[float] = None):
        """Args:
            activities_dir: Folder with activity_*.json files.
            configured_ftp: User's declared FTP (authoritative if set).
        """
        self._dir = activities_dir
        self._ftp = configured_ftp

    @staticmethod
    def _parse_ride(data) -> Optional["PowerRide"]:
        """Parse one activity JSON payload into a PowerRide, or None.

        Returns None for non-cycling activities or cycling rides with no
        power data. Accepts either a dict or a 1-element list payload.
        """
        if isinstance(data, list):
            data = data[0] if data else {}
        if not isinstance(data, dict):
            return None
        sport = (data.get("activityType") or {}).get("typeKey", "")
        if sport not in CYCLING_TYPES:
            return None

        peak = {}
        for d in CURVE_DURATIONS:
            val = data.get(f"maxAvgPower_{d}")
            if val is not None:
                peak[d] = float(val)
        if not peak and data.get("normPower") is None:
            return None  # cycling ride but no usable power

        zones = {}
        for z in range(1, 8):
            val = data.get(f"powerTimeInZone_{z}")
            if val is not None:
                zones[z] = float(val)

        start = (data.get("startTimeLocal") or "")[:10]
        try:
            ride_date = datetime.strptime(start, "%Y-%m-%d").date()
        except ValueError:
            return None

        return PowerRide(
            date=ride_date,
            sport=sport,
            avg_power=data.get("avgPower"),
            norm_power=data.get("normPower"),
            peak_power=peak,
            power_time_in_zone=zones,
        )

    def _best_curve(self, rides: List["PowerRide"]) -> Dict[int, float]:
        """Best (max) average power per duration across rides."""
        curve: Dict[int, float] = {}
        for d in CURVE_DURATIONS:
            vals = [r.peak_power[d] for r in rides if d in r.peak_power]
            if vals:
                curve[d] = max(vals)
        return curve
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest test/test_power_analyzer.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add garmindb/analysis/power_analyzer.py test/test_power_analyzer.py
git commit -m "feat(analysis): add PowerAnalyzer parsing and power-curve core"
```

---

## Task 6: PowerAnalyzer — zone mix, insights, full `analyze()`

**Files:**
- Modify: `garmindb/analysis/power_analyzer.py`
- Test: `test/test_power_analyzer_analyze.py`

- [ ] **Step 1: Write the failing test**

```python
# test/test_power_analyzer_analyze.py
import json
import os
from datetime import date
from garmindb.analysis.power_analyzer import PowerAnalyzer


def _write_ride(folder, activity_id, day, **fields):
    payload = {
        "activityType": {"typeKey": "cycling"},
        "startTimeLocal": f"{day} 10:00:00",
    }
    payload.update(fields)
    with open(os.path.join(folder, f"activity_{activity_id}.json"), "w") as f:
        json.dump(payload, f)


def test_analyze_builds_result(tmp_path):
    folder = str(tmp_path)
    _write_ride(folder, 1, "2026-05-20", maxAvgPower_1200=290, maxAvgPower_3600=250,
                powerTimeInZone_1=600.0, powerTimeInZone_2=1400.0)
    _write_ride(folder, 2, "2026-06-01", maxAvgPower_1200=305, maxAvgPower_3600=240,
                powerTimeInZone_2=1000.0, powerTimeInZone_3=500.0)

    analyzer = PowerAnalyzer(folder, configured_ftp=325)
    result = analyzer.analyze(date(2026, 5, 1), date(2026, 6, 7))

    assert result.rides_with_power == 2
    assert result.best_20min_recent == 305
    assert result.estimated_ftp == round(305 * 0.95)
    assert result.configured_ftp == 325
    # configured (325) > observed best-20min (305) -> recommend a test
    assert result.ftp_needs_test is True
    # zone distribution sums to ~100
    assert abs(sum(result.power_zone_distribution.values()) - 100.0) < 0.1
    # an FTP-test insight should be present
    assert any("FTP" in i.title for i in result.insights)


def test_analyze_empty_dir(tmp_path):
    analyzer = PowerAnalyzer(str(tmp_path), configured_ftp=325)
    result = analyzer.analyze(date(2026, 5, 1), date(2026, 6, 7))
    assert result.rides_with_power == 0
    assert result.best_20min_recent is None
    assert result.ftp_needs_test is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m pytest test/test_power_analyzer_analyze.py -v`
Expected: FAIL with `AttributeError: 'PowerAnalyzer' object has no attribute 'analyze'`

- [ ] **Step 3: Write minimal implementation**

Append these methods to the `PowerAnalyzer` class in `garmindb/analysis/power_analyzer.py`:

```python
    def _load_rides(self) -> List["PowerRide"]:
        """Glob the activities dir and parse all cycling rides with power."""
        rides: List[PowerRide] = []
        if not os.path.isdir(self._dir):
            return rides
        for path in glob.glob(os.path.join(self._dir, "activity_*.json")):
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue
            ride = self._parse_ride(data)
            if ride is not None:
                rides.append(ride)
        return rides

    @staticmethod
    def _zone_distribution(rides: List["PowerRide"]) -> Dict[int, float]:
        """Aggregate time-in-power-zone across rides into percentages."""
        totals: Dict[int, float] = {}
        for ride in rides:
            for zone, secs in ride.power_time_in_zone.items():
                totals[zone] = totals.get(zone, 0.0) + secs
        grand = sum(totals.values())
        if grand == 0:
            return {}
        return {z: round(secs / grand * 100, 1) for z, secs in sorted(totals.items())}

    def analyze(self, start_date: date, end_date: date) -> "PowerAnalysisResult":
        """Build a PowerAnalysisResult for the period.

        'recent' = last RECENT_WINDOW_DAYS before end_date (current form);
        'alltime' = every ride on disk (personal bests).
        """
        all_rides = self._load_rides()
        recent_start = end_date - timedelta(days=self.RECENT_WINDOW_DAYS)
        recent = [r for r in all_rides if recent_start <= r.date <= end_date]

        curve_recent = self._best_curve(recent)
        curve_all = self._best_curve(all_rides)
        best20_recent = curve_recent.get(1200)
        best20_all = curve_all.get(1200)
        est_ftp = round(best20_recent * 0.95) if best20_recent else None
        ftp_needs_test = bool(
            self._ftp and best20_recent and self._ftp > best20_recent
        )

        result = PowerAnalysisResult(
            period_start=start_date,
            period_end=end_date,
            configured_ftp=self._ftp,
            estimated_ftp=est_ftp,
            best_20min_recent=best20_recent,
            best_20min_alltime=best20_all,
            power_curve_recent=curve_recent,
            power_curve_alltime=curve_all,
            power_zone_distribution=self._zone_distribution(recent),
            rides_with_power=len(recent),
            total_rides=len(all_rides),
            ftp_needs_test=ftp_needs_test,
        )
        result.insights = self._build_insights(result)
        return result

    def _build_insights(self, result: "PowerAnalysisResult") -> List[Insight]:
        """Generate power insights (FTP test recommendation, etc.)."""
        insights: List[Insight] = []
        if result.ftp_needs_test:
            insights.append(Insight(
                title="Confirme sua FTP com um teste",
                description=(
                    f"Sua FTP configurada ({result.configured_ftp:.0f} W) é maior "
                    f"que o melhor esforço de 20 min dos seus dados recentes "
                    f"({result.best_20min_recent:.0f} W). Um teste de FTP "
                    f"confirmaria o número atual."
                ),
                severity=InsightSeverity.INFO,
                category="power",
                data_points={
                    "configured_ftp": result.configured_ftp,
                    "best_20min_recent": result.best_20min_recent,
                },
                recommendations=[
                    "Faça um teste de 20 min ou rampa nas próximas 2 semanas",
                ],
            ))
        return insights
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest test/test_power_analyzer_analyze.py test/test_power_analyzer.py -v`
Expected: PASS (7 passed total)

- [ ] **Step 5: Commit**

```bash
git add garmindb/analysis/power_analyzer.py test/test_power_analyzer_analyze.py
git commit -m "feat(analysis): PowerAnalyzer zone mix, insights, analyze()"
```

---

## Task 7: PerformanceReport model + builder

**Files:**
- Create: `garmindb/analysis/performance_report.py`
- Test: `test/test_performance_report.py`

The builder orchestrates: PowerAnalyzer + ActivityAnalyzer + RecoveryAnalyzer + SleepAnalyzer + StressAnalyzer + weight series + VO2max + targets + deltas. It computes W/kg, the scorecard, a readiness light from `RecoveryAnalysisResult.recovery_score`, and top-3 priorities from the union of all insights.

- [ ] **Step 1: Write the failing test**

```python
# test/test_performance_report.py
from datetime import date, datetime
from garmindb.analysis.performance_report import (
    PerformanceReportBuilder, ScorecardRow,
)
from garmindb.analysis.performance_targets import PerformanceTargets
from garmindb.analysis.models import (
    ActivityAnalysisResult, TrainingStressMetrics, RecoveryAnalysisResult,
    SleepAnalysisResult, StressAnalysisResult, MetricSummary, Insight,
    InsightSeverity, TrendDirection,
)


class _StubRepo:
    def get_weight_series(self, s, e):
        return [(date(2026, 5, 3), 84.0), (date(2026, 5, 27), 85.0)]


def _activity_result():
    r = ActivityAnalysisResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        total_activities=20, total_duration_hours=24.8,
        total_distance_km=509.0, total_calories=15000,
        training_stress=TrainingStressMetrics(
            atl=62.0, ctl=76.0, tsb=13.0, monotony=0.6, strain=247.0,
            confidence_score=0.9),
    )
    return r


def _recovery_result(score):
    return RecoveryAnalysisResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        recovery_score=score, recovery_trend=TrendDirection.STABLE,
        rhr_summary=MetricSummary("RHR", 55.0, "bpm"),
        body_battery_summary=MetricSummary("BB", 45.0, "%"),
        training_load_summary=MetricSummary("Load", 2000.0, "TSS"),
        rhr_baseline=50.0, rhr_deviation=5.0, weekly_tss=2000.0,
        insights=[Insight("Elevated RHR", "RHR up", InsightSeverity.WARNING, "recovery")],
    )


def _sleep_result():
    return SleepAnalysisResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        avg_total_sleep=MetricSummary("Sleep", 7.1, "hours"),
        avg_deep_sleep=MetricSummary("Deep", 16.0, "%"),
        avg_rem_sleep=MetricSummary("REM", 17.0, "%"),
        sleep_consistency_score=50.0,
    )


def _stress_result():
    return StressAnalysisResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        avg_stress=MetricSummary("Stress", 32.0, ""),
        low_stress_percent=47.0, medium_stress_percent=34.0, high_stress_percent=19.0,
    )


def _build(monkeypatch, recovery_score=60, last_metrics=None):
    import garmindb.analysis.performance_report as mod
    monkeypatch.setattr(mod, "_run_power", lambda d, ftp, s, e: _power_stub(ftp))
    monkeypatch.setattr(mod, "_run_activity", lambda repo, s, e: _activity_result())
    monkeypatch.setattr(mod, "_run_recovery", lambda repo, s, e: _recovery_result(recovery_score))
    monkeypatch.setattr(mod, "_run_sleep", lambda repo, s, e: _sleep_result())
    monkeypatch.setattr(mod, "_run_stress", lambda repo, s, e: _stress_result())
    monkeypatch.setattr(mod, "get_latest_vo2max", lambda d, s, e: 56.0)
    builder = PerformanceReportBuilder(
        repository=_StubRepo(), db_dir="/tmp/db", activities_dir="/tmp/acts",
        targets=PerformanceTargets(ftp_watts=325, weight_target_kg=80, wkg_target=4.0,
                                   race_name="L'Etape", race_date="2026-09-27"),
        last_metrics=last_metrics,
    )
    return builder.build(date(2026, 5, 9), date(2026, 6, 7),
                         datetime(2026, 6, 8, 12, 0, 0))


def _power_stub(ftp):
    from garmindb.analysis.power_analyzer import PowerAnalysisResult
    return PowerAnalysisResult(
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        configured_ftp=ftp, estimated_ftp=267, best_20min_recent=281,
        best_20min_alltime=319, power_curve_recent={1200: 281},
        power_curve_alltime={1200: 319}, power_zone_distribution={2: 100.0},
        rides_with_power=12, total_rides=12, ftp_needs_test=True, insights=[],
    )


def test_builds_wkg_and_scorecard(monkeypatch):
    report = _build(monkeypatch)
    # current weight = mean(84, 85) = 84.5; wkg = 325 / 84.5
    assert round(report.current_weight_kg, 1) == 84.5
    assert round(report.wkg_current, 2) == round(325 / 84.5, 2)
    labels = [row.label for row in report.scorecard]
    assert "W/kg" in labels and "FTP" in labels and "Peso" in labels


def test_readiness_light_from_recovery_score(monkeypatch):
    assert _build(monkeypatch, recovery_score=80).readiness_light == "🟢"
    assert _build(monkeypatch, recovery_score=60).readiness_light == "🟡"
    assert _build(monkeypatch, recovery_score=40).readiness_light == "🔴"


def test_priorities_lead_with_severe_insights(monkeypatch):
    report = _build(monkeypatch)
    assert len(report.priorities) >= 1
    # the WARNING recovery insight must outrank any INFO/POSITIVE
    assert "Elevated RHR" in report.priorities[0]


def test_deltas_present_with_prior(monkeypatch):
    last = {"metrics": {"wkg": 3.7}}
    report = _build(monkeypatch, last_metrics=last)
    assert report.deltas["wkg"].has_previous is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m pytest test/test_performance_report.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'garmindb.analysis.performance_report'`

- [ ] **Step 3: Write minimal implementation**

```python
# garmindb/analysis/performance_report.py
"""Performance report model + builder.

Aggregates power (JSON), training load / recovery / sleep / stress
(existing analyzers via the repository), weight and VO2max, applies
targets, and computes a scorecard, readiness light, deltas and priorities.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Dict, List, Optional

from .models import (
    ActivityAnalysisResult, RecoveryAnalysisResult, SleepAnalysisResult,
    StressAnalysisResult, Insight, InsightSeverity,
)
from .power_analyzer import PowerAnalysisResult, PowerAnalyzer
from .performance_targets import PerformanceTargets
from .report_state import MetricDelta, compute_deltas
from .db_metrics import get_latest_vo2max

# Severity ranking for prioritisation (lower = more urgent).
_SEVERITY_RANK = {
    InsightSeverity.ALERT: 0,
    InsightSeverity.WARNING: 1,
    InsightSeverity.INFO: 2,
    InsightSeverity.POSITIVE: 3,
}


# Thin indirections so tests can monkeypatch each analyzer independently.
def _run_power(activities_dir, ftp, start, end) -> PowerAnalysisResult:
    return PowerAnalyzer(activities_dir, ftp).analyze(start, end)


def _run_activity(repository, start, end) -> ActivityAnalysisResult:
    from .activity_analyzer import ActivityAnalyzer
    return ActivityAnalyzer(repository).analyze(start, end)


def _run_recovery(repository, start, end) -> RecoveryAnalysisResult:
    from .recovery_analyzer import RecoveryAnalyzer
    return RecoveryAnalyzer(repository).analyze(start, end)


def _run_sleep(repository, start, end) -> SleepAnalysisResult:
    from .sleep_analyzer import SleepAnalyzer
    return SleepAnalyzer(repository).analyze(start, end)


def _run_stress(repository, start, end) -> StressAnalysisResult:
    from .stress_analyzer import StressAnalyzer
    return StressAnalyzer(repository).analyze(start, end)


@dataclass
class ScorecardRow:
    """One row of the executive scorecard."""

    label: str
    current: str           # formatted, e.g. "3,81"
    target: str            # formatted or "—"
    gap: str               # formatted or "—"
    delta: Optional[MetricDelta] = None


@dataclass
class PerformanceReport:
    """Complete performance report payload for rendering."""

    generated_at: datetime
    period_start: date
    period_end: date
    targets: PerformanceTargets

    scorecard: List[ScorecardRow]
    readiness_light: str
    readiness_label: str
    priorities: List[str]

    power: PowerAnalysisResult
    activity: ActivityAnalysisResult
    recovery: RecoveryAnalysisResult
    sleep: SleepAnalysisResult
    stress: StressAnalysisResult

    current_weight_kg: Optional[float]
    wkg_current: Optional[float]
    ftp_used: Optional[float]
    vo2max: Optional[float]

    deltas: Dict[str, MetricDelta]
    metric_snapshot: Dict[str, float] = field(default_factory=dict)


class PerformanceReportBuilder:
    """Builds a PerformanceReport from data sources + targets."""

    def __init__(self, repository, db_dir, activities_dir, targets, last_metrics=None):
        self._repo = repository
        self._db_dir = db_dir
        self._acts_dir = activities_dir
        self._targets = targets
        self._last = last_metrics

    def build(self, start_date, end_date, generated_at) -> PerformanceReport:
        t = self._targets
        power = _run_power(self._acts_dir, t.ftp_watts, start_date, end_date)
        activity = _run_activity(self._repo, start_date, end_date)
        recovery = _run_recovery(self._repo, start_date, end_date)
        sleep = _run_sleep(self._repo, start_date, end_date)
        stress = _run_stress(self._repo, start_date, end_date)

        weight = self._current_weight(start_date, end_date)
        vo2max = get_latest_vo2max(self._db_dir, start_date, end_date)

        ftp_used = t.ftp_watts or power.estimated_ftp
        wkg = (ftp_used / weight) if (ftp_used and weight) else None

        ctl = activity.training_stress.ctl if activity.training_stress else None
        tsb = activity.training_stress.tsb if activity.training_stress else None

        snapshot = self._snapshot(wkg, ftp_used, weight, vo2max, ctl, tsb)
        deltas = compute_deltas(snapshot, self._last)

        scorecard = self._scorecard(wkg, ftp_used, weight, vo2max, ctl, tsb, deltas)
        light, label = self._readiness(recovery.recovery_score)
        priorities = self._priorities([power, activity, recovery, sleep, stress])

        return PerformanceReport(
            generated_at=generated_at, period_start=start_date, period_end=end_date,
            targets=t, scorecard=scorecard, readiness_light=light,
            readiness_label=label, priorities=priorities, power=power,
            activity=activity, recovery=recovery, sleep=sleep, stress=stress,
            current_weight_kg=weight, wkg_current=wkg, ftp_used=ftp_used,
            vo2max=vo2max, deltas=deltas, metric_snapshot=snapshot,
        )

    def _current_weight(self, start_date, end_date) -> Optional[float]:
        series = self._repo.get_weight_series(start_date, end_date)
        if not series:
            return None
        return sum(w for _, w in series) / len(series)

    @staticmethod
    def _snapshot(wkg, ftp, weight, vo2max, ctl, tsb) -> Dict[str, float]:
        raw = {"wkg": wkg, "ftp": ftp, "weight": weight,
               "vo2max": vo2max, "ctl": ctl, "tsb": tsb}
        return {k: float(v) for k, v in raw.items() if v is not None}

    def _scorecard(self, wkg, ftp, weight, vo2max, ctl, tsb, deltas) -> List[ScorecardRow]:
        t = self._targets

        def fmt(v, nd=1):
            return f"{v:.{nd}f}".replace(".", ",") if v is not None else "—"

        def gap(cur, tgt):
            if cur is None or tgt is None:
                return "—"
            return fmt(cur - tgt, 1 if abs(cur - tgt) >= 1 else 2)

        rows = [
            ScorecardRow("W/kg", fmt(wkg, 2), fmt(t.wkg_target, 1),
                         gap(wkg, t.wkg_target), deltas.get("wkg")),
            ScorecardRow("FTP", fmt(ftp, 0) + " W", "—", "—", deltas.get("ftp")),
            ScorecardRow("Peso", fmt(weight, 1) + " kg", fmt(t.weight_target_kg, 0) + " kg",
                         gap(weight, t.weight_target_kg), deltas.get("weight")),
            ScorecardRow("VO2max", fmt(vo2max, 0), "—", "—", deltas.get("vo2max")),
            ScorecardRow("Fitness (CTL)", fmt(ctl, 0), "—", "—", deltas.get("ctl")),
            ScorecardRow("Forma (TSB)", fmt(tsb, 0), "—", "—", deltas.get("tsb")),
        ]
        return rows

    @staticmethod
    def _readiness(recovery_score: int):
        if recovery_score >= 70:
            return "🟢", "pronto para construir"
        if recovery_score >= 50:
            return "🟡", "recuperação parcial — module a carga"
        return "🔴", "recuperação baixa — priorize descanso"

    @staticmethod
    def _priorities(results) -> List[str]:
        insights: List[Insight] = []
        for r in results:
            insights.extend(getattr(r, "insights", []) or [])
        insights.sort(key=lambda i: _SEVERITY_RANK.get(i.severity, 9))
        return [f"{i.severity_icon} {i.title}: {i.description}" for i in insights[:3]]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest test/test_performance_report.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add garmindb/analysis/performance_report.py test/test_performance_report.py
git commit -m "feat(analysis): add PerformanceReport model and builder"
```

---

## Task 8: PerformancePresenter (Markdown)

**Files:**
- Create: `garmindb/presentation/markdown/performance_renderer.py`
- Test: `test/test_performance_renderer.py`

- [ ] **Step 1: Write the failing test**

```python
# test/test_performance_renderer.py
from datetime import date, datetime
from garmindb.presentation.markdown.performance_renderer import PerformancePresenter
from garmindb.analysis.performance_report import PerformanceReport, ScorecardRow
from garmindb.analysis.performance_targets import PerformanceTargets
from garmindb.analysis.report_state import MetricDelta


def _report():
    return PerformanceReport(
        generated_at=datetime(2026, 6, 8, 12, 0, 0),
        period_start=date(2026, 5, 9), period_end=date(2026, 6, 7),
        targets=PerformanceTargets(ftp_watts=325, weight_target_kg=80, wkg_target=4.0,
                                   race_name="L'Etape Campos do Jordao", race_date="2026-09-27"),
        scorecard=[
            ScorecardRow("W/kg", "3,81", "4,0", "-0,19",
                         MetricDelta(3.81, 3.71, 0.10)),
            ScorecardRow("Peso", "84,5 kg", "80 kg", "4,5", MetricDelta(84.5, 85.3, -0.8)),
        ],
        readiness_light="🟡", readiness_label="recuperação parcial",
        priorities=["⚠️ Elevated RHR: RHR up", "ℹ️ Confirme FTP: teste"],
        power=None, activity=None, recovery=None, sleep=None, stress=None,
        current_weight_kg=84.5, wkg_current=3.81, ftp_used=325, vo2max=56,
        deltas={}, metric_snapshot={},
    )


def test_render_contains_header_and_goal():
    md = PerformancePresenter().render(_report())
    assert "# " in md
    assert "L'Etape Campos do Jordao" in md
    assert "PRONTIDÃO" in md.upper() or "Prontidão" in md


def test_render_scorecard_table_and_priorities():
    md = PerformancePresenter().render(_report())
    assert "W/kg" in md and "3,81" in md and "4,0" in md
    assert "| Métrica" in md  # scorecard table header
    assert "Elevated RHR" in md


def test_render_delta_arrows():
    md = PerformancePresenter().render(_report())
    # W/kg improved (+0.10 toward target) -> up arrow; Peso decreased -> down
    assert "↑" in md and "↓" in md


def test_no_metadata_flag_skips_frontmatter():
    md = PerformancePresenter(include_metadata=False).render(_report())
    assert not md.startswith("---")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m pytest test/test_performance_renderer.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'garmindb.presentation.markdown.performance_renderer'`

- [ ] **Step 3: Write minimal implementation**

```python
# garmindb/presentation/markdown/performance_renderer.py
"""Render a PerformanceReport to Markdown."""

from typing import List, Optional

from garmindb.analysis.performance_report import PerformanceReport, ScorecardRow
from garmindb.analysis.report_state import MetricDelta


class PerformancePresenter:
    """Self-contained Markdown renderer for the performance report."""

    def __init__(self, include_metadata: bool = True):
        self._include_metadata = include_metadata

    def render(self, report: PerformanceReport) -> str:
        parts: List[str] = []
        if self._include_metadata:
            parts.append(self._frontmatter(report))
        parts.append(self._header(report))
        parts.append(self._readiness(report))
        parts.append(self._scorecard(report))
        parts.append(self._priorities(report))
        return "\n".join(p for p in parts if p).rstrip() + "\n"

    def _frontmatter(self, r: PerformanceReport) -> str:
        return (
            "---\n"
            "report_type: performance\n"
            f"generated: {r.generated_at.isoformat()}\n"
            f"period_start: {r.period_start}\n"
            f"period_end: {r.period_end}\n"
            f"race: {r.targets.race_name or ''}\n"
            "---\n"
        )

    def _header(self, r: PerformanceReport) -> str:
        race = r.targets.race_name or "prova-alvo"
        return (
            f"# 🎯 Performance — {r.period_start} a {r.period_end}\n\n"
            f"Meta: {race}"
            + (f" ({r.targets.race_date})" if r.targets.race_date else "")
            + f" · gerado {r.generated_at:%d/%m/%Y}\n"
        )

    def _readiness(self, r: PerformanceReport) -> str:
        return f"\n**PRONTIDÃO:** {r.readiness_light} {r.readiness_label}\n"

    @staticmethod
    def _delta_cell(delta: Optional[MetricDelta]) -> str:
        if delta is None or not delta.has_previous or delta.delta is None:
            return "baseline"
        arrow = "↑" if delta.delta > 0 else ("↓" if delta.delta < 0 else "→")
        return f"{arrow} {abs(delta.delta):.2f}".replace(".", ",")

    def _scorecard(self, r: PerformanceReport) -> str:
        lines = [
            "\n## Resumo Executivo\n",
            "| Métrica | Agora | Meta | Gap | Δ |",
            "|---|---|---|---|---|",
        ]
        for row in r.scorecard:
            lines.append(
                f"| {row.label} | {row.current} | {row.target} | "
                f"{row.gap} | {self._delta_cell(row.delta)} |"
            )
        return "\n".join(lines) + "\n"

    def _priorities(self, r: PerformanceReport) -> str:
        if not r.priorities:
            return ""
        lines = ["\n## Prioridades agora\n"]
        for i, p in enumerate(r.priorities, 1):
            lines.append(f"{i}. {p}")
        return "\n".join(lines) + "\n"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest test/test_performance_renderer.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add garmindb/presentation/markdown/performance_renderer.py test/test_performance_renderer.py
git commit -m "feat(presentation): add PerformancePresenter markdown renderer"
```

---

## Task 9: Wire `--performance` into the CLI + exports

**Files:**
- Modify: `scripts/generate_report.py`
- Modify: `garmindb/analysis/__init__.py`
- Test: `test/test_performance_cli_smoke.py`

- [ ] **Step 1: Write the failing test**

This smoke test runs the real CLI against the real databases (read-only) and asserts a populated report. It is skipped automatically if the DBs are absent (e.g. CI).

```python
# test/test_performance_cli_smoke.py
import os
import subprocess
import sys
import pytest

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DBS = os.path.expanduser("~/HealthData/DBs/garmin.db")


@pytest.mark.skipif(not os.path.exists(DBS), reason="real DBs not present")
def test_performance_cli_generates_report(tmp_path):
    out = tmp_path / "perf.md"
    result = subprocess.run(
        [sys.executable, "scripts/generate_report.py", "--performance",
         "--start", "2026-05-09", "--end", "2026-06-07", "-o", str(out)],
        cwd=REPO, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    text = out.read_text()
    assert "Resumo Executivo" in text
    assert "W/kg" in text
    assert "PRONTIDÃO" in text.upper()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/python3 -m pytest test/test_performance_cli_smoke.py -v`
Expected: FAIL — the CLI has no `--performance` flag, so the subprocess exits non-zero (or the test skips if DBs absent; on this machine DBs are present so it runs and fails).

- [ ] **Step 3: Write minimal implementation**

In `scripts/generate_report.py`, add the flag in the argparse block (after `--no-metadata`):

```python
    parser.add_argument(
        "--performance",
        action="store_true",
        help="Generate the performance report (power/W-kg/TSB/recovery)",
    )
```

Then replace the report-generation/render block (lines ~54-85, from `# Import here...` to the output handling) with a branch:

```python
    # Import here to avoid slow startup for --help
    from garmindb import GarminConnectConfigManager

    gc_config = GarminConnectConfigManager()
    db_params = gc_config.get_db_params()

    if args.performance:
        import os
        from datetime import datetime as _dt
        from garmindb.data.repositories import SQLiteHealthRepository
        from garmindb.analysis.performance_targets import load_performance_targets
        from garmindb.analysis.performance_report import PerformanceReportBuilder
        from garmindb.analysis.report_state import load_last_metrics, save_metrics
        from garmindb.presentation.markdown.performance_renderer import PerformancePresenter

        db_dir = db_params.db_path
        activities_dir = os.path.join(
            os.path.dirname(db_dir), "FitFiles", "Activities"
        )
        state_path = os.path.join(
            os.path.dirname(db_dir), "reports", "last_metrics.json"
        )

        end = args.end or date.today()
        start = args.start or (end - __import__("datetime").timedelta(days=30))
        generated = _dt(end.year, end.month, end.day, 12, 0, 0)

        repository = SQLiteHealthRepository(db_params)
        targets = load_performance_targets()
        last = load_last_metrics(state_path)

        builder = PerformanceReportBuilder(
            repository=repository, db_dir=db_dir, activities_dir=activities_dir,
            targets=targets, last_metrics=last,
        )
        report = builder.build(start, end, generated)
        save_metrics(state_path, report.metric_snapshot, generated.isoformat())
        markdown = PerformancePresenter(
            include_metadata=not args.no_metadata
        ).render(report)
    else:
        from garmindb.data.repositories import SQLiteHealthRepository
        from garmindb.analysis import HealthAnalyzer
        from garmindb.presentation import MarkdownPresenter

        repository = SQLiteHealthRepository(db_params)
        analyzer = HealthAnalyzer(repository)
        presenter = MarkdownPresenter(include_metadata=not args.no_metadata)
        if args.start and args.end:
            report = analyzer.generate_report(args.start, args.end)
        elif args.period == "daily":
            report = analyzer.daily_report()
        elif args.period == "monthly":
            report = analyzer.monthly_report()
        else:
            report = analyzer.weekly_report()
        markdown = presenter.render_report(report)

    # Output
    if args.output:
        args.output.write_text(markdown)
        print(f"Report saved to: {args.output}")
    else:
        print(markdown)
```

Then export the builder from `garmindb/analysis/__init__.py` (append to the existing exports; keep existing lines intact):

```python
from .performance_report import PerformanceReport, PerformanceReportBuilder  # noqa: F401
from .performance_targets import PerformanceTargets, load_performance_targets  # noqa: F401
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/python3 -m pytest test/test_performance_cli_smoke.py -v`
Expected: PASS (1 passed). Then manually verify:
`.venv/bin/python3 scripts/generate_report.py --performance --start 2026-05-09 --end 2026-06-07 -o /tmp/perf.md` → "Report saved to: /tmp/perf.md", and the file shows the scorecard with your real W/kg.

- [ ] **Step 5: Commit**

```bash
git add scripts/generate_report.py garmindb/analysis/__init__.py test/test_performance_cli_smoke.py
git commit -m "feat(cli): add --performance report mode wiring"
```

---

## Task 10: Create your `performance_targets.json`

**Files:**
- Create: `~/.GarminDb/performance_targets.json` (user data, not in git)

- [ ] **Step 1: Write the config**

```bash
cat > ~/.GarminDb/performance_targets.json <<'JSON'
{
  "ftp_watts": 325,
  "weight_target_kg": 80,
  "wkg_target": 4.0,
  "race_name": "L'Etape Campos do Jordao",
  "race_date": "2026-09-27"
}
JSON
```

- [ ] **Step 2: Regenerate the report and eyeball it**

Run: `.venv/bin/python3 scripts/generate_report.py --performance --start 2026-05-09 --end 2026-06-07 -o docs/relatorio-performance-2026-06-08.md`
Expected: scorecard shows W/kg ≈ 3,8, FTP 325 W, Peso ≈ 84–85 kg with target 80, readiness light, and the FTP-test insight in priorities. (Confirm the race date — placeholder 2026-09-27 — before trusting it.)

No commit (user data + generated doc per existing convention).

---

## Self-review notes

- **Spec coverage:** Exec summary scorecard (Task 7/8), §1 Motor power+FTP+VO2max (Tasks 5/6/7), §2 TSB via ActivityAnalyzer (Task 7), §3 recovery readiness light (Task 7), §4 weight/W-kg (Tasks 2/7), §5 deltas (Task 4/7/8), §6 priorities (Task 7). FTP input + cross-check (Tasks 3/6). Power-from-JSON, no DB changes (Tasks 5/6). All covered.
- **Deferred to a fast-follow (not blocking v1):** the full per-section prose rendering of §1–§4 bodies and the §6 "next block focus" narrative — Task 8 renders header, readiness, scorecard and priorities (the high-information core). Extending `PerformancePresenter` with the per-section detail tables is additive and can be its own task once the skeleton is validated.
- **Type consistency:** `MetricDelta`, `ScorecardRow`, `PerformanceReport`, `PowerAnalysisResult`, `PerformanceTargets` signatures are used identically across tasks. `db_params.db_path` confirmed (DbParams). `Weight.get_for_period` confirmed. VO2max via raw sqlite3 confirmed against `cycle_activities`/`activities` schema.
