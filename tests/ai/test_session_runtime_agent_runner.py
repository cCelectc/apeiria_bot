from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from apeiria.ai.model import AIModelBindingTarget, AIModelMessage, AIModelToolDefinition
from apeiria.ai.tools import AIToolPolicy
from apeiria.app.ai.session_runtime import (
    DeliveryTarget,
    RuntimeExecutionOutcome,
    RuntimeTurnPlan,
    RuntimeTurnSource,
    ToolExposurePlan,
    TurnContext,
)
from apeiria.app.ai.session_runtime import execution as execution_module
from apeiria.app.ai.session_runtime.runner import RuntimeAgentRunner
from apeiria.conversation.models import ChatSessionIdentity
from tests.ai.agent_turn_helpers import selected_model


def _context(*, exposure_plan: ToolExposurePlan | None = None) -> TurnContext:
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
        tool_policy=AIToolPolicy(execution_enabled=True),
        tool_exposure_plan=exposure_plan or ToolExposurePlan(),
        prompt_messages=(AIModelMessage(role="user", content="hello"),),
    )


def _plan(*, exposure_plan: ToolExposurePlan | None = None) -> RuntimeTurnPlan:
    return RuntimeTurnPlan(
        stage="planning",
        selected=selected_model("runner"),
        fallback_models=(),
        skill_runtime=SimpleNamespace(turns=()),
        skill_activation=None,
        pre_tool_task_class="reply_default",
        prompt_messages=(AIModelMessage(role="user", content="hello"),),
        prompt_diagnostics={},
        tool_exposure_plan=exposure_plan or ToolExposurePlan(),
    )


def _outcome(source: str) -> RuntimeExecutionOutcome:
    return RuntimeExecutionOutcome(
        stage="execution",
        response=None,
        skill_runtime=SimpleNamespace(turns=()),
        post_tool_task_class=None,
        delivery_result=None,
        turn_result=SimpleNamespace(response_source=source),
    )


def test_agent_runner_uses_native_direct_path_without_tools(monkeypatch: Any) -> None:
    calls: list[tuple[str, TurnContext, RuntimeTurnPlan]] = []

    async def direct(
        *,
        turn_context: TurnContext,
        plan: RuntimeTurnPlan,
    ) -> RuntimeExecutionOutcome:
        calls.append(("direct", turn_context, plan))
        return _outcome("direct")

    async def tool_capable(**_: object) -> RuntimeExecutionOutcome:
        raise AssertionError("tool path should not run")  # noqa: TRY003

    monkeypatch.setattr(execution_module, "execute_direct_runtime_turn", direct)
    monkeypatch.setattr(
        execution_module,
        "execute_tool_capable_runtime_turn",
        tool_capable,
    )
    context = _context()
    plan = _plan()

    result = asyncio.run(RuntimeAgentRunner().run_turn(context, plan))

    assert result.turn_result is not None
    assert result.turn_result.response_source == "direct"
    assert calls == [("direct", context, plan)]


def test_agent_runner_uses_native_tool_path_with_selected_tools(
    monkeypatch: Any,
) -> None:
    tool = AIModelToolDefinition(
        name="memory.query",
        description="Recall memory",
        parameters={"type": "object", "properties": {}},
    )
    exposure_plan = ToolExposurePlan(selected_tools=(tool,))
    calls: list[tuple[str, TurnContext, RuntimeTurnPlan]] = []

    async def direct(**_: object) -> RuntimeExecutionOutcome:
        raise AssertionError("direct path should not run")  # noqa: TRY003

    async def tool_capable(
        *,
        turn_context: TurnContext,
        plan: RuntimeTurnPlan,
    ) -> RuntimeExecutionOutcome:
        calls.append(("tool", turn_context, plan))
        return _outcome("tool_loop")

    monkeypatch.setattr(execution_module, "execute_direct_runtime_turn", direct)
    monkeypatch.setattr(
        execution_module,
        "execute_tool_capable_runtime_turn",
        tool_capable,
    )
    context = _context(exposure_plan=exposure_plan)
    plan = _plan(exposure_plan=exposure_plan)

    result = asyncio.run(RuntimeAgentRunner().run_turn(context, plan))

    assert result.turn_result is not None
    assert result.turn_result.response_source == "tool_loop"
    assert calls == [("tool", context, plan)]
