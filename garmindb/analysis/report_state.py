"""Persist key report metrics between runs to compute deltas.

State file shape: {"generated": "<iso>", "metrics": {name: value, ...}}
"""

import json
import os
from dataclasses import dataclass
from typing import Dict, Optional


@dataclass
class MetricDelta:
    """A metric's current value vs the previous report's value."""

    current: float
    previous: Optional[float]
    delta: Optional[float]  # current - previous, or None on first run

    @property
    def has_previous(self) -> bool:
        return self.previous is not None


def load_last_metrics(path: str) -> Optional[dict]:
    """Load the previous report's state, or None if absent."""
    if not os.path.exists(path):
        return None
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_metrics(path: str, metrics: Dict[str, float], generated_iso: str) -> None:
    """Write the current report's key metrics for next time."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    payload = {"generated": generated_iso, "metrics": metrics}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)


def compute_deltas(
    current: Dict[str, float], last: Optional[dict]
) -> Dict[str, MetricDelta]:
    """Compute per-metric deltas vs the previous report (None-safe)."""
    prev_metrics = (last or {}).get("metrics", {})
    result: Dict[str, MetricDelta] = {}
    for name, value in current.items():
        prev = prev_metrics.get(name)
        delta = (value - prev) if prev is not None else None
        result[name] = MetricDelta(current=value, previous=prev, delta=delta)
    return result
