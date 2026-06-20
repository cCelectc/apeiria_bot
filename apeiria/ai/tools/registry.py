from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

if TYPE_CHECKING:
    from collections.abc import Awaitable, Callable

    from apeiria.ai.types import PromptFragment, SessionContext, Tool


class ToolRegistry:
    _tools: ClassVar[dict[str, Tool]] = {}

    @classmethod
    def register(cls, tool: Tool) -> None:
        if tool.name in cls._tools:
            return
        cls._tools[tool.name] = tool

    @classmethod
    def list_all(cls) -> list[Tool]:
        return list(cls._tools.values())

    @classmethod
    def get(cls, name: str) -> Tool | None:
        return cls._tools.get(name)

    @classmethod
    def clear(cls) -> None:
        cls._tools.clear()


class HandlerRegistry:
    _handlers: ClassVar[
        list[Callable[[SessionContext], Awaitable[PromptFragment | None]]]
    ] = []
    _handler_ids: ClassVar[set[int]] = set()

    @classmethod
    def register(
        cls,
        handler: Callable[[SessionContext], Awaitable[PromptFragment | None]],
    ) -> None:
        handler_id = id(handler)
        if handler_id in cls._handler_ids:
            return
        cls._handler_ids.add(handler_id)
        cls._handlers.append(handler)

    @classmethod
    def list_all(
        cls,
    ) -> list[Callable[[SessionContext], Awaitable[PromptFragment | None]]]:
        return list(cls._handlers)

    @classmethod
    def clear(cls) -> None:
        cls._handlers.clear()
        cls._handler_ids.clear()


def register_tool(tool: Tool) -> None:
    ToolRegistry.register(tool)


def register_context_handler(
    handler: Callable[[SessionContext], Awaitable[PromptFragment | None]],
) -> None:
    HandlerRegistry.register(handler)
