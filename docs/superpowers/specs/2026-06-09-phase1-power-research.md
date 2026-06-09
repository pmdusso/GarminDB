# Phase 1 — Power via Summary Files: Research

`#needs-peer-review` · Date: 2026-06-09

Consolidated research for the Phase 1 (cycling power via pre-computed Garmin summary
JSONs) implementation plan. Five parallel investigations merged: data substrate, existing
analyzer code, report integration, anamnesis/weight pairing, and eFTP/NP best practices.

**One-line thesis:** Garmin's per-activity *summary* JSONs already carry a real mean-max
power curve + 7 power zones + NP for ~602 cycling rides (2022–2026). The `PowerAnalyzer`
already reads them correctly. Phase 1 is about (a) running it longitudinally instead of in
a 30-day window, (b) adding an honest publication gate, (c) handling indoor/outdoor, and
(d) deciding where the measured-power output lands — **not** new parsing. Per-second watts
are unrecoverable from these files; everything is pre-computed scalars and curves.

---

## Data substrate (ground truth)

**Corpus:** 1191 `activity_<id>.json` (summary) + 1190 `activity_details_<id>.json`, in
`~/HealthData/FitFiles/Activities/`. Real ripgrep at `/opt/homebrew/bin/rg` (shell `rg` is
aliased to BSD grep — counts must use the real binary).

### Exact JSON keys (in the SUMMARY file)

| Key | Type | Files | Meaning |
|---|---|---|---|
| `maxAvgPower_<N>` | int W | see below | mean-max curve, N = window seconds |
| `powerTimeInZone_1..7` | float s | 602 | seconds in each of 7 zones (sum ≈ ride duration) |
| `avgPower` | float W | 788 | ride average power |
| `maxPower` | float W | 788 | raw 1-s peak — **do NOT use as "peak"** (spikes) |
| `normPower` | float W | 751 | Garmin's genuine 4th-power NP (== `summaryDTO.normalizedPower`) |
| `max20MinPower` | float W | 582 | best 20-min block (== `summaryDTO.maxPowerTwentyMinutes`) |
| `startTimeLocal` | str | all | local time `"2025-09-09 05:31:06"` (bucket year off `[0:4]`) |
| `duration` | float s | all | timer seconds (use for the NP≥30min gate) |
| `distance` | float m | all | **meters** (39078.32 → 39.08 km — convert!) |
| `activityType.typeKey` | str | all | sport filter |
| `manufacturer` | str | all | trainer brand (indoor detection) |
| `excludeFromPowerCurveReports` | bool | 602 | honor it — 5 rides flagged `true` |

### Mean-max curve durations available (15 keys)

`maxAvgPower_<N>` exists for **N ∈ {1, 2, 5, 10, 20, 30, 60, 120, 300, 600, 1200, 1800,
3600, 7200, 18000}** seconds. Longer buckets are gated by ride length:

| N(s) | files | N(s) | files | N(s) | files |
|---|---|---|---|---|---|
| 1 | 602 | 60 | 602 | 1200 | **589** |
| 2 | 602 | 120 | 601 | 1800 | 573 |
| 5 | 602 | 300 | 601 | 3600 | **489** |
| 10 | 602 | 600 | 598 | 7200 | 159 |
| 20 | 602 | 30 | 602 | 18000 | 14 |

Values are integer watts. Example `activity_20329183822`: `maxAvgPower_1200=215`,
`maxAvgPower_3600=195`. The **602** curve-bearing rides are the real "power-bearing cycling
ride" population (1-min/5s/20s curve present on all 602).

> **Note:** the current analyzer's `CURVE_DURATIONS = [5, 60, 300, 1200, 3600]` uses only 5
> of the 15 available durations. A CP-model fit (best practice §Algorithm) wants the 180s
> (`maxAvgPower_180`? — **not in the list**; closest are 120 and 300) and 600/720s anchors.
> The 3–12 min CP window maps onto available keys **300, 600, 1200** (5/10/20 min); there is
> **no native 3-min (180s) bucket** — closest are `maxAvgPower_120` (2 min) and
> `maxAvgPower_300` (5 min). This constrains CP fitting (see Algorithm).

