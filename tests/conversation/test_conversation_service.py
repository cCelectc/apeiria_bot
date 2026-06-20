from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path


def test_ensure_session_creates_new(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.conversation.service import ensure_session

        async with async_db(tmp_path / "test.db"):
            session = await ensure_session("onebot:group:123", "onebot", "group", "123")
            assert session.id == "onebot:group:123"
            assert session.platform == "onebot"
            session2 = await ensure_session(
                "onebot:group:123", "onebot", "group", "123"
            )
            assert session2.id == session.id

    asyncio.run(_run())


def test_append_and_load_messages(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.conversation.service import (
            append_message,
            ensure_session,
            load_recent,
        )

        async with async_db(tmp_path / "test.db"):
            await ensure_session("s1", "p", "g", "1")
            await append_message("s1", "user", "hello", user_id="u1")
            await append_message("s1", "assistant", "hi there")
            msgs = await load_recent("s1")
            assert len(msgs) == 2  # noqa: PLR2004
            assert msgs[0].role == "user"
            assert msgs[1].role == "assistant"

    asyncio.run(_run())


def test_load_recent_limit(tmp_path: Path) -> None:
    async def _run() -> None:
        from apeiria.conversation.service import (
            append_message,
            ensure_session,
            load_recent,
        )

        async with async_db(tmp_path / "test.db"):
            await ensure_session("s1", "p", "g", "1")
            for i in range(10):
                await append_message("s1", "user", f"msg {i}")
            msgs = await load_recent("s1", limit=5)
            assert len(msgs) == 5  # noqa: PLR2004
            assert msgs[0].content == "msg 5"

    asyncio.run(_run())


def test_compaction_boundary(tmp_path: Path) -> None:
    async def _run() -> None:
        from sqlalchemy import select

        from apeiria.conversation.service import (
            append_message,
            ensure_session,
            load_recent,
        )
        from apeiria.db.engine import get_session
        from apeiria.db.models.conversation import Session

        async with async_db(tmp_path / "test.db"):
            await ensure_session("s1", "p", "g", "1")
            await append_message("s1", "user", "old msg 1")
            m2 = await append_message("s1", "user", "old msg 2")
            await append_message("s1", "system", "Summary of earlier conversation")
            await append_message("s1", "user", "new msg 1")
            await append_message("s1", "user", "new msg 2")

            async with get_session() as db:
                s = (
                    await db.execute(select(Session).where(Session.id == "s1"))
                ).scalar_one()
                s.last_compacted_message_id = m2.id
                await db.commit()

            msgs = await load_recent("s1")
            roles = [m.role for m in msgs]
            assert "system" in roles
            contents = [m.content for m in msgs]
            assert "old msg 1" not in contents
            assert "old msg 2" not in contents
            assert "new msg 1" in contents
            assert "new msg 2" in contents

    asyncio.run(_run())
