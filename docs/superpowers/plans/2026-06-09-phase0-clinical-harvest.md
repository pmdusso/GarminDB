# Phase 0 — Clinical Harvest Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface six clinically valuable metrics that GarminDB *already stores but never reads* — SpO2, resting respiration, anaerobic Training Effect, the full HRV band (weekly average + status), overnight Body Battery recharge + sleep architecture, and an operational max-HR ceiling — into the `--anamnesis` longitudinal report, with declared coverage and zero fabrication.

**Architecture:** Extend the existing `data → analysis → presentation` stack. Each metric adds (1) a `MetricSeries` (or small scalar) built inside `LongitudinalReportBuilder.build()` by querying the SQLite DBs directly, and (2) renderer wiring in `LongitudinalPresenter`. No new imports, no DB migrations, no CLI changes — `scripts/generate_report.py --anamnesis` already calls `builder.build()` then `presenter.render()`, so new series flow through untouched.

**Tech Stack:** Python 3, SQLite (`sqlite3` stdlib, read-only via `_query`), dataclasses, pytest (`tmp_path` fixtures), flake8.

---

## Why this is Phase 0 (read first)

The roadmap (`docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md`) re-prioritized power *down* to Phase 1 and put this clinical harvest *first*, because the data is already in the DBs at high coverage:

| Metric | Source table.column | Why it matters clinically |
|---|---|---|
| SpO2 | `garmin.db` `daily_summary.spo2_avg` | Altitude acclimation (mountain race) |
| Respiration | `garmin.db` `daily_summary.rr_waking_avg` | Stress / illness / overreaching marker |
| Anaerobic TE | `garmin_activities.db` `activities.anaerobic_training_effect` | High-intensity dose, next to aerobic TE we already show |
| Full HRV band | `garmin_monitoring.db` `monitoring_hrv_status.{weekly_average, status}` | Autonomic trend; today we read only `last_night_average` |
| Body Battery recharge | `garmin.db` `daily_summary.bb_charged` | Overnight recovery (distinct from `bb_max` peak we show) |
| Sleep architecture | `garmin.db` `sleep.{deep_sleep, light_sleep, rem_sleep, awake, avg_stress}` | Recovery substrate detail |
| Operational max HR | `garmin_activities.db` `activities.max_hr` (per sport, spike-trimmed) | Context for HR zones — NOT a tested max |

**Data-honesty rule (non-negotiable — output goes to a doctor):** every new metric declares its coverage ("N dias/atividades medidos"), nothing is fabricated, and a section with no real data renders nothing. These are Garmin optical-sensor estimates — screening, not diagnosis — and the provenance section says so.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `garmindb/analysis/longitudinal_report.py` | Reads DBs, builds `MetricSeries` + report payload | Add builder methods; register series in `build()`; add 3 fields to `LongitudinalReport`; one module constant |
| `garmindb/presentation/markdown/longitudinal_renderer.py` | Renders `LongitudinalReport` → clinician Markdown | Add `_respiratory` section; extend `_cardiovascular`, `_aerobic`, `_recovery`; add panel rows; add provenance caveats |
| `test/test_longitudinal_clinical.py` | **New** — Phase 0 metric tests with self-contained full-schema synthetic DBs | Created in Task 1; one+ test function per task |
| `docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md` | Roadmap changelog | Task 7 marks Fase 0 status |

**Why a new test module** (`test_longitudinal_clinical.py`) instead of extending `test/test_longitudinal_report.py`: the existing file's synthetic DBs use minimal schemas (no `spo2_avg`, `bb_charged`, etc.). The new module ships full Phase-0 schemas once, so each task only adds rows + assertions. The existing tests stay green untouched because `_query` degrades missing columns to `[]` (verified in Task 1).

---

## Task 1: SpO2 trend + the shared test scaffold + `_daily_series` coverage note

This task does triple duty: it creates the new test module with comprehensive synthetic-DB writers (reused by Tasks 2–6), extends the shared `_daily_series` helper with an optional coverage note, and ships the first metric (SpO2) plus a new `## 2b. Respiratório` renderer section that Task 2 will also populate.

**Files:**
- Create: `test/test_longitudinal_clinical.py`
- Modify: `garmindb/analysis/longitudinal_report.py` (extend `_daily_series`; register `series["spo2"]` in `build()`)
- Modify: `garmindb/presentation/markdown/longitudinal_renderer.py` (add `_respiratory`; wire into `render()`; panel row; provenance)

- [ ] **Step 1: Write the new test module with full-schema writers + the SpO2 failing test**

Create `test/test_longitudinal_clinical.py`:

