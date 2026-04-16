"""Pure in-memory tool registry."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from apeiria.app.ai.tools.models import AIToolOrigin, AIToolSpec


class AIToolRegistry:
    """Registry for AI-visible tools.

    Supports both direct ``register()`` calls and bulk registration
    from the ``@ai_tool`` decorator via ``register_pending_tools()``.
    """

    def __init__(self) -> None:
        self._tools: dict[str, AIToolSpec] = {}

    def register(self, tool: "AIToolSpec") -> None:
        self._tools[tool.name] = tool

    def get(self, name: str) -> "AIToolSpec | None":
        return self._tools.get(name)

    def list_tools(self) -> list["AIToolSpec"]:
        return [self._tools[name] for name in sorted(self._tools)]

    def list_by_origin(self, origin: "AIToolOrigin") -> list["AIToolSpec"]:
        return [tool for tool in self.list_tools() if tool.origin == origin]

    def register_pending_tools(self) -> int:
        """Import handler modules and register all ``@ai_tool`` decorated specs.

        Returns the number of newly registered tools.
        """

        from apeiria.app.ai.tools.decorators import collect_pending_tools
        from apeiria.app.ai.tools.handlers import ensure_handlers_loaded

        ensure_handlers_loaded()
        pending: list[Any] = collect_pending_tools()
        count = 0
        for spec in pending:
            self.register(spec)
            count += 1
        return count
