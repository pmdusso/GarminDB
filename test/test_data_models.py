"""Tests for data layer DTOs.

Note: These tests import directly from the models module to avoid
loading the heavy dependencies in garmindb/__init__.py (like fitfile).
"""

import sys
import os
import unittest
from datetime import date, datetime, timedelta

# Add the garmindb/data directory to path to import models directly
# This avoids triggering garmindb/__init__.py which has heavy dependencies
_data_path = os.path.join(os.path.dirname(__file__), '..', 'garmindb', 'data')
sys.path.insert(0, os.path.abspath(_data_path))

from models import (  # noqa: E402
    SleepRecord,
    HeartRateRecord,
    StressRecord,
    BodyBatteryRecord,
    ActivityRecord,
    DailySummaryRecord,
)


class TestSleepRecord(unittest.TestCase):
    """Test SleepRecord DTO."""

    def test_sleep_record_creation(self):
        """Test creating a SleepRecord with all fields."""
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
        record = StressRecord(
            timestamp=datetime(2025, 1, 15, 10, 0),
            stress_level=35,
        )

        self.assertEqual(record.stress_level, 35)

    def test_stress_category(self):
        """Test stress_category property."""
        ts = datetime(2025, 1, 15, 10, 0)
        low = StressRecord(timestamp=ts, stress_level=20)
        medium = StressRecord(timestamp=ts, stress_level=45)
        high = StressRecord(timestamp=ts, stress_level=75)

        self.assertEqual(low.stress_category, "low")
        self.assertEqual(medium.stress_category, "medium")
        self.assertEqual(high.stress_category, "high")

    def test_stress_category_boundaries(self):
        """Test stress_category at boundary values."""
        ts = datetime(2025, 1, 15, 10, 0)
        # Test exact boundary values: 25, 50, 76
        at_25 = StressRecord(timestamp=ts, stress_level=25)
        at_50 = StressRecord(timestamp=ts, stress_level=50)
        at_76 = StressRecord(timestamp=ts, stress_level=76)

        self.assertEqual(at_25.stress_category, "low")  # <= 25 is low
        self.assertEqual(at_50.stress_category, "medium")  # <= 50 is medium
        self.assertEqual(at_76.stress_category, "very_high")  # > 75


class TestActivityRecord(unittest.TestCase):
    """Test ActivityRecord DTO."""

    def test_activity_record_creation(self):
        """Test creating an ActivityRecord."""
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

    def test_pace_per_km_edge_cases(self):
        """Test pace_per_km with edge case values."""
        # Test with distance=0
        record_zero = ActivityRecord(
            activity_id="123",
            name="Test",
            sport="running",
            start_time=datetime(2025, 1, 15, 7, 0),
            duration=timedelta(minutes=30),
            distance=0,
        )
        self.assertIsNone(record_zero.pace_per_km)

        # Test with distance=None
        record_none = ActivityRecord(
            activity_id="124",
            name="Test",
            sport="running",
            start_time=datetime(2025, 1, 15, 7, 0),
            duration=timedelta(minutes=30),
            distance=None,
        )
        self.assertIsNone(record_none.pace_per_km)


class TestBodyBatteryRecord(unittest.TestCase):
    """Test BodyBatteryRecord DTO."""

    def test_body_battery_record_creation(self):
        """Test creating a BodyBatteryRecord."""
        record = BodyBatteryRecord(
            timestamp=datetime(2025, 1, 15, 8, 0),
            level=75,
            charged=10,
            drained=5,
        )

        self.assertEqual(record.level, 75)
        self.assertEqual(record.charged, 10)
        self.assertEqual(record.drained, 5)


class TestDailySummaryRecord(unittest.TestCase):
    """Test DailySummaryRecord DTO."""

    def test_daily_summary_creation(self):
        """Test creating a DailySummaryRecord."""
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
