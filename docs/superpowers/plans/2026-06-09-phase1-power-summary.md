# Phase 1 — Power via Summary Files Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Surface real, data-honest cycling power (eFTP, indoor/outdoor mean-max curves, 7-zone distribution, neuromuscular peak, W/kg) from Garmin's pre-computed summary JSONs — gated by a moderate publication rule — into **both** the `--performance` and `--anamnesis` reports, and remove the now-false "no power data" claims from the clinician report.

**Architecture:** `PowerAnalyzer` (file-based, DB-free) becomes the single source of truth: it classifies indoor/outdoor, builds separate curves, computes an eFTP **publication gate**, and exposes a neuromuscular peak + NP variability. Both report builders consume that one result; weight pairing (±7 d, for W/kg) happens in the builders that have DB access. No new parsing, no DB migration, no per-second streams (confirmed unrecoverable).

**Tech Stack:** Python 3, stdlib `json`/`glob`, dataclasses, SQLite (read-only via the longitudinal builder's `_query`), pytest (`tmp_path`), flake8.

**Research:** `docs/superpowers/specs/2026-06-09-phase1-power-research.md` (ground-truth keys, coverage, integration points, eFTP/NP best practices, cited sources). Read it for context.

---

## Decisions locked (from the user, 2026-06-09)

- **(a) Gate = moderate:** publish "measured eFTP" only if a 20-min effort within **6 weeks** (42 d), **IF ≥ 0.90**, **≥ 3 rides** carrying `maxAvgPower_1200` in the window; eFTP = best-20 × 0.95. Else fall back to "FTP configurado X W (não testado nestes dados)".
- **(b) Indoor/outdoor = separate curves.** Headline eFTP from **outdoor if its gate passes**, else **indoor** eFTP explicitly labelled "≈8–12% déficit vs outdoor". 536 indoor / 66 outdoor.
- **(c) Output = both reports.** Sequence: `--performance` first (cheap — fields already computed), then `--anamnesis`. The anamnesis "no power data" falsehood is corrected **regardless** of whether an eFTP is published.
- **(d) NP = trust stored `normPower`,** variability-only, gated to `duration ≥ 1800 s`; never an FTP/IF *output* (it IS used as the gate's IF numerator: IF = NP / configured FTP).
- **(bonus) Show BOTH** configured FTP (325) and measured eFTP with the gap, instead of one silently overwriting the other.

## Ground-truth facts the code depends on (from research)

- Summary key truths: `maxAvgPower_<N>` (int W), `powerTimeInZone_1..7` (float s), `avgPower`/`maxPower`/`normPower`/`max20MinPower` (float W), `duration` (float s), `startTimeLocal` ("YYYY-MM-DD ..."), `activityType.typeKey` (str), `manufacturer` (str), `excludeFromPowerCurveReports` (bool). `distance` is **meters**.
- **Indoor rule:** `typeKey ∈ {indoor_cycling, virtual_ride}` **OR** `manufacturer ∈ {TACX, THE_SUFFERFEST, TRAINER_ROAD, VIRTUALTRAINING}` (case-insensitive). GPS does NOT distinguish (TACX rides carry simulated GPS).
- **NP trap:** on 37% of rides `normPower > max20MinPower` (interval/erg surges). NP is variability, not a 20-min proxy.
- **Per-second watts are gone** (0/1190 details files) — no NP recompute.
- The analyzer already reads the right keys and already half-computes all-time curves; the renderers **drop** the computed fields. The anamnesis report hardcodes "no power" in 3 places + a module docstring.

## Backward-compatibility contract (must stay green)

- `PowerRide` is constructed **positionally** by `test/test_power_analyzer.py` with 6 args → every new field MUST have a default and be appended at the end.
- `test/test_power_analyzer_analyze.py` asserts the legacy `estimated_ftp` (= recent best-20 × 0.95), `best_20min_recent`, `ftp_needs_test`, `power_zone_distribution`, `rides_with_power`, `skipped_files`, and the "FTP" insight — **keep all of them**. The new gate (`eftp_measured`) is additive.
- `test/test_performance_report.py`, `test/test_performance_renderer.py`, `test/test_performance_cli_smoke.py` must stay green. The Phase-0 `test/test_longitudinal_*.py` stay green **except** two assertions that intentionally change in Task 6 (they currently `assert "Não há dados de potência" in md` — Phase 1 removes that falsehood, so Task 6 rewrites them to assert the honest fallback wording).

## CRITICAL environment note (every task)

Run all Python through the project venv — the global pyenv interpreter lacks deps:
- Tests: `.venv/bin/python -m pytest <files> -v`
- flake8: `.venv/bin/python -m flake8 <files> --max-line-length=180 --ignore=E203,E221,E241,W503`
  (the lint target excludes `garmindb/analysis/` & `presentation/`, so lint touched files directly).

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `garmindb/analysis/power_analyzer.py` | File-based power source of truth | T1 classification/sanity; T2 separate curves + peak; T3 gate; T4 NP + insights |
| `garmindb/analysis/performance_report.py` | `--performance` builder | T5 consume gate, both FTPs, paired weight |
| `garmindb/presentation/markdown/performance_renderer.py` | `--performance` renderer | T5 un-drop curve/zones/peak/both-FTP |
| `garmindb/analysis/longitudinal_report.py` | `--anamnesis` builder (SQLite) | T6 wire PowerAnalyzer, power field, weight pairing; docstring |
| `garmindb/presentation/markdown/longitudinal_renderer.py` | `--anamnesis` renderer | T6 measured-power block; fix 3 "no power" strings |
| `scripts/generate_report.py` | CLI | T6 pass `activities_dir` to the longitudinal builder |
| `test/test_power_analyzer_phase1.py` | **New** — Phase 1 analyzer tests | T1–T4 |
| `test/test_performance_power_phase1.py` | **New** — performance wiring tests | T5 |
| `test/test_longitudinal_power_phase1.py` | **New** — anamnesis power tests | T6 |
| `docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md` | Roadmap changelog | T7 |

---

## Task 1: Ride classification, duration, exclude & sanity drop

Add indoor/outdoor classification, ride duration, and artifact filtering to the parse layer. New `PowerRide` fields are appended with defaults (positional back-compat preserved).

**Files:**
- Modify: `garmindb/analysis/power_analyzer.py`
- Test: `test/test_power_analyzer_phase1.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `test/test_power_analyzer_phase1.py`:

```python
# test/test_power_analyzer_phase1.py
"""Phase 1 power tests: indoor/outdoor split, gate, peak, NP, W/kg inputs."""

from datetime import date

from garmindb.analysis.power_analyzer import PowerAnalyzer, PowerRide


# --------------------------------------------------------------------------- #
# Task 1 — classification / duration / exclude / sanity
# --------------------------------------------------------------------------- #

def test_parse_ride_classifies_indoor_by_type():
    data = {"activityType": {"typeKey": "indoor_cycling"},
            "startTimeLocal": "2026-05-20 10:00:00", "maxAvgPower_1200": 250}
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None and ride.is_indoor is True


def test_parse_ride_classifies_indoor_by_manufacturer():
    # typeKey "cycling" but a TACX trainer -> indoor (356 such rides exist).
    data = {"activityType": {"typeKey": "cycling"}, "manufacturer": "TACX",
            "startTimeLocal": "2026-05-20 10:00:00", "maxAvgPower_1200": 250}
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None and ride.is_indoor is True


def test_parse_ride_classifies_outdoor():
    data = {"activityType": {"typeKey": "road_biking"}, "manufacturer": "GARMIN",
            "startTimeLocal": "2026-05-20 10:00:00", "maxAvgPower_1200": 300,
            "duration": 5400.0}
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None
    assert ride.is_indoor is False
    assert ride.duration_s == 5400.0


def test_parse_ride_honors_exclude_flag():
    data = {"activityType": {"typeKey": "cycling"},
            "startTimeLocal": "2026-05-20 10:00:00", "maxAvgPower_1200": 250,
            "excludeFromPowerCurveReports": True}
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None and ride.exclude is True


def test_parse_ride_sanity_drops_impossible_curve():
    # best-20min (27) below ride average (72) is physically impossible -> exclude.
    data = {"activityType": {"typeKey": "cycling"},
            "startTimeLocal": "2026-05-20 10:00:00",
            "avgPower": 72.0, "maxAvgPower_1200": 27}
    ride = PowerAnalyzer._parse_ride(data)
    assert ride is not None and ride.exclude is True
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest test/test_power_analyzer_phase1.py -v`
Expected: FAIL — `AttributeError: 'PowerRide' object has no attribute 'is_indoor'`.

- [ ] **Step 3: Add the classification constants and `PowerRide` fields**

In `garmindb/analysis/power_analyzer.py`, after `CYCLING_TYPES` (line ~27) add:

```python
# Indoor detection: explicit indoor sport types OR a trainer-app manufacturer.
# GPS presence does NOT separate them (TACX rides carry simulated GPS).
_INDOOR_TYPES = {"indoor_cycling", "virtual_ride"}
_INDOOR_MANUFACTURERS = {"TACX", "THE_SUFFERFEST", "TRAINER_ROAD", "VIRTUALTRAINING"}


def _is_indoor(type_key: str, manufacturer) -> bool:
    if type_key in _INDOOR_TYPES:
        return True
    return str(manufacturer or "").upper() in _INDOOR_MANUFACTURERS
```

Extend the `PowerRide` dataclass — append three fields **with defaults** (positional back-compat: existing tests build `PowerRide(date, sport, None, None, {...}, {})`):

```python
@dataclass
class PowerRide:
    """One ride's parsed power summary."""

    date: date
    sport: str
    avg_power: Optional[float]
    norm_power: Optional[float]
    peak_power: Dict[int, float]          # duration_s -> best avg watts
    power_time_in_zone: Dict[int, float]  # zone (1..7) -> seconds
    is_indoor: bool = False               # trainer/virtual vs outdoor power-meter
    duration_s: Optional[float] = None    # timer seconds (NP>=30min gate)
    exclude: bool = False                 # excludeFromPowerCurveReports / sanity
```

- [ ] **Step 4: Populate the new fields in `_parse_ride`**

In `_parse_ride`, replace the final `return PowerRide(...)` block (and add classification/sanity just before it). The method should end like this (keep the sport-filter, curve, zones, and date parsing above unchanged):

```python
        start = (data.get("startTimeLocal") or "")[:10]
        try:
            ride_date = datetime.strptime(start, "%Y-%m-%d").date()
        except ValueError:
            return None

        avg = data.get("avgPower")
        best20 = peak.get(1200)
        # Sanity: a 20-min best below the whole-ride average is impossible
        # (malformed export). Honor Garmin's own exclude flag too.
        exclude = bool(data.get("excludeFromPowerCurveReports"))
        if avg is not None and best20 is not None and float(best20) < float(avg):
            exclude = True

        return PowerRide(
            date=ride_date,
            sport=sport,
            avg_power=avg,
            norm_power=data.get("normPower"),
            peak_power=peak,
            power_time_in_zone=zones,
            is_indoor=_is_indoor(sport, data.get("manufacturer")),
            duration_s=(float(data["duration"])
                        if data.get("duration") is not None else None),
            exclude=exclude,
        )
```

- [ ] **Step 5: Run to verify pass + no regression**

Run: `.venv/bin/python -m pytest test/test_power_analyzer_phase1.py test/test_power_analyzer.py test/test_power_analyzer_analyze.py -v`
Expected: PASS (new Task-1 tests + the existing power tests unchanged).

- [ ] **Step 6: flake8**

Run: `.venv/bin/python -m flake8 garmindb/analysis/power_analyzer.py --max-line-length=180 --ignore=E203,E221,E241,W503`
Expected: clean.

- [ ] **Step 7: Commit**

```bash
git add test/test_power_analyzer_phase1.py garmindb/analysis/power_analyzer.py
git commit -m "feat(power): classify indoor/outdoor + duration + artifact filtering"
```

---

## Task 2: Separate indoor/outdoor curves, per-env eFTP & neuromuscular peak

Split the all-time mean-max curve by environment, compute an (ungated) eFTP per environment, and expose the best-5 s neuromuscular peak. All additive to `PowerAnalysisResult`.

**Files:**
- Modify: `garmindb/analysis/power_analyzer.py`
- Test: `test/test_power_analyzer_phase1.py`

- [ ] **Step 1: Write the failing test**

Append to `test/test_power_analyzer_phase1.py`:

```python
import json
import os


def _write(folder, aid, day, *, indoor=False, **fields):
    payload = {
        "activityType": {"typeKey": "indoor_cycling" if indoor else "road_biking"},
        "manufacturer": "TACX" if indoor else "GARMIN",
        "startTimeLocal": f"{day} 10:00:00",
    }
    payload.update(fields)
    with open(os.path.join(folder, f"activity_{aid}.json"), "w") as f:
        json.dump(payload, f)


# --------------------------------------------------------------------------- #
# Task 2 — separate curves + per-env eFTP + peak 5s
# --------------------------------------------------------------------------- #

def test_separate_indoor_outdoor_curves_and_peak(tmp_path):
    folder = str(tmp_path)
    _write(folder, 1, "2026-05-10", indoor=True, maxAvgPower_1200=260,
           maxAvgPower_5=700, duration=3600.0)
    _write(folder, 2, "2026-05-12", indoor=False, maxAvgPower_1200=300,
           maxAvgPower_5=820, duration=5400.0)
    analyzer = PowerAnalyzer(folder, configured_ftp=325)
    r = analyzer.analyze(date(2026, 1, 1), date(2026, 6, 7))
    assert r.curve_indoor[1200] == 260
    assert r.curve_outdoor[1200] == 300
    assert r.eftp_indoor == round(260 * 0.95)
    assert r.eftp_outdoor == round(300 * 0.95)
    assert r.peak_5s == 820            # best 5-s across all (outdoor here)


def test_excluded_ride_is_dropped_from_curves(tmp_path):
    folder = str(tmp_path)
    _write(folder, 1, "2026-05-12", indoor=False, maxAvgPower_1200=300,
           duration=5400.0)
    _write(folder, 2, "2026-05-13", indoor=False, maxAvgPower_1200=999,
           excludeFromPowerCurveReports=True, duration=5400.0)
    analyzer = PowerAnalyzer(folder, configured_ftp=325)
    r = analyzer.analyze(date(2026, 1, 1), date(2026, 6, 7))
    assert r.curve_outdoor[1200] == 300     # the 999 W excluded ride is ignored
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest test/test_power_analyzer_phase1.py -k "separate or excluded" -v`
Expected: FAIL — `AttributeError: ... 'curve_indoor'`.

- [ ] **Step 3: Add the new result fields**

In `PowerAnalysisResult`, append (after `skipped_files`, before `insights`):

```python
    skipped_files: int = 0                 # corrupt/unreadable JSONs ignored
    curve_indoor: Dict[int, float] = field(default_factory=dict)
    curve_outdoor: Dict[int, float] = field(default_factory=dict)
    eftp_indoor: Optional[float] = None    # indoor best-20 * 0.95 (ungated)
    eftp_outdoor: Optional[float] = None   # outdoor best-20 * 0.95 (ungated)
    peak_5s: Optional[float] = None        # best maxAvgPower_5 (neuromuscular)
    insights: List[Insight] = field(default_factory=list)
```

- [ ] **Step 4: Compute them in `analyze()`**

In `analyze()`, after `curve_all = self._best_curve(all_rides)` (line ~181), insert:

```python
        usable = [r for r in all_rides if not r.exclude]
        indoor = [r for r in usable if r.is_indoor]
        outdoor = [r for r in usable if not r.is_indoor]
        curve_indoor = self._best_curve(indoor)
        curve_outdoor = self._best_curve(outdoor)
        eftp_indoor = (round(curve_indoor[1200] * 0.95)
                       if curve_indoor.get(1200) else None)
        eftp_outdoor = (round(curve_outdoor[1200] * 0.95)
                        if curve_outdoor.get(1200) else None)
        peak_5s = max((r.peak_power[5] for r in usable if 5 in r.peak_power),
                      default=None)
```

Then pass them into the `PowerAnalysisResult(...)` constructor (add these kwargs alongside the existing ones):

```python
            skipped_files=skipped_files,
            curve_indoor=curve_indoor,
            curve_outdoor=curve_outdoor,
            eftp_indoor=eftp_indoor,
            eftp_outdoor=eftp_outdoor,
            peak_5s=peak_5s,
        )
```

> Note: `_best_curve` currently includes excluded rides via the legacy `all_rides`/`recent` paths. That is fine — the legacy `power_curve_alltime`/`estimated_ftp` keep their exact old values (back-compat), while the new `curve_indoor`/`curve_outdoor` use the `usable` (exclude-filtered) set.

- [ ] **Step 5: Run to verify pass + full power regression**

Run: `.venv/bin/python -m pytest test/test_power_analyzer_phase1.py test/test_power_analyzer.py test/test_power_analyzer_analyze.py -v`
Expected: PASS.

- [ ] **Step 6: flake8 + commit**

```bash
.venv/bin/python -m flake8 garmindb/analysis/power_analyzer.py --max-line-length=180 --ignore=E203,E221,E241,W503
git add test/test_power_analyzer_phase1.py garmindb/analysis/power_analyzer.py
git commit -m "feat(power): separate indoor/outdoor curves + per-env eFTP + 5s peak"
```

---

## Task 3: Moderate eFTP publication gate + headline eFTP

The gate decides whether to publish a "measured eFTP". Moderate rule: ≥3 rides with `maxAvgPower_1200` in the last 42 days, IF ≥ 0.90 (NP / configured FTP) on at least one, artifact-clean. Headline = outdoor if its gate passes, else indoor (labelled).

**Files:**
- Modify: `garmindb/analysis/power_analyzer.py`
- Test: `test/test_power_analyzer_phase1.py`

- [ ] **Step 1: Write the failing tests**

Append to `test/test_power_analyzer_phase1.py`:

```python
# --------------------------------------------------------------------------- #
# Task 3 — publication gate + headline eFTP
# --------------------------------------------------------------------------- #

def _hard_outdoor(folder, aid, day, best20):
    # NP just above 0.90 * 325 = 292.5 -> IF >= 0.90 (a genuinely hard ride).
    _write(folder, aid, day, indoor=False, maxAvgPower_1200=best20,
           normPower=295.0, duration=3600.0)


def test_gate_publishes_outdoor_when_moderate_rule_met(tmp_path):
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    _hard_outdoor(folder, 1, "2026-05-20", 300)
    _hard_outdoor(folder, 2, "2026-05-27", 305)
    _hard_outdoor(folder, 3, "2026-06-02", 298)
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    assert r.gate.published is True
    assert r.gate.source_env == "outdoor"
    assert r.gate.candidate_count == 3
    assert r.eftp_measured == round(305 * 0.95)     # best candidate * 0.95
    assert r.eftp_source == "outdoor"
    assert r.eftp_date == date(2026, 5, 27)


def test_gate_fails_with_too_few_candidates(tmp_path):
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    _hard_outdoor(folder, 1, "2026-05-20", 300)
    _hard_outdoor(folder, 2, "2026-05-27", 305)      # only 2 < 3
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    assert r.gate.published is False
    assert r.eftp_measured is None
    assert "configurado" in r.gate.reason.lower()


def test_gate_fails_on_stale_efforts(tmp_path):
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    for i, day in enumerate(("2026-01-10", "2026-01-12", "2026-01-15"), 1):
        _hard_outdoor(folder, i, day, 300)           # all > 42 days old
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    assert r.gate.published is False
    assert r.gate.recency_ok is False


def test_gate_falls_back_to_indoor_label(tmp_path):
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    # 3 hard INDOOR rides, no qualifying outdoor -> indoor headline, labelled.
    for i, day in enumerate(("2026-05-20", "2026-05-27", "2026-06-02"), 1):
        _write(folder, i, day, indoor=True, maxAvgPower_1200=300,
               normPower=295.0, duration=3600.0)
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    assert r.gate.published is True
    assert r.gate.source_env == "indoor"
    assert r.eftp_source == "indoor"
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest test/test_power_analyzer_phase1.py -k gate -v`
Expected: FAIL — `AttributeError: ... 'gate'`.

- [ ] **Step 3: Add the gate constants and `PowerGate` dataclass**

In `power_analyzer.py`, after `CURVE_DURATIONS` (line ~22) add:

```python
# Moderate publication-gate thresholds (user decision 2026-06-09).
GATE_RECENCY_DAYS = 42        # 6 weeks
GATE_MIN_CANDIDATES = 3       # >=3 rides carrying maxAvgPower_1200 in window
GATE_MIN_IF = 0.90           # IF = normPower / configured FTP
EFTP_MULTIPLIER = 0.95       # best 20-min * 0.95
```

Add the `PowerGate` dataclass (after `PowerRide`, before `PowerAnalysisResult`):

```python
@dataclass
class PowerGate:
    """Verdict of the eFTP publication gate (data-honesty for a clinician)."""

    published: bool
    source_env: Optional[str]            # "outdoor" | "indoor" | None
    candidate_count: int                 # qualifying rides in the recency window
    recency_ok: bool
    if_ok: bool
    newest_effort_date: Optional[date]
    reason: str                          # human-readable verdict (pt-BR)
```

- [ ] **Step 4: Add the gate fields to `PowerAnalysisResult`**

Append (after `peak_5s`, before `insights`):

```python
    peak_5s: Optional[float] = None        # best maxAvgPower_5 (neuromuscular)
    gate: Optional["PowerGate"] = None
    eftp_measured: Optional[float] = None  # gated headline eFTP
    eftp_source: Optional[str] = None      # "outdoor" | "indoor" | None
    eftp_date: Optional[date] = None       # date of the qualifying 20-min effort
    insights: List[Insight] = field(default_factory=list)
```

- [ ] **Step 5: Implement the gate method**

Add to `PowerAnalyzer` (after `_zone_distribution`):

```python
    def _gate_env(
        self, rides_env: List["PowerRide"], end_date: date, env: str,
    ) -> Tuple["PowerGate", Optional[float], Optional[date]]:
        """Evaluate the moderate publication gate for one environment.

        Returns the verdict plus (eftp, eftp_date) when it publishes.
        """
        window_start = end_date - timedelta(days=GATE_RECENCY_DAYS)
        candidates = [
            r for r in rides_env
            if not r.exclude and 1200 in r.peak_power
            and window_start <= r.date <= end_date
        ]
        count = len(candidates)
        newest = max((r.date for r in candidates), default=None)
        recency_ok = newest is not None
        # IF = NP / configured FTP on at least one candidate (a genuinely hard
        # near-threshold block). Needs a configured FTP to anchor IF.
        if_ok = bool(self._ftp) and any(
            r.norm_power and (r.norm_power / self._ftp) >= GATE_MIN_IF
            for r in candidates
        )
        published = count >= GATE_MIN_CANDIDATES and recency_ok and if_ok
        eftp = eftp_date = None
        if published:
            best = max(candidates, key=lambda r: r.peak_power[1200])
            eftp = round(best.peak_power[1200] * EFTP_MULTIPLIER)
            eftp_date = best.date
            reason = (f"eFTP medido {env}: melhor 20-min x {EFTP_MULTIPLIER:g}, "
                      f"{count} pedais na janela de {GATE_RECENCY_DAYS} dias")
        else:
            bits = []
            if count < GATE_MIN_CANDIDATES:
                bits.append(f"{count}<{GATE_MIN_CANDIDATES} pedais com 20-min")
            if not recency_ok:
                bits.append(f"sem esforco nos ultimos {GATE_RECENCY_DAYS} dias")
            if not if_ok:
                bits.append("sem esforco duro (IF<0,90)")
            reason = ("FTP configurado (nao testado nestes dados: "
                      + "; ".join(bits) + ")")
        gate = PowerGate(
            published=published, source_env=(env if published else None),
            candidate_count=count, recency_ok=recency_ok, if_ok=if_ok,
            newest_effort_date=newest, reason=reason,
        )
        return gate, eftp, eftp_date
```

- [ ] **Step 6: Wire the gate into `analyze()` (outdoor-first headline)**

In `analyze()`, after the `peak_5s = ...` block from Task 2, add:

```python
        out_gate, out_eftp, out_date = self._gate_env(outdoor, end_date, "outdoor")
        in_gate, in_eftp, in_date = self._gate_env(indoor, end_date, "indoor")
        if out_gate.published:
            gate, eftp_measured, eftp_source, eftp_date = \
                out_gate, out_eftp, "outdoor", out_date
        elif in_gate.published:
            gate, eftp_measured, eftp_source, eftp_date = \
                in_gate, in_eftp, "indoor", in_date
        else:
            # Neither published: surface the outdoor verdict if outdoor rides
            # exist, else the indoor verdict (so the reason is the relevant one).
            gate = out_gate if outdoor else in_gate
            eftp_measured = eftp_source = eftp_date = None
```

Pass the four new values into the `PowerAnalysisResult(...)` call:

```python
            peak_5s=peak_5s,
            gate=gate,
            eftp_measured=eftp_measured,
            eftp_source=eftp_source,
            eftp_date=eftp_date,
        )
