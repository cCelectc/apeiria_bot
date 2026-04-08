"""Pure helpers for selecting low-risk tools from user messages."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterable

    from apeiria.app.ai.tools.models import AIToolSpec

_MEMORY_QUERY_TOKENS = (
    "记得",
    "还记得",
    "喜欢什么",
    "偏好",
    "爱好",
    "之前说过",
)
_RELATIONSHIP_INSPECT_TOKENS = (
    "好感",
    "关系",
    "怎么看我",
    "讨厌我",
    "喜欢我",
    "态度",
)


def select_tools_for_message(
    *,
    message_text: str,
    available_tools: Iterable[AIToolSpec],
) -> list[AIToolSpec]:
    """Select a small set of relevant low-risk tools for one message."""

    normalized = message_text.strip().lower()
    if not normalized:
        return []

    tool_map = {tool.name: tool for tool in available_tools}
    selected: list[AIToolSpec] = []

    if _contains_any(normalized, _MEMORY_QUERY_TOKENS):
        tool = tool_map.get("memory.query")
        if tool is not None:
            selected.append(tool)

    if _contains_any(normalized, _RELATIONSHIP_INSPECT_TOKENS):
        tool = tool_map.get("relationship.inspect")
        if tool is not None:
            selected.append(tool)

    return selected


def _contains_any(text: str, patterns: tuple[str, ...]) -> bool:
    return any(pattern in text for pattern in patterns)
