from __future__ import annotations

import asyncio
from typing import Any

from apeiria.ai.model import AIModelBindingTarget, AISelectedModel
from apeiria.ai.tools import ToolGatewayResult
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
    assert result.turn_result is not None
    assert result.turn_result.runtime_mode == "future_task"
    assert result.delivery_result == DeliveryOutcome(delivered=True)

