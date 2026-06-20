from __future__ import annotations

import asyncio
from typing import Any

from apeiria.ai.agent.agent import Agent
from apeiria.ai.types import (
    Message,
    StreamEvent,
    StreamEventType,
    TokenUsage,
    Tool,
    ToolCall,
    ToolResult,
)


def test_agent_skip_tool_call() -> None:
    async def mock_stream(**_kwargs: Any) -> Any:
        yield StreamEvent(
            type=StreamEventType.TOOL_CALL_END,
            tool_call=ToolCall(id="1", name="skip_if_not_worth_it"),
        )
        yield StreamEvent(type=StreamEventType.END)

    skip_tool = Tool(
        name="skip_if_not_worth_it",
        description="skip",
        parameters={},
        execute=lambda: ToolResult(success=True),
    )
    agent = Agent("test_session", stream_fn=mock_stream, tools=[skip_tool])

    async def _run() -> None:
        result = await agent.run([Message(role="user", content="hi")])
        assert not result.has_reply

    asyncio.run(_run())


def test_agent_text_reply() -> None:
    async def mock_stream(**_kwargs: Any) -> Any:
        yield StreamEvent(type=StreamEventType.TEXT_DELTA, text="Hello!")
        yield StreamEvent(
            type=StreamEventType.USAGE,
            usage=TokenUsage(prompt_tokens=50, completion_tokens=10),
        )
        yield StreamEvent(type=StreamEventType.END)

    agent = Agent("test_session", stream_fn=mock_stream)

    async def _run() -> None:
        result = await agent.run([Message(role="user", content="hi")])
        assert result.has_reply
        assert result.reply_text == "Hello!"

    asyncio.run(_run())


def test_agent_empty_response_is_no_action() -> None:
    async def mock_stream(**_kwargs: Any) -> Any:
        yield StreamEvent(type=StreamEventType.END)

    agent = Agent("test_session", stream_fn=mock_stream)

    async def _run() -> None:
        result = await agent.run([Message(role="user", content="...")])
        assert not result.has_reply

    asyncio.run(_run())


def test_agent_tool_loop() -> None:
    call_count = 0

    async def mock_stream(**_kwargs: Any) -> Any:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            yield StreamEvent(
                type=StreamEventType.TOOL_CALL_END,
                tool_call=ToolCall(id="c1", name="my_tool", arguments={"x": 1}),
            )
            yield StreamEvent(type=StreamEventType.END)
        else:
            yield StreamEvent(type=StreamEventType.TEXT_DELTA, text="Done with tool")
            yield StreamEvent(type=StreamEventType.END)

    async def tool_exec(**kw: Any) -> ToolResult:
        return ToolResult(success=True, content=f"result: {kw.get('x', 0)}")

    tool = Tool(
        name="my_tool",
        description="test",
        parameters={"type": "object", "properties": {"x": {"type": "integer"}}},
        execute=tool_exec,
    )
    agent = Agent("test_session", stream_fn=mock_stream, tools=[tool])

    async def _run() -> None:
        result = await agent.run([Message(role="user", content="use tool")])
        assert result.has_reply
        assert "Done with tool" in (result.reply_text or "")

    asyncio.run(_run())


def test_agent_usage_tracking() -> None:
    async def mock_stream(**_kwargs: Any) -> Any:
        yield StreamEvent(type=StreamEventType.TEXT_DELTA, text="reply")
        yield StreamEvent(
            type=StreamEventType.USAGE,
            usage=TokenUsage(prompt_tokens=200, completion_tokens=30),
        )
        yield StreamEvent(type=StreamEventType.END)

    agent = Agent("test_session", stream_fn=mock_stream)

    async def _run() -> None:
        result = await agent.run([Message(role="user", content="hi")])
        assert result.usage is not None
        assert result.usage.prompt_tokens == 200  # noqa: PLR2004
        assert result.usage.completion_tokens == 30  # noqa: PLR2004

    asyncio.run(_run())
