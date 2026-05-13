"""Declarative @ai_tool decorator for first-class tool registration."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from apeiria.ai.tools.models import (
    AIToolDefinition,
    AIToolLevel,
    AIToolOrigin,
    AIToolReadiness,
    coerce_tool_level,
)
from apeiria.ai.tools.schema import build_json_schema, build_parameters_from_signature

if TYPE_CHECKING:
    from collections.abc import Callable

_PENDING_TOOLS: list[AIToolDefinition] = []


def ai_tool(  # noqa: PLR0913
    *,
    name: str,
    description: str,
    required_level: AIToolLevel | str,
    origin: AIToolOrigin = "builtin",
    enabled: bool = True,
    manageable: bool = False,
    readiness: AIToolReadiness | None = None,
    version: int = 1,
    tags: tuple[str, ...] = (),
) -> "Callable[..., Any]":
    """Register an async function as a provider-neutral AI tool."""

    def decorator(func: Any) -> Any:
        parameters = build_parameters_from_signature(func)
        tool = AIToolDefinition(
            name=name,
            description=description,
            input_schema=build_json_schema(parameters) if parameters else _EMPTY_SCHEMA,
            required_level=coerce_tool_level(required_level),
            executor=func,
            readiness=readiness or AIToolReadiness.available(),
            origin=origin,
            enabled=enabled,
            manageable=manageable,
            version=version,
            tags=tags,
        )
        _PENDING_TOOLS.append(tool)
        func.__ai_tool_definition__ = tool
        return func

    return decorator


def collect_pending_tools() -> list[AIToolDefinition]:
    """Return decorator-collected tool definitions."""

    return list(_PENDING_TOOLS)


_EMPTY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


__all__ = ["ai_tool", "collect_pending_tools"]
