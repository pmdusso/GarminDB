# Architecture Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Safely de-cruft the GarminDB repo root, archive legacy notebooks, and bring the analysis/report/data test suite into the Makefile + CI — without breaking `make verify_commit`, packaging, or any live workflow.

**Architecture:** Sequenced workstreams on one branch (A → C → B → D → E). Workstream C lands first so the new pytest suite is a safety net before the structural move (B). Three known blockers are fixed up front in C: `setup.py` package list (CI installs a non-editable wheel), the two-`models.py` pytest-collection collision (run per-file), and config/DB-dependent tests (split `safe` vs `manual`).

**Tech Stack:** Python 3.12/3.13, SQLite + SQLAlchemy, `make` (root `Makefile` + `test/Makefile`), pytest 9.0.2 + unittest, GitHub Actions (`.github/workflows/pythonapp.yml`), `setuptools`.

**Decisions locked (this session):** root cruft → **archive** to `scripts/legacy/` (not `git rm`); branch from **`master`** (corrected 2026-06-10 — `origin/develop` is the upstream PostgreSQL branch, 90 commits behind master, and contains none of the code this plan touches: no `garmindb/analysis|data|presentation`, no scripts to archive, no analysis tests; PR therefore targets `master`); one plan, workstreams independently committable.

---

## File Structure

Files created/modified, and what each is responsible for:

- **`scripts/legacy/` (new dir)** — home for the 5 archived ad-hoc root scripts + a `README.md` marking them legacy.
- **`setup.py`** — switch the hand-maintained `packages=[...]` to `find_packages(include=['garmindb', 'garmindb.*'])` so the built wheel includes `garmindb.analysis/data/presentation` (CI installs the wheel, not editable).
- **`dev-requirements.in` / `dev-requirements.txt`** — declare `pytest==9.0.2` so `devdeps` installs it in CI.
- **`test/Makefile`** — add an `analysis` target that runs the curated pytest suite **per-file** (sidesteps the two-`models.py` collision); wire it into `all` and `verify_commit`.
- **`Makefile` (root)** — remove/neutralize every `Jupyter/` reference (`graphdeps`, `jupiterdeps`, `alldeps`, the two `Jupyter/requirements*.txt` targets, `remove_deps` l.188-189, `clean` l.205/211); expand the `flake8:` target to lint `garmindb/analysis`, `garmindb/data`, `garmindb/presentation`, `scripts`.
- **`Jupyter/` → `docs/notebooks/`** — archived; `__init__.py` deleted (no phantom `docs.notebooks` package).
- **`.gitignore`** — repoint the `Jupyter/.ipynb_checkpoints/` line.
- **`README.md`, `AGENTS.md`, `garmindb/GarminDB_Comprehensive_Documentation.md`, `CLAUDE.md`** — update notebook paths + test-command docs.
- **`contributors.txt`** — add the author (project convention).

---

## Task 0: Branch + contributors

**Files:**
- Modify: `contributors.txt`

- [x] **Step 1: Create the branch from `master`**

Run:
```bash
git switch -c chore/architecture-cleanup master
```
Expected: `Switched to a new branch 'chore/architecture-cleanup'`.
(Was `origin/develop` in the draft — corrected: develop lacks all the code this plan touches.)

- [ ] **Step 2: Add yourself to contributors.txt**

Append your name on its own line (match the existing format — inspect the last line first with `tail -3 contributors.txt`).

- [ ] **Step 3: Commit**

```bash
git add contributors.txt
git commit -m "chore: add contributor for architecture cleanup"
```

---

## Workstream A — Archive root cruft

### Task A1: Move the 5 ad-hoc scripts to `scripts/legacy/`

**Files:**
- Create: `scripts/legacy/README.md`
- Move: `debug_insert.py`, `recompute_q4_report.py`, `test_activity_report.py`, `test_recovery_report.py`, `test_stress_report.py` → `scripts/legacy/`

- [ ] **Step 1: Re-confirm zero in-repo references (safety re-check)**

