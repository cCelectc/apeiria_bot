"""Conversation summary compression prompt recipe."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import PromptPacket, PromptSection

if TYPE_CHECKING:
    from apeiria.conversation.models import ChatContextMessageView

_SPEAKER_MAP = {
    "user": "User",
    "assistant": "Assistant",
    "system": "System",
    "tool": "Tool",
}
_MAX_OVERFLOW_CHARS_FOR_PROMPT = 4000


@dataclass(frozen=True)
class ConversationSummaryPromptInput:
    """Prompt-facing materials for one conversation summary compression call."""

    overflow_messages: tuple["ChatContextMessageView", ...]
    existing_summary: str | None
    scene_type: str


def build_conversation_summary_packet(
    inputs: ConversationSummaryPromptInput,
) -> PromptPacket:
    """Build a packet for compressing overflow conversation history."""

    sections = [
        PromptSection(
            role="system",
            name="Instruction",
            content="\n".join(
                (
                    "将以下对话历史压缩为简洁摘要。",
                    "保留：主要话题、关键事实和结论、参与者的立场或态度、未解决的问题。",
                    "丢弃：寒暄、重复内容、无实质信息的消息。",
                    "输出纯文本摘要，200字以内。不要输出任何解释或标注。",
                )
            ),
        )
    ]
    if inputs.scene_type == "group":
        sections.append(
            PromptSection(
                role="system",
                name="GroupGuidance",
                content="这是群聊对话，注意区分不同参与者。",
            )
        )
    if inputs.existing_summary:
        sections.append(
            PromptSection(
                role="user",
                name="ExistingSummary",
                content=inputs.existing_summary,
            )
        )
        conversation_name = "NewConversationHistory"
    else:
        conversation_name = "ConversationHistory"
    sections.append(
        PromptSection(
            role="user",
            name=conversation_name,
            content=_format_overflow_for_prompt(inputs.overflow_messages),
        )
    )
    return PromptPacket(purpose="conversation_summary", sections=tuple(sections))


def _format_overflow_for_prompt(
    messages: tuple["ChatContextMessageView", ...],
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


def _format_summary_message(msg: "ChatContextMessageView") -> str:
    speaker = _SPEAKER_MAP.get(msg.author_role, "Message")
    if msg.author_name:
        speaker = msg.author_name
    return f"{speaker}: {msg.text_content.strip()}"
