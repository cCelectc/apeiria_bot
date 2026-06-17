"""Database infrastructure layer."""

from .runtime import ApeiriaDatabase, database_runtime
from .schema_constants import (
    CURRENT_SCHEMA_LINE,
    CURRENT_SCHEMA_VERSION,
    DatabaseSchemaError,
    IncompatibleDatabaseError,
    UnsupportedDatabaseVersionError,
)

__all__ = [
    "CURRENT_SCHEMA_LINE",
    "CURRENT_SCHEMA_VERSION",
    "ApeiriaDatabase",
    "DatabaseSchemaError",
    "IncompatibleDatabaseError",
    "UnsupportedDatabaseVersionError",
    "database_runtime",
]
