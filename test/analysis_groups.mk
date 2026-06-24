# Analysis / report pytest suite, classified by what the CI runner provides.
#
# Run per-file (NOT a single pytest process): two modules named models.py
# (garmindb/analysis/models.py and garmindb/data/models.py) are imported via a
# sys.path hack in test_data_models.py / test_markdown_presenter.py, which
# collides in a combined collection (ImportError: cannot import name ...).
#
# CI environment (verified 2026-06-11): `make setup_repo` copies
# garmindb/GarminConnectConfig.json.example to ~/.GarminDb/GarminConnectConfig.json,
# so the config FILE exists, but there is no real ~/HealthData data. Every test
# below was confirmed to pass in that environment AND against the maintainer's
# real config+data. Two tiers exist (both CI-safe, hence both in ANALYSIS_SAFE):
#   * fully hermetic  -> pass even with no config at all (use fakes/in-memory).
#   * config-coupled  -> call GarminConnectConfigManager(); the example config
#     satisfies them (they query empty/real DBs and assert on report structure,
#     not data values): recovery/sleep/stress/health analyzers, sqlite_repository,
#     integration.
#
# An earlier draft classified against an EMPTY HOME, which wrongly flagged the
# six config-coupled tests as needing a "real DB"; CI provides the example
# config, so they run fine.

# All analysis tests that pass in CI (example config, no real data). Wired into
# all + verify_commit.
ANALYSIS_SAFE=test_activity_analyzer test_recovery_analyzer test_sleep_analyzer \
  test_stress_analyzer test_health_analyzer test_power_analyzer test_power_analyzer_analyze \
  test_power_analyzer_phase1 test_decoupling_analyzer test_performance_report \
  test_performance_renderer test_performance_targets test_performance_cli_smoke \
  test_performance_power_phase1 test_longitudinal_report test_longitudinal_clinical \
  test_longitudinal_power_phase1 test_markdown_presenter test_report_state \
  test_repositories test_sqlite_repository test_data_models test_db_metrics \
  test_integration test_weight_series test_download_auth_adapter \
  test_garmin_connect_auth_adapter test_power_import_phase2_sp1 \
  test_readiness_analyzer test_training_readiness_db test_training_readiness_download \
  test_training_readiness_import test_training_readiness_cli_smoke

# Reserved for tests that require REAL downloaded data (~/HealthData DBs the CI
# runner does not have). None currently -- the example config + empty DBs satisfy
# every analysis test. Add here (and they stay out of verify_commit/CI) if a
# future test asserts on specific real data. Run with `make -C test analysis_manual`.
ANALYSIS_MANUAL=
