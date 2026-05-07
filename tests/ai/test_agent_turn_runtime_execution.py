from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from apeiria.ai.model import AIModelBindingTarget, AIModelMessage, AIModelToolDefinition
from apeiria.ai.tools import AIToolPolicy, AIToolTurnCreateInput, ToolGatewayResult
from apeiria.app.ai.agent_turn import AgentModelGenerationResult, AgentTurnResult
from apeiria.app.ai.runtime import execution as execution_module
from apeiria.app.ai.runtime.planning.prompts import RuntimePromptComposeInput
from apeiria.app.ai.runtime.planning.tool_exposure import ToolExposurePlan
from apeiria.app.ai.runtime.session.context import (
    DeliveryTarget,
    RuntimeTurnSource,
    TurnContext,
)
from apeiria.app.ai.runtime.stages import RuntimeTurnPlan
from apeiria.conversation.models import ChatSessionIdentity
from tests.ai.agent_turn_helpers import model_response, selected_model


def _identity() -> ChatSessionIdentity:
    return ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id=None,
    )


def _context(
    *,
    runtime_mode: str = "message",
    exposure_plan: ToolExposurePlan | None = None,
    prompt_messages: tuple[AIModelMessage, ...] | None = None,
) -> TurnContext:
    return TurnContext(
        trace_id=f"trace-{runtime_mode}",
        identity=_identity(),
        source=RuntimeTurnSource(
            runtime_mode=runtime_mode,  # type: ignore[arg-type]
            message_text="runtime request text",
            source_message_id="msg-1",
            user_id="user-1",
            direct_signal=True,
            is_private=True,
        ),
        delivery_target=DeliveryTarget(
            session_id="session-1",
            reply_to_message_id="msg-1",
            delivery_channel=runtime_mode,
        ),
        current_time=datetime(2026, 4, 28, tzinfo=timezone.utc),
        model_target=AIModelBindingTarget(
            conversation_id="session-1",
            group_id=None,
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(execution_enabled=True),
        tool_exposure_plan=exposure_plan or ToolExposurePlan(),
        prompt_messages=prompt_messages
        or (AIModelMessage(role="user", content="context-only prompt"),),
        prompt_diagnostics={"prompt_purpose": "reply_final"},
    )


def _compose_input() -> RuntimePromptComposeInput:
    return RuntimePromptComposeInput(
        persona=None,
        scene_type="private",
        person_profile=(),
        relationship=None,
        tool_policy="No tools.",
        tool_results=(),
        memories=[],
        conversation_summary=None,
        social_policy_summary="reply",
        future_task_context=None,
        turns=[],
    )


def _plan(
    *,
    exposure_plan: ToolExposurePlan | None = None,
    prompt_messages: tuple[AIModelMessage, ...] | None = None,
    reply_compose_input: RuntimePromptComposeInput | None = None,
) -> RuntimeTurnPlan:
    return RuntimeTurnPlan(
        stage="planning",
        selected=selected_model("main"),
        fallback_models=(),
        skill_runtime=ToolGatewayResult(policy_text="", result_lines=(), turns=()),
        skill_activation=None,
        pre_tool_task_class="reply_default",
        prompt_messages=prompt_messages
        or (AIModelMessage(role="user", content="context-only prompt"),),
        prompt_diagnostics={"prompt_purpose": "reply_final"},
        tool_exposure_plan=exposure_plan or ToolExposurePlan(),
        reply_compose_input=reply_compose_input,
        tool_mode="allow",
        tool_execution_timeout_seconds=3.0,
    )


def test_direct_execution_records_future_task_runtime_mode(monkeypatch: Any) -> None:
    selected = selected_model("main")
    captured_requests: list[Any] = []

    async def generate_model_turn(request: Any) -> AgentModelGenerationResult:
        captured_requests.append(request)
        response = model_response(selected, "future answer")
        return AgentModelGenerationResult(
            response=response,
            selected=selected,
            turn=AgentTurnResult(
                trace_id=request.trace_id,
                runtime_mode=request.runtime_mode,
                status="completed",
                finish_reason="direct_model_completed",
                response=response,
                response_source=request.response_source,
            ),
        )

    monkeypatch.setattr(
        execution_module,
        "generate_model_turn",
        generate_model_turn,
    )
    context = _context(runtime_mode="future_task")
    plan = _plan(prompt_messages=context.prompt_messages)

    result = asyncio.run(
        execution_module.execute_direct_runtime_turn(
            turn_context=context,
            plan=plan,
        )
    )

    assert captured_requests[0].runtime_mode == "future_task"
    assert captured_requests[0].prompt == ""
    assert captured_requests[0].messages == context.prompt_messages
    assert result.turn_result is not None
    assert result.turn_result.runtime_mode == "future_task"
    assert result.response is not None
    assert result.response.content == "future answer"


def test_direct_execution_uses_turn_context_messages(monkeypatch: Any) -> None:
    selected = selected_model("main")
    captured_requests: list[Any] = []

    async def generate_model_turn(request: Any) -> AgentModelGenerationResult:
        captured_requests.append(request)
        response = model_response(selected, "context answer")
        return AgentModelGenerationResult(
            response=response,
            selected=selected,
            turn=AgentTurnResult(
                trace_id=request.trace_id,
                runtime_mode=request.runtime_mode,
                status="completed",
                finish_reason="direct_model_completed",
                response=response,
                response_source=request.response_source,
            ),
        )

    monkeypatch.setattr(
        execution_module,
        "generate_model_turn",
        generate_model_turn,
    )
    context = _context(
        prompt_messages=(AIModelMessage(role="user", content="context prompt"),)
    )
    plan = _plan(prompt_messages=context.prompt_messages)

    result = asyncio.run(
        execution_module.execute_direct_runtime_turn(
            turn_context=context,
            plan=plan,
        )
    )

    assert captured_requests[0].trace_id == context.trace_id
    assert captured_requests[0].session_id == "session-1"
    assert captured_requests[0].messages == context.prompt_messages
    assert result.response is not None
    assert result.response.content == "context answer"
    assert result.turn_result is not None
    assert result.turn_result.metadata["prompt_diagnostics"] == {
        "prompt_purpose": "reply_final"
    }


def test_tool_execution_uses_runtime_exposure_and_refinement_messages(
    monkeypatch: Any,
) -> None:
    selected = selected_model("main")
    refinement_requests: list[Any] = []
    tool_loop_requests: list[Any] = []
    tool_loop_messages: list[tuple[Any, ...]] = []
    tool_definition = AIModelToolDefinition(
        name="memory.query",
        description="Recall memory",
        parameters={"type": "object", "properties": {}},
    )
    exposure_plan = ToolExposurePlan(selected_tools=(tool_definition,))

    async def run_tool_loop(
        request: Any,
        *,
        messages: list[Any],
        tools: tuple[Any, ...],
        selected: Any,
        fallback_models: tuple[Any, ...],
    ) -> ToolGatewayResult:
        del tools, fallback_models
        tool_loop_requests.append(request)
        tool_loop_messages.append(tuple(messages))
        return ToolGatewayResult(
            policy_text="allowed: memory.query",
            result_lines=("- [memory.query] result",),
            turns=(
                AIToolTurnCreateInput(
                    author_id="tool",
                    text_content="- [memory.query] result",
                    meta={"tool_name": "memory.query"},
                ),
            ),
            final_response=model_response(selected, "draft after tool"),
            loop_finish_reason="completed",
        )

    async def generate_model_turn(request: Any) -> Any:
        refinement_requests.append(request)
        response = model_response(selected, "final after refinement")
        return AgentModelGenerationResult(
            response=response,
            selected=selected,
            turn=AgentTurnResult(
                trace_id=request.trace_id,
                runtime_mode=request.runtime_mode,
                status="completed",
                finish_reason="refinement_completed",
                response=response,
                response_source=request.response_source,
            ),
        )

    async def select_fallbacks(_selected: Any) -> tuple[Any, ...]:
        return ()

    async def select_model(*, task_class: str, target: object) -> Any:
        del task_class, target
        return selected

    monkeypatch.setattr(execution_module.tool_gateway, "run_tool_loop", run_tool_loop)
    monkeypatch.setattr(
        execution_module,
        "generate_model_turn",
        generate_model_turn,
    )
    monkeypatch.setattr(
        execution_module,
        "select_fallback_models",
        select_fallbacks,
    )
    monkeypatch.setattr(execution_module, "select_model", select_model)

    context = _context(
        runtime_mode="future_task",
        exposure_plan=exposure_plan,
        prompt_messages=(AIModelMessage(role="user", content="tool prompt"),),
    )
    plan = _plan(
        exposure_plan=exposure_plan,
        prompt_messages=context.prompt_messages,
        reply_compose_input=_compose_input(),
    )

    result = asyncio.run(
        execution_module.execute_tool_capable_runtime_turn(
            turn_context=context,
            plan=plan,
        )
    )

    assert tool_loop_requests[0].runtime_mode == "future_task"
    assert tool_loop_requests[0].executable_tool_names == frozenset({"memory.query"})
    assert tool_loop_messages == [context.prompt_messages]
    assert refinement_requests[0].runtime_mode == "future_task"
    assert refinement_requests[0].prompt == ""
    assert refinement_requests[0].messages
    assert refinement_requests[0].messages[-1].role == "user"
    assert result.response is not None
    assert result.response.content == "final after refinement"
    assert result.turn_result is not None
    assert result.turn_result.runtime_mode == "future_task"
    assert result.turn_result.response_source == "refinement"


def test_tool_execution_uses_provider_schema_from_same_exposure_plan(
    monkeypatch: Any,
) -> None:
    tool_definition = AIModelToolDefinition(
        name="memory_query",
        description="Recall memory",
        parameters={"type": "object", "properties": {}},
    )
    exposure_plan = ToolExposurePlan(selected_tools=(tool_definition,))
    gateway_tools: list[tuple[AIModelToolDefinition, ...]] = []
    gateway_allowlists: list[frozenset[str] | None] = []

    async def run_tool_loop(
        request: Any,
        *,
        messages: list[Any],
        tools: tuple[AIModelToolDefinition, ...],
        selected: Any,
        fallback_models: tuple[Any, ...],
    ) -> ToolGatewayResult:
        del messages, fallback_models
        gateway_allowlists.append(request.executable_tool_names)
        gateway_tools.append(tools)
        return ToolGatewayResult(
            policy_text="allowed: memory.query",
            result_lines=(),
            turns=(),
            final_response=model_response(selected, "tool answer"),
            loop_finish_reason="final_response",
        )

    monkeypatch.setattr(execution_module.tool_gateway, "run_tool_loop", run_tool_loop)
    context = _context(exposure_plan=exposure_plan)
    plan = _plan(
        exposure_plan=exposure_plan,
        prompt_messages=context.prompt_messages,
        reply_compose_input=_compose_input(),
    )

    result = asyncio.run(
        execution_module.execute_tool_capable_runtime_turn(
            turn_context=context,
            plan=plan,
        )
    )

    assert gateway_tools == [(tool_definition,)]
    assert gateway_allowlists == [frozenset({"memory.query"})]
    assert result.response is not None
    assert result.response.content == "tool answer"
    assert result.turn_result is not None
    assert result.turn_result.response_source == "tool_loop"
