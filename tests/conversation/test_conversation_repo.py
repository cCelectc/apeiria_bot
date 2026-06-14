"""Tests for conversation session identity, messages, and summaries."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

import pytest

from apeiria.conversation.contracts import ChatMessageCreate
from apeiria.conversation.identity import build_chat_session_identity
from apeiria.conversation.service import ChatSessionService
from tests.db_helpers import async_db

if TYPE_CHECKING:
    from pathlib import Path


class TestBuildIdentity:
    def test_private_chat(self) -> None:
        identity = build_chat_session_identity(
            platform="qq", bot_id="bot1", user_id="u1"
        )
        assert identity.scene_type == "private"
        assert identity.scene_id == "u1"
        assert identity.session_id.startswith("session_")

    def test_group_chat(self) -> None:
        identity = build_chat_session_identity(
            platform="qq", bot_id="bot1", user_id="u1", group_id="g1"
        )
        assert identity.scene_type == "group"
        assert identity.scene_id == "g1"

    def test_different_inputs_produce_different_ids(self) -> None:
        a = build_chat_session_identity(platform="qq", bot_id="b", user_id="u1")
        b = build_chat_session_identity(platform="qq", bot_id="b", user_id="u2")
        assert a.session_id != b.session_id


class TestChatSessionService:
    @pytest.mark.anyio
    async def test_ensure_and_list_sessions(self, tmp_path: Path) -> None:
        async with async_db(tmp_path / "test.db"):
            svc = ChatSessionService()
            identity = build_chat_session_identity(
                platform="qq", bot_id="b1", user_id="u1", group_id="g1"
            )
            row = await svc.ensure_session(identity)
            assert row.session_id == identity.session_id
            assert row.platform == "qq"

            await svc.ensure_session(
                build_chat_session_identity(platform="qq", bot_id="b", user_id="u2")
            )
            sessions = await svc.list_recent_sessions(limit=10)
            assert len(sessions) == 2  # noqa: PLR2004

    @pytest.mark.anyio
    async def test_append_and_list_messages(self, tmp_path: Path) -> None:
        async with async_db(tmp_path / "test.db"):
            svc = ChatSessionService()
            identity = build_chat_session_identity(
                platform="qq", bot_id="b1", user_id="u1"
            )
            await svc.ensure_session(identity)

            msg = await svc.append_message(
                identity,
                ChatMessageCreate(
                    author_role="user",
                    author_id="u1",
                    text_content="Hello!",
                    message_kind="text",
                ),
            )
            assert msg.author_role == "user"
            assert msg.text_content == "Hello!"

            msgs = await svc.list_recent_messages(identity, max_messages=10)
            assert len(msgs) == 1
            assert msgs[0].text_content == "Hello!"

    @pytest.mark.anyio
    async def test_summary_store_load_clear(self, tmp_path: Path) -> None:
        async with async_db(tmp_path / "test.db"):
            svc = ChatSessionService()
            identity = build_chat_session_identity(
                platform="qq", bot_id="b1", user_id="u1"
            )
            await svc.ensure_session(identity)
            msg = await svc.append_message(
                identity,
                ChatMessageCreate(
                    author_role="user",
                    author_id="u1",
                    text_content="Hi",
                    message_kind="text",
                ),
            )
            now = datetime.now(timezone.utc)
            await svc.store_session_summary(
                identity,
                summary="User greeted the bot",
                source_until_message_id=msg.message_id,
                source_until_created_at=now,
            )
            summary = await svc.load_session_summary(identity)
            assert summary is not None
            assert summary.summary_text == "User greeted the bot"

            await svc.clear_session_summary(identity)
            assert await svc.load_session_summary(identity) is None
