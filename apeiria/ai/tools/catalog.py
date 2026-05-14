"""Lifecycle-owned catalog for essential builtin AI tools."""

from __future__ import annotations

from typing import TYPE_CHECKING, Protocol, cast

from apeiria.ai.tools.essential import build_essential_builtin_tools

if TYPE_CHECKING:
    from apeiria.ai.tools.models import AIToolDefinition


class AIToolCatalogRegistry(Protocol):
    """Minimal registry surface used by the builtin catalog loader."""

    def get(self, name: str) -> "AIToolDefinition | None": ...

    def register(self, tool: "AIToolDefinition") -> None: ...


def essential_builtin_tools() -> tuple["AIToolDefinition", ...]:
    """Return essential builtin tool definitions in deterministic order."""

    return tuple(sorted(build_essential_builtin_tools(), key=lambda tool: tool.name))


def load_builtin_tool_catalog(registry: AIToolCatalogRegistry) -> int:
    """Register essential builtin tools through the shared AI tool registry."""

    count = 0
    for tool in essential_builtin_tools():
        existing = _get_existing_tool(registry, tool.name)
        if _is_same_catalog_tool(existing):
            continue
        if existing is not None:
            registry.register(tool)  # type: ignore[attr-defined]
        else:
            registry.register(tool)  # type: ignore[attr-defined]
            count += 1
    return count


def _get_existing_tool(registry: object, name: str) -> "AIToolDefinition | None":
    get = getattr(registry, "get", None)
    if callable(get):
        return cast("AIToolDefinition | None", get(name))
    list_tools = getattr(registry, "list_tools", None)
    if not callable(list_tools):
        return None
    for tool in cast("list[AIToolDefinition]", list_tools()):
        if tool.name == name:
            return tool
    return None


def _is_same_catalog_tool(tool: "AIToolDefinition | None") -> bool:
    return tool is not None and tool.origin == "builtin" and "essential" in tool.tags


__all__ = ["essential_builtin_tools", "load_builtin_tool_catalog"]