Run:
```bash
rg -n --hidden --glob '!.git' 'debug_insert|recompute_q4_report|test_activity_report|test_recovery_report|test_stress_report' \
  | rg -v 'docs/plans/|docs/superpowers/plans/'
```
Expected: **no output** (the only matches are this plan + the strategy doc). If any other file matches, STOP — investigate before moving.

- [ ] **Step 2: Create the archive dir + README**

Create `scripts/legacy/README.md`:
```markdown
# Legacy ad-hoc scripts

Working but unmaintained one-off CLIs (debug / manual report regeneration) that
import live `garmindb` APIs. No automated reference exists (test/Makefile/CI).
Kept for occasional manual use; not part of packaging, tests, or CI. Prefer
`scripts/generate_report.py` and `garmindb_cli.py` for current workflows.
```

- [ ] **Step 3: Move the 5 scripts (git mv preserves history)**

Run:
```bash
git mv debug_insert.py recompute_q4_report.py test_activity_report.py test_recovery_report.py test_stress_report.py scripts/legacy/
```

- [ ] **Step 4: Verify the root is clean and nothing references the old paths**

Run:
```bash
ls scripts/legacy/
rg -n --hidden --glob '!.git' '(^|[^/])debug_insert\.py|recompute_q4_report\.py' | rg -v 'docs/|scripts/legacy/'
```
Expected: 5 scripts listed under `scripts/legacy/`; second command prints nothing.

- [ ] **Step 5: Commit**

```bash
git add -A scripts/legacy/ && git commit -m "chore: archive ad-hoc root scripts to scripts/legacy/"
```

---

## Workstream C — Tests into Makefile + CI (run first; fixes 3 blockers)

### Task C1: Fix `setup.py` packages so the wheel includes analysis/data/presentation

**Files:**
- Modify: `setup.py:5` (import), `setup.py:41` (packages)
- Test: a clean-venv wheel install + import

- [ ] **Step 1: Write the failing check (prove the gap)**

Run (from repo root):
```bash
python -c "import ast,sys; src=open('setup.py').read(); print('analysis' in src and 'find_packages' in src)"
```
Expected: `False` (no `find_packages`, no analysis subpackage listed) — confirms the gap.

- [ ] **Step 2: Edit the import line**

`setup.py:5` — change:
```python
from setuptools import setup
```
to:
```python
from setuptools import setup, find_packages
```

- [ ] **Step 3: Replace the hand-maintained packages list**

`setup.py:41` — change:
```python
      packages=[module_name, f'{module_name}.garmindb', f'{module_name}.fitbitdb', f'{module_name}.mshealthdb', f'{module_name}.summarydb'],
```
to:
```python
      packages=find_packages(include=[module_name, f'{module_name}.*']),
```

- [ ] **Step 4: Verify the wheel now contains the subpackages**

Run:
```bash
rm -rf /tmp/whltest && python -m venv /tmp/whltest && /tmp/whltest/bin/pip install -q build
make build   # builds dist/garmindb-*.whl
/tmp/whltest/bin/pip install -q dist/garmindb-*.whl
/tmp/whltest/bin/python -c "import garmindb.analysis, garmindb.data, garmindb.presentation; print('OK')"
```
Expected: `OK` (no `ModuleNotFoundError`). Before the fix this raised `ModuleNotFoundError: No module named 'garmindb.analysis'`.

- [ ] **Step 5: Commit**

```bash
git add setup.py && git commit -m "fix(packaging): include garmindb.analysis/data/presentation via find_packages"
```

### Task C2: Declare pytest as a dev dependency

**Files:**
- Modify: `dev-requirements.in`, `dev-requirements.txt`

- [ ] **Step 1: Add the pin to dev-requirements.in**

`dev-requirements.in` — add a line:
```
pytest==9.0.2
```
(Final file: `flake8`, `build`, `wheel`, `twine`, `pytest==9.0.2`.)

- [ ] **Step 2: Regenerate dev-requirements.txt in a CLEAN venv (NOT the current one)**

