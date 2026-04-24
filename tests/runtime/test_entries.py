from datetime import datetime, timezone

from nonebot.adapters import Event
from pytest import raises

from apeiria.chat.event import WebChatMessageEvent
from apeiria.chat.message import WebChatMessage
from apeiria.chat.protocol import SessionStatus, WebUIPrincipal
from apeiria.chat.session import ChatSession
from apeiria.runtime.entries import (
    ApeiriaEntryKind,
    ApeiriaEntryTrigger,
    build_ai_trace_entry,
    build_conversation_entry,
)


class FakeMessageEvent(Event):
    user_id: str
    message: WebChatMessage

    def __init__(self, *, user_id: str = "10001", message: str = "hello") -> None:
        event_data = {
            "user_id": user_id,
            "message": WebChatMessage(message),
        }
        super().__init__(**event_data)
        self.user_id = user_id
        self.message = WebChatMessage(message)

    def get_type(self) -> str:
        return "message"

    def get_event_name(self) -> str:
        return "message.private"

    def get_event_description(self) -> str:
        return str(self.message)

    def get_user_id(self) -> str:
        return self.user_id

    def get_session_id(self) -> str:
        return self.user_id

    def get_message(self) -> WebChatMessage:
        return self.message

    def get_plaintext(self) -> str:
        return str(self.message)

    def is_tome(self) -> bool:
        return True


def _entry_kind_names() -> tuple[str, ...]:
    return tuple(ApeiriaEntryKind.__members__)


def _entry_trigger_name(trigger: ApeiriaEntryTrigger) -> str:
    return trigger.name


def _build_webchat_event() -> WebChatMessageEvent:
    return WebChatMessageEvent(
        session=ChatSession(
            session_id="session-1",
            created_by=WebUIPrincipal(id="webui", username="webui", role="admin"),
            target_user_id="10001",
            status=SessionStatus.READY,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        ),
        message=WebChatMessage("hello from webchat"),
        message_id="message-1",
        timestamp=1,
    )


def test_future_task_uses_conversation_kind() -> None:
    entry = build_conversation_entry(ApeiriaEntryTrigger.AI_FUTURE_TASK)

    assert entry.kind is ApeiriaEntryKind.CONVERSATION
    assert entry.trigger is ApeiriaEntryTrigger.AI_FUTURE_TASK


def test_ai_future_task_is_not_a_top_level_entry_kind() -> None:
    assert _entry_kind_names() == ("CONVERSATION", "CONTROL", "SYSTEM")
    assert "AI_FUTURE_TASK" not in ApeiriaEntryKind.__members__
    assert _entry_trigger_name(ApeiriaEntryTrigger.AI_FUTURE_TASK) == "AI_FUTURE_TASK"


def test_build_conversation_entry_rejects_non_conversation_triggers() -> None:
    for trigger in (
        ApeiriaEntryTrigger.STARTUP,
        ApeiriaEntryTrigger.CLEANUP,
        ApeiriaEntryTrigger.CLI_ACTION,
        ApeiriaEntryTrigger.WEBUI_ACTION,
    ):
        with raises(ValueError):
            build_conversation_entry(trigger)


def test_build_ai_trace_entry_maps_webchat_message_to_webchat_conversation() -> None:
    entry = build_ai_trace_entry("message", event=_build_webchat_event())

    assert entry.kind is ApeiriaEntryKind.CONVERSATION
    assert entry.trigger is ApeiriaEntryTrigger.WEB_CHAT_MESSAGE


def test_build_ai_trace_entry_maps_other_message_events_to_nonebot_conversation(
) -> None:
    entry = build_ai_trace_entry("message", event=FakeMessageEvent())

    assert entry.kind is ApeiriaEntryKind.CONVERSATION
    assert entry.trigger is ApeiriaEntryTrigger.NONEBOT_MESSAGE


def test_build_ai_trace_entry_maps_future_task_to_future_task_conversation() -> None:
    entry = build_ai_trace_entry("future_task")

    assert entry.kind is ApeiriaEntryKind.CONVERSATION
    assert entry.trigger is ApeiriaEntryTrigger.AI_FUTURE_TASK