```

- [ ] **Step 7: Run to verify pass + full regression**

Run: `.venv/bin/python -m pytest test/test_power_analyzer_phase1.py test/test_power_analyzer.py test/test_power_analyzer_analyze.py -v`
Expected: PASS (gate tests + existing power tests; the existing analyze tests have only 1–2 rides so `gate.published` is False there, which does not touch their assertions).

- [ ] **Step 8: flake8 + commit**

```bash
.venv/bin/python -m flake8 garmindb/analysis/power_analyzer.py --max-line-length=180 --ignore=E203,E221,E241,W503
git add test/test_power_analyzer_phase1.py garmindb/analysis/power_analyzer.py
git commit -m "feat(power): moderate eFTP publication gate + headline selection"
```

---

## Task 4: NP variability (≥30 min) + gate-aware insight

Expose stored `normPower` as a *variability* indicator over long recent rides only, and add a gate-aware Portuguese insight (publish vs configured-fallback). Legacy `ftp_needs_test` insight stays.

**Files:**
- Modify: `garmindb/analysis/power_analyzer.py`
- Test: `test/test_power_analyzer_phase1.py`

- [ ] **Step 1: Write the failing test**

Append to `test/test_power_analyzer_phase1.py`:

```python
# --------------------------------------------------------------------------- #
# Task 4 — NP variability (>=30min) + gate-aware insight
# --------------------------------------------------------------------------- #

