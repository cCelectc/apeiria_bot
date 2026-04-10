"""Conversation boundary compatibility exports over the legacy context package."""

from .identity import (
    ScopeType,
    build_conversation_identity,
    build_conversation_identity_from_event,
    trim_turn_window,
)
from .models import AIContextTurnView, AIConversationIdentity
from .service import AIConversationService, AITurnCreate, ai_conversation_service

__all__ = [
    "AIContextTurnView",
    "AIConversationIdentity",
    "AIConversationService",
    "AITurnCreate",
    "ScopeType",
    "ai_conversation_service",
    "build_conversation_identity",
    "build_conversation_identity_from_event",
    "trim_turn_window",
]
