from __future__ import annotations

import sys
import types
from pathlib import Path

_MEMORY_PATH = (
    Path(__file__).resolve().parent.parent.parent.parent / "apeiria" / "ai" / "memory"
)

if "apeiria.ai.memory" not in sys.modules:
    _stub = types.ModuleType("apeiria.ai.memory")
    _stub.__path__ = [str(_MEMORY_PATH)]
    _stub.__package__ = "apeiria.ai.memory"
    sys.modules["apeiria.ai.memory"] = _stub

import asyncio
from datetime import datetime, timedelta, timezone

from tests.db_helpers import async_db

THIRTY_DAYS = 30
IMPORTANCE_HIGH = 0.8
IMPORTANCE_DECAYED_UPPER = 0.6
IMPORTANCE_FLOOR_LOWER = 0.05


def test_remember_creates_fact(tmp_path: Path) -> None:
    async def _run() -> None:
        from sqlalchemy import select

        from apeiria.ai.memory.service import remember
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_memory import Fact

        async with async_db(tmp_path / "test.db"):
            fact = await remember("user1", "session1", "likes cats", 0.7)
            assert fact.id is not None
            assert fact.user_id == "user1"
            assert fact.session_id == "session1"
            assert fact.content == "likes cats"

            async with get_session() as db:
                row = (
                    await db.execute(select(Fact).where(Fact.id == fact.id))
                ).scalar_one()
                assert row.content == "likes cats"

    asyncio.run(_run())


def test_search_returns_facts(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.ai.memory.service import remember, search
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_settings import AIRuntimeSettings

        async with async_db(tmp_path / "test.db"):
            await remember("user1", "session1", "likes cats")
            await remember("user1", "session1", "hates dogs")

            async with get_session() as db:
                settings = AIRuntimeSettings(id=1)
                db.add(settings)
                await db.commit()
                await db.refresh(settings)

            results = await search("user1", "session1", "cats", settings=settings)
            assert len(results) >= 1
            assert any("cats" in f.content for f in results)

    asyncio.run(_run())


def test_decay_reduces_importance(tmp_path: Path) -> None:
    async def _run() -> None:
        from sqlalchemy import select

        from apeiria.ai.memory.service import remember, search
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_memory import Fact
        from apeiria.db.models.ai_settings import AIRuntimeSettings

        async with async_db(tmp_path / "test.db"):
            fact = await remember(
                "user1", "session1", "important memory", IMPORTANCE_HIGH
            )

            thirty_days_ago = (
                datetime.now(timezone.utc) - timedelta(days=THIRTY_DAYS)
            ).isoformat()
            async with get_session() as db:
                row = (
                    await db.execute(select(Fact).where(Fact.id == fact.id))
                ).scalar_one()
                row.last_reinforced_at = thirty_days_ago
                db.add(row)
                await db.commit()

            async with get_session() as db:
                settings = AIRuntimeSettings(id=1)
                db.add(settings)
                await db.commit()
                await db.refresh(settings)

            results = await search(
                "user1", "session1", "important memory", settings=settings
            )
            assert len(results) == 1
            assert results[0].importance < IMPORTANCE_DECAYED_UPPER
            assert results[0].importance > IMPORTANCE_FLOOR_LOWER

    asyncio.run(_run())


def test_memory_isolation_by_session(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.ai.memory.service import remember, search
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_settings import AIRuntimeSettings

        async with async_db(tmp_path / "test.db"):
            await remember("user1", "session_a", "fact in session A")
            await remember("user1", "session_b", "fact in session B")

            async with get_session() as db:
                settings = AIRuntimeSettings(id=1, memory_isolate_by_session=1)
                db.add(settings)
                await db.commit()
                await db.refresh(settings)

            results = await search("user1", "session_a", "fact", settings=settings)
            assert all(f.session_id == "session_a" for f in results)
            assert len(results) == 1

    asyncio.run(_run())
