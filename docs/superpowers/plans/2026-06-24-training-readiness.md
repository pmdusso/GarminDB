# Training Readiness Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Download Garmin Training Readiness daily data, store it in `garmin.db`, and render a readiness subsection in the longitudinal anamnesis report (Section 4).

**Architecture:** Vertical slice mirroring the existing HRV path end-to-end (download → JSON file → `JsonFileProcessor` import → daily table in `garmin.db`) plus the decoupling render pattern (analyzer in `garmindb/analysis/` → builder method → renderer subsection). No new dependency: `garminconnect==0.3.3` already exposes the endpoint.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 ORM (via `idbutils.DbObject`), `garminconnect` client (via `GarminConnectAuthAdapter`), unittest + pytest.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-06-24-training-readiness-design.md`.
- Endpoint: `/metrics-service/metrics/trainingreadiness/{YYYY-MM-DD}` via `self.garmin.connectapi(url)` (mirrors HRV; goes through the adapter's error handling).
- The endpoint returns a **list of ~3 readings per day**; persist the **latest by `timestamp`** per `calendarDate`.
- New table lives in `garmin.db` (the `GarminDb` database), `table_version = 1`, `day` is the primary key.
- Never fabricate data; the renderer must **suppress** its subsection silently when there is no data (same contract as decoupling).
- After editing `scripts/garmindb_cli.py` you MUST reinstall (`.venv/bin/pip install -e . --force-reinstall --no-deps`) or run from source (`PYTHONPATH=. .venv/bin/python scripts/garmindb_cli.py …`); the venv copies scripts at install time and will otherwise run a stale CLI (see `docs/knowledge/2026-06-09-venv-script-staleness-rebuild-hrv-bug.md`).
- `make flake8` must stay clean; `make -C test analysis` must stay green.
- Commit after each task.

---

## File Structure

- `garmindb/statistics.py` — add `training_readiness` enum member (modify).
- `garmindb/garmindb/garmin_db.py` — `TrainingReadiness` table model (modify).
- `garmindb/import_monitoring.py` — `GarminTrainingReadinessData` importer (modify).
- `garmindb/__init__.py` — export the importer (modify).
- `garmindb/garmin_connect_config_manager.py` — `get_training_readiness_dir()` (modify).
- `garmindb/download.py` — URL constant + `__get_training_readiness_day` + `get_training_readiness` (modify).
- `scripts/garmindb_cli.py` — imports, `stats_to_db_map`, `--training_readiness` arg, download + import dispatch (modify).
- `garmindb/analysis/readiness_analyzer.py` — `TrainingReadinessAnalyzer` + result dataclasses (create).
- `garmindb/analysis/longitudinal_report.py` — report dataclass field + builder method + `build()` wiring (modify).
- `garmindb/presentation/markdown/longitudinal_renderer.py` — `_training_readiness()` + append inside `_load()` (modify).
- `test/test_training_readiness_db.py` — model test (create).
- `test/test_training_readiness_import.py` — importer test incl. list-of-3 (create).
- `test/test_readiness_analyzer.py` — analyzer test (create).
- `test/test_markdown_presenter.py` — renderer subsection test (modify).

---

### Task 1: TrainingReadiness table model

**Files:**
- Modify: `garmindb/garmindb/garmin_db.py` (add class after `Hrv`, before `DailySummary`)
- Test: `test/test_training_readiness_db.py`

**Interfaces:**
- Produces: `TrainingReadiness` ORM class with `day` (DateTime PK), `score` (Integer), `level` (String), `feedback_short`/`feedback_long` (String), `recovery_time` (Integer), `sleep_score`/`sleep_score_factor_pct`/`acwr_factor_pct`/`acute_load`/`stress_history_factor_pct`/`hrv_factor_pct`/`hrv_weekly_average`/`sleep_history_factor_pct` (Integer), `timestamp` (DateTime). Classmethod `get_stats(session, start_ts, end_ts) -> dict` with keys `readiness_avg`, `readiness_min`, `readiness_max`.

- [ ] **Step 1: Write the failing test**

Create `test/test_training_readiness_db.py`:

```python
"""Test the TrainingReadiness table."""

