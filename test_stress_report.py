
import sys
import os
from datetime import date, timedelta, datetime

# Ensure garmindb is in the path
sys.path.append(os.getcwd())

from garmindb.data.repositories.sqlite import SQLiteHealthRepository
from garmindb.analysis.stress_analyzer import StressAnalyzer
from garmindb.analysis.health_analyzer import HealthAnalyzer
from garmindb.presentation.markdown.renderer import MarkdownPresenter
from garmindb.garmin_connect_config_manager import GarminConnectConfigManager

def main():
    config = GarminConnectConfigManager()
    db_params = config.get_db_params()
    repository = SQLiteHealthRepository(db_params)
    
    analyzer = StressAnalyzer(repository)
    
    # Analyze last 7 days (ending Jan 4)
    end_date = date(2026, 1, 4)
    start_date = end_date - timedelta(days=7)
    
    print(f"--- Running Stress Analysis for {start_date} to {end_date} ---")
    result = analyzer.analyze(start_date, end_date)
    
    print(f"Average Stress: {result.avg_stress.current_value}")
    print(f"Personal Baseline: {result.personal_baseline:.1f}")
    
    if result.stress_load:
        print(f"Total Stress Load: {result.stress_load.total_load:.0f} pts")
        print(f"Avg Intensity: {result.stress_load.avg_intensity:.1f}")
        if result.stress_load.peak_load_hour:
            print(f"Peak Load Hour: {result.stress_load.peak_load_hour.strftime('%H:%M')}")
    
    print(f"\nDistribution:")
    print(f"- Low: {result.low_stress_percent}%")
    print(f"- Medium: {result.medium_stress_percent}%")
    print(f"- High: {result.high_stress_percent}%")
    
    if result.recovery_efficiency is not None:
        print(f"\nRecovery Efficiency: {result.recovery_efficiency:.0f}/100")
        print(f"Avg Recovery Time: {result.avg_recovery_time_minutes:.1f} min")
        print(f"Post-Activity Patterns analyzed: {len(result.post_activity_patterns)}")

    print(f"\nInsights count: {len(result.insights)}")
    for insight in result.insights:
        print(f"[{insight.severity.value.upper()}] {insight.title}: {insight.description}")

    # Test Markdown Rendering
    print("\n--- Testing Markdown Rendering ---")
    presenter = MarkdownPresenter()
    report = HealthAnalyzer(repository).generate_report(start_date, end_date)
    markdown = presenter.render_report(report)
    
    # Check if Stress section exists in markdown
    if "## Stress Analysis" in markdown:
        print("✅ MarkdownPresenter integration confirmed.")
        # Print a snippet of the stress section
        start_idx = markdown.find("## Stress Analysis")
        end_idx = markdown.find("##", start_idx + 1)
        print(markdown[start_idx:end_idx if end_idx != -1 else len(markdown)])
    else:
        print("❌ MarkdownPresenter integration missing '## Stress Analysis' section.")

if __name__ == "__main__":
    main()
