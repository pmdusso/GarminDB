"""Test the Training Readiness download wiring (URL + filename), no network."""

import datetime
import unittest

from garmindb.download import Download


class _FakeAdapter:
    def __init__(self):
        self.calls = []

    def connectapi(self, url):
        self.calls.append(url)
        return [{'calendarDate': '2026-06-22', 'timestamp': '2026-06-22T15:00:00.0', 'score': 69}]


class TestTrainingReadinessDownload(unittest.TestCase):
    def test_day_download_uses_endpoint_and_filename(self):
        dl = Download.__new__(Download)            # bypass __init__/login
        dl.garmin = _FakeAdapter()
        saved = {}
        dl.save_json_to_file = lambda fn, data, overwrite=False: saved.setdefault('fn', fn) or saved.setdefault('data', data)
        day = datetime.date(2026, 6, 22)
        # call the name-mangled private method directly:
        getattr(dl, '_Download__get_training_readiness_day')('/tmp/tr', day, True)
        self.assertEqual(dl.garmin.calls, ['/metrics-service/metrics/trainingreadiness/2026-06-22'])
        self.assertEqual(saved['fn'], '/tmp/tr/training_readiness_2026-06-22')


if __name__ == '__main__':
    unittest.main()