### NP availability and reliability

- `normPower` present on **751** files; equals `summaryDTO.normalizedPower` in details.
- **It is Garmin's genuine 4th-power NP**, always ≥ `avgPower`.
- **Trap:** on **37% of rides (214/582), `normPower` EXCEEDS `max20MinPower`** — physically
  impossible for a steady effort, but normal for **interval/erg trainer workouts** where
  surges inflate whole-ride NP above any 20-min block. **Treat `normPower` as a variability
  metric, NOT a 20-min FTP proxy.** For FTP use `max20MinPower × 0.95` or `maxAvgPower_1200`.
- High-variability exemplar `activity_15747953757`: NP 258 vs max20 229.

### Indoor / outdoor detection (real values)

**No boolean exists** (`trainer`/`virtualRide`/`isIndoor` absent). **GPS presence does NOT
separate them** — 356 TACX "cycling" trainer rides carry *simulated GPS + `hasPolyline=true`*
(TACX real-world video routes). Detection = `activityType.typeKey` + `manufacturer`:

| typeKey | manufacturer | count | class |
|---|---|---|---|
| cycling | TACX | 356 | INDOOR (TACX films, sim GPS) |
| indoor_cycling | THE_SUFFERFEST | 69 | INDOOR |
| road_biking | GARMIN | 32 | OUTDOOR |
| indoor_cycling | GARMIN | 32 | INDOOR |
| indoor_cycling | TACX | 26 | INDOOR |
| indoor_cycling | TRAINER_ROAD | 22 | INDOOR |
| virtual_ride | VIRTUALTRAINING | 16 | INDOOR (virtual) |
| cycling | GARMIN | 13 | OUTDOOR |
| virtual_ride | TACX | 12 | INDOOR (virtual) |
| cycling | (blank) | 9 | outdoor-ish |
| mountain_biking | GARMIN | 5 | OUTDOOR |
| cycling | WAHOO_FITNESS | 5 | OUTDOOR |
| indoor_cycling | DEVELOPMENT | 2 | INDOOR |

**Recommended indoor rule:** `typeKey ∈ {indoor_cycling, virtual_ride}` **OR**
`manufacturer ∈ {TACX, THE_SUFFERFEST, TRAINER_ROAD, VIRTUALTRAINING}`.
Exemplars: indoor TACX `20329183822` (manufacturer TACX, typeKey cycling, sim GPS);
outdoor GARMIN road `22532795249` (real GPS −30.05,−51.20).

### Coverage by year (curve-present rides, by `startTimeLocal`)

| Year | INDOOR | OUTDOOR | Total |
|---|---|---|---|
| 2022 | 5 | 0 | 5 |
| 2023 | 109 | 36 | 145 |
| 2024 | 189 | 6 | 195 |
| 2025 | 165 | 19 | 184 |
| 2026 | 68 | 5 | 73 |
| **All** | **536** | **66** | **602** |

Data extends back to **2022**, not just 2024+. Heavily indoor (536/602). NP≥30min gate is
feasible: **567** curve rides have `duration ≥ 1800s AND normPower present`.

### Cycling sport filter

`activityType.typeKey ∈ {cycling, road_biking, indoor_cycling, virtual_ride,
mountain_biking}`, all share `sportTypeId=2`. No `gravel_cycling` key appears in this corpus
(the analyzer lists it but it never matches here). Power-bearing counts: cycling 385,
indoor_cycling 152, road_biking 32, virtual_ride 28, mountain_biking 5. `parentTypeId`
(17 = outdoor umbrella, 2 = subtypes) is **unreliable** for indoor/outdoor (TACX cycling
uses 17). Gate on `sportTypeId=2` + `typeKey`.

### Per-second watts are NOT recoverable — CONFIRMED