Do **not** run `make dev-requirements.txt` in the maintainer venv — `pip freeze -r` would drag in Jupyter, the `-e git+ssh://…` editable, and personal deps. Instead, in a throwaway venv:
```bash
python -m venv /tmp/devreq && /tmp/devreq/bin/pip install -q flake8 build wheel twine pytest==9.0.2
/tmp/devreq/bin/pip freeze -r dev-requirements.in > dev-requirements.txt
```
Then inspect the diff and confirm it contains **no** `git+ssh`, no Jupyter packages:
```bash
git diff dev-requirements.txt | rg -i 'git\+ssh|jupyter|notebook|matplotlib' && echo "REVIEW: unexpected dep" || echo "clean"
```
Expected: `clean`. If unexpected deps appear, hand-edit them out.

- [ ] **Step 3: Verify pytest installs via devdeps**

Run:
```bash
rg -n 'pytest' dev-requirements.txt
```
Expected: a pinned `pytest==9.0.2` line present.

- [ ] **Step 4: Commit**

```bash
git add dev-requirements.in dev-requirements.txt && git commit -m "build(test): declare pytest==9.0.2 as a dev dependency"
```

### Task C3: Classify the 28 analysis tests into `safe` vs `manual`

**Files:**
- Create: `test/analysis_groups.mk` (a documented list, included by the Makefile in C4)

- [ ] **Step 1: Run each candidate in a clean-env simulation and bin it**

Simulate a CI runner with no real config/DBs by pointing `HOME` at an empty dir (so `GarminConnectConfigManager` finds no `~/.GarminDb/...` and no `~/HealthData/...`):
```bash
cd test
for t in test_activity_analyzer test_recovery_analyzer test_sleep_analyzer test_stress_analyzer \
         test_health_analyzer test_power_analyzer test_power_analyzer_analyze test_power_analyzer_phase1 \
         test_decoupling_analyzer test_performance_report test_performance_renderer test_performance_targets \
         test_performance_cli_smoke test_performance_power_phase1 test_longitudinal_report \
         test_longitudinal_clinical test_longitudinal_power_phase1 test_markdown_presenter test_report_state \
         test_repositories test_sqlite_repository test_data_models test_db_metrics test_integration \
         test_weight_series test_download_auth_adapter test_garmin_connect_auth_adapter test_power_import_phase2_sp1; do
  HOME=$(mktemp -d) ../.venv/bin/python -m pytest -p no:cacheprovider -q "$t.py" >/dev/null 2>&1 \
    && echo "SAFE   $t" || echo "MANUAL $t"
done
cd ..
```
Expected (from prior verification): `test_integration` → MANUAL (it does `GarminConnectConfigManager()` in `setUpClass` → `SystemExit`). The two auth adapters → SAFE (fully mocked). Record the actual SAFE/MANUAL split from the output.

- [ ] **Step 2: Write the curated lists into test/analysis_groups.mk**

Create `test/analysis_groups.mk` using the SAFE names from Step 1. Seed (adjust to match Step 1 output):
```make
# Hermetic analysis/report tests — no real ~/.GarminDb config or ~/HealthData DB.
# Run per-file (two models.py modules collide in a single pytest process).
ANALYSIS_SAFE=test_activity_analyzer test_recovery_analyzer test_sleep_analyzer test_stress_analyzer \
  test_health_analyzer test_power_analyzer test_power_analyzer_analyze test_power_analyzer_phase1 \
  test_decoupling_analyzer test_performance_report test_performance_renderer test_performance_targets \
  test_performance_cli_smoke test_performance_power_phase1 test_longitudinal_report \
  test_longitudinal_clinical test_longitudinal_power_phase1 test_markdown_presenter test_report_state \
  test_data_models test_download_auth_adapter test_garmin_connect_auth_adapter test_power_import_phase2_sp1

# Needs real config/DB — kept OUT of verify_commit/CI; run manually.
ANALYSIS_MANUAL=test_integration test_repositories test_sqlite_repository test_db_metrics test_weight_series
```
**Rule:** any test that printed `MANUAL` in Step 1 goes in `ANALYSIS_MANUAL`; do not add it to `ANALYSIS_SAFE`.

- [ ] **Step 3: Commit**

