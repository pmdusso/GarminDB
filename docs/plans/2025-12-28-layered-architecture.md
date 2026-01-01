# Layered Architecture Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Refactor GarminDB from notebook-centric to layered architecture (Data → Analysis → Presentation) enabling markdown reports, web apps, and LLM-friendly output.

**Architecture:** Three-layer design separating concerns: (1) Data Layer wraps existing GarminDB with Repository pattern and DTOs, (2) Analysis Layer contains all business logic in reusable analyzers, (3) Presentation Layer adapts output to markdown/web/notebooks. Each layer only depends on the layer below.

**Tech Stack:** Python 3.12, SQLAlchemy (existing), dataclasses for DTOs, pytest for testing, matplotlib for charts, FastAPI (future web)

---

## Phase 1: Data Layer Foundation

### Task 1: Create Data Module Structure

**Files:**
- Create: `garmindb/data/__init__.py`
- Create: `garmindb/data/models.py`
- Create: `garmindb/data/repositories/__init__.py`
- Create: `garmindb/data/repositories/base.py`

**Step 1: Create data module directories**

```bash
mkdir -p garmindb/data/repositories
```

**Step 2: Create data module init**

Create `garmindb/data/__init__.py`:
```python
"""Data layer: DTOs and repository abstractions."""

from .models import (
    SleepRecord,
    HeartRateRecord,
    StressRecord,
    BodyBatteryRecord,
    ActivityRecord,
    DailySummaryRecord,
)
from .repositories import HealthRepository, SQLiteHealthRepository

__all__ = [
    "SleepRecord",
    "HeartRateRecord",
    "StressRecord",
    "BodyBatteryRecord",
    "ActivityRecord",
    "DailySummaryRecord",
    "HealthRepository",
    "SQLiteHealthRepository",
]
```

**Step 3: Commit**

```bash
git add garmindb/data/
git commit -m "feat(data): create data layer module structure"
```

---

### Task 2: Create DTO Models

**Files:**
- Create: `garmindb/data/models.py`
- Test: `test/test_data_models.py`

**Step 1: Write failing test for SleepRecord**

Create `test/test_data_models.py`:
```python
"""Tests for data layer DTOs."""

import unittest
from datetime import date, time, timedelta


class TestSleepRecord(unittest.TestCase):
    """Test SleepRecord DTO."""

    def test_sleep_record_creation(self):
        """Test creating a SleepRecord with all fields."""
        from garmindb.data.models import SleepRecord

        record = SleepRecord(
            date=date(2025, 1, 15),
            total_sleep=timedelta(hours=7, minutes=30),
            deep_sleep=timedelta(hours=1, minutes=45),
            light_sleep=timedelta(hours=4),
            rem_sleep=timedelta(hours=1, minutes=45),
            awake_time=timedelta(minutes=15),
            sleep_score=82,
        )

        self.assertEqual(record.date, date(2025, 1, 15))
        self.assertEqual(record.total_sleep, timedelta(hours=7, minutes=30))
        self.assertEqual(record.sleep_score, 82)

    def test_sleep_record_optional_score(self):
        """Test SleepRecord with optional sleep_score as None."""
        from garmindb.data.models import SleepRecord

        record = SleepRecord(
            date=date(2025, 1, 15),
            total_sleep=timedelta(hours=7),
            deep_sleep=timedelta(hours=1),
            light_sleep=timedelta(hours=4),
            rem_sleep=timedelta(hours=2),
            awake_time=timedelta(minutes=10),
            sleep_score=None,
        )

        self.assertIsNone(record.sleep_score)

    def test_sleep_record_total_hours(self):
        """Test total_hours property."""
        from garmindb.data.models import SleepRecord

        record = SleepRecord(
            date=date(2025, 1, 15),
            total_sleep=timedelta(hours=7, minutes=30),
            deep_sleep=timedelta(hours=1),
            light_sleep=timedelta(hours=4),
            rem_sleep=timedelta(hours=2),
            awake_time=timedelta(minutes=30),
        )

        self.assertAlmostEqual(record.total_hours, 7.5, places=2)


class TestHeartRateRecord(unittest.TestCase):
    """Test HeartRateRecord DTO."""

    def test_heart_rate_record_creation(self):
        """Test creating a HeartRateRecord."""
        from datetime import datetime
        from garmindb.data.models import HeartRateRecord

        record = HeartRateRecord(
            timestamp=datetime(2025, 1, 15, 8, 30),
            heart_rate=72,
            resting_hr=52,
        )

        self.assertEqual(record.heart_rate, 72)
        self.assertEqual(record.resting_hr, 52)


class TestStressRecord(unittest.TestCase):
    """Test StressRecord DTO."""

    def test_stress_record_creation(self):
        """Test creating a StressRecord."""
        from datetime import datetime
        from garmindb.data.models import StressRecord

        record = StressRecord(
            timestamp=datetime(2025, 1, 15, 10, 0),
            stress_level=35,
        )

        self.assertEqual(record.stress_level, 35)

    def test_stress_category(self):
        """Test stress_category property."""
        from datetime import datetime
        from garmindb.data.models import StressRecord

        low = StressRecord(timestamp=datetime(2025, 1, 15, 10, 0), stress_level=20)
        medium = StressRecord(timestamp=datetime(2025, 1, 15, 10, 0), stress_level=45)
        high = StressRecord(timestamp=datetime(2025, 1, 15, 10, 0), stress_level=75)

        self.assertEqual(low.stress_category, "low")
        self.assertEqual(medium.stress_category, "medium")
        self.assertEqual(high.stress_category, "high")


class TestActivityRecord(unittest.TestCase):
    """Test ActivityRecord DTO."""

    def test_activity_record_creation(self):
        """Test creating an ActivityRecord."""
        from datetime import datetime, timedelta
        from garmindb.data.models import ActivityRecord

        record = ActivityRecord(
            activity_id="12345",
            name="Morning Run",
            sport="running",
            start_time=datetime(2025, 1, 15, 7, 0),
            duration=timedelta(minutes=45),
            distance=8.5,
            calories=450,
            avg_hr=145,
            training_effect=3.2,
        )

        self.assertEqual(record.name, "Morning Run")
        self.assertEqual(record.distance, 8.5)


class TestDailySummaryRecord(unittest.TestCase):
    """Test DailySummaryRecord DTO."""

    def test_daily_summary_creation(self):
        """Test creating a DailySummaryRecord."""
        from datetime import date, timedelta
        from garmindb.data.models import DailySummaryRecord

        record = DailySummaryRecord(
            date=date(2025, 1, 15),
            resting_hr=52,
            stress_avg=28,
            bb_max=95,
            bb_min=25,
            steps=8500,
            floors=12,
            sleep_avg=timedelta(hours=7, minutes=30),
        )

        self.assertEqual(record.steps, 8500)
        self.assertEqual(record.stress_avg, 28)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest test/test_data_models.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'garmindb.data'`

**Step 3: Write DTO models implementation**

