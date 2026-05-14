"""Declarative @ai_tool decorator for provider-neutral tool definitions."""

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


def ai_tool(  # noqa: PLR0913
    *,
    name: str,
    description: str,
    required_level: AIToolLevel | str,
    origin: AIToolOrigin = "internal",
    enabled: bool = True,
    manageable: bool = False,
    readiness: AIToolReadiness | None = None,
    version: int = 1,
) -> "Callable[..., Any]":
    """Declare an async function as a provider-neutral AI tool."""

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
        )
        func.__ai_tool_definition__ = tool
        return func

    return decorator


_EMPTY_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {},
    "additionalProperties": False,
}


__all__ = ["ai_tool"]
