from __future__ import annotations

from apeiria.ai.tools.registry import (
    HandlerRegistry,
    ToolRegistry,
    register_context_handler,
    register_tool,
)
from apeiria.ai.types import PromptFragment, SessionContext, Tool, ToolResult


def setup_function() -> None:
    ToolRegistry.clear()
    HandlerRegistry.clear()


def test_register_and_list_tool() -> None:
    tool = Tool(
        name="test_tool",
        description="A test tool",
        parameters={"type": "object", "properties": {}},
        execute=lambda: ToolResult(success=True, content="ok"),
    )
    register_tool(tool)
    all_tools = ToolRegistry.list_all()
    assert len(all_tools) == 1
    assert all_tools[0].name == "test_tool"


def test_idempotent_registration() -> None:
    tool = Tool(name="dup", description="", parameters={}, execute=lambda: None)
    register_tool(tool)
    register_tool(tool)
    assert len(ToolRegistry.list_all()) == 1


def test_get_tool() -> None:
    tool = Tool(name="find_me", description="", parameters={}, execute=lambda: None)
    register_tool(tool)
    assert ToolRegistry.get("find_me") is not None
    assert ToolRegistry.get("not_exist") is None


def test_register_context_handler() -> None:
    async def handler(_ctx: SessionContext) -> PromptFragment | None:
        return PromptFragment(role="system", content="test")

    register_context_handler(handler)
    assert len(HandlerRegistry.list_all()) == 1


def test_handler_idempotent() -> None:
    async def handler(_ctx: SessionContext) -> PromptFragment | None:
        return None

    register_context_handler(handler)
    register_context_handler(handler)
    assert len(HandlerRegistry.list_all()) == 1
