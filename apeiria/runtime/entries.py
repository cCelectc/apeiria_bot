"""Lightweight runtime entry models for trace and log context."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Final, Literal


class ApeiriaEntryKind(str, Enum):
    """Top-level runtime entry categories."""

    CONVERSATION = "conversation"
    CONTROL = "control"
    SYSTEM = "system"


class ApeiriaEntryTrigger(str, Enum):
    """Concrete triggers that describe how a runtime entry was initiated."""

    NONEBOT_MESSAGE = "nonebot_message"
    WEB_CHAT_MESSAGE = "web_chat_message"
    AI_FUTURE_TASK = "ai_future_task"
    WEBUI_ACTION = "webui_action"
    CLI_ACTION = "cli_action"
    STARTUP = "startup"
    CLEANUP = "cleanup"


_CONVERSATION_TRIGGERS: Final[tuple[ApeiriaEntryTrigger, ...]] = (
    ApeiriaEntryTrigger.NONEBOT_MESSAGE,
    ApeiriaEntryTrigger.WEB_CHAT_MESSAGE,
    ApeiriaEntryTrigger.AI_FUTURE_TASK,
)


@dataclass(frozen=True, slots=True)
class ApeiriaEntry:
    """Minimal runtime entry descriptor."""

    kind: ApeiriaEntryKind
    trigger: ApeiriaEntryTrigger


def resolve_message_entry_trigger(event: object | None) -> ApeiriaEntryTrigger:
    """Map a runtime message event to its lightweight trace trigger."""

    if event is not None:
        from apeiria.chat.event import WebChatMessageEvent

        if isinstance(event, WebChatMessageEvent):
            return ApeiriaEntryTrigger.WEB_CHAT_MESSAGE
    return ApeiriaEntryTrigger.NONEBOT_MESSAGE


def build_conversation_entry(trigger: ApeiriaEntryTrigger) -> ApeiriaEntry:
    """Build a conversation-scoped runtime entry for trace usage."""

    if trigger not in _CONVERSATION_TRIGGERS:
        raise ValueError
    return ApeiriaEntry(kind=ApeiriaEntryKind.CONVERSATION, trigger=trigger)


def build_ai_trace_entry(
    runtime_mode: Literal["message", "future_task"],
    *,
    event: object | None = None,
) -> ApeiriaEntry:
    """Map AI runtime entrypoints to lightweight trace context."""

    if runtime_mode == "future_task":
        return build_conversation_entry(ApeiriaEntryTrigger.AI_FUTURE_TASK)
    return build_conversation_entry(resolve_message_entry_trigger(event))


__all__ = [
    "ApeiriaEntry",
    "ApeiriaEntryKind",
    "ApeiriaEntryTrigger",
    "build_ai_trace_entry",
    "build_conversation_entry",
    "resolve_message_entry_trigger",
]
