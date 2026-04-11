"""Application-level outbound message delivery service."""

from __future__ import annotations

from typing import TYPE_CHECKING

import nonebot

from apeiria.app.message_delivery.models import (
    MessageDeliveryRequest,
    MessageDeliveryResult,
)

if TYPE_CHECKING:
    from nonebot.adapters import Bot


class MessageDeliveryService:
    """Send outbound messages through adapter-specific bot APIs."""

    async def send(self, request: MessageDeliveryRequest) -> MessageDeliveryResult:
        bot = self._get_bot(request.target.bot_id)
        if bot is None:
            return MessageDeliveryResult(
                delivered=False,
                channel="missing_bot",
                error=f"bot {request.target.bot_id} is not connected",
            )

        if self._is_onebot_v11_target(bot, request):
            return await self._send_onebot_v11(bot, request)

        return MessageDeliveryResult(
            delivered=False,
            channel="unsupported",
            error=(
                "proactive delivery is not implemented for platform "
                f"{request.target.platform}"
            ),
        )

    @staticmethod
    def _get_bot(bot_id: str) -> "Bot | None":
        try:
            return nonebot.get_bot(bot_id)
        except Exception:  # noqa: BLE001
            return None

    @staticmethod
    def _is_onebot_v11_target(
        bot: "Bot",
        request: MessageDeliveryRequest,
    ) -> bool:
        if not _is_onebot_api_available(bot):
            return False
        platform = request.target.platform.lower()
        return "onebot" in platform and "12" not in platform

    async def _send_onebot_v11(
        self,
        bot: "Bot",
        request: MessageDeliveryRequest,
    ) -> MessageDeliveryResult:
        if request.target.scope_type == "private":
            user_id = _to_onebot_numeric_id(
                request.target.user_id or request.target.scope_id
            )
            if user_id is None:
                return MessageDeliveryResult(
                    delivered=False,
                    channel="onebot.v11",
                    error="invalid private target user_id for onebot v11",
                )
            result = await bot.call_api(
                "send_private_msg",
                user_id=user_id,
                message=request.content_text,
            )
            return MessageDeliveryResult(
                delivered=True,
                channel="onebot.v11",
                remote_message_id=_extract_message_id(result),
            )

        if request.target.scope_type == "group":
            group_id = _to_onebot_numeric_id(request.target.scope_id)
            if group_id is None:
                return MessageDeliveryResult(
                    delivered=False,
                    channel="onebot.v11",
                    error="invalid group target group_id for onebot v11",
                )
            result = await bot.call_api(
                "send_group_msg",
                group_id=group_id,
                message=request.content_text,
            )
            return MessageDeliveryResult(
                delivered=True,
                channel="onebot.v11",
                remote_message_id=_extract_message_id(result),
            )

        return MessageDeliveryResult(
            delivered=False,
            channel="onebot.v11",
            error=f"scope type {request.target.scope_type} is not supported",
        )


def _extract_message_id(result: object) -> str | None:
    if not isinstance(result, dict):
        return None
    message_id = result.get("message_id")
    return str(message_id) if message_id is not None else None


def _is_onebot_api_available(bot: "Bot") -> bool:
    adapter = getattr(bot, "adapter", None)
    get_name = getattr(adapter, "get_name", None)
    if not callable(get_name):
        return False
    adapter_name = str(get_name()).lower()
    return "onebot" in adapter_name


def _to_onebot_numeric_id(value: str) -> int | None:
    normalized = value.strip()
    if not normalized.isdigit():
        return None
    return int(normalized)


message_delivery_service = MessageDeliveryService()
