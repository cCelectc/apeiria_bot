from __future__ import annotations

import asyncio
from typing import Any

from apeiria.ai.agent.agent import Agent
from apeiria.ai.types import (
    Message,
    StreamEvent,
    StreamEventType,
    Tool,
    ToolCall,
    ToolResult,
)


def test_multi_round_tool_calls() -> None:
    call_count = 0

    async def mock_stream(**_kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call=ToolCall(id="c1", name="lookup", arguments={"key": "abc"}),
            )
            yield StreamEvent(type=StreamEventType.END)
        elif call_count == 2:  # noqa: PLR2004
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call=ToolCall(id="c2", name="lookup", arguments={"key": "def"}),
            )
            yield StreamEvent(type=StreamEventType.END)
        else:
            yield StreamEvent(type=StreamEventType.TEXT_DELTA, text="Final answer")
            yield StreamEvent(type=StreamEventType.END)

    async def tool_exec(**kw: Any) -> ToolResult:
        return ToolResult(success=True, content=f"value:{kw.get('key', '')}")

    tool = Tool(
        name="lookup",
        description="lookup tool",
        parameters={
            "type": "object",
            "properties": {"key": {"type": "string"}},
        },
        execute=tool_exec,
    )
    agent = Agent("test_session", stream_fn=mock_stream, tools=[tool])

    async def _run() -> None:
        result = await agent.run([Message(role="user", content="search")])
        assert result.has_reply
        assert result.reply_text == "Final answer"

    asyncio.run(_run())


def test_unknown_tool_returns_error() -> None:
    call_count = 0

    async def mock_stream(**_kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call=ToolCall(id="c1", name="nonexistent_tool", arguments={}),
            )
            yield StreamEvent(type=StreamEventType.END)
        else:
            yield StreamEvent(type=StreamEventType.TEXT_DELTA, text="Handled error")
            yield StreamEvent(type=StreamEventType.END)

    agent = Agent("test_session", stream_fn=mock_stream)

    async def _run() -> None:
        result = await agent.run([Message(role="user", content="do it")])
        assert result.has_reply
        assert result.reply_text == "Handled error"

    asyncio.run(_run())


def test_agent_emits_tool_events() -> None:
    events_collected: list[str] = []

    async def mock_stream(**_kwargs: Any) -> Any:
        messages = _kwargs.get("messages", [])
        if any(m.get("role") == "tool" for m in messages):
            yield StreamEvent(type=StreamEventType.TEXT_DELTA, text="Done")
            yield StreamEvent(type=StreamEventType.END)
        else:
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call=ToolCall(id="c1", name="echo", arguments={}),
            )
            yield StreamEvent(type=StreamEventType.END)

    async def tool_exec(**_kw: Any) -> ToolResult:
        return ToolResult(success=True, content="ok")

    tool = Tool(
        name="echo",
        description="echo",
        parameters={"type": "object", "properties": {}},
        execute=tool_exec,
    )
    agent = Agent("test_session", stream_fn=mock_stream, tools=[tool])

    async def on_event(event: Any) -> None:
        events_collected.append(event.type)

    agent.event_bus.subscribe("tool:start", on_event)
    agent.event_bus.subscribe("tool:end", on_event)

    async def _run() -> None:
        await agent.run([Message(role="user", content="go")])
        assert "tool:start" in events_collected
        assert "tool:end" in events_collected

    asyncio.run(_run())
