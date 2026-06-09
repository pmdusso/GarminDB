# SP1 — Import per-second power into the DB (SPEC)

Status: **DRAFT — awaiting approval. No code written yet.**
Phase: 2 ("Profundidade"), sub-project 1. Branch (when approved): `phase2-sp1-power-import`.

## 1. Problem

Cycling power (watts) is the single most valuable missing signal for the
sports-medicine report. It is present in the raw `.fit` files but **dropped on
import**: the per-second `activity_records` table has no `power` column, so
mean-max power curves, NP/IF, and Pa:Hr decoupling (SP2b) cannot be computed
from the DB. SP1 makes per-second power a first-class DB column.

## 2. Evidence (verified in this repo / runtime)

- `record` FIT message field 7 = `PowerField()`, `_name='power'`, `_units='watts'`
  (`fitfile/definition_message_data.py:459`, `fitfile/fields.py:301`).
- **Runtime-confirmed:** parsing a real ride, `message.fields.get('power')`
  returns watts (e.g. `203, 202, 392, 397, 445…`); rides with no meter return
  `None`.
- `ActivityFitFileProcessor._write_record_entry` builds the record dict at
  `activity_fit_file_processor.py:68-81` with **no `power` key** (it reads
  `heart_rate`, `cadence`, `speed`, etc. via `message_fields.get(...)`).
- `ActivityRecords` (`activities_db.py:274`) has **no power column**;
  `table_version = 3`. PK = `(activity_id, record)`. Writes are **insert-only**
  (guarded by `ActivityRecords.s_exists`, line 67) → re-import never updates an
  existing row.
- Migration machinery (idbutils): **there is NO auto-migration / ALTER path.**
  `db_attributes.table_version_check` (`db_attributes.py:30-35`) compares the
  stored `activity_records.version` to the code's `table_version` and **raises
  `RuntimeError("…version mismatch… Please rebuild the DB")`** on mismatch.
  Schema is created with SQLAlchemy `metadata.create_all` (`db.py:60`), which
  only creates *missing* tables — it never alters an existing one.

## 3. Consequences that shape the design

1. Adding a column + bumping `table_version` 3→4 means an existing v3
   `garmin_activities.db` will **refuse to open** until rebuilt — by design.
2. Because writes are insert-only, a plain `--import` over existing files would
   **not** backfill power into the 4.7M already-present rows. Backfill therefore
   requires either a full rebuild (drop + recreate + re-parse) or an explicit
   in-place ALTER + per-row UPDATE.

## 4. Proposed change

### 4.1 Schema (`garmindb/garmindb/activities_db.py`)
- Add `power = Column(Integer)  # watts` to `ActivityRecords`.
- Bump `ActivityRecords.table_version` `3 → 4`.

### 4.2 Processor (`garmindb/activity_fit_file_processor.py`)
- Add `'power': message_fields.get('power'),` to the record dict (68-81).
- **Refactor for testability:** extract the dict build into a pure
  `@staticmethod _record_dict(fit_file, message_fields, record_num, activity_id)`
  returning the dict; `_write_record_entry` calls it. No behaviour change; lets
  us unit-test the NULL-when-absent guarantee without a DB/session.

### 4.3 Migration / backfill — **decision needed (see §7)**
- **Option A (recommended, idbutils-blessed):** the version bump forces a
  rebuild of `garmin_activities.db`. Document/run
  `garmindb_cli.py --rebuild_db` (deletes the enabled-stats DBs and re-imports
  from the **retained** `.fit` files — 1190 present locally), repopulating
  `activity_records` *with* power. Simple, correct, consistent with the
  project's documented "version mismatch → rebuild" guidance. Cost: re-parse all
  activity `.fit` (minutes). Other DBs (garmin.db, monitoring) are also
  rebuilt — acceptable and idempotent.
- **Option B (optional power-user, more code/risk):** a one-off migration
  script — `ALTER TABLE activity_records ADD COLUMN power INTEGER`, set the
  stored `activity_records.version` attribute to 4, then a dedicated backfill
  that parses each `.fit` and **UPDATEs** power per `(activity_id, record)`
  (cannot reuse the insert-only path). Avoids touching the other DBs but
  re-parses the same files anyway and adds bespoke UPDATE logic.

Recommendation: **Option A** as the shipped path; mention B as a documented
alternative, build it only if you ask.

## 5. Test plan (pure-unit; no committed `.fit` fixture exists)

`test/test_files/fit/activity` holds only a readme (users drop their own files),
so we cannot rely on a binary fixture. Tests (runnable via
`.venv/bin/python -m pytest`):

1. **Schema:** `ActivityRecords` has a `power` `Column`; `table_version == 4`.
2. **Power present:** `_record_dict` with a fake `message_fields` exposing
   `get('power')→250` yields `record['power'] == 250`.
3. **No meter (the key guarantee):** `message_fields.get('power')→None` yields
   `record['power'] is None` — imports NULL silently, no error.
4. **Regression:** existing `test_activities_db.py` assertions on
   `ActivityRecords` still pass (run via the unittest path).
5. *(Optional, skipped if absent)* if a user `.fit` with power is present under
   `test_files/`, import it and assert `power` is populated.

## 6. Risks & mitigations

- **Forced rebuild surprises the user** → call it out explicitly; it is the
  documented idbutils behaviour, not a bug. Mitigate by clearly stating the
  rebuild command and that `.fit` files are retained so no re-download occurs.
- **Indoor/virtual power** is real (trainer power), so no filtering needed at
  import; consumers decide context (SP2b will).
- **Storage growth:** one nullable INTEGER over 4.7M rows ≈ a few MB. Negligible.
- **Plugin path:** `_plugin_dispatch('write_record_entry', …)` may already inject
  keys; `record.update(plugin_record)` runs after our dict, so a plugin can still
  override power — preserved, no conflict.

## 7. Open questions for you

1. **Migration strategy:** Option A (rebuild, recommended) or also build
   Option B (in-place ALTER + UPDATE backfill)?
2. **Scope of rebuild:** OK to rebuild all enabled-stats DBs via `--rebuild_db`,
   or do you want an activities-only rebuild path?
3. Should SP1 also add a **summary** power column anywhere (e.g. nothing in
   `activities` changes here — avg/NP power already live elsewhere), or keep SP1
   strictly to per-second `activity_records`? (Recommend: strictly per-second.)

## 8. Task breakdown (once approved)

1. Schema: add `power` column + bump `table_version` to 4 (+ schema test).
2. Processor: extract `_record_dict`, add `power` (+ unit tests 2 & 3).
3. Migration: document the rebuild; (optional) Option B script + test.
4. Capstone: rebuild locally, sanity-check real power lands in
   `activity_records`, run the activities-db regression, flake8 touched files.

## 9. Rollback

Revert the two source edits and the `table_version` bump → next rebuild
restores the v3 schema. No data loss beyond the (re-derivable) power column.
