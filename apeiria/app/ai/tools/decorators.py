"""Declarative @ai_tool decorator for tool registration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.app.ai.tools.schema import build_parameters_from_signature

if TYPE_CHECKING:
    from collections.abc import Callable

    from apeiria.app.ai.tools.models import AIToolRiskLevel

_PENDING_TOOLS: list[Any] = []


def ai_tool(  # noqa: PLR0913
    *,
    name: str,
    description: str,
    read_only: bool,
    concurrency_safe: bool,
    risk_level: AIToolRiskLevel = "low",
    is_capability_bridge: bool = False,
    tags: tuple[str, ...] = (),
) -> Callable[..., Any]:
    """Decorator that registers an async function as an AI tool.

    The function signature is inspected to auto-generate JSON Schema
    parameters.  A keyword-only ``context: AIToolExecutionContext``
    parameter is injected at call time and **not** included in the
    schema.

    Usage::

        @ai_tool(
            name="memory.query",
            description="inspect recalled long-term memory",
            read_only=True,
            concurrency_safe=True,
        )
        async def handle_memory_query(
            query_text: str,
            *,
            context: AIToolExecutionContext,
        ) -> AIToolResult:
            ...
    """

    def decorator(func: Any) -> Any:
        from apeiria.app.ai.tools.models import AIToolSpec

        parameters = build_parameters_from_signature(func)
        spec = AIToolSpec(
            name=name,
            description=description,
            read_only=read_only,
            concurrency_safe=concurrency_safe,
            risk_level=risk_level,
            is_capability_bridge=is_capability_bridge,
            parameters=parameters,
            entrypoint=func,
            origin="builtin",
            tags=tags,
        )
        _PENDING_TOOLS.append(spec)
        func.__ai_tool_spec__ = spec
        return func

    return decorator


def collect_pending_tools() -> list[Any]:
    """Return and clear all pending tool specs collected by decorators."""

    tools = list(_PENDING_TOOLS)
    _PENDING_TOOLS.clear()
    return tools
