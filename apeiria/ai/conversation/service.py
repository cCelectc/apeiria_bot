"""Conversation service for normalized chat session and message persistence."""

from __future__ import annotations

import json
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from apeiria.ai.conversation.identity import (
    build_chat_session_identity_from_event,
    trim_message_window,
)
from apeiria.ai.conversation.models import (
    AuthorRole,
    ChatContextMessageView,
    ChatMessageDetailView,
    ChatSessionAdminView,
    ChatSessionIdentity,
    MessageKind,
)
from apeiria.ai.conversation.summary import build_short_conversation_summary
from apeiria.db.runtime import database_runtime

if TYPE_CHECKING:
    from sqlite3 import Connection

    from nonebot.adapters import Bot, Event

    from apeiria.ai.conversation.models import SceneType


_MEDIA_TYPES = {"image", "img", "audio", "record", "video", "file"}


@dataclass
class _ChatSessionRow:
    id: int
    session_id: str
    platform: str
    bot_id: str
    scene_type: str
    scene_id: str
    subject_id: str | None
    title: str | None
    summary_text: str | None
    extra_json: str | None
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime


@dataclass
class _ChatMessageRow:
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
    directed_to_bot: bool
    mentions_bot: bool
    has_media: bool
    text_content: str
    content_json: str | None
    meta_json: str | None
    raw_data_json: str | None
    created_at: datetime


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _datetime_to_text(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _datetime_from_text(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


@dataclass(frozen=True)
class ChatMessageCreate:
    """Input payload for creating one persisted chat message."""

    author_role: AuthorRole
    author_id: str
    text_content: str
    author_name: str | None = None
    message_kind: MessageKind = "text"
    directed_to_bot: bool = False
    mentions_bot: bool = False
    has_media: bool = False
    platform_message_id: str | None = None
    reply_to_message_id: str | None = None
    platform_reply_id: str | None = None
    content: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    raw_data: dict[str, Any] | None = None


class ChatSessionService:
    """Conversation service for session upsert and normalized message append."""

    @staticmethod
    def _deserialize_json_payload(raw_json: str | None) -> dict[str, Any] | None:
        if not raw_json:
            return None
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    @staticmethod
    def _serialize_json_payload(payload: Any | None) -> str | None:
        if payload is None:
            return None
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            default=str,
        )

    async def ensure_session(
        self,
        identity: ChatSessionIdentity,
    ) -> _ChatSessionRow:
        """Create or update the canonical chat session row for one scene."""
        now = _utcnow()
        with database_runtime.transaction_sync() as connection:
            return self._upsert_session_row(connection, identity, now)

    async def load_session_summary(
        self,
        identity: ChatSessionIdentity,
    ) -> str | None:
        """Load the stored conversation summary for one session."""
        chat_session = self._get_session_row(session_id=identity.session_id)
        if chat_session is None:
            return None
        return chat_session.summary_text

    async def store_summary_text(
        self,
        identity: ChatSessionIdentity,
        *,
        summary: str | None,
    ) -> None:
        """Persist an externally-built conversation summary."""
        chat_session = await self.ensure_session(identity)
        chat_session.summary_text = summary
        chat_session.updated_at = _utcnow()
        with database_runtime.connect_sync() as connection:
            connection.execute(
                """
                UPDATE chat_session
                SET summary_text = ?, updated_at = ?
                WHERE session_id = ?
                """,
                (
                    chat_session.summary_text,
                    _datetime_to_text(chat_session.updated_at),
                    chat_session.session_id,
                ),
            )

    async def update_summary_text(
        self,
        identity: ChatSessionIdentity,
        *,
        messages: list[ChatContextMessageView],
    ) -> str | None:
        """Refresh the compact stored summary for one session.

        .. deprecated::
            Prefer ``store_summary_text`` with an externally-built summary.
        """

        summary = build_short_conversation_summary(messages)
        await self.store_summary_text(identity, summary=summary)
        return summary

    async def append_message(
        self,
        identity: ChatSessionIdentity,
        message_data: ChatMessageCreate,
    ) -> _ChatMessageRow:
        """Append one normalized message to the chat session history."""
        now = _utcnow()
        message_id = f"msg_{uuid4().hex}"
        with database_runtime.transaction_sync() as connection:
            chat_session = self._upsert_session_row(connection, identity, now)
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
                    directed_to_bot,
                    mentions_bot,
                    has_media,
                    text_content,
                    content_json,
                    meta_json,
                    raw_data_json,
                    created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                    1 if message_data.directed_to_bot else 0,
                    1 if message_data.mentions_bot else 0,
                    1 if message_data.has_media else 0,
                    message_data.text_content,
                    self._serialize_json_payload(message_data.content),
                    self._serialize_json_payload(message_data.meta),
                    self._serialize_json_payload(message_data.raw_data),
                    _datetime_to_text(now),
                ),
            )
            row = connection.execute(
                _SELECT_CHAT_MESSAGE_FIELDS + " WHERE chat_message.id = ?",
                (int(cursor.lastrowid or 0),),
            ).fetchone()
        assert row is not None
        return _row_to_chat_message(row)

    def _upsert_session_row(
        self,
        connection: "Connection",
        identity: ChatSessionIdentity,
        timestamp: datetime,
    ) -> _ChatSessionRow:
        timestamp_text = _datetime_to_text(timestamp)
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
            ON CONFLICT(session_id) DO UPDATE SET
                platform = excluded.platform,
                bot_id = excluded.bot_id,
                scene_type = excluded.scene_type,
                scene_id = excluded.scene_id,
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
            _SELECT_CHAT_SESSION_FIELDS + " WHERE session_id = ?",
            (identity.session_id,),
        ).fetchone()
        assert row is not None
        return _row_to_chat_session(row)

    async def ingest_event(
        self,
        bot: "Bot",
        event: "Event",
        *,
        persist_raw_data: bool = False,
    ) -> tuple[ChatSessionIdentity, _ChatMessageRow] | None:
        """Convert one runtime event into a canonical chat message."""

        identity = build_chat_session_identity_from_event(bot, event)
        if identity is None:
            return None

        raw_data = (
            event.model_dump(mode="json") if hasattr(event, "model_dump") else None
        )
        text_content = event.get_plaintext()
        mentions_bot = bool(hasattr(event, "is_tome") and event.is_tome())
        author_id = str(event.get_user_id())
        author_name = _extract_author_name(raw_data) or author_id
        platform_message_id = _extract_platform_message_id(event, raw_data)
        platform_reply_id = _extract_platform_reply_id(raw_data)
        has_media = _detect_has_media(raw_data)
        content = _build_normalized_content(
            raw_data=raw_data, text_content=text_content
        )
        message_kind = _resolve_message_kind(
            text_content=text_content, has_media=has_media
        )
        message = await self.append_message(
            identity,
            ChatMessageCreate(
                author_role="user",
                author_id=author_id,
                author_name=author_name,
                text_content=text_content,
                message_kind=message_kind,
                directed_to_bot=(identity.scene_type == "private" or mentions_bot),
                mentions_bot=mentions_bot,
                has_media=has_media,
                platform_message_id=platform_message_id,
                platform_reply_id=platform_reply_id,
                content=content,
                raw_data=(
                    _build_debug_raw_payload(raw_data) if persist_raw_data else None
                ),
            ),
        )
        return identity, message

    async def list_recent_messages(
        self,
        identity: ChatSessionIdentity,
        *,
        max_messages: int,
    ) -> list[ChatContextMessageView]:
        """List recent messages for one chat session identity."""
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
        message_rows = [_row_to_chat_message(row) for row in rows]
        message_rows.reverse()
        messages = [self._to_context_message_view(row) for row in message_rows]
        return trim_message_window(messages, max_messages=max_messages)

    async def list_recent_sessions(
        self,
        *,
        limit: int,
    ) -> list[ChatSessionAdminView]:
        with database_runtime.connect_sync() as connection:
            rows = connection.execute(
                _SELECT_CHAT_SESSION_FIELDS
                + """
                ORDER BY last_message_at DESC, id DESC
                LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [self._to_session_admin_view(_row_to_chat_session(row)) for row in rows]

    async def get_session_view(
        self,
        *,
        session_id: str,
    ) -> ChatSessionAdminView | None:
        row = self._get_session_row(session_id=session_id)
        if row is None:
            return None
        return self._to_session_admin_view(row)

    async def list_messages_for_session(
        self,
        *,
        session_id: str,
        limit: int,
    ) -> list[ChatMessageDetailView]:
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
        messages = [
            self._to_message_detail_view(
                message=_row_to_chat_message(row),
                session_id=session_id,
            )
            for row in rows
        ]
        messages.reverse()
        return messages

    async def list_recent_user_ids_for_session(
        self,
        *,
        session_id: str,
        limit: int = 5,
    ) -> list[str]:
        """List distinct recent user author ids for one session."""
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

    async def get_session_identity(
        self,
        *,
        session_id: str,
    ) -> ChatSessionIdentity | None:
        """Load the canonical identity for one stored session id."""
        row = self._get_session_row(session_id=session_id)
        if row is None:
            return None
        return ChatSessionIdentity(
            session_id=row.session_id,
            platform=row.platform,
            bot_id=row.bot_id,
            scene_type=cast("SceneType", row.scene_type),
            scene_id=row.scene_id,
            subject_id=row.subject_id,
        )

    @staticmethod
    def _get_session_row(*, session_id: str) -> _ChatSessionRow | None:
        with database_runtime.connect_sync() as connection:
            row = connection.execute(
                _SELECT_CHAT_SESSION_FIELDS + " WHERE session_id = ?",
                (session_id,),
            ).fetchone()
        return None if row is None else _row_to_chat_session(row)

    def _to_context_message_view(self, row: _ChatMessageRow) -> ChatContextMessageView:
        content = self._deserialize_json_payload(row.content_json)
        return ChatContextMessageView(
            message_id=row.message_id,
            author_role=cast("AuthorRole", row.author_role),
            author_id=row.author_id,
            author_name=row.author_name,
            text_content=row.text_content,
            content=content,
            created_at=row.created_at,
            reply_to_message_id=row.reply_to_message_id,
        )

    def _to_session_admin_view(self, row: _ChatSessionRow) -> ChatSessionAdminView:
        return ChatSessionAdminView(
            session_id=row.session_id,
            platform=row.platform,
            bot_id=row.bot_id,
            scene_type=cast("SceneType", row.scene_type),
            scene_id=row.scene_id,
            subject_id=row.subject_id,
            title=row.title,
            summary_text=row.summary_text,
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_message_at=row.last_message_at,
        )

    def _to_message_detail_view(
        self,
        *,
        message: _ChatMessageRow,
        session_id: str,
    ) -> ChatMessageDetailView:
        content = self._deserialize_json_payload(message.content_json)
        meta = self._deserialize_json_payload(message.meta_json)
        raw_data = self._deserialize_json_payload(message.raw_data_json)
        return ChatMessageDetailView(
            message_id=message.message_id,
            session_id=session_id,
            platform_message_id=message.platform_message_id,
            reply_to_message_id=message.reply_to_message_id,
            platform_reply_id=message.platform_reply_id,
            author_role=cast("AuthorRole", message.author_role),
            author_id=message.author_id,
            author_name=message.author_name,
            message_kind=cast("MessageKind", message.message_kind),
            directed_to_bot=message.directed_to_bot,
            mentions_bot=message.mentions_bot,
            has_media=message.has_media,
            text_content=message.text_content,
            content=content,
            meta=meta,
            raw_data=raw_data,
            created_at=message.created_at,
        )


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
    summary_text,
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


def _row_to_chat_session(row: tuple[object, ...]) -> _ChatSessionRow:
    return _ChatSessionRow(
        id=int(str(row[0])),
        session_id=str(row[1]),
        platform=str(row[2]),
        bot_id=str(row[3]),
        scene_type=str(row[4]),
        scene_id=str(row[5]),
        subject_id=str(row[6]) if row[6] is not None else None,
        title=str(row[7]) if row[7] is not None else None,
        summary_text=str(row[8]) if row[8] is not None else None,
        extra_json=str(row[9]) if row[9] is not None else None,
        created_at=_datetime_from_text(row[10]),
        updated_at=_datetime_from_text(row[11]),
        last_message_at=_datetime_from_text(row[12]),
    )


def _row_to_chat_message(row: tuple[object, ...]) -> _ChatMessageRow:
    return _ChatMessageRow(
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
        directed_to_bot=bool(row[10]),
        mentions_bot=bool(row[11]),
        has_media=bool(row[12]),
        text_content=str(row[13]),
        content_json=str(row[14]) if row[14] is not None else None,
        meta_json=str(row[15]) if row[15] is not None else None,
        raw_data_json=str(row[16]) if row[16] is not None else None,
        created_at=_datetime_from_text(row[17]),
    )


chat_session_service = ChatSessionService()


def _extract_platform_message_id(
    event: "Event", raw_data: dict[str, Any] | None
) -> str | None:
    getter = getattr(event, "get_message_id", None)
    if callable(getter):
        try:
            value = getter()
            if value is not None:
                return str(value)
        except Exception:  # noqa: BLE001
            pass
    if not raw_data:
        return None
    for key in ("message_id", "id"):
        value = raw_data.get(key)
        if value is not None:
            return str(value)
    return None


def _extract_platform_reply_id(raw_data: dict[str, Any] | None) -> str | None:
    if not raw_data:
        return None
    reply = raw_data.get("reply")
    if isinstance(reply, dict):
        for key in ("message_id", "id"):
            value = reply.get(key)
            if value is not None:
                return str(value)
    return None


def _extract_author_name(raw_data: dict[str, Any] | None) -> str | None:
    if not raw_data:
        return None
    sender = raw_data.get("sender")
    if isinstance(sender, dict):
        for key in ("card", "nickname", "name"):
            value = sender.get(key)
            if isinstance(value, str) and value.strip():
                return value.strip()
    for key in ("user_name", "nickname", "name"):
        value = raw_data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _detect_has_media(raw_data: dict[str, Any] | None) -> bool:
    if not raw_data:
        return False
    message = raw_data.get("message")
    if isinstance(message, list):
        for segment in message:
            if isinstance(segment, dict):
                seg_type = segment.get("type")
                if isinstance(seg_type, str) and seg_type in _MEDIA_TYPES:
                    return True
    return False


def _resolve_message_kind(*, text_content: str, has_media: bool) -> MessageKind:
    has_text = bool(text_content.strip())
    if has_text and has_media:
        return "mixed"
    if has_media:
        return "media"
    return "text"


def _build_normalized_content(  # noqa: C901, PLR0912
    *,
    raw_data: dict[str, Any] | None,
    text_content: str,
) -> dict[str, Any]:
    segments: list[dict[str, Any]] = []
    if text_content.strip():
        segments.append({"type": "text", "text": text_content.strip()})

    mentioned_user_ids: list[str] = []
    quoted_text: str | None = None
    if raw_data:
        reply = raw_data.get("reply")
        if isinstance(reply, dict):
            for key in ("text", "message", "content"):
                value = reply.get(key)
                if isinstance(value, str) and value.strip():
                    quoted_text = value.strip()
                    break
        message = raw_data.get("message")
        if isinstance(message, list):
            for segment in message:
                if not isinstance(segment, dict):
                    continue
                seg_type = segment.get("type")
                data = segment.get("data")
                if not isinstance(seg_type, str):
                    continue
                if seg_type == "at" and isinstance(data, dict):
                    qq = data.get("qq")
                    if qq is not None:
                        mentioned_user_ids.append(str(qq))
                elif seg_type in _MEDIA_TYPES:
                    segments.append({"type": seg_type})

    payload: dict[str, Any] = {
        "segments": segments,
        "plain_text": text_content,
        "mentioned_user_ids": mentioned_user_ids,
    }
    if quoted_text:
        payload["quoted_text"] = quoted_text
    return payload


def _build_debug_raw_payload(
    raw_data: dict[str, Any] | None,
) -> dict[str, Any] | None:
    if not raw_data:
        return None

    payload: dict[str, Any] = {}
    for key in (
        "message_id",
        "id",
        "time",
        "self_id",
        "user_id",
        "group_id",
        "post_type",
        "message_type",
        "sub_type",
        "notice_type",
        "request_type",
    ):
        value = raw_data.get(key)
        if isinstance(value, (str, int, float, bool)):
            payload[key] = value

    sender = raw_data.get("sender")
    sender_summary = _build_mapping_summary(
        sender,
        allowed_keys=("user_id", "nickname", "card", "name", "role"),
    )
    if sender_summary:
        payload["sender"] = sender_summary

    reply = raw_data.get("reply")
    reply_summary = _build_mapping_summary(
        reply,
        allowed_keys=("message_id", "id", "user_id", "text"),
    )
    if reply_summary:
        payload["reply"] = reply_summary

    message = raw_data.get("message")
    if isinstance(message, list):
        segment_types = [
            seg_type
            for segment in message
            if isinstance(segment, Mapping)
            and isinstance((seg_type := segment.get("type")), str)
            and seg_type.strip()
        ]
        if segment_types:
            payload["message_segment_types"] = segment_types[:20]

    return payload or None


def _build_mapping_summary(
    value: object,
    *,
    allowed_keys: tuple[str, ...],
) -> dict[str, Any] | None:
    if not isinstance(value, Mapping):
        return None

    summary = {
        key: item
        for key in allowed_keys
        if isinstance((item := value.get(key)), (str, int, float, bool))
    }
    return summary or None
