"""App-owned internal executable AI tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from . import future_tasks, knowledge, memory, relationship

if TYPE_CHECKING:
    from collections.abc import Callable

    from apeiria.ai.contributions import AIContributionRegistry
    from apeiria.ai.tools.models import AIToolDefinition

_INTERNAL_TOOL_HANDLERS: tuple["Callable[..., Any]", ...] = (
    memory.search_memory,
    memory.write_memory,
    knowledge.search_knowledge,
    future_tasks.create_future_task,
    future_tasks.list_future_tasks,
    future_tasks.cancel_future_task,
    relationship.inspect_relationship,
)


def internal_tools() -> tuple["AIToolDefinition", ...]:
    """Return Apeiria-owned internal tool declarations."""

    return tuple(
        cast("AIToolDefinition", cast("Any", handler).__ai_tool_definition__)
        for handler in _INTERNAL_TOOL_HANDLERS
    )


def register_internal_tools(registry: "AIContributionRegistry") -> int:
    """Register Apeiria-owned internal tool declarations."""

    count = 0
    for tool in internal_tools():
        registry.register_tool(tool=tool)
        count += 1
    return count


__all__ = ["internal_tools", "register_internal_tools"]
