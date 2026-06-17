"""Async SQLAlchemy persistence for chat sessions and messages."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING
from uuid import uuid4

from sqlalchemy import delete, select, update
from sqlalchemy.dialects.sqlite import insert

from apeiria.db.base import _epoch_ms
from apeiria.db.engine import get_session
from apeiria.db.models.conversation import (
    ChatMessage,
    ChatSession,
    ChatSessionContextSummary,
)

if TYPE_CHECKING:
    from apeiria.conversation.contracts import ChatMessageCreate
    from apeiria.conversation.models import ChatSessionIdentity


@dataclass
class ChatSessionRow:
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
    message_id: str
    session_id: str
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
        now = _epoch_ms()
        stmt = insert(ChatSession).values(
            session_id=identity.session_id,
            platform=identity.platform,
            bot_id=identity.bot_id,
            scene_type=identity.scene_type,
            scene_id=identity.scene_id,
            subject_id=identity.subject_id,
            created_at=now,
            updated_at=now,
            last_message_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[
                ChatSession.platform,
                ChatSession.bot_id,
                ChatSession.scene_type,
                ChatSession.scene_id,
            ],
            set_={
                "session_id": stmt.excluded.session_id,
                "subject_id": stmt.excluded.subject_id,
                "updated_at": stmt.excluded.updated_at,
                "last_message_at": stmt.excluded.last_message_at,
            },
        )
        async with get_session() as session:
            await session.execute(stmt)
            await session.commit()
            result = await session.execute(
                select(ChatSession).where(
                    ChatSession.platform == identity.platform,
                    ChatSession.bot_id == identity.bot_id,
                    ChatSession.scene_type == identity.scene_type,
                    ChatSession.scene_id == identity.scene_id,
                )
            )
            row = result.scalar_one()
        return _map_session_row(row)

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
        now = _epoch_ms()
        until_ms = int(source_until_created_at.timestamp() * 1000)
        stmt = insert(ChatSessionContextSummary).values(
            session_id=chat_session.session_id,
            summary_text=summary.strip(),
            source_until_message_id=source_until_message_id,
            source_until_created_at=until_ms,
            updated_at=now,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[ChatSessionContextSummary.session_id],
            set_={
                "summary_text": stmt.excluded.summary_text,
                "source_until_message_id": stmt.excluded.source_until_message_id,
                "source_until_created_at": stmt.excluded.source_until_created_at,
                "updated_at": stmt.excluded.updated_at,
            },
        )
        async with get_session() as session:
            await session.execute(stmt)
            await session.commit()

    async def clear_context_summary(self, *, session_id: str) -> None:
        async with get_session() as session:
            await session.execute(
                delete(ChatSessionContextSummary).where(
                    ChatSessionContextSummary.session_id == session_id
                )
            )
            await session.commit()

    async def get_context_summary_row(
        self,
        *,
        session_id: str,
    ) -> ChatSessionContextSummaryRow | None:
        async with get_session() as session:
            result = await session.execute(
                select(ChatSessionContextSummary).where(
                    ChatSessionContextSummary.session_id == session_id
                )
            )
            row = result.scalar_one_or_none()
        if row is None:
            return None
        return ChatSessionContextSummaryRow(
            session_id=row.session_id,
            summary_text=row.summary_text,
            source_until_message_id=row.source_until_message_id,
            source_until_created_at=_epoch_ms_to_datetime(row.source_until_created_at),
            updated_at=_epoch_ms_to_datetime(row.updated_at),
        )

    async def append_message(
        self,
        identity: "ChatSessionIdentity",
        message_data: "ChatMessageCreate",
    ) -> ChatMessageRow:
        now = _epoch_ms()
        message_id = f"msg_{uuid4().hex}"
        upsert_stmt = insert(ChatSession).values(
            session_id=identity.session_id,
            platform=identity.platform,
            bot_id=identity.bot_id,
            scene_type=identity.scene_type,
            scene_id=identity.scene_id,
            subject_id=identity.subject_id,
            created_at=now,
            updated_at=now,
            last_message_at=now,
        )
        upsert_stmt = upsert_stmt.on_conflict_do_update(
            index_elements=[
                ChatSession.platform,
                ChatSession.bot_id,
                ChatSession.scene_type,
                ChatSession.scene_id,
            ],
            set_={
                "session_id": upsert_stmt.excluded.session_id,
                "subject_id": upsert_stmt.excluded.subject_id,
                "updated_at": upsert_stmt.excluded.updated_at,
                "last_message_at": upsert_stmt.excluded.last_message_at,
            },
        )
        async with get_session() as session:
            await session.execute(upsert_stmt)
            msg_stmt = insert(ChatMessage).values(
                message_id=message_id,
                session_id=identity.session_id,
                platform_message_id=message_data.platform_message_id,
                reply_to_message_id=message_data.reply_to_message_id,
                platform_reply_id=message_data.platform_reply_id,
                author_role=message_data.author_role,
                author_id=message_data.author_id,
                author_name=message_data.author_name,
                message_kind=message_data.message_kind,
                turn_disposition=message_data.turn_disposition,
                directed_to_bot=1 if message_data.directed_to_bot else 0,
                mentions_bot=1 if message_data.mentions_bot else 0,
                has_media=1 if message_data.has_media else 0,
                text_content=message_data.text_content,
                content_json=_serialize_json_payload(message_data.content),
                meta_json=_serialize_json_payload(message_data.meta),
                raw_data_json=_serialize_json_payload(message_data.raw_data),
                created_at=now,
            )
            await session.execute(msg_stmt)
            await session.commit()
            result = await session.execute(
                select(ChatMessage).where(ChatMessage.message_id == message_id)
            )
            row = result.scalar_one()
        return _map_message_row(row)

    async def get_session_row(
        self,
        *,
        session_id: str,
    ) -> ChatSessionRow | None:
        async with get_session() as session:
            result = await session.execute(
                select(ChatSession).where(ChatSession.session_id == session_id)
            )
            row = result.scalar_one_or_none()
        return None if row is None else _map_session_row(row)

    async def list_recent_message_rows(
        self,
        identity: "ChatSessionIdentity",
        *,
        max_messages: int,
    ) -> list[ChatMessageRow]:
        async with get_session() as session:
            result = await session.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == identity.session_id)
                .order_by(ChatMessage.created_at.desc(), ChatMessage.message_id.desc())
                .limit(max_messages)
            )
            rows = result.scalars().all()
        return [_map_message_row(r) for r in rows]

    async def list_recent_session_rows(
        self,
        *,
        limit: int,
    ) -> list[ChatSessionRow]:
        async with get_session() as session:
            result = await session.execute(
                select(ChatSession)
                .order_by(
                    ChatSession.last_message_at.desc(),
                    ChatSession.session_id.desc(),
                )
                .limit(limit)
            )
            rows = result.scalars().all()
        return [_map_session_row(r) for r in rows]

    async def list_message_rows_for_session(
        self,
        *,
        session_id: str,
        limit: int,
    ) -> list[ChatMessageRow]:
        async with get_session() as session:
            result = await session.execute(
                select(ChatMessage)
                .where(ChatMessage.session_id == session_id)
                .order_by(ChatMessage.created_at.desc(), ChatMessage.message_id.desc())
                .limit(limit)
            )
            rows = result.scalars().all()
        return [_map_message_row(r) for r in rows]

    async def get_message_row_by_platform_message_id(
        self,
        *,
        session_id: str,
        platform_message_id: str,
    ) -> ChatMessageRow | None:
        async with get_session() as session:
            result = await session.execute(
                select(ChatMessage)
                .where(
                    ChatMessage.session_id == session_id,
                    ChatMessage.platform_message_id == platform_message_id,
                )
                .order_by(ChatMessage.created_at.desc(), ChatMessage.message_id.desc())
                .limit(1)
            )
            row = result.scalar_one_or_none()
        return None if row is None else _map_message_row(row)

    async def update_message_disposition(
        self,
        *,
        message_id: str,
        turn_disposition: str,
    ) -> ChatMessageRow | None:
        async with get_session() as session:
            await session.execute(
                update(ChatMessage)
                .where(ChatMessage.message_id == message_id)
                .values(turn_disposition=turn_disposition)
            )
            await session.commit()
            result = await session.execute(
                select(ChatMessage).where(ChatMessage.message_id == message_id)
            )
            row = result.scalar_one_or_none()
        return None if row is None else _map_message_row(row)

    async def list_recent_user_ids_for_session(
        self,
        *,
        session_id: str,
        limit: int = 5,
    ) -> list[str]:
        async with get_session() as session:
            result = await session.execute(
                select(ChatMessage.author_id)
                .where(
                    ChatMessage.session_id == session_id,
                    ChatMessage.author_role == "user",
                )
                .order_by(ChatMessage.created_at.desc(), ChatMessage.message_id.desc())
                .limit(max(limit * 4, limit))
            )
            rows = result.scalars().all()
        author_ids: list[str] = []
        seen: set[str] = set()
        for author_id in rows:
            if author_id in seen:
                continue
            seen.add(author_id)
            author_ids.append(author_id)
            if len(author_ids) >= limit:
                break
        return author_ids


def _map_session_row(row: ChatSession) -> ChatSessionRow:
    return ChatSessionRow(
        session_id=row.session_id,
        platform=row.platform,
        bot_id=row.bot_id,
        scene_type=row.scene_type,
        scene_id=row.scene_id,
        subject_id=row.subject_id,
        title=row.title,
        extra_json=row.extra_json,
        created_at=_epoch_ms_to_datetime(row.created_at),
        updated_at=_epoch_ms_to_datetime(row.updated_at),
        last_message_at=_epoch_ms_to_datetime(row.last_message_at),
    )


def _map_message_row(row: ChatMessage) -> ChatMessageRow:
    return ChatMessageRow(
        message_id=row.message_id,
        session_id=row.session_id,
        platform_message_id=row.platform_message_id,
        reply_to_message_id=row.reply_to_message_id,
        platform_reply_id=row.platform_reply_id,
        author_role=row.author_role,
        author_id=row.author_id,
        author_name=row.author_name,
        message_kind=row.message_kind,
        turn_disposition=row.turn_disposition,
        directed_to_bot=bool(row.directed_to_bot),
        mentions_bot=bool(row.mentions_bot),
        has_media=bool(row.has_media),
        text_content=row.text_content,
        content_json=row.content_json,
        meta_json=row.meta_json,
        raw_data_json=row.raw_data_json,
        created_at=_epoch_ms_to_datetime(row.created_at),
    )


def _epoch_ms_to_datetime(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc)


def _serialize_json_payload(payload: object | None) -> str | None:
    if payload is None:
        return None
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        default=str,
    )
