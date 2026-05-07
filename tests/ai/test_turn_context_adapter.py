from __future__ import annotations

from datetime import datetime, timezone

from apeiria.ai.model import AIModelBindingTarget, AIModelMessage, AIModelToolDefinition
from apeiria.ai.tools import AIToolPolicy
from apeiria.app.ai.reply_strategy import ReplyStrategyDecision
from apeiria.app.ai.runtime.context.adapter import build_turn_context
from apeiria.app.ai.runtime.context.materials import RuntimeContextInputBundle
from apeiria.app.ai.runtime.live import AIRuntimeTurnRequest
from apeiria.app.ai.runtime.planning.tool_exposure import ToolExposurePlan
from apeiria.app.ai.runtime.session.context import (
    DeliveryTarget,
    RuntimeContextMaterials,
    RuntimeTurnInput,
)
from apeiria.app.ai.runtime.strategy import RuntimeHardRuleDecision
from apeiria.conversation.models import ChatSessionIdentity


def _identity(scene_type: str = "group") -> ChatSessionIdentity:
    return ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type=scene_type,  # type: ignore[arg-type]
        scene_id="scene-1",
        subject_id="user-1",
    )


def _inputs() -> RuntimeContextInputBundle:
    return RuntimeContextInputBundle(
        turns=[],
        conversation_summary="summary",
        relationship_target=object(),  # type: ignore[arg-type]
        model_target=AIModelBindingTarget(
            conversation_id="session-1",
            group_id="scene-1",
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(execution_enabled=True),
        persona=None,
        recalled_memories=[],
        relationship_context="friendly",
        person_profile=("profile",),
        allowed_tools=(),
        initiative_bias=0.2,
    )


def _hard_decision() -> RuntimeHardRuleDecision:
    return RuntimeHardRuleDecision(
        action="continue",
        reason_codes=("direct_signal",),
        reason_text="direct",
        evidence={"direct_signal": True},
        should_observe=True,
        should_reply=True,
    )


def _social_decision() -> ReplyStrategyDecision:
    return ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="allow",
        reason_codes=("social_ok",),
        reason_text="ok",
        evidence={"score": 1.0},
        decision_source="llm",
    )


def test_build_turn_context_freezes_message_turn_runtime_inputs() -> None:
    request = AIRuntimeTurnRequest(
        identity=_identity(),
        message_text="hello",
        source_message_id="msg-1",
        user_id="user-1",
        sender_id="bot-1",
        runtime_mode="message",
        is_tome=True,
        event_dedupe_key="platform_message:msg-1",
        event_dedupe_claimed=True,
    )
    prompt_messages = (
        AIModelMessage(role="system", content="persona"),
        AIModelMessage(role="user", content="hello"),
    )
    tool = AIModelToolDefinition(
        name="memory.query",
        description="Recall memory",
        parameters={"type": "object", "properties": {}},
    )
    tool_plan = ToolExposurePlan(
        awareness_text="tools available",
        selected_tools=(tool,),
        diagnostics={"selected_tool_count": 1},
    )
    delivery = DeliveryTarget(
        session_id="session-1",
        reply_to_message_id="msg-1",
        delivery_channel="message",
    )
    current_time = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)

    context = build_turn_context(
        trace_id="trace-1",
        turn=RuntimeTurnInput.from_turn_request(request),
        context=RuntimeContextMaterials.from_context_input_bundle(_inputs()),
        hard_decision=_hard_decision(),
        social_decision=_social_decision(),
        delivery_target=delivery,
        prompt_messages=prompt_messages,
        tool_exposure_plan=tool_plan,
        current_time=current_time,
    )

    assert context.trace_id == "trace-1"
    assert context.identity == request.identity
    assert context.runtime_mode == "message"
    assert context.source.message_text == "hello"
    assert context.source.source_message_id == "msg-1"
    assert context.source.direct_signal is True
    assert context.source.event_dedupe_key == "platform_message:msg-1"
    assert context.source.event_dedupe_claimed is True
    assert context.delivery_target == delivery
    assert context.current_time == current_time
    assert context.model_target == _inputs().model_target
    assert context.tool_policy == _inputs().tool_policy
    assert context.prompt_messages == prompt_messages
    assert context.tool_exposure_plan == tool_plan
    assert context.hard_rule_decision == _hard_decision()
    assert context.social_decision == _social_decision()


def test_build_turn_context_records_future_task_delivery_target() -> None:
    request = AIRuntimeTurnRequest(
        identity=_identity(scene_type="private"),
        message_text="scheduled",
        source_message_id="future-source-1",
        user_id="user-1",
        sender_id="bot-1",
        runtime_mode="future_task",
    )
    delivery = DeliveryTarget(
        session_id="session-1",
        reply_to_message_id=None,
        delivery_channel="future_task",
    )

    context = build_turn_context(
        trace_id="trace-future",
        turn=RuntimeTurnInput.from_turn_request(request),
        context=RuntimeContextMaterials.from_context_input_bundle(_inputs()),
        hard_decision=_hard_decision(),
        social_decision=_social_decision(),
        delivery_target=delivery,
        prompt_messages=(AIModelMessage(role="user", content="scheduled"),),
        tool_exposure_plan=ToolExposurePlan(),
        current_time=datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc),
    )

    assert context.runtime_mode == "future_task"
    assert context.source.is_private is True
    assert context.delivery_target == delivery
    assert context.delivery_target.delivery_channel == "future_task"
