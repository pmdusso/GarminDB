# GarminDB Data-Coverage Audit — what we capture vs. what we use

**Date:** 2026-06-09
**Scope:** Evidence-based sweep of the GarminDB ORM models, the 5 live SQLite DBs in
`~/HealthData/DBs/`, the download/import layer, the upstream project, and the `Fit/`
submodule. Goal: rank everything Garmin captures/models that our health-reporting
pipeline does **not** yet use, for a **longitudinal sports-medicine report for an
endurance cyclist** (profile: male, 1988, 87 kg, 1.91 m, VO2max cycling 55 / running 54;
739 of 1190 activities are cycling).

**Fork status:** local `version_info = (3, 8, 0)` == upstream latest `v3.8.0`. The fork
does **not** lag upstream; all gaps below are GarminDB-wide, not fork-specific.

**Three gap depths used throughout:**
- **(a) CAPTURED-BUT-UNUSED** — already in our DBs and populated; we just don't query it.
- **(b) NOT-IMPORTED** — GarminDB supports it, but our DB is empty/missing it.
- **(c) NOT-SUPPORTED** — Garmin Connect has it; GarminDB cannot download/import it.

---

## 1. Executive summary — TOP 10 highest-value gaps (ranked)

| # | Gap | Status | Effort | Why it matters (one line) |
|---|-----|--------|--------|---------------------------|
| 1 | **Cycling power** (FTP, W·kg, NP, IF, kJ, power curve) | (c) not in any table — raw `.fit` + `activity_details_*.json` only | High | The single biggest hole for a cyclist; today FTP/W·kg are *configured*, not measured. Roadmap Phase 1. |
| 2 | **Intraday SpO2 / pulse-ox** (`monitoring_pulse_ox`, 544,818 rows, 2022-10→2026-06) | (a) captured-but-unused | Low | Altitude-acclimatization signal for a mountain race; nocturnal desaturation = sleep/altitude health. |
| 3 | **Respiration rate** (daily `rr_waking_avg` 55%, sleep `avg_rr` 51%, intraday `monitoring_rr` 1.46M rows) | (a) captured-but-unused | Low | Recovery/overtraining + respiratory-illness marker; trends well longitudinally. |
| 4 | **Anaerobic Training Effect** (`activities.anaerobic_training_effect`, 85.5% populated) | (a) captured-but-unused | Trivial | Aerobic vs. anaerobic load balance — already next to the `training_effect` we use. |
| 5 | **Garmin training analytics** (Training Status, Readiness, Recovery Time, Endurance/Hill Score, Acute Load) | (c) not supported | High | Garmin's own periodization verdicts; closest thing to a coach's readout. Needs new download+import. |
| 6 | **Lactate threshold (HR/pace) + per-discipline VO2max history** | (c)/(a) partial | Med | Threshold drift over months is the core endurance-fitness trend; only a *current* VO2max is stored (attributes). |
| 7 | **HR / power mean-max curves + time-in-zones for ALL rides** (from `activity_records`, 4.73M rows) | (a) streams unused | Med | Per-second `hr`/`speed` exist for every ride; unlocks decoupling, peak curves. Roadmap Phase 0/2. |
| 8 | **Body Battery intraday + `bb_charged` drain/charge** (`daily_summary.bb_charged` 55%) | (a) captured-but-unused | Low | Daily energy economy; charge-rate is a recovery-quality proxy. |
| 9 | **Sleep detail** (`light_sleep`/`awake` 100%, `avg_stress` 51%, `sleep_events` 7,529 rows) | (a) captured-but-unused | Low | Sleep architecture + fragmentation beyond the score/stages we already show. |
| 10 | **Daily `hrv` table is EMPTY (0 rows)** though GarminDB supports it | (b) not-imported | Low | HRV baseline/weekly trend richer than the single `last_night_average` we use; needs `--hrv` import. |

**Body composition % fat** is confirmed **(c) NOT-SUPPORTED** — Garmin imports only `weight`.

---

## 2. Full inventory (by DB) — table.column | meaning/unit | status | coverage | value

Coverage = our live DBs (row counts + % populated). USED = per the baseline in the brief.
Legend value: H/M/L = clinical/athletic value for this athlete's anamnesis.

### 2.1 `garmin.db` (file model: `garmindb/garmindb/garmin_db.py`)

