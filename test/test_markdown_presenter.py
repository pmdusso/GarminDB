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


    def test_training_readiness_section_renders(self):
        from datetime import date
        from garmindb.analysis.readiness_analyzer import (
            TrainingReadinessResult, ReadinessDay)
        from garmindb.presentation.markdown.longitudinal_renderer import LongitudinalPresenter

        tr = TrainingReadinessResult(
            period_start=date(2026, 6, 1), period_end=date(2026, 6, 30),
            recent_days=[ReadinessDay(date(2026, 6, 22), 69, 'MODERATE', 101, 'RECOVERED_AND_READY')],
            monthly_score=[('2026-06', 69.0)], day_count=1)
        out = LongitudinalPresenter()._training_readiness(type('R', (), {'training_readiness': tr})())
        self.assertIn('Training Readiness', out)
        self.assertIn('69', out)
        self.assertIn('101', out)

    def test_training_readiness_recovery_time_none_renders_dash(self):
        from datetime import date
        from garmindb.analysis.readiness_analyzer import (
            TrainingReadinessResult, ReadinessDay)
        from garmindb.presentation.markdown.longitudinal_renderer import LongitudinalPresenter

        tr = TrainingReadinessResult(
            period_start=date(2026, 6, 1), period_end=date(2026, 6, 30),
            recent_days=[ReadinessDay(date(2026, 6, 22), 69, 'MODERATE', None, 'RECOVERED_AND_READY')],
            monthly_score=[('2026-06', 69.0)], day_count=1)
        out = LongitudinalPresenter()._training_readiness(type('R', (), {'training_readiness': tr})())
        self.assertIn('—', out)

    def test_training_readiness_section_suppressed_when_empty(self):
        from garmindb.presentation.markdown.longitudinal_renderer import LongitudinalPresenter
        out = LongitudinalPresenter()._training_readiness(type('R', (), {'training_readiness': None})())
        self.assertEqual(out, '')

    def test_training_readiness_section_suppressed_when_day_count_zero(self):
        from garmindb.analysis.readiness_analyzer import TrainingReadinessResult
        from garmindb.presentation.markdown.longitudinal_renderer import LongitudinalPresenter
        from datetime import date
        tr = TrainingReadinessResult(
            period_start=date(2026, 6, 1), period_end=date(2026, 6, 30),
            recent_days=[], monthly_score=[], day_count=0)
        out = LongitudinalPresenter()._training_readiness(type('R', (), {'training_readiness': tr})())
        self.assertEqual(out, '')


if __name__ == "__main__":
    unittest.main()
