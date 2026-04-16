"""Conversation service for normalized chat session and message persistence."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.conversation.identity import (
    build_chat_session_identity_from_event,
    trim_message_window,
)
from apeiria.app.ai.conversation.models import (
    AuthorRole,
    ChatContextMessageView,
    ChatMessageDetailView,
    ChatSessionAdminView,
    ChatSessionIdentity,
    MessageKind,
)
from apeiria.app.ai.conversation.summary import build_short_conversation_summary
from apeiria.infra.db.models import ChatMessage, ChatSession

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.conversation.models import SceneType


_MEDIA_TYPES = {"image", "img", "audio", "record", "video", "file"}


def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


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
        session: "AsyncSession",
        identity: ChatSessionIdentity,
    ) -> ChatSession:
        """Create or update the canonical chat session row for one scene."""

        result = await session.execute(
            select(ChatSession).where(ChatSession.session_id == identity.session_id)
        )
        chat_session = result.scalar_one_or_none()
        if chat_session is None:
            chat_session = ChatSession(
                session_id=identity.session_id,
                platform=identity.platform,
                bot_id=identity.bot_id,
                scene_type=identity.scene_type,
                scene_id=identity.scene_id,
                subject_id=identity.subject_id,
            )
            session.add(chat_session)
            await session.flush()

        chat_session.last_message_at = _utcnow_naive()
        return chat_session

    async def load_session_summary(
        self,
        session: "AsyncSession",
        identity: ChatSessionIdentity,
    ) -> str | None:
        """Load the stored conversation summary for one session."""

        result = await session.execute(
            select(ChatSession).where(ChatSession.session_id == identity.session_id)
        )
        chat_session = result.scalar_one_or_none()
        if chat_session is None:
            return None
        return chat_session.summary_text

    async def store_summary_text(
        self,
        session: "AsyncSession",
        identity: ChatSessionIdentity,
        *,
        summary: str | None,
    ) -> None:
        """Persist an externally-built conversation summary."""

        chat_session = await self.ensure_session(session, identity)
        chat_session.summary_text = summary
        await session.flush()

    async def update_summary_text(
        self,
        session: "AsyncSession",
        identity: ChatSessionIdentity,
        *,
        messages: list[ChatContextMessageView],
    ) -> str | None:
        """Refresh the compact stored summary for one session.

        .. deprecated::
            Prefer ``store_summary_text`` with an externally-built summary.
        """

        chat_session = await self.ensure_session(session, identity)
        summary = build_short_conversation_summary(messages)
        chat_session.summary_text = summary
        await session.flush()
        return summary

    async def append_message(
        self,
        session: "AsyncSession",
        identity: ChatSessionIdentity,
        message_data: ChatMessageCreate,
    ) -> ChatMessage:
        """Append one normalized message to the chat session history."""

        chat_session = await self.ensure_session(session, identity)
        message = ChatMessage(
            message_id=f"msg_{uuid4().hex}",
            session_pk=chat_session.id,
            platform_message_id=message_data.platform_message_id,
            reply_to_message_id=message_data.reply_to_message_id,
            platform_reply_id=message_data.platform_reply_id,
            author_role=message_data.author_role,
            author_id=message_data.author_id,
            author_name=message_data.author_name,
            message_kind=message_data.message_kind,
            directed_to_bot=message_data.directed_to_bot,
            mentions_bot=message_data.mentions_bot,
            has_media=message_data.has_media,
            text_content=message_data.text_content,
            content_json=self._serialize_json_payload(message_data.content),
            meta_json=self._serialize_json_payload(message_data.meta),
            raw_data_json=self._serialize_json_payload(message_data.raw_data),
        )
        session.add(message)
        await session.flush()
        return message

    async def ingest_event(
        self,
        session: "AsyncSession",
        bot: "Bot",
        event: "Event",
    ) -> tuple[ChatSessionIdentity, ChatMessage] | None:
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
            session,
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
                raw_data=raw_data,
            ),
        )
        return identity, message

    async def list_recent_messages(
        self,
        session: "AsyncSession",
        identity: ChatSessionIdentity,
        *,
        max_messages: int,
    ) -> list[ChatContextMessageView]:
        """List recent messages for one chat session identity."""

        result = await session.execute(
            select(ChatMessage)
            .join(ChatSession, ChatMessage.session_pk == ChatSession.id)
            .where(ChatSession.session_id == identity.session_id)
            .order_by(ChatMessage.created_at.asc(), ChatMessage.id.asc())
        )
        messages = [
            self._to_context_message_view(row) for row in result.scalars().all()
        ]
        return trim_message_window(messages, max_messages=max_messages)

    async def list_recent_sessions(
        self,
        session: "AsyncSession",
        *,
        limit: int,
    ) -> list[ChatSessionAdminView]:
        result = await session.execute(
            select(ChatSession)
            .order_by(ChatSession.last_message_at.desc(), ChatSession.id.desc())
            .limit(limit)
        )
        return [self._to_session_admin_view(row) for row in result.scalars().all()]

    async def get_session_view(
        self,
        session: "AsyncSession",
        *,
        session_id: str,
    ) -> ChatSessionAdminView | None:
        result = await session.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return self._to_session_admin_view(row)

    async def list_messages_for_session(
        self,
        session: "AsyncSession",
        *,
        session_id: str,
        limit: int,
    ) -> list[ChatMessageDetailView]:
        result = await session.execute(
            select(ChatMessage, ChatSession.session_id)
            .join(ChatSession, ChatMessage.session_pk == ChatSession.id)
            .where(ChatSession.session_id == session_id)
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(limit)
        )
        rows = result.all()
        messages = [
            self._to_message_detail_view(message=row, session_id=session_id_value)
            for row, session_id_value in rows
        ]
        messages.reverse()
        return messages

    async def list_recent_user_ids_for_session(
        self,
        session: "AsyncSession",
        *,
        session_id: str,
        limit: int = 5,
    ) -> list[str]:
        """List distinct recent user author ids for one session."""

        result = await session.execute(
            select(ChatMessage.author_id)
            .join(ChatSession, ChatMessage.session_pk == ChatSession.id)
            .where(
                ChatSession.session_id == session_id,
                ChatMessage.author_role == "user",
            )
            .order_by(ChatMessage.created_at.desc(), ChatMessage.id.desc())
            .limit(max(limit * 4, limit))
        )
        author_ids: list[str] = []
        seen: set[str] = set()
        for author_id in result.scalars().all():
            if author_id in seen:
                continue
            seen.add(author_id)
            author_ids.append(author_id)
            if len(author_ids) >= limit:
                break
        return author_ids

    async def get_session_identity(
        self,
        session: "AsyncSession",
        *,
        session_id: str,
    ) -> ChatSessionIdentity | None:
        """Load the canonical identity for one stored session id."""

        result = await session.execute(
            select(ChatSession).where(ChatSession.session_id == session_id)
        )
        row = result.scalar_one_or_none()
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

    def _to_context_message_view(self, row: ChatMessage) -> ChatContextMessageView:
        content = self._deserialize_json_payload(row.content_json)
        created_at = (
            row.created_at.replace(tzinfo=timezone.utc)
            if row.created_at.tzinfo is None
            else row.created_at
        )
        return ChatContextMessageView(
            message_id=row.message_id,
            author_role=cast("AuthorRole", row.author_role),
            author_id=row.author_id,
            author_name=row.author_name,
            text_content=row.text_content,
            content=content,
            created_at=created_at,
            reply_to_message_id=row.reply_to_message_id,
        )

    def _to_session_admin_view(self, row: ChatSession) -> ChatSessionAdminView:
        created_at = (
            row.created_at.replace(tzinfo=timezone.utc)
            if row.created_at.tzinfo is None
            else row.created_at
        )
        updated_at = (
            row.updated_at.replace(tzinfo=timezone.utc)
            if row.updated_at.tzinfo is None
            else row.updated_at
        )
        last_message_at = (
            row.last_message_at.replace(tzinfo=timezone.utc)
            if row.last_message_at.tzinfo is None
            else row.last_message_at
        )
        return ChatSessionAdminView(
            session_id=row.session_id,
            platform=row.platform,
            bot_id=row.bot_id,
            scene_type=cast("SceneType", row.scene_type),
            scene_id=row.scene_id,
            subject_id=row.subject_id,
            title=row.title,
            summary_text=row.summary_text,
            created_at=created_at,
            updated_at=updated_at,
            last_message_at=last_message_at,
        )

    def _to_message_detail_view(
        self,
        *,
        message: ChatMessage,
        session_id: str,
    ) -> ChatMessageDetailView:
        content = self._deserialize_json_payload(message.content_json)
        meta = self._deserialize_json_payload(message.meta_json)
        raw_data = self._deserialize_json_payload(message.raw_data_json)
        created_at = (
            message.created_at.replace(tzinfo=timezone.utc)
            if message.created_at.tzinfo is None
            else message.created_at
        )
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
            created_at=created_at,
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
