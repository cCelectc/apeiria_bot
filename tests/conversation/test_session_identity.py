from __future__ import annotations

import pytest

from apeiria.conversation.models import SessionIdentity


def test_parse_valid() -> None:
    sid = SessionIdentity.parse("onebot:group:12345")
    assert sid.platform == "onebot"
    assert sid.scene_type == "group"
    assert sid.scene_id == "12345"


def test_session_id_property() -> None:
    sid = SessionIdentity(platform="qq", scene_type="private", scene_id="999")
    assert sid.session_id == "qq:private:999"


def test_parse_invalid() -> None:
    with pytest.raises(ValueError, match="Invalid session_id"):
        SessionIdentity.parse("invalid")


def test_parse_with_colons_in_scene_id() -> None:
    sid = SessionIdentity.parse("platform:type:id:with:colons")
    assert sid.platform == "platform"
    assert sid.scene_type == "type"
    assert sid.scene_id == "id:with:colons"
