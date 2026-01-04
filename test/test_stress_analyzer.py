"""Unit tests for StressAnalyzer."""

import unittest
from unittest.mock import MagicMock
from datetime import date, datetime, timedelta, time
from garmindb.analysis.stress_analyzer import StressAnalyzer
from garmindb.data.models import StressRecord, ActivityRecord
from garmindb.analysis.models import StressAnalysisResult, InsightSeverity


class TestStressAnalyzer(unittest.TestCase):
    """Test suite for StressAnalyzer logic."""

    @classmethod
    def setUpClass(cls):
        """Set up repository for integration tests."""
        from garmindb import GarminConnectConfigManager
        from garmindb.data.repositories import SQLiteHealthRepository

        try:
            gc_config = GarminConnectConfigManager()
            db_params = gc_config.get_db_params()
            cls.repository = SQLiteHealthRepository(db_params)
        except Exception:
            cls.repository = MagicMock()

    def setUp(self):
        """Set up analyzer with mocked repository for logic tests."""
        self.mock_repo = MagicMock()
        self.analyzer = StressAnalyzer(self.mock_repo)

    def test_instantiation(self):
        """Test creating StressAnalyzer."""
        self.assertIsNotNone(self.analyzer)

    def test_calculate_stress_load_basic(self):
        """Test AUC calculation with simple linear data."""
        # 1 hour of stress 50 = (50 * 60) / 60 = 50 stress points
        start = datetime(2026, 1, 1, 10, 0)
        records = [
            StressRecord(timestamp=start, stress_level=50),
            StressRecord(timestamp=start + timedelta(minutes=30), stress_level=50),
            StressRecord(timestamp=start + timedelta(minutes=60), stress_level=50),
        ]
        
        # We cap at 15m, but here intervals are 30m. 
        # First interval: 50 * 15 / 60 = 12.5
        # Second interval: 50 * 15 / 60 = 12.5
        # Last record: 50 * 1 / 60 = 0.83
        # Total approx 25.8
        
        result = self.analyzer._calculate_stress_load(records, start, start + timedelta(hours=2))
        self.assertGreater(result.total_load, 0)
        self.assertEqual(result.avg_intensity, 50.0)

    def test_calculate_stress_load_gap_capping(self):
        """Test that large gaps do not inflate stress load."""
        start = datetime(2026, 1, 1, 10, 0)
        records = [
            StressRecord(timestamp=start, stress_level=80),
            # 4 hour gap
            StressRecord(timestamp=start + timedelta(hours=4), stress_level=20),
        ]
        
        # Logic: 
        # record 1 (80) duration = min(240, 15) = 15 min. Load = 80 * 15 / 60 = 20 pts.
        # record 2 (20) duration = 1 min. Load = 20 * 1 / 60 = 0.33 pts.
        # Total approx 20.3
        
        result = self.analyzer._calculate_stress_load(records, start, start + timedelta(hours=5))
        self.assertLess(result.total_load, 25.0)  # Should be around 20.3, NOT 320+
        self.assertEqual(result.period_minutes, 16) # 15 + 1

    def test_calculate_personal_baseline(self):
        """Test 25th percentile baseline calculation."""
        end_date = date(2026, 1, 1)
        # Create a range of values 10, 11, ... 49
        records = []
        for i in range(40):
            records.append(StressRecord(
                timestamp=datetime.combine(end_date, time(hour=1)) + timedelta(minutes=i),
                stress_level=10 + i
            ))
        
        # 40 values. 25th percentile index = 40 * 0.25 = 10.
        # Sorted values[10] = 10 + 10 = 20.
        baseline = self.analyzer._calculate_personal_baseline(records, end_date)
        self.assertEqual(baseline, 20.0)

    def test_analyze_post_activity_recovery_fast(self):
        """Test detection of fast recovery."""
        baseline = 10.0
        # Activity ends at 12:00
        activity = ActivityRecord(
            activity_id="1", name="Run", sport="running",
            start_time=datetime(2026, 1, 1, 11, 0),
            duration=timedelta(hours=1)
        )
        
        # Stress after activity: 80, 60, 40, 20, 12 (recovered!)
        # 12 is within baseline + 5 (15)
        stop_time = activity.start_time + activity.duration
        records = [
            StressRecord(timestamp=stop_time + timedelta(minutes=5), stress_level=80),
            StressRecord(timestamp=stop_time + timedelta(minutes=15), stress_level=12),
        ]
        
        patterns = self.analyzer._analyze_post_activity_recovery([activity], records, baseline)
        self.assertEqual(len(patterns), 1)
        self.assertEqual(patterns[0].recovery_time_minutes, 15)

    def test_analyze_post_activity_no_recovery(self):
        """Test scenario where stress stays high."""
        baseline = 10.0
        activity = ActivityRecord(
            activity_id="1", name="Run", sport="running",
            start_time=datetime(2026, 1, 1, 11, 0),
            duration=timedelta(hours=1)
        )
        stop_time = activity.start_time + activity.duration
        # Stress stays at 40 for 2 hours
        records = [
            StressRecord(timestamp=stop_time + timedelta(minutes=i*10), stress_level=40)
            for i in range(13) # 120 minutes
        ]
        
        patterns = self.analyzer._analyze_post_activity_recovery([activity], records, baseline)
        self.assertIsNone(patterns[0].recovery_time_minutes)

    def test_recovery_efficiency_score(self):
        """Test efficiency scoring logic."""
        from garmindb.analysis.models import PostActivityStressPattern
        
        # Pattern 1: 30 min recovery
        p1 = PostActivityStressPattern("1", "run", datetime.now(), 15, 80, 20, 30)
        # Pattern 2: No recovery (None)
        p2 = PostActivityStressPattern("2", "run", datetime.now(), 15, 80, 20, None)
        
        # Avg = (30 + 120) / 2 = 75 min
        # Efficiency = 100 - (75 / 120) * 100 = 100 - 62.5 = 37.5
        efficiency = self.analyzer._calculate_recovery_efficiency([p1, p2])
        self.assertEqual(efficiency, 37.5)

    def test_generate_insights_occupational(self):
        """Test detection of occupational stress insight."""
        # Mock result with high weekday stress
        result = MagicMock()
        result.period_start = date(2026, 1, 1)
        result.period_end = date(2026, 1, 7)
        result.weekday_avg = {
            "Monday": 50.0, "Tuesday": 50.0, "Wednesday": 50.0, "Thursday": 50.0, "Friday": 50.0,
            "Saturday": 20.0, "Sunday": 20.0
        }
        # 50 > 20 * 1.45 (29) -> Should trigger
        result.stress_load.total_load = 0
        result.recovery_efficiency = 100
        result.avg_recovery_time_minutes = 30 # Concrete value
        result.peak_stress_time = None
        result.post_activity_patterns = []
        
        insights = self.analyzer._generate_insights(result)
        titles = [i.title for i in insights]
        self.assertIn("Occupational Stress Detected", titles)

    def test_empty_analyze_returns_valid_object(self):
        """Test that analyze() handles no data gracefully."""
        self.mock_repo.get_stress_data.return_value = []
        self.mock_repo.get_activities.return_value = []
        
        result = self.analyzer.analyze(date(2026, 1, 1), date(2026, 1, 7))
        self.assertIsInstance(result, StressAnalysisResult)
        self.assertEqual(result.avg_stress.current_value, 0.0)
        self.assertEqual(result.personal_baseline, 25.0)

if __name__ == "__main__":
    unittest.main()