Create `garmindb/data/models.py`:
```python
"""Data Transfer Objects (DTOs) for health data.

These dataclasses provide a clean interface between the data layer
and the analysis layer, decoupling from SQLAlchemy models.
"""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Optional


@dataclass
class SleepRecord:
    """Sleep data for a single night."""

    date: date
    total_sleep: timedelta
    deep_sleep: timedelta
    light_sleep: timedelta
    rem_sleep: timedelta
    awake_time: timedelta
    sleep_score: Optional[int] = None
    bedtime: Optional[time] = None
    wake_time: Optional[time] = None

    @property
    def total_hours(self) -> float:
        """Total sleep in hours."""
        return self.total_sleep.total_seconds() / 3600

    @property
    def deep_sleep_percent(self) -> float:
        """Deep sleep as percentage of total."""
        if self.total_sleep.total_seconds() == 0:
            return 0.0
        return (self.deep_sleep.total_seconds() / self.total_sleep.total_seconds()) * 100

    @property
    def rem_sleep_percent(self) -> float:
        """REM sleep as percentage of total."""
        if self.total_sleep.total_seconds() == 0:
            return 0.0
        return (self.rem_sleep.total_seconds() / self.total_sleep.total_seconds()) * 100


@dataclass
class HeartRateRecord:
    """Heart rate measurement."""

    timestamp: datetime
    heart_rate: int
    resting_hr: Optional[int] = None


@dataclass
class StressRecord:
    """Stress level measurement."""

    timestamp: datetime
    stress_level: int  # 0-100

    @property
    def stress_category(self) -> str:
        """Categorize stress level."""
        if self.stress_level <= 25:
            return "low"
        elif self.stress_level <= 50:
            return "medium"
        elif self.stress_level <= 75:
            return "high"
        else:
            return "very_high"


@dataclass
class BodyBatteryRecord:
    """Body battery measurement."""

    timestamp: datetime
    level: int  # 0-100
    charged: Optional[int] = None
    drained: Optional[int] = None


@dataclass
class ActivityRecord:
    """Single activity record."""

    activity_id: str
    name: Optional[str]
    sport: str
    start_time: datetime
    duration: timedelta
    distance: Optional[float] = None  # km
    calories: Optional[int] = None
    avg_hr: Optional[int] = None
    max_hr: Optional[int] = None
    training_effect: Optional[float] = None
    anaerobic_effect: Optional[float] = None
    training_load: Optional[int] = None

    @property
    def pace_per_km(self) -> Optional[timedelta]:
        """Calculate pace per km for distance activities."""
        if not self.distance or self.distance <= 0:
            return None
        seconds_per_km = self.duration.total_seconds() / self.distance
        return timedelta(seconds=seconds_per_km)


@dataclass
class DailySummaryRecord:
    """Daily aggregated health summary."""

    date: date
    resting_hr: Optional[int] = None
    stress_avg: Optional[int] = None
    bb_max: Optional[int] = None
    bb_min: Optional[int] = None
    steps: Optional[int] = None
    floors: Optional[int] = None
    distance: Optional[float] = None  # km
    calories_active: Optional[int] = None
    calories_total: Optional[int] = None
    sleep_avg: Optional[timedelta] = None
    intensity_mins: Optional[int] = None
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest test/test_data_models.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add garmindb/data/models.py test/test_data_models.py
git commit -m "feat(data): add DTO models for health data"
```

---

### Task 3: Create Repository Interface

**Files:**
- Create: `garmindb/data/repositories/base.py`
- Create: `garmindb/data/repositories/__init__.py`
- Test: `test/test_repositories.py`

**Step 1: Write failing test for repository interface**

Create `test/test_repositories.py`:
```python
"""Tests for repository pattern implementation."""

import unittest
from abc import ABC
from datetime import date


class TestHealthRepositoryInterface(unittest.TestCase):
    """Test HealthRepository abstract interface."""

    def test_repository_is_abstract(self):
        """Test that HealthRepository cannot be instantiated directly."""
        from garmindb.data.repositories.base import HealthRepository

        with self.assertRaises(TypeError):
            HealthRepository()

    def test_repository_defines_required_methods(self):
        """Test that interface defines required abstract methods."""
        from garmindb.data.repositories.base import HealthRepository
        import inspect

        abstract_methods = {
            name for name, method in inspect.getmembers(HealthRepository)
            if getattr(method, '__isabstractmethod__', False)
        }

        expected_methods = {
            'get_sleep_data',
            'get_heart_rate_data',
            'get_stress_data',
            'get_body_battery_data',
            'get_activities',
            'get_daily_summaries',
        }

        self.assertEqual(abstract_methods, expected_methods)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest test/test_repositories.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 3: Write repository interface**

Create `garmindb/data/repositories/base.py`:
```python
"""Abstract repository interface for health data access.

The Repository pattern decouples the analysis layer from
specific data storage implementations (SQLite, API, etc.).
"""

from abc import ABC, abstractmethod
from datetime import date, datetime
from typing import List, Optional

from ..models import (
    SleepRecord,
    HeartRateRecord,
    StressRecord,
    BodyBatteryRecord,
    ActivityRecord,
    DailySummaryRecord,
)


class HealthRepository(ABC):
    """Abstract interface for health data access.

    Implementations can wrap SQLite (GarminDB), REST APIs,
    or other data sources while providing a consistent interface.
    """

    @abstractmethod
    def get_sleep_data(
        self,
        start_date: date,
        end_date: date,
    ) -> List[SleepRecord]:
        """Get sleep records for date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of SleepRecord DTOs ordered by date
        """
        pass

    @abstractmethod
    def get_heart_rate_data(
        self,
        start_date: date,
        end_date: date,
        resting_only: bool = False,
    ) -> List[HeartRateRecord]:
        """Get heart rate records for date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            resting_only: If True, only return resting HR values

        Returns:
            List of HeartRateRecord DTOs ordered by timestamp
        """
        pass

    @abstractmethod
    def get_stress_data(
        self,
        start_date: date,
        end_date: date,
    ) -> List[StressRecord]:
        """Get stress records for date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of StressRecord DTOs ordered by timestamp
        """
        pass

    @abstractmethod
    def get_body_battery_data(
        self,
        start_date: date,
        end_date: date,
    ) -> List[BodyBatteryRecord]:
        """Get body battery records for date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of BodyBatteryRecord DTOs ordered by timestamp
        """
        pass

    @abstractmethod
    def get_activities(
        self,
        start_date: date,
        end_date: date,
        sport: Optional[str] = None,
    ) -> List[ActivityRecord]:
        """Get activity records for date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            sport: Optional filter by sport type

        Returns:
            List of ActivityRecord DTOs ordered by start_time
        """
        pass

    @abstractmethod
    def get_daily_summaries(
        self,
        start_date: date,
        end_date: date,
    ) -> List[DailySummaryRecord]:
        """Get daily summary records for date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of DailySummaryRecord DTOs ordered by date
        """
        pass
```

Create `garmindb/data/repositories/__init__.py`:
```python
"""Repository implementations for health data access."""

from .base import HealthRepository

__all__ = ["HealthRepository"]
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest test/test_repositories.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add garmindb/data/repositories/
git commit -m "feat(data): add HealthRepository abstract interface"
```

---

### Task 4: Implement SQLite Repository

**Files:**
- Create: `garmindb/data/repositories/sqlite.py`
- Modify: `garmindb/data/repositories/__init__.py`
- Test: `test/test_sqlite_repository.py`

**Step 1: Write failing test for SQLite repository**

Create `test/test_sqlite_repository.py`:
```python
"""Tests for SQLite repository implementation."""

import unittest
from datetime import date, datetime, timedelta
import os


