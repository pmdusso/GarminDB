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

    args = parser.parse_args()

    # Import here to avoid slow startup for --help
    from garmindb import GarminConnectConfigManager
    from garmindb.data.repositories import SQLiteHealthRepository
    from garmindb.analysis import HealthAnalyzer
    from garmindb.presentation import MarkdownPresenter

    # Setup
    gc_config = GarminConnectConfigManager()
    db_params = gc_config.get_db_params()
    repository = SQLiteHealthRepository(db_params)
    analyzer = HealthAnalyzer(repository)
    presenter = MarkdownPresenter(include_metadata=not args.no_metadata)

    # Generate report
    if args.start and args.end:
        report = analyzer.generate_report(args.start, args.end)
    elif args.period == "daily":
        report = analyzer.daily_report()
    elif args.period == "monthly":
        report = analyzer.monthly_report()
    else:
        report = analyzer.weekly_report()

    # Render
    markdown = presenter.render_report(report)

    # Output
    if args.output:
        args.output.write_text(markdown)
        print(f"Report saved to: {args.output}")
    else:
        print(markdown)


if __name__ == "__main__":
    main()
