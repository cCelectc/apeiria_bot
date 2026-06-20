from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING, Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

if TYPE_CHECKING:
    from pathlib import Path

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None
_write_semaphore: asyncio.Semaphore | None = None


async def init_engine(database_path: "Path") -> None:
    global _engine, _session_factory, _write_semaphore  # noqa: PLW0603
    url = f"sqlite+aiosqlite:///{database_path}"
    _engine = create_async_engine(
        url,
        echo=False,
        connect_args={"timeout": 5},
    )

    @event.listens_for(_engine.sync_engine, "connect")
    def _set_sqlite_pragma(
        dbapi_connection: Any,
        connection_record: Any,  # noqa: ARG001
    ) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA busy_timeout=5000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.execute("PRAGMA auto_vacuum=INCREMENTAL")
        cursor.close()

    _session_factory = async_sessionmaker(
        _engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )

    _write_semaphore = asyncio.Semaphore(3)


async def close_engine() -> None:
    global _engine, _session_factory, _write_semaphore  # noqa: PLW0603
    if _engine is not None:
        await _engine.dispose()
    _engine = None
    _session_factory = None
    _write_semaphore = None


def get_session() -> AsyncSession:
    if _session_factory is None:
        msg = "Database engine not initialized"
        raise RuntimeError(msg)
    return _session_factory()


def get_engine() -> AsyncEngine:
    if _engine is None:
        msg = "Database engine not initialized"
        raise RuntimeError(msg)
    return _engine


def get_write_semaphore() -> asyncio.Semaphore:
    if _write_semaphore is None:
        msg = "Database engine not initialized"
        raise RuntimeError(msg)
    return _write_semaphore


def rowcount(result: object) -> int:
    return int(getattr(result, "rowcount", 0))