```python
# test/test_longitudinal_clinical.py
"""Tests for Phase 0 clinical metrics in the longitudinal anamnesis report.

Covers the 'harvest what we already store' metrics: SpO2, resting respiration,
anaerobic Training Effect, the full HRV band (weekly average + status),
overnight Body Battery recharge, sleep architecture, and operational max HR.

The synthetic-DB writers create the FULL Phase-0 schema so each metric test
supplies only the rows it cares about. The builder reads these DBs exactly like
production; columns left empty degrade to 'no data', never crash.
"""

import os
import sqlite3
from datetime import date, datetime

from garmindb.analysis.longitudinal_report import LongitudinalReportBuilder
from garmindb.analysis.performance_targets import PerformanceTargets
from garmindb.presentation.markdown.longitudinal_renderer import (
    LongitudinalPresenter,
)

GEN = datetime(2026, 6, 8, 12, 0, 0)


def _write_garmin_db(db_dir, *, daily=None, sleep=None, attrs=None, weight=None):
    """daily: {date: {spo2_avg, rr_waking_avg, bb_charged, bb_max, bb_min, rhr,
    stress_avg}}. sleep: {date: {total, deep, light, rem, awake, avg_stress,
    avg_spo2, avg_rr, score}}. Values default to NULL when a key is absent."""
    con = sqlite3.connect(os.path.join(db_dir, "garmin.db"))
    con.execute("CREATE TABLE attributes (timestamp TEXT, key TEXT, value TEXT)")
    for k, v in (attrs or {}).items():
        con.execute("INSERT INTO attributes VALUES (?,?,?)",
                    ("2026-06-08 00:00:00", k, str(v)))
    con.execute(
        "CREATE TABLE daily_summary "
        "(day TEXT, rhr INTEGER, stress_avg INTEGER, bb_max INTEGER, "
        "bb_min INTEGER, bb_charged INTEGER, spo2_avg FLOAT, spo2_min FLOAT, "
        "rr_waking_avg FLOAT, rr_max FLOAT, rr_min FLOAT)")
    for d, v in (daily or {}).items():
        con.execute(
            "INSERT INTO daily_summary "
            "(day, rhr, stress_avg, bb_max, bb_min, bb_charged, spo2_avg, "
            "rr_waking_avg) VALUES (?,?,?,?,?,?,?,?)",
            (f"{d} 00:00:00", v.get("rhr"), v.get("stress_avg"), v.get("bb_max"),
             v.get("bb_min"), v.get("bb_charged"), v.get("spo2_avg"),
             v.get("rr_waking_avg")))
    con.execute(
        "CREATE TABLE sleep "
        "(day TEXT, total_sleep TEXT, deep_sleep TEXT, light_sleep TEXT, "
        "rem_sleep TEXT, awake TEXT, avg_spo2 FLOAT, avg_rr FLOAT, "
        "avg_stress FLOAT, score INTEGER)")
    for d, v in (sleep or {}).items():
        con.execute(
            "INSERT INTO sleep (day, total_sleep, deep_sleep, light_sleep, "
            "rem_sleep, awake, avg_spo2, avg_rr, avg_stress, score) "
            "VALUES (?,?,?,?,?,?,?,?,?,?)",
            (f"{d} 00:00:00", v.get("total"), v.get("deep"), v.get("light"),
             v.get("rem"), v.get("awake"), v.get("avg_spo2"), v.get("avg_rr"),
             v.get("avg_stress"), v.get("score")))
    con.execute("CREATE TABLE weight (day TEXT, weight FLOAT)")
    for d, kg in (weight or {}).items():
        con.execute("INSERT INTO weight VALUES (?,?)", (f"{d} 00:00:00", kg))
    con.commit()
    con.close()


def _write_activities_db(db_dir, activities):
    """activities: list of {id, day, sport, km, moving, ascent, load, te,
    anaerobic_te, avg_hr, max_hr, cal}."""
    con = sqlite3.connect(os.path.join(db_dir, "garmin_activities.db"))
    con.execute(
        "CREATE TABLE activities "
        "(activity_id TEXT, start_time TEXT, sport TEXT, distance FLOAT, "
        "moving_time TEXT, ascent FLOAT, training_load FLOAT, "
        "training_effect FLOAT, anaerobic_training_effect FLOAT, "
        "avg_hr INTEGER, max_hr INTEGER, calories INTEGER)")
    con.execute("CREATE TABLE cycle_activities (activity_id TEXT, vo2_max FLOAT)")
    con.execute("CREATE TABLE steps_activities (activity_id TEXT, vo2_max FLOAT)")
    for a in activities:
        con.execute(
            "INSERT INTO activities (activity_id, start_time, sport, distance, "
            "moving_time, ascent, training_load, training_effect, "
            "anaerobic_training_effect, avg_hr, max_hr, calories) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (str(a["id"]), f"{a['day']} 10:00:00", a.get("sport", "cycling"),
             a.get("km", 0.0), a.get("moving", "01:00:00"), a.get("ascent", 0.0),
             a.get("load"), a.get("te"), a.get("anaerobic_te"),
             a.get("avg_hr"), a.get("max_hr"), a.get("cal", 0)))
    con.commit()
    con.close()


def _write_monitoring_db(db_dir, hrv=None):
    """hrv: {date: {last_night_average, weekly_average, baseline_low,
    baseline_high, status}}."""
    con = sqlite3.connect(os.path.join(db_dir, "garmin_monitoring.db"))
    con.execute(
        "CREATE TABLE monitoring_hrv_status "
        "(timestamp TEXT, weekly_average FLOAT, last_night FLOAT, "
        "last_night_average FLOAT, baseline_low FLOAT, baseline_high FLOAT, "
        "status INTEGER, reading_count INTEGER)")
    for d, v in (hrv or {}).items():
        con.execute(
            "INSERT INTO monitoring_hrv_status (timestamp, weekly_average, "
            "last_night_average, baseline_low, baseline_high, status) "
            "VALUES (?,?,?,?,?,?)",
            (f"{d} 07:00:00", v.get("weekly_average"),
             v.get("last_night_average"), v.get("baseline_low"),
             v.get("baseline_high"), v.get("status")))
    con.commit()
    con.close()


def _builder(db_dir, start, end, targets=None):
    return LongitudinalReportBuilder(
        db_dir=str(db_dir), targets=targets or PerformanceTargets(),
        start_date=start, end_date=end, generated_at=GEN,
    )


def _spread_daily(start, months, value_fn):
    """5 days per month, each day's dict = value_fn('YYYY-MM')."""
    out = {}
    y, m = start.year, start.month
    for _ in range(months):
        for d in range(1, 6):
            out[date(y, m, d).isoformat()] = value_fn(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


# --------------------------------------------------------------------------- #
# SpO2
# --------------------------------------------------------------------------- #

def test_spo2_series_monthly_mean_and_coverage_note(tmp_path):
    daily = _spread_daily(date(2025, 1, 1), 6,
                          lambda ym: {"spo2_avg": 97.0 if ym < "2025-04"
                                      else 94.0})
    _write_garmin_db(str(tmp_path), daily=daily)
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 6, 30)).build()
    spo2 = report.series["spo2"]
    assert spo2.points[0] == ("2025-01", 97.0)
    assert spo2.current == 94.0
    assert spo2.better == "up"
    # Coverage is declared, not implied: 30 measured days (6 months x 5 days).
    assert spo2.note is not None and "30 dias medidos" in spo2.note


def test_spo2_renders_in_respiratory_section(tmp_path):
    daily = _spread_daily(date(2025, 1, 1), 3, lambda ym: {"spo2_avg": 96.0})
    _write_garmin_db(str(tmp_path), daily=daily)
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 3, 31)).build()
    md = LongitudinalPresenter().render(report)
    assert "Respiratório" in md
    assert "SpO2" in md


def test_respiratory_section_absent_when_no_spo2_or_rr(tmp_path):
    _write_garmin_db(str(tmp_path), daily=_spread_daily(
        date(2025, 1, 1), 2, lambda ym: {"rhr": 50}))
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 2, 28)).build()
    md = LongitudinalPresenter().render(report)
    assert "Respiratório" not in md
```

- [ ] **Step 2: Run the SpO2 tests to verify they fail**

Run: `python -m pytest test/test_longitudinal_clinical.py -v`
Expected: FAIL — `KeyError: 'spo2'` (series not registered) and `"Respiratório" not in md`.

(`uv run pytest test/test_longitudinal_clinical.py -v` is equivalent if you prefer the project venv.)

- [ ] **Step 3: Extend `_daily_series` with an optional coverage note**

In `garmindb/analysis/longitudinal_report.py`, change the `_daily_series` signature and body. Find:

```python
    def _daily_series(
        self, db: str, table: str, col: str, day_col: str,
        *, key: str, label: str, unit: str, better: str, decimals: int,
    ) -> MetricSeries:
        rows = self._query(
            db,
            f"SELECT {day_col}, {col} FROM {table} "
            f"WHERE date({day_col}) >= ? AND date({day_col}) <= ? "
            f"AND {col} IS NOT NULL",
            (self._start.isoformat(), self._end.isoformat()),
        )
        daily = {}
        for d, v in rows:
            day = _parse_date(d)
            if day is not None and v is not None:
                daily[day] = float(v)
        s = MetricSeries(key=key, label=label, unit=unit, better=better,
                         decimals=decimals)
        s.points = self._monthly_mean_points(daily, decimals)
        s.baseline, s.baseline_low, s.baseline_high = \
            self._baseline_band(daily, decimals)
        return s
```

Replace with (adds `coverage_note` param + sets `s.note` with the measured-day count):