def test_np_variability_uses_only_long_rides(tmp_path):
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    # Long ride: counts. avg 200, NP 220 -> ratio 1.10.
    _write(folder, 1, "2026-05-20", indoor=False, maxAvgPower_1200=290,
           avgPower=200.0, normPower=220.0, duration=3600.0)
    # Short ride: NP must be ignored (duration < 1800s).
    _write(folder, 2, "2026-05-21", indoor=False, maxAvgPower_1200=280,
           avgPower=150.0, normPower=300.0, duration=600.0)
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    assert r.np_long_ride_count == 1
    assert abs(r.np_variability_ratio - 1.10) < 0.01


def test_gate_insight_present_when_published(tmp_path):
    folder = str(tmp_path)
    end = date(2026, 6, 7)
    for i, day in enumerate(("2026-05-20", "2026-05-27", "2026-06-02"), 1):
        _write(folder, i, day, indoor=False, maxAvgPower_1200=305,
               normPower=295.0, duration=3600.0)
    r = PowerAnalyzer(folder, configured_ftp=325).analyze(date(2026, 1, 1), end)
    assert any("Potência de campo" in i.title for i in r.insights)
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest test/test_power_analyzer_phase1.py -k "np_variability or gate_insight" -v`
Expected: FAIL — `AttributeError: ... 'np_long_ride_count'`.

- [ ] **Step 3: Add the NP fields**

Append to `PowerAnalysisResult` (after `eftp_date`, before `insights`):

```python
    eftp_date: Optional[date] = None       # date of the qualifying 20-min effort
    np_variability_ratio: Optional[float] = None  # mean(NP/avg) over long rides
    np_long_ride_count: int = 0            # rides with duration >= 1800s
    insights: List[Insight] = field(default_factory=list)
