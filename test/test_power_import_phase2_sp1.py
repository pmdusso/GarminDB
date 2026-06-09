"""SP1: per-second power is imported into activity_records.

Pure-unit tests (no committed binary .fit fixture exists). They pin the schema
change and the processor's record-dict build, including the critical guarantee
that a ride with no power meter imports NULL silently rather than erroring.
"""

from garmindb.garmindb import ActivityRecords
from garmindb import ActivityFitFileProcessor


class _FakeFields(dict):
    """dict with attribute access for .timestamp, .get() for the rest."""

    def __init__(self, data, timestamp="2026-05-20 09:00:00"):
        super().__init__(data)
        self.timestamp = timestamp


class _FakeFile:
    filename = "/data/123456_ACTIVITY.fit"

    @staticmethod
    def utc_datetime_to_local(ts):
        return ts


# --------------------------------------------------------------------------- #
# Schema
# --------------------------------------------------------------------------- #

def test_activity_records_has_power_column():
    assert "power" in ActivityRecords.__table__.columns


def test_activity_records_table_version_bumped():
    assert ActivityRecords.table_version == 4


# --------------------------------------------------------------------------- #
# Processor record-dict build
# --------------------------------------------------------------------------- #

def test_record_dict_carries_power_when_present():
    fields = _FakeFields({"heart_rate": 150, "speed": 30.0, "power": 250})
    rec = ActivityFitFileProcessor._record_dict(_FakeFile(), fields, 0, "123456")
    assert rec["power"] == 250
    assert rec["hr"] == 150
    assert rec["activity_id"] == "123456" and rec["record"] == 0


def test_record_dict_power_is_none_for_no_meter_ride():
    # A ride with no power meter must import NULL silently (no KeyError/raise).
    fields = _FakeFields({"heart_rate": 150, "speed": 30.0})
    rec = ActivityFitFileProcessor._record_dict(_FakeFile(), fields, 5, "123456")
    assert rec["power"] is None
    assert rec["hr"] == 150