```python
    def _daily_series(
        self, db: str, table: str, col: str, day_col: str,
        *, key: str, label: str, unit: str, better: str, decimals: int,
        coverage_note: Optional[str] = None,
    ) -> MetricSeries:
        rows = self._query(
            db,
            f"SELECT {day_col}, {col} FROM {table} "
            f"WHERE date({day_col}) >= ? AND date({day_col}) <= ? "
            f"AND {col} IS NOT NULL",
            (self._start.isoformat(), self._end.isoformat()),
        )
        daily = {}
        for d, v in rows:
            day = _parse_date(d)
            if day is not None and v is not None:
                daily[day] = float(v)
        s = MetricSeries(key=key, label=label, unit=unit, better=better,
                         decimals=decimals)
        s.points = self._monthly_mean_points(daily, decimals)
        s.baseline, s.baseline_low, s.baseline_high = \
            self._baseline_band(daily, decimals)
        # Declare coverage explicitly when asked (data-honesty: the reader is a
        # clinician and must see how many days back a trend). Default None keeps
        # the existing callers (rhr/stress/etc.) unchanged.
        if coverage_note is not None and daily:
            s.note = f"{len(daily)} dias medidos no período — {coverage_note}"
        return s
```

- [ ] **Step 4: Register the SpO2 series in `build()`**

In `garmindb/analysis/longitudinal_report.py`, in `build()`, find the block that registers physiology series (after `series["body_battery"] = ...`). Add right after it:

```python
        series["spo2"] = self._daily_series(
            "garmin.db", "daily_summary", "spo2_avg", "day",
            key="spo2", label="SpO2 (saturação de O2)", unit="%", better="up",
            decimals=1,
            coverage_note=("relevante para aclimatação a altitude "
                           "(prova de montanha); estimativa óptica de pulso"),
        )
```

- [ ] **Step 5: Add the `_respiratory` renderer section and wire it in**

In `garmindb/presentation/markdown/longitudinal_renderer.py`, in `render()`, find:

```python
        parts.append(self._cardiovascular(report))
        parts.append(self._aerobic(report))
```

Change to insert the new section between them:

```python
        parts.append(self._cardiovascular(report))
        parts.append(self._respiratory(report))
        parts.append(self._aerobic(report))
```

Then add the `_respiratory` method (place it right after `_cardiovascular`). It already handles the `respiracao` series so Task 2 needs no further renderer change — both metrics share this section:

```python
    def _respiratory(self, r: LongitudinalReport) -> str:
        """SpO2 + resting respiration. Numbered 2b to avoid renumbering the
        existing 1-8 sections. Renders nothing when both series are empty."""
        spo2 = r.series.get("spo2")
        rr = r.series.get("respiracao")
        present = [s for s in (spo2, rr) if s and s.values]
        if not present:
            return ""
        lines = ["\n## 2b. Respiratório / aclimatação a altitude\n"]
        lines.append(
            "SpO2 (saturação periférica de O2) e frequência respiratória de "
            "repouso ajudam a triar tolerância a altitude e carga "
            "respiratória/estresse. Estimativas ópticas de pulso — triagem, "
            "não oximetria clínica.\n")
        for s in present:
            lines.append(self._metric_summary_line(s))
        lines.append("")
        cols = []
        if spo2 and spo2.values:
            cols.append(("SpO2 (%)", spo2, 1))
        if rr and rr.values:
            cols.append(("FR repouso (rpm)", rr, 1))
        lines.append(self._months_table(r, cols))
        for s in present:
            if s.note:
                lines.append(f"\n_{s.note}._")
        return "\n".join(lines) + "\n"
```

- [ ] **Step 6: Add SpO2 to the executive panel and a provenance caveat**

In `longitudinal_renderer.py`, in `_panel`, find the `order` list and append `("spo2", 1)`:

```python
        order = [
            ("rhr", 0), ("hrv", 0), ("vo2max_cycling", 0), ("vo2max_running", 0),
            ("ctl", 0), ("weight", 1), ("sleep", 1), ("sleep_score", 0),
            ("stress", 0), ("body_battery", 0), ("spo2", 1),
        ]
```

In `_provenance`, add a caveat line before the closing "Este relatório é um resumo..." bullet:

```python
            "- **SpO2 e frequência respiratória** são estimativas do sensor "
            "óptico de pulso (Pulse Ox / respiração), não oximetria/capnografia "
            "clínica — usar para tendência e triagem de altitude, não diagnóstico.\n"
```

- [ ] **Step 7: Run the SpO2 tests to verify they pass**

Run: `python -m pytest test/test_longitudinal_clinical.py -v`
Expected: PASS (3 tests).

- [ ] **Step 8: Prove zero regression on the existing longitudinal suite**

Run: `python -m pytest test/test_longitudinal_report.py -v`
Expected: PASS (all existing tests). This proves the `_query` graceful-degradation claim: the old synthetic DBs lack `spo2_avg`, the new SELECT raises "no such column", `_query` returns `[]`, the SpO2 series is empty, and `_respiratory` renders nothing.

- [ ] **Step 9: Lint the touched modules**

Run: `python -m flake8 garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py --max-line-length=180 --ignore=E203,E221,E241,W503`
Expected: no output (clean).

- [ ] **Step 10: Commit**

```bash
git add test/test_longitudinal_clinical.py garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py
git commit -m "feat(anamnesis): harvest SpO2 trend + respiratory section scaffold"
```

---

## Task 2: Resting respiration trend

The `_respiratory` section (Task 1) already renders a `respiracao` series if present — this task only builds it and adds the panel row.

**Files:**
- Modify: `garmindb/analysis/longitudinal_report.py` (register `series["respiracao"]`)
- Modify: `garmindb/presentation/markdown/longitudinal_renderer.py` (panel row)
- Test: `test/test_longitudinal_clinical.py`

- [ ] **Step 1: Write the failing test**

Append to `test/test_longitudinal_clinical.py`:

```python
# --------------------------------------------------------------------------- #
# Respiration
# --------------------------------------------------------------------------- #

def test_respiration_series_and_renders_with_spo2(tmp_path):
    daily = _spread_daily(
        date(2025, 1, 1), 4,
        lambda ym: {"spo2_avg": 96.0,
                    "rr_waking_avg": 13.0 if ym < "2025-03" else 16.0})
    _write_garmin_db(str(tmp_path), daily=daily)
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 4, 30)).build()
    rr = report.series["respiracao"]
    assert rr.points[0] == ("2025-01", 13.0)
    assert rr.current == 16.0
    assert rr.better == "down"          # rising resting RR is unfavourable
    assert rr.note is not None and "dias medidos" in rr.note
    md = LongitudinalPresenter().render(report)
    assert "FR repouso (rpm)" in md
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest test/test_longitudinal_clinical.py::test_respiration_series_and_renders_with_spo2 -v`
Expected: FAIL — `KeyError: 'respiracao'`.

- [ ] **Step 3: Register the respiration series in `build()`**

In `longitudinal_report.py` `build()`, add right after the `series["spo2"] = ...` block from Task 1:

```python
        series["respiracao"] = self._daily_series(
            "garmin.db", "daily_summary", "rr_waking_avg", "day",
            key="respiracao", label="Freq. respiratória (repouso)", unit="rpm",
            better="down", decimals=1,
            coverage_note=("FR de repouso elevada acompanha "
                           "estresse/doença/overreaching"),
        )
```

