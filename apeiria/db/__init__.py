"""Database infrastructure layer."""

from .runtime import ApeiriaDatabase, database_runtime
from .schema import (
    CURRENT_SCHEMA_LINE,
    CURRENT_SCHEMA_VERSION,
    DatabaseSchemaError,
    IncompatibleDatabaseError,
    NewerDatabaseError,
    ensure_database_ready,
    ensure_database_ready_sync,
)

__all__ = [
    "CURRENT_SCHEMA_LINE",
    "CURRENT_SCHEMA_VERSION",
    "ApeiriaDatabase",
    "DatabaseSchemaError",
    "IncompatibleDatabaseError",
    "NewerDatabaseError",
    "database_runtime",
    "ensure_database_ready",
    "ensure_database_ready_sync",
]
