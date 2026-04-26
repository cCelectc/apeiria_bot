from __future__ import annotations

import importlib
import sys


def test_import_apeiria_conversation_does_not_eagerly_import_runtime_services() -> None:
    for module_name in (
        "apeiria.conversation",
        "apeiria.conversation.service",
        "apeiria.ai.model.gateway",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.conversation")

    assert module.__name__ == "apeiria.conversation"
    assert module.__all__ == [
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

    assert "apeiria.conversation.service" not in sys.modules
    assert "apeiria.ai.model.gateway" not in sys.modules

    chat_session_service = module.chat_session_service

    assert (
        chat_session_service
        is sys.modules["apeiria.conversation.service"].chat_session_service
    )