| table.column | meaning / unit | status | coverage (our DB) | value |
|---|---|---|---|---|
| `daily_summary` (table) | daily roll-up | — | 2,351 rows, 2019-12-31→2026-06-07 | — |
| `daily_summary.rhr` | resting HR / bpm | USED | (see resting_hr) | H |
| `daily_summary.stress_avg` | avg stress | USED | populated | M |
| `daily_summary.bb_max/bb_min` | Body Battery max/min | USED | 55.2% | M |
| `daily_summary.bb_charged` | BB charged overnight | **CAPTURED-BUT-UNUSED** | 55.2% | M (recovery proxy) |
| `daily_summary.steps/calories_total` | steps / kcal | USED | high | L |
| `daily_summary.hr_min/hr_max` | daily HR min/max / bpm | **CAPTURED-BUT-UNUSED** | 55.3% | M |
| `daily_summary.spo2_avg/spo2_min` | daily SpO2 / % | **CAPTURED-BUT-UNUSED** | 51.6% | H (altitude) |
| `daily_summary.rr_waking_avg/rr_max/rr_min` | waking respiration / brpm | **CAPTURED-BUT-UNUSED** | 55.3% | H |
| `daily_summary.moderate_activity_time` | moderate intensity min | **CAPTURED-BUT-UNUSED** | 100% | M |
| `daily_summary.vigorous_activity_time/intensity_time_goal` | vigorous min / goal | **CAPTURED-BUT-UNUSED** | ~100% | M |
| `daily_summary.floors_up/floors_down` | floors climbed/descended | **CAPTURED-BUT-UNUSED** | 57.3% | L |
| `daily_summary.calories_active` | active kcal | **CAPTURED-BUT-UNUSED** | 86.6% | M |
| `daily_summary.calories_bmr` | basal kcal | **CAPTURED-BUT-UNUSED** | 67.2% | L |
| `daily_summary.calories_consumed` | food kcal | **CAPTURED-BUT-UNUSED** | 4.9% (sparse) | L |
| `daily_summary.hydration_intake/hydration_goal` | hydration / mL | **CAPTURED-BUT-UNUSED** | 19.7% | L |
| `daily_summary.sweat_loss` | sweat loss / mL | **CAPTURED-BUT-UNUSED** | 19.7% | L |
| `sleep` (table) | nightly sleep | — | 2,351 rows | — |
| `sleep.total_sleep/deep_sleep/rem_sleep/score` | stages + score | USED | ~51% (deep/rem/score) | H |
| `sleep.light_sleep/awake` | light + awake time | **CAPTURED-BUT-UNUSED** | 100% | M |
| `sleep.avg_spo2` | sleep SpO2 / % | **CAPTURED-BUT-UNUSED** | 50.2% | H (altitude/apnea) |
| `sleep.avg_rr` | sleep respiration / brpm | **CAPTURED-BUT-UNUSED** | 51.4% | M |
| `sleep.avg_stress` | sleep stress | **CAPTURED-BUT-UNUSED** | 51.5% | M |
| `sleep.start/end/qualifier` | timing + label | **CAPTURED-BUT-UNUSED** | populated | L |
| `sleep_events` (table) | stage transitions | **CAPTURED-BUT-UNUSED** | 7,529 rows, 2025-04-30→ | M (fragmentation) |
| `resting_hr.resting_heart_rate` | RHR / bpm | USED (via rhr) | 1,146 rows, 2022-09→2026-01 | H |
| `stress.stress` | intraday stress | **CAPTURED-BUT-UNUSED** | 1,911,801 rows | M |
| `weight.weight` | body weight / kg | USED | 417 rows, 2020-01→2026-05 | H |
| `hrv` (table: weekly_avg, baseline_low/upper, status) | daily HRV summary | **NOT-IMPORTED** | **0 rows (EMPTY)** | H if filled |
| `device_info.software_version` | firmware | **CAPTURED-BUT-UNUSED** | 22,114 rows, 86.5% | L (data-quality) |
| `device_info.battery_voltage/battery_status` | device battery | **CAPTURED-BUT-UNUSED** | 3.5% | L |
| `attributes.*` | profile, vo2max_running=54, vo2max_cycling=55, height, weight | USED | current snapshot only | M |

### 2.2 `garmin_monitoring.db` (`monitoring_db.py`)

