"""Tests for repository pattern implementation.

Note: These tests import directly from the repositories module to avoid
loading the heavy dependencies in garmindb/__init__.py (like fitfile).
"""

import os
import sys
import unittest

# Add the garmindb/data directory to path to import repositories directly
# This avoids triggering garmindb/__init__.py which has heavy dependencies
_data_path = os.path.join(os.path.dirname(__file__), '..', 'garmindb', 'data')
sys.path.insert(0, os.path.abspath(_data_path))

from repositories.base import HealthRepository  # noqa: E402


class TestHealthRepositoryInterface(unittest.TestCase):
    """Test HealthRepository abstract interface."""

    def test_repository_is_abstract(self):
        """Test that HealthRepository cannot be instantiated directly."""
        with self.assertRaises(TypeError):
            HealthRepository()

    def test_repository_defines_required_methods(self):
        """Test that interface defines required abstract methods."""
        import inspect

        abstract_methods = {
            name for name, method in inspect.getmembers(HealthRepository)
            if getattr(method, '__isabstractmethod__', False)
        }

        expected_methods = {
            'get_sleep_data',
            'get_heart_rate_data',
            'get_stress_data',
            'get_body_battery_data',
            'get_activities',
            'get_daily_summaries',
        }

        self.assertEqual(abstract_methods, expected_methods)


if __name__ == "__main__":
    unittest.main()