```bash
git add test/analysis_groups.mk && git commit -m "test: classify analysis tests into safe (CI) vs manual (needs DB)"
```

### Task C4: Add the `analysis` target (per-file) and wire it into all + verify_commit

**Files:**
- Modify: `test/Makefile` (add include + `analysis` target; extend `all`, `verify_commit`, `.PHONY`)

- [ ] **Step 1: Include the groups file and add the per-file target**

`test/Makefile` — after the `include $(PROJECT_BASE)/defines.mk` line (line 8), add:
```make
include analysis_groups.mk
```
Then add a new target (place it near the other group targets, before the `.PHONY` line):
```make
# pytest analysis suite — per-file to avoid the two models.py collision.
analysis:
	@set -e; for t in $(ANALYSIS_SAFE); do \
	  echo "== pytest $$t =="; \
	  $(PYTHON_PATH) -m pytest -p no:cacheprovider -q $$t.py; \
	done

analysis_manual:
	@set -e; for t in $(ANALYSIS_MANUAL); do \
	  echo "== pytest $$t (manual) =="; \
	  $(PYTHON_PATH) -m pytest -p no:cacheprovider -q $$t.py; \
	done
```

- [ ] **Step 2: Wire `analysis` into `all` and `verify_commit`**

`test/Makefile:22` — change:
```make
all: $(ALL_TEST_GROUPS)
```
to:
```make
all: $(ALL_TEST_GROUPS) analysis
```
`test/Makefile:32` — change:
```make
verify_commit: module_versions db_objects
```
to:
```make
verify_commit: module_versions db_objects analysis
```
`test/Makefile:50` — add `analysis analysis_manual` to the `.PHONY` line.

- [ ] **Step 3: Run the analysis target and verify it passes per-file**

Run:
```bash
make -C test analysis
```
Expected: each `== pytest test_* ==` block reports `passed`, overall exit 0. (Confirms the per-file loop avoids the `ImportError: cannot import name 'SleepRecord'` that a single combined run hits.)

- [ ] **Step 4: Verify verify_commit (local) now includes analysis and is green**

Run:
```bash
make -C test verify_commit
```
Expected: `module_versions`, `db_objects`, then the `analysis` per-file blocks, all passing.

- [ ] **Step 5: Commit**

```bash
git add test/Makefile && git commit -m "test: add per-file pytest 'analysis' target to all + verify_commit"
```

### Task C5: Expand `make flake8` to cover the touched dirs

**Files:**
- Modify: `Makefile:345` (the `flake8:` recipe)

- [ ] **Step 1: Enumerate the dirs to add**

Run:
```bash
fd -e py . garmindb/analysis garmindb/data garmindb/presentation scripts | sed 's#/[^/]*$##' | sort -u
```
Expected: lists the dirs holding the new code (e.g. `garmindb/analysis`, `garmindb/data`, `garmindb/data/repositories`, `garmindb/presentation`, `garmindb/presentation/markdown`, `scripts`, `scripts/legacy`). Use these to build the glob in Step 2.

- [ ] **Step 2: Add the globs to the flake8 recipe**

`Makefile:345` — append the new globs (keep the existing ones and flags):
```make
	$(PYTHON_PATH) -m flake8 garmindb/*.py garmindb/garmindb/*.py garmindb/summarydb/*.py garmindb/fitbitdb/*.py garmindb/mshealthdb/*.py garmindb/analysis/*.py garmindb/data/*.py garmindb/data/repositories/*.py garmindb/presentation/*.py garmindb/presentation/markdown/*.py scripts/*.py scripts/legacy/*.py --max-line-length=180 --ignore=E203,E221,E241,W503
```
(Drop any glob from Step 1 that matched no files to avoid a flake8 "path not found" error.)

- [ ] **Step 3: Run flake8 and confirm clean + that it lints the new files**

Run:
```bash
make flake8
```
Expected: exit 0, no findings. (The analysis/presentation code already passed manual flake8 with these flags; if `scripts/legacy/*.py` flags issues in the archived scripts, either fix them or exclude `scripts/legacy` from the glob — decide and note it.)