| table.column | meaning / unit | status | coverage | value |
|---|---|---|---|---|
| `monitoring_hrv_status.last_night_average` | nightly HRV / ms | USED | 1,350 rows, 90.6% | H |
| `monitoring_hrv_status.weekly_average/last_night/baseline_low/baseline_high/status/reading_count` | HRV baseline + status | **CAPTURED-BUT-UNUSED** | 1,350 rows | H (baseline trend) |
| `monitoring_hrv_value.hrv` | intraday HRV RMSSD / ms | **CAPTURED-BUT-UNUSED** | 107,175 rows, 2022-10→2026-06 | M |
| `monitoring_pulse_ox.pulse_ox` | intraday SpO2 / % | **CAPTURED-BUT-UNUSED** | 544,818 rows | H (altitude) |
| `monitoring_rr.rr` | intraday respiration / brpm | **CAPTURED-BUT-UNUSED** | 1,460,069 rows | H |
| `monitoring_hr.heart_rate` | continuous HR / bpm | **CAPTURED-BUT-UNUSED** | 1,418,123 rows | M |
| `monitoring_intensity.moderate/vigorous_activity_time` | intensity min intraday | **CAPTURED-BUT-UNUSED** | 6,639 rows | M |
| `monitoring_climb.cum_ascent/cum_descent` | continuous floors/elev | **CAPTURED-BUT-UNUSED** | 49,862 rows | L |
| `monitoring.active_calories/steps/distance` | intraday energy/movement | **CAPTURED-BUT-UNUSED** | 529,260 rows; active_cal 28.7% | L |
| `monitoring_info.resting_metabolic_rate` | RMR / kcal | **CAPTURED-BUT-UNUSED** | 19,474 rows, 100% | M |

### 2.3 `garmin_activities.db` (`activities_db.py`)

| table.column | meaning / unit | status | coverage | value |
|---|---|---|---|---|
| `activities` (table) | per-activity summary | — | 1,190 rows (739 cycling, 185 running), 2022-07→2026-06 | — |
| `activities.training_load/training_effect` | load + aerobic TE | USED | 84.9% / 88.6% | H |
| `activities.anaerobic_training_effect` | anaerobic TE | **CAPTURED-BUT-UNUSED** | 85.5% | H |
| `activities.distance/moving_time/ascent/avg_hr/max_hr/calories/sport` | core ride metrics | USED | high | H |
| `activities.hrz_1..5_time / hrz_1..5_hr` | time-in-HR-zone + bounds | USED | hrz_1_time 100% | H |
| `activities.self_eval_feel/self_eval_effort` | subjective RPE/feel | **CAPTURED-BUT-UNUSED** | 5.1% (sparse) | M |
| `activities.avg_rr/max_rr` | activity respiration / brpm | **CAPTURED-BUT-UNUSED** | 18.5% | L |
| `activities.avg/min/max_temperature` | temperature / °C | **CAPTURED-BUT-UNUSED** | 74% | L |
| `activities.avg_cadence/max_cadence` | cadence / rpm | **CAPTURED-BUT-UNUSED** | 75% | M |
| `activities.avg_speed/max_speed/descent/start_lat,long` | speed/geo | **CAPTURED-BUT-UNUSED** | populated | L |
| `cycle_activities.vo2_max` | cycling VO2max | USED | 740 rows, 5.1% (sparse) | M |
| `cycle_activities.strokes` | pedal cycles | **CAPTURED-BUT-UNUSED** | 10.7% | L |
| `steps_activities.vo2_max` | running VO2max | USED | 221 rows, 55.7% | M |
| `steps_activities.avg_vertical_oscillation/avg_ground_contact_time/avg_gct_balance/avg_step_length/avg_vertical_ratio` | running dynamics | **CAPTURED-BUT-UNUSED** | 61.5%/100% | L (cyclist) |
| `activity_laps.*` | per-lap splits (all ActivitiesCommon cols) | **CAPTURED-BUT-UNUSED** | 14,557 rows | M (intervals) |
| `activity_splits.*` | climb/split rows | empty | **0 rows** | — |
| `activity_records` (table) | per-second stream | partial USE (hr/speed via roadmap) | 4,728,964 rows | — |
| `activity_records.hr/speed` | per-second HR/speed | USED (planned) | high | H |
| `activity_records.cadence/altitude/distance/position` | per-second stream | **CAPTURED-BUT-UNUSED** | high | M |
| `activity_records.rr/temperature` | per-second resp/temp | **CAPTURED-BUT-UNUSED** | present | L |
| `activity_records.POWER` | per-second watts | **NOT-SUPPORTED (no column)** | column absent | H |
| `paddle_activities` / `climbing_activities` | sport-specific | n/a | 5 / 0 rows | L |

### 2.4 `garmin_summary.db` + legacy `summary.db` (`summary_base.py`)

`months_summary` (58 rows, 2019-12→2026-06) is **USED**. The same `SummaryBase` columns also
exist in `days_summary` (1,619 rows in legacy `summary.db`), `weeks_summary`, `years_summary`
— mostly **CAPTURED-BUT-UNUSED** at finer/coarser granularity.

