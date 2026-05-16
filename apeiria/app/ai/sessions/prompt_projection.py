"""Projection helpers for packet-derived prompt preview channels."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.prompting import (
    project_reply_prompt_regions,
    prompt_region_diagnostics,
)
from apeiria.ai.prompting.reply import (
    REPLY_SECTION_CONTEXT_PRIORITY,
    REPLY_SECTION_CONVERSATION,
    REPLY_SECTION_EVIDENCE_CONTEXT,
    REPLY_SECTION_EXPRESSION_CONTEXT,
    REPLY_SECTION_INSTRUCTION,
    REPLY_SECTION_PERSONA,
    REPLY_SECTION_RESPONSE_RULES,
    REPLY_SECTION_STYLE,
    REPLY_SECTION_SYSTEM_INSTRUCTIONS,
    REPLY_SECTION_TOOL_POLICY,
)

from .models import (
    AISessionPromptChannels,
    AISessionPromptDiagnostics,
    AISessionPromptSection,
)

if TYPE_CHECKING:
    from apeiria.ai.prompting import PromptPacket


def project_prompt_packet_to_channels(
    packet: "PromptPacket",
    *,
    mode: str,
    profile_card_source_refs: tuple[str, ...] = (),
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
    evidence_lines = _section_lines(packet, REPLY_SECTION_EVIDENCE_CONTEXT)
    return AISessionPromptChannels(
        mode=mode,
        system_instructions=_section_lines(packet, REPLY_SECTION_SYSTEM_INSTRUCTIONS),
        persona=_section_text(packet, REPLY_SECTION_PERSONA) or "",
        style=_section_text(packet, REPLY_SECTION_STYLE),
        tool_policy=_section_text(packet, REPLY_SECTION_TOOL_POLICY),
        profile_card_source_refs=profile_card_source_refs,
        expression_context=_section_lines(packet, REPLY_SECTION_EXPRESSION_CONTEXT),
        evidence_context=evidence_lines,
        context_priority=_section_lines(packet, REPLY_SECTION_CONTEXT_PRIORITY),
        conversation_messages=tuple(
            line for line in _section_lines(packet, REPLY_SECTION_CONVERSATION)
        ),
        response_rules=_section_lines(packet, REPLY_SECTION_RESPONSE_RULES),
        instruction=_section_text(packet, REPLY_SECTION_INSTRUCTION) or "",
        sections=sections,
    )


def project_prompt_packet_to_preview(
    packet: "PromptPacket",
    *,
    mode: str,
    profile_card_source_refs: tuple[str, ...] = (),
) -> tuple[AISessionPromptChannels, AISessionPromptDiagnostics]:
    """Project a packet into preview channels plus bounded region diagnostics."""

    return (
        project_prompt_packet_to_channels(
            packet,
            mode=mode,
            profile_card_source_refs=profile_card_source_refs,
        ),
        project_prompt_packet_to_diagnostics(packet),
    )


def project_prompt_packet_to_diagnostics(
    packet: "PromptPacket",
) -> AISessionPromptDiagnostics:
    """Project reply packet regions into session-read diagnostics."""

    diagnostics = prompt_region_diagnostics(project_reply_prompt_regions(packet))
    return AISessionPromptDiagnostics(
        prompt_purpose=str(diagnostics["prompt_purpose"]),
        section_names=_string_tuple(diagnostics["section_names"]),
        stable_section_names=_string_tuple(diagnostics["stable_section_names"]),
        dynamic_section_names=_string_tuple(diagnostics["dynamic_section_names"]),
        stable_section_count=_int_value(diagnostics["stable_section_count"]),
        dynamic_section_count=_int_value(diagnostics["dynamic_section_count"]),
        total_section_count=_int_value(diagnostics["total_section_count"]),
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


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, (tuple, list)):
        return ()
    return tuple(str(item) for item in value)


def _int_value(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    return 0


__all__ = [
    "project_prompt_packet_to_channels",
    "project_prompt_packet_to_diagnostics",
    "project_prompt_packet_to_preview",
]
