# test/test_report_state.py
from garmindb.analysis.report_state import (
    MetricDelta,
    load_last_metrics,
    save_metrics,
    compute_deltas,
    merge_metrics,
)


def test_metric_delta_is_computed_from_current_and_previous():
    # delta must be a derived invariant, not a stored field.
    d = MetricDelta(current=3.81, previous=3.71)
    assert round(d.delta, 2) == 0.10
    assert d.has_previous is True


def test_metric_delta_is_none_without_previous():
    d = MetricDelta(current=3.81, previous=None)
    assert d.delta is None
    assert d.has_previous is False


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


def test_merge_metrics_carries_forward_absent_metrics():
    # A one-run gap (vo2max absent this run) must NOT destroy the baseline.
    previous = {"metrics": {"wkg": 3.71, "vo2max": 56.0}}
    current = {"wkg": 3.81}
    merged = merge_metrics(previous, current)
    assert merged["wkg"] == 3.81           # updated
    assert merged["vo2max"] == 56.0        # carried forward


def test_merge_metrics_none_previous_returns_current():
    merged = merge_metrics(None, {"wkg": 3.81})
    assert merged == {"wkg": 3.81}


def test_merge_metrics_does_not_mutate_inputs():
    previous = {"metrics": {"vo2max": 56.0}}
    current = {"wkg": 3.81}
    merge_metrics(previous, current)
    assert previous == {"metrics": {"vo2max": 56.0}}
    assert current == {"wkg": 3.81}
