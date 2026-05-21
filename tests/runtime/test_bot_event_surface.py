from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from apeiria.bot.event_context import group_id_from_event
from apeiria.bot.normalization import (
    build_debug_raw_payload,
    build_normalized_content,
    detect_has_media,
    resolve_message_kind,
)


def test_group_id_from_event_prefers_platform_field() -> None:
    event = SimpleNamespace(group_id=1234)

    assert group_id_from_event(event) == "1234"


def test_group_id_from_event_falls_back_to_session_shape() -> None:
    event = _Event(session_id="group_9876_user_1", user_id="user-1")

    assert group_id_from_event(event) == "9876"


def test_bot_normalization_keeps_safe_message_payload() -> None:
    raw_data: dict[str, Any] = {
        "message_id": "m-1",
        "user_id": "u-1",
        "group_id": "g-1",
        "sender": {"card": "Alice", "token": "drop"},
        "reply": {"message_id": "m-0", "text": "quoted"},
        "message": [
            {"type": "text", "data": {"text": "hello"}},
            {"type": "at", "data": {"qq": 42}},
            {"type": "image", "data": {"url": "https://example.test/a.png"}},
            {"type": "json", "data": {"id": "safe", "secret": "drop"}},
        ],
    }

    content = build_normalized_content(
        raw_data=raw_data,
        text_content="hello",
        adapter="onebot",
    )
    debug_payload = build_debug_raw_payload(raw_data)

    assert detect_has_media(raw_data) is True
    assert resolve_message_kind(text_content="hello", has_media=True) == "mixed"
    assert content["mentioned_user_ids"] == ["42"]
    assert content["quoted_text"] == "quoted"
    assert {"type": "image", "url": "https://example.test/a.png"} in content["segments"]
    assert {
        "type": "adapter",
        "segment_type": "json",
        "adapter": "onebot",
        "data": {"id": "safe"},
    } in content["segments"]
    assert debug_payload == {
        "message_id": "m-1",
        "user_id": "u-1",
        "group_id": "g-1",
        "sender": {"card": "Alice"},
        "reply": {"message_id": "m-0", "text": "quoted"},
        "message_segment_types": ["text", "at", "image", "json"],
    }


class _Event:
    def __init__(self, *, session_id: str, user_id: str) -> None:
        self._session_id = session_id
        self._user_id = user_id

    def get_session_id(self) -> str:
        return self._session_id

    def get_user_id(self) -> str:
        return self._user_id
