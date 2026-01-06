
import sys
import os
from datetime import date, timedelta, datetime

# Ensure garmindb is in the path
sys.path.append(os.getcwd())

from garmindb.data.repositories.sqlite import SQLiteHealthRepository
from garmindb.analysis.health_analyzer import HealthAnalyzer
from garmindb.presentation.markdown.renderer import MarkdownPresenter
from garmindb.garmin_connect_config_manager import GarminConnectConfigManager

def main():
    config = GarminConnectConfigManager()
    db_params = config.get_db_params()
    repository = SQLiteHealthRepository(db_params)
    
    # Analyze Q4 2025
    start_date = date(2025, 10, 1)
    end_date = date(2025, 12, 31)
    
    print(f"--- Recomputing Full Health Report for Q4 2025 ({start_date} to {end_date}) ---")
    analyzer = HealthAnalyzer(repository)
    report = analyzer.generate_report(start_date, end_date)
    
    presenter = MarkdownPresenter()
    markdown = presenter.render_report(report)
    
    # Save results to a new file to compare
    output_path = "docs/relatorio-q4-2025-REBUILT.md"
    with open(output_path, "w") as f:
        f.write(markdown)
    
    print(f"✅ Rebuilt report saved to {output_path}")

    # Display some key improvements
    if report.recovery:
        print("\n--- Recovery Analysis Improvements ---")
        print(f"Recovery Score: {report.recovery.recovery_score}/100")
        bb_sum = report.recovery.body_battery_summary
        print(f"BB Recharge Avg (Period): {bb_sum.current_value:.1f}%")
        print(f"BB Recharge Avg (Last 7d): {bb_sum.average_7d if bb_sum.average_7d else '---'}%")
        print(f"High Recovery Days: {report.recovery.high_recovery_days}")
        print(f"Low Recovery Days: {report.recovery.low_recovery_days}")

    if report.activities and report.activities.training_stress:
        print("\n--- Training Stress Consistency ---")
        ts = report.activities.training_stress
        print(f"TSB Confidence Score: {ts.confidence_score:.2f}")

if __name__ == "__main__":
    main()
