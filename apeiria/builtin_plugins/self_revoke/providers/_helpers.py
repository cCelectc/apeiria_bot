from __future__ import annotations

from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING, cast

from nonebot.log import logger

if TYPE_CHECKING:
    from nonebot.adapters import Bot

from apeiria.bot.platform import (
    adapter_name,
    call_platform_api,
    event_message_id,
    id_value,
    mapping_string_attr,
    nested_string_attr,
    string_attr,
)

from ._types import RevokeActionResult, RevokeTarget

_ONEBOT_SUCCESS_REACTION_EMOJI_ID = "124"
_ONEBOT_FAILURE_REACTION_EMOJI_ID = "424"
_ONEBOT_V11_ADAPTER_NAME = "onebotv11"
_ONEBOT_V12_ADAPTER_NAME = "onebotv12"
_TELEGRAM_ADAPTER_NAME = "telegram"
_DISCORD_ADAPTER_NAME = "discord"
_QQ_ADAPTER_NAME = "qq"
_FEISHU_ADAPTER_NAME = "feishu"
_SATORI_ADAPTER_NAME = "satori"


def _normalized_adapter_name(bot: object) -> str:
    return adapter_name(bot)


def _string_attr(value: object, name: str) -> str | None:
    return string_attr(value, name)


def _nested_string_attr(value: object, *names: str) -> str | None:
    return nested_string_attr(value, *names)


def _mapping_string_attr(value: object, key: str) -> str | None:
    return mapping_string_attr(value, key)


def _event_type_name(event: object) -> str:
    value = getattr(event, "__type__", None)
    if value is None:
        return ""
    name = getattr(value, "value", value)
    return str(name).lower()


def _target_matches_bot_id(target: RevokeTarget, bot_ids: tuple[object, ...]) -> bool:
    normalized_bot_ids = {
        str(item).strip() for item in bot_ids if item is not None and str(item).strip()
    }
    return target.author_id is not None and target.author_id in normalized_bot_ids


def _event_message_id(event: object) -> str | None:
    return event_message_id(event)


def _feishu_bot_app_id(bot: object) -> str | None:
    return _nested_string_attr(bot, "bot_config", "app_id") or _string_attr(
        bot,
        "self_id",
    )


def _satori_bot_user_id(bot: object) -> str | None:
    getter = getattr(bot, "get_self_id", None)
    if callable(getter):
        try:
            value = getter()
        except Exception:  # noqa: BLE001
            value = None
        if value is not None and str(value).strip():
            return str(value).strip()
    return _nested_string_attr(bot, "self_info", "id")


def _satori_channel_id(event: object) -> str | None:
    return _nested_string_attr(event, "channel", "id")


def _satori_event_message_id(event: object) -> str | None:
    return (
        _string_attr(event, "msg_id")
        or _nested_string_attr(event, "message", "id")
        or _event_message_id(event)
    )


def _satori_reply_message_id(reply: object) -> str | None:
    return _mapping_string_attr(getattr(reply, "data", None), "id") or _string_attr(
        reply,
        "id",
    )


def _satori_reply_author_id(reply: object) -> str | None:
    children = getattr(reply, "children", None)
    getter = getattr(children, "get", None)
    if not callable(getter):
        return None
    try:
        author_segments = getter("author")
    except Exception:  # noqa: BLE001
        return None
    if not isinstance(author_segments, Sequence):
        return None
    try:
        author = author_segments[0]
    except (IndexError, TypeError):
        return None
    return _mapping_string_attr(getattr(author, "data", None), "id") or _string_attr(
        author,
        "id",
    )


async def _satori_fetch_author_id(
    bot: object,
    event: object,
    message_id: str | None,
) -> str | None:
    channel_id = _satori_channel_id(event)
    if message_id is None or channel_id is None:
        return None
    call_api = getattr(bot, "call_api", None)
    if not callable(call_api):
        return None
    try:
        message = await cast("Callable[..., Awaitable[object]]", call_api)(
            "message_get",
            channel_id=channel_id,
            message_id=message_id,
        )
    except Exception as exc:  # noqa: BLE001
        logger.debug("Self-revoke Satori message_get failed: {}", exc)
        return None
    return _nested_string_attr(message, "user", "id")


def _message_id_value(message_id: str) -> int | str:
    return id_value(message_id)


async def _call_onebot_api(
    bot: "Bot",
    api: str,
    **data: object,
) -> RevokeActionResult:
    return await call_platform_api(
        bot,
        api,
        data=data,
        result_type=RevokeActionResult,
        log_label="Self-revoke OneBot",
    )


async def _call_adapter_api(
    bot: "Bot",
    adapter: str,
    api: str,
    **data: object,
) -> RevokeActionResult:
    return await call_platform_api(
        bot,
        api,
        data=data,
        result_type=RevokeActionResult,
        log_label=f"Self-revoke {adapter}",
    )
