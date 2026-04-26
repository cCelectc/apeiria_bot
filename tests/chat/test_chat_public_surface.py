from __future__ import annotations

import importlib
import sys

import pytest


def test_import_app_chat_exposes_expected_public_surface() -> None:
    for module_name in (
        "apeiria.app.chat",
        "apeiria.app.chat.gateway",
    ):
        sys.modules.pop(module_name, None)

    module = importlib.import_module("apeiria.app.chat")

    assert module.__name__ == "apeiria.app.chat"
    assert module.__all__ == [
        "AuthHelloPayload",
        "AuthOkPayload",
        "CapabilitiesResponsePayload",
        "ChatAssetFileMissingError",
        "ChatAssetNotFoundError",
        "ChatAuthError",
        "ChatCapabilities",
        "ChatEnvelope",
        "ChatGatewayService",
        "ChatSegment",
        "ChatSessionState",
        "EnvelopeVersion",
        "ErrorPayload",
        "ImageSegment",
        "MentionSegment",
        "MessageAckPayload",
        "MessageReceivePayload",
        "MessageSendPayload",
        "RawSegment",
        "ReplySegment",
        "SessionCreatePayload",
        "SessionDeletePayload",
        "SessionListItem",
        "SessionSelectPayload",
        "SessionSnapshotPayload",
        "SessionStatus",
        "SystemMessagePayload",
        "TextSegment",
        "WebChatConnection",
        "WebChatService",
        "WebUIPrincipal",
        "chat_gateway_service",
        "web_chat_service",
    ]


@pytest.mark.parametrize(
    "module_name",
    [
        "apeiria.chat",
        "apeiria.chat.gateway",
        "apeiria.chat.transport",
    ],
)
def test_legacy_chat_modules_are_removed(module_name: str) -> None:
    sys.modules.pop(module_name, None)

    with pytest.raises(ModuleNotFoundError):
        importlib.import_module(module_name)
