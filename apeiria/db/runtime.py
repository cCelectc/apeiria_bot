"""SQLite runtime helpers for the Apeiria control-plane database."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class ApeiriaDatabase:
    """Own the SQLite path and low-level connection configuration."""

    def __init__(self, project_root: Path | None = None) -> None:
        self._project_root = (
            project_root.resolve() if project_root is not None else None
        )
        self._migrations_applied = False

    @property
    def project_root(self) -> Path:
        if self._project_root is not None:
            return self._project_root
        from apeiria.utils.project_context import current_project_root

        return current_project_root()

    def database_path(self) -> Path:
        return self.project_root / "data" / "db" / "apeiria.sqlite3"

    def ensure_parent_dir(self) -> Path:
        parent = self.database_path().parent
        parent.mkdir(parents=True, exist_ok=True)
        return parent

    def alembic_config_path(self) -> Path:
        return self.project_root / "alembic.ini"

    @contextmanager
    def connect_sync(self) -> Iterator[sqlite3.Connection]:
        """Open a synchronous SQLite connection.

        Intended for startup bootstrap and CLI-only paths.
        Runtime database access should use the async engine via
        ``apeiria.db.engine.get_session()``.
        """
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
        """Open one SQLite transaction for a logical write operation.

        Intended for startup bootstrap and CLI-only paths.
        Runtime database access should use the async engine via
        ``apeiria.db.engine.get_session()``.
        """

        with self.connect_sync() as connection:
            connection.execute("BEGIN IMMEDIATE")
            yield connection

    def ensure_ready(self) -> None:
        """Initialize or migrate the control-plane database.

        Uses Alembic migrations when ``alembic.ini`` is present (production
        path).  Falls back to SQLAlchemy ``Base.metadata.create_all()`` when
        the config file is absent (test / first-run bootstrap path).
        Idempotent — safe to call multiple times during a single process.
        """
        if self._migrations_applied:
            return
        self.ensure_parent_dir()
        if self.alembic_config_path().exists():
            self._run_migrations()
        else:
            self._run_legacy_bootstrap()
        self._migrations_applied = True

    def _run_legacy_bootstrap(self) -> None:
        from sqlalchemy import create_engine, inspect

        import apeiria.db.models  # noqa: F401  # register all table models on Base.metadata
        from apeiria.db.base import Base

        sync_url = f"sqlite:///{self.database_path()}"
        engine = create_engine(sync_url)
        try:
            inspector = inspect(engine)
            existing = inspector.get_table_names()
            if not existing:
                Base.metadata.create_all(engine)
        finally:
            engine.dispose()

    def _run_migrations(self) -> None:
        from alembic import command
        from alembic.config import Config

        alembic_cfg = Config(str(self.alembic_config_path()))
        command.upgrade(alembic_cfg, "head")

    @staticmethod
    def _configure_connection(connection: sqlite3.Connection) -> None:
        connection.execute("PRAGMA journal_mode=WAL")
        connection.execute("PRAGMA busy_timeout=5000")
        connection.execute("PRAGMA foreign_keys=ON")


database_runtime = ApeiriaDatabase()
