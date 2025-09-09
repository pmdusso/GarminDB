# GarminDB - Comprehensive Documentation for AI Agents

## Table of Contents
1. [Project Overview](#project-overview)
2. [Architecture & Components](#architecture--components)
3. [Installation & Setup](#installation--setup)
4. [Database Schema](#database-schema)
5. [Core Functionality](#core-functionality)
6. [CLI Commands](#cli-commands)
7. [Configuration](#configuration)
8. [Data Flow](#data-flow)
9. [Plugin System](#plugin-system)
10. [Testing](#testing)
11. [Development Guide](#development-guide)

## Project Overview

### Purpose
GarminDB is a Python-based system for downloading, storing, and analyzing health and fitness data from Garmin Connect. It creates local SQLite databases to store:
- Daily monitoring data (heart rate, steps, floors climbed, stress, intensity minutes)
- Activities (running, cycling, swimming, etc.)
- Sleep data
- Weight and body composition
- Resting heart rate
- Summary statistics (daily, weekly, monthly, yearly)

### Version
Current version: 3.6.4

### Key Features
- Automatic data download from Garmin Connect
- Data copying from USB-mounted Garmin devices
- SQLite database storage with normalized schema
- Data analysis and statistics generation
- Activity export to TCX format
- Jupyter notebook integration for data visualization
- Plugin architecture for custom data processing
- Support for multiple data sources (Garmin, Fitbit, Microsoft Health)

## Architecture & Components

### Project Structure
```
GarminDB/
├── garmindb/               # Main package directory
│   ├── __init__.py
│   ├── download.py         # Garmin Connect download functionality
│   ├── copy.py            # USB device copy functionality
│   ├── analyze.py         # Data analysis tools
│   ├── statistics.py      # Statistics generation
│   ├── garmindb/          # Database models package
│   │   ├── garmin_db.py   # Main Garmin database models
│   │   ├── activities_db.py # Activities database models
│   │   ├── monitoring_db.py # Monitoring database models
│   │   └── garmin_summary_db.py # Summary database models
│   ├── summarydb/         # Summary database package
│   ├── fitbitdb/          # Fitbit integration
│   ├── mshealthdb/        # Microsoft Health integration
│   └── *.py               # Various processors and utilities
├── scripts/               # CLI entry points
│   ├── garmindb_cli.py   # Main CLI tool
│   ├── garmindb_checkup.py # Health checkup tool
│   └── garmindb_bug_report.py # Bug reporting tool
├── Fit/                   # FIT file parsing submodule
├── Tcx/                   # TCX file parsing submodule
├── utilities/             # Common utilities submodule
├── Plugins/              # Plugin extensions
├── Jupyter/              # Jupyter notebooks for analysis
└── test/                 # Test suite
```

### Core Components

#### 1. **Download Module** (`download.py`)
- Uses `garth` library for Garmin Connect authentication
- Handles session management and caching
- Downloads various data types:
  - Activities (FIT and TCX files)
  - Daily monitoring data
  - Sleep data
  - Weight measurements
  - Resting heart rate
  - Hydration data

#### 2. **Copy Module** (`copy.py`)
- Copies data from USB-mounted Garmin devices
- Supports direct FIT file transfer
- Handles device detection and mounting

#### 3. **Database Layer**
- **GarminDb**: Main database for device info, attributes, sleep, weight, RHR
- **ActivitiesDb**: Detailed activity data including laps and records
- **MonitoringDb**: Daily monitoring data (heart rate, steps, floors, etc.)
- **GarminSummaryDb**: Aggregated summary statistics
- **SummaryDb**: Cross-database summaries

#### 4. **FIT File Processors**
- `FitFileProcessor`: Base processor for FIT files
- `ActivityFitFileProcessor`: Processes activity FIT files
- `MonitoringFitFileProcessor`: Processes daily monitoring FIT files
- `SleepFitFileProcessor`: Processes sleep FIT files

#### 5. **Data Import/Export**
- JSON data importers for various Garmin Connect data
- TCX file import/export
- Activity export functionality

## Installation & Setup

### Requirements
- Python 3.0+ (tested with 3.11.4)
- SQLite3
- Git (for source installation)

### Dependencies
```
SQLAlchemy==2.0.40
python-dateutil==2.9.0.post0
cached-property==1.5.2
tqdm==4.66.5
garth==0.5.7
fitfile>=1.1.10
tcxfile>=1.0.4
idbutils>=1.1.0
tornado>=6.4.2  # security fix
```

### Installation Methods

#### Method 1: PyPI Installation (Recommended)
```bash
# Install from PyPI
pip install garmindb

# Create configuration directory
mkdir ~/.GarminDb

# Copy and edit configuration
curl -o ~/.GarminDb/GarminConnectConfig.json https://raw.githubusercontent.com/tcgoetz/GarminDB/master/garmindb/GarminConnectConfig.json.example
# Edit ~/.GarminDb/GarminConnectConfig.json with your credentials

# Initial full download and database creation
garmindb_cli.py --all --download --import --analyze

# Incremental updates
garmindb_cli.py --all --download --import --analyze --latest
```

#### Method 2: From Source
```bash
# Clone repository (must use SSH for submodules)
git clone git@github.com:tcgoetz/GarminDB.git
cd GarminDB

# Setup environment
make setup

# Copy and configure
cp garmindb/GarminConnectConfig.json.example ~/.GarminDb/GarminConnectConfig.json
# Edit configuration file

# Create databases
make create_dbs

# Update databases
make
```

### Virtual Environment Setup
The project automatically creates a virtual environment at `.venv/` when using Make commands.

## Database Schema

### Main Databases

#### 1. **garmin.db** (GarminDb)
Primary database for core Garmin data.

**Tables:**
- `attributes`: Key-value store for system attributes
- `devices`: Garmin device information
  - serial_number (PK)
  - timestamp
  - device_type
  - manufacturer
  - product
  - hardware_version
- `device_info`: Device info from FIT files
- `files`: Tracked data files
- `sleep`: Sleep data
- `weight`: Weight measurements
- `resting_heart_rate`: RHR data

#### 2. **garmin_activities.db** (ActivitiesDb)
Detailed activity tracking.

**Tables:**
- `activities`: Main activity records
  - activity_id (PK)
  - name, description, type, sport, sub_sport
  - start_time, stop_time
  - distance, calories, avg_hr, max_hr
  - avg_speed, max_speed
  - ascent, descent
  - lap_count
- `activity_laps`: Lap data for activities
- `activity_records`: Detailed record points
- `steps_activities`: Step-specific activities
- `paddle_activities`: Paddle sport activities
- `cycle_activities`: Cycling activities
- `elliptical_activities`: Elliptical activities

#### 3. **garmin_monitoring.db** (MonitoringDb)
Daily monitoring and health metrics.

**Tables:**
- `monitoring_hr`: Heart rate monitoring
- `monitoring`: General monitoring data
- `monitoring_climb`: Floors climbed
- `monitoring_intensity`: Intensity minutes
- `monitoring_steps`: Step counts

#### 4. **garmin_summary.db** (GarminSummaryDb)
Aggregated statistics.

**Tables:**
- `sleep_summary`: Sleep statistics
- `rhr_summary`: Resting heart rate summary
- `monitoring_summary`: Daily monitoring summary
- `steps_summary`: Step statistics
- `itime_summary`: Intensity time summary

### Database Relationships
- Activities reference devices via serial_number
- Laps and records reference activities via activity_id
- Summary tables aggregate data from main tables
- Files table tracks all imported data files

## Core Functionality

### Data Download Process
1. **Authentication**: Uses Garth library with session caching
2. **Data Types Downloaded**:
   - User profile and settings
   - Activity list and details
   - Daily monitoring FIT files
   - Sleep data
   - Weight measurements
   - Resting heart rate
   - Hydration data

### Data Import Process
1. **FIT File Processing**:
   - Parse binary FIT files using fitfile library
   - Extract relevant fields based on file type
   - Handle manufacturer-specific data
2. **JSON Processing**:
   - Parse Garmin Connect JSON responses
   - Map to database models
3. **TCX Processing**:
   - Parse TCX XML files
   - Extract activity data

### Analysis Features
- Generate daily, weekly, monthly, yearly summaries
- Calculate statistics (averages, totals, trends)
- Create database views for easier querying
- Export data for external analysis

## CLI Commands

### Main CLI Tool (`garmindb_cli.py`)

#### Basic Commands
```bash
# Download all data and create database
garmindb_cli.py --all --download --import --analyze

# Update with latest data
garmindb_cli.py --all --download --import --analyze --latest

# Rebuild database from existing files
garmindb_cli.py --rebuild_db

# Backup databases
garmindb_cli.py --backup

# Export activities
garmindb_cli.py --export_activities --start_date 2024-01-01
```

#### Options
- `--all`: Process all enabled statistics
- `--download`: Download data from Garmin Connect
- `--copy`: Copy from USB device
- `--import`: Import downloaded data to database
- `--analyze`: Run analysis and generate summaries
- `--latest`: Only process recent data
- `--rebuild_db`: Rebuild database from scratch
- `--backup`: Create database backups
- `--export_activities`: Export activities as TCX
- `--start_date`, `--end_date`: Date range filters

### Health Checkup Tool (`garmindb_checkup.py`)
Analyzes health trends and provides insights.

### Bug Report Tool (`garmindb_bug_report.py`)
Generates diagnostic information for troubleshooting.

## Configuration

### Configuration File Location
`~/.GarminDb/GarminConnectConfig.json`

### Configuration Structure
```json
{
    "db": {
        "type": "sqlite"
    },
    "garmin": {
        "domain": "garmin.com"
    },
    "credentials": {
        "user": "email@example.com",
        "secure_password": false,
        "password": "password",
        "password_file": null
    },
    "data": {
        "weight_start_date": "12/31/2019",
        "sleep_start_date": "12/31/2019",
        "rhr_start_date": "12/31/2019",
        "monitoring_start_date": "12/31/2019",
        "download_latest_activities": 25,
        "download_all_activities": 1000
    },
    "directories": {
        "relative_to_home": true,
        "base_dir": "HealthData",
        "mount_dir": "/Volumes/GARMIN"
    },
    "enabled_stats": {
        "monitoring": true,
        "steps": true,
        "itime": true,
        "sleep": true,
        "rhr": true,
        "weight": true,
        "activities": true
    },
    "course_views": {
        "steps": []
    },
    "activities": {
        "display": []
    },
    "settings": {
        "metric": false,
        "default_display_activities": ["walking", "running", "cycling"]
    },
    "checkup": {
        "look_back_days": 90
    }
}
```

### Key Configuration Options
- **credentials**: Garmin Connect login information
- **data.***_start_date**: Historical data download start dates
- **directories.base_dir**: Root directory for data storage
- **directories.mount_dir**: USB device mount point
- **enabled_stats**: Toggle data types to process
- **settings.metric**: Use metric vs imperial units

## Data Flow

### Download Flow
1. User initiates download via CLI
2. Authenticate with Garmin Connect
3. Query available data based on date ranges
4. Download files to local directories:
   - `~/HealthData/FitFiles/[Year]/Activities/`
   - `~/HealthData/FitFiles/[Year]/Monitoring/`
   - `~/HealthData/FitFiles/[Year]/Sleep/`
5. Save session for reuse

### Import Flow
1. Scan directories for new files
2. Parse files based on type
3. Create/update database records
4. Track processed files to avoid duplicates
5. Generate summaries and statistics

### USB Copy Flow
1. Detect mounted Garmin device
2. Locate data directories on device
3. Copy FIT files to local storage
4. Process as normal import

## Plugin System

### Plugin Architecture
- Plugins extend data processing capabilities
- Located in `Plugins/` directory
- Inherit from base plugin classes
- Can process custom FIT file data fields

### Available Plugins
- `fbb_dozen_*_plugin.py`: FirstBeat Dozen workout plugins
- `fbb_hrv_plugin.py`: HRV (Heart Rate Variability) processing
- `stryd_zones_plugin.py`: Stryd power meter zones

### Creating Custom Plugins
1. Inherit from `ActivityFitPluginBase` or `MonitoringFitPluginBase`
2. Implement required methods:
   - `init_activity()`: Initialize plugin for activity
   - `process_record()`: Process each data record
   - `finish_activity()`: Finalize processing
3. Register plugin in configuration

## Testing

### Test Structure
```
test/
├── test_garmin_db.py        # Main database tests
├── test_activities_db.py    # Activities database tests
├── test_monitoring_db.py    # Monitoring database tests
├── test_fit_file.py        # FIT file parsing tests
├── test_tcx_file.py        # TCX file parsing tests
└── test_config.py          # Configuration tests
```

### Running Tests
```bash
# Run all tests
make -C test all

# Run specific test group
make -C test garmin_db

# Run individual test
python test/test_garmin_db.py
```

### Test Data
Test files are located in `test/test_files/` with sample FIT, TCX, and JSON files.

## Development Guide

### Setting Up Development Environment
```bash
# Clone with submodules
git clone --recurse-submodules git@github.com:tcgoetz/GarminDB.git

# Install development dependencies
pip install -r dev-requirements.txt

# Run code quality checks
make flake8
```

### Code Style
- Follow PEP 8 guidelines
- Use flake8 for linting
- Document all public methods
- Add type hints where applicable

### Database Migrations
- Database version tracked in each DB class
- Automatic migration on version mismatch
- Backup before migration recommended

### Adding New Data Types
1. Create database model in appropriate `*_db.py`
2. Create processor class for parsing
3. Add import logic to main CLI
4. Update configuration schema
5. Add tests

### Debugging
- Log files: `garmindb.log`
- Verbose mode: Add `--verbose` flag
- Debug database: Use SQLite browser tools
- Check `bugreport.txt` for diagnostics

### Common Issues & Solutions

#### Authentication Failures
- Check credentials in config
- Delete `~/.GarminDb/garth_session.json` to force re-login
- Verify Garmin Connect is accessible

#### Database Corruption
```bash
# Rebuild from downloaded files
garmindb_cli.py --rebuild_db
```

#### Missing Data
- Check date ranges in configuration
- Verify data exists in Garmin Connect
- Check enabled_stats in config

#### Performance Issues
- Use `--latest` for incremental updates
- Consider date range limits
- Monitor disk space

### Contributing
1. Fork repository
2. Create feature branch from `develop`
3. Add tests for new functionality
4. Run `make flake8` and fix issues
5. Submit pull request to `develop` branch
6. Add yourself to `contributors.txt`

## Additional Resources

### Jupyter Notebooks
Located in `Jupyter/` directory:
- `activities.ipynb`: Activity analysis
- `daily.ipynb`: Daily statistics
- `monitoring.ipynb`: Heart rate monitoring
- `summary.ipynb`: Overall summaries

### Database Views
Automatically created views for easier querying:
- Activity views by type
- Daily/weekly/monthly summaries
- Course comparison views

### Export Formats
- TCX for activities
- CSV via pandas export
- JSON for raw data

### Third-Party Integrations
- Jupyter for visualization
- SQLite browsers for direct queries
- External analysis tools via exports

## Troubleshooting Commands

```bash
# Generate bug report
garmindb_bug_report.py

# Check database integrity
sqlite3 ~/HealthData/DBs/garmin.db "PRAGMA integrity_check;"

# View recent activities
sqlite3 ~/HealthData/DBs/garmin_activities.db "SELECT * FROM activities ORDER BY start_time DESC LIMIT 10;"

# Check monitoring data
sqlite3 ~/HealthData/DBs/garmin_monitoring.db "SELECT date, steps FROM monitoring_summary ORDER BY date DESC LIMIT 10;"
```

## Notes for AI Agents

### Key Entry Points
- Main CLI: `scripts/garmindb_cli.py`
- Core logic: `garmindb/download.py`, `garmindb/copy.py`
- Database models: `garmindb/garmindb/*.py`
- Configuration: `~/.GarminDb/GarminConnectConfig.json`

### Important Patterns
- All database operations use SQLAlchemy ORM
- FIT file parsing through fitfile submodule
- Plugin system for extensibility
- Makefile automation for common tasks

### Development Workflow
1. Configuration setup is mandatory
2. Initial download can take hours
3. Incremental updates are fast
4. Database rebuilds preserve downloaded files
5. Testing uses sample data files

### Security Considerations
- Credentials stored in plain text (use password_file for better security)
- Session tokens cached locally
- No encryption on local databases
- Consider file permissions on data directories

---

*This documentation is designed for AI agents to quickly understand and work with the GarminDB codebase. For human-readable documentation, see the project README and wiki.*