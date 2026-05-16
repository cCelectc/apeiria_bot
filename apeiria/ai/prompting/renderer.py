"""Render prompt packets into model-runtime inputs."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.ai.model.runtime.adapter import AIModelMessage
from apeiria.ai.prompting.reply import REPLY_SECTION_TAG_NAMES

if TYPE_CHECKING:
    from .models import PromptPacket, PromptSection


def render_messages(packet: "PromptPacket") -> tuple[AIModelMessage, ...]:
    """Render packet sections into model messages in packet order."""

    messages: list[AIModelMessage] = []
    for section in _non_empty_sections(packet):
        content = _render_section(packet, section)
        if messages and messages[-1].role == section.role:
            previous = messages[-1]
            messages[-1] = AIModelMessage(
                role=previous.role,
                content=f"{previous.content}\n\n{content}",
            )
            continue
        messages.append(AIModelMessage(role=section.role, content=content))
    return tuple(messages)


def render_flat(packet: "PromptPacket") -> str:
    """Render packet sections into an explicit plain prompt string."""

    return "\n\n".join(
        _render_section(packet, section) for section in _non_empty_sections(packet)
    )


def _non_empty_sections(packet: "PromptPacket") -> tuple["PromptSection", ...]:
    return tuple(section for section in packet.sections if section.content.strip())


def _render_section(packet: "PromptPacket", section: "PromptSection") -> str:
    if (
        packet.purpose in {"reply_planner", "reply_final"}
        and section.name in REPLY_SECTION_TAG_NAMES
    ):
        return f"<{section.name}>\n{section.content.strip()}\n</{section.name}>"
    return f"[{section.name}]\n{section.content.strip()}"
