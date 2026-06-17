"""Conversation service for normalized chat session and message persistence."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any, cast

from apeiria.conversation.contracts import ChatMessageCreate as _ChatMessageCreate
from apeiria.conversation.identity import trim_message_window
from apeiria.conversation.models import (
    ChatContextMessageView,
    ChatMessageDetailView,
    ChatSessionAdminView,
    ChatSessionContextSummary,
    ChatSessionIdentity,
)
from apeiria.conversation.repository import (
    ChatMessageRow,
    ChatSessionRepository,
    ChatSessionRow,
)

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.conversation.contracts import ChatMessageCreate
    from apeiria.conversation.models import (
        AuthorRole,
        MessageKind,
        SceneType,
        TurnDisposition,
    )


class ChatSessionService:
    """Conversation service for session upsert and normalized message append."""

    def __init__(
        self,
        *,
        repository: ChatSessionRepository | None = None,
    ) -> None:
        self._repository = repository or ChatSessionRepository()

    @staticmethod
    def _deserialize_json_payload(raw_json: str | None) -> dict[str, Any] | None:
        if not raw_json:
            return None
        try:
            payload = json.loads(raw_json)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    async def ensure_session(
        self,
        identity: ChatSessionIdentity,
    ) -> ChatSessionRow:
        """Create or update the canonical chat session row for one scene."""

        return await self._repository.ensure_session(identity)

    async def load_session_summary(
        self,
        identity: ChatSessionIdentity,
    ) -> ChatSessionContextSummary | None:
        """Load the prompt-facing context summary for one session."""

        row = await self._repository.get_context_summary_row(
            session_id=identity.session_id,
        )
        if row is None:
            return None
        return ChatSessionContextSummary(
            session_id=row.session_id,
            summary_text=row.summary_text,
            source_until_message_id=row.source_until_message_id,
            source_until_created_at=row.source_until_created_at,
            updated_at=row.updated_at,
        )

    async def store_session_summary(
        self,
        identity: ChatSessionIdentity,
        *,
        summary: str | None,
        source_until_message_id: str,
        source_until_created_at: datetime,
    ) -> None:
        """Persist a prompt-facing context summary."""

        await self._repository.store_context_summary(
            identity,
            summary=summary,
            source_until_message_id=source_until_message_id,
            source_until_created_at=source_until_created_at,
        )

    async def clear_session_summary(self, identity: ChatSessionIdentity) -> None:
        """Clear the prompt-facing context summary for one session."""

        await self._repository.clear_context_summary(session_id=identity.session_id)

    async def append_message(
        self,
        identity: ChatSessionIdentity,
        message_data: ChatMessageCreate,
    ) -> ChatMessageRow:
        """Append one normalized message to the chat session history."""

        return await self._repository.append_message(identity, message_data)

    async def append_observed_turn(  # noqa: PLR0913
        self,
        identity: ChatSessionIdentity,
        *,
        author_id: str,
        text_content: str,
        author_name: str | None = None,
        platform_message_id: str | None = None,
        reply_to_message_id: str | None = None,
        platform_reply_id: str | None = None,
        content: dict[str, Any] | None = None,
        meta: dict[str, Any] | None = None,
        raw_data: dict[str, Any] | None = None,  # noqa: ARG002
        message_kind: "MessageKind" = "text",
        directed_to_bot: bool = False,
        mentions_bot: bool = False,
        has_media: bool = False,
    ) -> ChatMessageRow:
        """Append one ambient observed turn as a thin conversation fact."""

        return await self._repository.append_message(
            identity,
            _ChatMessageCreate(
                author_role="user",
                author_id=author_id,
                author_name=author_name,
                text_content=text_content,
                message_kind=message_kind,
                turn_disposition="observed",
                directed_to_bot=directed_to_bot,
                mentions_bot=mentions_bot,
                has_media=has_media,
                platform_message_id=platform_message_id,
                reply_to_message_id=reply_to_message_id,
                platform_reply_id=platform_reply_id,
                content=content,
                meta=meta,
                raw_data=None,
            ),
        )

    async def mark_message_observed(
        self,
        *,
        message_id: str,
    ) -> ChatMessageRow | None:
        """Mark an existing persisted message as observed context."""

        return await self._repository.update_message_disposition(
            message_id=message_id,
            turn_disposition="observed",
        )

    async def list_recent_messages(
        self,
        identity: ChatSessionIdentity,
        *,
        max_messages: int,
    ) -> list[ChatContextMessageView]:
        """List recent messages for one chat session identity."""

        message_rows = await self._repository.list_recent_message_rows(
            identity,
            max_messages=max_messages,
        )
        message_rows.reverse()
        messages = [self._to_context_message_view(row) for row in message_rows]
        return trim_message_window(messages, max_messages=max_messages)

    async def list_recent_sessions(
        self,
        *,
        limit: int,
    ) -> list[ChatSessionAdminView]:
        rows = await self._repository.list_recent_session_rows(limit=limit)
        return [self._to_session_admin_view(row) for row in rows]

    async def get_session_view(
        self,
        *,
        session_id: str,
    ) -> ChatSessionAdminView | None:
        row = await self._repository.get_session_row(session_id=session_id)
        if row is None:
            return None
        return self._to_session_admin_view(row)

    async def list_messages_for_session(
        self,
        *,
        session_id: str,
        limit: int,
    ) -> list[ChatMessageDetailView]:
        rows = await self._repository.list_message_rows_for_session(
            session_id=session_id,
            limit=limit,
        )
        messages = [
            self._to_message_detail_view(
                message=row,
                session_id=session_id,
            )
            for row in rows
        ]
        messages.reverse()
        return messages

    async def get_message_by_platform_message_id(
        self,
        *,
        session_id: str,
        platform_message_id: str,
    ) -> ChatMessageDetailView | None:
        row = await self._repository.get_message_row_by_platform_message_id(
            session_id=session_id,
            platform_message_id=platform_message_id,
        )
        if row is None:
            return None
        return self._to_message_detail_view(
            message=row,
            session_id=session_id,
        )

    async def list_recent_user_ids_for_session(
        self,
        *,
        session_id: str,
        limit: int = 5,
    ) -> list[str]:
        """List distinct recent user author ids for one session."""

        return await self._repository.list_recent_user_ids_for_session(
            session_id=session_id,
            limit=limit,
        )

    async def get_session_identity(
        self,
        *,
        session_id: str,
    ) -> ChatSessionIdentity | None:
        """Load the canonical identity for one stored session id."""

        row = await self._repository.get_session_row(session_id=session_id)
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

    def _to_context_message_view(
        self,
        row: ChatMessageRow,
    ) -> ChatContextMessageView:
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
            turn_disposition=cast("TurnDisposition", row.turn_disposition),
        )

    def _to_session_admin_view(self, row: ChatSessionRow) -> ChatSessionAdminView:
        return ChatSessionAdminView(
            session_id=row.session_id,
            platform=row.platform,
            bot_id=row.bot_id,
            scene_type=cast("SceneType", row.scene_type),
            scene_id=row.scene_id,
            subject_id=row.subject_id,
            title=row.title,
            created_at=row.created_at,
            updated_at=row.updated_at,
            last_message_at=row.last_message_at,
        )

    def _to_message_detail_view(
        self,
        *,
        message: ChatMessageRow,
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
            turn_disposition=cast("TurnDisposition", message.turn_disposition),
        )


chat_session_service = ChatSessionService()
