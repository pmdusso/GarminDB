"""Repository implementations for health data access."""

# Note: HealthRepository is imported at the module level to expose the interface.
# Type-only imports in base.py ensure this works even without the full garmindb
# package loaded.
from .base import HealthRepository

__all__ = ["HealthRepository"]
