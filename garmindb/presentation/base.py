"""Base presenter interface."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from garmindb.analysis.models import SleepAnalysisResult, HealthReport


class Presenter(ABC):
    """Abstract base for all presenters."""

    @abstractmethod
    def render_sleep(self, result: "SleepAnalysisResult") -> str:
        """Render sleep analysis."""
        pass

    @abstractmethod
    def render_report(self, report: "HealthReport") -> str:
        """Render complete health report."""
        pass
