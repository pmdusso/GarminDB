"""Performance goal configuration (FTP, weight/W-kg targets, race)."""

import json
import logging
import os
from dataclasses import dataclass
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class PerformanceTargets:
    """User-configured performance targets. All fields optional."""

    ftp_watts: Optional[float] = None
    weight_target_kg: Optional[float] = None
    wkg_target: Optional[float] = None
    race_name: Optional[str] = None
    race_date: Optional[str] = None


def _coerce_float(data: dict, key: str) -> Optional[float]:
    """Coerce a config field to float, or None if absent.

    A malformed value (e.g. "abc") raises a clear ValueError naming the
    offending key, failing loudly at load time instead of silently
    producing a garbage W/kg downstream.
    """
    value = data.get(key)
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError) as err:
        logger.error("Invalid numeric value for %s: %r", key, value)
        raise ValueError(
            f"Invalid numeric value for {key!r} in performance targets: "
            f"{value!r}"
        ) from err


def load_performance_targets(path: Optional[str] = None) -> PerformanceTargets:
    """Load targets from JSON. Returns empty defaults if file is missing.

    Args:
        path: Path to performance_targets.json. Defaults to
            ~/.GarminDb/performance_targets.json.

    Returns:
        PerformanceTargets (empty if file absent).

    Raises:
        ValueError: If a numeric field holds a non-numeric value.
    """
    if path is None:
        path = os.path.join(
            os.path.expanduser("~"), ".GarminDb", "performance_targets.json"
        )
    if not os.path.exists(path):
        logger.debug("No performance targets at %s; using empty defaults", path)
        return PerformanceTargets()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    targets = PerformanceTargets(
        ftp_watts=_coerce_float(data, "ftp_watts"),
        weight_target_kg=_coerce_float(data, "weight_target_kg"),
        wkg_target=_coerce_float(data, "wkg_target"),
        race_name=data.get("race_name"),
        race_date=data.get("race_date"),
    )
    logger.debug("Loaded performance targets from %s", path)
    return targets
