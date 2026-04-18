"""Delivery gateway for the Runtime Kernel control layer.

`DeliveryGateway` is the single outbound boundary for reply and proactive
send. Every runtime-originated delivery attempt goes through this gateway,
gets recorded as an `Effect`, and is attributed to the active runtime frame
when one exists.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import nonebot

from apeiria.app.runtime.effect import (
    Effect,
    current_effect_queue,
    new_effect,
)
from apeiria.app.runtime.models import DeliveryTarget, SendResult
from apeiria.app.runtime.observer import current_request_id

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event, Message, MessageSegment


class DeliveryGateway:
    """Unified reply / send boundary for runtime delivery."""

    async def reply(
        self,
        *,
        bot: "Bot",
        event: "Event",
        text: "str | Message | MessageSegment",
        origin: str = "runtime.reply",
    ) -> SendResult:
        """Reply to an incoming event through its originating bot."""

        effect = self._record_effect(
            kind="reply",
            origin=origin,
            payload={
                "platform": str(bot.type),
                "bot_id": str(bot.self_id),
                "event_type": type(event).__name__,
                "preview": _preview(text),
            },
        )
        try:
            await bot.send(event, text)
        except Exception as exc:  # noqa: BLE001
            effect.mark_failed(str(exc))
            return SendResult(
                delivered=False,
                channel=_channel_from_bot(bot),
                error=str(exc),
            )
        result = SendResult(delivered=True, channel=_channel_from_bot(bot))
        effect.mark_flushed(
            {
                "delivered": result.delivered,
                "channel": result.channel,
            }
        )
        return result

    async def send(
        self,
        *,
        target: DeliveryTarget,
        text: str,
        origin: str = "runtime.send",
    ) -> SendResult:
        """Proactively send ``text`` to a platform delivery target."""

        effect = self._record_effect(
            kind="send",
            origin=origin,
            payload={
                "platform": target.platform,
                "bot_id": target.bot_id,
                "scope_kind": target.scope_kind,
                "scope_id": target.scope_id,
                "preview": _preview(text),
            },
        )
        bot = self._get_bot(target.bot_id)
        if bot is None:
            error = f"bot {target.bot_id} is not connected"
            effect.mark_failed(error)
            return SendResult(delivered=False, channel="missing_bot", error=error)

        if _is_onebot_v11_target(bot, target):
            result = await self._send_onebot_v11(bot, target, text)
        else:
            result = SendResult(
                delivered=False,
                channel="unsupported",
                error=(
                    "proactive delivery is not implemented for platform "
                    f"{target.platform}"
                ),
            )

        if result.delivered:
            effect.mark_flushed(
                {
                    "delivered": True,
                    "channel": result.channel,
                    "remote_message_id": result.remote_message_id,
                }
            )
        else:
            effect.mark_failed(result.error or "delivery_failed")
        return result

    @staticmethod
    def _record_effect(
        *,
        kind: str,
        origin: str,
        payload: dict[str, Any],
    ) -> Effect:
        effect = new_effect(
            kind=kind,  # type: ignore[arg-type]
            origin=origin,
            request_id=current_request_id(),
            payload=payload,
        )
        queue = current_effect_queue()
        if queue is not None:
            queue.enqueue(effect)
        return effect

    @staticmethod
    def _get_bot(bot_id: str) -> "Bot | None":
        try:
            return nonebot.get_bot(bot_id)
        except Exception:  # noqa: BLE001
            return None

    async def _send_onebot_v11(
        self,
        bot: "Bot",
        target: DeliveryTarget,
        text: str,
    ) -> SendResult:
        if target.scope_kind == "private":
            user_id = _to_onebot_numeric_id(target.user_id or target.scope_id)
            if user_id is None:
                return SendResult(
                    delivered=False,
                    channel="onebot.v11",
                    error="invalid private target user_id for onebot v11",
                )
            payload = await bot.call_api(
                "send_private_msg",
                user_id=user_id,
                message=text,
            )
            return SendResult(
                delivered=True,
                channel="onebot.v11",
                remote_message_id=_extract_message_id(payload),
            )

        if target.scope_kind == "group":
            group_id = _to_onebot_numeric_id(target.scope_id)
            if group_id is None:
                return SendResult(
                    delivered=False,
                    channel="onebot.v11",
                    error="invalid group target group_id for onebot v11",
                )
            payload = await bot.call_api(
                "send_group_msg",
                group_id=group_id,
                message=text,
            )
            return SendResult(
                delivered=True,
                channel="onebot.v11",
                remote_message_id=_extract_message_id(payload),
            )

        return SendResult(
            delivered=False,
            channel="onebot.v11",
            error=f"scope kind {target.scope_kind} is not supported",
        )


_WEB_CHAT_HINTS = ("webchat", "webui", "web_chat")
_MAX_PREVIEW_CHARS = 64


def _channel_from_bot(bot: "Bot") -> Any:
    adapter_name = _adapter_name(bot).lower()
    if any(hint in adapter_name for hint in _WEB_CHAT_HINTS):
        return "web_chat"
    if "onebot" in adapter_name and "12" not in adapter_name:
        return "onebot.v11"
    return "unsupported"


def _is_onebot_v11_target(bot: "Bot", target: DeliveryTarget) -> bool:
    if not _is_onebot_api_available(bot):
        return False
    platform = target.platform.lower()
    return "onebot" in platform and "12" not in platform


def _is_onebot_api_available(bot: "Bot") -> bool:
    return "onebot" in _adapter_name(bot).lower()


def _adapter_name(bot: "Bot") -> str:
    adapter = getattr(bot, "adapter", None)
    get_name = getattr(adapter, "get_name", None)
    if not callable(get_name):
        return ""
    try:
        return str(get_name())
    except Exception:  # noqa: BLE001
        return ""


def _extract_message_id(payload: object) -> str | None:
    if not isinstance(payload, dict):
        return None
    message_id = payload.get("message_id")
    return str(message_id) if message_id is not None else None


def _to_onebot_numeric_id(value: str) -> int | None:
    normalized = value.strip()
    if not normalized.isdigit():
        return None
    return int(normalized)


def _preview(text: "str | Message | MessageSegment") -> str:
    raw = text if isinstance(text, str) else str(text)
    compact = raw.replace("\n", " ").strip()
    if len(compact) > _MAX_PREVIEW_CHARS:
        return compact[:_MAX_PREVIEW_CHARS] + "..."
    return compact


delivery_gateway = DeliveryGateway()
