"""Persist key report metrics between runs to compute deltas.

State file shape: {"generated": "<iso>", "metrics": {name: value, ...}}
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Dict, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricDelta:
    """A metric's current value vs the previous report's value."""

    current: float
    previous: Optional[float]

    @property
    def delta(self) -> Optional[float]:
        """Derived: current - previous, or None on first run.

        Computed (not stored) so it can never drift out of sync with
        ``current``/``previous``.
        """
        if self.previous is None:
            return None
        return self.current - self.previous

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
    logger.debug("Saved %d metric(s) to %s", len(metrics), path)


def merge_metrics(
    previous: Optional[dict], current: Dict[str, float]
) -> Dict[str, float]:
    """Carry forward last-known values for metrics absent this run.

    A metric that is None this run is dropped from ``current`` upstream, so
    naively persisting ``current`` would destroy its baseline after a single
    gap. Merging the new snapshot onto the previous metrics keeps the baseline
    alive while still letting present metrics update.
    """
    prev_metrics = (previous or {}).get("metrics", {})
    merged = dict(prev_metrics)
    merged.update(current)
    carried = set(prev_metrics) - set(current)
    if carried:
        logger.debug("Carried forward %d stale metric(s): %s",
                     len(carried), sorted(carried))
    return merged


def compute_deltas(
    current: Dict[str, float], last: Optional[dict]
) -> Dict[str, MetricDelta]:
    """Compute per-metric deltas vs the previous report (None-safe)."""
    prev_metrics = (last or {}).get("metrics", {})
    result: Dict[str, MetricDelta] = {}
    for name, value in current.items():
        prev = prev_metrics.get(name)
        result[name] = MetricDelta(current=value, previous=prev)
    return result