import unittest
from datetime import datetime

from garmindb import GarminConnectConfigManager
from garmindb.garmindb import GarminDb, TrainingReadiness


class TestTrainingReadinessDb(unittest.TestCase):
    """Test TrainingReadiness insert/read and stats."""

    @classmethod
    def setUpClass(cls):
        cls.garmin_db = GarminDb(GarminConnectConfigManager().get_db_params(test_db=True))

    def test_insert_and_read(self):
        day = datetime(2026, 6, 22)
        point = {
            'day': day, 'timestamp': datetime(2026, 6, 22, 15, 45, 58),
            'score': 69, 'level': 'MODERATE',
            'feedback_short': 'RECOVERED_AND_READY',
            'feedback_long': 'MOD_RT_LOW_SS_GOOD_ACWR_NEG',
            'recovery_time': 101, 'sleep_score': 89, 'sleep_score_factor_pct': 88,
            'acwr_factor_pct': 69, 'acute_load': 1103,
            'stress_history_factor_pct': 73, 'hrv_factor_pct': 93,
            'hrv_weekly_average': 37, 'sleep_history_factor_pct': 65,
        }
        TrainingReadiness.insert_or_update(self.garmin_db, point, ignore_none=True)
        row = TrainingReadiness.get(self.garmin_db, day)
        self.assertIsNotNone(row)
        self.assertEqual(row.score, 69)
        self.assertEqual(row.level, 'MODERATE')
        self.assertEqual(row.recovery_time, 101)

    def test_get_stats(self):
        with self.garmin_db.managed_session() as session:
            stats = TrainingReadiness.get_stats(
                session, datetime(2026, 6, 1), datetime(2026, 6, 30))
        self.assertIn('readiness_avg', stats)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest test/test_training_readiness_db.py -v`
Expected: FAIL — `ImportError: cannot import name 'TrainingReadiness'`.

- [ ] **Step 3: Add the model**

In `garmindb/garmindb/garmin_db.py`, insert after the `Hrv` class (ends ~line 357) and before `class DailySummary`:

```python
class TrainingReadiness(GarminDb.Base, idbutils.DbObject):
    """Class representing a daily Garmin Training Readiness reading."""

    __tablename__ = 'training_readiness'

    db = GarminDb
    table_version = 1
    _col_units = {'recovery_time': 'mins', 'acute_load': 'load'}

    day = Column(DateTime, primary_key=True)
    timestamp = Column(DateTime)
    score = Column(Integer)
    level = Column(String)
    feedback_short = Column(String)
    feedback_long = Column(String)
    recovery_time = Column(Integer)
    sleep_score = Column(Integer)
    sleep_score_factor_pct = Column(Integer)
    acwr_factor_pct = Column(Integer)
    acute_load = Column(Integer)
    stress_history_factor_pct = Column(Integer)
    hrv_factor_pct = Column(Integer)
    hrv_weekly_average = Column(Integer)
    sleep_history_factor_pct = Column(Integer)

    @classmethod
    def get_stats(cls, session, start_ts, end_ts):
        """Return a dictionary of aggregate statistics for the given time period."""
        return {
            'readiness_avg': cls.s_get_col_avg(session, cls.score, start_ts, end_ts, ignore_le_zero=True),
            'readiness_min': cls.s_get_col_min(session, cls.score, start_ts, end_ts, ignore_le_zero=True),
            'readiness_max': cls.s_get_col_max(session, cls.score, start_ts, end_ts),
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest test/test_training_readiness_db.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add garmindb/garmindb/garmin_db.py test/test_training_readiness_db.py
git commit -m "feat(db): add training_readiness table"
```

---

### Task 2: Training Readiness importer (handles list-of-3)

**Files:**
- Modify: `garmindb/import_monitoring.py` (add class after `GarminHrvData`, ends ~line 522)
- Modify: `garmindb/__init__.py` (export)
- Test: `test/test_training_readiness_import.py`

**Interfaces:**
- Consumes: `TrainingReadiness` (Task 1).
- Produces: `GarminTrainingReadinessData(db_params, input_dir, latest, debug)` with `.process()` and `.file_count()` (from `JsonFileProcessor`); its `_process_json(json_data)` accepts a **list** of daily readings, stores the latest by `timestamp`, returns 1 on insert / 0 on empty.

- [ ] **Step 1: Write the failing test**

Create `test/test_training_readiness_import.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest test/test_training_readiness_import.py -v`
Expected: FAIL — `ImportError: cannot import name 'GarminTrainingReadinessData'`.

- [ ] **Step 3: Add the importer**

In `garmindb/import_monitoring.py`, after `GarminHrvData` (ends ~line 522), add. First ensure `TrainingReadiness` is imported at the top of the file alongside the other `from .garmindb import ...` names (add `TrainingReadiness`):

```python
class GarminTrainingReadinessData(JsonFileProcessor):
    """Class for importing JSON formatted Garmin Connect Training Readiness data into a database."""

    def __init__(self, db_params, input_dir, latest, debug):
        """Return an instance of GarminTrainingReadinessData.

        Parameters:
        ----------
        db_params (object): configuration data for accessing the database
        input_dir (string): directory (full path) to check for readiness files
        latest (Boolean): check for latest files only
        debug (Boolean): enable debug logging
        """
        super().__init__(r'training_readiness_\d{4}-\d{2}-\d{2}\.json', input_dir=input_dir, latest=latest, debug=debug)
        self.garmin_db = GarminDb(db_params)
        self.conversions = {'calendarDate': self._parse_date, 'timestamp': self._parse_date}

    def _process_json(self, json_data):
        # The endpoint returns a list of intra-day readings; keep the latest.
        if not json_data:
            return 0
        readings = json_data if isinstance(json_data, list) else [json_data]
        latest = max(readings, key=lambda r: r.get('timestamp') or '')
        day = latest.get('calendarDate')
        if day is None:
            return 0
        if isinstance(day, str):
            day = self._parse_date(day)
        ts = latest.get('timestamp')
        if isinstance(ts, str):
            ts = self._parse_date(ts)
        point = {
            'day': day.date() if hasattr(day, 'date') else day,
            'timestamp': ts,
            'score': self._get_field(latest, 'score', int),
            'level': self._get_field(latest, 'level', str),
            'feedback_short': self._get_field(latest, 'feedbackShort', str),
            'feedback_long': self._get_field(latest, 'feedbackLong', str),
            'recovery_time': self._get_field(latest, 'recoveryTime', int),
            'sleep_score': self._get_field(latest, 'sleepScore', int),
            'sleep_score_factor_pct': self._get_field(latest, 'sleepScoreFactorPercent', int),
            'acwr_factor_pct': self._get_field(latest, 'acwrFactorPercent', int),
            'acute_load': self._get_field(latest, 'acuteLoad', int),
            'stress_history_factor_pct': self._get_field(latest, 'stressHistoryFactorPercent', int),
            'hrv_factor_pct': self._get_field(latest, 'hrvFactorPercent', int),
            'hrv_weekly_average': self._get_field(latest, 'hrvWeeklyAverage', int),
            'sleep_history_factor_pct': self._get_field(latest, 'sleepHistoryFactorPercent', int),
        }
        TrainingReadiness.insert_or_update(self.garmin_db, point, ignore_none=True)
        return 1
```

In `garmindb/__init__.py`, add `GarminTrainingReadinessData` to the existing import line that brings in `GarminHrvData` (line ~36) so it is re-exported.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest test/test_training_readiness_import.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add garmindb/import_monitoring.py garmindb/__init__.py test/test_training_readiness_import.py
git commit -m "feat(import): training readiness importer (latest reading per day)"
```

---

### Task 3: Config directory + download methods

**Files:**
- Modify: `garmindb/garmin_connect_config_manager.py` (after `get_rhr_dir`, ~line 145)
- Modify: `garmindb/download.py` (URL constant ~line 45; methods after `get_hrv` ~line 305)
- Test: `test/test_training_readiness_db.py` (add a download-unit test class) — or a new `test/test_training_readiness_download.py`

**Interfaces:**
- Produces: `GarminConnectConfigManager.get_training_readiness_dir() -> str`; `Download.get_training_readiness(directory, date, days, overwrite)` which writes `training_readiness_YYYY-MM-DD.json` files by calling `connectapi("/metrics-service/metrics/trainingreadiness/{date}")`.

- [ ] **Step 1: Write the failing test**

Create `test/test_training_readiness_download.py`:

```python
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
        dl._Download__get_training_readiness_day(dl, '/tmp/tr', day, True) if False else None
        # call the name-mangled private method directly:
        getattr(dl, '_Download__get_training_readiness_day')('/tmp/tr', day, True)
        self.assertEqual(dl.garmin.calls, ['/metrics-service/metrics/trainingreadiness/2026-06-22'])
        self.assertEqual(saved['fn'], '/tmp/tr/training_readiness_2026-06-22')


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest test/test_training_readiness_download.py -v`
Expected: FAIL — `AttributeError: 'Download' object has no attribute '_Download__get_training_readiness_day'`.

- [ ] **Step 3: Add the URL constant, config dir, and download methods**

In `garmindb/download.py` class attributes (after line 45 `garmin_connect_hrv_url = "/hrv-service/hrv"`):

```python
    garmin_connect_training_readiness_url = "/metrics-service/metrics/trainingreadiness"
```

After `get_hrv` (~line 305) add:

```python
    def __get_training_readiness_day(self, directory, day, overwrite=False):
        date_str = day.strftime('%Y-%m-%d')
        json_filename = f'{directory}/training_readiness_{date_str}'
        url = f'{self.garmin_connect_training_readiness_url}/{date_str}'
        try:
            self.save_json_to_file(json_filename, self.garmin.connectapi(url), overwrite)
        except GarminConnectAuthError as e:
            root_logger.error("Exception getting training readiness %s", e)

    def get_training_readiness(self, directory, date, days, overwrite):
        """Download the training readiness data from Garmin Connect and save to a JSON file."""
        root_logger.info("Getting training readiness: %s (%d)", date, days)
        self.__get_stat(self.__get_training_readiness_day, directory, date, days, overwrite)
```

In `garmindb/garmin_connect_config_manager.py`, after `get_rhr_dir` (~line 145):

```python
    def get_training_readiness_dir(self):
        """Return the configured directory of where the training readiness files will be stored."""
        return self.__create_dir_if_needed(self.get_base_dir() + os.sep + 'TrainingReadiness')
```

> Note: `__create_dir_if_needed` is name-mangled to the config class; reference it exactly as the neighbouring `get_rhr_dir` does.

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest test/test_training_readiness_download.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add garmindb/download.py garmindb/garmin_connect_config_manager.py test/test_training_readiness_download.py
git commit -m "feat(download): training readiness endpoint + directory"
```

---

### Task 4: CLI wiring (Statistics + download/import dispatch)

**Files:**
- Modify: `garmindb/statistics.py` (add enum member)
- Modify: `scripts/garmindb_cli.py` (import, `stats_to_db_map`, arg, download dispatch ~after line 167, import dispatch ~after line 235)
- Test: `test/test_training_readiness_cli_smoke.py`

**Interfaces:**
- Consumes: `TrainingReadiness`, `GarminTrainingReadinessData`, `Download.get_training_readiness`, `get_training_readiness_dir` (Tasks 1–3).
- Produces: `Statistics.training_readiness`; CLI flag `--training_readiness`.

- [ ] **Step 1: Write the failing test**

Create `test/test_training_readiness_cli_smoke.py`:

```python
"""Smoke test: the CLI exposes --training_readiness and the enum member exists."""

import subprocess
import sys
import unittest

from garmindb.statistics import Statistics


class TestTrainingReadinessCliSmoke(unittest.TestCase):
    def test_enum_member_exists(self):
        self.assertTrue(hasattr(Statistics, 'training_readiness'))

    def test_help_lists_flag(self):
        out = subprocess.run(
            [sys.executable, 'scripts/garmindb_cli.py', '--help'],
            capture_output=True, text=True, env={'PYTHONPATH': '.', 'PATH': ''})
        self.assertIn('--training_readiness', out.stdout)


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest test/test_training_readiness_cli_smoke.py -v`
Expected: FAIL — `Statistics` has no `training_readiness`.

- [ ] **Step 3: Wire the CLI**

In `garmindb/statistics.py`, add the next enum value after `hrv = 8`:

```python
    training_readiness = 9
```

In `scripts/garmindb_cli.py`:

1. Add `TrainingReadiness` to the `from garmindb.garmindb import ...` line (line 23) and `GarminTrainingReadinessData` to the `from garmindb import ...` importer line.
2. In `stats_to_db_map`, after `Statistics.hrv : GarminDb,` (line 53):

```python
        Statistics.training_readiness    : GarminDb,
```

3. In the download dispatch, after the `hrv` block (line 167):

```python
        if Statistics.training_readiness in stats:
            date, days = self.__get_date_and_days(GarminDb(self.gc_config.get_db_params()), latest, TrainingReadiness, TrainingReadiness.day, 'training_readiness')
            if days > 0:
                tr_dir = self.gc_config.get_training_readiness_dir()
                root_logger.info("Date range to update: %s (%d) to %s", date, days, tr_dir)
                download.get_training_readiness(tr_dir, date, days, overwrite)
                root_logger.info("Saved training readiness files for %s (%d) to %s for processing", date, days, tr_dir)
```

4. In the import dispatch, after the `hrv` block (line 235):

```python
        if Statistics.training_readiness in stats:
            from garmindb import GarminTrainingReadinessData
            tr_dir = self.gc_config.get_training_readiness_dir()
            gtrd = GarminTrainingReadinessData(self.gc_config.get_db_params(), tr_dir, latest, debug)
            if gtrd.file_count() > 0:
                gtrd.process()
```

5. In the argument group, after the `--hrv` argument (line 323):

```python
    stats_group.add_argument("--training_readiness", help="Download and/or import Garmin Training Readiness data.", dest='stats', action='append_const', const=Statistics.training_readiness)
```

- [ ] **Step 4: Reinstall so the venv CLI is current, then run the test**

```bash
.venv/bin/pip install -e . --force-reinstall --no-deps -q
PYTHONPATH=. .venv/bin/python -m pytest test/test_training_readiness_cli_smoke.py -v
```
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add garmindb/statistics.py scripts/garmindb_cli.py test/test_training_readiness_cli_smoke.py
git commit -m "feat(cli): wire --training_readiness download/import"
```

---

### Task 5: Readiness analyzer (read garmin.db → monthly + recent + coverage)

**Files:**
- Create: `garmindb/analysis/readiness_analyzer.py`
- Test: `test/test_readiness_analyzer.py`

**Interfaces:**
- Produces: `TrainingReadinessAnalyzer(db_dir)` with `analyze(start_date, end_date) -> TrainingReadinessResult`. `TrainingReadinessResult` fields: `period_start`, `period_end`, `recent_days: List[ReadinessDay]` (date desc), `monthly_score: List[Tuple[str, Optional[float]]]`, `day_count: int`. `ReadinessDay` fields: `day` (date), `score` (int), `level` (str), `recovery_time` (Optional[int]), `feedback_short` (str).
- Consumes: `training_readiness` table (Task 1).

- [ ] **Step 1: Write the failing test**

Create `test/test_readiness_analyzer.py`:

```python
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

    def test_missing_db_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            result = TrainingReadinessAnalyzer(d).analyze(date(2026, 6, 1), date(2026, 6, 30))
        self.assertEqual(result.day_count, 0)
        self.assertEqual(result.recent_days, [])


if __name__ == '__main__':
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest test/test_readiness_analyzer.py -v`
Expected: FAIL — module `readiness_analyzer` does not exist.

- [ ] **Step 3: Write the analyzer**

Create `garmindb/analysis/readiness_analyzer.py`:

```python
"""Training Readiness longitudinal analysis from the garmin.db table.

Reads the ``training_readiness`` table and produces a monthly mean score
series plus the most recent days, for the clinical anamnesis. Never raises:
returns an empty result on any DB problem (same contract as the decoupling
analyzer).
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

RECENT_DAYS = 7


@dataclass
class ReadinessDay:
    """One day's readiness summary for the recent-days table."""

    day: date
    score: int
    level: str
    recovery_time: Optional[int]
    feedback_short: str


@dataclass
class TrainingReadinessResult:
    """Output of TrainingReadinessAnalyzer.analyze()."""

    period_start: date
    period_end: date
    recent_days: List[ReadinessDay] = field(default_factory=list)
    monthly_score: List[Tuple[str, Optional[float]]] = field(default_factory=list)
    day_count: int = 0


class TrainingReadinessAnalyzer:
    """Compute readiness trend + recent days from garmin.db."""

    def __init__(self, db_dir: str):
        self._db_dir = db_dir

    def _query(self, sql: str, params: Sequence = ()) -> List[tuple]:
        path = os.path.join(self._db_dir, "garmin.db")
        if not os.path.exists(path):
            return []
        try:
            con = sqlite3.connect(path)
            try:
                return con.execute(sql, params).fetchall()
            finally:
                con.close()
        except sqlite3.Error as e:
            logger.warning("Readiness query failed: %s", e)
            return []

    def analyze(self, start_date: date, end_date: date) -> "TrainingReadinessResult":
        rows = self._query(
            "SELECT day, score, level, recovery_time, feedback_short "
            "FROM training_readiness "
            "WHERE date(day) >= ? AND date(day) <= ? AND score IS NOT NULL "
            "ORDER BY day DESC",
            (start_date.isoformat(), end_date.isoformat()),
        )
        days: List[ReadinessDay] = []
        for day, score, level, recovery_time, feedback_short in rows:
            d = _parse_day(day)
            if d is None:
                continue
            days.append(ReadinessDay(
                day=d, score=int(score), level=level or "",
                recovery_time=int(recovery_time) if recovery_time is not None else None,
                feedback_short=feedback_short or ""))
        return TrainingReadinessResult(
            period_start=start_date, period_end=end_date,
            recent_days=days[:RECENT_DAYS],
            monthly_score=_monthly_mean(days, start_date, end_date),
            day_count=len(days),
        )


def _parse_day(value) -> Optional[date]:
    if value is None:
        return None
    text = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _monthly_mean(days: List[ReadinessDay], start: date, end: date):
    buckets = {}
    for d in days:
        buckets.setdefault(f"{d.day.year:04d}-{d.day.month:02d}", []).append(d.score)
    keys = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        keys.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return [(k, round(sum(buckets[k]) / len(buckets[k]), 1) if k in buckets else None)
            for k in keys]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest test/test_readiness_analyzer.py -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add garmindb/analysis/readiness_analyzer.py test/test_readiness_analyzer.py
git commit -m "feat(analysis): training readiness analyzer"
```

---

### Task 6: Builder wiring (LongitudinalReport)

**Files:**
- Modify: `garmindb/analysis/longitudinal_report.py` (import ~line 34; dataclass field ~line 246; builder method ~near `_decoupling` line 1209; `build()` call ~line 401)
- Test: `test/test_longitudinal_report.py` (add one test) — or extend existing

**Interfaces:**
- Consumes: `TrainingReadinessAnalyzer`, `TrainingReadinessResult` (Task 5).
- Produces: `LongitudinalReport.training_readiness: Optional[TrainingReadinessResult]`.

- [ ] **Step 1: Write the failing test**

Add to `test/test_longitudinal_report.py` (mirror its existing fixtures/imports):

```python
    def test_report_has_training_readiness_field(self):
        # The dataclass must expose the field even when None (no data).
        from garmindb.analysis.longitudinal_report import LongitudinalReport
        self.assertIn('training_readiness', LongitudinalReport.__dataclass_fields__)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest test/test_longitudinal_report.py -k training_readiness -v`
Expected: FAIL — field not present.

- [ ] **Step 3: Wire the builder**

In `garmindb/analysis/longitudinal_report.py`:

1. Top imports (near line 34 where `DecouplingResult, PaHrResult` are imported):

```python
from .readiness_analyzer import TrainingReadinessResult
```

2. In the `LongitudinalReport` dataclass (near `decoupling: "Optional[DecouplingResult]" = None`, ~line 246):

```python
    training_readiness: "Optional[TrainingReadinessResult]" = None
```

3. Add a builder method next to `_decoupling` (~line 1216):

```python
    def _training_readiness(self):
        """Training readiness trend over the period (None on any failure)."""
        from .readiness_analyzer import TrainingReadinessAnalyzer
        try:
            return TrainingReadinessAnalyzer(self._db_dir).analyze(self._start, self._end)
        except Exception as e:  # never let readiness break the clinical report
            logger.warning("Longitudinal readiness analysis failed: %s", e)
            return None
```

4. In the `build()` call's local computation (where `decoupling = self._decoupling()` is, ~line 371) add:

```python
        training_readiness = self._training_readiness()
```

5. In the dataclass construction inside `build()` (where `decoupling=decoupling, pahr=pahr,` ~line 401):

```python
            training_readiness=training_readiness,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest test/test_longitudinal_report.py -k training_readiness -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add garmindb/analysis/longitudinal_report.py test/test_longitudinal_report.py
git commit -m "feat(report): carry training readiness in LongitudinalReport"
```

---

### Task 7: Renderer subsection (Section 4)

**Files:**
- Modify: `garmindb/presentation/markdown/longitudinal_renderer.py` (`_training_readiness` method; append inside `_load`)
- Test: `test/test_markdown_presenter.py` (add a test)

**Interfaces:**
- Consumes: `LongitudinalReport.training_readiness` (Task 6).
- Produces: `_training_readiness(self, r) -> str` rendered as a `###` subsection inside Section 4.

- [ ] **Step 1: Write the failing test**

Add to `test/test_markdown_presenter.py`:

```python
    def test_training_readiness_section_renders(self):
        from datetime import date
        from garmindb.analysis.readiness_analyzer import (
            TrainingReadinessResult, ReadinessDay)
        from garmindb.presentation.markdown.longitudinal_renderer import LongitudinalPresenter

        tr = TrainingReadinessResult(
            period_start=date(2026, 6, 1), period_end=date(2026, 6, 30),
            recent_days=[ReadinessDay(date(2026, 6, 22), 69, 'MODERATE', 101, 'RECOVERED_AND_READY')],
            monthly_score=[('2026-06', 69.0)], day_count=1)
        out = LongitudinalPresenter()._training_readiness(type('R', (), {'training_readiness': tr})())
        self.assertIn('Training Readiness', out)
        self.assertIn('69', out)

    def test_training_readiness_section_suppressed_when_empty(self):
        from garmindb.presentation.markdown.longitudinal_renderer import LongitudinalPresenter
        out = LongitudinalPresenter()._training_readiness(type('R', (), {'training_readiness': None})())
        self.assertEqual(out, '')
```

- [ ] **Step 2: Run test to verify it fails**

Run: `PYTHONPATH=. .venv/bin/python -m pytest test/test_markdown_presenter.py -k training_readiness -v`
Expected: FAIL — `_training_readiness` not defined.

- [ ] **Step 3: Add the renderer method and call it from `_load`**

In `garmindb/presentation/markdown/longitudinal_renderer.py`, add the method (near `_decoupling`, ~line 395):

```python
    def _training_readiness(self, r) -> str:
        tr = getattr(r, "training_readiness", None)
        if tr is None or getattr(tr, "day_count", 0) == 0:
            return ""
        body = ["\n### Prontidão de treino (Training Readiness)\n",
                "Score diário 0–100 do Garmin combinando sono, recuperação, VFC, "
                "histórico de stress/sono e carga aguda. Síntese matinal de "
                "prontidão (triagem, não diagnóstico).\n"]
        months = [(ym, sc) for ym, sc in tr.monthly_score if sc is not None]
        if months:
            body.append("| Mês | Score médio |")
            body.append("|---|---|")
            for ym, sc in months:
                body.append(f"| {ym} | {_num(sc, 1)} |")
        if tr.recent_days:
            body.append("\n**Dias recentes:**\n")
            body.append("| Dia | Score | Nível | Recuperação (min) | Feedback |")
            body.append("|---|---|---|---|---|")
            for d in tr.recent_days:
                rt = d.recovery_time if d.recovery_time is not None else "—"
                body.append(f"| {d.day} | {d.score} | {d.level} | {rt} | {d.feedback_short} |")
        body.append(f"\n_{tr.day_count} dia(s) com leitura de prontidão no período._")
        return "\n".join(body)
```

Then, inside `_load(self, r)`, just before its `return "\n".join(lines)`, append the subsection so it nests under "## 4.":

```python
        lines.append(self._training_readiness(r))
```

(If `_load` returns via a different join variable, append to that list before the return.)

- [ ] **Step 4: Run test to verify it passes**

Run: `PYTHONPATH=. .venv/bin/python -m pytest test/test_markdown_presenter.py -k training_readiness -v`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
git add garmindb/presentation/markdown/longitudinal_renderer.py test/test_markdown_presenter.py
git commit -m "feat(render): training readiness subsection in anamnese Section 4"
```

---

### Task 8: End-to-end run, lint, and roadmap changelog

**Files:**
- Modify: `~/.GarminDb/GarminConnectConfig.json` (enable the stat — local only, not committed)
- Modify: `docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md` (changelog)

- [ ] **Step 1: Full test suite + lint**

```bash
make flake8
make -C test analysis
```
Expected: flake8 clean; analysis suite green (including the 5 new test files).

- [ ] **Step 2: Live download + import + report (real data)**

Enable readiness in `~/.GarminDb/GarminConnectConfig.json` `enabled_stats` (add `"training_readiness": true`), then:

```bash
.venv/bin/garmindb_cli.py --training_readiness --download --import --latest
sqlite3 ~/HealthData/DBs/garmin.db "SELECT COUNT(*), MAX(day), MAX(score) FROM training_readiness;"
.venv/bin/python scripts/generate_report.py --anamnesis -o docs/reports/relatorio-anamnese-2025-2026.md
```
Expected: table populated; the anamnesis Section 4 shows the "Prontidão de treino" subsection with a monthly table + recent days. Confirm `recovery_time` unit (minutes) against the Garmin app and adjust the `_col_units`/label if needed.

- [ ] **Step 3: Update the roadmap changelog**

Append a dated entry to `docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md` recording that Training Readiness shipped (and noting decoupling / power import / hrv table were already delivered — the doc was stale). Mark Training Status as the remaining Fase 2 item.

- [ ] **Step 4: Commit (reports + roadmap; config stays local)**

```bash
git add docs/reports/relatorio-anamnese-2025-2026.md docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md
git commit -m "docs: training readiness in anamnese + roadmap changelog"
```

---

## Self-Review

**Spec coverage:** download (Task 3) ✓ · table (Task 1) ✓ · importer w/ list-of-3 latest (Task 2) ✓ · recovery_time as field (Task 1 column + Task 7 render) ✓ · CLI wiring + staleness note (Task 4) ✓ · analyzer + builder + renderer in Section 4 (Tasks 5–7) ✓ · suppression when empty (Task 7) ✓ · coverage line (Task 7) ✓ · tests per layer (every task) ✓ · flake8 + analysis green + roadmap changelog (Task 8) ✓ · recovery_time unit verification (Task 8 Step 2) ✓.

**Placeholder scan:** all code steps contain real code; no TBD/TODO. The one "if `_load` returns differently" note in Task 7 is a guard for the implementer, not a placeholder — the action (append before return) is explicit.

**Type consistency:** `TrainingReadiness` columns (Task 1) match the importer's `point` keys (Task 2) and the analyzer's SELECT columns (Task 5). `TrainingReadinessResult`/`ReadinessDay` fields (Task 5) match the builder field name `training_readiness` (Task 6) and the renderer's attribute reads (Task 7). `Statistics.training_readiness` used consistently (Task 4). Endpoint URL string identical in Task 3 method and constant.