- [ ] **Step 4: Add respiration to the executive panel**

In `longitudinal_renderer.py` `_panel`, extend the `order` list with `("respiracao", 1)`:

```python
        order = [
            ("rhr", 0), ("hrv", 0), ("vo2max_cycling", 0), ("vo2max_running", 0),
            ("ctl", 0), ("weight", 1), ("sleep", 1), ("sleep_score", 0),
            ("stress", 0), ("body_battery", 0), ("spo2", 1), ("respiracao", 1),
        ]
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest test/test_longitudinal_clinical.py -v`
Expected: PASS (all clinical tests so far).

- [ ] **Step 6: Lint**

Run: `python -m flake8 garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py --max-line-length=180 --ignore=E203,E221,E241,W503`
Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add test/test_longitudinal_clinical.py garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py
git commit -m "feat(anamnesis): harvest resting respiration trend"
```

---

## Task 3: Anaerobic Training Effect series

Per-activity metric (0–5 scale) aggregated to a monthly mean — modelled on the existing `_vo2max_series` (per-activity → monthly), rendered into Section 3 next to the aerobic VO2max it complements.

**Files:**
- Modify: `garmindb/analysis/longitudinal_report.py` (add `_anaerobic_te_series`; register in `build()`)
- Modify: `garmindb/presentation/markdown/longitudinal_renderer.py` (extend `_aerobic`)
- Test: `test/test_longitudinal_clinical.py`

- [ ] **Step 1: Write the failing test**

Append to `test/test_longitudinal_clinical.py`:

```python
# --------------------------------------------------------------------------- #
# Anaerobic Training Effect
# --------------------------------------------------------------------------- #

def test_anaerobic_te_monthly_mean_and_render(tmp_path):
    _write_garmin_db(str(tmp_path))
    _write_activities_db(str(tmp_path), [
        {"id": 1, "day": "2025-02-05", "anaerobic_te": 2.0},
        {"id": 2, "day": "2025-02-20", "anaerobic_te": 4.0},   # Feb mean = 3.0
        {"id": 3, "day": "2025-03-10", "anaerobic_te": 1.0},
    ])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 3, 31)).build()
    te = report.series["anaerobic_te"]
    assert dict(te.points)["2025-02"] == 3.0
    assert dict(te.points)["2025-03"] == 1.0
    assert dict(te.points)["2025-01"] is None    # no activity -> gap, not zero
    assert te.note is not None and "3 atividades" in te.note
    md = LongitudinalPresenter().render(report)
    assert "anaeróbico" in md
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest test/test_longitudinal_clinical.py::test_anaerobic_te_monthly_mean_and_render -v`
Expected: FAIL — `KeyError: 'anaerobic_te'`.

- [ ] **Step 3: Add the `_anaerobic_te_series` builder method**

In `longitudinal_report.py`, add this method right after `_vo2max_series` (it shares that method's per-activity → monthly shape, but takes a *mean* since anaerobic TE is a dose, not a best-of):

```python
    def _anaerobic_te_series(self) -> MetricSeries:
        """Monthly MEAN anaerobic Training Effect (0-5) across activities.

        Unlike VO2max (best estimate per month), anaerobic TE is a per-session
        high-intensity dose, so the monthly mean is the meaningful summary.
        """
        rows = self._query(
            "garmin_activities.db",
            "SELECT start_time, anaerobic_training_effect FROM activities "
            "WHERE anaerobic_training_effect IS NOT NULL "
            "AND date(start_time) >= ? AND date(start_time) <= ?",
            (self._start.isoformat(), self._end.isoformat()),
        )
        monthly: Dict[str, List[float]] = {}
        for ts, v in rows:
            day = _parse_date(ts)
            if day is None or v is None:
                continue
            monthly.setdefault(_ym(day), []).append(float(v))
        s = MetricSeries(
            key="anaerobic_te", label="Training Effect anaeróbico",
            unit="", better="neutral", decimals=1)
        s.points = [
            (ym, round(sum(monthly[ym]) / len(monthly[ym]), 4)
             if ym in monthly else None)
            for ym in _month_keys(self._start, self._end)
        ]
        n = sum(len(v) for v in monthly.values())
        s.note = (f"{n} atividades com TE anaeróbico; escala 0–5 (estímulo de "
                  "alta intensidade), complementa o TE aeróbico") if n else None
        return s
```

Then register it in `build()`, right after the `series["vo2max_running"] = ...` line:

```python
        series["anaerobic_te"] = self._anaerobic_te_series()
```

- [ ] **Step 4: Render it into Section 3 (`_aerobic`)**

In `longitudinal_renderer.py`, in `_aerobic`, find:

```python
        for key in ("vo2max_cycling", "vo2max_running"):
            lines.append(self._metric_summary_line(r.series.get(key)))
        lines.append("")
        lines.append(self._months_table(
            r,
            [("VO2max ciclismo", r.series.get("vo2max_cycling"), 0),
             ("VO2max corrida", r.series.get("vo2max_running"), 0)],
        ))
```

Replace with (adds anaerobic TE summary line + a months-table column + note):

```python
        for key in ("vo2max_cycling", "vo2max_running", "anaerobic_te"):
            lines.append(self._metric_summary_line(r.series.get(key)))
        lines.append("")
        lines.append(self._months_table(
            r,
            [("VO2max ciclismo", r.series.get("vo2max_cycling"), 0),
             ("VO2max corrida", r.series.get("vo2max_running"), 0),
             ("TE anaeróbico", r.series.get("anaerobic_te"), 1)],
        ))
        te = r.series.get("anaerobic_te")
        if te and te.note:
            lines.append(f"\n_{te.note}._")
```

- [ ] **Step 5: Run the test to verify it passes**

Run: `python -m pytest test/test_longitudinal_clinical.py -v`
Expected: PASS.

- [ ] **Step 6: Lint**

Run: `python -m flake8 garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py --max-line-length=180 --ignore=E203,E221,E241,W503`
Expected: no output.

- [ ] **Step 7: Commit**

```bash
git add test/test_longitudinal_clinical.py garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py
git commit -m "feat(anamnesis): harvest anaerobic Training Effect series"
```

---

## Task 4: Full HRV band — weekly average + status

Today the report reads only `last_night_average`. This adds the longer-range `weekly_average` trend and the categorical `status`. **Deliberate data-honesty decision:** we do NOT plot Garmin's `baseline_low/high` columns — the existing code comment (`_hrv_series`) documents that they sit on a different/legacy scale (~33–40 ms vs ~50–76 ms nightly) and would print a band that doesn't contain its own mean. We surface the same-scale `weekly_average` plus the status label instead.

**Files:**
- Modify: `garmindb/analysis/longitudinal_report.py` (module const `_HRV_STATUS`; methods `_hrv_weekly_series`, `_hrv_status`; 2 new fields on `LongitudinalReport`; register in `build()`)
- Modify: `garmindb/presentation/markdown/longitudinal_renderer.py` (extend `_cardiovascular`; provenance)
- Test: `test/test_longitudinal_clinical.py`

- [ ] **Step 1: Write the failing test**

Append to `test/test_longitudinal_clinical.py`:

```python
# --------------------------------------------------------------------------- #
# Full HRV band (weekly average + status)
# --------------------------------------------------------------------------- #

