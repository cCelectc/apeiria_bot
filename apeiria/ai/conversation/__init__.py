"""Conversation boundary exports with lazy service loading."""

from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

from .identity import (
    SceneType,
    build_chat_session_identity,
    build_chat_session_identity_from_event,
    build_participant_subject_id,
    trim_message_window,
)
from .models import (
    ChatContextMessageView,
    ChatMessageDetailView,
    ChatSessionAdminView,
    ChatSessionIdentity,
)

if TYPE_CHECKING:
    from .service import (
        ChatMessageCreate,
        ChatSessionService,
        chat_session_service,
    )

__all__ = [
    "ChatContextMessageView",
    "ChatMessageCreate",
    "ChatMessageDetailView",
    "ChatSessionAdminView",
    "ChatSessionIdentity",
    "ChatSessionService",
    "SceneType",
    "build_chat_session_identity",
    "build_chat_session_identity_from_event",
    "build_participant_subject_id",
    "chat_session_service",
    "trim_message_window",
]

_LAZY_EXPORTS = {
    "ChatMessageCreate": ".service",
    "ChatSessionService": ".service",
    "chat_session_service": ".service",
}


def __getattr__(name: str) -> Any:
    module_name = _LAZY_EXPORTS.get(name)
    if module_name is None:
        raise AttributeError(name)
    module = import_module(module_name, __name__)
    value = getattr(module, name)
    globals()[name] = value
    return value