`activity_details_*.json` has **NO `metricDescriptors`, NO `activityDetailMetrics`** —
verified across **all 1190 details files (0 matches)**; no array exceeds 20 elements.
`summaryDTO` carries only scalars: `averagePower, maxPower, minPower, normalizedPower,
maxPowerTwentyMinutes, totalWork` + pedal balance/TE/smoothness. **`totalWork` is in
kilocalories, NOT joules** (avgP×dur/4184 ≈ totalWork ≈ `calories`: 943kJ/4.184=225.5). To
get streams you'd need raw `.fit` files or the Garmin details API with `maxChartSize` params
— **out of scope for Phase 1.** Any NP "recompute from a 1-Hz stream" is therefore impossible.

### Data-quality flags

- Honor `excludeFromPowerCurveReports` (5 rides `true`, 597 `false`).
- Malformed exemplar `activity_11291889627` (blank manufacturer): `maxAvgPower_1200=27` vs
  `avgPower=72` — nonsensical. Add sanity bounds.
- **No power-meter-quality flag.** TACX/SufferFest/TrainerRoad numbers are trainer-derived;
  flag indoor as lower-trust for absolute watts.

---

## Existing code

Primary file: `garmindb/analysis/power_analyzer.py`. Filesystem/glob-based, **fully
decoupled from the SQLite DBs** — reads summary `activity_*.json` directly (docstring lines
3–7).

### PowerAnalyzer API

- **Constructor** `power_analyzer.py:67`:
  `def __init__(self, activities_dir: str, configured_ftp: Optional[float] = None)`.
  Stores `self._dir`, `self._ftp`. No repository, no DB.
- **Public method** `power_analyzer.py:170`:
  `def analyze(self, start_date: date, end_date: date) -> "PowerAnalysisResult"`.
- `_parse_ride` is a `@staticmethod` exercised directly by tests (semi-public).

### What it reads (keys consumed in `_parse_ride`, `:75-117`)

- Sport filter `:86-88`: `data["activityType"]["typeKey"]` ∈ `CYCLING_TYPES` (`:24-27`:
  cycling, virtual_ride, road_biking, indoor_cycling, gravel_cycling, mountain_biking).
- Curve `:91-94`: `data.get(f"maxAvgPower_{d}")` for `d ∈ CURVE_DURATIONS = [5,60,300,1200,3600]` (`:22`).
- Usability gate `:95-96`: drop ride if `not peak and data.get("normPower") is None`.
- Zones `:98-102`: `data.get(f"powerTimeInZone_{z}")` for `z ∈ 1..7` (seconds).
- Date `:104-108`: `data["startTimeLocal"][:10]` parsed `%Y-%m-%d`.
- avg/norm `:113-114`: `avgPower`, `normPower` carried onto `PowerRide` but **never used in
  `analyze()`**. Accepts dict or 1-element-list payload (`:82-83`).

### The 30-day-window mechanic — important correction

- The analyzer's own recent window is **`RECENT_WINDOW_DAYS = 90`** (`:65`), NOT 30.
- The "37 rides" / "30-day" artefact lives in the **report period** (`start_date`/`end_date`)
  passed by the caller `generate_report.py:116`: `start = args.start or (end - td(days=30))`.
- Window applied in `analyze` (`:176-178`):
  `recent_start = end_date - timedelta(days=90)`; `recent = [r for r in all_rides if recent_start <= r.date <= end_date]`.

### All-time is ALREADY half-computed

`analyze()` already produces both views:
- `curve_all = self._best_curve(all_rides)` (`:181`) — no date filter; `best20_all = curve_all.get(1200)` (`:183`).
- Flow into `power_curve_alltime`, `best_20min_alltime` (`:195-197`).

Still windowed (the source of "37"): `est_ftp = round(best20_recent * 0.95)` (`:184`);
`ftp_needs_test` (`:185-187`); `power_zone_distribution = _zone_distribution(recent)` (`:198`);
`rides_with_power = len(recent)` (`:199`) — **this is the "37" counter**;
`total_rides = len(all_rides)` (`:200`) is already all-time.

**To run all-time:** caller passes a `start`/`end` spanning full history (ensure `end−90d` <
first ride). Cleaner: surface the existing `*_alltime` fields and/or recompute `estimated_ftp`,
`power_zone_distribution`, `rides_with_power` from `all_rides`.

