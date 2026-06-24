"""Test the TrainingReadiness table."""

import unittest
from datetime import datetime

from garmindb import GarminConnectConfigManager
from garmindb.garmindb import GarminDb, TrainingReadiness


class TestTrainingReadinessDb(unittest.TestCase):
    """Test TrainingReadiness insert/read and stats."""

    @classmethod
    def setUpClass(cls):
        cls.garmin_db = GarminDb(GarminConnectConfigManager().get_db_params(test_db=True))

    def test_insert_and_read(self):
        day = datetime(2026, 6, 22)
        point = {
            'day': day, 'timestamp': datetime(2026, 6, 22, 15, 45, 58),
            'score': 69, 'level': 'MODERATE',
            'feedback_short': 'RECOVERED_AND_READY',
            'feedback_long': 'MOD_RT_LOW_SS_GOOD_ACWR_NEG',
            'recovery_time': 101, 'sleep_score': 89, 'sleep_score_factor_pct': 88,
            'acwr_factor_pct': 69, 'acute_load': 1103,
            'stress_history_factor_pct': 73, 'hrv_factor_pct': 93,
            'hrv_weekly_average': 37, 'sleep_history_factor_pct': 65,
        }
        TrainingReadiness.insert_or_update(self.garmin_db, point, ignore_none=True)
        row = TrainingReadiness.get(self.garmin_db, day)
        self.assertIsNotNone(row)
        self.assertEqual(row.score, 69)
        self.assertEqual(row.level, 'MODERATE')
        self.assertEqual(row.recovery_time, 101)
        self.assertEqual(row.feedback_short, 'RECOVERED_AND_READY')
        self.assertEqual(row.hrv_factor_pct, 93)

    def test_get_stats(self):
        # Two distinct scores so min/max/avg are genuinely different values.
        for d, score in ((datetime(2026, 6, 21), 50), (datetime(2026, 6, 22), 70)):
            point = {
                'day': d, 'timestamp': datetime(d.year, d.month, d.day, 15, 45, 58),
                'score': score, 'level': 'MODERATE',
                'feedback_short': 'RECOVERED_AND_READY',
                'feedback_long': 'MOD_RT_LOW_SS_GOOD_ACWR_NEG',
                'recovery_time': 101, 'sleep_score': 89, 'sleep_score_factor_pct': 88,
                'acwr_factor_pct': 69, 'acute_load': 1103,
                'stress_history_factor_pct': 73, 'hrv_factor_pct': 93,
                'hrv_weekly_average': 37, 'sleep_history_factor_pct': 65,
            }
            TrainingReadiness.insert_or_update(self.garmin_db, point, ignore_none=True)
        with self.garmin_db.managed_session() as session:
            stats = TrainingReadiness.get_stats(
                session, datetime(2026, 6, 1), datetime(2026, 6, 30))
        self.assertEqual(stats['readiness_avg'], 60)  # (50 + 70) / 2
        self.assertEqual(stats['readiness_min'], 50)
        self.assertEqual(stats['readiness_max'], 70)


if __name__ == '__main__':
    unittest.main()
