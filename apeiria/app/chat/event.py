"""Event types for WebChat."""

from __future__ import annotations

from typing import Any

from nonebot.adapters import Event

from .message import WebChatMessage  # noqa: TC001
from .session import ChatSession  # noqa: TC001


class WebChatMessageEvent(Event):
    session: "ChatSession"
    message: "WebChatMessage"
    message_id: str
    time: int
    self_id: str
    post_type: str
    message_type: str
    user_id: str

    def __init__(
        self,
        *,
        session: "ChatSession",
        message: "WebChatMessage",
        message_id: str,
        timestamp: int,
        self_id: str = "webchat",
        **kwargs: Any,
    ) -> None:
        event_data = {
            "session": session,
            "message": message,
            "message_id": message_id,
            "time": timestamp,
            "self_id": self_id,
            "post_type": "message",
            "message_type": "private",
            "user_id": session.target_user_id,
            **kwargs,
        }
        super().__init__(**event_data)

    def get_type(self) -> str:
        return "message"

    def get_event_name(self) -> str:
        return "message.private"

    def get_event_description(self) -> str:
        return f"WebUI chat: {self.get_plaintext()}"

    def get_message(self) -> "WebChatMessage":
        return self.message

    def get_plaintext(self) -> str:
        return str(self.message)

    def get_user_id(self) -> str:
        return self.user_id

    def get_session_id(self) -> str:
        return self.session.target_user_id

    def is_tome(self) -> bool:
        return True


WebChatMessageEvent.model_rebuild()
