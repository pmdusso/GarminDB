"""Abstract repository interface for health data access.

The Repository pattern decouples the analysis layer from
specific data storage implementations (SQLite, API, etc.).
"""

from abc import ABC, abstractmethod
from datetime import date
from typing import List, Optional, TYPE_CHECKING

# Use TYPE_CHECKING to avoid import issues when running tests in isolation
# while still having proper type hints available for IDEs and type checkers
if TYPE_CHECKING:
    from ..models import (
        SleepRecord,
        HeartRateRecord,
        StressRecord,
        BodyBatteryRecord,
        ActivityRecord,
        DailySummaryRecord,
    )


class HealthRepository(ABC):
    """Abstract interface for health data access.

    Implementations can wrap SQLite (GarminDB), REST APIs,
    or other data sources while providing a consistent interface.
    """

    @abstractmethod
    def get_sleep_data(
        self,
        start_date: date,
        end_date: date,
    ) -> List["SleepRecord"]:
        """Get sleep records for date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of SleepRecord DTOs ordered by date
        """
        pass

    @abstractmethod
    def get_heart_rate_data(
        self,
        start_date: date,
        end_date: date,
        resting_only: bool = False,
    ) -> List["HeartRateRecord"]:
        """Get heart rate records for date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            resting_only: If True, only return resting HR values

        Returns:
            List of HeartRateRecord DTOs ordered by timestamp
        """
        pass

    @abstractmethod
    def get_stress_data(
        self,
        start_date: date,
        end_date: date,
    ) -> List["StressRecord"]:
        """Get stress records for date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of StressRecord DTOs ordered by timestamp
        """
        pass

    @abstractmethod
    def get_body_battery_data(
        self,
        start_date: date,
        end_date: date,
    ) -> List["BodyBatteryRecord"]:
        """Get body battery records for date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of BodyBatteryRecord DTOs ordered by timestamp
        """
        pass

    @abstractmethod
    def get_activities(
        self,
        start_date: date,
        end_date: date,
        sport: Optional[str] = None,
    ) -> List["ActivityRecord"]:
        """Get activity records for date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)
            sport: Optional filter by sport type

        Returns:
            List of ActivityRecord DTOs ordered by start_time
        """
        pass

    @abstractmethod
    def get_daily_summaries(
        self,
        start_date: date,
        end_date: date,
    ) -> List["DailySummaryRecord"]:
        """Get daily summary records for date range.

        Args:
            start_date: Start of date range (inclusive)
            end_date: End of date range (inclusive)

        Returns:
            List of DailySummaryRecord DTOs ordered by date
        """
        pass
