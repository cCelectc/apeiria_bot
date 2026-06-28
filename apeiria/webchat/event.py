from __future__ import annotations

import re
from collections.abc import Iterable
from typing import override

from nonebot.adapters import Event as BaseEvent

from apeiria.webchat.message import Message, MessageSegment


class WebChatEvent(BaseEvent):
    """WebChat 事件基类。"""

    time: int
    self_id: str
    post_type: str

    @override
    def get_type(self) -> str:
        return self.post_type

    @override
    def get_event_name(self) -> str:
        return self.post_type

    @override
    def get_event_description(self) -> str:
        return self.post_type

    @override
    def get_user_id(self) -> str:
        raise ValueError("Event has no user_id")  # noqa: TRY003

    @override
    def get_session_id(self) -> str:
        raise ValueError("Event has no session_id")  # noqa: TRY003

    @override
    def get_message(self) -> Message:
        raise ValueError("Event has no message")  # noqa: TRY003

    @override
    def is_tome(self) -> bool:
        return False


class WebChatMessageEvent(WebChatEvent):
    """WebChat 消息事件。"""

    post_type: str = "message"
    message_id: str
    user_id: str
    message: Message
    scene_type: str  # "private" | "group"
    scene_id: str
    to_me: bool = False
    connection_id: str = ""

    @override
    def get_event_name(self) -> str:
        return f"message.{self.scene_type}"

    @override
    def get_event_description(self) -> str:
        scene = "private" if self.scene_type == "private" else f"group:{self.scene_id}"
        return f"Message from {self.user_id}@{scene}: {self.get_plaintext()!r}"

    @override
    def get_user_id(self) -> str:
        return self.user_id

    @override
    def get_session_id(self) -> str:
        if self.scene_type == "group":
            return f"webchat:group:{self.scene_id}"
        return f"webchat:private:{self.user_id}"

    @override
    def get_message(self) -> Message:
        return self.message

    @override
    def is_tome(self) -> bool:
        return self.to_me


def is_at_me(
    message: Message,
    scene_type: str,
    nicknames: Iterable[str],
) -> bool:
    """私聊恒真；群聊检测是否命中昵称前缀。"""
    if scene_type != "group":
        return True
    names = [re.escape(n) for n in nicknames if n]
    if not names or not message or message[0].type != "text":
        return False
    text = message[0].data.get("text", "")
    return bool(re.match(rf"^(?:{'|'.join(names)})\s*", text))


def strip_at_prefix(message: Message, nicknames: Iterable[str]) -> None:
    """从消息首段剥离已匹配的昵称前缀。"""
    names = [re.escape(n) for n in nicknames if n]
    if not names or not message or message[0].type != "text":
        return
    text = message[0].data.get("text", "")
    matched = re.match(rf"^(?:{'|'.join(names)})\s*", text)
    if not matched:
        return
    message[0].data["text"] = text[matched.end() :]
    if not message[0].data["text"]:
        del message[0]
    if not message:
        message.append(MessageSegment.text(""))


def resolve_to_me(
    message: Message,
    scene_type: str,
    nicknames: Iterable[str],
) -> bool:
    result = is_at_me(message, scene_type, nicknames)
    if result and scene_type == "group":
        strip_at_prefix(message, nicknames)
    return result
