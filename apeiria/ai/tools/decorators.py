"""Declarative @ai_tool decorator for tool registration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.ai.capabilities import (
    AICapabilityContract,
    AICapabilityKind,
    AICapabilityOrigin,
    AICapabilitySafety,
)
from apeiria.ai.tools.registry import local_tool_declaration
from apeiria.ai.tools.schema import build_json_schema, build_parameters_from_signature

if TYPE_CHECKING:
    from collections.abc import Callable

    from apeiria.ai.tools.models import AIToolRiskLevel

_PENDING_TOOLS: list[Any] = []


def ai_tool(  # noqa: PLR0913
    *,
    name: str,
    description: str,
    read_only: bool,
    concurrency_safe: bool,
    risk_level: AIToolRiskLevel = "low",
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
        parameters = build_parameters_from_signature(func)
        contract = AICapabilityContract(
            name=name,
            kind=AICapabilityKind.EXECUTABLE,
            origin=AICapabilityOrigin.BUILTIN,
            description=description,
            input_schema=build_json_schema(parameters) if parameters else {},
            safety=AICapabilitySafety(
                read_only=read_only,
                risk_level=risk_level,
                concurrency_safe=concurrency_safe,
            ),
            tags=tags,
        )
        declaration = local_tool_declaration(contract=contract, handler=func)
        _PENDING_TOOLS.append(declaration)
        func.__ai_tool_contract__ = contract
        func.__ai_tool_binding__ = declaration.binding
        return func

    return decorator


def collect_pending_tools() -> list[Any]:
    """Return and clear all pending tool specs collected by decorators."""

    tools = list(_PENDING_TOOLS)
    _PENDING_TOOLS.clear()
    return tools
