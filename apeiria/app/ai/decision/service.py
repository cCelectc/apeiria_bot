"""Application service for reply engagement decisions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from .policy import evaluate_engagement
from .signals import build_decision_context

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

    from .models import AIDecisionResult


class AIDecisionService:
    """Single entrypoint for deciding whether AI should reply."""

    def decide_for_event(
        self,
        bot: "Bot",
        event: "Event",
    ) -> tuple["AIDecisionResult", str] | None:
        """Return one decision result and normalized plaintext for the event."""

        context = build_decision_context(bot, event)
        if context is None:
            return None
        return evaluate_engagement(context), context.message_text


ai_decision_service = AIDecisionService()
