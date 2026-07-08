"""Test raw Garmin Connect metric importer."""

import datetime
import json
import os
import tempfile
import unittest

from garmindb import GarminConnectConfigManager, GarminConnectMetricRawData
from garmindb.garmindb import ConnectMetricRaw, GarminDb


class TestConnectMetricRawImport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.db_params = GarminConnectConfigManager().get_db_params(test_db=True)

    def test_imports_and_updates_raw_payload(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "training_status_2026-07-08.json")
            with open(path, "w", encoding="utf-8") as f:
                json.dump({"status": "MAINTAINING"}, f)

            importer = GarminConnectMetricRawData(
                self.db_params, d, "training_status", r"training_status_\d{4}-\d{2}-\d{2}\.json", False, False)
            self.assertEqual(importer.file_count(), 1)
            importer.process()

            with open(path, "w", encoding="utf-8") as f:
                json.dump({"status": "PRODUCTIVE"}, f)
            importer.process()

        garmin_db = GarminDb(self.db_params)
        row = ConnectMetricRaw.get(
            garmin_db, ("training_status", "2026-07-08", "2026-07-08", "daily"))
        self.assertEqual(json.loads(row.payload_json), {"status": "PRODUCTIVE"})
        self.assertIsInstance(row.imported_at, datetime.datetime)

    def test_empty_payload_is_coverage(self):
        importer = GarminConnectMetricRawData(
            self.db_params, "", "fitness_age", r".*", False, False)
        self.assertEqual(importer._process_json({}), 1)

        garmin_db = GarminDb(self.db_params)
        row = ConnectMetricRaw.get(
            garmin_db, ("fitness_age", "", "", "raw"))
        self.assertEqual(json.loads(row.payload_json), {})


if __name__ == "__main__":
    unittest.main()
