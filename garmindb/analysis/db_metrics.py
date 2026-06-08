"""Read-only metric helpers that go straight to sqlite.

Some GarminDB tables (e.g. cycle_activities.vo2_max) are not exposed
through the SQLAlchemy DTO repository, so we read them directly.
"""

import logging
import os
import sqlite3
from datetime import date
from typing import Optional

logger = logging.getLogger(__name__)


def get_latest_vo2max(db_dir: str, start_date: date, end_date: date) -> Optional[float]:
    """Return the max cycling VO2max recorded in [start_date, end_date].

    Args:
        db_dir: Directory containing garmin_activities.db.
        start_date: Inclusive range start.
        end_date: Inclusive range end.

    Returns:
        Max vo2_max as float, or None if no data / db missing / unreadable.

    A missing file, an old schema (no cycle_activities/vo2_max), a locked DB
    (a concurrent ``garmindb_cli --import``) or a corrupt DB must never crash
    report generation; in those cases this logs a warning and returns None so
    the already-computed power/recovery/sleep sections survive.
    """
    path = os.path.join(db_dir, "garmin_activities.db")
    if not os.path.exists(path):
        logger.debug("VO2max source DB not found at %s; returning None", path)
        return None
    con = None
    try:
        con = sqlite3.connect(path)
        row = con.execute(
            "SELECT MAX(ca.vo2_max) FROM cycle_activities ca "
            "JOIN activities a ON ca.activity_id = a.activity_id "
            "WHERE ca.vo2_max IS NOT NULL AND date(a.start_time) BETWEEN ? AND ?",
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchone()
    except sqlite3.Error as e:
        logger.warning("VO2max query on %s failed (%s); returning None", path, e)
        return None
    finally:
        if con is not None:
            con.close()
    return float(row[0]) if row and row[0] is not None else None
