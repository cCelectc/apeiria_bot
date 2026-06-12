from __future__ import annotations

from contextlib import asynccontextmanager
from typing import TYPE_CHECKING

from apeiria.db.base import Base
from apeiria.db.engine import close_engine, get_engine, init_engine

if TYPE_CHECKING:
    from collections.abc import AsyncGenerator
    from pathlib import Path


@asynccontextmanager
async def async_db(
    db_path: Path, *, create_tables: bool = True
) -> AsyncGenerator[None, None]:
    await init_engine(db_path)
    try:
        if create_tables:
            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        yield
    finally:
        await close_engine()
