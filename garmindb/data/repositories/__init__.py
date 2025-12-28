"""Repository implementations for health data access."""

# Note: HealthRepository is imported at the module level to expose the interface.
# Type-only imports in base.py ensure this works even without the full garmindb
# package loaded.
from .base import HealthRepository

# SQLiteHealthRepository has dependencies on other garmindb modules, so we
# import it lazily to avoid import errors when the repositories module is
# loaded in isolation (e.g., by test_repositories.py which manipulates sys.path)
try:
    from .sqlite import SQLiteHealthRepository
except ImportError:
    # Will be available when imported through the main garmindb package
    SQLiteHealthRepository = None

__all__ = ["HealthRepository", "SQLiteHealthRepository"]