class TestSQLiteHealthRepository(unittest.TestCase):
    """Test SQLiteHealthRepository implementation."""

    @classmethod
    def setUpClass(cls):
        """Set up test database connection."""
        from garmindb import GarminConnectConfigManager

        gc_config = GarminConnectConfigManager()
        cls.db_params = gc_config.get_db_params()

    def test_repository_instantiation(self):
        """Test creating SQLiteHealthRepository."""
        from garmindb.data.repositories import SQLiteHealthRepository

        repo = SQLiteHealthRepository(self.db_params)
        self.assertIsNotNone(repo)

    def test_implements_interface(self):
        """Test that SQLiteHealthRepository implements HealthRepository."""
        from garmindb.data.repositories import SQLiteHealthRepository, HealthRepository

        repo = SQLiteHealthRepository(self.db_params)
        self.assertIsInstance(repo, HealthRepository)

    def test_get_sleep_data_returns_list(self):
        """Test get_sleep_data returns list of SleepRecords."""
        from garmindb.data.repositories import SQLiteHealthRepository
        from garmindb.data.models import SleepRecord

        repo = SQLiteHealthRepository(self.db_params)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = repo.get_sleep_data(start_date, end_date)

        self.assertIsInstance(result, list)
        if result:
            self.assertIsInstance(result[0], SleepRecord)

    def test_get_daily_summaries_returns_list(self):
        """Test get_daily_summaries returns list of DailySummaryRecords."""
        from garmindb.data.repositories import SQLiteHealthRepository
        from garmindb.data.models import DailySummaryRecord

        repo = SQLiteHealthRepository(self.db_params)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = repo.get_daily_summaries(start_date, end_date)

        self.assertIsInstance(result, list)
        if result:
            self.assertIsInstance(result[0], DailySummaryRecord)

    def test_get_activities_returns_list(self):
        """Test get_activities returns list of ActivityRecords."""
        from garmindb.data.repositories import SQLiteHealthRepository
        from garmindb.data.models import ActivityRecord

        repo = SQLiteHealthRepository(self.db_params)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        result = repo.get_activities(start_date, end_date)

        self.assertIsInstance(result, list)
        if result:
            self.assertIsInstance(result[0], ActivityRecord)

    def test_get_activities_filter_by_sport(self):
        """Test get_activities can filter by sport."""
        from garmindb.data.repositories import SQLiteHealthRepository

        repo = SQLiteHealthRepository(self.db_params)
        end_date = date.today()
        start_date = end_date - timedelta(days=90)

        all_activities = repo.get_activities(start_date, end_date)
        running = repo.get_activities(start_date, end_date, sport="running")

        # Running subset should be smaller or equal
        self.assertLessEqual(len(running), len(all_activities))

        # All running activities should have sport="running"
        for activity in running:
            self.assertEqual(activity.sport.lower(), "running")


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest test/test_sqlite_repository.py -v
```

Expected: FAIL with `ImportError: cannot import name 'SQLiteHealthRepository'`

**Step 3: Write SQLite repository implementation**

Create `garmindb/data/repositories/sqlite.py`:
```python
"""SQLite implementation of HealthRepository using GarminDB."""

from datetime import date, datetime, timedelta, time as dt_time
from typing import List, Optional

from .base import HealthRepository
from ..models import (
    SleepRecord,
    HeartRateRecord,
    StressRecord,
    BodyBatteryRecord,
    ActivityRecord,
    DailySummaryRecord,
)


class SQLiteHealthRepository(HealthRepository):
    """SQLite implementation using existing GarminDB models.

    Wraps the existing GarminDB SQLAlchemy models to provide
    a clean repository interface with DTO return types.
    """

    def __init__(self, db_params: dict):
        """Initialize repository with database parameters.

        Args:
            db_params: Database connection parameters from GarminConnectConfigManager
        """
        self.db_params = db_params
        self._garmin_db = None
        self._activities_db = None
        self._monitoring_db = None
        self._summary_db = None

    @property
    def garmin_db(self):
        """Lazy-load GarminDb connection."""
        if self._garmin_db is None:
            from garmindb.garmindb import GarminDb
            self._garmin_db = GarminDb(self.db_params)
        return self._garmin_db

    @property
    def activities_db(self):
        """Lazy-load ActivitiesDb connection."""
        if self._activities_db is None:
            from garmindb.garmindb import ActivitiesDb
            self._activities_db = ActivitiesDb(self.db_params)
        return self._activities_db

    @property
    def monitoring_db(self):
        """Lazy-load MonitoringDb connection."""
        if self._monitoring_db is None:
            from garmindb.garmindb import MonitoringDb
            self._monitoring_db = MonitoringDb(self.db_params)
        return self._monitoring_db

    @property
    def summary_db(self):
        """Lazy-load SummaryDb connection."""
        if self._summary_db is None:
            from garmindb.summarydb import SummaryDb
            self._summary_db = SummaryDb(self.db_params, False)
        return self._summary_db

    def _to_datetime(self, d: date) -> datetime:
        """Convert date to datetime for queries."""
        return datetime.combine(d, datetime.min.time())

    def _to_datetime_end(self, d: date) -> datetime:
        """Convert date to end-of-day datetime for queries."""
        return datetime.combine(d, datetime.max.time())

    def _time_to_timedelta(self, t: Optional[dt_time]) -> timedelta:
        """Convert time object to timedelta."""
        if t is None:
            return timedelta(0)
        return timedelta(hours=t.hour, minutes=t.minute, seconds=t.second)

    def get_sleep_data(
        self,
        start_date: date,
        end_date: date,
    ) -> List[SleepRecord]:
        """Get sleep records from GarminDB.Sleep table."""
        from garmindb.garmindb import Sleep

        start_ts = self._to_datetime(start_date)
        end_ts = self._to_datetime_end(end_date)

        raw_data = Sleep.get_for_period(self.garmin_db, start_ts, end_ts)

        records = []
        for row in raw_data:
            try:
                record = SleepRecord(
                    date=row.day,
                    total_sleep=self._time_to_timedelta(row.total_sleep),
                    deep_sleep=self._time_to_timedelta(row.deep_sleep),
                    light_sleep=self._time_to_timedelta(row.light_sleep),
                    rem_sleep=self._time_to_timedelta(row.rem_sleep),
                    awake_time=self._time_to_timedelta(row.awake),
                    sleep_score=getattr(row, 'score', None),
                )
                records.append(record)
            except Exception:
                # Skip malformed rows
                continue

        return sorted(records, key=lambda r: r.date)

    def get_heart_rate_data(
        self,
        start_date: date,
        end_date: date,
        resting_only: bool = False,
    ) -> List[HeartRateRecord]:
        """Get heart rate records from MonitoringHeartRate or RestingHeartRate."""
        if resting_only:
            from garmindb.garmindb import RestingHeartRate

            start_ts = self._to_datetime(start_date)
            end_ts = self._to_datetime_end(end_date)

            raw_data = RestingHeartRate.get_for_period(self.garmin_db, start_ts, end_ts)

            records = []
            for row in raw_data:
                record = HeartRateRecord(
                    timestamp=datetime.combine(row.day, datetime.min.time()),
                    heart_rate=row.resting_heart_rate,
                    resting_hr=row.resting_heart_rate,
                )
                records.append(record)

            return sorted(records, key=lambda r: r.timestamp)
        else:
            from garmindb.garmindb import MonitoringHeartRate

            start_ts = self._to_datetime(start_date)
            end_ts = self._to_datetime_end(end_date)

            raw_data = MonitoringHeartRate.get_for_period(self.monitoring_db, start_ts, end_ts)

            records = []
            for row in raw_data:
                record = HeartRateRecord(
                    timestamp=row.timestamp,
                    heart_rate=row.heart_rate,
                    resting_hr=None,
                )
                records.append(record)

            return sorted(records, key=lambda r: r.timestamp)

    def get_stress_data(
        self,
        start_date: date,
        end_date: date,
    ) -> List[StressRecord]:
        """Get stress records from GarminDB.Stress table."""
        from garmindb.garmindb import Stress

        start_ts = self._to_datetime(start_date)
        end_ts = self._to_datetime_end(end_date)

        raw_data = Stress.get_for_period(self.garmin_db, start_ts, end_ts)

        records = []
        for row in raw_data:
            if row.stress is not None:
                record = StressRecord(
                    timestamp=row.timestamp,
                    stress_level=row.stress,
                )
                records.append(record)

        return sorted(records, key=lambda r: r.timestamp)

    def get_body_battery_data(
        self,
        start_date: date,
        end_date: date,
    ) -> List[BodyBatteryRecord]:
        """Get body battery records from Stress table (contains BB data)."""
        from garmindb.garmindb import Stress

        start_ts = self._to_datetime(start_date)
        end_ts = self._to_datetime_end(end_date)

        raw_data = Stress.get_for_period(self.garmin_db, start_ts, end_ts)

        records = []
        for row in raw_data:
            bb_level = getattr(row, 'body_battery', None)
            if bb_level is not None:
                record = BodyBatteryRecord(
                    timestamp=row.timestamp,
                    level=bb_level,
                )
                records.append(record)

        return sorted(records, key=lambda r: r.timestamp)

    def get_activities(
        self,
        start_date: date,
        end_date: date,
        sport: Optional[str] = None,
    ) -> List[ActivityRecord]:
        """Get activity records from ActivitiesDb."""
        from garmindb.garmindb import Activities

        start_ts = self._to_datetime(start_date)
        end_ts = self._to_datetime_end(end_date)

        raw_data = Activities.get_for_period(self.activities_db, start_ts, end_ts)

        records = []
        for row in raw_data:
            # Filter by sport if specified
            row_sport = str(row.sport) if row.sport else ""
            if sport and sport.lower() not in row_sport.lower():
                continue

            # Calculate duration
            if row.elapsed_time:
                duration = self._time_to_timedelta(row.elapsed_time)
            elif row.moving_time:
                duration = self._time_to_timedelta(row.moving_time)
            else:
                duration = timedelta(0)

            record = ActivityRecord(
                activity_id=str(row.activity_id),
                name=row.name,
                sport=row_sport,
                start_time=row.start_time,
                duration=duration,
                distance=row.distance,
                calories=row.calories,
                avg_hr=row.avg_hr,
                max_hr=row.max_hr,
                training_effect=row.training_effect,
                anaerobic_effect=row.anaerobic_training_effect,
                training_load=getattr(row, 'training_load', None),
            )
            records.append(record)

        return sorted(records, key=lambda r: r.start_time)

    def get_daily_summaries(
        self,
        start_date: date,
        end_date: date,
    ) -> List[DailySummaryRecord]:
        """Get daily summary records from SummaryDb."""
        from garmindb.summarydb import DaysSummary

        start_ts = self._to_datetime(start_date)
        end_ts = self._to_datetime_end(end_date)

        raw_data = DaysSummary.get_for_period(self.summary_db, start_ts, end_ts, DaysSummary)

        records = []
        for row in raw_data:
            sleep_avg = None
            if hasattr(row, 'sleep_avg') and row.sleep_avg:
                sleep_avg = self._time_to_timedelta(row.sleep_avg)

            record = DailySummaryRecord(
                date=row.day,
                resting_hr=getattr(row, 'rhr_avg', None),
                stress_avg=getattr(row, 'stress_avg', None),
                bb_max=getattr(row, 'bb_max', None),
                bb_min=getattr(row, 'bb_min', None),
                steps=getattr(row, 'steps', None),
                floors=getattr(row, 'floors', None),
                distance=getattr(row, 'distance', None),
                calories_active=getattr(row, 'calories_active_avg', None),
                calories_total=getattr(row, 'calories_avg', None),
                sleep_avg=sleep_avg,
                intensity_mins=getattr(row, 'intensity_time', None),
            )
            records.append(record)

        return sorted(records, key=lambda r: r.date)
