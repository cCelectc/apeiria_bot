from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from apeiria.ai.model import AIModelBindingTarget
from apeiria.ai.tools import AIToolPolicy
from apeiria.ai.tools.gateway import ToolGatewayResult
from apeiria.app.ai.agent_turn import AgentModelGenerationResult, AgentTurnResult
from apeiria.app.ai.pipeline import generation_steps
from apeiria.app.ai.pipeline import service as service_module
from apeiria.app.ai.pipeline.generation_steps import (
    ReplyGeneration,
    ReplyPreparation,
)
from apeiria.app.ai.pipeline.input_steps import ReplyInputs
from apeiria.app.ai.pipeline.service import (
    AIRuntimeReplyRequest,
    AIRuntimeService,
    AITraceContext,
)
from apeiria.app.ai.reply_strategy import ReplyStrategyDecision, WakeContext
from apeiria.app.ai.session_runtime import (
    AISessionTurnEngine,
    RuntimeTurnPlan,
    TurnContext,
)
from apeiria.conversation.models import ChatSessionIdentity
from tests.ai.agent_turn_helpers import model_response, selected_model


def _request() -> AIRuntimeReplyRequest:
    return AIRuntimeReplyRequest(
        identity=ChatSessionIdentity(
            session_id="session-1",
            platform="test",
            bot_id="bot-1",
            scene_type="group",
            scene_id="scene-1",
            subject_id="user-1",
        ),
        message_text="hello",
        source_message_id="msg-1",
        user_id="user-1",
        sender_id="bot-1",
        runtime_mode="message",
        is_tome=True,
    )


def _wake() -> WakeContext:
    return WakeContext(
        bot_self_id="bot-1",
        user_id="user-1",
        message_text="hello",
        is_tome=True,
        is_private=False,
        is_future_task=False,
        allow_group_initiative=True,
    )


def _inputs() -> ReplyInputs:
    return ReplyInputs(
        turns=[],
        conversation_summary=None,
        relationship_target=object(),  # type: ignore[arg-type]
        model_target=AIModelBindingTarget(
            conversation_id="session-1",
            group_id="scene-1",
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(execution_enabled=False),
        persona=None,
        recalled_memories=[],
        relationship_context=None,
        person_profile=(),
        allowed_tools=(),
        initiative_bias=0.0,
    )


def _social_decision() -> ReplyStrategyDecision:
    return ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="avoid",
        reason_codes=("direct",),
        reason_text="direct",
        evidence={},
        decision_source="llm",
    )


async def _noop_observation_effects(*_args: Any, **_kwargs: Any) -> None:
    return None