### Done vs missing in the analyzer

**Done:** `_best_curve` (`:119-126`, max per duration); eFTP `best20_recent * 0.95` (`:184`,
recent only); `ftp_needs_test` Insight (`:212-234`, Portuguese); `_zone_distribution`
(`:158-168`, percent of time); corrupt-file `skipped_files` counter (`:141-156`).

**Missing (= Phase 1 work):** eFTP publication gate; indoor/outdoor split; per-ride W·kg with
paired weight; NP validation/use; CP-model fit. (Raw `maxPower` is *correctly* never read —
analyzer only reads `maxAvgPower_*`.)

### Caller, report, targets

- Sole production call site: `performance_report.py:17` (import), `:44-45`
  `_run_power(activities_dir, ftp, start, end) → PowerAnalyzer(...).analyze(...)`, `:120`
  `power = _run_power(self._acts_dir, t.ftp_watts, start_date, end_date)`.
- `--performance` flow: entry `generate_report.py:95-134`; builder `PerformanceReportBuilder`
  (`performance_report.py:108`); renderer `PerformancePresenter`
  (`presentation/markdown/performance_renderer.py:14`). Default window **30 days**
  (`generate_report.py:116`). Activities dir resolved `generate_report.py:108-110` →
  `<db_path>/../FitFiles/Activities`.
- **Already consumes** full `PowerAnalysisResult` (`PerformanceReport.power`,
  `performance_report.py:93`). Output today: `ftp_used = t.ftp_watts or power.estimated_ftp`
  (`:129`) → one "FTP" scorecard row (target/gap hard-coded `"—"`, `:181`);
  `wkg = ftp_used / weight` (`:130`) → "W/kg" row. **Renderer DROPS** `estimated_ftp` (as a
  distinct number), `best_20min_recent/alltime`, `power_curve_recent/alltime`,
  `power_zone_distribution`. Only `_coverage()` (`performance_renderer.py:80-117`) surfaces
  `rides_with_power / total_rides / skipped_files`. **Phase 1 measured-power block in
  `--performance` = wiring already-computed fields into the renderer, not new analysis.**

#### `PerformanceTargets` (`performance_targets.py:12-20`)

```python
@dataclass
class PerformanceTargets:
    ftp_watts: Optional[float] = None
    weight_target_kg: Optional[float] = None
    wkg_target: Optional[float] = None
    race_name: Optional[str] = None
    race_date: Optional[str] = None
```

`load_performance_targets()` (`:43-73`): default path `~/.GarminDb/performance_targets.json`;
empty `PerformanceTargets()` if absent; numerics via `_coerce_float` (loud `ValueError` on
malformed); **explicit key-by-key mapping (`:65-71`) — any extra JSON key is silently
ignored**, so a new config field requires editing both the dataclass and this function.

#### `performance_targets.json` actual content

| key | value |
|---|---|
| `ftp_watts` | `325` |
| `weight_target_kg` | `80` |
| `wkg_target` | `4.0` |
| `race_name` | `"L'Étape Campos do Jordão 2026"` |
| `race_date` | `"2026-09-27"` |

These are *configured goals*, not measurements (configured W·kg = 325/80 = 4.06).

### The anamnesis `_power_caveat` to replace

`--anamnesis` flow: `generate_report.py:71-94`; builder `LongitudinalReportBuilder`
(`longitudinal_report.py:246`); renderer `LongitudinalPresenter` (`longitudinal_renderer.py:62`).
It **reads SQLite directly** (`_query`, `longitudinal_report.py:391-408`) and **does NOT use
PowerAnalyzer**. Window: prior calendar year → today (`generate_report.py:83`), month-by-month.
Audience: **sports-medicine clinician** (this is the anamnesis deliverable, committed at
`docs/reports/relatorio-anamnese-2025-2026.md`).

