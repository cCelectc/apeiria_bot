from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path


def test_get_score_creates_default(tmp_path: Path) -> None:
    async def _run() -> None:
        from sqlalchemy import select

        from apeiria.ai.relationship.service import get_score
        from apeiria.db.engine import get_session
        from apeiria.db.models.ai_settings import AIRuntimeSettings

        async with async_db(tmp_path / "test.db"):
            async with get_session() as db:
                db.add(AIRuntimeSettings(id=1))
                await db.commit()

            async with get_session() as db:
                settings = (
                    await db.execute(
                        select(AIRuntimeSettings).where(AIRuntimeSettings.id == 1)
                    )
                ).scalar_one()

            score = await get_score("user1", "session1", settings=settings)
            assert score.score == 50  # noqa: PLR2004
            assert score.user_id == "user1"

    asyncio.run(_run())


def test_adjust_clamp(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.ai.relationship.service import adjust

        async with async_db(tmp_path / "test.db"):
            score = await adjust("user1", "session1", 60)
            assert score.score == 100  # noqa: PLR2004
            score = await adjust("user1", "session1", -200)
            assert score.score == 0

    asyncio.run(_run())


def test_emotion_projection() -> None:
    from apeiria.ai.relationship.service import project_emotion

    assert project_emotion(10) == "冷淡"
    assert project_emotion(30) == "戒备"
    assert project_emotion(50) == "普通"
    assert project_emotion(70) == "亲近"
    assert project_emotion(90) == "亲密"
