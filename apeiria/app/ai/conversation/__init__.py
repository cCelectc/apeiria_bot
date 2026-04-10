"""Conversation boundary exports with lazy service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .identity import (
    ScopeType,
    build_conversation_identity,
    build_conversation_identity_from_event,
    trim_turn_window,
)
from .models import AIContextTurnView, AIConversationIdentity

if TYPE_CHECKING:
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

_LAZY_EXPORTS = {
    "AIConversationService": ".service",
    "AITurnCreate": ".service",
    "ai_conversation_service": ".service",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
