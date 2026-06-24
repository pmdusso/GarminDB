"""Test TrainingReadinessAnalyzer over a seeded garmin.db."""

import os
import sqlite3
import tempfile
import unittest
from datetime import date

from garmindb.analysis.readiness_analyzer import TrainingReadinessAnalyzer


def _seed(db_dir):
    con = sqlite3.connect(os.path.join(db_dir, 'garmin.db'))
    con.execute("CREATE TABLE training_readiness (day TIMESTAMP PRIMARY KEY, "
                "timestamp TIMESTAMP, score INTEGER, level TEXT, feedback_short TEXT, "
                "feedback_long TEXT, recovery_time INTEGER, sleep_score INTEGER, "
                "sleep_score_factor_pct INTEGER, acwr_factor_pct INTEGER, acute_load INTEGER, "
                "stress_history_factor_pct INTEGER, hrv_factor_pct INTEGER, "
                "hrv_weekly_average INTEGER, sleep_history_factor_pct INTEGER)")
    rows = [('2026-06-20 06:00:00', 80, 'HIGH', 'GOOD', 60),
            ('2026-06-21 06:00:00', 60, 'MODERATE', 'OK', 120),
            ('2026-06-22 06:00:00', 69, 'MODERATE', 'OK', 101)]
    for day, score, level, fb, rt in rows:
        con.execute("INSERT INTO training_readiness (day, score, level, feedback_short, recovery_time) "
                    "VALUES (?,?,?,?,?)", (day, score, level, fb, rt))
    con.commit()
    con.close()


class TestReadinessAnalyzer(unittest.TestCase):
    def test_analyze(self):
        with tempfile.TemporaryDirectory() as d:
            _seed(d)
            result = TrainingReadinessAnalyzer(d).analyze(date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(result.day_count, 3)
        self.assertEqual(result.recent_days[0].day, date(2026, 6, 22))  # date desc
        self.assertEqual(result.recent_days[0].score, 69)
        self.assertEqual(dict(result.monthly_score)['2026-06'], round((80 + 60 + 69) / 3, 1))

    def test_cross_month_gap(self):
        def seed_months(db_dir):
            con = sqlite3.connect(os.path.join(db_dir, 'garmin.db'))
            con.execute(
                "CREATE TABLE training_readiness (day TIMESTAMP PRIMARY KEY, "
                "score INTEGER, level TEXT, feedback_short TEXT, recovery_time INTEGER)")
            rows = [('2026-03-10 06:00:00', 40), ('2026-03-20 06:00:00', 60),
                    ('2026-06-05 06:00:00', 70), ('2026-06-15 06:00:00', 80)]
            for day, score in rows:
                con.execute("INSERT INTO training_readiness (day, score) VALUES (?,?)",
                            (day, score))
            con.commit()
            con.close()

        with tempfile.TemporaryDirectory() as d:
            seed_months(d)
            result = TrainingReadinessAnalyzer(d).analyze(date(2026, 3, 1), date(2026, 6, 30))
        monthly = dict(result.monthly_score)
        self.assertEqual(monthly['2026-03'], round((40 + 60) / 2, 1))
        self.assertEqual(monthly['2026-06'], round((70 + 80) / 2, 1))
        self.assertIsNone(monthly['2026-04'])  # gap month
        self.assertIsNone(monthly['2026-05'])  # gap month

    def test_missing_db_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            result = TrainingReadinessAnalyzer(d).analyze(date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(result.day_count, 0)
        self.assertEqual(result.recent_days, [])


if __name__ == '__main__':
    unittest.main()