| representative column | meaning | status | coverage (months) | value |
|---|---|---|---|---|
| `rhr_avg/rhr_min/rhr_max` | RHR stats | **CAPTURED-BUT-UNUSED** | 70.7% | M |
| `inactive_hr_avg/min/max` | inactive HR | **CAPTURED-BUT-UNUSED** | populated | L |
| `weight_avg/min/max` | weight stats | **CAPTURED-BUT-UNUSED** | 81.0% | M |
| `intensity_time` | moderate+2×vigorous | **CAPTURED-BUT-UNUSED** | 100% | M |
| `rem_sleep_avg` | REM avg | **CAPTURED-BUT-UNUSED** | 100% | M |
| `spo2_avg / rr_waking_avg` | SpO2 / resp monthly | **CAPTURED-BUT-UNUSED** | 75.9% / 77.6% | H |
| `bb_max / hydration_avg / calories_active_avg` | BB / hydration / kcal | **CAPTURED-BUT-UNUSED** | 77.6% / 87.9% / 96.6% | M/L |
| `intensity_hr` (table) | HR-vs-intensity points | **CAPTURED-BUT-UNUSED** | present | L |

---

## 3. "Captured but unused" — quick wins already in our DBs

These need **zero import/config work** — only a query + a chart/line in the report. Ranked.

1. **`activities.anaerobic_training_effect`** (85.5%) — plot beside aerobic TE per ride/month;
   shows aerobic vs. anaerobic stimulus balance. *Trivial.*
2. **Intraday SpO2** — `monitoring_pulse_ox.pulse_ox` (544,818 rows) + `daily_summary.spo2_avg/min`
   (51.6%) + `sleep.avg_spo2` (50.2%). Nightly minima around training camps / altitude. *Low.*
3. **Respiration rate** — `daily_summary.rr_waking_avg` (55.3%), `sleep.avg_rr` (51.4%),
   `monitoring_rr` (1.46M rows). Waking-RR trend = recovery/illness marker. *Low.*
4. **Full HRV status** — `monitoring_hrv_status.{weekly_average, baseline_low, baseline_high,
   status}` (1,350 rows). We already read `last_night_average`; the baseline band + status give
   the clinically meaningful "in/out of personal range" read for free. *Low.*
5. **Body Battery charge** — `daily_summary.bb_charged` (55.2%): overnight recharge rate. *Low.*
6. **Sleep architecture detail** — `sleep.light_sleep`/`awake` (100%), `avg_stress` (51.5%),
   `sleep_events` (7,529 rows from 2025-04-30) for fragmentation. *Low.*
7. **Activity laps** — `activity_laps` (14,557 rows) for interval/structured-workout analysis. *Med.*
8. **RHR/weight summary stats** — `months_summary.{rhr_avg/min/max, weight_avg/min/max}`
   (70.7% / 81.0%) for min/max bands, not just the mean. *Low.*
9. **Intensity minutes & RMR** — `daily_summary.moderate/vigorous_activity_time` (100%),
   `monitoring_info.resting_metabolic_rate` (100%). *Low.*

---

## 4. "Importable but not captured" — needs a GarminDB download/import run

GarminDB *can* fetch these (code exists) but our DB lacks them. Fix = config + a download/import pass.

| Item | Evidence | Why our DB is empty | Action |
|---|---|---|---|
| **Daily `hrv` table** | `Hrv` model exists (`garmin_db.py:328`); `Statistics.hrv=8`; download `get_hrv()` (`download.py`) | Table has **0 rows** — daily HRV JSON never imported (only `monitoring_*` FIT path ran) | Run `garmindb_cli.py` with `--hrv` / `enabled_stats.hrv=true` then `--import` |
| **Hydration history** | `GarminHydrationData` importer; `daily_summary.hydration_intake` | only **19.7%** populated (no start-date config key; not in `Statistics` enum) | Backfill hydration JSON; low value here |
| **Older intraday SpO2/RR/HRV** | monitoring tables start 2022-10, daily_summary from 2019-12 | device/firmware era — no pre-2022 wrist data exists | none (hardware limit) |

Note: hydration download has **no `Statistics` enum member and no `*_start_date`** key
(`statistics.py:11`, `GarminConnectConfig.json.example`), so it is the one importer not
gated by the standard config — explaining its sparse coverage.

---

## 5. "Garmin Connect has it, GarminDB doesn't" — deepest gaps + feasibility

GarminDB has **no download method, no importer, and no table** for any of these (verified in
`download.py`, `import_monitoring.py`, `statistics.py`, and all `*_db.py` models).