```

- [ ] **Step 4: Compute NP variability in `analyze()`**

In `analyze()`, after the gate block, add (use the recent window for "current" variability):

```python
        long_recent = [
            r for r in recent
            if not r.exclude and r.duration_s and r.duration_s >= 1800
            and r.norm_power and r.avg_power and r.avg_power > 0
        ]
        np_ratios = [r.norm_power / r.avg_power for r in long_recent]
        np_variability_ratio = (round(sum(np_ratios) / len(np_ratios), 2)
                                if np_ratios else None)
        np_long_ride_count = len(long_recent)
```

Pass into the constructor:

```python
            eftp_date=eftp_date,
            np_variability_ratio=np_variability_ratio,
            np_long_ride_count=np_long_ride_count,
        )
```

- [ ] **Step 5: Add the gate-aware insight**

In `_build_insights`, after the existing `ftp_needs_test` block (before `return insights`), add:

```python
        gate = result.gate
        if gate is not None and gate.published and result.eftp_measured:
            src = "outdoor" if result.eftp_source == "outdoor" else \
                "indoor (~8-12% abaixo do outdoor)"
            insights.append(Insight(
                # Title avoids the bare "FTP" fragment so it never collides with
                # the legacy `not any("FTP" in i.title)` assertions.
                title="Potência de campo estimada disponível",
                description=(
                    f"eFTP estimado {result.eftp_measured:.0f} W "
                    f"(fonte {src}; melhor 20-min x 0,95, "
                    f"{gate.candidate_count} pedais na janela de 6 semanas). "
                    "Estimativa de campo, não teste de laboratório."
                ),
                severity=InsightSeverity.INFO,
                category="power",
                data_points={"eftp_measured": result.eftp_measured,
                             "source": result.eftp_source},
                recommendations=["Comparar com a FTP configurada; "
                                 "revalidar com teste se divergirem"],
            ))
        return insights
