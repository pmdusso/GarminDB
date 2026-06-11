# Analysis / report pytest suite, classified by hermeticity.
#
# Run per-file (NOT a single pytest process): two modules named models.py
# (garmindb/analysis/models.py and garmindb/data/models.py) are imported via a
# sys.path hack in test_data_models.py / test_markdown_presenter.py, which
# collides in a combined collection (ImportError: cannot import name ...).
#
# Classification verified empirically 2026-06-11 by running each file under an
# empty HOME (no ~/.GarminDb/GarminConnectConfig.json, no ~/HealthData/ DBs):
#   SAFE   -> passed clean  -> CI / verify_commit
#   MANUAL -> errored at setup building GarminConnectConfigManager (needs real
#             ~/.GarminDb config) -> excluded from CI, run on demand.

# Hermetic: no real config or DB. Wired into all + verify_commit (CI).
ANALYSIS_SAFE=test_activity_analyzer test_power_analyzer test_power_analyzer_analyze \
  test_power_analyzer_phase1 test_decoupling_analyzer test_performance_report \
  test_performance_renderer test_performance_targets test_performance_cli_smoke \
  test_performance_power_phase1 test_longitudinal_report test_longitudinal_clinical \
  test_longitudinal_power_phase1 test_markdown_presenter test_report_state \
  test_repositories test_data_models test_db_metrics test_weight_series \
  test_download_auth_adapter test_garmin_connect_auth_adapter test_power_import_phase2_sp1

# Needs real ~/.GarminDb config (GarminConnectConfigManager at setup) and/or DBs.
# Kept OUT of verify_commit / CI; run manually with `make -C test analysis_manual`.
ANALYSIS_MANUAL=test_recovery_analyzer test_sleep_analyzer test_stress_analyzer \
  test_health_analyzer test_sqlite_repository test_integration
