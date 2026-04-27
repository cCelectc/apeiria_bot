"""Public operation contracts for conversation persistence."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apeiria.conversation.models import AuthorRole, MessageKind


@dataclass(frozen=True)
class ChatMessageCreate:
    """Input payload for creating one persisted chat message."""

    author_role: "AuthorRole"
    author_id: str
    text_content: str
    author_name: str | None = None
    message_kind: "MessageKind" = "text"
    directed_to_bot: bool = False
    mentions_bot: bool = False
    has_media: bool = False
    platform_message_id: str | None = None
    reply_to_message_id: str | None = None
    platform_reply_id: str | None = None
    content: dict[str, Any] | None = None
    meta: dict[str, Any] | None = None
    raw_data: dict[str, Any] | None = None
