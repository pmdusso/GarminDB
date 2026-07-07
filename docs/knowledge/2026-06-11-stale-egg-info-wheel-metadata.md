#needs-peer-review

# Stale `garmindb.egg-info/` poisons locally-built wheel dependency metadata

**Date:** 2026-06-11

## Context

While fixing `setup.py` to ship `garmindb.analysis/data/presentation` in the
wheel (workstream C1 of the architecture-cleanup plan), I built a wheel locally
with `python -m build --wheel` and inspected its metadata to verify the fix.
The package list was correct, but the dependency list was wrong.

## The Myth / Assumption

`python -m build` (or `make build`) produces a wheel whose `Requires-Dist`
metadata reflects the **current** `requirements.txt` (which `setup.py` reads via
`get_requirements('requirements.txt')` into `install_requires`).

## The Fact / Truth

A locally-built wheel can carry **stale dependency metadata** that does **not**
match `requirements.txt`. The build reuses the cached
`garmindb.egg-info/requires.txt` (written by a *previous* editable install) for
`Requires-Dist`, while `packages=find_packages()` is recomputed fresh. Result:
**new package list + old dependency pins** in the same wheel.

Most consequentially, the code imports `garminconnect`
(`garmindb/garmin_connect_auth_adapter.py:10`), but a wheel built over a stale
egg-info declared `garth==0.5.19` instead — so a clean `pip install <that wheel>`
would install the wrong auth library and fail at `import garmindb` with
`ModuleNotFoundError: No module named 'garminconnect'`.

## Evidence

Current `requirements.txt` (source of `install_requires`):
```
SQLAlchemy==2.0.49
cached-property==2.0.1
tqdm==4.67.1
garminconnect==0.3.3
fitfile>=1.2.0
tornado>=6.5.4
```

Stale `garmindb.egg-info/requires.txt` (gitignored; left by an old editable install):
```
cached-property==1.5.2
fitfile>=1.1.11
garth==0.5.19            <-- not even the same auth library the code imports
sqlalchemy==2.0.41
tornado>=6.4.2
tqdm==4.66.5
```

The freshly-built wheel's `Requires-Dist` matched the **egg-info**, not
`requirements.txt`. The wheel's package namelist, however, *did* include
`garmindb/analysis/`, `garmindb/data/`, `garmindb/presentation/` (the C1 fix),
proving `find_packages` ran fresh while `Requires-Dist` did not.

`git check-ignore garmindb.egg-info` -> ignored (it is a build artifact, not tracked).

## Analytical Implication

- **CI is NOT affected:** CI builds from a fresh checkout with no `*.egg-info`,
  so its wheel metadata is regenerated correctly from `requirements.txt`.
- **Local wheel builds are unreliable for dependency auditing.** Before trusting
  a locally-built wheel's `Requires-Dist`, delete `*.egg-info` first
  (`rm -rf garmindb.egg-info` then rebuild). Do **not** delete it casually while
  a maintainer editable install depends on it — reinstall (`make setup`) after.
- Verifying the C1 packaging fix by import is only valid if runtime deps are
  installed from `requirements.txt` (not from the wheel's stale `Requires-Dist`).
- Sibling gotcha to the already-documented "venv script staleness" issue: both
  stem from build artifacts in the tree drifting from source.
