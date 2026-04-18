"""Runtime feedback helpers for denied plugin execution."""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from apeiria.app.message_delivery import delivery_gateway

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

    from apeiria.app.access.models import PermissionDecision


class GuardFeedbackService:
    """Best-effort runtime feedback for denied access decisions."""

    async def handle_denied(
        self,
        bot: Bot,
        event: Event,
        decision: PermissionDecision,
    ) -> None:
        if not decision.reason:
            return
        with contextlib.suppress(Exception):
            await delivery_gateway.reply(
                bot=bot,
                event=event,
                text=decision.reason,
                origin="bot.guard_feedback",
            )


guard_feedback_service = GuardFeedbackService()
