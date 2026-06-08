# test/test_performance_targets.py
import json

import pytest

from garmindb.analysis.performance_targets import (
    PerformanceTargets,
    load_performance_targets,
)


def test_missing_file_returns_empty_defaults():
    t = load_performance_targets("/nonexistent/targets.json")
    assert isinstance(t, PerformanceTargets)
    assert t.ftp_watts is None
    assert t.wkg_target is None


def test_loads_values(tmp_path):
    p = tmp_path / "targets.json"
    p.write_text(json.dumps({
        "ftp_watts": 325,
        "weight_target_kg": 80,
        "wkg_target": 4.0,
        "race_name": "L'Etape Campos do Jordao",
        "race_date": "2026-09-27",
    }))
    t = load_performance_targets(str(p))
    assert t.ftp_watts == 325
    assert t.weight_target_kg == 80
    assert t.wkg_target == 4.0
    assert t.race_name == "L'Etape Campos do Jordao"


def test_malformed_numeric_value_raises_clear_error(tmp_path):
    # A non-numeric numeric field must fail loudly at load time, not silently
    # produce a garbage W/kg later in the report.
    p = tmp_path / "targets.json"
    p.write_text(json.dumps({"ftp_watts": "abc"}))
    with pytest.raises(ValueError) as exc:
        load_performance_targets(str(p))
    assert "ftp_watts" in str(exc.value)


def test_numeric_strings_are_coerced(tmp_path):
    # Numeric values supplied as strings are coerced to float, not rejected.
    p = tmp_path / "targets.json"
    p.write_text(json.dumps({"ftp_watts": "325", "wkg_target": "4.0"}))
    t = load_performance_targets(str(p))
    assert t.ftp_watts == 325.0
    assert t.wkg_target == 4.0
