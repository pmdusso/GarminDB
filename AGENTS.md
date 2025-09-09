# Repository Guidelines

## Project Structure & Module Organization
- Source: `garmindb/` (core modules) with subpackages: `garmindb/garmindb`, `garmindb/summarydb`, `garmindb/fitbitdb`, `garmindb/mshealthdb`.
- CLI and tools: `scripts/` (e.g., `garmindb_cli.py`, `garmindb_bug_report.py`, `fitbit.py`, `mshealth.py`).
- Tests: `test/` with `test_*.py` and a `Makefile`; sample data in `test/test_files/`.
- Submodules: `Fit/`, `Tcx/`, `utilities/` (run `git submodule init && git submodule update`).
- Notebooks and assets: `Jupyter/`, `Screenshots/`; plugins under `Plugins/`.
- Config: `~/.GarminDb/GarminConnectConfig.json` (copy from `garmindb/GarminConnectConfig.json.example`).

## Build, Test, and Development Commands
- `make setup`: Create venv and prepare repo (incl. submodules).
- `make install_all`: Build and install package + submodules into venv.
- `make -C test all`: Run all unit tests; `python -m unittest -v test_garmin_db` for a file.
- `make flake8`: Lint Python sources (must be clean before PRs).
- `make build` / `make publish_check`: Build wheel / validate distribution.
- Data workflows: `make create_dbs`, `make update_dbs`, `make rebuild_dbs` or use `garmindb_cli.py --all --download --import --analyze [--latest]`.

## Coding Style & Naming Conventions
- Python 3; 4‑space indentation; keep functions small and cohesive.
- Lint: flake8 with `--max-line-length=180`, ignoring `E203,E221,E241,W503`.
- Names: modules/functions `snake_case`; classes `CapWords`; constants `UPPER_CASE`.
- Follow existing patterns in DB models, processors, and CLI flow.

## Testing Guidelines
- Framework: `unittest`. Place tests in `test/` as `test_*.py` and add focused cases.
- Run: `make -C test all`; quick groups exist (e.g., `make -C test garmin_db`).
- Use fixtures in `test/test_files/`; avoid network or live Garmin calls.

## Commit & Pull Request Guidelines
- Branching: open PRs against `develop`. Add yourself to `contributors.txt`.
- Pre‑submit: `make flake8` and `make -C test verify_commit` should pass.
- Messages: concise, imperative subject; reference issues (e.g., `Issue #272:`), use topical prefixes when helpful (e.g., `tests:`, `fix:`).
- PRs: clear description, linked issues, notes on DB/schema effects (and whether `--rebuild_db` is required).

## Security & Configuration Tips
- Never commit credentials. Use `password_file` in `GarminConnectConfig.json` when possible.
- Sessions cache at `~/.GarminDb/garth_session.json`; logs in `garmindb.log`.
- Prefer the project venv (`.venv`) and keep submodules updated.