It **asserts a falsehood Phase 1 disproves.** Three hardcoded "no power" locations to keep in
sync:
1. `_power_caveat()` `longitudinal_renderer.py:358-380` — heading
   `### Potência (FTP / W·kg) — somente metas configuradas` (`:364`) + blockquote
   `> ⚠️ **Não há dados de potência** nas bases…` (`:365-367`); W·kg =
   `t.ftp_watts / r.current_weight` (`:361-362`).
2. `_provenance()` `:515-516`: `- **Sem dados de potência.** Nenhuma atividade registrou watts…`
3. `_frontmatter` `:129`: `data_caveat` includes `… sem dados de potência`.
Plus module docstring `longitudinal_report.py:10-11` ("There is NO power-meter data").
Power values come **only** from `r.targets`; **no `series["power"]` / FTP series exists** in
the `series` dict (`longitudinal_report.py:288-355`). A measured-power path needs a new
builder method feeding a series or report field, plus a gate flag the renderer branches on.
The natural home is section 3 `_aerobic()` (`:334-356`, which ends by calling `_power_caveat`
at `:355`), beside VO2max.

### Weight-pairing approach

Table `weight` in `garmin.db`: day col `day` (ISO text, queried `date(day)`), value col `weight`.

- **`_latest_weight()`** `longitudinal_report.py:445-471` — robust "current" scalar =
  **median of weigh-ins in the last 45 days** (hand-rolled median: sort, middle / mean of two
  middles; no `statistics.median`). Fallback: most-recent single reading. Becomes
  `athlete.weight_kg` → `report.current_weight` (`:371`), used for ALL W·kg math today.
  Deliberately robust against an outlier (docstring cites a 87.25 kg reading == profile config).
- **`_weight_series()`** `:783-802` — monthly-**mean** trend series (`MetricSeries key="weight"`).
- **No per-ride pairing exists.** For per-ride W·kg within ±7d, mirror the `_latest_weight`
  median style:
  ```sql
  SELECT weight FROM weight
  WHERE weight IS NOT NULL
    AND date(day) >= date(?, '-7 days') AND date(day) <= date(?, '+7 days')
  ```
  bind ride date twice; reduce to median (consistent) or nearest-in-time
  (`ORDER BY abs(julianday(day)-julianday(?)) LIMIT 1`). Ride dates from
  `_read_activities()` (`:475-485`, `start_time → _parse_date`). `_query` (`:391-408`) returns
  `[]` on missing file / any `sqlite3.Error` — degrades gracefully.

---

## Algorithm (grounded in cited best practices)

### eFTP from the mean-max curve

- **Default (Phase 1):** `eFTP = best maxAvgPower_1200 × 0.95` (best 20-min × 0.95). The 5%
  haircut compensates for residual W′ in a 20-min effort. Equivalent input: `max20MinPower`
  (582 files) — prefer `maxAvgPower_1200` (589 files) for the curve-consistent value.
- **Multiplier is rider-dependent (0.92–0.97), not universal.** Overestimates for
  anaerobically-strong riders, underestimates for steady-state TTers. **Record the multiplier;
  default 0.95; allow a rider-type note.**
- **Caveat for a *passive* curve:** the canonical 20-min protocol requires blowing off W′
  first (5-s sprints + 5-min VO2max effort + recovery). A 20-min peak harvested from arbitrary
  ride history almost never satisfies this → blind ×0.95 on a found peak is the *least*
  trustworthy variant. This is exactly why the publication gate (below) matters.
- **Alternative — CP 2-parameter model** (`Work = CP·t + W′`, i.e. `P(t) = W′/t + CP`): more
  reliable when ≥2 *validated maximal* anchors exist at distinct durations. Best input window
  **~3–12 min**; test-retest CP r≈0.94, W′ r≈0.87. **Constraint from our data:** no native
  180-s (3-min) bucket — usable anchors are `maxAvgPower_300/600/1200` (5/10/20 min). CP lands
  a few % above 20-min×0.95 and is *not the same number* as FTP — never present them as one. CP
  fit on submaximal anchors is *confidently wrong*; require maximality per anchor. **Recommend:
  ship ×0.95 in Phase 1; defer CP fit to a later phase** (the maximality gate per-anchor is the
  hard part and we lack a clean 3-min bucket).

