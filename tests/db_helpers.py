from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

import apeiria.db.models  # noqa: F401
from apeiria.db.base import Base
from apeiria.db.engine import close_engine, get_engine, get_session, init_engine

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path

    from sqlalchemy.ext.asyncio import AsyncSession


@asynccontextmanager
async def async_db(
    db_path: Path, *, create_tables: bool = True
) -> AsyncGenerator[None, None]:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    await init_engine(db_path)
    try:
        if create_tables:
            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        yield
    finally:
        await close_engine()


@asynccontextmanager
async def async_db_session(
    db_path: Path,
) -> AsyncGenerator[AsyncSession, None]:
    async with async_db(db_path), get_session() as session:
        yield session