- [ ] **Step 4: Commit**

```bash
git add Makefile && git commit -m "build: lint analysis/data/presentation/scripts in make flake8"
```

### Task C6: Full CI-like verification of Workstream C

- [ ] **Step 1: Confirm verify_commit is green in a clean-HOME run**

Run:
```bash
HOME=$(mktemp -d) make -C test verify_commit
```
Expected: green. If anything in `ANALYSIS_SAFE` fails here (but passed with the real HOME), it has a hidden config/DB dependency — move it to `ANALYSIS_MANUAL` (edit `test/analysis_groups.mk`) and re-run. Amend the C3/C4 commits if needed.

- [ ] **Step 2: Commit any reclassification**

```bash
git add test/analysis_groups.mk && git commit -m "test: move <name> to analysis_manual (hidden DB dependency)"
```
(Skip if Step 1 was already green.)

---

## Workstream B — Archive notebooks (edit refs BEFORE moving)

### Task B1: Remove every `Jupyter/` reference from the root Makefile

**Files:**
- Modify: `Makefile` (targets at lines ~156-160, 174-180, 185-189, 200-211)

- [ ] **Step 1: List every Jupyter reference (so none is missed)**

Run:
```bash
rg -n 'Jupyter' Makefile
```
Expected matches: lines 156, 159 (the two `Jupyter/requirements*.txt` targets), 174-178 (`graphdeps`/`jupiterdeps`), 180 (`alldeps`), 188-189 (`remove_deps`), 205, 211 (`clean`).

- [ ] **Step 2: Delete the two notebook requirements targets**

Remove these blocks entirely (`Makefile:156-160`):
```make
Jupyter/requirements.txt:
	$(PIP_PATH) freeze -r Jupyter/requirements.in > Jupyter/requirements.txt

Jupyter/requirements_graphs.txt:
	$(PIP_PATH) freeze -r Jupyter/requirements_graphs.in > Jupyter/requirements_graphs.txt
```

- [ ] **Step 3: Delete graphdeps/jupiterdeps and drop jupiterdeps from alldeps**

Remove (`Makefile:174-178`):
```make
graphdeps:
	$(PIP_PATH) install --upgrade --requirement Jupyter/requirements_graphs.txt

jupiterdeps: graphdeps
	$(PIP_PATH) install --upgrade --requirement Jupyter/requirements.txt
```
Change `Makefile:180` from:
```make
alldeps: update_pip_packages deps devdeps jupiterdeps
```
to:
```make
alldeps: update_pip_packages deps devdeps
```

- [ ] **Step 4: Drop the Jupyter uninstall lines from remove_deps**

Remove `Makefile:188-189`:
```make
	$(PIP_PATH) uninstall -y --requirement Jupyter/requirements.txt
	$(PIP_PATH) uninstall -y --requirement Jupyter/requirements_graphs.txt
```

- [ ] **Step 5: Drop the Jupyter rm lines from clean**

Remove `Makefile:205` (`rm -f Jupyter/*.log`) and `Makefile:211` (`rm -f Jupyter/*stats.txt`).

- [ ] **Step 6: Verify no Jupyter refs remain and the Makefile still parses**

Run:
```bash
rg -n 'Jupyter' Makefile; echo "---"; make -n alldeps clean remove_deps >/dev/null && echo "makefile parses"
```
Expected: first command prints nothing; `makefile parses`.

- [ ] **Step 7: Commit**

```bash
git add Makefile && git commit -m "chore(make): drop all Jupyter/ targets and references"
```

### Task B2: Update docs that point at the `Jupyter/` path

**Files:**
- Modify: `README.md` (lines ~21, 25, 51-53), `AGENTS.md:8`, `garmindb/GarminDB_Comprehensive_Documentation.md` (lines 36, 68, 521-522, 540)

- [ ] **Step 1: README.md — repoint the notebooks section**

