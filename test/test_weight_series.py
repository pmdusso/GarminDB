# test/test_weight_series.py
from datetime import date
from garmindb.data.repositories.sqlite import SQLiteHealthRepository


class _Row:
    def __init__(self, day, weight):
        self.day = day
        self.weight = weight


def test_get_weight_series_maps_and_sorts(monkeypatch, tmp_path):
    repo = SQLiteHealthRepository({"db_type": "sqlite", "db_path": str(tmp_path)})

    rows = [_Row(date(2026, 5, 20), 84.6), _Row(date(2026, 5, 3), 83.9), _Row(date(2026, 5, 10), None)]

    import garmindb.data.repositories.sqlite as sqlite_mod

    class _FakeWeight:
        @staticmethod
        def get_for_period(db, start_ts, end_ts):
            return rows

    monkeypatch.setattr(sqlite_mod, "_import_weight_model", lambda: _FakeWeight, raising=False)
    # Force the lazy garmin_db property to a sentinel (not used by the fake)
    repo._garmin_db = object()

    series = repo.get_weight_series(date(2026, 5, 1), date(2026, 5, 31))
    assert series == [(date(2026, 5, 3), 83.9), (date(2026, 5, 20), 84.6)]
