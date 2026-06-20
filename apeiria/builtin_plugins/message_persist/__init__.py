from __future__ import annotations

import json
from typing import Any

from nonebot import on_message
from nonebot.adapters import Bot, Event
from nonebot.log import logger
from nonebot.message import event_preprocessor
from nonebot.plugin import PluginMetadata

__plugin_meta__ = PluginMetadata(
    name="Message Persist",
    description="Persists all chat messages to database",
    usage="Automatic",
)

import apeiria.builtin_plugins.message_persist.adapters  # noqa: F401

_SESSION_PARTS = 3

_SEND_APIS = frozenset(
    {
        "send_msg",
        "send_group_msg",
        "send_private_msg",
        "send_message",
    }
)

_msg_handler = on_message(priority=1, block=False)


@_msg_handler.handle()
async def handle_incoming(bot: Bot, event: Event) -> None:
    from apeiria.bot.platform import build_session_id, resolve_session
    from apeiria.builtin_plugins.message_persist.registry import extract_message
    from apeiria.conversation.service import append_message, ensure_session

    try:
        extracted = extract_message(bot, event)
        if not extracted or extracted.is_bot_message:
            return

        platform, scene_type, scene_id = resolve_session(bot, event)
        session_id = build_session_id(bot, event)

        await ensure_session(session_id, platform, scene_type, scene_id)
        await append_message(
            session_id,
            "user",
            extracted.content,
            user_id=extracted.user_id,
            message_id=extracted.message_id,
            msg_type="message",
            meta_json=json.dumps(extracted.meta, ensure_ascii=False)
            if extracted.meta
            else None,
        )
    except (RuntimeError, OSError, ValueError):
        logger.warning("Message persist failed", exc_info=True)


@event_preprocessor
async def handle_sent_event(bot: Bot, event: Event) -> None:
    if not hasattr(event, "message"):
        return

    from apeiria.bot.platform import build_session_id, resolve_session
    from apeiria.builtin_plugins.message_persist.registry import extract_message
    from apeiria.conversation.service import append_message, ensure_session

    try:
        extracted = extract_message(bot, event)
        if not extracted or not extracted.is_bot_message:
            return

        platform, scene_type, scene_id = resolve_session(bot, event)
        session_id = build_session_id(bot, event)

        await ensure_session(session_id, platform, scene_type, scene_id)
        await append_message(
            session_id,
            "assistant",
            extracted.content,
            user_id=extracted.user_id,
            message_id=extracted.message_id,
            msg_type="message_sent",
            meta_json=json.dumps(extracted.meta, ensure_ascii=False)
            if extracted.meta
            else None,
        )
    except (RuntimeError, OSError, ValueError):
        logger.debug("Sent event persist skipped", exc_info=True)


@Bot.on_called_api
async def handle_api_call(
    bot: Bot,
    exception: BaseException | None,
    api: str,
    data: dict[str, Any],
    result: Any,
) -> None:
    if exception is not None:
        return
    if api not in _SEND_APIS:
        return

    from apeiria.conversation.context import is_recording_suppressed

    if is_recording_suppressed():
        return

    try:
        from apeiria.conversation.service import append_message, ensure_session

        session_id = _resolve_session_from_api(bot, data)
        if not session_id:
            return

        content = _extract_content_from_api(data)
        if not content:
            return

        message_id = None
        if isinstance(result, dict):
            message_id = str(result.get("message_id", "")) or None

        parts = session_id.split(":", 2)
        if len(parts) == _SESSION_PARTS:
            await ensure_session(session_id, parts[0], parts[1], parts[2])

        await append_message(
            session_id,
            "assistant",
            content,
            message_id=message_id,
            msg_type="message_sent",
        )
    except (RuntimeError, OSError, ValueError):
        logger.debug("API call persist failed", exc_info=True)


def _resolve_session_from_api(bot: Bot, data: dict[str, Any]) -> str | None:
    from apeiria.bot.platform import adapter_name

    platform_raw = adapter_name(bot)
    platform = "onebot" if "onebot" in platform_raw else platform_raw

    group_id = data.get("group_id")
    user_id = data.get("user_id")
    msg_type = data.get("message_type") or data.get("detail_type", "")

    if msg_type in ("group", "private"):
        target = group_id if msg_type == "group" else user_id
        if target:
            return f"{platform}:{msg_type}:{target}"

    if group_id:
        return f"{platform}:group:{group_id}"
    if user_id:
        return f"{platform}:private:{user_id}"

    return None


def _extract_content_from_api(data: dict[str, Any]) -> str:
    message = data.get("message", "")
    if isinstance(message, str):
        return message.strip()
    if isinstance(message, list):
        parts = [
            seg.get("data", {}).get("text", "")
            for seg in message
            if isinstance(seg, dict) and seg.get("type") == "text"
        ]
        return "".join(parts).strip()
    return str(message).strip() if message else ""
