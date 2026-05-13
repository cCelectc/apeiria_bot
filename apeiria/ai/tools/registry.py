"""In-memory registry for first-class AI tools."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Mapping

    from apeiria.ai.tools.models import AIToolDefinition, AIToolOrigin


class AIDuplicateToolError(ValueError):
    """Raised when a tool name is registered twice."""


class AIInvalidToolSchemaError(ValueError):
    """Raised when a tool schema is outside the canonical provider-neutral subset."""


@dataclass(frozen=True)
class AIToolRegistrySnapshot:
    """Immutable AI tool registry read model."""

    tools: tuple["AIToolDefinition", ...]
    by_name: "Mapping[str, AIToolDefinition]"


class AIToolRegistry:
    """Mutable registry for provider-neutral AI tool definitions."""

    def __init__(self, tools: tuple["AIToolDefinition", ...] = ()) -> None:
        self._tools: dict[str, "AIToolDefinition"] = {}
        for tool in tools:
            self.register(tool)

    def register(self, tool: "AIToolDefinition") -> None:
        """Register one tool by stable name."""

        if tool.name in self._tools:
            raise AIDuplicateToolError(tool.name)
        validate_tool_schema(tool.input_schema)
        self._tools[tool.name] = tool

    def get(self, name: str) -> "AIToolDefinition | None":
        return self._tools.get(name)

    def list_tools(self) -> list["AIToolDefinition"]:
        return list(self.snapshot().tools)

    def list_by_origin(self, origin: "AIToolOrigin") -> list["AIToolDefinition"]:
        return [tool for tool in self.list_tools() if tool.origin == origin]

    def snapshot(self) -> AIToolRegistrySnapshot:
        tools = tuple(self._tools[name] for name in sorted(self._tools))
        return AIToolRegistrySnapshot(
            tools=tools,
            by_name=MappingProxyType({tool.name: tool for tool in tools}),
        )

    def register_pending_tools(self) -> int:
        """Import handler modules and register all decorator-collected tools."""

        from apeiria.ai.tools.decorators import collect_pending_tools
        from apeiria.ai.tools.handlers import ensure_handlers_loaded

        ensure_handlers_loaded()
        pending: list[Any] = collect_pending_tools()
        count = 0
        for tool in pending:
            self.register(tool)
            count += 1
        return count


__all__ = [
    "AIDuplicateToolError",
    "AIInvalidToolSchemaError",
    "AIToolRegistry",
    "AIToolRegistrySnapshot",
    "validate_tool_schema",
]


_SUPPORTED_SCHEMA_TYPES = frozenset(
    {"string", "number", "integer", "boolean", "array", "object"}
)
_SUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "type",
        "properties",
        "required",
        "description",
        "enum",
        "items",
        "additionalProperties",
        "default",
    }
)
_UNSUPPORTED_SCHEMA_KEYS = frozenset(
    {
        "$ref",
        "$defs",
        "definitions",
        "oneOf",
        "anyOf",
        "allOf",
        "not",
        "patternProperties",
        "dependencies",
        "dependentRequired",
        "dependentSchemas",
    }
)


def validate_tool_schema(schema: dict[str, Any]) -> None:
    """Validate the provider-neutral JSON Schema subset accepted by tools."""

    if not isinstance(schema, dict):
        _schema_error("root schema must be object")
    if schema.get("type") != "object":
        _schema_error("root schema must be object")
    _validate_schema_node(schema, path="$")


def _validate_schema_node(schema: Any, *, path: str) -> None:  # noqa: C901
    if not isinstance(schema, dict):
        _schema_error(f"{path}: schema node must be object")

    for key in schema:
        if key in _UNSUPPORTED_SCHEMA_KEYS:
            _schema_error(f"{path}: unsupported schema key {key}")
        if key not in _SUPPORTED_SCHEMA_KEYS:
            _schema_error(f"{path}: unsupported schema key {key}")

    schema_type = schema.get("type")
    if isinstance(schema_type, list):
        _schema_error(f"{path}: union schema types are unsupported")
    if schema_type not in _SUPPORTED_SCHEMA_TYPES:
        _schema_error(f"{path}: unsupported schema type {schema_type}")

    enum_values = schema.get("enum")
    if enum_values is not None and not isinstance(enum_values, list):
        _schema_error(f"{path}: enum must be a list")

    if "description" in schema and not isinstance(schema["description"], str):
        _schema_error(f"{path}: description must be a string")

    if schema_type == "object":
        _validate_object_schema(schema, path=path)
    elif schema_type == "array":
        items = schema.get("items")
        if items is None:
            _schema_error(f"{path}: array schema must declare items")
        _validate_schema_node(items, path=f"{path}.items")
    elif "properties" in schema or "required" in schema:
        _schema_error(
            f"{path}: properties and required are only valid on object schemas"
        )


def _validate_object_schema(schema: dict[str, Any], *, path: str) -> None:
    properties = schema.get("properties", {})
    if not isinstance(properties, dict):
        _schema_error(f"{path}: properties must be an object")

    required = schema.get("required", [])
    if not isinstance(required, list) or not all(
        isinstance(item, str) for item in required
    ):
        _schema_error(f"{path}: required must be a string list")

    property_names = set(properties)
    unknown_required = [name for name in required if name not in property_names]
    if unknown_required:
        _schema_error(f"{path}: required field is not declared: {unknown_required[0]}")

    additional = schema.get("additionalProperties")
    if additional is not None and not isinstance(additional, bool):
        _schema_error(f"{path}: additionalProperties must be boolean")

    for name, child_schema in properties.items():
        if not isinstance(name, str):
            _schema_error(f"{path}: property names must be strings")
        _validate_schema_node(child_schema, path=f"{path}.properties.{name}")


def _schema_error(message: str) -> None:
    raise AIInvalidToolSchemaError(message)
