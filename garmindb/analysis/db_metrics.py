"""Read-only metric helpers that go straight to sqlite.

Some GarminDB tables (e.g. cycle_activities.vo2_max) are not exposed
through the SQLAlchemy DTO repository, so we read them directly.
"""

import os
import sqlite3
from datetime import date
from typing import Optional


def get_latest_vo2max(db_dir: str, start_date: date, end_date: date) -> Optional[float]:
    """Return the max cycling VO2max recorded in [start_date, end_date].

    Args:
        db_dir: Directory containing garmin_activities.db.
        start_date: Inclusive range start.
        end_date: Inclusive range end.

    Returns:
        Max vo2_max as float, or None if no data / db missing.
    """
    path = os.path.join(db_dir, "garmin_activities.db")
    if not os.path.exists(path):
        return None
    con = sqlite3.connect(path)
    try:
        row = con.execute(
            "SELECT MAX(ca.vo2_max) FROM cycle_activities ca "
            "JOIN activities a ON ca.activity_id = a.activity_id "
            "WHERE ca.vo2_max IS NOT NULL AND date(a.start_time) BETWEEN ? AND ?",
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchone()
    finally:
        con.close()
    return float(row[0]) if row and row[0] is not None else None
