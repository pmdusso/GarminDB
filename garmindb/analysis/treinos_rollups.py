"""Small GarminDB rollups used by the BloodB Treinos bridge."""

import sqlite3
from pathlib import Path


LOAD_FACTORS = {
    "running": 0.8,
    "cycling": 0.6,
    "walking": 0.3,
    "swimming": 0.9,
    "strength_training": 0.5,
    "hiking": 0.5,
    "default": 0.5,
}

POWER_WINDOWS = (5, 60, 300, 1200)


def materialize_training_load(db_dir):
    db_dir = Path(db_dir)
    path = db_dir / "garmin_activities.db"
    if not path.exists():
        return {"rows": 0}
    rows = _activity_load_rows(db_dir)
    with sqlite3.connect(path) as con:
        con.execute("DROP TABLE IF EXISTS daily_training_load")
        con.execute("""
            CREATE TABLE daily_training_load (
                day TEXT NOT NULL,
                sport TEXT NOT NULL,
                activities_count INTEGER NOT NULL,
                duration_hours REAL NOT NULL,
                distance_km REAL NOT NULL,
                load REAL NOT NULL,
                estimated_load_count INTEGER NOT NULL,
                aerobic_te_avg REAL,
                anaerobic_te_avg REAL,
                PRIMARY KEY (day, sport)
            )
        """)
        con.executemany(
            "INSERT INTO daily_training_load VALUES (?,?,?,?,?,?,?,?,?)",
            [(r["day"], r["sport"], r["activities_count"], r["duration_hours"],
              r["distance_km"], r["load"], r["estimated_load_count"],
              r["aerobic_te_avg"], r["anaerobic_te_avg"]) for r in rows],
        )
    return {"rows": len(rows)}


def materialize_power_summary(db_dir):
    db_dir = Path(db_dir)
    path = db_dir / "garmin_activities.db"
    if not path.exists():
        return {"rows": 0}
    rows = _power_summary_from_records(db_dir)
    with sqlite3.connect(path) as con:
        con.execute("DROP TABLE IF EXISTS activity_power_summary")
        con.execute("""
            CREATE TABLE activity_power_summary (
                activity_id TEXT PRIMARY KEY,
                day TEXT NOT NULL,
                sport TEXT,
                duration_s INTEGER,
                avg_power REAL,
                max_power INTEGER,
                best_5s REAL,
                best_60s REAL,
                best_300s REAL,
                best_1200s REAL,
                sample_count INTEGER NOT NULL
            )
        """)
        con.executemany(
            "INSERT INTO activity_power_summary VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            [(r["activity_id"], r["day"], r["sport"], r["duration_s"],
              r["avg_power"], r["max_power"], r["best_5s"], r["best_60s"],
              r["best_300s"], r["best_1200s"], r["sample_count"]) for r in rows],
        )
    return {"rows": len(rows)}


def daily_training_load_rows(db_dir, start, end):
    db_dir = Path(db_dir)
    rows = _query(
        db_dir, "garmin_activities.db",
        "SELECT day, sport, activities_count, duration_hours, distance_km, load, "
        "estimated_load_count, aerobic_te_avg, anaerobic_te_avg "
        "FROM daily_training_load WHERE day BETWEEN ? AND ? ORDER BY day, sport",
        (start.isoformat(), end.isoformat()),
    )
    if rows:
        return [dict(r) for r in rows]
    return [r for r in _activity_load_rows(db_dir) if start.isoformat() <= r["day"] <= end.isoformat()]


def power_summary_rows(db_dir, start, end):
    rows = _query(
        Path(db_dir), "garmin_activities.db",
        "SELECT activity_id, day, sport, duration_s, avg_power, max_power, "
        "best_5s, best_60s, best_300s, best_1200s, sample_count "
        "FROM activity_power_summary WHERE day BETWEEN ? AND ? ORDER BY day",
        (start.isoformat(), end.isoformat()),
    )
    return [dict(r) for r in rows]


def daily_hrv_series(db_dir, start, end):
    db_dir = Path(db_dir)
    by_day = {}
    for row in _monitoring_hrv_rows(db_dir, start, end):
        day = _day(row["timestamp"])
        by_day[day] = {
            "day": day,
            "weekly_avg": row.get("weekly_average"),
            "last_night_avg": row["last_night_average"],
            "baseline_low": row.get("baseline_low"),
            "baseline_upper": row.get("baseline_high"),
            "status": row.get("status"),
            "source": "monitoring",
        }
    for row in _query(
        db_dir, "garmin.db",
        "SELECT day, weekly_avg, last_night_avg, baseline_low, baseline_upper, status "
        "FROM hrv WHERE day BETWEEN ? AND ? AND last_night_avg IS NOT NULL",
        (start.isoformat(), end.isoformat()),
    ):
        day = _day(row["day"])
        by_day.setdefault(day, {
            "day": day,
            "weekly_avg": row["weekly_avg"],
            "last_night_avg": row["last_night_avg"],
            "baseline_low": row["baseline_low"],
            "baseline_upper": row["baseline_upper"],
            "status": row["status"],
            "source": "garmin",
        })
    return [by_day[d] for d in sorted(by_day)]