def _hrv_rows(start, months, weekly_fn, status_fn):
    out = {}
    y, m = start.year, start.month
    for _ in range(months):
        for d in range(1, 6):
            ym = f"{y:04d}-{m:02d}"
            out[date(y, m, d).isoformat()] = {
                "last_night_average": weekly_fn(ym),
                "weekly_average": weekly_fn(ym),
                "status": status_fn(ym),
            }
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return out


def test_hrv_weekly_series_and_status(tmp_path):
    hrv = _hrv_rows(date(2025, 1, 1), 4,
                    weekly_fn=lambda ym: 70.0 if ym < "2025-03" else 60.0,
                    status_fn=lambda ym: 4 if ym < "2025-03" else 3)
    _write_garmin_db(str(tmp_path))
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), hrv)
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 4, 30)).build()
    weekly = report.series["hrv_weekly"]
    assert weekly.points[0] == ("2025-01", 70.0)
    assert weekly.current == 60.0
    # Latest status (March/April = 3 -> "baixo"); end window is late April.
    assert report.hrv_status_latest == "baixo"
    assert report.hrv_status_balanced_pct is not None
    md = LongitudinalPresenter().render(report)
    assert "média semanal" in md
    assert "Status VFC" in md


def test_hrv_status_absent_when_no_status_rows(tmp_path):
    # weekly_average present but status all NULL -> no status line, no crash.
    hrv = _hrv_rows(date(2025, 1, 1), 2,
                    weekly_fn=lambda ym: 65.0, status_fn=lambda ym: None)
    _write_garmin_db(str(tmp_path))
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), hrv)
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 2, 28)).build()
    assert report.hrv_status_latest is None
    assert report.hrv_status_balanced_pct is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest test/test_longitudinal_clinical.py -k hrv -v`
Expected: FAIL — `KeyError: 'hrv_weekly'` / `AttributeError: ... 'hrv_status_latest'`.

- [ ] **Step 3: Add the `_HRV_STATUS` constant and two builder methods**

In `longitudinal_report.py`, add the module constant near the other constants (after `_SPARK_BLOCKS`):

```python
# Garmin HRV status codes (monitoring_hrv_status.status).
_HRV_STATUS = {2: "ruim", 3: "baixo", 4: "equilibrado"}
```

Add these two methods right after `_hrv_series`:

```python
    def _hrv_weekly_series(self) -> MetricSeries:
        """Weekly-average rMSSD trend (same ms scale as the nightly series)."""
        rows = self._query(
            "garmin_monitoring.db",
            "SELECT timestamp, weekly_average FROM monitoring_hrv_status "
            "WHERE date(timestamp) >= ? AND date(timestamp) <= ? "
            "AND weekly_average IS NOT NULL",
            (self._start.isoformat(), self._end.isoformat()),
        )
        daily = {}
        for ts, v in rows:
            day = _parse_date(ts)
            if day is not None and v is not None:
                daily[day] = float(v)
        s = MetricSeries(key="hrv_weekly", label="VFC média semanal (Garmin)",
                         unit="ms", better="up", decimals=0)
        s.points = self._monthly_mean_points(daily, 0)
        s.baseline, s.baseline_low, s.baseline_high = \
            self._baseline_band(daily, 0)
        return s

    def _hrv_status(self) -> Tuple[Optional[str], Optional[float]]:
        """Latest HRV status label + % of the last 30 days marked 'balanced'.

        We use the categorical status (not Garmin's baseline_low/high columns,
        which are on a different/legacy scale -- see _hrv_series).
        """
        rows = self._query(
            "garmin_monitoring.db",
            "SELECT status FROM monitoring_hrv_status "
            "WHERE status IS NOT NULL AND status > 0 "
            "AND date(timestamp) >= ? AND date(timestamp) <= ? "
            "ORDER BY timestamp",
            ((self._end - timedelta(days=30)).isoformat(),
             self._end.isoformat()),
        )
        statuses = [int(r[0]) for r in rows if r[0] is not None]
        if not statuses:
            return None, None
        latest = _HRV_STATUS.get(statuses[-1])
        balanced = 100.0 * sum(1 for s in statuses if s == 4) / len(statuses)
        return latest, round(balanced, 0)
```

- [ ] **Step 4: Add two fields to the `LongitudinalReport` dataclass**

In `longitudinal_report.py`, find the end of the `@dataclass class LongitudinalReport` field list:

```python
    current_month_partial: bool
    confidence_score: Optional[float]
```

Add the two new fields immediately after:

```python
    current_month_partial: bool
    confidence_score: Optional[float]
    hrv_status_latest: Optional[str]
    hrv_status_balanced_pct: Optional[float]
```

- [ ] **Step 5: Register the series + status in `build()`**

In `build()`, register the weekly series next to the other HRV/physiology series (after `series["hrv"] = self._hrv_series()`):

```python
        series["hrv_weekly"] = self._hrv_weekly_series()
