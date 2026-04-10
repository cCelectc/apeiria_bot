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
    AIConversationIdentity,
    SenderType,
)
from apeiria.infra.db.models import AIConversation, AITurn

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event
    from sqlalchemy.ext.asyncio import AsyncSession


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


ai_conversation_service = AIConversationService()
