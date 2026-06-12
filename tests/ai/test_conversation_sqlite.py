from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from pathlib import Path

    import pytest

OLD_MESSAGE_DAYS = 5
RETENTION_DAYS = 1


def test_conversation_service_uses_sqlite(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

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

    async def scenario() -> None:
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

    asyncio.run(scenario())


def test_conversation_context_summary_uses_dedicated_storage(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

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

    async def scenario() -> None:
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

    asyncio.run(scenario())


def test_recent_target_title_uses_latest_message_excerpt(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

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

    async def scenario() -> None:
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

    asyncio.run(scenario())


def test_conversation_disposition_defaults_and_observed_reads(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

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

    async def scenario() -> None:
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
        assert observed.raw_data_json is None
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

    asyncio.run(scenario())


def test_session_upsert_uses_scene_identity_and_cascades_session_id_updates(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.conversation.models import ChatSessionIdentity
    from apeiria.conversation.service import chat_session_service

    old_time = "2026-04-25T00:00:00"
    with database_runtime.connect_sync() as connection:
        connection.execute(
            """
            INSERT INTO chat_session (
                session_id,
                platform,
                bot_id,
                scene_type,
                scene_id,
                created_at,
                updated_at,
                last_message_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                "session-old",
                "onebot",
                "bot-1",
                "private",
                "user-1",
                old_time,
                old_time,
                old_time,
            ),
        )
        connection.execute(
            """
            INSERT INTO ai_tool_execution (
                execution_id,
                session_id,
                tool_name,
                status,
                created_at
            ) VALUES (?, ?, ?, ?, ?)
            """,
            ("exec-1", "session-old", "tool.test", "success", old_time),
        )

    identity = ChatSessionIdentity(
        session_id="session-new",
        platform="onebot",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id="user-1",
    )

    async def scenario() -> None:
        row = await chat_session_service.ensure_session(identity)
        assert row.session_id == "session-new"

    asyncio.run(scenario())

    with database_runtime.connect_sync() as connection:
        session_rows = connection.execute(
            """
            SELECT session_id
            FROM chat_session
            WHERE platform = ? AND bot_id = ? AND scene_type = ? AND scene_id = ?
            """,
            ("onebot", "bot-1", "private", "user-1"),
        ).fetchall()
        execution_session_id = connection.execute(
            """
            SELECT session_id
            FROM ai_tool_execution
            WHERE execution_id = ?
            """,
            ("exec-1",),
        ).fetchone()

    assert session_rows == [("session-new",)]
    assert execution_session_id == ("session-new",)


def test_conversation_retention_deletes_sqlite_rows(
    tmp_path: Path,
) -> None:
    from apeiria.ai.retention import AIRetentionService
    from apeiria.db.base import Base
    from apeiria.db.engine import close_engine, get_engine, get_session, init_engine
    from apeiria.db.models.conversation import ChatMessage, ChatSession

    db_path = tmp_path / "test.db"

    old_epoch_ms = int(
        (datetime.now(timezone.utc) - timedelta(days=OLD_MESSAGE_DAYS)).timestamp()
        * 1000
    )
    new_epoch_ms = int(datetime.now(timezone.utc).timestamp() * 1000)

    async def run() -> None:
        await init_engine(db_path)
        try:
            async with get_engine().begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

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
        finally:
            await close_engine()

    asyncio.run(run())
