"""Tests for RecoveryAnalyzer."""

import unittest
from datetime import date, timedelta


class TestRecoveryAnalyzer(unittest.TestCase):
    """Test RecoveryAnalyzer implementation."""

    @classmethod
    def setUpClass(cls):
        """Set up repository for tests."""
        from garmindb import GarminConnectConfigManager
        from garmindb.data.repositories import SQLiteHealthRepository

        gc_config = GarminConnectConfigManager()
        db_params = gc_config.get_db_params()
        cls.repository = SQLiteHealthRepository(db_params)

    def test_analyzer_instantiation(self):
        """Test creating RecoveryAnalyzer."""
        from garmindb.analysis.recovery_analyzer import RecoveryAnalyzer

        analyzer = RecoveryAnalyzer(self.repository)
        self.assertIsNotNone(analyzer)

    def test_analyze_returns_result(self):
        """Test analyze returns RecoveryAnalysisResult."""
        from garmindb.analysis.recovery_analyzer import RecoveryAnalyzer
        from garmindb.analysis.models import RecoveryAnalysisResult

        analyzer = RecoveryAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=7)

        result = analyzer.analyze(start_date, end_date)

        self.assertIsInstance(result, RecoveryAnalysisResult)
        self.assertEqual(result.period_start, start_date)
        self.assertEqual(result.period_end, end_date)

    def test_analyze_recovery_score_range(self):
        """Test that recovery score is in valid range 0-100."""
        from garmindb.analysis.recovery_analyzer import RecoveryAnalyzer

        analyzer = RecoveryAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        result = analyzer.analyze(start_date, end_date)

        self.assertGreaterEqual(result.recovery_score, 0)
        self.assertLessEqual(result.recovery_score, 100)

    def test_analyze_generates_metric_summaries(self):
        """Test that analyze generates metric summaries."""
        from garmindb.analysis.recovery_analyzer import RecoveryAnalyzer

        analyzer = RecoveryAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        result = analyzer.analyze(start_date, end_date)

        self.assertIsNotNone(result.rhr_summary)
        self.assertIsNotNone(result.body_battery_summary)
        self.assertIsNotNone(result.training_load_summary)

    def test_daily_readiness_returns_result(self):
        """Test daily_readiness returns DailyReadinessResult."""
        from garmindb.analysis.recovery_analyzer import RecoveryAnalyzer
        from garmindb.analysis.models import DailyReadinessResult

        analyzer = RecoveryAnalyzer(self.repository)
        target_date = date.today()

        result = analyzer.daily_readiness(target_date)

        self.assertIsInstance(result, DailyReadinessResult)
        self.assertEqual(result.analysis_date, target_date)

    def test_daily_readiness_score_range(self):
        """Test daily readiness scores are in valid range."""
        from garmindb.analysis.recovery_analyzer import RecoveryAnalyzer

        analyzer = RecoveryAnalyzer(self.repository)
        target_date = date.today()

        result = analyzer.daily_readiness(target_date)

        self.assertGreaterEqual(result.recovery_score, 0)
        self.assertLessEqual(result.recovery_score, 100)
        self.assertGreaterEqual(result.readiness_score, 0)
        self.assertLessEqual(result.readiness_score, 100)

    def test_empty_period_returns_default_result(self):
        """Test analysis of period with no data."""
        from garmindb.analysis.recovery_analyzer import RecoveryAnalyzer

        analyzer = RecoveryAnalyzer(self.repository)
        start_date = date(2099, 1, 1)
        end_date = date(2099, 1, 7)

        result = analyzer.analyze(start_date, end_date)

        self.assertEqual(result.period_start, start_date)
        self.assertEqual(result.period_end, end_date)
        # Default score when no data
        self.assertEqual(result.recovery_score, 50)

    def test_acwr_calculation(self):
        """Test ACWR is calculated when sufficient data."""
        from garmindb.analysis.recovery_analyzer import RecoveryAnalyzer

        analyzer = RecoveryAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        result = analyzer.analyze(start_date, end_date)

        # ACWR is optional - may be None if no activities or 0 if no recent activities
        if result.acute_chronic_ratio is not None:
            self.assertGreaterEqual(result.acute_chronic_ratio, 0)


class TestRecoveryAnalyzerInsights(unittest.TestCase):
    """Test RecoveryAnalyzer insight generation."""

    @classmethod
    def setUpClass(cls):
        """Set up repository for tests."""
        from garmindb import GarminConnectConfigManager
        from garmindb.data.repositories import SQLiteHealthRepository

        gc_config = GarminConnectConfigManager()
        db_params = gc_config.get_db_params()
        cls.repository = SQLiteHealthRepository(db_params)

    def test_insights_list_exists(self):
        """Test insights list is created."""
        from garmindb.analysis.recovery_analyzer import RecoveryAnalyzer

        analyzer = RecoveryAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        result = analyzer.analyze(start_date, end_date)

        self.assertIsInstance(result.insights, list)

    def test_insights_have_required_fields(self):
        """Test all insights have required fields."""
        from garmindb.analysis.recovery_analyzer import RecoveryAnalyzer
        from garmindb.analysis.models import Insight

        analyzer = RecoveryAnalyzer(self.repository)
        end_date = date.today()
        start_date = end_date - timedelta(days=30)

        result = analyzer.analyze(start_date, end_date)

        for insight in result.insights:
            self.assertIsInstance(insight, Insight)
            self.assertTrue(insight.title)
            self.assertTrue(insight.description)
            self.assertEqual(insight.category, "recovery")


if __name__ == "__main__":
    unittest.main()
