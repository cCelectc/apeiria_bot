from __future__ import annotations

import importlib
import sys
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from nonebot.adapters import Event, Message, MessageSegment
from nonebot.matcher import matchers
from pydantic import create_model

if TYPE_CHECKING:
    from collections.abc import Iterable, Mapping


# Pure plugin tests own parser, provider, store, and service edge cases. These
# helpers are intentionally small and only support NoneBug matcher lifecycle
# tests: trigger wiring, send/API expectations, and propagation behavior.


class FakeMessageSegment(MessageSegment["FakeMessage"]):
    @classmethod
    def get_message_class(cls) -> type["FakeMessage"]:
        return FakeMessage

    def __str__(self) -> str:
        if self.type == "text":
            return str(self.data.get("text", ""))
        return f"[fake:{self.type}]"

    def is_text(self) -> bool:
        return self.type == "text"

    @classmethod
    def text(cls, text: str) -> "FakeMessageSegment":
        return cls("text", {"text": text})


class FakeMessage(Message[FakeMessageSegment]):
    @classmethod
    def get_segment_class(cls) -> type[FakeMessageSegment]:
        return FakeMessageSegment

    @staticmethod
    def _construct(
        message: str | Iterable[Mapping[str, object]],
    ) -> Iterable[FakeMessageSegment]:
        if isinstance(message, str):
            yield FakeMessageSegment.text(message)
            return

        for segment in message:
            yield FakeMessageSegment(
                str(segment.get("type", "")),
                dict(segment.get("data", {})),
            )


def fake_message(text: str) -> FakeMessage:
    return FakeMessage(text)


def fake_text_segments(text: str) -> FakeMessage:
    return FakeMessage((FakeMessageSegment.text(text),))


def make_fake_event(  # noqa: PLR0913
    *,
    event_type: str = "message",
    user_id: str = "20000",
    group_id: str | None = None,
    message: FakeMessage | None = None,
    self_id: str = "10000",
    message_id: int | str = 123,
    reply: object | None = None,
    request_type: str | None = None,
    sub_type: str | None = None,
    flag: str | None = None,
    comment: str | None = None,
) -> Event:
    resolved_message = message or FakeMessage()
    fields: dict[str, tuple[type[Any], Any]] = {
        "self_id": (str, self_id),
        "message_id": (int | str, message_id),
        "user_id": (str, user_id),
        "group_id": (str | None, group_id),
        "reply": (object | None, reply),
        "request_type": (str | None, request_type),
        "sub_type": (str | None, sub_type),
        "flag": (str | None, flag),
        "comment": (str | None, comment),
    }

    class FakeEvent(Event):
        def get_type(self) -> str:
            return event_type

        def get_event_name(self) -> str:
            return "fake"

        def get_event_description(self) -> str:
            return resolved_message.extract_plain_text()

        def get_user_id(self) -> str:
            return user_id

        def get_session_id(self) -> str:
            if group_id is None:
                return f"private:{user_id}"
            return f"group:{group_id}:{user_id}"

        def get_message(self) -> FakeMessage:
            return resolved_message

        def is_tome(self) -> bool:
            return True

    return create_model("FakeEvent", __base__=FakeEvent, **fields)()


def reply(
    message_id: int | str = 456,
    *,
    user_id: str = "10000",
) -> SimpleNamespace:
    return SimpleNamespace(
        message_id=message_id,
        sender=SimpleNamespace(user_id=user_id),
    )


def import_fresh_plugin(module_name: str) -> Any:
    existing = sys.modules.pop(module_name, None)
    if existing is not None:
        for priority_matchers in list(matchers.values()):
            priority_matchers[:] = [
                matcher
                for matcher in priority_matchers
                if matcher.module_name != module_name
            ]
    return importlib.import_module(module_name)
