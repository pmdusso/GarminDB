"""Performance goal configuration (FTP, weight/W-kg targets, race)."""

import json
import os
from dataclasses import dataclass
from typing import Optional


@dataclass
class PerformanceTargets:
    """User-configured performance targets. All fields optional."""

    ftp_watts: Optional[float] = None
    weight_target_kg: Optional[float] = None
    wkg_target: Optional[float] = None
    race_name: Optional[str] = None
    race_date: Optional[str] = None


def load_performance_targets(path: Optional[str] = None) -> PerformanceTargets:
    """Load targets from JSON. Returns empty defaults if file is missing.

    Args:
        path: Path to performance_targets.json. Defaults to
            ~/.GarminDb/performance_targets.json.

    Returns:
        PerformanceTargets (empty if file absent).
    """
    if path is None:
        path = os.path.join(
            os.path.expanduser("~"), ".GarminDb", "performance_targets.json"
        )
    if not os.path.exists(path):
        return PerformanceTargets()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return PerformanceTargets(
        ftp_watts=data.get("ftp_watts"),
        weight_target_kg=data.get("weight_target_kg"),
        wkg_target=data.get("wkg_target"),
        race_name=data.get("race_name"),
        race_date=data.get("race_date"),
    )