```

Then compute the status just before the `return LongitudinalReport(` and pass the two new fields. Find:

```python
        return LongitudinalReport(
            generated_at=self._generated,
```

Insert before it:

```python
        hrv_status_latest, hrv_status_balanced = self._hrv_status()
```

And add the two arguments to the `LongitudinalReport(...)` call, right after `confidence_score=confidence,`:

```python
            confidence_score=confidence,
            hrv_status_latest=hrv_status_latest,
            hrv_status_balanced_pct=hrv_status_balanced,
        )
```

- [ ] **Step 6: Render the weekly trend + status into Section 2 (`_cardiovascular`)**

In `longitudinal_renderer.py`, in `_cardiovascular`, find:

```python
        lines.append(self._months_table(
            r,
            [("FC rep. (bpm)", r.series.get("rhr"), 0),
             ("VFC (ms)", r.series.get("hrv"), 0),
             ("Estresse", r.series.get("stress"), 0)],
        ))
        hrv = r.series.get("hrv")
        if hrv and hrv.note:
            lines.append(f"\n_{hrv.note}._")
        return "\n".join(lines) + "\n"
```

Replace with (adds a weekly-HRV column and a status line, both guarded for emptiness):

```python
        weekly = r.series.get("hrv_weekly")
        cols = [("FC rep. (bpm)", r.series.get("rhr"), 0),
                ("VFC noturna (ms)", r.series.get("hrv"), 0),
                ("Estresse", r.series.get("stress"), 0)]
        if weekly and weekly.values:
            cols.insert(2, ("VFC média semanal (ms)", weekly, 0))
        lines.append(self._months_table(r, cols))
        hrv = r.series.get("hrv")
        if hrv and hrv.note:
            lines.append(f"\n_{hrv.note}._")
        if r.hrv_status_latest:
            extra = ""
            if r.hrv_status_balanced_pct is not None:
                extra = (f" · {r.hrv_status_balanced_pct:.0f}% dos últimos 30 "
                         "dias em equilíbrio")
            lines.append(
                f"\n- **Status VFC (Garmin):** {r.hrv_status_latest}{extra}. "
                "Categoria do próprio Garmin; a banda de base do fabricante usa "
                "uma escala distinta da VFC noturna e por isso não é plotada "
                "como faixa.")
        return "\n".join(lines) + "\n"
```

- [ ] **Step 7: Run the HRV tests to verify they pass**

Run: `python -m pytest test/test_longitudinal_clinical.py -k hrv -v`
Expected: PASS (2 tests).

- [ ] **Step 8: Confirm no regression (new dataclass fields)**

Run: `python -m pytest test/test_longitudinal_report.py test/test_longitudinal_clinical.py -v`
Expected: PASS. The two new required fields are populated only inside `build()`, the sole construction site, so existing tests are unaffected.

- [ ] **Step 9: Lint**

Run: `python -m flake8 garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py --max-line-length=180 --ignore=E203,E221,E241,W503`
Expected: no output.

- [ ] **Step 10: Commit**

```bash
git add test/test_longitudinal_clinical.py garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py
git commit -m "feat(anamnesis): harvest full HRV band (weekly avg + status)"
```

---

## Task 5: Overnight Body Battery recharge + sleep architecture

Two recovery additions into Section 5: `bb_charged` (overnight recharge — distinct from the `bb_max` peak already shown) and the sleep-stage breakdown (`deep/light/rem/awake` as hours, plus `avg_stress` during sleep). Sleep stages are stored as `TIME` strings, so they need a stage-series helper mirroring the existing `_sleep_series` (which uses `_parse_hms`).

**Files:**
- Modify: `garmindb/analysis/longitudinal_report.py` (add `_sleep_stage_series`; register 6 series in `build()`)
- Modify: `garmindb/presentation/markdown/longitudinal_renderer.py` (extend `_recovery`)
- Test: `test/test_longitudinal_clinical.py`

- [ ] **Step 1: Write the failing test**

Append to `test/test_longitudinal_clinical.py`:

```python
# --------------------------------------------------------------------------- #
# Body Battery recharge + sleep architecture
# --------------------------------------------------------------------------- #

def test_bb_charged_and_sleep_architecture(tmp_path):
    daily = _spread_daily(date(2025, 1, 1), 3,
                          lambda ym: {"bb_charged": 60, "bb_max": 90})
    sleep = {}
    for d in daily:
        sleep[d] = {"total": "07:30:00", "deep": "01:30:00",
                    "light": "04:00:00", "rem": "02:00:00", "awake": "00:20:00",
                    "avg_stress": 18.0, "score": 80}
    _write_garmin_db(str(tmp_path), daily=daily, sleep=sleep)
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 3, 31)).build()
    assert report.series["bb_charged"].current == 60.0
    assert report.series["bb_charged"].better == "up"
    assert report.series["sleep_deep"].current == 1.5      # 1h30 -> 1.5 h
    assert report.series["sleep_rem"].current == 2.0
    # 00:20:00 = 0.3333 h; monthly means are stored at 4 dp, so compare at 2 dp.
    assert round(report.series["sleep_awake"].current, 2) == 0.33
    assert report.series["sleep_stress"].current == 18.0
    md = LongitudinalPresenter().render(report)
    assert "recarga noturna" in md
    assert "Sono profundo" in md
    assert "Arquitetura do sono" in md
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest test/test_longitudinal_clinical.py::test_bb_charged_and_sleep_architecture -v`
Expected: FAIL — `KeyError: 'bb_charged'`.

- [ ] **Step 3: Add the `_sleep_stage_series` helper**

In `longitudinal_report.py`, add this method right after `_sleep_series` (it converts the `TIME` string to hours via `_parse_hms`, like `_sleep_series` does for `total_sleep`):

```python
    def _sleep_stage_series(
        self, col: str, *, key: str, label: str, better: str,
    ) -> MetricSeries:
        """Monthly mean of one sleep stage (stored as a TIME string), in hours."""
        rows = self._query(
            "garmin.db",
            f"SELECT day, {col} FROM sleep "
            f"WHERE date(day) >= ? AND date(day) <= ? AND {col} IS NOT NULL",
            (self._start.isoformat(), self._end.isoformat()),
        )
        daily = {}
        for d, val in rows:
            day = _parse_date(d)
            if day is None or val is None:
                continue
            hours = _parse_hms(val) / 3600.0
            if hours > 0:
                daily[day] = hours
        s = MetricSeries(key=key, label=label, unit="h", better=better,
                         decimals=1)
        s.points = self._monthly_mean_points(daily, 2)
        s.baseline = round(s.mean, 1) if s.mean is not None else None
        return s
```

- [ ] **Step 4: Register the recovery series in `build()`**

In `build()`, add after the existing `series["body_battery"] = ...` block (or after the SpO2/respiration blocks — order within the dict does not matter):

```python
        series["bb_charged"] = self._daily_series(
            "garmin.db", "daily_summary", "bb_charged", "day",
            key="bb_charged", label="Body Battery (recarga noturna)", unit="",
            better="up", decimals=0,
            coverage_note="recarga durante o sono (reserva de recuperação)",
        )
        series["sleep_deep"] = self._sleep_stage_series(
            "deep_sleep", key="sleep_deep", label="Sono profundo", better="up")
        series["sleep_light"] = self._sleep_stage_series(
            "light_sleep", key="sleep_light", label="Sono leve",
            better="neutral")
        series["sleep_rem"] = self._sleep_stage_series(
            "rem_sleep", key="sleep_rem", label="Sono REM", better="up")
        series["sleep_awake"] = self._sleep_stage_series(
            "awake", key="sleep_awake", label="Acordado (na cama)",
            better="down")
        series["sleep_stress"] = self._daily_series(
            "garmin.db", "sleep", "avg_stress", "day",
            key="sleep_stress", label="Estresse durante o sono", unit="",
            better="down", decimals=0,
            coverage_note="estresse autonômico médio medido durante o sono",
        )