### NP — recompute vs stored

- **Recompute from a 1-Hz stream is IMPOSSIBLE** here (no per-second watts in any file). The
  Coggan algorithm (30-s rolling avg → 4th power → mean → 4th root) needs the stream.
- **Use the stored `normPower`** (Garmin's genuine 4th-power NP) as a *variability* metric
  only. **Do NOT use it as a 20-min FTP proxy** — 37% of rides have NP > max20MinPower.
- A `maxAvgPower`-derived proxy is not NP; don't conflate.

### The NP ≥ 30-min rule

NP is "somewhat misleading" for efforts < ~20 min (TrainerRoad); practical floor **≥20–30 min**.
On a 5-min sprint-fest a single surge dominates → NP inflates. **Gate NP usage/display on
`duration ≥ 1800s`** (our data: 567 rides qualify). Otherwise label "NP não representativa
(esforço curto/variável)".

### Spike filter — `maxAvgPower_5`, not raw `maxPower`

- Raw 1-s `maxPower` is dominated by electrical/dropout artifacts (e.g. 2000–2400 W transients
  with zero neighbors, no cadence). Plausibility ceiling for trained amateurs ~1500–1800 W (1 s).
- **Report best-5-s (`maxAvgPower_5`) as the neuromuscular peak; never raw `maxPower`.**
  5-s averaging *reduces but doesn't eliminate* a sharp spike (2400 W × 2 s ≈ 1000 W over 5 s),
  so combine with a rider-relative plausibility ceiling. The analyzer already only reads
  `maxAvgPower_*` — keep that; just expose `maxAvgPower_5` as "peak", and drop curves failing
  sanity bounds / `excludeFromPowerCurveReports`.

### 7-zone Coggan mapping (% of FTP)

| Zone | Name | % FTP |
|---|---|---|
| Z1 | Active Recovery | ≤ 55 |
| Z2 | Endurance | 56–75 |
| Z3 | Tempo | 76–90 |
| Z4 | Lactate Threshold | 91–105 |
| Z5 | VO2max | 106–120 |
| Z6 | Anaerobic Capacity | 121–150 |
| Z7 | Neuromuscular | > 150 |

Garmin's `powerTimeInZone_1..7` already give seconds-in-zone → use directly for the
distribution; the % boundaries above are only needed if we recompute zones from a chosen FTP.
Map to polarized TID (low = Z1–Z2, moderate = Z3, high = Z4–Z7). **TID is only valid against a
trustworthy current FTP** — if FTP is stale, the distribution is mislabeled; always state the
FTP and date the zones derive from. (Garmin's stored zones were computed against whatever FTP
the device had at ride time — a provenance caveat to disclose.)

### W/kg with paired weight (±7d)

`W/kg = power / bodyMass`. A stale weight corrupts it (2 kg drift ≈ 3% error, comparable to
device tolerance). **Pair each power figure with the weight nearest in time (±7d window)**;
suppress or label-with-date if no contemporaneous weight. Reuse the `_latest_weight` median
pattern over the ±7d window (see Weight-pairing). For a medical reader, never show W/kg without
the weight value and its date.

### Indoor/outdoor handling

Same rider: indoor FTP/power commonly **~20–30 W (8–12%) lower** than outdoor (cooling, fixed
position, no coasting micro-recoveries, ±2–5% trainer tolerance). **Don't silently pool indoor
and outdoor into one MMP curve for FTP.** Tag source (trainer vs power-meter) + environment;
surface to the clinician. Given our corpus is 536/602 indoor, a single pooled eFTP is
*indoor-biased* — the 66 outdoor rides are a thin, possibly-PB-bearing minority.

---

## Publication gate (proposed)

Publish a **"measured eFTP"** number only if ALL hold; otherwise fall back to **"configurado,
não testado"** (configured FTP, untested):

1. **Recency.** Newest qualifying 20-min effort within **last 6 weeks** (~42 days) of the
   report `end_date`. FTP drifts ±3–5%; an old peak doesn't reflect current fitness.
2. **Hard-effort / IF threshold.** The qualifying ride's 20-min block must represent a genuine
   near-threshold effort. Operationalize with the data we have: the ride's `normPower`
   (variability ok at ≥30 min) and `maxAvgPower_1200` should imply **IF ≈ NP/configuredFTP ≥
   0.90** (relax from the textbook 0.95 because trainer NP is noisy and indoor power is
   deficit-biased). Alternatively, gate on `maxAvgPower_1200 ≥ 0.90 × max20MinPower` to confirm
   a sustained (not surge-driven) block.
3. **Minimum candidate count.** Require **≥3 rides** in the recency window carrying
   `maxAvgPower_1200` (one dubious peak is not enough). All-time curve PBs can still be shown as
   "histórico" regardless of the gate.
4. **Artifact-clean.** Candidate survives sanity bounds and `excludeFromPowerCurveReports=false`.
5. **Source disclosure.** Label indoor-derived eFTP as such; don't mix silently.

**Verdict states:**
- Gate passes → publish **"eFTP medido ≈ X W (melhor 20-min × 0.95, janela 6 sem, N pedais,
  fonte indoor/outdoor)"**.
