"""Pure helpers for compact conversation summaries + LLM compression."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.prompting import (
    ConversationSummaryPromptInput,
    build_conversation_summary_packet,
    render_messages,
)
from apeiria.conversation.summary import build_short_conversation_summary

if TYPE_CHECKING:
    from apeiria.conversation.models import ChatContextMessageView


async def compress_conversation_history(
    overflow_messages: list["ChatContextMessageView"],
    *,
    existing_summary: str | None,
    scene_type: str,
) -> str | None:
    """Compress overflow messages into a structured summary via LLM.

    Falls back to :func:`build_short_conversation_summary` when the LLM
    call is unavailable or fails.
    """

    if not overflow_messages:
        return existing_summary

    from apeiria.ai.model import model_invoker
    from apeiria.app.ai.runtime.planning.model_selection import select_task_model

    messages = render_messages(
        build_conversation_summary_packet(
            ConversationSummaryPromptInput(
                overflow_messages=tuple(overflow_messages),
                existing_summary=existing_summary,
                scene_type=scene_type,
            )
        )
    )

    selected = await select_task_model(task_class="planner_light")

    if selected is None:
        logger.debug("context compression skipped: no model for planner_light")
        return _fallback_summary(overflow_messages, existing_summary)

    try:
        response = await model_invoker.generate_text(
            selected=selected,
            messages=messages,
        )
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).warning("context compression LLM call failed")
        return _fallback_summary(overflow_messages, existing_summary)

    if response is None or not response.content.strip():
        return _fallback_summary(overflow_messages, existing_summary)

    return response.content.strip()


def _fallback_summary(
    overflow_messages: list["ChatContextMessageView"],
    existing_summary: str | None,
) -> str | None:
    del existing_summary
    return build_short_conversation_summary(overflow_messages)