```

Update `garmindb/data/repositories/__init__.py`:
```python
"""Repository implementations for health data access."""

from .base import HealthRepository
from .sqlite import SQLiteHealthRepository

__all__ = ["HealthRepository", "SQLiteHealthRepository"]
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest test/test_sqlite_repository.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add garmindb/data/repositories/
git commit -m "feat(data): add SQLiteHealthRepository implementation"
```

---

## Phase 2: Analysis Layer

### Task 5: Create Analysis Module Structure

**Files:**
- Create: `garmindb/analysis/__init__.py`
- Create: `garmindb/analysis/models.py`
- Create: `garmindb/analysis/base.py`

**Step 1: Create analysis module directory**

```bash
mkdir -p garmindb/analysis
```

**Step 2: Create analysis models**

Create `garmindb/analysis/models.py`:
```python
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


@dataclass
class RecoveryAnalysisResult:
    """Recovery and readiness analysis."""

    analysis_date: date

    # Scores (0-100)
    recovery_score: int
    readiness_score: int

    # Factors
    sleep_factor: float  # 0-1, contribution to recovery
    stress_factor: float
    activity_factor: float
    body_battery_morning: Optional[int] = None

    # Recommendation
    recommended_intensity: str  # "rest", "light", "moderate", "intense"

    # Insights
    insights: List[Insight] = field(default_factory=list)


@dataclass
class ActivityAnalysisResult:
    """Activity/training analysis result."""

    period_start: date
    period_end: date

    # Counts
    total_activities: int
    activities_by_sport: Dict[str, int] = field(default_factory=dict)

    # Metrics
    total_duration_hours: float
    total_distance_km: float
    total_calories: int
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
```

**Step 3: Create analysis module init**

Create `garmindb/analysis/__init__.py`:
```python
"""Analysis layer: health data analyzers and insights."""

from .models import (
    TrendDirection,
    InsightSeverity,
    MetricSummary,
    Insight,
    SleepAnalysisResult,
    StressAnalysisResult,
    RecoveryAnalysisResult,
    ActivityAnalysisResult,
    HealthReport,
)

__all__ = [
    "TrendDirection",
    "InsightSeverity",
    "MetricSummary",
    "Insight",
    "SleepAnalysisResult",
    "StressAnalysisResult",
    "RecoveryAnalysisResult",
    "ActivityAnalysisResult",
    "HealthReport",
]
```

**Step 4: Commit**

```bash
git add garmindb/analysis/
git commit -m "feat(analysis): add analysis models and module structure"
```

---

### Task 6: Implement Sleep Analyzer

**Files:**
- Create: `garmindb/analysis/sleep_analyzer.py`
- Update: `garmindb/analysis/__init__.py`
- Test: `test/test_sleep_analyzer.py`

**Step 1: Write failing test**

Create `test/test_sleep_analyzer.py`:
```python
"""Tests for SleepAnalyzer."""

import unittest
from datetime import date, timedelta


class TestSleepAnalyzer(unittest.TestCase):
    """Test SleepAnalyzer implementation."""

    @classmethod
    def setUpClass(cls):
        """Set up repository for tests."""
        from garmindb import GarminConnectConfigManager
        from garmindb.data.repositories import SQLiteHealthRepository

        gc_config = GarminConnectConfigManager()
        db_params = gc_config.get_db_params()
        cls.repository = SQLiteHealthRepository(db_params)

    def test_analyzer_instantiation(self):
        """Test creating SleepAnalyzer."""
        from garmindb.analysis.sleep_analyzer import SleepAnalyzer

        analyzer = SleepAnalyzer(self.repository)
        self.assertIsNotNone(analyzer)

    def test_analyze_returns_result(self):
        """Test analyze returns SleepAnalysisResult."""
        from garmindb.analysis.sleep_analyzer import SleepAnalyzer
        from garmindb.analysis.models import SleepAnalysisResult

        analyzer = SleepAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = analyzer.analyze(start_date, end_date)

        self.assertIsInstance(result, SleepAnalysisResult)
        self.assertEqual(result.period_start, start_date)
        self.assertEqual(result.period_end, end_date)

    def test_analyze_generates_insights(self):
        """Test that analyze generates insights."""
        from garmindb.analysis.sleep_analyzer import SleepAnalyzer

        analyzer = SleepAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        result = analyzer.analyze(start_date, end_date)

        # Should have at least some analysis (may or may not have insights)
        self.assertIsNotNone(result.avg_total_sleep)
        self.assertIsNotNone(result.avg_deep_sleep)

    def test_empty_period_returns_empty_result(self):
        """Test analysis of period with no data."""
        from garmindb.analysis.sleep_analyzer import SleepAnalyzer

        analyzer = SleepAnalyzer(self.repository)
        # Use far future dates where no data exists
        start_date = date(2099, 1, 1)
        end_date = date(2099, 1, 7)

        result = analyzer.analyze(start_date, end_date)

        self.assertEqual(result.period_start, start_date)
        self.assertEqual(result.avg_total_sleep.current_value, 0)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest test/test_sleep_analyzer.py -v
```

Expected: FAIL with `ModuleNotFoundError: No module named 'garmindb.analysis.sleep_analyzer'`

**Step 3: Implement SleepAnalyzer**

Create `garmindb/analysis/sleep_analyzer.py`:
```python
"""Sleep data analyzer."""

from datetime import date, timedelta
from typing import List, Dict, Optional
from collections import defaultdict
import statistics

from garmindb.data.repositories.base import HealthRepository
from garmindb.data.models import SleepRecord
from .models import (
    SleepAnalysisResult,
    MetricSummary,
    Insight,
    TrendDirection,
    InsightSeverity,
)


