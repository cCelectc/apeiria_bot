"""Chat session kernel view models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from datetime import datetime

SceneType = Literal["group", "private"]
AuthorRole = Literal["user", "assistant", "system", "tool"]
MessageKind = Literal["text", "mixed", "media", "system", "tool"]
TurnDisposition = Literal["active", "observed", "generated", "tool", "system"]


@dataclass(frozen=True)
class ChatSessionIdentity:
    """Canonical chat session identity derived from a runtime event."""

    session_id: str
    platform: str
    bot_id: str
    scene_type: SceneType
    scene_id: str
    subject_id: str | None


@dataclass(frozen=True)
class ChatSessionContextSummary:
    """Prompt-facing overflow continuity summary for one chat session."""

    session_id: str
    summary_text: str
    source_until_message_id: str
    source_until_created_at: datetime
    updated_at: datetime


@dataclass(frozen=True)
class ChatContextMessageView:
    """Small immutable message view used by runtime context assembly."""

    message_id: str
    author_role: AuthorRole
    author_id: str
    author_name: str | None
    text_content: str
    content: dict[str, Any] | None
    created_at: datetime
    reply_to_message_id: str | None = None
    turn_disposition: TurnDisposition = "active"

    @property
    def sender_type(self) -> str:
        return "bot" if self.author_role == "assistant" else self.author_role

    @property
    def sender_id(self) -> str:
        return self.author_id

    @property
    def content_text(self) -> str:
        return self.text_content

    @property
    def is_observed_context(self) -> bool:
        return self.turn_disposition == "observed"


@dataclass(frozen=True)
class ChatSessionAdminView:
    """Session summary used by admin and workbench surfaces."""

    session_id: str
    platform: str
    bot_id: str
    scene_type: SceneType
    scene_id: str
    subject_id: str | None
    title: str | None
    created_at: datetime
    updated_at: datetime
    last_message_at: datetime


@dataclass(frozen=True)
class ChatMessageDetailView:
    """Expanded message view for workbench inspection."""

    message_id: str
    session_id: str
    platform_message_id: str | None
    reply_to_message_id: str | None
    platform_reply_id: str | None
    author_role: AuthorRole
    author_id: str
    author_name: str | None
    message_kind: MessageKind
    directed_to_bot: bool
    mentions_bot: bool
    has_media: bool
    text_content: str
    content: dict[str, Any] | None
    meta: dict[str, Any] | None
    raw_data: dict[str, Any] | None
    created_at: datetime
    turn_disposition: TurnDisposition = "active"

    @property
    def sender_type(self) -> str:
        return "bot" if self.author_role == "assistant" else self.author_role

    @property
    def sender_id(self) -> str:
        return self.author_id

    @property
    def content_text(self) -> str:
        return self.text_content

    @property
    def is_observed_context(self) -> bool:
        return self.turn_disposition == "observed"

    @property
    def raw_payload(self) -> dict[str, Any] | None:
        return self.meta or self.raw_data

    @property
    def trace_id(self) -> str | None:
        value = (self.meta or {}).get("trace_id")
        return value if isinstance(value, str) else None

    @property
    def source_id(self) -> str | None:
        value = (self.meta or {}).get("source_id")
        return value if isinstance(value, str) else None

    @property
    def model_name(self) -> str | None:
        value = (self.meta or {}).get("model_name")
        return value if isinstance(value, str) else None

    @property
    def recalled_memory_count(self) -> int | None:
        value = (self.meta or {}).get("recalled_memory_count")
        return value if isinstance(value, int) else None

    @property
    def tool_observation_count(self) -> int | None:
        value = (self.meta or {}).get("tool_observation_count")
        return value if isinstance(value, int) else None
