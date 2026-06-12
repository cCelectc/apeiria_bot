from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pathlib import Path

OLD_MESSAGE_DAYS = 5
RETENTION_DAYS = 1


def test_conversation_service_uses_sqlite(
    tmp_path: Path,
) -> None:
    from apeiria.db.models.conversation import ChatMessage, ChatSession  # noqa: F401
    from tests.db_helpers import async_db

    db_path = tmp_path / "test.db"

    async def run() -> None:
        async with async_db(db_path):
            from apeiria.conversation.contracts import ChatMessageCreate
            from apeiria.conversation.models import ChatSessionIdentity
            from apeiria.conversation.service import chat_session_service

            identity = ChatSessionIdentity(
                session_id="onebot:bot-1:private:user-1",
                platform="onebot",
                bot_id="bot-1",
                scene_type="private",
                scene_id="user-1",
                subject_id="user-1",
            )

            user_message = await chat_session_service.append_message(
                identity,
                ChatMessageCreate(
                    author_role="user",
                    author_id="user-1",
                    text_content="hello",
                    raw_data={"message_id": 1},
                ),
            )
            await chat_session_service.append_message(
                identity,
                ChatMessageCreate(
                    author_role="assistant",
                    author_id="bot-1",
                    text_content="hi",
                ),
            )
            turns = await chat_session_service.list_recent_messages(
                identity,
                max_messages=10,
            )
            assert [turn.text_content for turn in turns] == ["hello", "hi"]
            assert turns[0].message_id == user_message.message_id

            sessions = await chat_session_service.list_recent_sessions(limit=10)
            assert [session.session_id for session in sessions] == [identity.session_id]

            user_ids = await chat_session_service.list_recent_user_ids_for_session(
                session_id=identity.session_id,
            )
            assert user_ids == ["user-1"]

    asyncio.run(run())


def test_conversation_context_summary_uses_dedicated_storage(
    tmp_path: Path,
) -> None:
    from apeiria.db.models.conversation import (  # noqa: F401
        ChatMessage,
        ChatSession,
        ChatSessionContextSummary,
    )
    from tests.db_helpers import async_db

    db_path = tmp_path / "test.db"

    async def run() -> None:
        async with async_db(db_path):
            from apeiria.conversation.models import ChatSessionIdentity
            from apeiria.conversation.service import chat_session_service

            identity = ChatSessionIdentity(
                session_id="onebot:bot-1:private:user-1",
                platform="onebot",
                bot_id="bot-1",
                scene_type="private",
                scene_id="user-1",
                subject_id="user-1",
            )
            first_boundary = datetime(2026, 5, 16, 1, 0, tzinfo=timezone.utc)
            second_boundary = datetime(2026, 5, 16, 2, 0, tzinfo=timezone.utc)

            await chat_session_service.store_session_summary(
                identity,
                summary="first summary",
                source_until_message_id="msg-1",
                source_until_created_at=first_boundary,
            )
            await chat_session_service.store_session_summary(
                identity,
                summary="second summary",
                source_until_message_id="msg-2",
                source_until_created_at=second_boundary,
            )

            summary = await chat_session_service.load_session_summary(identity)
            sessions = await chat_session_service.list_recent_sessions(limit=10)

            assert summary is not None
            assert summary.summary_text == "second summary"
            assert summary.source_until_message_id == "msg-2"
            assert summary.source_until_created_at == second_boundary
            assert [session.session_id for session in sessions] == [identity.session_id]

    asyncio.run(run())


def test_recent_target_title_uses_latest_message_excerpt(
    tmp_path: Path,
) -> None:
    from apeiria.db.models.conversation import ChatMessage, ChatSession  # noqa: F401
    from tests.db_helpers import async_db

    db_path = tmp_path / "test.db"

    async def run() -> None:
        async with async_db(db_path):
            from apeiria.app.ai.sessions.targets import list_recent_targets
            from apeiria.conversation.contracts import ChatMessageCreate
            from apeiria.conversation.models import ChatSessionIdentity
            from apeiria.conversation.service import chat_session_service

            identity = ChatSessionIdentity(
                session_id="onebot:bot-1:private:user-1",
                platform="onebot",
                bot_id="bot-1",
                scene_type="private",
                scene_id="user-1",
                subject_id="user-1",
            )

            await chat_session_service.append_message(
                identity,
                ChatMessageCreate(
                    author_role="user",
                    author_id="user-1",
                    text_content="latest useful message",
                ),
            )

            targets = await list_recent_targets(limit=1)

            assert targets[0].target_type == "scene"
            assert targets[0].title == "latest useful message"

    asyncio.run(run())