class SleepAnalyzer:
    """Analyzes sleep data and generates insights."""

    # Sleep recommendations (hours)
    RECOMMENDED_SLEEP_MIN = 7.0
    RECOMMENDED_SLEEP_MAX = 9.0
    RECOMMENDED_DEEP_PERCENT = 15.0
    RECOMMENDED_REM_PERCENT = 20.0

    def __init__(self, repository: HealthRepository):
        """Initialize with a health data repository.

        Args:
            repository: Data source implementing HealthRepository
        """
        self.repository = repository

    def analyze(self, start_date: date, end_date: date) -> SleepAnalysisResult:
        """Run complete sleep analysis for the given period.

        Args:
            start_date: Start of analysis period
            end_date: End of analysis period

        Returns:
            SleepAnalysisResult with metrics, patterns, and insights
        """
        sleep_data = self.repository.get_sleep_data(start_date, end_date)

        if not sleep_data:
            return self._empty_result(start_date, end_date)

        # Calculate metrics
        avg_total = self._calc_metric_summary(
            "Total Sleep",
            [r.total_hours for r in sleep_data],
            "hours"
        )
        avg_deep = self._calc_metric_summary(
            "Deep Sleep",
            [r.deep_sleep_percent for r in sleep_data],
            "%"
        )
        avg_rem = self._calc_metric_summary(
            "REM Sleep",
            [r.rem_sleep_percent for r in sleep_data],
            "%"
        )

        # Calculate consistency
        consistency = self._calc_consistency(sleep_data)

        # Find patterns
        best_day, worst_day = self._find_best_worst_days(sleep_data)

        # Generate insights
        insights = self._generate_insights(sleep_data, avg_total, avg_deep, avg_rem)

        # Prepare chart data
        daily_total = {r.date: r.total_hours for r in sleep_data}
        daily_deep = {r.date: r.deep_sleep_percent for r in sleep_data}

        return SleepAnalysisResult(
            period_start=start_date,
            period_end=end_date,
            avg_total_sleep=avg_total,
            avg_deep_sleep=avg_deep,
            avg_rem_sleep=avg_rem,
            sleep_consistency_score=consistency,
            best_sleep_day=best_day,
            worst_sleep_day=worst_day,
            insights=insights,
            daily_total_hours=daily_total,
            daily_deep_percent=daily_deep,
        )

    def _empty_result(self, start_date: date, end_date: date) -> SleepAnalysisResult:
        """Create empty result for periods with no data."""
        empty_metric = MetricSummary(
            name="",
            current_value=0,
            unit="",
        )
        return SleepAnalysisResult(
            period_start=start_date,
            period_end=end_date,
            avg_total_sleep=empty_metric,
            avg_deep_sleep=empty_metric,
            avg_rem_sleep=empty_metric,
            sleep_consistency_score=0,
        )

    def _calc_metric_summary(
        self,
        name: str,
        values: List[float],
        unit: str
    ) -> MetricSummary:
        """Calculate summary statistics for a metric."""
        if not values:
            return MetricSummary(name=name, current_value=0, unit=unit)

        current = values[-1]
        avg_all = statistics.mean(values)

        # Calculate 7-day average if we have enough data
        avg_7d = statistics.mean(values[-7:]) if len(values) >= 7 else avg_all

        # Detect trend (comparing last 7 days to previous 7)
        trend = TrendDirection.STABLE
        if len(values) >= 14:
            recent = statistics.mean(values[-7:])
            previous = statistics.mean(values[-14:-7])
            change_pct = ((recent - previous) / previous * 100) if previous else 0

            if change_pct > 5:
                trend = TrendDirection.IMPROVING
            elif change_pct < -5:
                trend = TrendDirection.DECLINING

        return MetricSummary(
            name=name,
            current_value=current,
            unit=unit,
            average_7d=avg_7d,
            average_30d=avg_all,
            min_value=min(values),
            max_value=max(values),
            trend=trend,
        )

    def _calc_consistency(self, data: List[SleepRecord]) -> float:
        """Calculate sleep consistency score (0-100).

        Based on standard deviation of sleep times - lower variance = higher score.
        """
        if len(data) < 3:
            return 50.0  # Not enough data

        hours = [r.total_hours for r in data]
        std_dev = statistics.stdev(hours)

        # Score: 100 if std_dev=0, decreases with higher variance
        # std_dev of 2 hours would give score of ~50
        score = max(0, 100 - (std_dev * 25))
        return round(score, 1)

    def _find_best_worst_days(self, data: List[SleepRecord]) -> tuple:
        """Find best and worst sleep days of the week."""
        day_totals: Dict[str, List[float]] = defaultdict(list)

        for record in data:
            day_name = record.date.strftime("%A")
            day_totals[day_name].append(record.total_hours)

        if not day_totals:
            return None, None

        day_averages = {
            day: statistics.mean(hours)
            for day, hours in day_totals.items()
        }

        best = max(day_averages, key=day_averages.get)
        worst = min(day_averages, key=day_averages.get)

        return best, worst

    def _generate_insights(
        self,
        data: List[SleepRecord],
        avg_total: MetricSummary,
        avg_deep: MetricSummary,
        avg_rem: MetricSummary,
    ) -> List[Insight]:
        """Generate actionable insights from sleep data."""
        insights = []

        # Check for sleep debt
        avg_hours = avg_total.average_7d or avg_total.current_value
        if avg_hours < self.RECOMMENDED_SLEEP_MIN:
            insights.append(Insight(
                title="Sleep Debt Detected",
                description=f"Average sleep of {avg_hours:.1f}h is below the recommended {self.RECOMMENDED_SLEEP_MIN}-{self.RECOMMENDED_SLEEP_MAX}h range.",
                severity=InsightSeverity.WARNING,
                category="sleep",
                data_points={"avg_sleep": avg_hours, "recommended_min": self.RECOMMENDED_SLEEP_MIN},
                recommendations=[
                    "Try going to bed 30 minutes earlier",
                    "Limit caffeine after 2pm",
                    "Reduce screen time 1 hour before bed",
                ],
            ))
        elif avg_hours > self.RECOMMENDED_SLEEP_MAX:
            insights.append(Insight(
                title="Oversleeping Pattern",
                description=f"Average sleep of {avg_hours:.1f}h exceeds the recommended range.",
                severity=InsightSeverity.INFO,
                category="sleep",
                recommendations=[
                    "Consider a consistent wake time",
                    "Evaluate sleep quality vs quantity",
                ],
            ))
        else:
            insights.append(Insight(
                title="Healthy Sleep Duration",
                description=f"Average sleep of {avg_hours:.1f}h is within the recommended range.",
                severity=InsightSeverity.POSITIVE,
                category="sleep",
            ))

        # Check deep sleep
        avg_deep_pct = avg_deep.average_7d or avg_deep.current_value
        if avg_deep_pct < self.RECOMMENDED_DEEP_PERCENT:
            insights.append(Insight(
                title="Low Deep Sleep",
                description=f"Deep sleep of {avg_deep_pct:.1f}% is below the recommended {self.RECOMMENDED_DEEP_PERCENT}%.",
                severity=InsightSeverity.WARNING,
                category="sleep",
                recommendations=[
                    "Exercise regularly but not close to bedtime",
                    "Maintain a cool bedroom temperature",
                    "Limit alcohol which disrupts deep sleep",
                ],
            ))

        # Check REM sleep
        avg_rem_pct = avg_rem.average_7d or avg_rem.current_value
        if avg_rem_pct < self.RECOMMENDED_REM_PERCENT:
            insights.append(Insight(
                title="Low REM Sleep",
                description=f"REM sleep of {avg_rem_pct:.1f}% is below the recommended {self.RECOMMENDED_REM_PERCENT}%.",
                severity=InsightSeverity.INFO,
                category="sleep",
                recommendations=[
                    "Maintain consistent sleep schedule",
                    "Avoid alcohol before bed",
                ],
            ))

        # Check trend
        if avg_total.trend == TrendDirection.DECLINING:
            insights.append(Insight(
                title="Declining Sleep Trend",
                description="Your sleep duration has been decreasing over the past 2 weeks.",
                severity=InsightSeverity.WARNING,
                category="sleep",
                recommendations=[
                    "Review recent schedule changes",
                    "Consider sleep environment adjustments",
                ],
            ))

        return insights
