# Body Battery Recharge (bb_charged) Fix Summary

## Problem
The RecoveryAnalyzer was showing "---" for the 7-day Body Battery Recharge average despite the user wearing the watch every night.

## Root Causes Found

### 1. Missing bb_charged in DailySummary.get_stats()
**File**: `garmindb/garmindb/garmin_db.py`
**Issue**: The `get_stats()` method (lines 416-448) was missing the `bb_charged` field in the returned dictionary.
**Fix Applied** (line 446):
```python
'bb_charged'                : cls.s_get_col_avg(session, cls.bb_charged, start_ts, end_ts),
```

### 2. Missing bb_charged in SummaryBase class and VIEW definition
**File**: `garmindb/summarydb/summary_base.py`
**Issues**:
- Column not defined in SummaryBase class
- Column not included in days_summary_view definition

**Fixes Applied**:
- Line 69: Added `bb_charged = Column(Integer)`
- Line 221: Added `cls.round_col('bb_charged'),` to VIEW column list
- Line 18: Incremented `view_version` from 10 to 11

### 3. Package not installed in editable mode
**Issue**: The venv had a stale copy of the code in site-packages
**Fix**: Reinstalled package in editable mode with `.venv/bin/pip install -e . --no-deps`

## Current Status

### What's Working:
1. ✅ Code fixes are in place in all necessary files
2. ✅ Package is installed in editable mode
3. ✅ VIEW definitions include bb_charged column
4. ✅ garmin_summary.db days_summary_view has the bb_charged column (verified with PRAGMA table_info)

### What's Not Working Yet:
1. ❌ The `daily_summary` table in `garmin.db` is empty (0 rows)
2. ❌ Body Battery data from JSON files is not being imported into `daily_summary` table
3. ❌ Summary tables have no bb_charged data because source table is empty

## Data Flow Analysis

The correct data flow should be:

```
daily_summary_*.json files
  ↓ (GarminSummaryData class imports)
garmin.db.daily_summary table
  ↓ (DailySummary.get_stats() aggregates)
garmin_summary.db.days_summary table
  ↓ (VIEW exposes)
garmin_summary.db.days_summary_view
  ↓ (SQLiteHealthRepository reads)
DailySummaryRecord DTO
  ↓ (RecoveryAnalyzer uses)
Report shows bb_charged data
```

Currently blocked at step 1: JSON files → daily_summary table

## JSON Data Confirmed

Verified that daily_summary JSON files contain the data:
```json
{
  "bodyBatteryChargedValue": 65,
  "bodyBatteryHighestValue": 87,
  "bodyBatteryLowestValue": 28
}
```

## Next Steps Required

1. Investigate why `garmindb_cli.py --all --import --latest` doesn't populate the `daily_summary` table
2. Verify that GarminSummaryData class is being instantiated and processing files
3. Once daily_summary is populated, run `--analyze` to propagate data to summary tables
4. Verify RecoveryAnalyzer shows correct bb_charged values in report

## Files Modified

1. `/Users/pmdusso/code/GarminDB/garmindb/garmindb/garmin_db.py` - Added bb_charged to get_stats()
2. `/Users/pmdusso/code/GarminDB/garmindb/summarydb/summary_base.py` - Added bb_charged column and VIEW column
