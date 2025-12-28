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

        self.assertIsNotNone(result.avg_total_sleep)
        self.assertIsNotNone(result.avg_deep_sleep)

    def test_empty_period_returns_empty_result(self):
        """Test analysis of period with no data."""
        from garmindb.analysis.sleep_analyzer import SleepAnalyzer

        analyzer = SleepAnalyzer(self.repository)
        start_date = date(2099, 1, 1)
        end_date = date(2099, 1, 7)

        result = analyzer.analyze(start_date, end_date)

        self.assertEqual(result.period_start, start_date)
        self.assertEqual(result.avg_total_sleep.current_value, 0)


if __name__ == "__main__":
    unittest.main()
