"""Tool intent planning prompt recipe."""

from __future__ import annotations

from dataclasses import dataclass

from .models import PromptPacket, PromptSection


@dataclass(frozen=True)
class ToolIntentPlanningPromptInput:
    """Prompt-facing materials for one tool intent planning call."""

    message_text: str
    recalled_memory_ids: tuple[str, ...]
    recalled_memory_contents: tuple[str, ...]
    relationship_context: str | None


def build_tool_intent_planning_packet(
    inputs: ToolIntentPlanningPromptInput,
) -> PromptPacket:
    """Build a packet for model-driven tool intent planning."""

    sections: list[PromptSection] = [
        PromptSection(
            role="system",
            name="Instruction",
            content="\n".join(
                (
                    "判断是否需要针对用户消息调用任何可用工具。",
                    "只有在确实必要时才调用工具。",
                    "如果不需要工具，就直接返回纯文本，不要发起工具调用。",
                )
            ),
        ),
        PromptSection(
            role="system",
            name="MemoryUpdatePolicy",
            content=(
                "如果需要修订持久记忆，在更正已有条目时，"
                "使用下面召回记忆列表里的 memory_id 调用 memory.write。"
            ),
        ),
        PromptSection(
            role="user",
            name="UserMessage",
            content=inputs.message_text,
        ),
    ]
    memory_block = _build_memory_block(
        ids=inputs.recalled_memory_ids,
        contents=inputs.recalled_memory_contents,
    )
    if memory_block:
        sections.append(
            PromptSection(
                role="user",
                name="RecalledMemories",
                content=memory_block,
            )
        )
    if inputs.relationship_context:
        sections.append(
            PromptSection(
                role="user",
                name="RelationshipContext",
                content=inputs.relationship_context,
            )
        )
    return PromptPacket(purpose="tool_intent_planning", sections=tuple(sections))


def _build_memory_block(
    *,
    ids: tuple[str, ...],
    contents: tuple[str, ...],
) -> str | None:
    lines = [
        f"- {memory_id}: {content}"
        for memory_id, content in zip(ids[:3], contents[:3], strict=False)
        if memory_id and content
    ]
    return "\n".join(lines) if lines else None
