"""Integration tests for complete report generation flow."""

import unittest
import tempfile
import os


class TestFullReportGeneration(unittest.TestCase):
    """Test complete flow: Data → Analysis → Presentation."""

    @classmethod
    def setUpClass(cls):
        """Set up for integration tests."""
        from garmindb import GarminConnectConfigManager
        from garmindb.data.repositories import SQLiteHealthRepository
        from garmindb.analysis import HealthAnalyzer
        from garmindb.presentation import MarkdownPresenter

        gc_config = GarminConnectConfigManager()
        db_params = gc_config.get_db_params()

        cls.repository = SQLiteHealthRepository(db_params)
        cls.analyzer = HealthAnalyzer(cls.repository)
        cls.presenter = MarkdownPresenter()

    def test_full_weekly_report_flow(self):
        """Test generating and rendering a weekly report."""
        # Generate report
        report = self.analyzer.weekly_report()

        # Render to markdown
        markdown = self.presenter.render_report(report)

        # Validate output
        self.assertIsInstance(markdown, str)
        self.assertIn("Health Report", markdown)
        self.assertIn("Sleep Analysis", markdown)

        # Check structure
        self.assertIn("---", markdown)  # Has metadata
        self.assertIn("| Metric |", markdown)  # Has table

    def test_report_can_be_saved_to_file(self):
        """Test that report can be written to file."""
        report = self.analyzer.weekly_report()
        markdown = self.presenter.render_report(report)

        with tempfile.NamedTemporaryFile(
            mode='w', suffix='.md', delete=False
        ) as f:
            f.write(markdown)
            temp_path = f.name

        try:
            self.assertTrue(os.path.exists(temp_path))
            with open(temp_path, 'r') as f:
                content = f.read()
            self.assertEqual(content, markdown)
        finally:
            os.unlink(temp_path)

    def test_monthly_report_has_more_data(self):
        """Test that monthly report covers more data than weekly."""
        weekly = self.analyzer.weekly_report()
        monthly = self.analyzer.monthly_report()

        weekly_days = (weekly.period_end - weekly.period_start).days
        monthly_days = (monthly.period_end - monthly.period_start).days

        self.assertGreater(monthly_days, weekly_days)

    def test_report_metadata_is_llm_friendly(self):
        """Test that report has LLM-friendly YAML frontmatter."""
        report = self.analyzer.weekly_report()
        markdown = self.presenter.render_report(report)

        # Check YAML frontmatter structure
        self.assertTrue(markdown.startswith("---"))
        self.assertIn("report_type: health_analysis", markdown)
        self.assertIn("data_source: garmin_connect", markdown)
        self.assertIn("format_version:", markdown)


if __name__ == "__main__":
    unittest.main()
