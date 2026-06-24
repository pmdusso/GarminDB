"""Test the Training Readiness JSON importer."""

import json
import os
import tempfile
import unittest

from garmindb import GarminConnectConfigManager, GarminTrainingReadinessData
from garmindb.garmindb import GarminDb, TrainingReadiness


def _reading(ts, score):
    return {
        'calendarDate': '2026-06-22', 'timestamp': ts, 'timestampLocal': ts,
        'level': 'MODERATE', 'feedbackShort': 'RECOVERED_AND_READY',
        'feedbackLong': 'MOD_RT_LOW_SS_GOOD_ACWR_NEG', 'score': score,
        'sleepScore': 89, 'sleepScoreFactorPercent': 88, 'recoveryTime': 101,
        'acwrFactorPercent': 69, 'acuteLoad': 1103,
        'stressHistoryFactorPercent': 73, 'hrvFactorPercent': 93,
        'hrvWeeklyAverage': 37, 'sleepHistoryFactorPercent': 65,
    }


class TestTrainingReadinessImport(unittest.TestCase):
    """Importer picks the latest reading per day."""

    @classmethod
    def setUpClass(cls):
        cls.db_params = GarminConnectConfigManager().get_db_params(test_db=True)

    def test_picks_latest_of_three(self):
        with tempfile.TemporaryDirectory() as d:
            data = [_reading('2026-06-22T06:00:00.0', 50),
                    _reading('2026-06-22T15:45:58.0', 69),
                    _reading('2026-06-22T11:00:00.0', 60)]
            with open(os.path.join(d, 'training_readiness_2026-06-22.json'), 'w') as f:
                json.dump(data, f)
            tr = GarminTrainingReadinessData(self.db_params, d, False, False)
            self.assertEqual(tr.file_count(), 1)
            tr.process()
        garmin_db = GarminDb(self.db_params)
        import datetime
        row = TrainingReadiness.get(garmin_db, datetime.datetime(2026, 6, 22))
        self.assertEqual(row.score, 69)  # latest timestamp wins

    def test_empty_list_inserts_nothing(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, 'training_readiness_2026-06-23.json'), 'w') as f:
                json.dump([], f)
            tr = GarminTrainingReadinessData(self.db_params, d, False, False)
            tr.process()  # must not raise


if __name__ == '__main__':
    unittest.main()
