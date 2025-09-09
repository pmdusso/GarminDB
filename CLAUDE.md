# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Essential Commands

### Build and Setup
```bash
# Initial setup from source (creates venv, installs dependencies)
make setup

# Install all dependencies including submodules
make install_all

# Clean and rebuild virtual environment
make clean_venv && make setup
```

### Running Tests
```bash
# Run all tests
make -C test all

# Run specific test category
make -C test garmin_db       # Database tests
make -C test activities_db   # Activities database tests
make -C test fit_file        # FIT file parsing tests

# Run individual test file
python test/test_garmin_db.py

# Run specific test method
python -m unittest -v test_garmin_db.TestGarminDb.test_function_name
```

### Code Quality
```bash
# Run linting (MUST pass before submitting PRs)
make flake8

# Check build before publishing
make publish_check
```

### Database Operations
```bash
# Create all databases from downloaded data
make create_dbs

# Rebuild databases (preserves downloaded files)
make rebuild_dbs

# Update databases with latest data
make update_dbs

# Check database integrity
sqlite3 ~/HealthData/DBs/garmin.db "PRAGMA integrity_check;"
```

### Main CLI Operations
```bash
# Full initial download and import
garmindb_cli.py --all --download --import --analyze

# Incremental update (most common operation)
garmindb_cli.py --all --download --import --analyze --latest

# Rebuild database from existing files
garmindb_cli.py --rebuild_db

# Generate bug report for debugging
garmindb_bug_report.py
```

## Architecture Overview

### Core Data Flow
1. **Download/Copy** → Raw files stored in `~/HealthData/FitFiles/[Year]/`
2. **Parse** → FIT/TCX/JSON processors extract structured data
3. **Import** → Data stored in SQLite databases in `~/HealthData/DBs/`
4. **Analyze** → Generate summaries and statistics

### Database Architecture
The system uses multiple specialized SQLite databases:
- **garmin.db**: Core data (devices, sleep, weight, RHR)
- **garmin_activities.db**: Detailed activity records with laps and records
- **garmin_monitoring.db**: Continuous monitoring (HR, steps, intensity)
- **garmin_summary.db**: Aggregated statistics

All database models use SQLAlchemy ORM and track schema versions for automatic migration.

### Plugin System
Plugins extend FIT file processing capabilities:
- Located in `Plugins/` directory
- Inherit from `ActivityFitPluginBase` or `MonitoringFitPluginBase`
- Loaded dynamically by `PluginManager`
- Can add custom database tables and processing logic

### Authentication Flow
Uses `garth` library with session caching:
1. Credentials read from `~/.GarminDb/GarminConnectConfig.json`
2. Session cached in `~/.GarminDb/garth_session.json`
3. Auto-refreshes expired sessions

## Key Development Patterns

### Adding New Data Types
1. Define database model in appropriate `garmindb/*_db.py`
2. Create processor class inheriting from base processor
3. Add import logic to `garmindb_cli.py`
4. Update `Statistics` enum if needed
5. Add tests in `test/` directory

### FIT File Processing
- Base processor: `FitFileProcessor`
- Activity-specific: `ActivityFitFileProcessor`
- Monitoring-specific: `MonitoringFitFileProcessor`
- Each processor handles specific FIT message types

### Database Conventions
- All tables have `table_version` for migrations
- Use `s_get_from_dict()` for session-based queries
- Views created with `create_view()` methods
- Primary keys typically use composite keys for time-series data

## Configuration

Main config file: `~/.GarminDb/GarminConnectConfig.json`

Critical settings:
- `credentials.user/password`: Garmin Connect login
- `data.*_start_date`: Historical data download dates
- `enabled_stats`: Toggle data types to process
- `directories.mount_dir`: USB device mount point for direct copy

## Important Files and Locations

- **Main CLI entry**: `scripts/garmindb_cli.py`
- **Core download logic**: `garmindb/download.py`
- **Database definitions**: `garmindb/garmindb/*.py`
- **FIT processors**: `garmindb/*_fit_file_processor.py`
- **Test data**: `test/test_files/`
- **Downloaded data**: `~/HealthData/FitFiles/`
- **Databases**: `~/HealthData/DBs/`
- **Logs**: `garmindb.log` in working directory

## Testing Considerations

- Test files in `test/test_files/` contain sample FIT, TCX, and JSON data
- Database tests create temporary databases
- Use `make -C test verify_commit` before commits
- All new functionality requires tests

## Common Issues

### Authentication Failures
Delete session file to force re-login:
```bash
rm ~/.GarminDb/garth_session.json
```

### Database Version Mismatch
Rebuild after code updates:
```bash
garmindb_cli.py --rebuild_db
```

### Missing Submodules
```bash
git submodule init
git submodule update
```

## Development Workflow

1. All changes go to `develop` branch, not `master`
2. Run `make flake8` before committing
3. Add yourself to `contributors.txt`
4. Use existing code patterns and conventions
5. Preserve backward compatibility with database schemas

## Notes

- The project uses submodules (Fit, Tcx, utilities) that must be initialized
- Database operations are atomic - use transactions for consistency
- FIT file parsing is binary - use the fitfile submodule, don't parse manually
- All timestamps are UTC in the database
- The system preserves downloaded files to allow database rebuilds without re-downloading