```

Update `garmindb/analysis/__init__.py`:
```python
"""Analysis layer: health data analyzers and insights."""

from .models import (
    TrendDirection,
    InsightSeverity,
    MetricSummary,
    Insight,
    SleepAnalysisResult,
    StressAnalysisResult,
    RecoveryAnalysisResult,
    ActivityAnalysisResult,
    HealthReport,
)
from .sleep_analyzer import SleepAnalyzer

__all__ = [
    "TrendDirection",
    "InsightSeverity",
    "MetricSummary",
    "Insight",
    "SleepAnalysisResult",
    "StressAnalysisResult",
    "RecoveryAnalysisResult",
    "ActivityAnalysisResult",
    "HealthReport",
    "SleepAnalyzer",
]
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest test/test_sleep_analyzer.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add garmindb/analysis/
git commit -m "feat(analysis): add SleepAnalyzer with insights generation"
```

---

## Phase 3: Presentation Layer

### Task 7: Create Markdown Presenter

**Files:**
- Create: `garmindb/presentation/__init__.py`
- Create: `garmindb/presentation/base.py`
- Create: `garmindb/presentation/markdown/__init__.py`
- Create: `garmindb/presentation/markdown/renderer.py`
- Test: `test/test_markdown_presenter.py`

**Step 1: Create presentation module structure**

```bash
mkdir -p garmindb/presentation/markdown
```

**Step 2: Write failing test**

Create `test/test_markdown_presenter.py`:
```python
"""Tests for Markdown presenter."""

import unittest
from datetime import date, timedelta


class TestMarkdownPresenter(unittest.TestCase):
    """Test MarkdownPresenter implementation."""

    def test_presenter_instantiation(self):
        """Test creating MarkdownPresenter."""
        from garmindb.presentation.markdown import MarkdownPresenter

        presenter = MarkdownPresenter()
        self.assertIsNotNone(presenter)

    def test_render_sleep_analysis(self):
        """Test rendering SleepAnalysisResult as markdown."""
        from garmindb.presentation.markdown import MarkdownPresenter
        from garmindb.analysis.models import (
            SleepAnalysisResult,
            MetricSummary,
            TrendDirection,
        )

        presenter = MarkdownPresenter()

        result = SleepAnalysisResult(
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 7),
            avg_total_sleep=MetricSummary(
                name="Total Sleep",
                current_value=7.5,
                unit="hours",
                average_7d=7.3,
                trend=TrendDirection.STABLE,
            ),
            avg_deep_sleep=MetricSummary(
                name="Deep Sleep",
                current_value=22.0,
                unit="%",
                average_7d=20.0,
                trend=TrendDirection.IMPROVING,
            ),
            avg_rem_sleep=MetricSummary(
                name="REM Sleep",
                current_value=25.0,
                unit="%",
                average_7d=23.0,
                trend=TrendDirection.STABLE,
            ),
            sleep_consistency_score=75.0,
        )

        markdown = presenter.render_sleep(result)

        self.assertIn("## Sleep Analysis", markdown)
        self.assertIn("7.5", markdown)
        self.assertIn("Total Sleep", markdown)

    def test_render_includes_insights(self):
        """Test that insights are rendered."""
        from garmindb.presentation.markdown import MarkdownPresenter
        from garmindb.analysis.models import (
            SleepAnalysisResult,
            MetricSummary,
            Insight,
            InsightSeverity,
        )

        presenter = MarkdownPresenter()

        result = SleepAnalysisResult(
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 7),
            avg_total_sleep=MetricSummary(name="", current_value=6.0, unit="hours"),
            avg_deep_sleep=MetricSummary(name="", current_value=15.0, unit="%"),
            avg_rem_sleep=MetricSummary(name="", current_value=20.0, unit="%"),
            sleep_consistency_score=50.0,
            insights=[
                Insight(
                    title="Sleep Debt Detected",
                    description="Average sleep is below recommended.",
                    severity=InsightSeverity.WARNING,
                    category="sleep",
                    recommendations=["Go to bed earlier"],
                )
            ],
        )

        markdown = presenter.render_sleep(result)

        self.assertIn("Sleep Debt Detected", markdown)
        self.assertIn("Go to bed earlier", markdown)


if __name__ == "__main__":
    unittest.main()
```

**Step 3: Run test to verify it fails**

```bash
python -m pytest test/test_markdown_presenter.py -v
```

Expected: FAIL with `ModuleNotFoundError`

**Step 4: Implement MarkdownPresenter**

Create `garmindb/presentation/base.py`:
```python
"""Base presenter interface."""

from abc import ABC, abstractmethod
from garmindb.analysis.models import SleepAnalysisResult, HealthReport


class Presenter(ABC):
    """Abstract base for all presenters."""

    @abstractmethod
    def render_sleep(self, result: SleepAnalysisResult) -> str:
        """Render sleep analysis."""
        pass

    @abstractmethod
    def render_report(self, report: HealthReport) -> str:
        """Render complete health report."""
        pass
```

Create `garmindb/presentation/markdown/renderer.py`:
```python
"""Markdown renderer for health analysis results."""

from datetime import datetime
from typing import List

from garmindb.analysis.models import (
    SleepAnalysisResult,
    StressAnalysisResult,
    RecoveryAnalysisResult,
    ActivityAnalysisResult,
    HealthReport,
    MetricSummary,
    Insight,
    InsightSeverity,
)
from ..base import Presenter


