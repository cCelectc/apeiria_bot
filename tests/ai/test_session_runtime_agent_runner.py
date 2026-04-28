from __future__ import annotations

import asyncio
from datetime import datetime, timezone

from apeiria.ai.model import AIModelBindingTarget, AIModelToolDefinition
from apeiria.ai.tools import AIToolPolicy
from apeiria.app.ai.agent_turn import AgentTurnResult
from apeiria.app.ai.session_runtime import (
    DeliveryTarget,
    RuntimeAgentRunner,
    RuntimeTurnSource,
    ToolExposurePlan,
    TurnContext,
)
from apeiria.conversation.models import ChatSessionIdentity


def _context(*, tools: tuple[AIModelToolDefinition, ...] = ()) -> TurnContext:
    return TurnContext(
        trace_id="trace-1",
        identity=ChatSessionIdentity(
            session_id="session-1",
            platform="test",
            bot_id="bot-1",
            scene_type="private",
            scene_id="user-1",
            subject_id=None,
        ),
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text="hello",
            source_message_id="msg-1",
            user_id="user-1",
            direct_signal=True,
            is_private=True,
        ),
        delivery_target=DeliveryTarget(session_id="session-1"),
        current_time=datetime(2026, 4, 28, tzinfo=timezone.utc),
        model_target=AIModelBindingTarget(
            conversation_id="session-1",
            group_id=None,
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(execution_enabled=bool(tools)),
        tool_exposure_plan=ToolExposurePlan(selected_tools=tools),
    )


def test_agent_runner_uses_direct_executor_without_tools() -> None:
    calls: list[str] = []

    async def direct(context: TurnContext) -> AgentTurnResult:
        calls.append(f"direct:{context.trace_id}")
        return AgentTurnResult.skipped(
            trace_id=context.trace_id,
            runtime_mode=context.runtime_mode,
            finish_reason="direct",
        )

    async def tool_capable(context: TurnContext) -> AgentTurnResult:
        calls.append(f"tool:{context.trace_id}")
        return AgentTurnResult.skipped(
            trace_id=context.trace_id,
            runtime_mode=context.runtime_mode,
            finish_reason="tool",
        )

    runner = RuntimeAgentRunner(
        direct_executor=direct,
        tool_capable_executor=tool_capable,
    )

    result = asyncio.run(runner.run_turn(_context()))

    assert result.finish_reason == "direct"
    assert calls == ["direct:trace-1"]


def test_agent_runner_uses_tool_capable_executor_with_selected_tools() -> None:
    calls: list[str] = []

    async def direct(context: TurnContext) -> AgentTurnResult:
        calls.append(f"direct:{context.trace_id}")
        return AgentTurnResult.skipped(
            trace_id=context.trace_id,
            runtime_mode=context.runtime_mode,
            finish_reason="direct",
        )

    async def tool_capable(context: TurnContext) -> AgentTurnResult:
        calls.append(f"tool:{context.tool_exposure_plan.selected_tool_names}")
        return AgentTurnResult.skipped(
            trace_id=context.trace_id,
            runtime_mode=context.runtime_mode,
            finish_reason="tool",
        )

    runner = RuntimeAgentRunner(
        direct_executor=direct,
        tool_capable_executor=tool_capable,
    )
    tool = AIModelToolDefinition(
        name="memory.query",
        description="Recall memory",
        parameters={"type": "object", "properties": {}},
    )

    result = asyncio.run(runner.run_turn(_context(tools=(tool,))))

    assert result.finish_reason == "tool"
    assert calls == ["tool:('memory.query',)"]