```

- [ ] **Step 5: Render into Section 5 (`_recovery`)**

In `longitudinal_renderer.py`, find the whole `_recovery` method body and replace it:

```python
    def _recovery(self, r: LongitudinalReport) -> str:
        lines = ["\n## 5. Recuperação: sono e Body Battery\n"]
        lines.append(
            "Sono é o principal substrato de recuperação; o teto de Body Battery "
            "integra carga e recuperação num único proxy de reserva energética.\n")
        for key in ("sleep", "sleep_score", "body_battery", "bb_charged"):
            lines.append(self._metric_summary_line(r.series.get(key)))
        lines.append("")
        lines.append(self._months_table(
            r,
            [("Sono (h)", r.series.get("sleep"), 1),
             ("Pont. sono", r.series.get("sleep_score"), 0),
             ("BB pico", r.series.get("body_battery"), 0),
             ("BB recarga", r.series.get("bb_charged"), 0)],
        ))
        # Sleep architecture: only render when at least one stage has data.
        stages = [("Profundo (h)", r.series.get("sleep_deep"), 1),
                  ("Leve (h)", r.series.get("sleep_light"), 1),
                  ("REM (h)", r.series.get("sleep_rem"), 1),
                  ("Acordado (h)", r.series.get("sleep_awake"), 1),
                  ("Estresse sono", r.series.get("sleep_stress"), 0)]
        if any(s and s.values for _, s, _ in stages):
            lines.append("\n**Arquitetura do sono (médias mensais):**\n")
            lines.append(self._months_table(r, stages))
            lines.append(
                "\n_Estágios de sono e estresse são estimativas do dispositivo "
                "(não polissonografia); úteis como tendência de qualidade._")
        return "\n".join(lines) + "\n"
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m pytest test/test_longitudinal_clinical.py::test_bb_charged_and_sleep_architecture -v`
Expected: PASS.

- [ ] **Step 7: Confirm no regression**

Run: `python -m pytest test/test_longitudinal_report.py test/test_longitudinal_clinical.py -v`
Expected: PASS. (The existing smoke test's `sleep` table has no `deep_sleep`/`avg_stress` columns → those queries return `[]` → the architecture sub-block is skipped.)

- [ ] **Step 8: Lint**

Run: `python -m flake8 garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py --max-line-length=180 --ignore=E203,E221,E241,W503`
Expected: no output.

- [ ] **Step 9: Commit**

```bash
git add test/test_longitudinal_clinical.py garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py
git commit -m "feat(anamnesis): harvest overnight BB recharge + sleep architecture"
```

---

## Task 6: Operational max-HR ceiling (spike-trimmed, per sport)

Raw `activities.max_hr` can spike to ~230 on a single optical misread. The operational ceiling takes the value at index `int(0.95 * (n - 1))` of the ascending per-activity `max_hr` list per sport — which discards the lone top spike while keeping a realistic ceiling. It is explicitly **not** a strap-tested HR max; it only contextualises zones.

**Files:**
- Modify: `garmindb/analysis/longitudinal_report.py` (add `_operational_max_hr`; 1 new field on `LongitudinalReport`; populate in `build()`)
- Modify: `garmindb/presentation/markdown/longitudinal_renderer.py` (line in `_cardiovascular`)
- Test: `test/test_longitudinal_clinical.py`

- [ ] **Step 1: Write the failing test**

Append to `test/test_longitudinal_clinical.py`:

```python
# --------------------------------------------------------------------------- #
# Operational max HR
# --------------------------------------------------------------------------- #

def test_operational_max_hr_drops_spike(tmp_path):
    _write_garmin_db(str(tmp_path))
    _write_activities_db(str(tmp_path), [
        {"id": 1, "day": "2025-02-01", "sport": "cycling", "max_hr": 150},
        {"id": 2, "day": "2025-02-05", "sport": "cycling", "max_hr": 155},
        {"id": 3, "day": "2025-02-10", "sport": "cycling", "max_hr": 158},
        {"id": 4, "day": "2025-02-15", "sport": "cycling", "max_hr": 160},
        {"id": 5, "day": "2025-02-20", "sport": "cycling", "max_hr": 230},
        {"id": 6, "day": "2025-02-02", "sport": "running", "max_hr": 175},
    ])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 2, 28)).build()
    # idx = int(0.95 * (5-1)) = 3 -> sorted[3] = 160, the 230 spike is dropped.
    assert report.operational_max_hr["cycling"] == 160
    assert report.operational_max_hr["running"] == 175    # single value
    md = LongitudinalPresenter().render(report)
    assert "FC máx operacional" in md
    assert "ciclismo ~160 bpm" in md


def test_operational_max_hr_empty_when_no_activities(tmp_path):
    _write_garmin_db(str(tmp_path))
    _write_activities_db(str(tmp_path), [])
    _write_monitoring_db(str(tmp_path), {})
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 2, 28)).build()
    assert report.operational_max_hr == {"cycling": None, "running": None}
    md = LongitudinalPresenter().render(report)
    assert "FC máx operacional" not in md
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest test/test_longitudinal_clinical.py -k operational -v`
Expected: FAIL — `AttributeError: ... 'operational_max_hr'`.

- [ ] **Step 3: Add the `_operational_max_hr` builder method**

In `longitudinal_report.py`, add near the other per-activity readers (e.g. after `_vo2max_series` / `_anaerobic_te_series`):

```python
    def _operational_max_hr(self) -> Dict[str, Optional[int]]:
        """Spike-trimmed max-HR ceiling per main sport.

        A single optical misread can spike one activity's max_hr to ~230. Taking
        the value at index int(0.95*(n-1)) of the ascending per-activity list
        discards that lone top spike while keeping a realistic ceiling. This is
        NOT a tested/strap HR max -- it only contextualises HR zones.
        """
        out: Dict[str, Optional[int]] = {}
        for sport in ("cycling", "running"):
            rows = self._query(
                "garmin_activities.db",
                "SELECT max_hr FROM activities WHERE sport = ? "
                "AND max_hr IS NOT NULL AND max_hr > 0 "
                "AND date(start_time) >= ? AND date(start_time) <= ?",
                (sport, self._start.isoformat(), self._end.isoformat()),
            )
            vals = sorted(int(r[0]) for r in rows if r[0] is not None)
            if not vals:
                out[sport] = None
                continue
            out[sport] = vals[int(0.95 * (len(vals) - 1))]
        return out
```

- [ ] **Step 4: Add the field to `LongitudinalReport` and populate in `build()`**

In `longitudinal_report.py`, extend the dataclass field list (after the Task 4 fields):

```python
    hrv_status_latest: Optional[str]
    hrv_status_balanced_pct: Optional[float]
    operational_max_hr: Dict[str, Optional[int]]
```

In `build()`, compute it next to the HRV status (before the `return`):

```python
        operational_max_hr = self._operational_max_hr()
```

And pass it in the `LongitudinalReport(...)` call after the HRV status args:

```python
            hrv_status_latest=hrv_status_latest,
            hrv_status_balanced_pct=hrv_status_balanced,
            operational_max_hr=operational_max_hr,
        )
```

- [ ] **Step 5: Render the line in Section 2 (`_cardiovascular`)**

In `longitudinal_renderer.py`, in `_cardiovascular`, just before the final `return "\n".join(lines) + "\n"`, add:

```python
        omh = r.operational_max_hr or {}
        omh_parts = []
        if omh.get("cycling"):
            omh_parts.append(f"ciclismo ~{omh['cycling']} bpm")
        if omh.get("running"):
            omh_parts.append(f"corrida ~{omh['running']} bpm")
        if omh_parts:
            lines.append(
                "\n- **FC máx operacional** (p95 das atividades, descarta spike "
                "de sensor): " + " · ".join(omh_parts) + " — **não** é FC máx de "
                "teste com cinta; usar só para contextualizar zonas.")
```

- [ ] **Step 6: Run the test to verify it passes**

Run: `python -m pytest test/test_longitudinal_clinical.py -k operational -v`
Expected: PASS (2 tests).

- [ ] **Step 7: Full regression + lint**

Run: `python -m pytest test/test_longitudinal_report.py test/test_longitudinal_clinical.py -v`
Expected: PASS (all).

Run: `python -m flake8 garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py --max-line-length=180 --ignore=E203,E221,E241,W503`
Expected: no output.

- [ ] **Step 8: Commit**

```bash
git add test/test_longitudinal_clinical.py garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py
git commit -m "feat(anamnesis): add spike-trimmed operational max-HR ceiling"
```

---

## Task 7: Definition-of-Done verification + roadmap changelog

Final integration: prove the whole suite is green, smoke-test the renderer end-to-end with every Phase-0 metric populated at once, and record Fase 0 status in the roadmap.

**Files:**
- Modify: `test/test_longitudinal_clinical.py` (one end-to-end render smoke test)
- Modify: `docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md` (changelog)

- [ ] **Step 1: Write an end-to-end smoke test exercising all six metrics together**

Append to `test/test_longitudinal_clinical.py`:

```python
# --------------------------------------------------------------------------- #
# End-to-end: every Phase 0 metric populated at once
# --------------------------------------------------------------------------- #