def test_reply_pipeline_passes_turn_context_to_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = selected_model("primary")
    runtime_request = _request()
    inputs = _inputs()
    social_decision = _social_decision()
    prep = ReplyPreparation(
        skill_runtime=ToolGatewayResult(
            policy_text="No tools.",
            result_lines=(),
            turns=(),
        ),
        selected=selected,
        skill_activation=None,
        pre_tool_task_class="reply_default",
    )
    captured: dict[str, TurnContext] = {}

    async def gather_reply_inputs(*_args: Any, **_kwargs: Any) -> ReplyInputs:
        return inputs

    async def decide_whether_to_speak(
        *_args: Any,
        **_kwargs: Any,
    ) -> ReplyStrategyDecision:
        return social_decision

    async def prepare_generation(*_args: Any, **_kwargs: Any) -> ReplyPreparation:
        return prep

    async def generate_reply(
        *_args: Any,
        turn_context: TurnContext,
        **_kwargs: Any,
    ) -> ReplyGeneration:
        captured["context"] = turn_context
        return ReplyGeneration(
            response=model_response(selected, "reply"),
            skill_runtime=ToolGatewayResult(
                policy_text="No tools.",
                result_lines=(),
                turns=(),
            ),
            post_tool_task_class=None,
            delivery_result=None,
        )

    async def persist_reply(*_args: Any, **_kwargs: Any) -> None:
        return None

    monkeypatch.setattr(service_module, "gather_reply_inputs", gather_reply_inputs)
    monkeypatch.setattr(
        service_module,
        "decide_whether_to_speak",
        decide_whether_to_speak,
    )
    monkeypatch.setattr(service_module, "prepare_generation", prepare_generation)
    monkeypatch.setattr(service_module, "generate_reply", generate_reply)
    monkeypatch.setattr(service_module, "persist_reply", persist_reply)
    monkeypatch.setattr(
        service_module,
        "apply_reply_observation_effects",
        _noop_observation_effects,
    )
    monkeypatch.setattr(
        service_module,
        "reply_strategy_service",
        SimpleNamespace(notify_replied=lambda _session_id: None),
    )

    result = asyncio.run(
        AIRuntimeService()._run_reply_pipeline(
            trace_id="trace-1",
            trace=AITraceContext(kind="test", trigger="unit"),
            request=runtime_request,
            wake_context=_wake(),
        )
    )

    assert result is not None
    assert result.reply_text == "reply"
    context = captured["context"]
    assert context.trace_id == "trace-1"
    assert context.identity.session_id == "session-1"
    assert context.delivery_target.session_id == "session-1"
    assert context.delivery_target.reply_to_message_id == "msg-1"
    assert context.delivery_target.delivery_channel == "message"
    expected_messages = generation_steps.build_initial_reply_prompt_messages(
        request=runtime_request,
        inputs=inputs,
        social_decision=social_decision,
        prep=prep,
    )
    assert context.prompt_messages == expected_messages
    assert context.prompt_diagnostics == (
        generation_steps.build_initial_reply_prompt_diagnostics(
            request=runtime_request,
            inputs=inputs,
            social_decision=social_decision,
            prep=prep,
        )
    )
    assert context.tool_exposure_plan.selected_tools == ()
    assert context.hard_rule_decision is not None
    assert context.social_decision == social_decision


