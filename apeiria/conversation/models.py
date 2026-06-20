from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from datetime import datetime

SceneType = Literal["group", "private"]
AuthorRole = Literal["user", "assistant", "system", "tool"]
MessageKind = Literal["text", "mixed", "media", "system", "tool"]
TurnDisposition = Literal["active", "observed", "generated", "tool", "system"]

_SESSION_ID_PART_COUNT = 3


@dataclass(frozen=True)
class ChatSessionIdentity:
    """Canonical chat session identity derived from a runtime event."""

    session_id: str
    platform: str
    bot_id: str
    scene_type: SceneType
    scene_id: str
    subject_id: str | None


@dataclass
class SessionIdentity:
    platform: str
    scene_type: str
    scene_id: str

    @property
    def session_id(self) -> str:
        return f"{self.platform}:{self.scene_type}:{self.scene_id}"

    @classmethod
    def parse(cls, session_id: str) -> SessionIdentity:
        parts = session_id.split(":", 2)
        if len(parts) != _SESSION_ID_PART_COUNT:
            msg = f"Invalid session_id format: {session_id}"
            raise ValueError(msg)
        return cls(
            platform=parts[0],
            scene_type=parts[1],
            scene_id=parts[2],
        )


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