class MarkdownPresenter(Presenter):
    """Renders analysis results as LLM-friendly Markdown."""

    def __init__(self, include_metadata: bool = True):
        """Initialize presenter.

        Args:
            include_metadata: Include YAML frontmatter for LLM context
        """
        self.include_metadata = include_metadata

    def render_report(self, report: HealthReport) -> str:
        """Render complete health report as Markdown."""
        sections = []

        # Metadata header
        if self.include_metadata:
            sections.append(self._render_metadata(report))

        # Title
        sections.append(f"# Health Report: {report.period_start} to {report.period_end}")
        sections.append(f"\n*Generated: {report.generated_at.strftime('%Y-%m-%d %H:%M')}*\n")

        # Component sections
        if report.sleep:
            sections.append(self.render_sleep(report.sleep))

        if report.stress:
            sections.append(self._render_stress(report.stress))

        if report.activities:
            sections.append(self._render_activities(report.activities))

        # Key insights
        if report.key_insights:
            sections.append(self._render_insights_section(report.key_insights))

        return "\n\n".join(sections)

    def render_sleep(self, result: SleepAnalysisResult) -> str:
        """Render sleep analysis section."""
        lines = []
        lines.append("## Sleep Analysis")
        lines.append(f"\n*Period: {result.period_start} to {result.period_end}*\n")

        # Summary table
        lines.append("### Summary\n")
        lines.append("| Metric | Current | 7-day Avg | Trend |")
        lines.append("|--------|---------|-----------|-------|")

        for metric in [result.avg_total_sleep, result.avg_deep_sleep, result.avg_rem_sleep]:
            lines.append(self._metric_row(metric))

        # Consistency
        lines.append(f"\n**Sleep Consistency Score:** {result.sleep_consistency_score:.0f}/100\n")

        # Patterns
        if result.best_sleep_day or result.worst_sleep_day:
            lines.append("### Patterns\n")
            if result.best_sleep_day:
                lines.append(f"- **Best Sleep Day:** {result.best_sleep_day}")
            if result.worst_sleep_day:
                lines.append(f"- **Worst Sleep Day:** {result.worst_sleep_day}")
            lines.append("")

        # Insights
        if result.insights:
            lines.append("### Insights\n")
            for insight in result.insights:
                lines.append(self._render_insight(insight))

        return "\n".join(lines)

    def _render_metadata(self, report: HealthReport) -> str:
        """Render YAML frontmatter for LLM context."""
        return f"""---
report_type: health_analysis
generated: {report.generated_at.isoformat()}
period_start: {report.period_start}
period_end: {report.period_end}
data_source: garmin_connect
format_version: "1.0"
---"""

    def _metric_row(self, metric: MetricSummary) -> str:
        """Render a metric as a table row."""
        current = f"{metric.current_value:.1f} {metric.unit}"
        avg_7d = f"{metric.average_7d:.1f} {metric.unit}" if metric.average_7d else "—"
        trend = metric.trend_icon

        return f"| {metric.name} | {current} | {avg_7d} | {trend} |"

    def _render_insight(self, insight: Insight) -> str:
        """Render a single insight."""
        lines = []
        icon = insight.severity_icon
        lines.append(f"#### {icon} {insight.title}\n")
        lines.append(f"{insight.description}\n")

        if insight.recommendations:
            lines.append("**Recommendations:**")
            for rec in insight.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)

    def _render_insights_section(self, insights: List[Insight]) -> str:
        """Render key insights section."""
        lines = ["## Key Insights\n"]
        for insight in insights:
            lines.append(self._render_insight(insight))
        return "\n".join(lines)

    def _render_stress(self, result: StressAnalysisResult) -> str:
        """Render stress analysis section."""
        lines = []
        lines.append("## Stress Analysis")
        lines.append(f"\n*Period: {result.period_start} to {result.period_end}*\n")

        lines.append("### Distribution\n")
        lines.append(f"- **Low Stress:** {result.low_stress_percent:.1f}%")
        lines.append(f"- **Medium Stress:** {result.medium_stress_percent:.1f}%")
        lines.append(f"- **High Stress:** {result.high_stress_percent:.1f}%")

        if result.insights:
            lines.append("\n### Insights\n")
            for insight in result.insights:
                lines.append(self._render_insight(insight))

        return "\n".join(lines)

    def _render_activities(self, result: ActivityAnalysisResult) -> str:
        """Render activities analysis section."""
        lines = []
        lines.append("## Activity Summary")
        lines.append(f"\n*Period: {result.period_start} to {result.period_end}*\n")

        lines.append(f"- **Total Activities:** {result.total_activities}")
        lines.append(f"- **Total Duration:** {result.total_duration_hours:.1f} hours")
        lines.append(f"- **Total Distance:** {result.total_distance_km:.1f} km")
        lines.append(f"- **Total Calories:** {result.total_calories:,}")

        if result.activities_by_sport:
            lines.append("\n### By Sport\n")
            for sport, count in sorted(result.activities_by_sport.items()):
                lines.append(f"- **{sport}:** {count}")

        return "\n".join(lines)
```

Create `garmindb/presentation/markdown/__init__.py`:
```python
"""Markdown presentation module."""

from .renderer import MarkdownPresenter

__all__ = ["MarkdownPresenter"]
```

Create `garmindb/presentation/__init__.py`:
```python
"""Presentation layer: output formatters for different targets."""

from .base import Presenter
from .markdown import MarkdownPresenter

__all__ = ["Presenter", "MarkdownPresenter"]
```

**Step 5: Run test to verify it passes**

```bash
python -m pytest test/test_markdown_presenter.py -v
```

Expected: All tests PASS

**Step 6: Commit**

```bash
git add garmindb/presentation/
git commit -m "feat(presentation): add MarkdownPresenter for LLM-friendly output"
```

---

### Task 8: Create Main HealthAnalyzer Entry Point

**Files:**
- Create: `garmindb/analysis/health_analyzer.py`
- Update: `garmindb/analysis/__init__.py`
- Test: `test/test_health_analyzer.py`

**Step 1: Write failing test**

Create `test/test_health_analyzer.py`:
```python
"""Tests for main HealthAnalyzer entry point."""

import unittest
from datetime import date, timedelta


class TestHealthAnalyzer(unittest.TestCase):
    """Test HealthAnalyzer main entry point."""

    @classmethod
    def setUpClass(cls):
        """Set up repository for tests."""
        from garmindb import GarminConnectConfigManager
        from garmindb.data.repositories import SQLiteHealthRepository

        gc_config = GarminConnectConfigManager()
        db_params = gc_config.get_db_params()
        cls.repository = SQLiteHealthRepository(db_params)

    def test_analyzer_instantiation(self):
        """Test creating HealthAnalyzer."""
        from garmindb.analysis import HealthAnalyzer

        analyzer = HealthAnalyzer(self.repository)
        self.assertIsNotNone(analyzer)

    def test_weekly_report(self):
        """Test generating weekly report."""
        from garmindb.analysis import HealthAnalyzer, HealthReport

        analyzer = HealthAnalyzer(self.repository)
        report = analyzer.weekly_report()

        self.assertIsInstance(report, HealthReport)
        self.assertIsNotNone(report.generated_at)
        self.assertIsNotNone(report.period_start)
        self.assertIsNotNone(report.period_end)

    def test_daily_report(self):
        """Test generating daily report."""
        from garmindb.analysis import HealthAnalyzer, HealthReport

        analyzer = HealthAnalyzer(self.repository)
        report = analyzer.daily_report()

        self.assertIsInstance(report, HealthReport)

    def test_custom_period_report(self):
        """Test generating report for custom period."""
        from garmindb.analysis import HealthAnalyzer, HealthReport

        analyzer = HealthAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        report = analyzer.generate_report(start_date, end_date)

        self.assertIsInstance(report, HealthReport)
        self.assertEqual(report.period_start, start_date)
        self.assertEqual(report.period_end, end_date)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run test to verify it fails**

```bash
python -m pytest test/test_health_analyzer.py -v
```

Expected: FAIL with `ImportError: cannot import name 'HealthAnalyzer'`

**Step 3: Implement HealthAnalyzer**

Create `garmindb/analysis/health_analyzer.py`:
```python
"""Main health analyzer entry point."""

from datetime import date, datetime, timedelta
from typing import Optional

from garmindb.data.repositories.base import HealthRepository
from .models import HealthReport, Insight
from .sleep_analyzer import SleepAnalyzer


class HealthAnalyzer:
    """Main entry point for health analysis.

    Coordinates individual analyzers and generates comprehensive reports.
    """

    def __init__(self, repository: HealthRepository):
        """Initialize with a health data repository.

        Args:
            repository: Data source implementing HealthRepository
        """
        self.repository = repository
        self.sleep = SleepAnalyzer(repository)
        # Future: add more analyzers
        # self.stress = StressAnalyzer(repository)
        # self.recovery = RecoveryAnalyzer(repository)
        # self.activity = ActivityAnalyzer(repository)

    def daily_report(self, day: Optional[date] = None) -> HealthReport:
        """Generate report for a single day.

        Args:
            day: Date for report (default: today)

        Returns:
            HealthReport for the specified day
        """
        target_day = day or date.today()
        return self.generate_report(target_day, target_day)

    def weekly_report(self, end_date: Optional[date] = None) -> HealthReport:
        """Generate report for the past 7 days.

        Args:
            end_date: End date for report (default: today)

        Returns:
            HealthReport for the past week
        """
        end = end_date or date.today()
        start = end - timedelta(days=6)  # 7 days inclusive
        return self.generate_report(start, end)

    def monthly_report(self, end_date: Optional[date] = None) -> HealthReport:
        """Generate report for the past 30 days.

        Args:
            end_date: End date for report (default: today)

        Returns:
            HealthReport for the past month
        """
        end = end_date or date.today()
        start = end - timedelta(days=29)  # 30 days inclusive
        return self.generate_report(start, end)

    def generate_report(self, start_date: date, end_date: date) -> HealthReport:
        """Generate comprehensive health report for period.

        Args:
            start_date: Start of report period
            end_date: End of report period

        Returns:
            Complete HealthReport with all available analyses
        """
        # Run individual analyses
        sleep_result = self.sleep.analyze(start_date, end_date)

        # Collect key insights from all analyses
        key_insights = self._collect_key_insights(sleep_result)

        return HealthReport(
            generated_at=datetime.now(),
            period_start=start_date,
            period_end=end_date,
            sleep=sleep_result,
            # Future: add more analyses
            # stress=stress_result,
            # recovery=recovery_result,
            # activities=activity_result,
            key_insights=key_insights,
            metadata={
                "version": "1.0",
                "analyzers": ["sleep"],
            },
        )

    def _collect_key_insights(self, *analyses) -> list:
        """Collect most important insights from all analyses.

        Filters to show only WARNING and ALERT severity insights.
        """
        key_insights = []

        for analysis in analyses:
            if analysis and hasattr(analysis, 'insights'):
                for insight in analysis.insights:
                    if insight.severity in (
                        Insight.__class__.WARNING if hasattr(Insight, '__class__') else None,
                    ):
                        key_insights.append(insight)

        # For now, just collect warnings/alerts from all analyses
        for analysis in analyses:
            if analysis and hasattr(analysis, 'insights'):
                from .models import InsightSeverity
                for insight in analysis.insights:
                    if insight.severity in (InsightSeverity.WARNING, InsightSeverity.ALERT):
                        if insight not in key_insights:
                            key_insights.append(insight)

        return key_insights
```