def test_reply_pipeline_persists_runner_turn_result(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = selected_model("runner")
    captured: dict[str, AgentTurnResult | None] = {}

    async def gather_reply_inputs(*_args: Any, **_kwargs: Any) -> ReplyInputs:
        return _inputs()

    async def decide_whether_to_speak(
        *_args: Any,
        **_kwargs: Any,
    ) -> ReplyStrategyDecision:
        return _social_decision()

    async def prepare_generation(*_args: Any, **_kwargs: Any) -> ReplyPreparation:
        return ReplyPreparation(
            skill_runtime=ToolGatewayResult(
                policy_text="No tools.",
                result_lines=(),
                turns=(),
            ),
            selected=selected,
            skill_activation=None,
            pre_tool_task_class="reply_default",
        )

    async def generate_model_turn(request: Any) -> AgentModelGenerationResult:
        response = model_response(selected, "runner reply")
        return AgentModelGenerationResult(
            response=response,
            selected=selected,
            turn=AgentTurnResult(
                trace_id=request.trace_id,
                runtime_mode=request.runtime_mode,
                status="completed",
                finish_reason="runner_direct_completed",
                response=response,
                response_source=request.response_source,
                metadata={"runner": "direct"},
            ),
        )

    async def select_fallbacks(_selected: Any) -> tuple[Any, ...]:
        return ()

    async def deliver_generated_reply(*_args: Any, **_kwargs: Any) -> None:
        return None

    async def persist_reply(*_args: Any, gen: ReplyGeneration, **_kwargs: Any) -> None:
        captured["turn_result"] = gen.turn_result

    monkeypatch.setattr(service_module, "gather_reply_inputs", gather_reply_inputs)
    monkeypatch.setattr(
        service_module,
        "decide_whether_to_speak",
        decide_whether_to_speak,
    )
    monkeypatch.setattr(service_module, "prepare_generation", prepare_generation)
    monkeypatch.setattr(service_module, "persist_reply", persist_reply)
    monkeypatch.setattr(
        service_module,
        "apply_reply_observation_effects",
        _noop_observation_effects,
    )
    monkeypatch.setattr(generation_steps, "generate_model_turn", generate_model_turn)
    monkeypatch.setattr(
        generation_steps,
        "select_pipeline_fallback_models",
        select_fallbacks,
    )
    monkeypatch.setattr(generation_steps, "record_context_usage", lambda *_, **__: None)
    monkeypatch.setattr(
        generation_steps,
        "deliver_generated_reply",
        deliver_generated_reply,
    )
    monkeypatch.setattr(
        service_module,
        "reply_strategy_service",
        SimpleNamespace(notify_replied=lambda _session_id: None),
    )

    result = asyncio.run(
        AIRuntimeService()._run_reply_pipeline(
            trace_id="trace-1",
            trace=AITraceContext(kind="test", trigger="unit"),
            request=_request(),
            wake_context=_wake(),
        )
    )

    assert result is not None
    assert result.reply_text == "runner reply"
    turn_result = captured["turn_result"]
    assert turn_result is not None
    assert turn_result.finish_reason == "runner_direct_completed"
    assert turn_result.metadata["runner"] == "direct"
    assert "prompt_diagnostics" in turn_result.metadata


def test_turn_engine_passes_runtime_plan_through_execution_and_commit() -> None:
    selected = selected_model("engine")
    inputs = _inputs()
    social_decision = _social_decision()
    skill_runtime = ToolGatewayResult(
        policy_text="No tools.",
        result_lines=(),
        turns=(),
    )
    prep = ReplyPreparation(
        skill_runtime=skill_runtime,
        selected=selected,
        skill_activation=None,
        pre_tool_task_class="reply_default",
    )
    order: list[str] = []
    captured_plan: dict[str, RuntimeTurnPlan] = {}

    async def gather_reply_inputs(*_args: Any, **_kwargs: Any) -> ReplyInputs:
        order.append("context")
        return inputs

    async def decide_whether_to_speak(
        *_args: Any,
        **_kwargs: Any,
    ) -> ReplyStrategyDecision:
        order.append("social")
        return social_decision

    async def prepare_generation(*_args: Any, **_kwargs: Any) -> ReplyPreparation:
        order.append("planning")
        return prep

    async def generate_reply(
        *_args: Any,
        prep: RuntimeTurnPlan,
        turn_context: TurnContext,
        turn_plan: RuntimeTurnPlan,
        **_kwargs: Any,
    ) -> ReplyGeneration:
        order.append("execution")
        assert prep is turn_plan
        assert turn_context.prompt_messages == turn_plan.prompt_messages
        captured_plan["plan"] = turn_plan
        return ReplyGeneration(
            response=model_response(selected, "engine reply"),
            skill_runtime=skill_runtime,
            post_tool_task_class=None,
            delivery_result=None,
        )

    async def persist_reply(
        *_args: Any,
        prep: RuntimeTurnPlan,
        gen: Any,
        **_kwargs: Any,
    ) -> None:
        order.append("commit")
        assert prep is captured_plan["plan"]
        assert gen.stage == "execution"

    engine = AISessionTurnEngine(
        gather_reply_inputs=gather_reply_inputs,
        decide_whether_to_speak=decide_whether_to_speak,
        prepare_generation=prepare_generation,
        generate_reply=generate_reply,
        persist_reply=persist_reply,
        reply_strategy_service=SimpleNamespace(notify_replied=lambda _session_id: None),
    )

    commit = asyncio.run(
        engine.run_reply_turn(
            trace_id="trace-engine",
            trace=AITraceContext(kind="test", trigger="unit"),
            request=_request(),
            wake_context=_wake(),
            current_time=datetime(2026, 4, 28, tzinfo=timezone.utc),
            session_runtime=None,
        )
    )

    assert order == ["context", "social", "planning", "execution", "commit"]
    assert commit is not None
    assert commit.reply_text == "engine reply"


def test_turn_engine_applies_observation_effects_before_context() -> None:
    selected = selected_model("engine")
    inputs = _inputs()
    social_decision = _social_decision()
    skill_runtime = ToolGatewayResult(
        policy_text="No tools.",
        result_lines=(),
        turns=(),
    )
    prep = ReplyPreparation(
        skill_runtime=skill_runtime,
        selected=selected,
        skill_activation=None,
        pre_tool_task_class="reply_default",
    )
    order: list[str] = []

    async def apply_observation_effects(*_args: Any, **_kwargs: Any) -> None:
        order.append("observation")

    async def gather_reply_inputs(*_args: Any, **_kwargs: Any) -> ReplyInputs:
        order.append("context")
        return inputs

    async def decide_whether_to_speak(
        *_args: Any,
        **_kwargs: Any,
    ) -> ReplyStrategyDecision:
        order.append("social")
        return social_decision

    async def prepare_generation(*_args: Any, **_kwargs: Any) -> ReplyPreparation:
        order.append("planning")
        return prep

    async def generate_reply(*_args: Any, **_kwargs: Any) -> ReplyGeneration:
        order.append("execution")
        return ReplyGeneration(
            response=model_response(selected, "engine reply"),
            skill_runtime=skill_runtime,
            post_tool_task_class=None,
            delivery_result=None,
        )

    async def persist_reply(*_args: Any, **_kwargs: Any) -> None:
        order.append("commit")

    engine = AISessionTurnEngine(
        gather_reply_inputs=gather_reply_inputs,
        decide_whether_to_speak=decide_whether_to_speak,
        prepare_generation=prepare_generation,
        generate_reply=generate_reply,
        persist_reply=persist_reply,
        reply_strategy_service=SimpleNamespace(notify_replied=lambda _session_id: None),
        apply_observation_effects=apply_observation_effects,
    )

    commit = asyncio.run(
        engine.run_reply_turn(
            trace_id="trace-engine",
            trace=AITraceContext(kind="test", trigger="unit"),
            request=_request(),
            wake_context=_wake(),
            current_time=datetime(2026, 4, 28, tzinfo=timezone.utc),
            session_runtime=None,
        )
    )

    assert order == [
        "observation",
        "context",
        "social",
        "planning",
        "execution",
        "commit",
    ]
    assert commit is not None


@pytest.mark.parametrize("tool_count", [0, 1])
def test_turn_planning_is_side_effect_free_and_matches_prompt_messages(
    tool_count: int,
) -> None:
    selected = selected_model("planning")
    has_tools = tool_count > 0
    tool = SimpleNamespace(
        name="memory.query",
        description="Recall memory",
        parameters={"type": "object", "properties": {}},
    )
    skill_runtime = ToolGatewayResult(
        policy_text="Tool policy.",
        result_lines=(),
        turns=(),
        available_tools=(tool,) if has_tools else (),  # type: ignore[arg-type]
    )
    prep = ReplyPreparation(
        skill_runtime=skill_runtime,
        selected=selected,
        skill_activation="Skill active.",
        pre_tool_task_class="tool_orchestration" if has_tools else "reply_default",
    )
    calls: list[str] = []

    async def prepare_generation(*_args: Any, **_kwargs: Any) -> ReplyPreparation:
        calls.append("planning")
        return prep

    async def fail_later_stage(*_args: Any, **_kwargs: Any) -> None:
        raise AssertionError("planning must not execute or persist")  # noqa: TRY003

    engine = AISessionTurnEngine(
        gather_reply_inputs=fail_later_stage,
        decide_whether_to_speak=fail_later_stage,
        prepare_generation=prepare_generation,
        generate_reply=fail_later_stage,
        persist_reply=fail_later_stage,
        reply_strategy_service=SimpleNamespace(notify_replied=lambda _session_id: None),
    )

    inputs = _inputs()
    social_decision = _social_decision()
    plan = asyncio.run(
        engine.plan_turn(
            trace_id="trace-plan",
            request=_request(),
            inputs=inputs,
            social_decision=social_decision,
            current_time=datetime(2026, 4, 28, tzinfo=timezone.utc),
        )
    )

    assert calls == ["planning"]
    assert plan is not None
    assert plan.prompt_messages == generation_steps.build_initial_reply_prompt_messages(
        request=_request(),
        inputs=inputs,
        social_decision=social_decision,
        prep=prep,
    )
    assert plan.prompt_diagnostics == (
        generation_steps.build_initial_reply_prompt_diagnostics(
            request=_request(),
            inputs=inputs,
            social_decision=social_decision,
            prep=prep,
        )
    )
