
import sys
import os
from datetime import date, timedelta

# Ensure garmindb is in the path
sys.path.append(os.getcwd())

from garmindb.data.repositories.sqlite import SQLiteHealthRepository
from garmindb.analysis.recovery_analyzer import RecoveryAnalyzer
from garmindb.analysis.health_analyzer import HealthAnalyzer
from garmindb.presentation.markdown.renderer import MarkdownPresenter
from garmindb.garmin_connect_config_manager import GarminConnectConfigManager

def main():
    config = GarminConnectConfigManager()
    db_params = config.get_db_params()
    repository = SQLiteHealthRepository(db_params)
    
    analyzer = RecoveryAnalyzer(repository)
    
    # Analyze last 7 days (ending today Jan 4)
    end_date = date(2026, 1, 4)
    start_date = end_date - timedelta(days=7)
    
    print(f"--- Running Recovery Analysis for {start_date} to {end_date} ---")
    result = analyzer.analyze(start_date, end_date)
    
    print(f"Recovery Score: {result.recovery_score}")
    print(f"Recovery Trend: {result.recovery_trend.value}")
    print(f"RHR Baseline: {result.rhr_baseline:.1f} bpm")
    print(f"RHR Current Avg: {result.rhr_summary.current_value:.1f} bpm")
    print(f"RHR Deviation: {result.rhr_deviation:.1f} bpm")
    print(f"ACWR: {result.acute_chronic_ratio}")
    print(f"Insights count: {len(result.insights)}")
    
    for insight in result.insights:
        print(f"[{insight.severity.value.upper()}] {insight.title}: {insight.description}")

    print("\n--- Testing Daily Readiness for Jan 4 ---")
    readiness = analyzer.daily_readiness(end_date)
    print(f"Readiness Score: {readiness.readiness_score}")
    print(f"Recovery Score (Daily): {readiness.recovery_score}")
    print(f"Recommended Intensity: {readiness.recommended_intensity}")

if __name__ == "__main__":
    main()