def _monitoring_hrv_rows(db_dir, start, end):
    for db_name in ("monitoring_db.db", "garmin_monitoring.db"):
        cols = _columns(db_dir, db_name, "monitoring_hrv_status")
        if not {"timestamp", "last_night_average"}.issubset(cols):
            continue
        optional = [c for c in ("weekly_average", "baseline_low", "baseline_high", "status") if c in cols]
        select = ["timestamp", "last_night_average"] + optional
        rows = _query(
            db_dir, db_name,
            f"SELECT {', '.join(select)} FROM monitoring_hrv_status "
            "WHERE date(timestamp) BETWEEN ? AND ? AND last_night_average IS NOT NULL",
            (start.isoformat(), end.isoformat()),
        )
        if rows:
            return [dict(r) for r in rows]
    return []


def _query(db_dir, db_name, sql, params=()):
    path = db_dir / db_name
    if not path.exists():
        return []
    try:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        con.row_factory = sqlite3.Row
        try:
            return con.execute(sql, params).fetchall()
        finally:
            con.close()
    except (sqlite3.Error, OSError):
        return []


def _columns(db_dir, db_name, table):
    rows = _query(Path(db_dir), db_name, f"PRAGMA table_info({table})")
    return {r["name"] for r in rows}


def _activity_load_rows(db_dir):
    rows = _query(
        db_dir, "garmin_activities.db",
        "SELECT substr(start_time, 1, 10) AS day, sport, distance, moving_time, "
        "elapsed_time, training_load, training_effect, anaerobic_training_effect "
        "FROM activities WHERE start_time IS NOT NULL ORDER BY day, sport",
    )
    buckets = {}
    for row in rows:
        sport = row["sport"] or "unknown"
        key = (row["day"], sport)
        duration = _time_to_hours(row["moving_time"]) or _time_to_hours(row["elapsed_time"]) or 0.0
        load, estimated = _load_value(sport, duration, row["training_load"])
        bucket = buckets.setdefault(key, {
            "day": row["day"], "sport": sport, "activities_count": 0,
            "duration_hours": 0.0, "distance_km": 0.0, "load": 0.0,
            "estimated_load_count": 0, "_te": [], "_ate": [],
        })
        bucket["activities_count"] += 1
        bucket["duration_hours"] += duration
        bucket["distance_km"] += float(row["distance"] or 0)
        bucket["load"] += load
        bucket["estimated_load_count"] += 1 if estimated else 0
        if row["training_effect"] is not None:
            bucket["_te"].append(float(row["training_effect"]))
        if row["anaerobic_training_effect"] is not None:
            bucket["_ate"].append(float(row["anaerobic_training_effect"]))
    out = []
    for bucket in buckets.values():
        out.append({
            "day": bucket["day"],
            "sport": bucket["sport"],
            "activities_count": bucket["activities_count"],
            "duration_hours": round(bucket["duration_hours"], 2),
            "distance_km": round(bucket["distance_km"], 2),
            "load": round(bucket["load"], 2),
            "estimated_load_count": bucket["estimated_load_count"],
            "aerobic_te_avg": _avg(bucket["_te"]),
            "anaerobic_te_avg": _avg(bucket["_ate"]),
        })
    return sorted(out, key=lambda r: (r["day"], r["sport"]))


def _power_summary_from_records(db_dir):
    acts = {
        row["activity_id"]: row for row in _query(
            db_dir, "garmin_activities.db",
            "SELECT activity_id, substr(start_time, 1, 10) AS day, sport, moving_time "
            "FROM activities WHERE activity_id IS NOT NULL",
        )
    }
    records = _query(
        db_dir, "garmin_activities.db",
        "SELECT activity_id, timestamp, power FROM activity_records "
        "WHERE power IS NOT NULL ORDER BY activity_id, timestamp",
    )
    grouped = {}
    for row in records:
        grouped.setdefault(row["activity_id"], []).append(int(row["power"]))
    out = []
    for activity_id, powers in grouped.items():
        act = acts.get(activity_id)
        if not act or not powers:
            continue
        out.append({
            "activity_id": activity_id,
            "day": act["day"],
            "sport": act["sport"],
            "duration_s": int(round((_time_to_hours(act["moving_time"]) or 0) * 3600)) or len(powers),
            "avg_power": round(sum(powers) / len(powers), 1),
            "max_power": max(powers),
            "best_5s": _best_avg(powers, 5),
            "best_60s": _best_avg(powers, 60),
            "best_300s": _best_avg(powers, 300),
            "best_1200s": _best_avg(powers, 1200),
            "sample_count": len(powers),
        })
    return sorted(out, key=lambda r: (r["day"], r["activity_id"]))


def _load_value(sport, duration_hours, training_load):
    if training_load is not None and float(training_load) > 0:
        return float(training_load), False
    factor = LOAD_FACTORS.get(str(sport).lower(), LOAD_FACTORS["default"])
    return duration_hours * 60 * factor, True


def _time_to_hours(value):
    if not value:
        return None
    try:
        h, m, s = (list(map(float, str(value).split(":"))) + [0.0, 0.0, 0.0])[:3]
    except ValueError:
        return None
    return h + m / 60 + s / 3600


def _best_avg(values, window):
    if len(values) < window:
        return None
    current = sum(values[:window])
    best = current
    for i in range(window, len(values)):
        current += values[i] - values[i - window]
        best = max(best, current)
    return round(best / window, 1)


def _avg(values):
    return round(sum(values) / len(values), 2) if values else None


def _day(value):
    return str(value)[:10]
