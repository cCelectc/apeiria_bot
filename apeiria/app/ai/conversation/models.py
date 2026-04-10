"""Conversation kernel view models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Literal

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