| Item | Garmin Connect source | Feasibility | Value |
|---|---|---|---|
| **Cycling power** (avg/NP/max, time-in-power-zone, FTP) | raw `.fit` (`Fit/.../record` field 7 = `PowerField`, parsed but dropped by `activity_fit_file_processor`) **and** `activity_details_*.json → summaryDTO.{average,normalized,max}Power` (~788 files w/ power) | **Recoverable from our own files** (roadmap Phase 1) — no new GC download needed | **H** |
| **Cycling dynamics** (L/R balance, torque effectiveness, pedal smoothness, PCO, power phase) | `.fit` record fields 30,43–47,67–72 (parsed, not persisted) | Medium — parse `.fit`, add columns | M |
| **Training Status / Training Readiness / Recovery Time / Acute Load & Load Ratio** | GC training-status & readiness endpoints | Hard — new download + importer + tables (no endpoint in GarminDB today) | **H** |
| **Endurance Score / Hill Score / Race Predictor** | GC performance endpoints | Hard — same as above | M |
| **Lactate Threshold (HR & pace) + FTP** | GC user-stats / device settings | Hard — new endpoint; HR/pace LT is high value | **H** |
| **VO2max *history* per discipline** | GC has time series; we keep only current value in `attributes` + sparse per-activity `vo2_max` | Medium — could backfill from `activity_*` JSON | M |
| **Body composition** (% fat, muscle, bone, water, BMI) | GC Index-scale data; GarminDB imports **only `weight`** | Not supported — confirmed (only `Weight.weight`) | M |
| **Blood pressure / blood glucose / menstrual / pregnancy** | GC supports (with hardware/manual) | Not supported — no model/importer | L (this athlete) |
| **Per-second power/HRV/pulse-ox/respiration/stress streams in activities** | `.fit` `MessageType.{hrv,pulse_ox,respiration,stress_level}` parsed by submodule | Medium — `activity_records` has no power/hgb columns | M |
| **Running dynamics per-second** | `.fit` record fields 39–41,83–85 (aggregates only stored) | Medium — low value for a cyclist | L |

---

## 6. Tie-in to the TrainingPeaks north-star roadmap

`docs/plans/2026-06-09-roadmap-trainingpeaks-northstar.md` already names power as the headline gap.
This audit confirms and extends it:

- **Phase 0 (easy wins):** add §3 quick wins — **anaerobic_training_effect**, **SpO2**,
  **respiration**, **full HRV status band**, **sleep detail**, **laps**. All confirmed
  populated; aligns with the roadmap's "FC máxima / time-in-HR-zones / weekly granularity".
- **Phase 1 (power, north-star):** matches §5 row 1 — recover power from `activity_details_*.json`
  + `.fit`; the `Fit/` submodule already parses `record` field 7 (watts), the bottleneck is
  `activity_records` having **no power column** and the JSON parser reading flat keys not `summaryDTO`.
- **Phase 2 (streams + DB expansion):** §5 rows on per-second streams and "import power into a
  `power_records` table" map directly here; also HR/power mean-max curves from `activity_records`
  (4.73M rows already present).
- **Roadmap's "% Gordura não dá"** is confirmed by this audit: §5 — GarminDB imports only `weight`.
- **Beyond the roadmap:** Training Status / Readiness / Recovery Time / Lactate Threshold (§5)
  are *not* in TrainingPeaks-parity scope but are the highest-value **new-import** additions for a
  *medical* anamnesis and deserve a Phase 3 if GC-endpoint work is acceptable.

---

## 7. Bottom line — 3 most valuable, lowest-effort additions

1. **Anaerobic Training Effect** (`activities.anaerobic_training_effect`, 85.5%) — one query,
   already beside the data we use; reveals aerobic/anaerobic load mix. **Trivial / High value.**
2. **SpO2 + Respiration trends** (`monitoring_pulse_ox` 544k rows, `daily_summary.spo2_avg`,
   `sleep.avg_spo2`/`avg_rr`, `daily_summary.rr_waking_avg`) — directly relevant to the athlete's
   mountain-race altitude prep and to recovery/illness surveillance. **Low effort / High value.**
3. **Full HRV status band + Body Battery charge** (`monitoring_hrv_status.{weekly_average,
   baseline_low/high,status}`, `daily_summary.bb_charged`) — turns the single HRV number we
   already plot into an in/out-of-baseline recovery read. **Low effort / High value.**

All three are **CAPTURED-BUT-UNUSED** — zero download/import/config work, no fabrication risk.


