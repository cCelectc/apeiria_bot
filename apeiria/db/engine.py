from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

from urllib.parse import urlparse

from nonebot.log import logger
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

_DEFAULT_DB_PATH = "data/apeiria.db"
_DEFAULT_BUSY_TIMEOUT = 5000


class DbWriteGate:
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker
        self._write_lock = asyncio.Lock()

    @asynccontextmanager
    async def write(self) -> AsyncIterator[AsyncSession]:
        async with (
            self._write_lock,
            self._sessionmaker() as session,
            session.begin(),
        ):
            yield session

    @asynccontextmanager
    async def read(self) -> AsyncIterator[AsyncSession]:
        async with self._sessionmaker() as session:
            yield session


class ApeiriaDatabase:
    def __init__(
        self,
        url: str | None = None,
        *,
        busy_timeout_ms: int = _DEFAULT_BUSY_TIMEOUT,
    ) -> None:
        if url is None:
            url = f"sqlite+aiosqlite:///{_DEFAULT_DB_PATH}"
        self._url = url
        self._busy_timeout_ms = busy_timeout_ms
        self._engine: AsyncEngine | None = None
        self._sessionmaker: async_sessionmaker | None = None
        self._gate: DbWriteGate | None = None

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise RuntimeError("Database not initialized")  # noqa: TRY003
        return self._engine

    @property
    def gate(self) -> DbWriteGate:
        if self._gate is None:
            raise RuntimeError("Database not initialized")  # noqa: TRY003
        return self._gate

    async def init(self) -> None:
        parsed = urlparse(self._url)
        if parsed.scheme in ("sqlite+aiosqlite", "sqlite"):
            db_path = Path(parsed.path.lstrip("/"))
            db_path.parent.mkdir(parents=True, exist_ok=True)

        self._engine = create_async_engine(self._url, echo=False)
        self._sessionmaker = async_sessionmaker(
            self._engine, class_=AsyncSession, expire_on_commit=False
        )
        self._gate = DbWriteGate(self._sessionmaker)

        @event.listens_for(self._engine.sync_engine, "connect")
        def _on_connect(dbapi_connection, _connection_record):  # noqa: ANN001
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute(f"PRAGMA busy_timeout={self._busy_timeout_ms}")
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.close()

        logger.info("Database initialized at {}", db_path)

    async def close(self) -> None:
        if self._engine is not None:
            await self._engine.dispose()
            self._engine = None
            self._sessionmaker = None
            self._gate = None
            logger.info("Database connection closed")


_db: ApeiriaDatabase | None = None


def get_db() -> ApeiriaDatabase:
    if _db is None:
        raise RuntimeError("Database not initialized")  # noqa: TRY003
    return _db


async def init_db(url: str | None = None) -> ApeiriaDatabase:
    global _db  # noqa: PLW0603
    _db = ApeiriaDatabase(url)
    await _db.init()
    return _db


async def close_db() -> None:
    global _db  # noqa: PLW0603
    if _db is not None:
        await _db.close()
        _db = None
