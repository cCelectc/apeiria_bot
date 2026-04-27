"""Skill selection prompt recipe."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol

from .models import PromptPacket, PromptSection

if TYPE_CHECKING:
    from collections.abc import Sequence


class SkillCatalogEntryLike(Protocol):
    """Prompt-facing shape for one skill catalog entry."""

    @property
    def skill_name(self) -> str: ...

    @property
    def description(self) -> str: ...

    @property
    def entry_mode(self) -> str: ...


@dataclass(frozen=True)
class SkillSelectionPromptInput:
    """Prompt-facing materials for one skill selection call."""

    message_text: str
    conversation_summary: str | None
    entries: "Sequence[SkillCatalogEntryLike]"


def build_skill_selection_packet(
    inputs: SkillSelectionPromptInput,
) -> PromptPacket:
    """Build a packet for selecting relevant file-based skills."""

    sections: list[PromptSection] = [
        PromptSection(
            role="system",
            name="Instruction",
            content=(
                "You are a skill selector. Given the user message and "
                "available skills, decide which skills (if any) should be "
                "activated to help generate a good reply."
            ),
        ),
        PromptSection(
            role="user",
            name="UserMessage",
            content=inputs.message_text,
        ),
    ]
    if inputs.conversation_summary:
        sections.append(
            PromptSection(
                role="user",
                name="ConversationSummary",
                content=inputs.conversation_summary,
            )
        )
    sections.extend(
        (
            PromptSection(
                role="user",
                name="SkillCatalog",
                content=_build_catalog_prompt(inputs.entries),
            ),
            PromptSection(
                role="user",
                name="OutputContract",
                content="\n".join(
                    (
                        "Rules:",
                        "- Only select skills that are clearly relevant.",
                        "- Most messages need zero skills - return [] when unsure.",
                        (
                            "- Return a JSON array of skill names, e.g. "
                            '["social-observer"] or [].'
                        ),
                        "- Return ONLY the JSON array, nothing else.",
                    )
                ),
            ),
        )
    )
    return PromptPacket(purpose="skill_selection", sections=tuple(sections))


def _build_catalog_prompt(
    entries: "Sequence[SkillCatalogEntryLike]",
) -> str:
    lines: list[str] = ["Available skills:"]
    for entry in entries:
        mode_tag = f"[{entry.entry_mode}]"
        lines.append(f"- **{entry.skill_name}** {mode_tag}: {entry.description}")
    return "\n".join(lines)