`README.md:51-53` — change the `# Jupyter Notebooks #` section to note the archive:
```markdown
# Notebooks (archived) #

Legacy Jupyter notebooks were moved to `docs/notebooks/` (archived, unmaintained).
The current path for analysis output is the markdown reports (`scripts/generate_report.py`).
```
Also soften line 21 (`* Graph your data from the commandline or with Jupyter notebooks.`) and line 25 (the "supplied Jupyter notebooks" recommendation) to past tense / `docs/notebooks/`. Leave line 1 (the upstream raw.githubusercontent Screenshots URL) unchanged — it points at the upstream repo, not a local path.

- [ ] **Step 2: AGENTS.md:8 — repoint**

Change:
```markdown
- Notebooks and assets: `Jupyter/`, `Screenshots/`; plugins under `Plugins/`.
```
to:
```markdown
- Notebooks (archived): `docs/notebooks/`; assets: `Screenshots/`; plugins under `Plugins/`.
```

- [ ] **Step 3: GarminDB_Comprehensive_Documentation.md — repoint the 5 refs**

Update lines 36, 68 (`├── Jupyter/`), 521-522 (`### Jupyter Notebooks` / `Located in Jupyter/ directory:`), 540 to say `docs/notebooks/` and mark archived. Verify with `rg -n 'Jupyter/' garmindb/GarminDB_Comprehensive_Documentation.md` after editing (only `docs/notebooks/` should remain, or note any wiki URL kept intentionally).

- [ ] **Step 4: Verify**

Run:
```bash
rg -n 'Jupyter/' README.md AGENTS.md garmindb/GarminDB_Comprehensive_Documentation.md
```
Expected: no remaining bare `Jupyter/` path refs (URLs to the upstream repo are fine).

- [ ] **Step 5: Commit**

```bash
git add README.md AGENTS.md garmindb/GarminDB_Comprehensive_Documentation.md
git commit -m "docs: repoint Jupyter/ references to docs/notebooks/ (archived)"
```

### Task B3: Repoint the .gitignore checkpoints line

**Files:**
- Modify: `.gitignore:108`

- [ ] **Step 1: Edit the line**

`.gitignore:108` — change:
```
Jupyter/.ipynb_checkpoints/
```
to:
```
docs/notebooks/.ipynb_checkpoints/
```

- [ ] **Step 2: Commit**

```bash
git add .gitignore && git commit -m "chore: repoint .ipynb_checkpoints ignore to docs/notebooks/"
```

### Task B4: Move the notebooks and remove the phantom package

**Files:**
- Move: `Jupyter/` → `docs/notebooks/`
- Delete: `docs/notebooks/__init__.py`
- Create: `docs/notebooks/README.md`

- [ ] **Step 1: Move tracked files with git**

Run:
```bash
git mv Jupyter docs/notebooks
```
Expected: clean rename (`docs/notebooks/` did not pre-exist).

- [ ] **Step 2: Delete the package marker (avoid a phantom docs.notebooks package)**

Run:
```bash
git rm docs/notebooks/__init__.py
```

- [ ] **Step 3: Clean up the leftover untracked checkpoints dir at the old path**

Run:
```bash
rm -rf Jupyter   # only the untracked .ipynb_checkpoints/ remains here, if anything
```
Expected: no error; `ls Jupyter` → no such file.

- [ ] **Step 4: Add the dead-archive README**

Create `docs/notebooks/README.md`:
```markdown
# Archived notebooks

Legacy Jupyter notebooks (visualization/analysis), kept for reference only.
Unmaintained and not wired into the Makefile/CI. The current analysis path is the
markdown reports generated by `scripts/generate_report.py`. The
`requirements*.{in,txt}` here are also legacy — do not resurrect them in the Makefile.
```

- [ ] **Step 5: Verify the move and that nothing live references the old path**

Run:
```bash
ls docs/notebooks/*.ipynb | wc -l    # expect 15
test ! -e docs/notebooks/__init__.py && echo "no __init__"
rg -n --hidden --glob '!.git' 'Jupyter/' . | rg -v 'docs/plans/|docs/superpowers/plans/'
```
Expected: `15`; `no __init__`; the last command prints nothing.

- [ ] **Step 6: Commit**

