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
