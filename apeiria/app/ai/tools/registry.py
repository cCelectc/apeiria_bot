"""Pure in-memory tool registry."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from apeiria.app.ai.tools.models import AIToolSpec


class AIToolRegistry:
    """Simple registry for AI-visible tools."""

    def __init__(self) -> None:
        self._tools: dict[str, AIToolSpec] = {}

    def register(self, tool: AIToolSpec) -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> AIToolSpec | None:
        return self._tools.get(name)

    def list_tools(self) -> list[AIToolSpec]:
        return [self._tools[name] for name in sorted(self._tools)]
