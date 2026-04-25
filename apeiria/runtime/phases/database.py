"""Database startup phase."""

from apeiria.db.runtime import ApeiriaDatabase, database_runtime


def run_database_phase() -> ApeiriaDatabase:
    """Initialize or validate the Apeiria SQLite database."""

    database_runtime.ensure_ready()
    return database_runtime
