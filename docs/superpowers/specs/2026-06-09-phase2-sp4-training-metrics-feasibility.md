# SP4 — Feasibility: Training Status / Readiness / Recovery / Lactate Threshold

Status: **FEASIBILITY REPORT (read-only). No build performed.**
Phase: 2 ("Profundidade"), sub-project 4. Verdict: **all four are feasible; no blockers.**

## 1. Question

The roadmap flagged Training Status, Training Readiness, Recovery Time and
Lactate Threshold as unsupported upstream and possibly impossible (no endpoint).
SP4 checks tcgoetz/GarminDB issues + the Garmin Connect endpoints and reports
feasibility **before** any build is committed.

## 2. Upstream status (tcgoetz/GarminDB)

- Issue **#221** "Add support for Training Status/Training Load" — **closed
  2024-02-20**. Training *Load* is supported (`activities.training_load`, which
  our reports already use); Training *Status* itself was **not** added.
- No open issues for readiness / recovery time / lactate threshold.
- Conclusion: genuinely unsupported, with prior user demand.

## 3. Endpoint evidence

All four use the pattern GarminDB already uses everywhere:
`self.garmin.connectapi(url[, params])` -> `save_json_to_file` -> importer ->
table -> `Statistics` enum toggle. The "no endpoint" fear is resolved.

| Metric | Source | Effort | Evidence |
|---|---|---|---|
| **Lactate Threshold (HR & pace)** | **already on disk** in `user-settings.json` (downloaded at `download.py:67`) | **LOW** | Verified locally: `lactateThresholdHeartRate=172`, `lactateThresholdHeartRateCycling`, `lactateThresholdRowingPace`, `lactateThresholdSpeed=0.364` (unit ambiguous — see caveats). garth models the same fields (`garth/users/settings.py:53-54`). **No new download needed.** |
| **Training Readiness** | `GET /metrics-service/metrics/trainingreadiness/{date}` | **MEDIUM** | python-garminconnect `get_training_readiness`; returns `score`, `level`, `feedbackShort`, `sleepScore`, ACWR factors. garth does **not** wrap it -> raw `connectapi`. |
| **Recovery Time** | **same readiness endpoint** (`recoveryTime` field) | **MEDIUM** | Bundled in the readiness payload (`recoveryTime`, `recoveryTimeFactorPercent`) — one endpoint delivers both. |
| **Training Status** | `GET /metrics-service/metrics/trainingstatus/aggregated/{date}` | **MEDIUM** | python-garminconnect `get_training_status`; returns `trainingStatus`, `weeklyTrainingLoad`, **ACWR** (acute:chronic workload ratio), VO2max trend, heat/altitude acclimation. Nested JSON. |

## 4. Data-honesty caveats

- **Device-era gated:** readiness/status/recovery are recent Fenix/Forerunner
  features. History is shallow and dated endpoints backfill day-by-day only as
  far as Garmin retains data server-side.
- **Lactate Threshold is a current snapshot**, not a trend (like vo2max in
  `attributes`). A trend needs us to snapshot it over time.
- **`lactateThresholdSpeed=0.364` unit is unverified** (implausible as m/s for
  running). `lactateThresholdHeartRate=172` is the solid, directly clinical
  value. Any pace value must be unit-checked before it reaches a doctor.

## 5. Recommendation (a future Phase 3, value/effort order)

1. **Lactate Threshold HR** — lowest effort (data already downloaded), directly
   clinical. Parse `user-settings.json` into a field/table; optionally snapshot
   for a trend.
2. **Training Readiness + Recovery Time** — one endpoint; recovery/overtraining
   surveillance. New download + importer + table + `Statistics` toggle.
3. **Training Status + ACWR** — fitness-trend label + injury-risk ratio. Same
   pattern; nested-JSON parse.

Each is the standard download->import->table->toggle. No blockers found.

## 6. Scope note

This was a feasibility check only. No code, schema, downloader, or importer was
written for these metrics. Building any of them is a separate, approved Phase 3.
