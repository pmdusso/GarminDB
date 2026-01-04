"""Unit tests for ActivityAnalyzer."""

import unittest
from unittest.mock import MagicMock
from datetime import date, datetime, timedelta
from garmindb.analysis.activity_analyzer import ActivityAnalyzer
from garmindb.data.models import ActivityRecord
from garmindb.analysis.models import ActivityAnalysisResult, TrendDirection


class TestActivityAnalyzer(unittest.TestCase):
    """Test suite for ActivityAnalyzer logic."""

    def setUp(self):
        """Set up analyzer with mocked repository."""
        self.mock_repo = MagicMock()
        self.analyzer = ActivityAnalyzer(self.mock_repo)

    def test_instantiation(self):
        """Test creating ActivityAnalyzer."""
        self.assertIsNotNone(self.analyzer)

    def test_estimate_load_real(self):
        """Test that real training load is preserved."""
        activity = ActivityRecord(
            activity_id="1", name="Run", sport="running",
            start_time=datetime.now(), duration=timedelta(minutes=60),
            training_load=50.0
        )
        load, is_estimated = self.analyzer._estimate_load(activity)
        self.assertEqual(load, 50.0)
        self.assertFalse(is_estimated)

    def test_estimate_load_fallback(self):
        """Test load estimation for different sports when TSS is missing."""
        # Running: 60 min * 0.8 = 48
        run = ActivityRecord(
            activity_id="1", name="Run", sport="running",
            start_time=datetime.now(), duration=timedelta(minutes=60),
            training_load=None
        )
        load, is_estimated = self.analyzer._estimate_load(run)
        self.assertEqual(load, 48.0)
        self.assertTrue(is_estimated)

        # Walking: 60 min * 0.3 = 18
        walk = ActivityRecord(
            activity_id="2", name="Walk", sport="walking",
            start_time=datetime.now(), duration=timedelta(minutes=60),
            training_load=None
        )
        load, _ = self.analyzer._estimate_load(walk)
        self.assertEqual(load, 18.0)

    def test_build_daily_loads_continuous(self):
        """Test that daily series includes zeros for rest days."""
        start = date(2026, 1, 1)
        end = date(2026, 1, 5)
        # Activity only on day 2
        activity = ActivityRecord(
            activity_id="1", name="Run", sport="running",
            start_time=datetime(2026, 1, 2, 10, 0), duration=timedelta(minutes=60),
            training_load=100.0
        )
        
        loads, confidence = self.analyzer._build_daily_loads([activity], start, end)
        
        self.assertEqual(len(loads), 5)
        self.assertEqual(loads[date(2026, 1, 1)], 0.0)
        self.assertEqual(loads[date(2026, 1, 2)], 100.0)
        self.assertEqual(loads[date(2026, 1, 3)], 0.0)
        self.assertEqual(confidence, 1.0)

    def test_confidence_score_volume_based(self):
        """Test that confidence score is weighted by load volume."""
        # Real load 100, Estimated load 100 (60 min run with factor 0.8 is 48, so lets use specific values)
        # Act 1: Real 100
        a1 = ActivityRecord("1", "R", "running", datetime.now(), timedelta(minutes=60), training_load=100)
        # Act 2: Estimated (Running 60m = 48)
        a2 = ActivityRecord("2", "E", "running", datetime.now(), timedelta(minutes=60), training_load=None)
        
        loads, confidence = self.analyzer._build_daily_loads([a1, a2], date.today(), date.today())
        # Total = 148, Real = 100. Confidence = 100/148 = 0.675...
        self.assertAlmostEqual(confidence, 0.68, places=2)

    def test_calculate_ema(self):
        """Test EMA calculation for TSB."""
        values = [100.0, 100.0, 100.0]
        # EMA of constant values should eventually be the value
        ema = self.analyzer._calculate_ema(values, 7)
        self.assertEqual(ema, 100.0)
        
        # Test decay
        values = [100.0, 0.0, 0.0]
        # alpha = 2 / (7 + 1) = 0.25
        # step 1: 100
        # step 2: 0.25*0 + 0.75*100 = 75
        # step 3: 0.25*0 + 0.75*75 = 56.25
        ema = self.analyzer._calculate_ema(values, 7)
        self.assertEqual(ema, 56.25)

    def test_calculate_monotony_repetitive(self):
        """Test monotony calculation with repetitive training."""
        # Identical loads every day
        loads = [100.0] * 7
        monotony = self.analyzer._calculate_monotony(loads)
        # Should be capped at 10.0
        self.assertEqual(monotony, 10.0)

    def test_calculate_monotony_varied(self):
        """Test monotony calculation with varied training."""
        loads = [100, 0, 100, 0, 100, 0, 100]
        monotony = self.analyzer._calculate_monotony(loads)
        # Mean = 400/7 = 57.14
        # StdDev > 0, Monotony should be low-ish
        self.assertLess(monotony, 2.0)

    def test_intensity_distribution(self):
        """Test intensity categorization from training effect."""
        activities = [
            ActivityRecord("1", "R", "running", datetime.now(), timedelta(0), training_effect=1.5), # Recovery
            ActivityRecord("2", "R", "running", datetime.now(), timedelta(0), training_effect=3.5), # Improving
            ActivityRecord("3", "R", "running", datetime.now(), timedelta(0), training_effect=3.5), # Improving
        ]
        dist = self.analyzer._calculate_intensity_distribution(activities)
        self.assertEqual(dist["Recovery"], 33.3)
        self.assertEqual(dist["Improving"], 66.7)

    def test_efficiency_index(self):
        """Test efficiency index calculation (velocity/HR)."""
        # 12 km/h at 150 bpm = 12/150 * 100 = 8.0
        # ActivityRecord fields: duration, distance, avg_hr
        act = ActivityRecord("1", "R", "running", datetime.now(), timedelta(hours=1), distance=12.0, avg_hr=150)
        summaries = self.analyzer._build_sport_summaries([act])
        self.assertEqual(summaries["running"].efficiency_index, 8.0)

    def test_generate_insights_volume_spike(self):
        """Test detection of training volume spike."""
        end_date = date(2026, 1, 14)
        # Prev week: 100 load. Current week: 200 load (+100%)
        daily_loads = {}
        for i in range(14):
            day = end_date - timedelta(days=i)
            daily_loads[day] = 28.6 if i < 7 else 14.3 # Current week vs Prev week
        
        # Manually trigger insight check
        result = MagicMock()
        result.intensity_distribution = {}
        result.training_stress = None
        
        insights = self.analyzer._generate_insights(result, daily_loads, end_date)
        titles = [i.title for i in insights]
        self.assertIn("Training Volume Spike", titles)

    def test_empty_analyze_returns_valid_object(self):
        """Test that analyze() handles no data gracefully."""
        self.mock_repo.get_activities.return_value = []
        
        result = self.analyzer.analyze(date(2026, 1, 1), date(2026, 1, 7))
        self.assertIsInstance(result, ActivityAnalysisResult)
        self.assertEqual(result.total_activities, 0)
        self.assertEqual(result.total_distance_km, 0.0)

if __name__ == "__main__":
    unittest.main()
