"""Web UI chat application services."""

from apeiria.webchat.alconna import register_webchat_uninfo, register_webchat_uniseg
from apeiria.webchat.connection import WebChatConnection
from apeiria.webchat.gateway import (
    ChatAssetFileMissingError,
    ChatAssetNotFoundError,
    ChatAuthError,
    ChatGatewayService,
    chat_gateway_service,
)
from apeiria.webchat.gateway_protocol import (
    AuthOkPayload,
    CapabilitiesResponsePayload,
    ChatCapabilities,
    ChatEnvelope,
    ChatSegment,
    ChatSessionState,
    EnvelopeVersion,
    ErrorPayload,
    ImageSegment,
    MentionSegment,
    MessageAckPayload,
    MessageReceivePayload,
    MessageSendPayload,
    RawSegment,
    ReplySegment,
    SessionCreatePayload,
    SessionDeletePayload,
    SessionListItem,
    SessionSelectPayload,
    SessionSnapshotPayload,
    SessionStatus,
    SystemMessagePayload,
    TextSegment,
    WebUIPrincipal,
)
from apeiria.webchat.service import WebChatService, web_chat_service


def _ensure_alconna_registrations() -> None:
    """Register webchat alconna extensions (safe to call once framework is loaded).

    Called from the framework bootstrap phase after nonebot_plugin_alconna
    is confirmed loaded, rather than at module import time.
    """
    register_webchat_uniseg()
    register_webchat_uninfo()


__all__ = [
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
