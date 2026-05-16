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
                "你是技能选择器。根据用户消息和可用技能，判断是否需要激活某些技能来帮助生成更好的回复。"
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
                        "规则：",
                        "- 只选择明显相关的技能。",
                        (
                            "- 大多数消息不需要任何技能；拿不准时返回空的 "
                            "selected_names 列表。"
                        ),
                        (
                            "- 返回一个包含 selected_names 的 JSON 对象，例如 "
                            '{"selected_names":["social-observer"]} 或 '
                            '{"selected_names":[]}.'
                        ),
                        "- 只返回 JSON 对象，不要输出其他内容。",
                    )
                ),
            ),
        )
    )
    return PromptPacket(purpose="skill_selection", sections=tuple(sections))


def _build_catalog_prompt(
    entries: "Sequence[SkillCatalogEntryLike]",
) -> str:
    lines: list[str] = ["可用技能："]
    for entry in entries:
        mode_tag = f"[{entry.entry_mode}]"
        lines.append(f"- **{entry.skill_name}** {mode_tag}: {entry.description}")
    return "\n".join(lines)
