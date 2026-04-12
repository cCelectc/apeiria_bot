"""Conversation kernel view models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from datetime import datetime

ScopeType = Literal["group", "private"]
SenderType = Literal["user", "bot", "system", "tool"]


@dataclass(frozen=True)
class AIConversationIdentity:
    """Canonical AI conversation identity derived from a runtime event."""

    conversation_id: str
    platform: str
    bot_id: str
    scope_type: ScopeType
    scope_id: str
    subject_user_id: str | None


@dataclass(frozen=True)
class AIContextTurnView:
    """Small immutable turn view used by the conversation kernel."""

    turn_id: str
    sender_type: SenderType
    sender_id: str
    content_text: str
    created_at: datetime


@dataclass(frozen=True)
class AIConversationAdminView:
    """Conversation summary used by AI admin and workbench surfaces."""

    conversation_id: str
    platform: str
    bot_id: str
    scope_type: ScopeType
    scope_id: str
    subject_user_id: str | None
    short_summary: str | None
    created_at: datetime
    updated_at: datetime
    last_active_at: datetime


@dataclass(frozen=True)
class AIConversationTurnDetailView:
    """Expanded turn view for workbench inspection."""

    turn_id: str
    conversation_id: str
    sender_type: SenderType
    sender_id: str
    content_text: str
    created_at: datetime
    raw_payload: dict[str, Any] | None
    trace_id: str | None
    source_id: str | None
    model_name: str | None
    recalled_memory_count: int | None
    tool_observation_count: int | None
