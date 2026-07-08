"""Smoke test: CLI exposes raw Garmin Connect metric flags."""

import os
import json
import subprocess
import sys
import tempfile
import unittest

from garmindb import GarminConnectConfigManager
from garmindb.statistics import Statistics

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestConnectMetricCliSmoke(unittest.TestCase):
    def test_enum_members_exist(self):
        for name in (
            "training_status", "endurance_score", "hill_score",
            "lactate_threshold", "body_battery", "body_composition",
            "fitness_age", "running_predictions",
        ):
            self.assertTrue(hasattr(Statistics, name), name)

    def test_help_lists_flags(self):
        out = subprocess.run(
            [sys.executable, "scripts/garmindb_cli.py", "--help"],
            capture_output=True, text=True, cwd=REPO)
        self.assertEqual(out.returncode, 0, out.stderr)
        for flag in (
            "--training_status", "--endurance_score", "--hill_score",
            "--lactate_threshold", "--body_battery", "--body_composition",
            "--fitness_age", "--running_predictions",
        ):
            self.assertIn(flag, out.stdout)

    def test_enabled_stats_reads_new_metric_names(self):
        with tempfile.TemporaryDirectory() as d:
            with open(os.path.join(d, "GarminConnectConfig.json"), "w", encoding="utf-8") as f:
                json.dump({"enabled_stats": {"training_status": True, "endurance_score": False}}, f)
            stats = GarminConnectConfigManager(d).enabled_stats()
        self.assertIn(Statistics.training_status, stats)
        self.assertNotIn(Statistics.endurance_score, stats)


if __name__ == "__main__":
    unittest.main()
