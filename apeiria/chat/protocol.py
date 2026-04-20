"""WebChat websocket protocol schemas and frame names."""

from __future__ import annotations

from datetime import (
    datetime,  # noqa: TC003 - required for Pydantic runtime schema resolution
)
from enum import Enum
from typing import Annotated, Final, Literal

from pydantic import BaseModel, Field, model_validator

FRAME_AUTH_HELLO: Final = "auth.hello"
FRAME_AUTH_OK: Final = "auth.ok"
FRAME_AUTH_ERROR: Final = "auth.error"
FRAME_CAPABILITIES_REQUEST: Final = "capabilities.request"
FRAME_CAPABILITIES_RESPONSE: Final = "capabilities.response"
FRAME_SESSION_CREATE: Final = "session.create"
FRAME_SESSION_UPDATE: Final = "session.update"
FRAME_SESSION_DELETE: Final = "session.delete"
FRAME_SESSION_CLOSE: Final = "session.close"
FRAME_SESSION_CLEAR_HISTORY: Final = "session.clear_history"
FRAME_SESSION_STATE: Final = "session.state"
FRAME_SESSION_LIST: Final = "session.list"
FRAME_SESSION_DELETED: Final = "session.deleted"
FRAME_SESSION_HISTORY_CLEARED: Final = "session.history_cleared"
FRAME_MESSAGE_SEND: Final = "message.send"
FRAME_MESSAGE_ACK: Final = "message.ack"
FRAME_MESSAGE_RECEIVE: Final = "message.receive"
FRAME_MESSAGE_ERROR: Final = "message.error"
FRAME_SYSTEM_INFO: Final = "system.info"
FRAME_SYSTEM_WARNING: Final = "system.warning"
FRAME_SYSTEM_ERROR: Final = "system.error"

CLIENT_FRAME_TYPES: Final[tuple[str, ...]] = (
    FRAME_AUTH_HELLO,
    FRAME_CAPABILITIES_REQUEST,
    FRAME_SESSION_CREATE,
    FRAME_SESSION_UPDATE,
    FRAME_SESSION_DELETE,
    FRAME_SESSION_CLOSE,
    FRAME_SESSION_CLEAR_HISTORY,
    FRAME_SESSION_LIST,
    FRAME_MESSAGE_SEND,
)

SERVER_FRAME_TYPES: Final[tuple[str, ...]] = (
    FRAME_AUTH_OK,
    FRAME_AUTH_ERROR,
    FRAME_CAPABILITIES_RESPONSE,
    FRAME_SESSION_STATE,
    FRAME_SESSION_LIST,
    FRAME_SESSION_DELETED,
    FRAME_SESSION_HISTORY_CLEARED,
    FRAME_MESSAGE_ACK,
    FRAME_MESSAGE_RECEIVE,
    FRAME_MESSAGE_ERROR,
    FRAME_SYSTEM_INFO,
    FRAME_SYSTEM_WARNING,
    FRAME_SYSTEM_ERROR,
)


class SessionStatus(str, Enum):
    READY = "ready"
    CLOSED = "closed"
    ERROR = "error"


class EnvelopeVersion(str, Enum):
    V1 = "1.0"


class TextSegment(BaseModel):
    type: Literal["text"] = "text"
    text: str


class ImageSegment(BaseModel):
    type: Literal["image"] = "image"
    url: str | None = None
    asset_id: str | None = None
    base64: str | None = None
    mime: str | None = None
    alt: str | None = None
    width: int | None = None
    height: int | None = None


class MentionSegment(BaseModel):
    type: Literal["mention"] = "mention"
    target: str
    display: str | None = None
    mention_type: str = "user"


class ReplySegment(BaseModel):
    type: Literal["reply"] = "reply"
    message_id: str
    text: str | None = None


class RawSegment(BaseModel):
    type: Literal["raw"] = "raw"
    segment_type: str
    data: dict[str, object] = Field(default_factory=dict)


ChatSegment = Annotated[
    TextSegment | ImageSegment | MentionSegment | ReplySegment | RawSegment,
    Field(discriminator="type"),
]


class WebUIPrincipal(BaseModel):
    id: str
    username: str
    role: str


class ChatSessionState(BaseModel):
    session_id: str
    status: SessionStatus
    target_user_id: str
    created_by: WebUIPrincipal | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ChatCapabilities(BaseModel):
    segment_types: list[str]
    mock_apis: list[str]


class AuthHelloPayload(BaseModel):
    token: str


class AuthOkPayload(BaseModel):
    principal: WebUIPrincipal


class ErrorPayload(BaseModel):
    code: str
    message: str


class SessionCreatePayload(BaseModel):
    target_user_id: str

    @model_validator(mode="after")
    def normalize_values(self) -> "SessionCreatePayload":
        self.target_user_id = self.target_user_id.strip()
        if not self.target_user_id:
            raise ValueError("target_user_id is required")  # noqa: TRY003
        if not self.target_user_id.isdigit():
            raise ValueError("target_user_id must be numeric")  # noqa: TRY003
        return self


class SessionUpdatePayload(BaseModel):
    session_id: str
    target_user_id: str | None = None

    @model_validator(mode="after")
    def normalize_values(self) -> "SessionUpdatePayload":
        self.session_id = self.session_id.strip()
        if self.target_user_id is not None:
            self.target_user_id = self.target_user_id.strip()
            if not self.target_user_id:
                raise ValueError("target_user_id cannot be empty")  # noqa: TRY003
            if not self.target_user_id.isdigit():
                raise ValueError("target_user_id must be numeric")  # noqa: TRY003
        if not self.session_id:
            raise ValueError("session_id is required")  # noqa: TRY003
        return self


class SessionDeletePayload(BaseModel):
    session_id: str

    @model_validator(mode="after")
    def normalize_values(self) -> "SessionDeletePayload":
        self.session_id = self.session_id.strip()
        if not self.session_id:
            raise ValueError("session_id is required")  # noqa: TRY003
        return self


class SessionStatePayload(BaseModel):
    session: ChatSessionState
    history: list["MessageReceivePayload"] = Field(default_factory=list)


class SessionListItem(BaseModel):
    session: ChatSessionState
    message_count: int = 0
    last_message: str | None = None
    last_message_at: datetime | None = None


class SessionListPayload(BaseModel):
    sessions: list[SessionListItem] = Field(default_factory=list)


class SessionDeletedPayload(BaseModel):
    session_id: str


class MessageSendPayload(BaseModel):
    session_id: str
    message_id: str
    segments: list[ChatSegment]


class MessageAckPayload(BaseModel):
    session_id: str
    message_id: str
    accepted: bool = True


class MessageReceivePayload(BaseModel):
    session_id: str
    message_id: str
    role: Literal["user", "bot", "system", "error"]
    segments: list[ChatSegment]
    timestamp: datetime
    trace_id: str | None = None


class SystemMessagePayload(BaseModel):
    message: str


class CapabilitiesResponsePayload(BaseModel):
    capabilities: ChatCapabilities


class ChatEnvelope(BaseModel):
    version: EnvelopeVersion = EnvelopeVersion.V1
    type: str
    request_id: str | None = None
    payload: dict[str, object] = Field(default_factory=dict)