```

- [ ] **Step 6: Run to verify pass + full power regression**

Run: `.venv/bin/python -m pytest test/test_power_analyzer_phase1.py test/test_power_analyzer.py test/test_power_analyzer_analyze.py -v`
Expected: PASS.

- [ ] **Step 7: flake8 + commit**

```bash
.venv/bin/python -m flake8 garmindb/analysis/power_analyzer.py --max-line-length=180 --ignore=E203,E221,E241,W503
git add test/test_power_analyzer_phase1.py garmindb/analysis/power_analyzer.py
git commit -m "feat(power): NP variability (>=30min) + gate-aware eFTP insight"
```

---

## Task 5: `--performance` report — surface measured power + paired-weight W/kg

Un-drop the computed fields: show configured FTP **and** measured eFTP with the gap, the indoor/outdoor curves, zone distribution, the 5 s peak, and a measured W/kg using a weight paired (±7 d) to the eFTP date.

**Files:**
- Modify: `garmindb/analysis/performance_report.py`
- Modify: `garmindb/presentation/markdown/performance_renderer.py`
- Test: `test/test_performance_power_phase1.py` (create)

- [ ] **Step 1: Write the failing test**

Create `test/test_performance_power_phase1.py`:

```python
# test/test_performance_power_phase1.py
"""Phase 1: measured power flows into the --performance report + renderer."""

from datetime import date, datetime

from garmindb.analysis.power_analyzer import PowerAnalysisResult, PowerGate
from garmindb.analysis.performance_report import PerformanceReport
from garmindb.presentation.markdown.performance_renderer import (
    PerformancePresenter,
)


def _power_with_eftp():
    gate = PowerGate(published=True, source_env="outdoor", candidate_count=3,
                     recency_ok=True, if_ok=True,
                     newest_effort_date=date(2026, 5, 27),
                     reason="eFTP medido outdoor")
    return PowerAnalysisResult(
        period_start=date(2026, 1, 1), period_end=date(2026, 6, 7),
        configured_ftp=325, estimated_ftp=289, best_20min_recent=305,
        best_20min_alltime=305, power_curve_recent={1200: 305},
        power_curve_alltime={5: 820, 1200: 305}, power_zone_distribution={2: 60.0, 4: 40.0},
        rides_with_power=3, total_rides=3, ftp_needs_test=False,
        curve_outdoor={5: 820, 1200: 305}, curve_indoor={1200: 260},
        eftp_outdoor=290, eftp_indoor=247, peak_5s=820,
        gate=gate, eftp_measured=290, eftp_source="outdoor",
        eftp_date=date(2026, 5, 27),
    )


def test_renderer_shows_both_ftps_gap_wkg_and_zones():
    md = PerformancePresenter.render_power_block(_power_with_eftp(), wkg_measured=3.72)
    assert "FTP configurado" in md and "325" in md
    assert "eFTP medido" in md and "290" in md
    assert "3,72" in md                      # measured W/kg (paired weight)
    assert "820" in md                       # 5s neuromuscular peak
    assert "outdoor" in md
    assert "Zonas de potência" in md         # zone distribution surfaced (was dropped)


def test_weight_near_medians_within_window():
    from garmindb.analysis.performance_report import _weight_near

    class _Repo:
        def get_weight_series(self, start, end):
            return [(date(2026, 5, 20), 79.0), (date(2026, 5, 27), 77.0)]

    assert _weight_near(_Repo(), date(2026, 5, 24)) == 78.0    # median(77, 79)
    assert _weight_near(_Repo(), None) is None
    assert _weight_near(object(), date(2026, 5, 24)) is None    # no get_weight_series
```

> The first test targets the static `render_power_block` so the section is unit-testable without a full `PerformanceReport`. The second covers the `_weight_near` helper directly (including the defensive no-method path), so the `build()` weight-pairing wiring is exercised. Step 4 adds the renderer method; Step 5 calls it from `render()`.

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest test/test_performance_power_phase1.py -v`
Expected: FAIL — `AttributeError: ... 'render_power_block'`.

- [ ] **Step 3: Add a paired-weight helper to the performance builder**

In `performance_report.py`, add a module-level helper (after `_run_stress`):

```python
def _weight_near(repository, target: date, window_days: int = 7):
    """Median bodyweight within +/-window_days of target (None if none).

    Defensive: a repository (or test double) lacking get_weight_series yields
    None rather than crashing build().
    """
    if target is None:
        return None
    getter = getattr(repository, "get_weight_series", None)
    if getter is None:
        return None
    from datetime import timedelta
    series = getter(
        target - timedelta(days=window_days), target + timedelta(days=window_days))
    vals = sorted(w for _, w in series) if series else []
    if not vals:
        return None
    mid = len(vals) // 2
    return vals[mid] if len(vals) % 2 else (vals[mid - 1] + vals[mid]) / 2
```

In `build()`, after `ftp_used = ...`, compute the measured W/kg with the paired weight:

```python
        ftp_used = t.ftp_watts or power.estimated_ftp
        wkg = (ftp_used / weight) if (ftp_used and weight) else None
        eftp_weight = _weight_near(self._repo, power.eftp_date) or weight
        wkg_measured = ((power.eftp_measured / eftp_weight)
                        if (power.eftp_measured and eftp_weight) else None)
```

Add two fields at the **END** of `PerformanceReport`, after `metric_snapshot` (the only currently-defaulted field). Placing them after the non-defaulted `vo2max`/`deltas` would raise `TypeError: non-default argument 'vo2max' follows default argument` at import time, crashing the whole performance + anamnesis suite. Find:

```python
    deltas: Dict[str, MetricDelta]
    metric_snapshot: Dict[str, float] = field(default_factory=dict)
```
and change to:
```python
    deltas: Dict[str, MetricDelta]
    metric_snapshot: Dict[str, float] = field(default_factory=dict)
    eftp_measured: Optional[float] = None
    wkg_measured: Optional[float] = None
```

And pass them in the `PerformanceReport(...)` return (after `ftp_used=ftp_used,`):

```python
            vo2max=vo2max, deltas=deltas, metric_snapshot=snapshot,
            eftp_measured=power.eftp_measured, wkg_measured=wkg_measured,
        )
```

- [ ] **Step 4: Add `render_power_block` to the renderer**

In `performance_renderer.py`, add a static method to `PerformancePresenter`:

```python
    @staticmethod
    def render_power_block(power, wkg_measured=None) -> str:
        """Measured-vs-configured power section. Renders nothing if no power."""
        if power is None or power.total_rides == 0:
            return ""

        def w(v, nd=0):
            return f"{v:.{nd}f}".replace(".", ",") if v is not None else _NO_VALUE

        lines = ["\n## Potência (medida vs configurada)\n"]
        lines.append(f"- **FTP configurado:** {w(power.configured_ftp)} W (meta)")
        if power.gate and power.gate.published and power.eftp_measured:
            src = ("outdoor" if power.eftp_source == "outdoor"
                   else "indoor (~8–12% abaixo do outdoor)")
            gap = (power.eftp_measured - power.configured_ftp
                   if power.configured_ftp else None)
            lines.append(
                f"- **eFTP medido:** {w(power.eftp_measured)} W — fonte {src}; "
                f"melhor 20-min × 0,95 ({power.gate.candidate_count} pedais, "
                "janela 6 sem). Estimativa de campo, não teste de laboratório."
                + (f" Gap vs configurado: {w(gap)} W." if gap is not None else ""))
            if wkg_measured is not None:
                lines.append(f"- **W·kg medido:** {w(wkg_measured, 2)} "
                             "(eFTP ÷ peso pareado ±7 d do esforço)")
        else:
            reason = power.gate.reason if power.gate else "sem esforço qualificado"
            lines.append(f"- **eFTP medido:** não publicado — {reason}.")
        if power.peak_5s:
            lines.append(f"- **Pico neuromuscular (5 s):** {w(power.peak_5s)} W "
                         "(maxAvgPower_5; nunca o pico de 1 s, que é ruído).")
        if power.np_variability_ratio:
            lines.append(
                f"- **Variabilidade (NP/méd, ≥30 min):** "
                f"{w(power.np_variability_ratio, 2)} sobre "
                f"{power.np_long_ride_count} pedais (1,0 = constante).")
        # Curves (indoor/outdoor) at the key durations.
        labels = [(5, "5 s"), (60, "1 min"), (300, "5 min"),
                  (1200, "20 min"), (3600, "60 min")]
        lines.append("\n| Duração | Outdoor (W) | Indoor (W) |")
        lines.append("|---|---|---|")
        for d, lab in labels:
            lines.append(f"| {lab} | {w(power.curve_outdoor.get(d))} | "
                         f"{w(power.curve_indoor.get(d))} |")
        # Zone distribution (already computed by the analyzer; previously dropped).
        if power.power_zone_distribution:
            znames = {1: "Z1", 2: "Z2", 3: "Z3", 4: "Z4", 5: "Z5", 6: "Z6", 7: "Z7"}
            zbits = [f"{znames.get(z, z)} {p:.0f}%"
                     for z, p in sorted(power.power_zone_distribution.items())]
            lines.append("\n**Zonas de potência (% do tempo):** " + " · ".join(zbits))
        return "\n".join(lines) + "\n"
```

- [ ] **Step 5: Call the power block from `render()`**

In `performance_renderer.py` `render()`, insert the power block after the scorecard:

```python
        parts.append(self._scorecard(report))
        parts.append(self.render_power_block(report.power, report.wkg_measured))
        parts.append(self._coverage(report))
```

- [ ] **Step 6: Run the test + the existing performance suite**

Run: `.venv/bin/python -m pytest test/test_performance_power_phase1.py test/test_performance_report.py test/test_performance_renderer.py test/test_performance_cli_smoke.py -v`
Expected: PASS. (The new `PerformanceReport` fields have defaults, so existing construction sites are unaffected; the renderer addition is additive.)

- [ ] **Step 7: flake8 + commit**

```bash
.venv/bin/python -m flake8 garmindb/analysis/performance_report.py garmindb/presentation/markdown/performance_renderer.py --max-line-length=180 --ignore=E203,E221,E241,W503
git add test/test_performance_power_phase1.py garmindb/analysis/performance_report.py garmindb/presentation/markdown/performance_renderer.py
git commit -m "feat(performance): surface measured eFTP + curves + paired W/kg"
```

---

## Task 6: `--anamnesis` report — wire real power in, remove the falsehoods

Wire `PowerAnalyzer` into the SQLite-only longitudinal builder, add a measured-power block to Section 3, and correct the three hardcoded "no power data" claims + the module docstring. Gate-aware: shows measured power when the gate passes, an honest "configured, untested" line otherwise — never the old blanket falsehood.

**Files:**
- Modify: `scripts/generate_report.py` (pass `activities_dir`)
- Modify: `garmindb/analysis/longitudinal_report.py` (builder reads PowerAnalyzer; module docstring)
- Modify: `garmindb/presentation/markdown/longitudinal_renderer.py` (`_power_caveat`, `_provenance`, `_frontmatter`)
- Test: `test/test_longitudinal_power_phase1.py` (create)

- [ ] **Step 1: Write the failing tests**

Create `test/test_longitudinal_power_phase1.py`:

```python
# test/test_longitudinal_power_phase1.py
"""Phase 1: real power replaces the 'no power data' falsehood in --anamnesis."""

import json
import os
import sqlite3
from datetime import date, datetime

from garmindb.analysis.longitudinal_report import LongitudinalReportBuilder
from garmindb.analysis.performance_targets import PerformanceTargets
from garmindb.presentation.markdown.longitudinal_renderer import (
    LongitudinalPresenter,
)

GEN = datetime(2026, 6, 8, 12, 0, 0)


def _min_garmin_db(db_dir):
    con = sqlite3.connect(os.path.join(db_dir, "garmin.db"))
    con.execute("CREATE TABLE attributes (timestamp TEXT, key TEXT, value TEXT)")
    con.execute("CREATE TABLE weight (day TEXT, weight FLOAT)")
    con.execute("INSERT INTO weight VALUES (?,?)", ("2026-05-25 00:00:00", 78.0))
    con.commit()
    con.close()


def _hard_ride(folder, aid, day, best20):
    payload = {"activityType": {"typeKey": "road_biking"}, "manufacturer": "GARMIN",
               "startTimeLocal": f"{day} 10:00:00", "maxAvgPower_1200": best20,
               "normPower": 295.0, "duration": 3600.0,
               "powerTimeInZone_2": 1800.0, "powerTimeInZone_4": 600.0}
    with open(os.path.join(folder, f"activity_{aid}.json"), "w") as f:
        json.dump(payload, f)


def _builder(db_dir, acts_dir, start, end, targets):
    return LongitudinalReportBuilder(
        db_dir=str(db_dir), targets=targets, start_date=start, end_date=end,
        generated_at=GEN, activities_dir=str(acts_dir))


def test_anamnesis_publishes_measured_eftp(tmp_path):
    db = tmp_path / "db"; db.mkdir()
    acts = tmp_path / "acts"; acts.mkdir()
    _min_garmin_db(str(db))
    for i, d in enumerate(("2026-05-20", "2026-05-27", "2026-06-02"), 1):
        _hard_ride(str(acts), i, d, 305)
    targets = PerformanceTargets(ftp_watts=325, wkg_target=4.0)
    report = _builder(db, acts, date(2026, 1, 1), date(2026, 6, 7), targets).build()
    md = LongitudinalPresenter().render(report)
    assert "Não há dados de potência" not in md       # falsehood removed
    assert "eFTP medido" in md
    assert "290" in md                                  # 305 * 0.95


def test_anamnesis_no_power_files_is_honest_not_false(tmp_path):
    db = tmp_path / "db"; db.mkdir()
    acts = tmp_path / "acts"; acts.mkdir()              # empty
    _min_garmin_db(str(db))
    targets = PerformanceTargets(ftp_watts=325)
    report = _builder(db, acts, date(2026, 1, 1), date(2026, 6, 7), targets).build()
    md = LongitudinalPresenter().render(report)
    # No rides -> honest "configured, untested", NOT the blanket "no power data".
    assert "configurad" in md.lower()
```

- [ ] **Step 2: Run to verify failure**

Run: `.venv/bin/python -m pytest test/test_longitudinal_power_phase1.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'activities_dir'`.

- [ ] **Step 3: Give the longitudinal builder an `activities_dir` and a power result**

In `longitudinal_report.py`, fix the module docstring lines 9–11: change the bullet asserting "There is NO power-meter data in these DBs. FTP / W-kg are CONFIGURED goals…" to:

