#!/usr/bin/env python3
"""Generate health reports from command line.

Usage:
    python scripts/generate_report.py --period weekly
    python scripts/generate_report.py --period daily --output report.md
    python scripts/generate_report.py --start 2025-01-01 --end 2025-01-15
"""

import argparse
from datetime import date, datetime
from pathlib import Path


def parse_date(date_str: str) -> date:
    """Parse date string in YYYY-MM-DD format."""
    return datetime.strptime(date_str, "%Y-%m-%d").date()


def main():
    parser = argparse.ArgumentParser(
        description="Generate health reports from GarminDB"
    )
    parser.add_argument(
        "--period",
        choices=["daily", "weekly", "monthly"],
        default="weekly",
        help="Report period (default: weekly)",
    )
    parser.add_argument(
        "--start",
        type=parse_date,
        help="Start date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--end",
        type=parse_date,
        help="End date (YYYY-MM-DD)",
    )
    parser.add_argument(
        "--output",
        "-o",
        type=Path,
        help="Output file path (default: stdout)",
    )
    parser.add_argument(
        "--no-metadata",
        action="store_true",
        help="Exclude YAML frontmatter",
    )
    parser.add_argument(
        "--performance",
        action="store_true",
        help="Generate the performance report (power/W-kg/TSB/recovery)",
    )

    args = parser.parse_args()

    # Import here to avoid slow startup for --help
    from garmindb import GarminConnectConfigManager

    gc_config = GarminConnectConfigManager()
    db_params = gc_config.get_db_params()

    if args.performance:
        import os
        from datetime import datetime as _dt
        from datetime import timedelta as _td
        from garmindb.data.repositories import SQLiteHealthRepository
        from garmindb.analysis.performance_targets import load_performance_targets
        from garmindb.analysis.performance_report import PerformanceReportBuilder
        from garmindb.analysis.report_state import (
            load_last_metrics, save_metrics, merge_metrics,
        )
        from garmindb.presentation.markdown.performance_renderer import PerformancePresenter

        db_dir = db_params.db_path
        activities_dir = os.path.join(
            os.path.dirname(db_dir), "FitFiles", "Activities"
        )
        state_path = os.path.join(
            os.path.dirname(db_dir), "reports", "last_metrics.json"
        )

        end = args.end or date.today()
        start = args.start or (end - _td(days=30))
        generated = _dt(end.year, end.month, end.day, 12, 0, 0)

        repository = SQLiteHealthRepository(db_params)
        targets = load_performance_targets()
        last = load_last_metrics(state_path)

        builder = PerformanceReportBuilder(
            repository=repository, db_dir=db_dir, activities_dir=activities_dir,
            targets=targets, last_metrics=last,
        )
        report = builder.build(start, end, generated)
        # Merge onto the previous state so a metric absent this run carries its
        # last-known value forward instead of destroying the baseline.
        merged = merge_metrics(last, report.metric_snapshot)
        save_metrics(state_path, merged, generated.isoformat())
        markdown = PerformancePresenter(
            include_metadata=not args.no_metadata
        ).render(report)
    else:
        from garmindb.data.repositories import SQLiteHealthRepository
        from garmindb.analysis import HealthAnalyzer
        from garmindb.presentation import MarkdownPresenter

        repository = SQLiteHealthRepository(db_params)
        analyzer = HealthAnalyzer(repository)
        presenter = MarkdownPresenter(include_metadata=not args.no_metadata)
        if args.start and args.end:
            report = analyzer.generate_report(args.start, args.end)
        elif args.period == "daily":
            report = analyzer.daily_report()
        elif args.period == "monthly":
            report = analyzer.monthly_report()
        else:
            report = analyzer.weekly_report()
        markdown = presenter.render_report(report)

    # Output
    if args.output:
        args.output.write_text(markdown)
        print(f"Report saved to: {args.output}")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
