"""Pure reply engagement policy helpers."""

from __future__ import annotations

from .models import AIDecisionContext, AIDecisionResult


def evaluate_engagement(context: AIDecisionContext) -> AIDecisionResult:
    """Evaluate whether the runtime should produce a reply."""

    if context.user_id == context.bot_self_id:
        return AIDecisionResult(
            should_reply=False,
            reason="ignore_self_message",
        )
    if not context.message_text.strip():
        return AIDecisionResult(
            should_reply=False,
            reason="empty_plaintext",
        )
    if context.is_tome:
        return AIDecisionResult(
            should_reply=True,
            reason="mentioned_bot",
        )
    if context.is_private:
        return AIDecisionResult(
            should_reply=True,
            reason="private_default_reply",
        )
    return AIDecisionResult(
        should_reply=False,
        reason="group_no_engagement_signal",
    )