```python
- Power lives in the per-activity summary JSONs (not the DBs); a moderate
  publication gate decides whether to show a MEASURED eFTP or fall back to the
  configured FTP labelled as such (see :class:`PowerAnalyzer`).
```

Extend `LongitudinalReportBuilder.__init__` to accept `activities_dir`:

```python
    def __init__(
        self,
        db_dir: str,
        targets: PerformanceTargets,
        start_date: date,
        end_date: date,
        generated_at: datetime,
        activities_dir: Optional[str] = None,
    ):
        self._db_dir = db_dir
        self._targets = targets
        self._start = start_date
        self._end = end_date
        self._generated = generated_at
        self._acts_dir = activities_dir
```

Add a power method (after `_vo2max_series` or near the other readers):

```python
    def _power(self):
        """Run PowerAnalyzer over the summary JSONs (None if no dir/data)."""
        if not self._acts_dir:
            return None
        from .power_analyzer import PowerAnalyzer
        try:
            return PowerAnalyzer(
                self._acts_dir, self._targets.ftp_watts,
            ).analyze(self._start, self._end)
        except Exception as e:  # never let power break the clinical report
            logger.warning("Longitudinal power analysis failed: %s", e)
            return None
```

Add a `power` field to the `LongitudinalReport` dataclass (append after `confidence_score`/the Phase-0 fields — it is Optional with a default so construction stays safe):

```python
    operational_max_hr: Dict[str, Optional[int]]
    power: object = None        # PowerAnalysisResult | None (avoid import cycle)
```

In `build()`, compute it and pass it:

```python
        power = self._power()
```
```python
            operational_max_hr=operational_max_hr,
            power=power,
        )
```

- [ ] **Step 4: Replace the renderer's power caveat with a gate-aware block**

In `longitudinal_renderer.py`, replace the whole `_power_caveat` method body with a gate-aware version (keeps the configured-goal fallback, shows measured power when published, and NEVER prints the blanket falsehood):

```python
    def _power_caveat(self, r: LongitudinalReport) -> str:
        t = r.targets
        power = getattr(r, "power", None)
        wkg_cfg = (t.ftp_watts / r.current_weight
                   if t.ftp_watts and r.current_weight else None)
        body = ["\n### Potência (FTP / W·kg)\n"]
        published = bool(power and getattr(power, "gate", None)
                         and power.gate.published and power.eftp_measured)
        if published:
            src = ("outdoor" if power.eftp_source == "outdoor"
                   else "indoor (~8–12% abaixo do outdoor)")
            body.append(
                f"- **eFTP medido:** {power.eftp_measured:.0f} W (fonte {src}; "
                f"melhor 20-min × 0,95, {power.gate.candidate_count} pedais na "
                "janela de 6 semanas). Estimativa de campo, não teste de "
                "laboratório.")
            if r.current_weight:
                body.append(
                    f"- W·kg medido ≈ {power.eftp_measured / r.current_weight:.2f} "
                    f"(eFTP ÷ peso atual {r.current_weight:.1f} kg, mediana recente — "
                    "o eFTP está dentro da janela de 6 semanas, então o peso é "
                    "contemporâneo)")
        else:
            reason = (power.gate.reason if power and getattr(power, "gate", None)
                      else "sem arquivos de potência no período")
            body.append(
                "> ⚠️ Sem eFTP **medido** publicável neste período "
                f"({reason}). O número abaixo é **meta configurada**, não medição.")
        if t.ftp_watts:
            body.append(f"- FTP configurado: **{_num(t.ftp_watts, 0)} W** "
                        "(autorrelato / teste externo)")
        if wkg_cfg:
            body.append(f"- W·kg configurado = {_num(t.ftp_watts, 0)} ÷ "
                        f"{_num(r.current_weight, 1)} kg = **{_num(wkg_cfg, 2)} W/kg** "
                        f"(meta {_num(t.wkg_target, 1)})")
        if power and getattr(power, "total_rides", 0):
            body.append(f"\n_Cobertura de potência: {power.total_rides} pedais "
                        "com dados nos arquivos de resumo._")
        return "\n".join(body)
```

- [ ] **Step 5: Fix the remaining "no power" strings + the renderer docstring**

In `longitudinal_renderer.py` `_provenance`, replace the `- **Sem dados de potência.**…` bullet with:

```python
            "- **Potência** vem dos arquivos de resumo do Garmin (não das tabelas "
            "do DB); um eFTP só é publicado quando há esforço recente suficiente "
            "(gate de 6 semanas / IF≥0,90 / ≥3 pedais), senão mostra-se a FTP "
            "configurada rotulada como meta.\n"
```

In `_frontmatter`, change the `data_caveat` line — replace `… sem dados de potência` with `… potência só quando há esforço qualificado (senão meta configurada)`.

Fix the **renderer** module docstring too — the research only named the *builder* docstring, so this one was missed. At `longitudinal_renderer.py:8`, change the clause `estimates (screening, not diagnostic) and that no power data exists.` to:

```
estimates (screening, not diagnostic). Power, when a recent qualifying effort
exists, is shown as a gated eFTP (else the configured FTP, labelled as a goal).
```

Reword the accurate-but-bare load caveat in `_load()` so a grep for the *false* "sem potência" claim is clean. Find `"(proxy de TSS; sem potência)"` and change to `"(proxy de TSS; carga não ponderada por potência)"` (the CTL/ATL load proxy genuinely has no power weighting even after Phase 1 — this keeps the caveat true without the bare phrase that reads as a blanket "no power data" claim).

- [ ] **Step 6: Pass `activities_dir` from the CLI**

In `scripts/generate_report.py`, in the `--anamnesis` branch, derive and pass the activities dir (mirror the `--performance` branch which already computes `<db_path>/../FitFiles/Activities`). After `db_dir = db_params.db_path` add:

```python
        import os as _os
        acts_dir = _os.path.join(_os.path.dirname(db_dir), "FitFiles", "Activities")
```

and add `activities_dir=acts_dir` to the `LongitudinalReportBuilder(...)` call.

- [ ] **Step 7: Update the two Phase-0 assertions that pin the removed falsehood**

Exactly two Phase-0 assertions hardcode the literal string Phase 1 removes. These are the ONLY Phase-0 assertions that change, and the change is intended (the string was a falsehood). Both Phase-0 builders construct the longitudinal builder **without** `activities_dir`, so `_power()` returns `None` and `_power_caveat` renders the configured-goal fallback (which contains "configurada"/"configurado", never the old falsehood).

In `test/test_longitudinal_report.py` (in `test_renderer_smoke_and_power_caveat`), find:
```python
    assert "Não há dados de potência" in md
```
Replace with:
```python
    assert "Não há dados de potência" not in md   # Phase 1 removed the falsehood
    assert "configurad" in md.lower()              # honest configured-goal fallback
```

In `test/test_longitudinal_clinical.py` (in `test_phase0_full_render_smoke`), find:
```python
    assert "Não há dados de potência" in md
```
Replace with:
```python
    assert "Não há dados de potência" not in md   # Phase 1 removed the falsehood
    assert "configurad" in md.lower()              # honest configured-goal fallback
```

- [ ] **Step 8: Run the new tests + the full Phase-0 + power suites**

Run: `.venv/bin/python -m pytest test/test_longitudinal_power_phase1.py test/test_longitudinal_report.py test/test_longitudinal_clinical.py test/test_power_analyzer_phase1.py -v`
Expected: PASS (the two edited Phase-0 assertions now pass against the honest fallback; everything else green).

- [ ] **Step 9: flake8 + commit**

