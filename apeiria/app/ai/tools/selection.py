"""Prompt helpers for model-driven tool planning."""

from __future__ import annotations


def build_tool_planning_prompt(
    *,
    message_text: str,
    recalled_memory_ids: tuple[str, ...],
    recalled_memory_contents: tuple[str, ...],
    relationship_context: str | None,
) -> str:
    """Build a compact semantic prompt for tool planning.

    This prompt is consumed by a model with function-calling enabled. Tool
    choice should come from semantic judgment rather than lexical keyword
    matching.
    """

    memory_block = (
        "\n".join(
            f"- {memory_id}: {content}"
            for memory_id, content in zip(
                recalled_memory_ids[:3],
                recalled_memory_contents[:3],
                strict=False,
            )
        )
        if recalled_memory_ids and recalled_memory_contents
        else "<none>"
    )
    relationship_block = relationship_context or "<none>"
    return "\n".join(
        (
            "Decide whether any available tools should be called for the user message.",
            "Only call a tool when it is genuinely necessary.",
            "If no tool is needed, return plain text and no tool calls.",
            (
                "If you need to revise a recalled memory, use memory.update with a "
                "memory_id from the recalled memory list below."
            ),
            f"User message: {message_text}",
            f"Recalled memory excerpts: {memory_block}",
            f"Relationship context: {relationship_block}",
        )
    )
