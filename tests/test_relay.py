from __future__ import annotations

from time import monotonic

import pytest


@pytest.fixture(scope="module", autouse=True)
def _require_relay_deps(after_nonebot_init: None) -> None:  # noqa: ARG001
    from nonebot import require

    require("nonebot_plugin_alconna")
    require("nonebot_plugin_uninfo")


def _clear() -> None:
    from apeiria.builtin_plugins.relay import _rates

    _rates.clear()


def test_rate_check_zero_count_always_true() -> None:
    _clear()
    from apeiria.builtin_plugins.relay import _rate_check

    assert _rate_check("u", 0, 60.0) is True


def test_rate_check_blocks_after_limit() -> None:
    _clear()
    from apeiria.builtin_plugins.relay import _rate_check, _rate_push

    _rate_push("u")
    _rate_push("u")
    assert _rate_check("u", 2, 60.0) is False


def test_rate_check_allows_after_one_push() -> None:
    _clear()
    from apeiria.builtin_plugins.relay import _rate_check, _rate_push

    _rate_push("u")
    assert _rate_check("u", 2, 60.0) is True


def test_rate_check_does_not_create_entry() -> None:
    _clear()
    from apeiria.builtin_plugins.relay import _rate_check, _rates

    _rate_check("x", 2, 60.0)
    assert "x" not in _rates


def test_prune_removes_expired_entry() -> None:
    _clear()
    from collections import deque

    from apeiria.builtin_plugins.relay import _prune_rates, _rates

    _rates["u"] = deque([monotonic() - 10_000])
    _prune_rates(monotonic(), 60.0)
    assert "u" not in _rates


def test_blank_text_is_empty() -> None:
    from nonebot_plugin_alconna import UniMessage
    from nonebot_plugin_alconna.uniseg import Text

    assert not UniMessage([Text("  ")]).strip()


def test_pure_image_is_valid() -> None:
    from nonebot_plugin_alconna import UniMessage
    from nonebot_plugin_alconna.uniseg import Image

    assert UniMessage([Image(url="u")]).strip()


def test_reply_only_with_blank_is_empty() -> None:
    from nonebot_plugin_alconna import UniMessage
    from nonebot_plugin_alconna.uniseg import Reply, Text

    body = UniMessage([Reply("1"), Text("   ")]).exclude(Reply).strip()
    assert not body


def test_exclude_reply_keeps_other_segments() -> None:
    from nonebot_plugin_alconna import UniMessage
    from nonebot_plugin_alconna.uniseg import Image, Reply, Text

    result = UniMessage([Reply("1"), Text("hi"), Image(url="u")]).exclude(Reply)
    assert not result.get(Reply)
    assert result.get(Text)
    assert result.get(Image)


def test_parse_target_valid() -> None:
    from apeiria.builtin_plugins.relay import _parse_target

    assert _parse_target("QQClient:123") == ("QQClient", "123")


def test_parse_target_no_colon() -> None:
    from apeiria.builtin_plugins.relay import _parse_target

    assert _parse_target("nocolon") is None


def test_parse_target_missing_parts() -> None:
    from apeiria.builtin_plugins.relay import _parse_target

    assert _parse_target(":123") is None
    assert _parse_target("scope:") is None
