"""Pure helpers for compact conversation summaries + LLM compression."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

if TYPE_CHECKING:
    from apeiria.app.ai.conversation.models import ChatContextMessageView

_MAX_SUMMARY_TURNS = 4
_MAX_SUMMARY_LENGTH = 280

_SPEAKER_MAP = {
    "user": "User",
    "assistant": "Assistant",
    "system": "System",
    "tool": "Tool",
}

_MAX_OVERFLOW_CHARS_FOR_PROMPT = 4000


def build_short_conversation_summary(
    messages: list["ChatContextMessageView"],
) -> str | None:
    """Build a compact summary from the latest non-empty messages."""

    summary_lines = [
        _format_summary_message(msg)
        for msg in messages[-_MAX_SUMMARY_TURNS:]
        if msg.text_content.strip()
    ]
    if not summary_lines:
        return None

    summary = " | ".join(summary_lines)
    if len(summary) <= _MAX_SUMMARY_LENGTH:
        return summary
    return f"{summary[: _MAX_SUMMARY_LENGTH - 1].rstrip()}…"


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

    from nonebot_plugin_orm import get_session

    from apeiria.app.ai.model.models import AIModelRouteQuery
    from apeiria.app.ai.model.service import ai_model_facade

    prompt = _build_compression_prompt(
        overflow_messages,
        existing_summary=existing_summary,
        scene_type=scene_type,
    )

    async with get_session() as session:
        selected = await ai_model_facade.select_model(
            session,
            query=AIModelRouteQuery(task_class="planner_light"),
        )

    if selected is None:
        logger.debug("context compression skipped: no model for planner_light")
        return _fallback_summary(overflow_messages, existing_summary)

    try:
        response = await ai_model_facade.generate_text(
            selected,
            prompt=prompt,
        )
    except Exception as exc:  # noqa: BLE001
        logger.opt(exception=exc).warning("context compression LLM call failed")
        return _fallback_summary(overflow_messages, existing_summary)

    if response is None or not response.content.strip():
        return _fallback_summary(overflow_messages, existing_summary)

    return response.content.strip()


def _build_compression_prompt(
    overflow_messages: list["ChatContextMessageView"],
    *,
    existing_summary: str | None,
    scene_type: str,
) -> str:
    lines: list[str] = [
        "将以下对话历史压缩为简洁摘要。",
        "保留：主要话题、关键事实和结论、参与者的立场或态度、未解决的问题。",
        "丢弃：寒暄、重复内容、无实质信息的消息。",
        "输出纯文本摘要，200字以内。不要输出任何解释或标注。",
    ]

    if scene_type == "group":
        lines.append("这是群聊对话，注意区分不同参与者。")

    if existing_summary:
        lines.append(f"\n之前的摘要：\n{existing_summary}")
        lines.append("\n以下是新增对话，请整合到摘要中：")
    else:
        lines.append("\n对话历史：")

    formatted = _format_overflow_for_prompt(overflow_messages)
    lines.append(formatted)

    return "\n".join(lines)


def _format_overflow_for_prompt(
    messages: list["ChatContextMessageView"],
) -> str:
    parts: list[str] = []
    total_chars = 0
    for msg in messages:
        text = msg.text_content.strip()
        if not text:
            continue
        speaker = _format_summary_message(msg)
        if total_chars + len(speaker) > _MAX_OVERFLOW_CHARS_FOR_PROMPT:
            parts.append("... (更早的消息已省略)")
            break
        parts.append(speaker)
        total_chars += len(speaker)
    return "\n".join(parts)


def _fallback_summary(
    overflow_messages: list["ChatContextMessageView"],
    existing_summary: str | None,
) -> str | None:
    rule_summary = build_short_conversation_summary(overflow_messages)
    if existing_summary and rule_summary:
        combined = f"{existing_summary} | {rule_summary}"
        if len(combined) > _MAX_SUMMARY_LENGTH:
            return f"{combined[: _MAX_SUMMARY_LENGTH - 1].rstrip()}…"
        return combined
    return rule_summary or existing_summary


def _format_summary_message(msg: "ChatContextMessageView") -> str:
    speaker = _SPEAKER_MAP.get(msg.author_role, "Message")
    if msg.author_name:
        speaker = msg.author_name
    return f"{speaker}: {msg.text_content.strip()}"
