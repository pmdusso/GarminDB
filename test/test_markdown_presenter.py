"""Tests for Markdown presenter."""

import os
import sys
import unittest
from datetime import date

# Add paths to avoid loading heavy garmindb dependencies
# We import directly from the module files rather than through __init__.py
_base = os.path.dirname(__file__)
_project_root = os.path.abspath(os.path.join(_base, '..'))

# Add paths for direct module imports (bypasses __init__.py chains)
sys.path.insert(0, os.path.join(_project_root, 'garmindb', 'analysis'))
sys.path.insert(0, os.path.join(_project_root, 'garmindb', 'presentation'))

from models import (  # noqa: E402
    SleepAnalysisResult,
    MetricSummary,
    TrendDirection,
    Insight,
    InsightSeverity,
)

# Import base directly to avoid relative import issues
from base import Presenter  # noqa: E402
from markdown.renderer import MarkdownPresenter  # noqa: E402


class TestMarkdownPresenter(unittest.TestCase):
    """Test MarkdownPresenter implementation."""

    def test_presenter_instantiation(self):
        """Test creating MarkdownPresenter."""
        presenter = MarkdownPresenter()
        self.assertIsNotNone(presenter)

    def test_presenter_is_subclass_of_base(self):
        """Test that MarkdownPresenter inherits from Presenter."""
        presenter = MarkdownPresenter()
        self.assertIsInstance(presenter, Presenter)

    def test_render_sleep_analysis(self):
        """Test rendering SleepAnalysisResult as markdown."""
        presenter = MarkdownPresenter()

        result = SleepAnalysisResult(
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 7),
            avg_total_sleep=MetricSummary(
                name="Total Sleep",
                current_value=7.5,
                unit="hours",
                average_7d=7.3,
                trend=TrendDirection.STABLE,
            ),
            avg_deep_sleep=MetricSummary(
                name="Deep Sleep",
                current_value=22.0,
                unit="%",
                average_7d=20.0,
                trend=TrendDirection.IMPROVING,
            ),
            avg_rem_sleep=MetricSummary(
                name="REM Sleep",
                current_value=25.0,
                unit="%",
                average_7d=23.0,
                trend=TrendDirection.STABLE,
            ),
            sleep_consistency_score=75.0,
        )

        markdown = presenter.render_sleep(result)

        self.assertIn("## Sleep Analysis", markdown)
        self.assertIn("7.5", markdown)
        self.assertIn("Total Sleep", markdown)

    def test_render_includes_insights(self):
        """Test that insights are rendered."""
        presenter = MarkdownPresenter()

        result = SleepAnalysisResult(
            period_start=date(2025, 1, 1),
            period_end=date(2025, 1, 7),
            avg_total_sleep=MetricSummary(
                name="", current_value=6.0, unit="hours"
            ),
            avg_deep_sleep=MetricSummary(
                name="", current_value=15.0, unit="%"
            ),
            avg_rem_sleep=MetricSummary(name="", current_value=20.0, unit="%"),
            sleep_consistency_score=50.0,
            insights=[
                Insight(
                    title="Sleep Debt Detected",
                    description="Average sleep is below recommended.",
                    severity=InsightSeverity.WARNING,
                    category="sleep",
                    recommendations=["Go to bed earlier"],
                )
            ],
        )

        markdown = presenter.render_sleep(result)

        self.assertIn("Sleep Debt Detected", markdown)
        self.assertIn("Go to bed earlier", markdown)


if __name__ == "__main__":
    unittest.main()
