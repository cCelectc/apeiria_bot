"""SQLite runtime helpers for the Apeiria control-plane database."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator


class ApeiriaDatabase:
    """Own the SQLite path and low-level connection configuration."""

    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = (
            project_root
            if project_root is not None
            else Path(__file__).resolve().parent.parent.parent
        )

    @property
    def project_root(self) -> Path:
        return self._project_root

    def database_path(self) -> Path:
        return self.project_root / "data" / "db" / "apeiria.sqlite3"

    def ensure_parent_dir(self) -> Path:
        parent = self.database_path().parent
        parent.mkdir(parents=True, exist_ok=True)
        return parent

    @contextmanager
    def connect_sync(self) -> Iterator[sqlite3.Connection]:
        self.ensure_parent_dir()
        connection = sqlite3.connect(self.database_path())
        try:
            self._configure_connection(connection)
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @contextmanager
    def transaction_sync(self) -> Iterator[sqlite3.Connection]:
        """Open one SQLite transaction for a logical write operation."""

        with self.connect_sync() as connection:
            yield connection

    def ensure_ready(self) -> None:
        from apeiria.db.schema import ensure_database_ready_sync

        ensure_database_ready_sync(self)

    @staticmethod
    def _configure_connection(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")


database_runtime = ApeiriaDatabase()
