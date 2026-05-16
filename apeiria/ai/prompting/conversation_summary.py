"""Conversation summary compression prompt recipe."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .models import PromptPacket, PromptSection
from .template_loader import load_prompt_template

if TYPE_CHECKING:
    from apeiria.conversation.models import ChatContextMessageView

_SPEAKER_MAP = {
    "user": "用户",
    "assistant": "助手",
    "system": "系统",
    "tool": "工具",
}


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
            content=load_prompt_template("conversation_summary/instruction.md"),
        )
    ]
    if inputs.scene_type == "group":
        sections.append(
            PromptSection(
                role="system",
                name="GroupGuidance",
                content=load_prompt_template("conversation_summary/group_guidance.md"),
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
    for msg in messages:
        text = msg.text_content.strip()
        if not text:
            continue
        parts.append(_format_summary_message(msg))
    return "\n".join(parts)


def _format_summary_message(msg: "ChatContextMessageView") -> str:
    speaker = _SPEAKER_MAP.get(msg.author_role, "Message")
    if msg.author_name:
        speaker = msg.author_name
    return f"{speaker}: {msg.text_content.strip()}"