def test_conversation_disposition_defaults_and_observed_reads(
    tmp_path: Path,
) -> None:
    from apeiria.db.models.conversation import ChatMessage, ChatSession  # noqa: F401
    from tests.db_helpers import async_db

    db_path = tmp_path / "test.db"

    async def run() -> None:
        async with async_db(db_path):
            from apeiria.conversation.contracts import ChatMessageCreate
            from apeiria.conversation.models import ChatSessionIdentity
            from apeiria.conversation.service import chat_session_service

            identity = ChatSessionIdentity(
                session_id="onebot:bot-1:group:group-1",
                platform="onebot",
                bot_id="bot-1",
                scene_type="group",
                scene_id="group-1",
                subject_id=None,
            )

            active = await chat_session_service.append_message(
                identity,
                ChatMessageCreate(
                    author_role="user",
                    author_id="user-1",
                    text_content="direct hello",
                    raw_data={"message_id": 1},
                ),
            )
            observed = await chat_session_service.append_observed_turn(
                identity,
                author_id="user-2",
                text_content="ambient context",
                platform_message_id="platform-observed",
                content={
                    "segments": [
                        {"type": "text", "text": "ambient context"},
                        {
                            "type": "image",
                            "url": "https://cdn.example.test/img.png",
                            "file": "img.png",
                        },
                    ],
                    "plain_text": "ambient context",
                },
                meta={"policy_reason": "ambient"},
                raw_data={"secret": "not persisted by default"},
            )
            tool = await chat_session_service.append_message(
                identity,
                ChatMessageCreate(
                    author_role="tool",
                    author_id="memory.search",
                    message_kind="tool",
                    text_content="tool result",
                    turn_disposition="tool",
                ),
            )

            assert active.turn_disposition == "active"
            assert observed.turn_disposition == "observed"
            assert tool.turn_disposition == "tool"

            turns = await chat_session_service.list_recent_messages(
                identity,
                max_messages=10,
            )
            assert [turn.turn_disposition for turn in turns] == [
                "active",
                "observed",
                "tool",
            ]
            assert turns[1].is_observed_context is True
            assert turns[1].content == {
                "segments": [
                    {"type": "text", "text": "ambient context"},
                    {
                        "type": "image",
                        "url": "https://cdn.example.test/img.png",
                        "file": "img.png",
                    },
                ],
                "plain_text": "ambient context",
            }

            detail = await chat_session_service.list_messages_for_session(
                session_id=identity.session_id,
                limit=10,
            )
            assert [message.turn_disposition for message in detail] == [
                "active",
                "observed",
                "tool",
            ]
            assert detail[1].is_observed_context is True
            assert detail[1].raw_data is None

    asyncio.run(run())


def test_session_upsert_uses_scene_identity_and_cascades_session_id_updates(
    tmp_path: Path,
) -> None:
    from apeiria.db.base import _epoch_ms
    from apeiria.db.engine import get_session
    from apeiria.db.models.conversation import ChatSession
    from tests.db_helpers import async_db

    db_path = tmp_path / "test.db"

    async def run() -> None:
        async with async_db(db_path):
            old_ms = _epoch_ms() - 86_400_000

            async with get_session() as session:
                session.add(
                    ChatSession(
                        session_id="session-old",
                        platform="onebot",
                        bot_id="bot-1",
                        scene_type="private",
                        scene_id="user-1",
                        last_message_at=old_ms,
                        created_at=old_ms,
                        updated_at=old_ms,
                    )
                )
                await session.commit()

            from apeiria.conversation.models import ChatSessionIdentity
            from apeiria.conversation.service import chat_session_service

            identity = ChatSessionIdentity(
                session_id="session-new",
                platform="onebot",
                bot_id="bot-1",
                scene_type="private",
                scene_id="user-1",
                subject_id="user-1",
            )

            row = await chat_session_service.ensure_session(identity)
            assert row.session_id == "session-new"

            from sqlalchemy import select

            async with get_session() as session:
                result = await session.execute(
                    select(ChatSession.session_id).where(
                        ChatSession.platform == "onebot",
                        ChatSession.bot_id == "bot-1",
                        ChatSession.scene_type == "private",
                        ChatSession.scene_id == "user-1",
                    )
                )
                session_ids = result.scalars().all()

            assert session_ids == ["session-new"]

    asyncio.run(run())


def test_conversation_retention_deletes_sqlite_rows(
    tmp_path: Path,
) -> None:
    from apeiria.ai.retention import AIRetentionService
    from apeiria.db.engine import get_session
    from apeiria.db.models.conversation import ChatMessage, ChatSession
    from tests.db_helpers import async_db

    db_path = tmp_path / "test.db"

    old_epoch_ms = int(
        (datetime.now(timezone.utc) - timedelta(days=OLD_MESSAGE_DAYS)).timestamp()
        * 1000
    )
    new_epoch_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    async def run() -> None:
        async with async_db(db_path):
            async with get_session() as session:
                session.add(
                    ChatSession(
                        session_id="session-old",
                        platform="onebot",
                        bot_id="bot-1",
                        scene_type="private",
                        scene_id="user-1",
                        last_message_at=old_epoch_ms,
                        created_at=old_epoch_ms,
                        updated_at=old_epoch_ms,
                    )
                )
                await session.flush()
                session.add(
                    ChatMessage(
                        message_id="msg-old",
                        session_id="session-old",
                        author_role="user",
                        author_id="user-1",
                        message_kind="text",
                        text_content="old",
                        turn_disposition="active",
                        directed_to_bot=0,
                        mentions_bot=0,
                        has_media=0,
                        created_at=old_epoch_ms,
                    )
                )
                session.add(
                    ChatMessage(
                        message_id="msg-new",
                        session_id="session-old",
                        author_role="user",
                        author_id="user-1",
                        message_kind="text",
                        text_content="new",
                        turn_disposition="active",
                        directed_to_bot=0,
                        mentions_bot=0,
                        has_media=0,
                        created_at=new_epoch_ms,
                    )
                )
                await session.commit()

            result = await AIRetentionService().cleanup_conversations(
                conversation_retention_days=RETENTION_DAYS,
                raw_event_retention_days=RETENTION_DAYS,
            )

            async with get_session() as session:
                from sqlalchemy import select

                rows = (
                    (
                        await session.execute(
                            select(ChatMessage.message_id).order_by(
                                ChatMessage.message_id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )

            assert result.deleted_messages == 1
            assert result.deleted_sessions == 0
            assert result.cleared_raw_payloads == 0
            assert rows == ["msg-new"]

    asyncio.run(run())
