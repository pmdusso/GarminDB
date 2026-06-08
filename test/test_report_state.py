# test/test_report_state.py
from garmindb.analysis.report_state import (
    MetricDelta,
    load_last_metrics,
    save_metrics,
    compute_deltas,
)


def test_save_and_load_roundtrip(tmp_path):
    path = str(tmp_path / "reports" / "last_metrics.json")
    save_metrics(path, {"wkg": 3.81, "ftp": 325.0}, "2026-06-08T12:00:00")
    loaded = load_last_metrics(path)
    assert loaded["metrics"]["wkg"] == 3.81
    assert loaded["generated"] == "2026-06-08T12:00:00"


def test_load_missing_returns_none(tmp_path):
    assert load_last_metrics(str(tmp_path / "nope.json")) is None


def test_compute_deltas_first_run_has_no_previous():
    deltas = compute_deltas({"wkg": 3.81}, None)
    assert deltas["wkg"].current == 3.81
    assert deltas["wkg"].previous is None
    assert deltas["wkg"].delta is None
    assert deltas["wkg"].has_previous is False


def test_compute_deltas_with_previous():
    last = {"metrics": {"wkg": 3.71}}
    deltas = compute_deltas({"wkg": 3.81}, last)
    assert deltas["wkg"].previous == 3.71
    assert round(deltas["wkg"].delta, 2) == 0.10
    assert deltas["wkg"].has_previous is True