- Gate fails / no qualifying effort → publish **"FTP configurado X W (não testado nestes
  dados; última validação <date or 'n/d'>)"** + show the all-time curve as historical context.

Rationale: the output goes to a sports-medicine doctor. Every number must be data-honest —
gated on quality, labeled when estimated, never presented as a measured threshold when it's a
field approximation off a *passive* curve.

---

## Open design decisions for the human (CRITICAL)

Each fork the plan author must resolve with the user, with concrete options + recommended
default:

**(a) eFTP gate regime / thresholds.**
- Options: (i) **strict** — IF≥0.95, recency≤4 wk, ≥2 anchors, CP fit; (ii) **moderate** —
  IF≥0.90, recency≤6 wk, ≥3 rides w/ `maxAvgPower_1200`, ×0.95 only; (iii) **lax** — any 20-min
  peak ×0.95, no recency (current behavior).
- **Recommended default: (ii) moderate** — matches our noisy-indoor reality and "data-honest
  for a doctor" mandate without demanding maximality we can't verify.

**(b) Indoor/outdoor — label each PB or keep separate curves.**
- Options: (i) **one pooled curve, each PB labeled** indoor/outdoor; (ii) **two separate
  curves** (indoor / outdoor) with separate eFTP; (iii) pooled, indoor-only (ignore the 66
  outdoor as too sparse).
- **Recommended default: (ii) separate curves, but eFTP from outdoor only if it passes the gate,
  else indoor eFTP explicitly labeled "indoor (≈8–12% deficit vs outdoor)".** Pooling
  indoor-biases the headline number; 536 indoor vs 66 outdoor makes pooling misleading.

**(c) WHERE the measured-power output lands.**
- Options: (i) **enrich `--performance` only** (lowest friction — analyzer already runs; pure
  renderer change); (ii) **replace the anamnesis `_power_caveat` only** (highest clinical value,
  but requires wiring PowerAnalyzer into the SQLite-only builder + fixing 3 "no power" strings);
  (iii) **both**.
- **Recommended default: (iii) both** — but sequence it: do `--performance` first (cheap, no
  false-claim risk), then anamnesis. **The anamnesis is the priority for correctness** because
  it currently asserts a falsehood ("Não há dados de potência") that the two reports would
  otherwise contradict. At minimum, the anamnesis caveat MUST be corrected even if no eFTP is
  published.

**(d) NP: recompute vs trust stored vs proxy.**
- Options: (i) **recompute from a 1-Hz stream** — *impossible* (no per-second watts); (ii)
  **trust stored `normPower`** as a variability metric only, gated ≥30 min; (iii) **maxAvgPower-
  derived proxy** (not真 NP).
- **Recommended default: (ii) trust stored `normPower`, gated to `duration ≥ 1800s`, displayed
  as a variability indicator only — never as an FTP/IF input.** Option (i) is off the table.

