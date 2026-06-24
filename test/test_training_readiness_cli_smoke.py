"""Smoke test: the CLI exposes --training_readiness and the enum member exists."""

import os
import subprocess
import sys
import unittest

from garmindb.statistics import Statistics

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


class TestTrainingReadinessCliSmoke(unittest.TestCase):
    def test_enum_member_exists(self):
        self.assertTrue(hasattr(Statistics, 'training_readiness'))

    def test_help_lists_flag(self):
        out = subprocess.run(
            [sys.executable, 'scripts/garmindb_cli.py', '--help'],
            capture_output=True, text=True, cwd=REPO)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertIn('--training_readiness', out.stdout)


if __name__ == '__main__':
    unittest.main()
