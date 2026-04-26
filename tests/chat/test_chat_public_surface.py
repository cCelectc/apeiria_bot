from __future__ import annotations

import importlib


def test_import_apeiria_chat_exposes_expected_public_surface() -> None:
    module = importlib.import_module("apeiria.chat")

    assert module.__name__ == "apeiria.chat"
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
        "SessionDeletedPayload",
        "SessionListItem",
        "SessionListPayload",
        "SessionStatePayload",
        "SessionStatus",
        "SessionUpdatePayload",
        "SystemMessagePayload",
        "TextSegment",
        "WebChatConnection",
        "WebChatService",
        "WebUIPrincipal",
        "chat_gateway_service",
        "web_chat_service",
    ]