def test_phase0_full_render_smoke(tmp_path):
    daily = _spread_daily(
        date(2025, 1, 1), 6,
        lambda ym: {"rhr": 50, "stress_avg": 28, "bb_max": 88,
                    "bb_min": 22, "bb_charged": 58, "spo2_avg": 96.0,
                    "rr_waking_avg": 14.0})
    sleep = {d: {"total": "07:30:00", "deep": "01:20:00", "light": "04:10:00",
                 "rem": "02:00:00", "awake": "00:15:00", "avg_stress": 17.0,
                 "score": 81} for d in daily}
    hrv = _hrv_rows(date(2025, 1, 1), 6, weekly_fn=lambda ym: 66.0,
                    status_fn=lambda ym: 4)
    _write_garmin_db(
        str(tmp_path), daily=daily, sleep=sleep,
        attrs={"name": "Test Athlete", "year_of_birth": 1988,
               "gender": "Gender.male", "height": 1.91, "time_zone": "UTC"},
        weight={"2025-06-10": 85.0})
    _write_activities_db(str(tmp_path), [
        {"id": 1, "day": "2025-03-05", "sport": "cycling", "km": 50.0,
         "moving": "02:00:00", "load": 120, "te": 3.0, "anaerobic_te": 2.5,
         "max_hr": 168, "cyc_vo2": 55},
    ])
    _write_monitoring_db(str(tmp_path), hrv)
    report = _builder(tmp_path, date(2025, 1, 1), date(2025, 6, 30)).build()
    md = LongitudinalPresenter().render(report)
    # All six harvested families are present and labelled.
    for needle in ("SpO2", "Respiratório", "FR repouso", "anaeróbico",
                   "média semanal", "Status VFC", "recarga noturna",
                   "Arquitetura do sono", "FC máx operacional"):
        assert needle in md, f"missing: {needle}"
    # Data-honesty: still no power data, FTP still a configured goal.
    assert "Não há dados de potência" in md
```

Note: `_write_activities_db` ignores `cyc_vo2`; VO2max coverage is exercised in `test_longitudinal_report.py`, so this smoke test focuses on the Phase-0 families. Drop the `cyc_vo2` key if you prefer a strict per-helper contract.

- [ ] **Step 2: Run the full suite**

Run: `python -m pytest test/test_longitudinal_report.py test/test_longitudinal_clinical.py -v`
Expected: PASS (every test, including the new smoke test).

- [ ] **Step 3: (Optional, if real DBs are present) Generate against live data and eyeball coverage**

Only if `~/HealthData/DBs/garmin.db` exists on this machine:

Run: `python scripts/generate_report.py --anamnesis > /tmp/anamnesis_phase0.md && rg -n "SpO2|Respiratório|anaeróbico|média semanal|recarga noturna|Arquitetura do sono|FC máx operacional|dias medidos" /tmp/anamnesis_phase0.md`
Expected: each harvested metric appears with a real "N dias/atividades medidos" coverage note. If a metric is missing, that is honest (no data in that DB) — confirm against the coverage audit, do not fabricate.

- [ ] **Step 4: Update the roadmap changelog**

In `docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md`, append to the `## Changelog` section:

```markdown
- **2026-06-09 Fase 0 executada:** colhidos os clínicos já capturados no relatório `--anamnesis` — SpO2, frequência respiratória, Training Effect anaeróbico, banda completa de VFC (média semanal + status), recarga noturna de Body Battery, arquitetura do sono e FC máx operacional (descarta spike). Plano executável: `docs/superpowers/plans/2026-06-09-phase0-clinical-harvest.md`. Cobertura declarada por métrica; nada fabricado; zero import e zero migração. Próximo: **Fase 1 — Potência (via summary files)**.
```

- [ ] **Step 5: Lint the production modules one final time**

Run: `python -m flake8 garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py --max-line-length=180 --ignore=E203,E221,E241,W503`
Expected: no output.

- [ ] **Step 6: Commit**

```bash
git add test/test_longitudinal_clinical.py docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md
git commit -m "test(anamnesis): Phase 0 end-to-end smoke + roadmap changelog"
```

---

## Definition of Done (Phase 0)

- [ ] All six metric families appear in `--anamnesis` output, each with a declared coverage note ("N dias/atividades medidos").
- [ ] Every new section renders **nothing** when its series are empty (no fabricated zeros, no empty tables).
- [ ] `python -m pytest test/test_longitudinal_report.py test/test_longitudinal_clinical.py` is fully green.
- [ ] `python -m flake8 garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py --max-line-length=180 --ignore=E203,E221,E241,W503` is clean.
- [ ] No DB migration, no new import path, no CLI flag added — `generate_report.py --anamnesis` is unchanged.
- [ ] Provenance section states SpO2/respiration/HRV-status are optical-sensor estimates (screening, not diagnosis); the HRV baseline scale-mismatch is documented.
- [ ] Roadmap changelog records Fase 0 done and points to Fase 1 (power).

---

## Self-Review

**Spec coverage** — the six roadmap Fase 0 bullets map 1:1 to Tasks 1–6: SpO2 (T1), respiration (T2), anaerobic TE (T3), full HRV band (T4), Body Battery charge + detailed sleep (T5), operational max HR — "p99/mean-max 5s, não max cru" satisfied here by the spike-trimmed p95-by-index over per-activity max_hr, since per-second streams live only in the `.fit` (Phase 2) (T6). The DoD ("cobertura declarada, 1 teste por métrica, nenhuma fabricação") is enforced by the `coverage_note` mechanism, the per-metric tests, and the empty-section guards.

**Placeholder scan** — every code step shows complete, paste-ready code; every run step shows the exact command and expected result. No "TBD"/"add validation"/"similar to Task N".

**Type consistency** — series keys are used identically across builder and renderer: `spo2`, `respiracao`, `anaerobic_te`, `hrv_weekly`, `bb_charged`, `sleep_deep|light|rem|awake`, `sleep_stress`. The three new `LongitudinalReport` fields (`hrv_status_latest`, `hrv_status_balanced_pct`, `operational_max_hr`) are declared once (T4/T6) and populated only in `build()`. `_daily_series` gains one backward-compatible optional param (`coverage_note`). Method names (`_anaerobic_te_series`, `_hrv_weekly_series`, `_hrv_status`, `_sleep_stage_series`, `_operational_max_hr`) are referenced consistently.

**Risk note** — the only cross-task coupling is the shared test module and the `LongitudinalReport` dataclass field list; both are append-only and verified green after each task. The graceful-degradation contract (`_query` swallowing "no such column") is the safety net for the untouched existing suite and is explicitly re-verified in Tasks 1, 4, and 5.
