"""Plugin-facing AI registration helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, cast

from apeiria.ai.contributions import ai_contributions
from apeiria.ai.tools.decorators import ai_tool as define_ai_tool
from apeiria.ai.tools.models import AIToolLevel

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from apeiria.ai.tools.models import AIToolDefinition, AIToolResult

    AIToolHandler = Callable[..., Awaitable[AIToolResult]]


def ai_tool(
    *,
    name: str,
    description: str,
    required_level: AIToolLevel | str = AIToolLevel.READ,
) -> "Callable[[AIToolHandler], AIToolHandler]":
    """Declare a plugin-owned local executable AI tool."""

    def decorator(func: "AIToolHandler") -> "AIToolHandler":
        decorated = define_ai_tool(
            name=name,
            description=description,
            required_level=required_level,
            origin="plugin",
            manageable=True,
        )(func)
        func_with_metadata = cast("Any", func)
        tool = cast("AIToolDefinition", func_with_metadata.__ai_tool_definition__)
        ai_contributions.register_tool(tool=tool)
        return cast("AIToolHandler", decorated)

    return decorator


__all__ = ["ai_tool"]
