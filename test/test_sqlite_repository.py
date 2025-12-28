"""Tests for SQLite repository implementation."""

__author__ = "Tom Goetz"
__copyright__ = "Copyright Tom Goetz"
__license__ = "GPL"

import unittest
from datetime import date, timedelta


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
        from garmindb.data.repositories import (
            SQLiteHealthRepository, HealthRepository
        )

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

    def test_get_heart_rate_data_returns_list(self):
        """Test get_heart_rate_data returns list of HeartRateRecords."""
        from garmindb.data.repositories import SQLiteHealthRepository
        from garmindb.data.models import HeartRateRecord

        repo = SQLiteHealthRepository(self.db_params)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = repo.get_heart_rate_data(
            start_date, end_date, resting_only=True
        )

        self.assertIsInstance(result, list)
        if result:
            self.assertIsInstance(result[0], HeartRateRecord)

    def test_get_stress_data_returns_list(self):
        """Test get_stress_data returns list of StressRecords."""
        from garmindb.data.repositories import SQLiteHealthRepository
        from garmindb.data.models import StressRecord

        repo = SQLiteHealthRepository(self.db_params)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = repo.get_stress_data(start_date, end_date)

        self.assertIsInstance(result, list)
        if result:
            self.assertIsInstance(result[0], StressRecord)

    def test_get_body_battery_data_returns_list(self):
        """Test get_body_battery_data returns list of BodyBatteryRecords."""
        from garmindb.data.repositories import SQLiteHealthRepository
        from garmindb.data.models import BodyBatteryRecord

        repo = SQLiteHealthRepository(self.db_params)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = repo.get_body_battery_data(start_date, end_date)

        self.assertIsInstance(result, list)
        if result:
            self.assertIsInstance(result[0], BodyBatteryRecord)

    def test_lazy_loading_databases(self):
        """Test that database connections are lazy-loaded."""
        from garmindb.data.repositories import SQLiteHealthRepository

        repo = SQLiteHealthRepository(self.db_params)

        # Before accessing any data, internal db refs should be None
        self.assertIsNone(repo._garmin_db)
        self.assertIsNone(repo._activities_db)
        self.assertIsNone(repo._monitoring_db)
        self.assertIsNone(repo._summary_db)

        # After accessing sleep data, garmin_db should be initialized
        end = date.today()
        start = end - timedelta(days=1)
        _ = repo.get_sleep_data(start, end)
        self.assertIsNotNone(repo._garmin_db)

    def test_sleep_records_sorted_by_date(self):
        """Test that sleep records are returned sorted by date."""
        from garmindb.data.repositories import SQLiteHealthRepository

        repo = SQLiteHealthRepository(self.db_params)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        result = repo.get_sleep_data(start_date, end_date)

        if len(result) > 1:
            for i in range(len(result) - 1):
                self.assertLessEqual(result[i].date, result[i + 1].date)

    def test_activities_sorted_by_start_time(self):
        """Test that activities are returned sorted by start_time."""
        from garmindb.data.repositories import SQLiteHealthRepository

        repo = SQLiteHealthRepository(self.db_params)
        end_date = date.today()
        start_date = end_date - timedelta(days=90)

        result = repo.get_activities(start_date, end_date)

        if len(result) > 1:
            for i in range(len(result) - 1):
                self.assertLessEqual(
                    result[i].start_time, result[i + 1].start_time
                )

    def test_activities_sport_filter(self):
        """Test that activities can be filtered by sport."""
        from garmindb.data.repositories import SQLiteHealthRepository

        repo = SQLiteHealthRepository(self.db_params)
        end_date = date.today()
        start_date = end_date - timedelta(days=365)

        # Get all activities
        all_activities = repo.get_activities(start_date, end_date)

        # If there are activities, try filtering
        if all_activities:
            # Find a sport that exists
            sport = all_activities[0].sport
            filtered = repo.get_activities(start_date, end_date, sport=sport)

            # All filtered results should contain the sport
            for activity in filtered:
                self.assertIn(sport.lower(), activity.sport.lower())


if __name__ == "__main__":
    unittest.main()