```bash
git add -A docs/notebooks/ && git commit -m "chore: archive Jupyter notebooks to docs/notebooks/ (dead archive)"
```

---

## Workstream D — .gitignore hardening (optional)

### Task D1: Ignore temp_config/ as a directory

**Files:**
- Modify: `.gitignore`

- [ ] **Step 1: Check current coverage**

Run:
```bash
rg -n 'temp_config' .gitignore
```
Expected: only two specific paths (`temp_config/GarminConnectConfig.json`, `temp_config/garth_session`) — the dir itself is not ignored.

- [ ] **Step 2: Add a directory-level ignore (keep the specific lines or replace them)**

Add to `.gitignore`:
```
temp_config/
```

- [ ] **Step 3: Verify nothing tracked under temp_config would be lost**

Run:
```bash
git ls-files temp_config/
```
Expected: no output (nothing tracked there). If something IS tracked, do NOT add the broad ignore — keep the specific lines.

- [ ] **Step 4: Commit**

```bash
git add .gitignore && git commit -m "chore: ignore temp_config/ directory"
```

---

## Workstream E — Documentation (test commands + pytest dep)

### Task E1: Update CLAUDE.md / AGENTS.md test-command docs

**Files:**
- Modify: `CLAUDE.md`, `AGENTS.md`

- [ ] **Step 1: AGENTS.md — document the analysis suite + pytest dep**

In the build/test commands section, note that `make -C test all` now also runs the pytest `analysis` suite, that `make -C test analysis` runs it alone, that `make -C test analysis_manual` needs a real config/DB, and that `pytest` is a dev dependency (installed by `devdeps`).

- [ ] **Step 2: CLAUDE.md — same test-command update**

In CLAUDE.md's "Running Tests" section, add `make -C test analysis` and the note that `verify_commit` now includes the analysis suite; mention notebooks are archived under `docs/notebooks/`.

- [ ] **Step 3: Verify the docs build/render (no broken intra-doc links)**

Run:
```bash
rg -n 'Jupyter/|make -C test' CLAUDE.md AGENTS.md
```
Expected: no bare `Jupyter/` path; the test-command references are present and correct.

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md AGENTS.md && git commit -m "docs: document analysis test suite + pytest dev dep; notebooks archived"
```

---

## Final acceptance verification

Run each and confirm before opening the PR (against `master`):

- [ ] `make flake8` → exit 0 (now lints analysis/data/presentation/scripts).
- [ ] `HOME=$(mktemp -d) make -C test verify_commit` → green in a clean env (proves the safe/manual split).
- [ ] Wheel import: `rm -rf /tmp/acc && python -m venv /tmp/acc && make build && /tmp/acc/bin/pip install -q dist/garmindb-*.whl && /tmp/acc/bin/python -c "import garmindb.analysis, garmindb.data, garmindb.presentation; print('OK')"` → `OK`.
- [ ] Scoped config check: `git ls-files '*GarminConnectConfig*.json' | grep -v '\.example$'` → empty.
- [ ] No live Jupyter refs: `rg -n --hidden --glob '!.git' 'Jupyter/' . | rg -v 'docs/plans/|docs/superpowers/plans/|docs/notebooks/'` → empty.
- [ ] Archived scripts gone from root: `ls debug_insert.py recompute_q4_report.py 2>&1 | rg 'No such'` → both reported missing.

- [ ] **Open the PR against `master`** (corrected from `develop`); do NOT push without explicit approval.

---

## Notes / corrections baked in (vs the strategy doc)

- The `alldeps` "cross-deps" risk was **overstated** — the `graphdeps→jupiterdeps→alldeps` chain is an orphan leaf; the real risk was the un-listed `remove_deps`/`clean` refs (Task B1 steps 4-5).
- The auth-adapter tests are **mocked and safe** — the real CI-breaking dependency is `test_integration` (config/DB), handled in C3.
- §7 (deferred) dead-code premise is **wrong** — `HourlyStressPattern` and `Presenter.render_sleep` are live; do NOT delete them in a future phase. Only `hourly_patterns` is "computed but never rendered."
