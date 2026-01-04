"""SQLite implementation of HealthRepository using GarminDB.

This module provides a concrete implementation of the HealthRepository
interface that wraps the existing GarminDB SQLAlchemy models. It serves
as an adapter between the new layered architecture and the existing
database access layer.
"""

__author__ = "Tom Goetz"
__copyright__ = "Copyright Tom Goetz"
__license__ = "GPL"

from datetime import date, datetime, timedelta, time as dt_time
from typing import List, Optional

from .base import HealthRepository
from ..models import (
    SleepRecord,
    HeartRateRecord,
    StressRecord,
    BodyBatteryRecord,
    ActivityRecord,
    DailySummaryRecord,
)


class SQLiteHealthRepository(HealthRepository):
    """SQLite implementation using existing GarminDB models.

    This repository implementation wraps the existing GarminDB SQLAlchemy
    models and provides data access through the HealthRepository interface.
    Database connections are lazy-loaded to avoid opening connections until
    they are actually needed.

    Attributes:
        db_params: Dictionary containing database connection parameters
            as returned by GarminConnectConfigManager.get_db_params()
    """

    def __init__(self, db_params: dict):
        """Initialize repository with database parameters.

        Args:
            db_params: Database connection parameters dict containing
                db_path and other connection settings.
        """
        self.db_params = db_params
        self._garmin_db = None
        self._activities_db = None
        self._monitoring_db = None
        self._summary_db = None

    @property
    def garmin_db(self):
        """Lazy-load GarminDb connection.

        Returns:
            GarminDb instance for accessing core health data.
        """
        if self._garmin_db is None:
            from garmindb.garmindb import GarminDb
            self._garmin_db = GarminDb(self.db_params)
        return self._garmin_db

    @property
    def activities_db(self):
        """Lazy-load ActivitiesDb connection.

        Returns:
            ActivitiesDb instance for accessing activity data.
        """
        if self._activities_db is None:
            from garmindb.garmindb import ActivitiesDb
            self._activities_db = ActivitiesDb(self.db_params)
        return self._activities_db

    @property
    def monitoring_db(self):
        """Lazy-load MonitoringDb connection.

        Returns:
            MonitoringDb instance for accessing monitoring data.
        """
        if self._monitoring_db is None:
            from garmindb.garmindb import MonitoringDb
            self._monitoring_db = MonitoringDb(self.db_params)
        return self._monitoring_db

    @property
    def summary_db(self):
        """Lazy-load SummaryDb connection.

        Returns:
            SummaryDb instance for accessing summary data.
        """
        if self._summary_db is None:
            from garmindb.summarydb import SummaryDb
            self._summary_db = SummaryDb(self.db_params, False)
        return self._summary_db

    def _to_datetime(self, d: date) -> datetime:
        """Convert date to datetime for queries.

        Args:
            d: Date to convert

        Returns:
            Datetime at start of the given date (00:00:00)
        """
        return datetime.combine(d, datetime.min.time())

    def _to_datetime_end(self, d: date) -> datetime:
        """Convert date to end-of-day datetime for queries.

        Args:
            d: Date to convert

        Returns:
            Datetime at end of the given date (23:59:59.999999)
        """
        return datetime.combine(d, datetime.max.time())

    def _time_to_timedelta(self, t: Optional[dt_time]) -> timedelta:
        """Convert time object to timedelta.

        Args:
            t: Time object to convert, or None

        Returns:
            Timedelta representing the same duration, or zero if None
        """
        if t is None:
            return timedelta(0)
        return timedelta(
            hours=t.hour, minutes=t.minute, seconds=t.second
        )

    def get_sleep_data(
        self, start_date: date, end_date: date
    ) -> List[SleepRecord]:
        """Get sleep records from GarminDB.Sleep table.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of SleepRecord DTOs ordered by date
        """
        from garmindb.garmindb import Sleep

        start_ts = self._to_datetime(start_date)
        end_ts = self._to_datetime_end(end_date)

        raw_data = Sleep.get_for_period(self.garmin_db, start_ts, end_ts)

        records = []
        for row in raw_data:
            try:
                record = SleepRecord(
                    date=row.day,
                    total_sleep=self._time_to_timedelta(row.total_sleep),
                    deep_sleep=self._time_to_timedelta(row.deep_sleep),
                    light_sleep=self._time_to_timedelta(row.light_sleep),
                    rem_sleep=self._time_to_timedelta(row.rem_sleep),
                    awake_time=self._time_to_timedelta(row.awake),
                    sleep_score=getattr(row, 'score', None),
                )
                records.append(record)
            except Exception:
                # Skip malformed rows to ensure we return valid data
                continue

        return sorted(records, key=lambda r: r.date)

    def get_heart_rate_data(
        self,
        start_date: date,
        end_date: date,
        resting_only: bool = False
    ) -> List[HeartRateRecord]:
        """Get heart rate records.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            resting_only: If True, only return daily resting HR values.
                If False, return all monitoring HR data.

        Returns:
            List of HeartRateRecord DTOs ordered by timestamp
        """
        if resting_only:
            from garmindb.garmindb import RestingHeartRate

            start_ts = self._to_datetime(start_date)
            end_ts = self._to_datetime_end(end_date)

            raw_data = RestingHeartRate.get_for_period(
                self.garmin_db, start_ts, end_ts
            )

            records = []
            for row in raw_data:
                try:
                    rhr = row.resting_heart_rate
                    rhr = int(rhr) if rhr else None
                    if rhr is not None:
                        ts = datetime.combine(row.day, datetime.min.time())
                        record = HeartRateRecord(
                            timestamp=ts,
                            heart_rate=rhr,
                            resting_hr=rhr,
                        )
                        records.append(record)
                except Exception:
                    continue

            return sorted(records, key=lambda r: r.timestamp)
        else:
            from garmindb.garmindb import MonitoringHeartRate

            start_ts = self._to_datetime(start_date)
            end_ts = self._to_datetime_end(end_date)

            raw_data = MonitoringHeartRate.get_for_period(
                self.monitoring_db, start_ts, end_ts
            )

            records = []
            for row in raw_data:
                try:
                    record = HeartRateRecord(
                        timestamp=row.timestamp,
                        heart_rate=row.heart_rate,
                        resting_hr=None,
                    )
                    records.append(record)
                except Exception:
                    continue

            return sorted(records, key=lambda r: r.timestamp)

    def get_stress_data(
        self, start_date: date, end_date: date
    ) -> List[StressRecord]:
        """Get stress records from GarminDB.Stress table.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of StressRecord DTOs ordered by timestamp
        """
        from garmindb.garmindb import Stress

        start_ts = self._to_datetime(start_date)
        end_ts = self._to_datetime_end(end_date)

        raw_data = Stress.get_for_period(self.garmin_db, start_ts, end_ts)

        records = []
        for row in raw_data:
            try:
                if row.stress is not None:
                    record = StressRecord(
                        timestamp=row.timestamp,
                        stress_level=row.stress,
                    )
                    records.append(record)
            except Exception:
                continue

        return sorted(records, key=lambda r: r.timestamp)

    def get_body_battery_data(
        self, start_date: date, end_date: date
    ) -> List[BodyBatteryRecord]:
        """Get body battery records.

        Note: Body battery data is stored in the DailySummary table, not
        in the Stress table. This method queries daily summary data.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of BodyBatteryRecord DTOs ordered by timestamp
        """
        from garmindb.garmindb import DailySummary

        start_ts = self._to_datetime(start_date)
        end_ts = self._to_datetime_end(end_date)

        raw_data = DailySummary.get_for_period(
            self.garmin_db, start_ts, end_ts
        )

        records = []
        for row in raw_data:
            try:
                bb_max = getattr(row, 'bb_max', None)
                if bb_max is not None:
                    ts = datetime.combine(row.day, datetime.min.time())
                    record = BodyBatteryRecord(
                        timestamp=ts,
                        level=bb_max,
                        charged=getattr(row, 'bb_charged', None),
                        drained=None,
                    )
                    records.append(record)
            except Exception:
                continue

        return sorted(records, key=lambda r: r.timestamp)

    def get_activities(
        self,
        start_date: date,
        end_date: date,
        sport: Optional[str] = None
    ) -> List[ActivityRecord]:
        """Get activity records from ActivitiesDb.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            sport: Optional filter by sport type (case-insensitive match)

        Returns:
            List of ActivityRecord DTOs ordered by start_time
        """
        from garmindb.garmindb import Activities

        start_ts = self._to_datetime(start_date)
        end_ts = self._to_datetime_end(end_date)

        raw_data = Activities.get_for_period(
            self.activities_db, start_ts, end_ts
        )

        records = []
        for row in raw_data:
            try:
                row_sport = str(row.sport) if row.sport else ""

                # Apply sport filter if specified
                if sport and sport.lower() not in row_sport.lower():
                    continue

                # Calculate duration from elapsed_time or moving_time
                if row.elapsed_time:
                    duration = self._time_to_timedelta(row.elapsed_time)
                elif row.moving_time:
                    duration = self._time_to_timedelta(row.moving_time)
                else:
                    duration = timedelta(0)

                record = ActivityRecord(
                    activity_id=str(row.activity_id),
                    name=row.name,
                    sport=row_sport,
                    start_time=row.start_time,
                    duration=duration,
                    distance=row.distance,
                    calories=row.calories,
                    avg_hr=row.avg_hr,
                    max_hr=row.max_hr,
                    training_effect=row.training_effect,
                    anaerobic_effect=row.anaerobic_training_effect,
                    training_load=getattr(row, 'training_load', None),
                )
                records.append(record)
            except Exception:
                continue

        return sorted(records, key=lambda r: r.start_time)

    def get_daily_summaries(
        self, start_date: date, end_date: date
    ) -> List[DailySummaryRecord]:
        """Get daily summary records from SummaryDb.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of DailySummaryRecord DTOs ordered by date
        """
        from garmindb.summarydb import DaysSummary

        start_ts = self._to_datetime(start_date)
        end_ts = self._to_datetime_end(end_date)

        raw_data = DaysSummary.get_for_period(
            self.summary_db, start_ts, end_ts, DaysSummary
        )

        records = []
        for row in raw_data:
            try:
                # Convert sleep_avg from time to timedelta
                sleep_avg = None
                if hasattr(row, 'sleep_avg') and row.sleep_avg:
                    sleep_avg = self._time_to_timedelta(row.sleep_avg)

                # Convert intensity_time from time to minutes (int)
                intensity_mins = None
                if hasattr(row, 'intensity_time') and row.intensity_time:
                    intensity_td = self._time_to_timedelta(row.intensity_time)
                    intensity_mins = int(intensity_td.total_seconds() / 60)

                # Extract resting HR
                rhr_avg = getattr(row, 'rhr_avg', None)
                resting_hr = int(rhr_avg) if rhr_avg else None

                # Extract floors
                floors_val = getattr(row, 'floors', None)
                floors = int(floors_val) if floors_val else None

                record = DailySummaryRecord(
                    date=row.day,
                    resting_hr=resting_hr,
                    stress_avg=getattr(row, 'stress_avg', None),
                    bb_max=getattr(row, 'bb_max', None),
                    bb_min=getattr(row, 'bb_min', None),
                    bb_charged=getattr(row, 'bb_charged', None),
                    steps=getattr(row, 'steps', None),
                    floors=floors,
                    distance=getattr(row, 'activities_distance', None),
                    calories_active=getattr(row, 'calories_active_avg', None),
                    calories_total=getattr(row, 'calories_avg', None),
                    sleep_avg=sleep_avg,
                    intensity_mins=intensity_mins,
                )
                records.append(record)
            except Exception:
                continue

        return sorted(records, key=lambda r: r.date)