**Bonus fork — zones anchor FTP:** derive zone boundaries / target-W·kg from **configured FTP
(325)** or **measured eFTP**? The current precedence `t.ftp_watts or power.estimated_ftp`
(`performance_report.py:129`) silently prefers configured. **Recommended: surface BOTH so the
configured-vs-measured gap is visible** rather than overwritten.

---

## Sources

- Critical Powers — Formulas from *Training and Racing with a Power Meter*: https://medium.com/critical-powers/formulas-from-training-and-racing-with-a-power-meter-2a295c661b46
- TrainerRoad — Normalized Power: https://www.trainerroad.com/blog/normalized-power-what-it-is-and-how-to-use-it/
- TrainingPeaks — NP, IF, TSS: https://www.trainingpeaks.com/learn/articles/normalized-power-intensity-factor-training-stress/
- TrainingPeaks (coach blog) — Understanding NP: https://www.trainingpeaks.com/coach-blog/normalized-power-how-coaches-use/
- Fast Talk Labs — FTP from a 20-Minute Power Test: https://www.fasttalklabs.com/physiology/coachs-corner-how-to-determine-ftp-from-a-20-minute-power-test/
- INSCYD — FTP limitations: https://inscyd.com/article/ftp-limitation/
- Vekta — FTP vs Critical Power: https://joinvekta.com/blog/ftp-criticalpower
- FasCat — FTP versus Critical Power: https://fascatcoaching.com/blogs/training-tips/ftp-versus-critical-power/
- High North — Critical Power and W′ (calculator): https://www.highnorth.co.uk/articles/critical-power-calculator
- Working Triathlete — Critical Power Testing: https://www.workingtriathlete.com/articles/2023/1/23/critical-power-testing-how-do-dial-in-your-intensity-zones
- PubMed 16261386 — two-parameter model validity: https://pubmed.ncbi.nlm.nih.gov/16261386/
- PMC7862708 — CP test vs 20-min FTP: https://www.ncbi.nlm.nih.gov/pmc/articles/PMC7862708/
- Xert / Baron Biosystems — Real-Time FTP Determination: https://www.baronbiosys.com/real-time-ftp-determination/
- TrainerRoad — AI FTP Detection (intro): https://www.trainerroad.com/blog/ftp-testing-is-a-thing-of-the-past-introducing-ai-ftp-detection/
- TrainerRoad — AI FTP Detection FAQ: https://www.trainerroad.com/blog/trainerroad-ai-ftp-detection-faq/
- TrainerRoad — Why is AI FTP Detecting an FTP Change?: https://www.trainerroad.com/blog/why-is-ai-ftp-detecting-an-ftp-change/
- Xert Community Forum — Eliminating power spikes: https://forum.xertonline.com/t/eliminating-power-spikes/10909
- TrainingPeaks — Adjusting FTP for Indoor Riding: https://www.trainingpeaks.com/blog/adjusting-your-functional-threshold-power-for-indoor-riding/
- Wahoo — Power meter vs smart trainer numbers: https://support.wahoofitness.com/hc/en-us/articles/4402697595538-My-power-meter-numbers-don-t-match-my-smart-trainer-numbers-Why
- DC Rainmaker — Troubleshooting Trainer Accuracy: https://www.dcrainmaker.com/2018/12/troubleshooting-trainer-accuracy.html
- Roadman Cycling — FTP Training Zones (7-Zone Coggan): https://roadmancycling.com/blog/ftp-training-zones-cycling-complete-guide
- TrainingPeaks — Zones Calculator Overview: https://help.trainingpeaks.com/hc/en-us/articles/360017420092-Zones-Calculator-Overview
- TrainerRoad — Power-to-Weight Ratio: https://www.trainerroad.com/blog/power-to-weight-ratio-for-cyclists-when-watts-kg-matters-and-how-to-improve-it/
- TrainingPeaks — Why Weight Is Important in Cycling: https://www.trainingpeaks.com/blog/why-is-weight-so-important-in-cycling-part-1/
