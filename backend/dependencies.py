"""
dependencies.py
----------------
FastAPI dependency-injection wiring. Routers depend on `get_repository()`
rather than importing a concrete class, so swapping the storage backend
(CSV -> Postgres -> Timescale, etc.) is a one-line change here.
"""

from backend.data_access.repository import CsvDataRepository

# Singleton instance shared across requests (thread-safe reads; writes are
# lock-protected inside the repository). For a real deployment this would
# instead be a connection pool to a database.
_repository = CsvDataRepository()


def get_repository() -> CsvDataRepository:
    return _repository
