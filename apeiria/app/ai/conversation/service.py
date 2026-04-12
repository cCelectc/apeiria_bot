"""Conversation service for AI identity and turn ingestion."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, cast
from uuid import uuid4

from sqlalchemy import select

from apeiria.app.ai.conversation.identity import (
    build_conversation_identity_from_event,
    trim_turn_window,
)
from apeiria.app.ai.conversation.models import (
    AIContextTurnView,
    AIConversationAdminView,
    AIConversationIdentity,
    AIConversationTurnDetailView,
    SenderType,
)
from apeiria.app.ai.conversation.summary import build_short_conversation_summary
from apeiria.infra.db.models import AIConversation, AITurn

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event
    from sqlalchemy.ext.asyncio import AsyncSession

    from apeiria.app.ai.conversation.models import ScopeType

def _utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


@dataclass(frozen=True)
class AITurnCreate:
    """Input payload for creating one persisted AI turn."""

    sender_type: SenderType
    sender_id: str
    content_text: str
    raw_payload: Any | None = None


class AIConversationService:
    """Conversation service for conversation upsert and turn append."""

    @staticmethod
    def _deserialize_raw_payload(raw_payload_json: str | None) -> dict[str, Any] | None:
        if not raw_payload_json:
            return None
        try:
            payload = json.loads(raw_payload_json)
        except json.JSONDecodeError:
            return None
        return payload if isinstance(payload, dict) else None

    async def ensure_conversation(
        self,
        session: "AsyncSession",
        identity: AIConversationIdentity,
    ) -> AIConversation:
        """Create or update the canonical AI conversation row for one scene."""

        result = await session.execute(
            select(AIConversation).where(
                AIConversation.conversation_id == identity.conversation_id
            )
        )
        conversation = result.scalar_one_or_none()
        if conversation is None:
            conversation = AIConversation(
                conversation_id=identity.conversation_id,
                platform=identity.platform,
                bot_id=identity.bot_id,
                scope_type=identity.scope_type,
                scope_id=identity.scope_id,
                subject_user_id=identity.subject_user_id,
            )
            session.add(conversation)
            await session.flush()

        conversation.last_active_at = _utcnow_naive()
        return conversation

    async def update_short_summary(
        self,
        session: "AsyncSession",
        identity: AIConversationIdentity,
        *,
        turns: list[AIContextTurnView],
    ) -> str | None:
        """Refresh the compact stored summary for one conversation."""

        conversation = await self.ensure_conversation(session, identity)
        summary = build_short_conversation_summary(turns)
        conversation.short_summary = summary
        await session.flush()
        return summary

    async def append_turn(
        self,
        session: "AsyncSession",
        identity: AIConversationIdentity,
        turn_data: AITurnCreate,
    ) -> AITurn:
        """Append one turn to the AI conversation history."""

        conversation = await self.ensure_conversation(session, identity)
        turn = AITurn(
            turn_id=f"turn_{uuid4().hex}",
            conversation_pk=conversation.id,
            sender_type=turn_data.sender_type,
            sender_id=turn_data.sender_id,
            content_text=turn_data.content_text,
            raw_payload_json=(
                json.dumps(
                    turn_data.raw_payload,
                    ensure_ascii=False,
                    sort_keys=True,
                    default=str,
                )
                if turn_data.raw_payload is not None
                else None
            ),
        )
        session.add(turn)
        await session.flush()
        return turn

    async def ingest_event(
        self,
        session: "AsyncSession",
        bot: "Bot",
        event: "Event",
    ) -> tuple[AIConversationIdentity, AITurn] | None:
        """Convert one runtime event into a canonical AI turn."""

        identity = build_conversation_identity_from_event(bot, event)
        if identity is None:
            return None

        raw_payload = (
            event.model_dump(mode="json") if hasattr(event, "model_dump") else None
        )
        turn = await self.append_turn(
            session,
            identity,
            AITurnCreate(
                sender_type="user",
                sender_id=str(event.get_user_id()),
                content_text=event.get_plaintext(),
                raw_payload=raw_payload,
            ),
        )
        return identity, turn

    async def list_recent_turns(
        self,
        session: "AsyncSession",
        identity: AIConversationIdentity,
        *,
        max_turns: int,
    ) -> list[AIContextTurnView]:
        """List recent turns for one conversation identity."""

        result = await session.execute(
            select(AITurn)
            .join(AIConversation, AITurn.conversation_pk == AIConversation.id)
            .where(AIConversation.conversation_id == identity.conversation_id)
            .order_by(AITurn.created_at.asc(), AITurn.id.asc())
        )
        turns = [
            AIContextTurnView(
                turn_id=turn.turn_id,
                sender_type=cast("SenderType", turn.sender_type),
                sender_id=turn.sender_id,
                content_text=turn.content_text,
                created_at=turn.created_at.replace(tzinfo=timezone.utc)
                if turn.created_at.tzinfo is None
                else turn.created_at,
            )
            for turn in result.scalars().all()
        ]
        return trim_turn_window(turns, max_turns=max_turns)

    async def list_recent_conversations(
        self,
        session: "AsyncSession",
        *,
        limit: int,
    ) -> list[AIConversationAdminView]:
        result = await session.execute(
            select(AIConversation)
            .order_by(AIConversation.last_active_at.desc(), AIConversation.id.desc())
            .limit(limit)
        )
        return [
            AIConversationAdminView(
                conversation_id=row.conversation_id,
                platform=row.platform,
                bot_id=row.bot_id,
                scope_type=cast("ScopeType", row.scope_type),
                scope_id=row.scope_id,
                subject_user_id=row.subject_user_id,
                short_summary=row.short_summary,
                created_at=row.created_at.replace(tzinfo=timezone.utc)
                if row.created_at.tzinfo is None
                else row.created_at,
                updated_at=row.updated_at.replace(tzinfo=timezone.utc)
                if row.updated_at.tzinfo is None
                else row.updated_at,
                last_active_at=row.last_active_at.replace(tzinfo=timezone.utc)
                if row.last_active_at.tzinfo is None
                else row.last_active_at,
            )
            for row in result.scalars().all()
        ]

    async def get_conversation_view(
        self,
        session: "AsyncSession",
        *,
        conversation_id: str,
    ) -> AIConversationAdminView | None:
        """Load one admin conversation view by stable conversation id."""

        result = await session.execute(
            select(AIConversation).where(
                AIConversation.conversation_id == conversation_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return AIConversationAdminView(
            conversation_id=row.conversation_id,
            platform=row.platform,
            bot_id=row.bot_id,
            scope_type=cast("ScopeType", row.scope_type),
            scope_id=row.scope_id,
            subject_user_id=row.subject_user_id,
            short_summary=row.short_summary,
            created_at=row.created_at.replace(tzinfo=timezone.utc)
            if row.created_at.tzinfo is None
            else row.created_at,
            updated_at=row.updated_at.replace(tzinfo=timezone.utc)
            if row.updated_at.tzinfo is None
            else row.updated_at,
            last_active_at=row.last_active_at.replace(tzinfo=timezone.utc)
            if row.last_active_at.tzinfo is None
            else row.last_active_at,
        )

    async def list_turns_for_conversation(
        self,
        session: "AsyncSession",
        *,
        conversation_id: str,
        limit: int,
    ) -> list[AIConversationTurnDetailView]:
        result = await session.execute(
            select(AITurn, AIConversation.conversation_id)
            .join(AIConversation, AITurn.conversation_pk == AIConversation.id)
            .where(AIConversation.conversation_id == conversation_id)
            .order_by(AITurn.created_at.desc(), AITurn.id.desc())
            .limit(limit)
        )
        rows = result.all()
        turns = [
            self._to_turn_detail_view(turn=turn, conversation_id=conversation_id_value)
            for turn, conversation_id_value in rows
        ]
        turns.reverse()
        return turns

    async def get_conversation_identity(
        self,
        session: "AsyncSession",
        *,
        conversation_id: str,
    ) -> AIConversationIdentity | None:
        """Load the canonical identity for one stored conversation id."""

        result = await session.execute(
            select(AIConversation).where(
                AIConversation.conversation_id == conversation_id
            )
        )
        row = result.scalar_one_or_none()
        if row is None:
            return None
        return AIConversationIdentity(
            conversation_id=row.conversation_id,
            platform=row.platform,
            bot_id=row.bot_id,
            scope_type=cast("ScopeType", row.scope_type),
            scope_id=row.scope_id,
            subject_user_id=row.subject_user_id,
        )

    def _to_turn_detail_view(
        self,
        *,
        turn: AITurn,
        conversation_id: str,
    ) -> AIConversationTurnDetailView:
        raw_payload = self._deserialize_raw_payload(turn.raw_payload_json)
        return AIConversationTurnDetailView(
            turn_id=turn.turn_id,
            conversation_id=conversation_id,
            sender_type=cast("SenderType", turn.sender_type),
            sender_id=turn.sender_id,
            content_text=turn.content_text,
            created_at=turn.created_at.replace(tzinfo=timezone.utc)
            if turn.created_at.tzinfo is None
            else turn.created_at,
            raw_payload=raw_payload,
            trace_id=raw_payload.get("trace_id") if raw_payload else None,
            source_id=raw_payload.get("source_id") if raw_payload else None,
            model_name=raw_payload.get("model_name") if raw_payload else None,
            recalled_memory_count=(
                int(raw_payload["recalled_memory_count"])
                if raw_payload
                and raw_payload.get("recalled_memory_count") is not None
                else None
            ),
            tool_observation_count=(
                int(raw_payload["tool_observation_count"])
                if raw_payload
                and raw_payload.get("tool_observation_count") is not None
                else None
            ),
        )


ai_conversation_service = AIConversationService()
