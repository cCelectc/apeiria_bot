"""Runtime reply delivery steps."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest


@dataclass(frozen=True)
class DeliveryOutcome:
    """Outcome of a proactive (future_task) message delivery."""

    delivered: bool
    error: str | None = None


async def deliver_generated_reply(
    request: "AIRuntimeReplyRequest",
    reply_text: str,
) -> DeliveryOutcome | None:
    """Deliver a proactive reply for future_task mode via NoneBot native API."""
    if request.runtime_mode != "future_task" or not reply_text.strip():
        return None

    import nonebot

    identity = request.identity
    bot = nonebot.get_bots().get(identity.bot_id)
    if bot is None:
        return DeliveryOutcome(delivered=False, error="bot_not_connected")

    try:
        if identity.scene_type == "group":
            await bot.call_api(
                "send_group_msg",
                group_id=int(identity.scene_id),
                message=reply_text,
            )
        else:
            await bot.call_api(
                "send_private_msg",
                user_id=int(identity.scene_id),
                message=reply_text,
            )
    except Exception as exc:  # noqa: BLE001
        return DeliveryOutcome(delivered=False, error=str(exc))
    return DeliveryOutcome(delivered=True)
