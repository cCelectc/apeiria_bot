"""Projection helpers for packet-derived prompt preview channels."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.prompting.reply import (
    REPLY_SECTION_CONTEXT_PRIORITY,
    REPLY_SECTION_CONVERSATION,
    REPLY_SECTION_CONVERSATION_SUMMARY,
    REPLY_SECTION_FUTURE_TASK,
    REPLY_SECTION_INSTRUCTION,
    REPLY_SECTION_KNOWLEDGE_MEMORIES,
    REPLY_SECTION_LONG_TERM_MEMORIES,
    REPLY_SECTION_OPERATOR_MEMORIES,
    REPLY_SECTION_PERSON_PROFILE,
    REPLY_SECTION_PERSONA,
    REPLY_SECTION_RELATIONSHIP,
    REPLY_SECTION_RESPONSE_RULES,
    REPLY_SECTION_SOCIAL_POLICY,
    REPLY_SECTION_STYLE,
    REPLY_SECTION_SUMMARY_MEMORIES,
    REPLY_SECTION_SYSTEM_INSTRUCTIONS,
    REPLY_SECTION_TOOL_POLICY,
    REPLY_SECTION_TOOL_RESULTS,
)

from .models import AISessionPromptChannels, AISessionPromptSection

if TYPE_CHECKING:
    from apeiria.ai.prompting import PromptPacket


def project_prompt_packet_to_channels(
    packet: "PromptPacket",
    *,
    mode: str,
) -> AISessionPromptChannels:
    """Project a reply prompt packet into session-read preview channels."""

    sections = tuple(
        AISessionPromptSection(
            role=section.role,
            name=section.name,
            content=section.content,
        )
        for section in packet.sections
    )
    return AISessionPromptChannels(
        mode=mode,
        system_instructions=_section_lines(packet, REPLY_SECTION_SYSTEM_INSTRUCTIONS),
        persona=_section_text(packet, REPLY_SECTION_PERSONA) or "",
        style=_section_text(packet, REPLY_SECTION_STYLE),
        relationship=_section_text(packet, REPLY_SECTION_RELATIONSHIP),
        social_policy=_section_text(packet, REPLY_SECTION_SOCIAL_POLICY),
        tool_policy=_section_text(packet, REPLY_SECTION_TOOL_POLICY),
        future_task=_section_text(packet, REPLY_SECTION_FUTURE_TASK),
        person_profile=_section_lines(packet, REPLY_SECTION_PERSON_PROFILE),
        tool_results=_section_lines(packet, REPLY_SECTION_TOOL_RESULTS),
        operator_memories=_section_lines(packet, REPLY_SECTION_OPERATOR_MEMORIES),
        summary_memories=_section_lines(packet, REPLY_SECTION_SUMMARY_MEMORIES),
        long_term_memories=_section_lines(packet, REPLY_SECTION_LONG_TERM_MEMORIES),
        knowledge_memories=_section_lines(packet, REPLY_SECTION_KNOWLEDGE_MEMORIES),
        conversation_summary=_section_text(
            packet,
            REPLY_SECTION_CONVERSATION_SUMMARY,
        ),
        context_priority=_section_lines(packet, REPLY_SECTION_CONTEXT_PRIORITY),
        conversation_messages=tuple(
            section.content
            for section in packet.sections
            if section.name == REPLY_SECTION_CONVERSATION and section.content.strip()
        ),
        response_rules=_section_lines(packet, REPLY_SECTION_RESPONSE_RULES),
        instruction=_section_text(packet, REPLY_SECTION_INSTRUCTION) or "",
        sections=sections,
    )


def _section_text(packet: PromptPacket, name: str) -> str | None:
    for section in packet.sections:
        if section.name == name and section.content.strip():
            return section.content
    return None


def _section_lines(packet: PromptPacket, name: str) -> tuple[str, ...]:
    text = _section_text(packet, name)
    if text is None:
        return ()
    return tuple(line for line in text.splitlines() if line.strip())
