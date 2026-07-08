"""Test download endpoints for raw Garmin Connect metrics."""

import datetime
import os
import tempfile
import unittest
from unittest.mock import patch

from garmindb.download import Download


class FakeConfig:
    def __init__(self, fit_files_dir):
        self.fit_files_dir = fit_files_dir

    def get_fit_files_dir(self):
        return self.fit_files_dir


class FakeAdapter:
    instances = []

    def __init__(self, _gc_config):
        self.profile = {"displayName": "display", "fullName": "Full Name"}
        self.display_name = "display"
        self.full_name = "Full Name"
        self.connectapi_calls = []
        FakeAdapter.instances.append(self)

    def connectapi(self, path, **kwargs):
        self.connectapi_calls.append((path, kwargs))
        return {"path": path, "kwargs": kwargs}


class TestConnectMetricDownload(unittest.TestCase):
    def setUp(self):
        FakeAdapter.instances = []
        self.temp_dir = tempfile.TemporaryDirectory()
        self.config = FakeConfig(self.temp_dir.name)
        with patch("garmindb.download.GarminConnectAuthAdapter", FakeAdapter):
            self.download = Download(self.config)
        self.download.display_name = "display"

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_daily_metric_urls(self):
        day = datetime.date(2026, 7, 8)
        self.download.get_training_status(self.temp_dir.name, day, 1, True)
        self.download.get_endurance_score(self.temp_dir.name, day, 1, True)
        self.download.get_hill_score(self.temp_dir.name, day, 1, True)
        self.download.get_fitness_age(self.temp_dir.name, day, 1, True)

        calls = FakeAdapter.instances[0].connectapi_calls
        self.assertEqual(calls[0], ("/metrics-service/metrics/trainingstatus/aggregated/2026-07-08", {}))
        self.assertEqual(calls[1], ("/metrics-service/metrics/endurancescore", {"params": {"calendarDate": "2026-07-08"}}))
        self.assertEqual(calls[2], ("/metrics-service/metrics/hillscore", {"params": {"calendarDate": "2026-07-08"}}))
        self.assertEqual(calls[3], ("/fitnessage-service/fitnessage/2026-07-08", {}))

    def test_wrapped_metric_urls(self):
        day = datetime.date(2026, 7, 8)
        self.download.get_body_battery(self.temp_dir.name, day, 1, True)
        self.download.get_lactate_threshold(self.temp_dir.name, day, 1, True)

        calls = FakeAdapter.instances[0].connectapi_calls
        self.assertEqual(calls[0][0], "/wellness-service/wellness/bodyBattery/reports/daily")
        self.assertEqual(calls[0][1]["params"], {"startDate": "2026-07-08", "endDate": "2026-07-08"})
        self.assertEqual(calls[1][0], "/wellness-service/wellness/bodyBattery/events/2026-07-08")
        self.assertEqual(calls[2][0], "/biometric-service/biometric/latestLactateThreshold")
        self.assertEqual(calls[3][0], "/biometric-service/biometric/powerToWeight/latest/2026-07-08")
        self.assertEqual(calls[3][1]["params"], {"sport": "Running"})

    def test_range_metric_urls(self):
        day = datetime.date(2026, 7, 8)
        self.download.get_body_composition(self.temp_dir.name, day, 1, True)
        self.download.get_running_predictions(self.temp_dir.name, day, 1, True)

        calls = FakeAdapter.instances[0].connectapi_calls
        self.assertEqual(calls[0][0], "/weight-service/weight/dateRange")
        self.assertEqual(calls[0][1]["params"], {"startDate": "2026-07-08", "endDate": "2026-07-08"})
        self.assertEqual(calls[1][0], "/metrics-service/metrics/racepredictions/latest/display")
        self.assertEqual(calls[2][0], "/metrics-service/metrics/racepredictions/daily/display")
        self.assertEqual(calls[3][0], "/metrics-service/metrics/racepredictions/monthly/display")
        self.assertEqual(calls[4][0], "/metrics-service/metrics/runningtolerance/stats")


if __name__ == "__main__":
    unittest.main()
