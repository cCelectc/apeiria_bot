"""Web UI chat application services."""

from apeiria.app.chat.alconna import register_webchat_uninfo, register_webchat_uniseg
from apeiria.app.chat.connection import WebChatConnection
from apeiria.app.chat.gateway import (
    ChatAssetFileMissingError,
    ChatAssetNotFoundError,
    ChatAuthError,
    ChatGatewayService,
    chat_gateway_service,
)
from apeiria.app.chat.gateway_protocol import (
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
from apeiria.app.chat.service import WebChatService, web_chat_service

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