Update `garmindb/analysis/__init__.py`:
```python
"""Analysis layer: health data analyzers and insights."""

from .models import (
    TrendDirection,
    InsightSeverity,
    MetricSummary,
    Insight,
    SleepAnalysisResult,
    StressAnalysisResult,
    RecoveryAnalysisResult,
    ActivityAnalysisResult,
    HealthReport,
)
from .sleep_analyzer import SleepAnalyzer
from .health_analyzer import HealthAnalyzer

__all__ = [
    "TrendDirection",
    "InsightSeverity",
    "MetricSummary",
    "Insight",
    "SleepAnalysisResult",
    "StressAnalysisResult",
    "RecoveryAnalysisResult",
    "ActivityAnalysisResult",
    "HealthReport",
    "SleepAnalyzer",
    "HealthAnalyzer",
]
```

**Step 4: Run test to verify it passes**

```bash
python -m pytest test/test_health_analyzer.py -v
```

Expected: All tests PASS

**Step 5: Commit**

```bash
git add garmindb/analysis/
git commit -m "feat(analysis): add HealthAnalyzer main entry point"
```

---

### Task 9: Integration Test - Generate Full Report

**Files:**
- Create: `test/test_integration.py`

**Step 1: Write integration test**

Create `test/test_integration.py`:
```python
"""Integration tests for complete report generation flow."""

import unittest
from datetime import date, timedelta


class TestFullReportGeneration(unittest.TestCase):
    """Test complete flow: Data → Analysis → Presentation."""

    @classmethod
    def setUpClass(cls):
        """Set up for integration tests."""
        from garmindb import GarminConnectConfigManager
        from garmindb.data.repositories import SQLiteHealthRepository
        from garmindb.analysis import HealthAnalyzer
        from garmindb.presentation import MarkdownPresenter

        gc_config = GarminConnectConfigManager()
        db_params = gc_config.get_db_params()

        cls.repository = SQLiteHealthRepository(db_params)
        cls.analyzer = HealthAnalyzer(cls.repository)
        cls.presenter = MarkdownPresenter()

    def test_full_weekly_report_flow(self):
        """Test generating and rendering a weekly report."""
        # Generate report
        report = self.analyzer.weekly_report()

        # Render to markdown
        markdown = self.presenter.render_report(report)

        # Validate output
        self.assertIsInstance(markdown, str)
        self.assertIn("Health Report", markdown)
        self.assertIn("Sleep Analysis", markdown)

        # Check structure
        self.assertIn("---", markdown)  # Has metadata
        self.assertIn("| Metric |", markdown)  # Has table

    def test_report_can_be_saved_to_file(self):
        """Test that report can be written to file."""
        import tempfile
        import os

        report = self.analyzer.weekly_report()
        markdown = self.presenter.render_report(report)

        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write(markdown)
            temp_path = f.name

        try:
            self.assertTrue(os.path.exists(temp_path))
            with open(temp_path, 'r') as f:
                content = f.read()
            self.assertEqual(content, markdown)
        finally:
            os.unlink(temp_path)

    def test_monthly_report_has_more_data(self):
        """Test that monthly report covers more data than weekly."""
        weekly = self.analyzer.weekly_report()
        monthly = self.analyzer.monthly_report()

        weekly_days = (weekly.period_end - weekly.period_start).days
        monthly_days = (monthly.period_end - monthly.period_start).days

        self.assertGreater(monthly_days, weekly_days)


if __name__ == "__main__":
    unittest.main()
```

**Step 2: Run integration test**

```bash
python -m pytest test/test_integration.py -v
```

Expected: All tests PASS

**Step 3: Commit**

```bash
git add test/test_integration.py
git commit -m "test: add integration tests for full report flow"
```

---

### Task 10: Add CLI Command for Report Generation

**Files:**
- Create: `scripts/generate_report.py`

**Step 1: Create CLI script**

Create `scripts/generate_report.py`:
```python
#!/usr/bin/env python3
"""Generate health reports from command line.

Usage:
    python scripts/generate_report.py --period weekly
    python scripts/generate_report.py --period daily --output report.md
    python scripts/generate_report.py --start 2025-01-01 --end 2025-01-15
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from pathlib import Path


def parse_date(date_str: str) -> date:
    """Parse date string in YYYY-MM-DD format."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def main():
    parser = argparse.ArgumentParser(
        description="Generate health reports from GarminDB"
    )
    parser.add_argument(
        "--period",
        choices=["daily", "weekly", "monthly"],
        default="weekly",
        help="Report period (default: weekly)",
    )
    parser.add_argument(
        "--start",
        type=parse_date,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=parse_date,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Exclude YAML frontmatter",
    )

    args = parser.parse_args()

    # Import here to avoid slow startup for --help
    from garmindb import GarminConnectConfigManager
    from garmindb.data.repositories import SQLiteHealthRepository
    from garmindb.analysis import HealthAnalyzer
    from garmindb.presentation import MarkdownPresenter

    # Setup
    gc_config = GarminConnectConfigManager()
    db_params = gc_config.get_db_params()
    repository = SQLiteHealthRepository(db_params)
    analyzer = HealthAnalyzer(repository)
    presenter = MarkdownPresenter(include_metadata=not args.no_metadata)

    # Generate report
    if args.start and args.end:
        report = analyzer.generate_report(args.start, args.end)
    elif args.period == "daily":
        report = analyzer.daily_report()
    elif args.period == "monthly":
        report = analyzer.monthly_report()
    else:
        report = analyzer.weekly_report()

    # Render
    markdown = presenter.render_report(report)

    # Output
    if args.output:
        args.output.write_text(markdown)
        print(f"Report saved to: {args.output}")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
```

**Step 2: Make executable and test**

```bash
chmod +x scripts/generate_report.py
python scripts/generate_report.py --help
python scripts/generate_report.py --period weekly
```

**Step 3: Commit**

```bash
git add scripts/generate_report.py
git commit -m "feat(cli): add generate_report.py CLI script"
```

---

## Final Summary

After completing all tasks, run full test suite:

```bash
python -m pytest test/test_data_models.py test/test_repositories.py test/test_sqlite_repository.py test/test_sleep_analyzer.py test/test_markdown_presenter.py test/test_health_analyzer.py test/test_integration.py -v
```

The layered architecture is now in place:

```
garmindb/
├── data/                      # DATA LAYER
│   ├── models.py              # DTOs
│   └── repositories/
│       ├── base.py            # Interface
│       └── sqlite.py          # Implementation
├── analysis/                  # ANALYSIS LAYER
│   ├── models.py              # Result types
│   ├── sleep_analyzer.py      # Sleep analysis
│   └── health_analyzer.py     # Main entry point
└── presentation/              # PRESENTATION LAYER
    ├── base.py                # Interface
    └── markdown/
        └── renderer.py        # Markdown output
```