```bash
.venv/bin/python -m flake8 garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py --max-line-length=180 --ignore=E203,E221,E241,W503
git add test/test_longitudinal_power_phase1.py garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/longitudinal_renderer.py scripts/generate_report.py test/test_longitudinal_report.py test/test_longitudinal_clinical.py
git commit -m "feat(anamnesis): wire real power in + remove the 'no power data' falsehood"
```

---

## Task 7: DoD — end-to-end on real data + roadmap changelog

**Files:**
- Modify: `test/test_longitudinal_power_phase1.py` (one e2e assertion)
- Modify: `docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md`

- [ ] **Step 1: Add an end-to-end smoke test (both reports consistent)**

Append to `test/test_longitudinal_power_phase1.py`:

```python
def test_both_reports_agree_on_power_presence(tmp_path):
    # With 3 hard rides, the anamnesis must NOT claim "no power data".
    db = tmp_path / "db"; db.mkdir()
    acts = tmp_path / "acts"; acts.mkdir()
    _min_garmin_db(str(db))
    for i, d in enumerate(("2026-05-20", "2026-05-27", "2026-06-02"), 1):
        _hard_ride(str(acts), i, d, 305)
    from garmindb.analysis.power_analyzer import PowerAnalyzer
    power = PowerAnalyzer(str(acts), 325).analyze(date(2026, 1, 1), date(2026, 6, 7))
    assert power.gate.published is True            # performance side sees it
    report = _builder(db, acts, date(2026, 1, 1), date(2026, 6, 7),
                      PerformanceTargets(ftp_watts=325)).build()
    md = LongitudinalPresenter().render(report)
    assert "Não há dados de potência" not in md    # anamnesis side agrees
```

- [ ] **Step 2: Run the full project suite**

Run: `.venv/bin/python -m pytest test/test_power_analyzer_phase1.py test/test_power_analyzer.py test/test_power_analyzer_analyze.py test/test_performance_power_phase1.py test/test_performance_report.py test/test_performance_renderer.py test/test_performance_cli_smoke.py test/test_longitudinal_power_phase1.py test/test_longitudinal_report.py test/test_longitudinal_clinical.py -v`
Expected: ALL pass.

- [ ] **Step 3: (If real DBs + FitFiles present) generate both reports and eyeball**

Only if `~/HealthData/DBs/garmin.db` and `~/HealthData/FitFiles/Activities` exist:

Run: `.venv/bin/python scripts/generate_report.py --performance > /tmp/perf_phase1.md; .venv/bin/python scripts/generate_report.py --anamnesis > /tmp/anam_phase1.md; rg -n "eFTP|FTP configurado|Potência|Outdoor|Indoor|Não há dados de potência" /tmp/perf_phase1.md /tmp/anam_phase1.md`
Expected: both reports show the power block; **neither** contains "Não há dados de potência". Report what the gate decided (published eFTP vs configured fallback) — that is an honest outcome, not a defect. If the gate didn't publish, confirm the reason string is sensible.

- [ ] **Step 4: Update the roadmap changelog**

Append to `## Changelog` in `docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md`:

```markdown
- **2026-06-09 Fase 1 executada:** potência real via arquivos de resumo. `PowerAnalyzer` agora classifica indoor/outdoor, monta curvas separadas, aplica um **gate de publicação moderado** (recência 6 sem, IF≥0,90, ≥3 pedais com 20-min, ×0,95) e expõe pico neuromuscular (5 s) + variabilidade de NP (≥30 min). Saída nos **dois** relatórios: `--performance` (eFTP medido vs configurado + gap, curvas, zonas, W·kg pareado ±7d) e `--anamnesis` (bloco de potência medida; removidas as 3 afirmações falsas "Não há dados de potência"). Decisões: gate moderado, curvas separadas (headline outdoor→indoor rotulado), ambos os relatórios, NP só como variabilidade. Plano: `docs/superpowers/plans/2026-06-09-phase1-power-summary.md`. Próximo: **Fase 2 — profundidade** (decoupling, import de potência no DB, --hrv fix, Training Status/Readiness).
```

- [ ] **Step 5: flake8 final + commit**

```bash
.venv/bin/python -m flake8 garmindb/analysis/power_analyzer.py garmindb/analysis/performance_report.py garmindb/analysis/longitudinal_report.py garmindb/presentation/markdown/performance_renderer.py garmindb/presentation/markdown/longitudinal_renderer.py --max-line-length=180 --ignore=E203,E221,E241,W503
git add test/test_longitudinal_power_phase1.py docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md
git commit -m "test(power): Phase 1 e2e both-reports + roadmap changelog"
```

---

## Definition of Done (Phase 1)

- [ ] `PowerAnalyzer` classifies indoor/outdoor, builds separate curves, applies the moderate gate, exposes 5 s peak + NP variability — all additive (legacy fields/tests intact).
- [ ] `--performance` shows configured FTP **and** measured eFTP with the gap, indoor/outdoor curves, zones, 5 s peak, and a paired-weight (±7 d) measured W/kg.
- [ ] `--anamnesis` shows a measured-power block when the gate passes and an honest "configured, untested" line otherwise; the false blanket "no power data" claims are removed (the 3 named strings + **both** module docstrings — builder and renderer); the `_load()` proxy caveat is reworded so no bare "sem potência" survives, and every remaining power caveat is accurate (e.g. CTL load is genuinely not power-weighted).
- [ ] Gate is data-honest: no measured eFTP published unless ≥3 recent hard rides; indoor headline labelled with the deficit.
- [ ] Every new test green; the existing power, performance, and Phase-0 longitudinal suites stay green; flake8 clean on all five touched modules.
- [ ] No DB migration, no per-second parsing, no new import path; `PowerAnalyzer` remains the single source of truth consumed by both reports.
- [ ] Roadmap changelog records Fase 1 done and points to Fase 2.

---

## Self-Review

**Spec/decision coverage** — every locked decision maps to a task: moderate gate (T3), separate curves + outdoor→indoor headline (T2/T3), both reports (T5 performance, T6 anamnesis), NP variability-only ≥30 min (T4), show-both-FTPs + gap (T5/T6). The three anamnesis falsehoods + docstring are all addressed in T6. The research's data-quality items (`excludeFromPowerCurveReports`, sanity drop, `maxAvgPower_5` not raw `maxPower`) are in T1/T2.

**Backward-compat** — `PowerRide`'s new fields are defaulted + appended (positional tests intact); every new `PowerAnalysisResult`/`PerformanceReport`/`LongitudinalReport` field is defaulted; `estimated_ftp`/`ftp_needs_test`/legacy curves are untouched so `test_power_analyzer_analyze.py` stays green; the longitudinal `activities_dir` defaults to `None` so Phase-0 tests construct unchanged. Each task re-runs the relevant legacy suite.

**Type consistency** — `PowerGate` fields (`published`, `source_env`, `candidate_count`, `recency_ok`, `if_ok`, `newest_effort_date`, `reason`) are used identically in the analyzer, `render_power_block`, and `_power_caveat`. The headline trio (`eftp_measured`, `eftp_source`, `eftp_date`) is set once in `analyze()` and read in both renderers. `_gate_env` returns `(PowerGate, eftp, eftp_date)` consistently for both environments.

**Risk note** — the highest-risk surface is the gate logic (T3) and the anamnesis wiring (T6, new constructor param + 3 string edits). Both are covered by dedicated tests including the negative/fallback paths (too-few-candidates, stale, indoor-fallback, no-files-honest). The `_power()` call is wrapped so a power failure degrades the clinical report to the configured-goal fallback rather than crashing.
