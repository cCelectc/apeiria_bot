"""SQLite persistence for chat sessions and messages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from sqlite3 import Connection

    from apeiria.conversation.contracts import ChatMessageCreate
    from apeiria.conversation.models import ChatSessionIdentity


@dataclass
class ChatSessionRow:
    id: int
    session_id: str
    platform: str
    bot_id: str
    scene_type: str
    scene_id: str
    subject_id: str | None
    title: str | None
    extra_json: str | None
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime


@dataclass(frozen=True)
class ChatSessionContextSummaryRow:
    """Stored prompt-facing conversation summary for one chat session."""

    session_id: str
    summary_text: str
    source_until_message_id: str
    source_until_created_at: datetime
    updated_at: datetime


@dataclass
class ChatMessageRow:
    id: int
    message_id: str
    session_pk: int
    platform_message_id: str | None
    reply_to_message_id: str | None
    platform_reply_id: str | None
    author_role: str
    author_id: str
    author_name: str | None
    message_kind: str
    turn_disposition: str
    directed_to_bot: bool
    mentions_bot: bool
    has_media: bool
    text_content: str
    content_json: str | None
    meta_json: str | None
    raw_data_json: str | None
    created_at: datetime


class ChatSessionRepository:
    """Own SQL operations and row mapping for conversation persistence."""

    async def ensure_session(
        self,
        identity: "ChatSessionIdentity",
    ) -> ChatSessionRow:
        now = utcnow()
        with database_runtime.transaction_sync() as connection:
            return _upsert_session_row(connection, identity, now)

    async def store_context_summary(
        self,
        identity: "ChatSessionIdentity",
        *,
        summary: str | None,
        source_until_message_id: str,
        source_until_created_at: datetime,
    ) -> None:
        chat_session = await self.ensure_session(identity)
        if summary is None or not summary.strip():
            await self.clear_context_summary(session_id=chat_session.session_id)
            return
        updated_at = utcnow()
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                INSERT INTO chat_session_context_summary (
                    session_id,
                    summary_text,
                    source_until_message_id,
                    source_until_created_at,
                    updated_at
                ) VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(session_id) DO UPDATE SET
                    summary_text = excluded.summary_text,
                    source_until_message_id = excluded.source_until_message_id,
                    source_until_created_at = excluded.source_until_created_at,
                    updated_at = excluded.updated_at
                """,
                (
                    chat_session.session_id,
                    summary.strip(),
                    source_until_message_id,
                    datetime_to_text(source_until_created_at),
                    datetime_to_text(updated_at),
                ),
            )

    async def clear_context_summary(self, *, session_id: str) -> None:
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                DELETE FROM chat_session_context_summary
                WHERE session_id = ?
                """,
                (session_id,),
            )

    def get_context_summary_row(
        self,
        *,
        session_id: str,
    ) -> ChatSessionContextSummaryRow | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                """
                SELECT
                    session_id,
                    summary_text,
                    source_until_message_id,
                    source_until_created_at,
                    updated_at
                FROM chat_session_context_summary
                WHERE session_id = ?
                """,
                (session_id,),
            ).fetchone()
        return None if row is None else row_to_context_summary(row)

    async def append_message(
        self,
        identity: "ChatSessionIdentity",
        message_data: "ChatMessageCreate",
    ) -> ChatMessageRow:
        now = utcnow()
        message_id = f"msg_{uuid4().hex}"
        with database_runtime.transaction_sync() as connection:
            chat_session = _upsert_session_row(connection, identity, now)
            cursor = connection.execute(
                """
                INSERT INTO chat_message (
                    message_id,
                    session_pk,
                    platform_message_id,
                    reply_to_message_id,
                    platform_reply_id,
                    author_role,
                    author_id,
                    author_name,
                    message_kind,
                    turn_disposition,
                    directed_to_bot,
                    mentions_bot,
                    has_media,
                    text_content,
                    content_json,
                    meta_json,
                    raw_data_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    message_id,
                    chat_session.id,
                    message_data.platform_message_id,
                    message_data.reply_to_message_id,
                    message_data.platform_reply_id,
                    message_data.author_role,
                    message_data.author_id,
                    message_data.author_name,
                    message_data.message_kind,
                    message_data.turn_disposition,
                    1 if message_data.directed_to_bot else 0,
                    1 if message_data.mentions_bot else 0,
                    1 if message_data.has_media else 0,
                    message_data.text_content,
                    serialize_json_payload(message_data.content),
                    serialize_json_payload(message_data.meta),
                    serialize_json_payload(message_data.raw_data),
                    datetime_to_text(now),
                ),
            )
            row = connection.execute(
                _SELECT_CHAT_MESSAGE_FIELDS + " WHERE chat_message.id = ?",
                (int(cursor.lastrowid or 0),),
            ).fetchone()
        assert row is not None
        return row_to_chat_message(row)

    def get_session_row(
        self,
        *,
        session_id: str,
    ) -> ChatSessionRow | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_CHAT_SESSION_FIELDS + " WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return None if row is None else row_to_chat_session(row)

    def list_recent_message_rows(
        self,
        identity: "ChatSessionIdentity",
        *,
        max_messages: int,
    ) -> list[ChatMessageRow]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_CHAT_MESSAGE_FIELDS
                + """
                JOIN chat_session
                    ON chat_message.session_pk = chat_session.id
                WHERE chat_session.session_id = ?
                ORDER BY chat_message.created_at DESC, chat_message.id DESC
                LIMIT ?
                """,
                (identity.session_id, max_messages),
            ).fetchall()
        return [row_to_chat_message(row) for row in rows]

    def list_recent_session_rows(
        self,
        *,
        limit: int,
    ) -> list[ChatSessionRow]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_CHAT_SESSION_FIELDS
                + """
                ORDER BY last_message_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [row_to_chat_session(row) for row in rows]

    def list_message_rows_for_session(
        self,
        *,
        session_id: str,
        limit: int,
    ) -> list[ChatMessageRow]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_CHAT_MESSAGE_FIELDS
                + """
                JOIN chat_session
                    ON chat_message.session_pk = chat_session.id
                WHERE chat_session.session_id = ?
                ORDER BY chat_message.created_at DESC, chat_message.id DESC
                LIMIT ?
                """,
                (session_id, limit),
            ).fetchall()
        return [row_to_chat_message(row) for row in rows]

    async def update_message_disposition(
        self,
        *,
        message_id: str,
        turn_disposition: str,
        clear_raw_data: bool = False,
    ) -> ChatMessageRow | None:
        with database_runtime.transaction_sync() as connection:
            if clear_raw_data:
                connection.execute(
                    """
                    UPDATE chat_message
                    SET turn_disposition = ?, raw_data_json = NULL
                    WHERE message_id = ?
                    """,
                    (turn_disposition, message_id),
                )
            else:
                connection.execute(
                    """
                    UPDATE chat_message
                    SET turn_disposition = ?
                    WHERE message_id = ?
                    """,
                    (turn_disposition, message_id),
                )
            row = connection.execute(
                _SELECT_CHAT_MESSAGE_FIELDS + " WHERE chat_message.message_id = ?",
                (message_id,),
            ).fetchone()
        return None if row is None else row_to_chat_message(row)

    def list_recent_user_ids_for_session(
        self,
        *,
        session_id: str,
        limit: int = 5,
    ) -> list[str]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                """
                SELECT chat_message.author_id
                FROM chat_message
                JOIN chat_session
                    ON chat_message.session_pk = chat_session.id
                WHERE
                    chat_session.session_id = ?
                    AND chat_message.author_role = 'user'
                ORDER BY chat_message.created_at DESC, chat_message.id DESC
                LIMIT ?
                """,
                (session_id, max(limit * 4, limit)),
            ).fetchall()
        author_ids: list[str] = []
        seen: set[str] = set()
        for row in rows:
            author_id = str(row[0])
            if author_id in seen:
                continue
            seen.add(author_id)
            author_ids.append(author_id)
            if len(author_ids) >= limit:
                break
        return author_ids


def _upsert_session_row(
    connection: "Connection",
    identity: "ChatSessionIdentity",
    timestamp: datetime,
) -> ChatSessionRow:
    timestamp_text = datetime_to_text(timestamp)
    connection.execute(
        """
        INSERT INTO chat_session (
            session_id,
            platform,
            bot_id,
            scene_type,
            scene_id,
            subject_id,
            created_at,
            updated_at,
            last_message_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(platform, bot_id, scene_type, scene_id) DO UPDATE SET
            session_id = excluded.session_id,
            subject_id = excluded.subject_id,
            updated_at = excluded.updated_at,
            last_message_at = excluded.last_message_at
        """,
        (
            identity.session_id,
            identity.platform,
            identity.bot_id,
            identity.scene_type,
            identity.scene_id,
            identity.subject_id,
            timestamp_text,
            timestamp_text,
            timestamp_text,
        ),
    )
    row = connection.execute(
        _SELECT_CHAT_SESSION_FIELDS
        + """
        WHERE
            platform = ?
            AND bot_id = ?
            AND scene_type = ?
            AND scene_id = ?
        """,
        (
            identity.platform,
            identity.bot_id,
            identity.scene_type,
            identity.scene_id,
        ),
    ).fetchone()
    assert row is not None
    return row_to_chat_session(row)


_SELECT_CHAT_SESSION_FIELDS = """
SELECT
    id,
    session_id,
    platform,
    bot_id,
    scene_type,
    scene_id,
    subject_id,
    title,
    extra_json,
    created_at,
    updated_at,
    last_message_at
FROM chat_session
"""

_CHAT_MESSAGE_FIELDS = """
    chat_message.id,
    chat_message.message_id,
    chat_message.session_pk,
    chat_message.platform_message_id,
    chat_message.reply_to_message_id,
    chat_message.platform_reply_id,
    chat_message.author_role,
    chat_message.author_id,
    chat_message.author_name,
    chat_message.message_kind,
    chat_message.turn_disposition,
    chat_message.directed_to_bot,
    chat_message.mentions_bot,
    chat_message.has_media,
    chat_message.text_content,
    chat_message.content_json,
    chat_message.meta_json,
    chat_message.raw_data_json,
    chat_message.created_at
"""

_SELECT_CHAT_MESSAGE_FIELDS = f"""
SELECT
{_CHAT_MESSAGE_FIELDS}
FROM chat_message
"""


def row_to_chat_session(row: tuple[object, ...]) -> ChatSessionRow:
    return ChatSessionRow(
        id=int(str(row[0])),
        session_id=str(row[1]),
        platform=str(row[2]),
        bot_id=str(row[3]),
        scene_type=str(row[4]),
        scene_id=str(row[5]),
        subject_id=str(row[6]) if row[6] is not None else None,
        title=str(row[7]) if row[7] is not None else None,
        extra_json=str(row[8]) if row[8] is not None else None,
        created_at=datetime_from_text(row[9]),
        updated_at=datetime_from_text(row[10]),
        last_message_at=datetime_from_text(row[11]),
    )


def row_to_context_summary(row: tuple[object, ...]) -> ChatSessionContextSummaryRow:
    return ChatSessionContextSummaryRow(
        session_id=str(row[0]),
        summary_text=str(row[1]),
        source_until_message_id=str(row[2]),
        source_until_created_at=datetime_from_text(row[3]),
        updated_at=datetime_from_text(row[4]),
    )


def row_to_chat_message(row: tuple[object, ...]) -> ChatMessageRow:
    return ChatMessageRow(
        id=int(str(row[0])),
        message_id=str(row[1]),
        session_pk=int(str(row[2])),
        platform_message_id=str(row[3]) if row[3] is not None else None,
        reply_to_message_id=str(row[4]) if row[4] is not None else None,
        platform_reply_id=str(row[5]) if row[5] is not None else None,
        author_role=str(row[6]),
        author_id=str(row[7]),
        author_name=str(row[8]) if row[8] is not None else None,
        message_kind=str(row[9]),
        turn_disposition=str(row[10]),
        directed_to_bot=bool(row[11]),
        mentions_bot=bool(row[12]),
        has_media=bool(row[13]),
        text_content=str(row[14]),
        content_json=str(row[15]) if row[15] is not None else None,
        meta_json=str(row[16]) if row[16] is not None else None,
        raw_data_json=str(row[17]) if row[17] is not None else None,
        created_at=datetime_from_text(row[18]),
    )


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def datetime_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def datetime_from_text(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def serialize_json_payload(payload: object | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
