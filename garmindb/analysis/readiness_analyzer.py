"""Training Readiness longitudinal analysis from the garmin.db table.

Reads the ``training_readiness`` table and produces a monthly mean score
series plus the most recent days, for the clinical anamnesis. Never raises:
returns an empty result on any DB problem (same contract as the decoupling
analyzer).
"""

import logging
import os
import sqlite3
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import List, Optional, Sequence, Tuple

logger = logging.getLogger(__name__)

RECENT_DAYS = 7


@dataclass
class ReadinessDay:
    """One day's readiness summary for the recent-days table."""

    day: date
    score: int
    level: str
    recovery_time: Optional[int]
    feedback_short: str


@dataclass
class TrainingReadinessResult:
    """Output of TrainingReadinessAnalyzer.analyze()."""

    period_start: date
    period_end: date
    recent_days: List[ReadinessDay] = field(default_factory=list)
    monthly_score: List[Tuple[str, Optional[float]]] = field(default_factory=list)
    day_count: int = 0


class TrainingReadinessAnalyzer:
    """Compute readiness trend + recent days from garmin.db."""

    def __init__(self, db_dir: str):
        self._db_dir = db_dir

    def _query(self, sql: str, params: Sequence = ()) -> List[tuple]:
        path = os.path.join(self._db_dir, "garmin.db")
        if not os.path.exists(path):
            return []
        try:
            con = sqlite3.connect(path)
            try:
                return con.execute(sql, params).fetchall()
            finally:
                con.close()
        except sqlite3.Error as e:
            logger.warning("Readiness query failed: %s", e)
            return []

    def analyze(self, start_date: date, end_date: date) -> "TrainingReadinessResult":
        rows = self._query(
            "SELECT day, score, level, recovery_time, feedback_short "
            "FROM training_readiness "
            "WHERE date(day) >= ? AND date(day) <= ? AND score IS NOT NULL "
            "ORDER BY day DESC",
            (start_date.isoformat(), end_date.isoformat()),
        )
        days: List[ReadinessDay] = []
        for day, score, level, recovery_time, feedback_short in rows:
            d = _parse_day(day)
            if d is None:
                continue
            days.append(ReadinessDay(
                day=d, score=int(score), level=level or "",
                recovery_time=int(recovery_time) if recovery_time is not None else None,
                feedback_short=feedback_short or ""))
        return TrainingReadinessResult(
            period_start=start_date, period_end=end_date,
            recent_days=days[:RECENT_DAYS],
            monthly_score=_monthly_mean(days, start_date, end_date),
            day_count=len(days),
        )


def _parse_day(value) -> Optional[date]:
    if value is None:
        return None
    text = str(value).strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _monthly_mean(days: List[ReadinessDay], start: date, end: date):
    buckets = {}
    for d in days:
        buckets.setdefault(f"{d.day.year:04d}-{d.day.month:02d}", []).append(d.score)
    keys = []
    y, m = start.year, start.month
    while (y, m) <= (end.year, end.month):
        keys.append(f"{y:04d}-{m:02d}")
        m += 1
        if m > 12:
            m, y = 1, y + 1
    return [(k, round(sum(buckets[k]) / len(buckets[k]), 1) if k in buckets else None)
            for k in keys]
