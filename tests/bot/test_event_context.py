"""Tests for bot event context extraction."""

from __future__ import annotations

from typing import cast

from apeiria.bot.event_context import group_id_from_event
from apeiria.bot.platform import event_user_id


class _FakePrivateEvent:
    def __init__(self, user_id: str, group_id: str | None = None) -> None:
        self.user_id = user_id
        self.group_id = group_id
        self.message_type = "private" if group_id is None else "group"

    def get_user_id(self) -> str:
        return self.user_id

    def get_session_id(self) -> str:
        if self.group_id is not None:
            return f"group_{self.group_id}_{self.user_id}"
        return self.user_id

    def get_message(self) -> _FakeMessage:
        return _FakeMessage("")


class _FakeMessage:
    def __init__(self, text: str) -> None:
        self._text = text

    def extract_plain_text(self) -> str:
        return self._text


class TestGroupIdFromEvent:
    def test_private_event_returns_none(self) -> None:
        event = _FakePrivateEvent("u1")
        result = group_id_from_event(cast("object", event))
        assert result is None

    def test_group_event_returns_group_id(self) -> None:
        event = _FakePrivateEvent("u1", group_id="group123")
        result = group_id_from_event(cast("object", event))
        assert result == "group123"


class TestEventUserId:
    def test_extracts_user_id(self) -> None:
        event = _FakePrivateEvent("user123")
        assert event_user_id(cast("object", event)) == "user123"

    def test_none_when_no_getter(self) -> None:
        result = event_user_id(cast("object", object()))
        assert result is None
