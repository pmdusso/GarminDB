
import sys
import os
from datetime import date, timedelta, datetime

# Ensure garmindb is in the path
sys.path.append(os.getcwd())

from garmindb.data.repositories.sqlite import SQLiteHealthRepository
from garmindb.analysis.activity_analyzer import ActivityAnalyzer
from garmindb.analysis.health_analyzer import HealthAnalyzer
from garmindb.presentation.markdown.renderer import MarkdownPresenter
from garmindb.garmin_connect_config_manager import GarminConnectConfigManager

def main():
    config = GarminConnectConfigManager()
    db_params = config.get_db_params()
    repository = SQLiteHealthRepository(db_params)
    
    analyzer = ActivityAnalyzer(repository)
    
    # Analyze last 7 days (ending Jan 4)
    end_date = date(2026, 1, 4)
    start_date = end_date - timedelta(days=6)
    
    print(f"--- Running Activity Analysis for {start_date} to {end_date} ---")
    result = analyzer.analyze(start_date, end_date)
    
    print(f"Total Activities: {result.total_activities}")
    print(f"Total Distance: {result.total_distance_km:.1f} km")
    
    if result.training_stress:
        ts = result.training_stress
        print(f"\nTraining Load:")
        print(f"- Fitness (CTL): {ts.ctl:.1f}")
        print(f"- Fatigue (ATL): {ts.atl:.1f}")
        print(f"- Form (TSB): {ts.tsb:.1f}")
        print(f"- Monotony: {ts.monotony}")
        print(f"- Confidence: {ts.confidence_score:.2f}")
    
    print(f"\nIntensity Distribution:")
    for cat, pct in result.intensity_distribution.items():
        print(f"- {cat}: {pct}%")
    
    print(f"\nBy Sport:")
    for sport, summary in result.sport_summaries.items():
        eff = f"{summary.efficiency_index:.1f}" if summary.efficiency_index else "N/A"
        print(f"- {sport}: {summary.count} acts, {summary.total_distance_km} km, Eff: {eff}")

    print(f"\nInsights count: {len(result.insights)}")
    for insight in result.insights:
        print(f"[{insight.severity.value.upper()}] {insight.title}: {insight.description}")

    # Test Markdown Rendering
    print("\n--- Testing Markdown Rendering ---")
    presenter = MarkdownPresenter()
    report = HealthAnalyzer(repository).generate_report(start_date, end_date)
    markdown = presenter.render_report(report)
    
    if "## Activity Summary" in markdown:
        print("✅ MarkdownPresenter integration confirmed.")
        # Print the activity summary section
        start_idx = markdown.find("## Activity Summary")
        end_idx = markdown.find("## Key Insights", start_idx + 1)
        print(markdown[start_idx:end_idx if end_idx != -1 else len(markdown)])
    else:
        print("❌ MarkdownPresenter integration missing '## Activity Summary' section.")

if __name__ == "__main__":
    main()
