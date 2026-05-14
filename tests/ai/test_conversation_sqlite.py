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

    from apeiria.conversation.models import ChatSessionIdentity
    from apeiria.conversation.service import (
        ChatMessageCreate,
        chat_session_service,
    )

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
        await chat_session_service.store_summary_text(
            identity,
            summary="User greeted the bot.",
        )

        turns = await chat_session_service.list_recent_messages(
            identity,
            max_messages=10,
        )
        assert [turn.text_content for turn in turns] == ["hello", "hi"]
        assert turns[0].message_id == user_message.message_id

        sessions = await chat_session_service.list_recent_sessions(limit=10)
        assert [session.session_id for session in sessions] == [identity.session_id]
        assert sessions[0].summary_text == "User greeted the bot."

        user_ids = await chat_session_service.list_recent_user_ids_for_session(
            session_id=identity.session_id,
        )
        assert user_ids == ["user-1"]

    asyncio.run(scenario())


def test_conversation_disposition_defaults_and_observed_reads(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.conversation.models import ChatSessionIdentity
    from apeiria.conversation.service import (
        ChatMessageCreate,
        chat_session_service,
    )

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
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(database_runtime, "_project_root", tmp_path)
    database_runtime.ensure_ready()

    from apeiria.ai.retention import AIRetentionService

    old_time = (
        datetime.now(timezone.utc) - timedelta(days=OLD_MESSAGE_DAYS)
    ).isoformat(timespec="seconds")
    new_time = datetime.now(timezone.utc).isoformat(timespec="seconds")
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
        session_pk = connection.execute(
            "SELECT id FROM chat_session WHERE session_id = ?",
            ("session-old",),
        ).fetchone()[0]
        connection.execute(
            """
            INSERT INTO chat_message (
                message_id,
                session_pk,
                author_role,
                author_id,
                message_kind,
                text_content,
                raw_data_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("msg-old", session_pk, "user", "user-1", "text", "old", "{}", old_time),
        )
        connection.execute(
            """
            INSERT INTO chat_message (
                message_id,
                session_pk,
                author_role,
                author_id,
                message_kind,
                text_content,
                raw_data_json,
                created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("msg-new", session_pk, "user", "user-1", "text", "new", "{}", new_time),
        )

    result = AIRetentionService().cleanup_conversations(
        conversation_retention_days=RETENTION_DAYS,
        raw_event_retention_days=RETENTION_DAYS,
    )

    with database_runtime.connect_sync() as connection:
        rows = connection.execute(
            """
            SELECT message_id, raw_data_json
            FROM chat_message
            ORDER BY message_id
            """
        ).fetchall()
    assert result.deleted_messages == 1
    assert result.deleted_sessions == 0
    assert result.cleared_raw_payloads == 0
    assert rows == [("msg-new", "{}")]
