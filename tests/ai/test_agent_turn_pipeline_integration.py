from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any

from apeiria.ai.model import (
    AIModelBindingTarget,
    AIModelToolDefinition,
    AISelectedModel,
)
from apeiria.ai.tools import AIToolTurnCreateInput, ToolGatewayResult
from apeiria.ai.tools.models import AIToolPolicy
from apeiria.app.ai.agent_turn import (
    AgentModelGenerationResult,
    AgentTurnResult,
)
from apeiria.app.ai.pipeline.delivery_steps import DeliveryOutcome
from apeiria.app.ai.pipeline.generation_steps import ReplyPreparation
from apeiria.app.ai.pipeline.input_steps import ReplyInputs
from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
from apeiria.app.ai.reply_strategy import ReplyStrategyDecision
from apeiria.conversation.models import ChatSessionIdentity
from tests.ai.agent_turn_helpers import model_response, selected_model


def test_direct_generation_records_future_task_runtime_mode(monkeypatch: Any) -> None:
    from apeiria.app.ai.pipeline import generation_steps

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

    async def select_fallbacks(
        _selected: AISelectedModel,
    ) -> tuple[AISelectedModel, ...]:
        return ()

    async def deliver_reply(
        _request: AIRuntimeReplyRequest,
        _reply_text: str,
    ) -> DeliveryOutcome:
        return DeliveryOutcome(delivered=True)

    monkeypatch.setattr(generation_steps, "generate_model_turn", generate_model_turn)
    monkeypatch.setattr(
        generation_steps,
        "select_pipeline_fallback_models",
        select_fallbacks,
    )
    monkeypatch.setattr(generation_steps, "record_context_usage", lambda *_, **__: None)
    monkeypatch.setattr(generation_steps, "deliver_generated_reply", deliver_reply)

    identity = ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id=None,
    )
    request = AIRuntimeReplyRequest(
        identity=identity,
        message_text="future task",
        source_message_id=None,
        user_id="user-1",
        sender_id="bot-1",
        runtime_mode="future_task",
    )
    inputs = ReplyInputs(
        turns=[],
        conversation_summary=None,
        relationship_target=object(),
        model_target=AIModelBindingTarget(
            conversation_id="session-1",
            group_id=None,
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(),
        persona=None,
        recalled_memories=[],
        relationship_context=None,
        person_profile=(),
        allowed_tools=(),
        initiative_bias=0.0,
    )
    prep = ReplyPreparation(
        skill_runtime=ToolGatewayResult(policy_text="", result_lines=(), turns=()),
        selected=selected,
        skill_activation=None,
        pre_tool_task_class="reply_default",
    )
    social_decision = ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="allow",
        reason_codes=(),
        reason_text="test",
        evidence={},
        decision_source="fallback",
    )

    result = asyncio.run(
        generation_steps._generate_direct(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prep=prep,
            trace_id="trace-future",
        )
    )

    assert captured_requests[0].runtime_mode == "future_task"
    assert captured_requests[0].prompt == ""
    assert captured_requests[0].messages
    assert captured_requests[0].messages[-1].role == "user"
    assert (
        "Write only the final assistant reply"
        in captured_requests[0].messages[-1].content
    )
    assert result.turn_result is not None
    assert result.turn_result.runtime_mode == "future_task"


def test_tool_planner_and_refinement_use_messages_and_runtime_mode(
    monkeypatch: Any,
) -> None:
    from apeiria.app.ai.pipeline import generation_steps

    selected = selected_model("main")
    refinement_requests: list[Any] = []
    tool_loop_requests: list[Any] = []
    tool_loop_messages: list[tuple[Any, ...]] = []
    tool_definition = AIModelToolDefinition(
        name="memory.query",
        description="Recall memory",
        parameters={"type": "object", "properties": {}},
    )

    async def run_tool_loop(
        request: Any,
        *,
        messages: list[Any],
        tools: tuple[Any, ...],
        selected: AISelectedModel,
        fallback_models: tuple[AISelectedModel, ...],
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
            available_tools=(tool_definition,),
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

    async def select_fallbacks(
        _selected: AISelectedModel,
    ) -> tuple[AISelectedModel, ...]:
        return ()

    async def select_model(*, task_class: str, target: object) -> AISelectedModel:
        del task_class, target
        return selected

    async def append_tool_turns(**_kwargs: object) -> None:
        return None

    async def deliver_reply(
        _request: AIRuntimeReplyRequest,
        _reply_text: str,
    ) -> DeliveryOutcome:
        return DeliveryOutcome(delivered=True)

    monkeypatch.setattr(generation_steps.tool_gateway, "run_tool_loop", run_tool_loop)
    monkeypatch.setattr(generation_steps, "generate_model_turn", generate_model_turn)
    monkeypatch.setattr(
        generation_steps,
        "select_pipeline_fallback_models",
        select_fallbacks,
    )
    monkeypatch.setattr(generation_steps, "select_pipeline_model", select_model)
    monkeypatch.setattr(
        generation_steps,
        "append_tool_observation_turns",
        append_tool_turns,
    )
    monkeypatch.setattr(generation_steps, "record_context_usage", lambda *_, **__: None)
    monkeypatch.setattr(generation_steps, "deliver_generated_reply", deliver_reply)

    identity = ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id=None,
    )
    request = AIRuntimeReplyRequest(
        identity=identity,
        message_text="future task",
        source_message_id=None,
        user_id="user-1",
        sender_id="bot-1",
        runtime_mode="future_task",
    )
    inputs = ReplyInputs(
        turns=[],
        conversation_summary=None,
        relationship_target=object(),
        model_target=AIModelBindingTarget(
            conversation_id="session-1",
            group_id=None,
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(execution_enabled=True),
        persona=None,
        recalled_memories=[],
        relationship_context=None,
        person_profile=(),
        allowed_tools=(),
        initiative_bias=0.0,
    )
    prep = ReplyPreparation(
        skill_runtime=ToolGatewayResult(
            policy_text="allowed: memory.query",
            result_lines=(),
            turns=(),
            available_tools=(tool_definition,),
        ),
        selected=selected,
        skill_activation=None,
        pre_tool_task_class="tool_orchestration",
    )
    social_decision = ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="allow",
        reason_codes=(),
        reason_text="test",
        evidence={},
        decision_source="fallback",
    )

    result = asyncio.run(
        generation_steps._generate_with_tool_loop(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prep=prep,
            current_time=datetime(2026, 4, 28, tzinfo=timezone.utc),
            trace_id="trace-tools",
        )
    )

    assert tool_loop_requests[0].runtime_mode == "future_task"
    assert tool_loop_messages[0]
    assert tool_loop_messages[0][-1].role == "user"
    assert refinement_requests[0].runtime_mode == "future_task"
    assert refinement_requests[0].prompt == ""
    assert refinement_requests[0].messages
    assert refinement_requests[0].messages[-1].role == "user"
    assert result.turn_result is not None
    assert result.turn_result.runtime_mode == "future_task"
    assert result.delivery_result == DeliveryOutcome(delivered=True)
