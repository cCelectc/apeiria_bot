"""Chat session kernel view models."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from datetime import datetime

SceneType = Literal["group", "private"]
AuthorRole = Literal["user", "assistant", "system", "tool"]
MessageKind = Literal["text", "mixed", "media", "system", "tool"]


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
class ChatContextMessageView:
    """Small immutable message view used by runtime context assembly."""

    message_id: str
    author_role: AuthorRole
    author_id: str
    author_name: str | None
    text_content: str
    content: dict[str, Any] | None
    created_at: datetime

    @property
    def sender_type(self) -> str:
        return "bot" if self.author_role == "assistant" else self.author_role

    @property
    def sender_id(self) -> str:
        return self.author_id

    @property
    def content_text(self) -> str:
        return self.text_content


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
    summary_text: str | None
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
