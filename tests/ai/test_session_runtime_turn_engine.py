from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

import pytest

from apeiria.ai.model import AIModelBindingTarget, AIModelMessage
from apeiria.ai.tools import AIToolPolicy
from apeiria.ai.tools.gateway import ToolGatewayResult
from apeiria.app.ai.agent_turn import AgentTurnResult
from apeiria.app.ai.pipeline.input_steps import ReplyInputs
from apeiria.app.ai.pipeline.service import (
    AIRuntimeReplyRequest,
    AIRuntimeService,
    AITraceContext,
)
from apeiria.app.ai.reply_strategy import ReplyStrategyDecision, WakeContext
from apeiria.app.ai.session_runtime import (
    AISessionTurnEngine,
    DefaultRuntimeCommitStage,
    DefaultRuntimeContextStage,
    DefaultRuntimeExecutionStage,
    DefaultRuntimeObservationStage,
    DefaultRuntimePlanningStage,
    DefaultRuntimePolicyStage,
    DefaultRuntimeTraceStage,
    RuntimeExecutionOutcome,
    RuntimeTurnPlan,
    ToolExposurePlan,
    TurnContext,
)
from apeiria.app.ai.session_runtime import engine as engine_module
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


class _ReplyPersistenceStage:
    def __init__(self, persist_reply: Any | None = None) -> None:
        self._persist_reply = persist_reply

    async def persist_tool_observations(
        self,
        **_: Any,
    ) -> str:
        return "not_required"

    async def persist_assistant_message(
        self,
        *,
        plan: RuntimeTurnPlan,
        generation: Any,
        **kwargs: Any,
    ) -> None:
        if self._persist_reply is None:
            return
        await self._persist_reply(plan=plan, gen=generation, **kwargs)

    async def rebuild_context_window(self, **_: Any) -> None:
        return None


def _engine_from_stages(
    *,
    gather_reply_inputs: Any,
    decide_whether_to_speak: Any,
    prepare_generation: Any,
    apply_observation_effects: Any | None = None,
) -> AISessionTurnEngine:
    return AISessionTurnEngine(
        policy_stage=DefaultRuntimePolicyStage(decide_whether_to_speak),
        observation_stage=DefaultRuntimeObservationStage(apply_observation_effects),
        context_stage=DefaultRuntimeContextStage(gather_reply_inputs),
        planning_stage=DefaultRuntimePlanningStage(prepare_generation),
        execution_stage=DefaultRuntimeExecutionStage(),
        commit_stage=DefaultRuntimeCommitStage(
            reply_persistence=_ReplyPersistenceStage(),
            reply_strategy_service=SimpleNamespace(
                notify_replied=lambda _session_id: None
            ),
        ),
        trace_stage=DefaultRuntimeTraceStage(),
    )


def _service_from_stages(
    *,
    gather_reply_inputs: Any,
    decide_whether_to_speak: Any,
    prepare_generation: Any,
    persist_reply: Any | None = None,
) -> AIRuntimeService:
    engine = _engine_from_stages(
        gather_reply_inputs=gather_reply_inputs,
        decide_whether_to_speak=decide_whether_to_speak,
        prepare_generation=prepare_generation,
        apply_observation_effects=_noop_observation_effects,
    )
    return AIRuntimeService(
        turn_engine=AISessionTurnEngine(
            policy_stage=engine.policy_stage,
            observation_stage=engine.observation_stage,
            context_stage=engine.context_stage,
            planning_stage=engine.planning_stage,
            execution_stage=engine.execution_stage,
            commit_stage=DefaultRuntimeCommitStage(
                reply_persistence=_ReplyPersistenceStage(persist_reply),
                reply_strategy_service=SimpleNamespace(
                    notify_replied=lambda _session_id: None
                ),
            ),
            trace_stage=engine.trace_stage,
        )
    )


def test_reply_pipeline_passes_turn_context_to_generation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = selected_model("primary")
    runtime_request = _request()
    inputs = _inputs()
    social_decision = _social_decision()
    plan = RuntimeTurnPlan(
        stage="planning",
        selected=selected,
        fallback_models=(),
        skill_runtime=ToolGatewayResult(
            policy_text="No tools.",
            result_lines=(),
            turns=(),
        ),
        skill_activation=None,
        pre_tool_task_class="reply_default",
        prompt_messages=(AIModelMessage(role="user", content="hello"),),
        prompt_diagnostics={"prompt_purpose": "reply_final"},
        tool_exposure_plan=ToolExposurePlan(),
        reply_compose_input=None,
        tool_mode="avoid",
    )
    captured: dict[str, TurnContext] = {}
    expected_plan = plan

    async def gather_reply_inputs(*_args: Any, **_kwargs: Any) -> ReplyInputs:
        return inputs

    async def decide_whether_to_speak(
        *_args: Any,
        **_kwargs: Any,
    ) -> ReplyStrategyDecision:
        return social_decision

    async def prepare_generation(*_args: Any, **_kwargs: Any) -> RuntimeTurnPlan:
        return plan

    async def execute_runtime_turn(
        *,
        turn_context: TurnContext,
        plan: RuntimeTurnPlan,
    ) -> Any:
        captured["context"] = turn_context
        assert plan is expected_plan
        return RuntimeExecutionOutcome(
            stage="execution",
            response=model_response(selected, "reply"),
            skill_runtime=ToolGatewayResult(
                policy_text="No tools.",
                result_lines=(),
                turns=(),
            ),
            post_tool_task_class=None,
            delivery_result=None,
            turn_result=AgentTurnResult(
                trace_id=turn_context.trace_id,
                runtime_mode=turn_context.runtime_mode,
                status="completed",
                finish_reason="direct_model_completed",
                response=model_response(selected, "reply"),
                response_source="direct",
            ),
        )

    monkeypatch.setattr(
        engine_module,
        "execute_runtime_turn",
        execute_runtime_turn,
    )

    async def persist_reply(*_args: Any, **_kwargs: Any) -> None:
        return None

    service = _service_from_stages(
        gather_reply_inputs=gather_reply_inputs,
        decide_whether_to_speak=decide_whether_to_speak,
        prepare_generation=prepare_generation,
        persist_reply=persist_reply,
    )

    result = asyncio.run(
        service._run_reply_pipeline(
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
    assert context.prompt_messages == plan.prompt_messages
    assert context.prompt_diagnostics == plan.prompt_diagnostics
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

    async def prepare_generation(*_args: Any, **_kwargs: Any) -> RuntimeTurnPlan:
        return RuntimeTurnPlan(
            stage="planning",
            selected=selected,
            fallback_models=(),
            skill_runtime=ToolGatewayResult(
                policy_text="No tools.",
                result_lines=(),
                turns=(),
            ),
            skill_activation=None,
            pre_tool_task_class="reply_default",
            prompt_messages=(AIModelMessage(role="user", content="hello"),),
            prompt_diagnostics={},
            tool_exposure_plan=ToolExposurePlan(),
        )

    async def execute_runtime_turn(
        *,
        turn_context: TurnContext,
        plan: RuntimeTurnPlan,
    ) -> Any:
        del plan
        return RuntimeExecutionOutcome(
            stage="execution",
            response=model_response(selected, "runner reply"),
            skill_runtime=ToolGatewayResult(
                policy_text="No tools.",
                result_lines=(),
                turns=(),
            ),
            post_tool_task_class=None,
            delivery_result=None,
            turn_result=AgentTurnResult(
                trace_id=turn_context.trace_id,
                runtime_mode=turn_context.runtime_mode,
                status="completed",
                finish_reason="runner_direct_completed",
                response=model_response(selected, "runner reply"),
                response_source="direct",
                metadata={
                    "runner": "direct",
                    "prompt_diagnostics": turn_context.prompt_diagnostics,
                },
            ),
        )

    async def persist_reply(*_args: Any, gen: Any, **_kwargs: Any) -> None:
        captured["turn_result"] = gen.turn_result

    monkeypatch.setattr(
        engine_module,
        "execute_runtime_turn",
        execute_runtime_turn,
    )
    service = _service_from_stages(
        gather_reply_inputs=gather_reply_inputs,
        decide_whether_to_speak=decide_whether_to_speak,
        prepare_generation=prepare_generation,
        persist_reply=persist_reply,
    )

    result = asyncio.run(
        service._run_reply_pipeline(
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


def test_turn_engine_passes_runtime_plan_through_execution_and_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = selected_model("engine")
    inputs = _inputs()
    social_decision = _social_decision()
    skill_runtime = ToolGatewayResult(
        policy_text="No tools.",
        result_lines=(),
        turns=(),
    )
    plan = RuntimeTurnPlan(
        stage="planning",
        selected=selected,
        fallback_models=(),
        skill_runtime=skill_runtime,
        skill_activation=None,
        pre_tool_task_class="reply_default",
        prompt_messages=(AIModelMessage(role="user", content="hello"),),
        prompt_diagnostics={},
        tool_exposure_plan=ToolExposurePlan(),
    )
    order: list[str] = []
    expected_plan = plan

    async def gather_reply_inputs(*_args: Any, **_kwargs: Any) -> ReplyInputs:
        order.append("context")
        return inputs

    async def decide_whether_to_speak(
        *_args: Any,
        **_kwargs: Any,
    ) -> ReplyStrategyDecision:
        order.append("social")
        return social_decision

    async def prepare_generation(*_args: Any, **_kwargs: Any) -> RuntimeTurnPlan:
        order.append("planning")
        return plan

    async def execute_runtime_turn(
        *,
        turn_context: TurnContext,
        plan: RuntimeTurnPlan,
    ) -> Any:
        order.append("execution")
        assert turn_context.prompt_messages == plan.prompt_messages
        return RuntimeExecutionOutcome(
            stage="execution",
            response=model_response(selected, "engine reply"),
            skill_runtime=skill_runtime,
            post_tool_task_class=None,
            delivery_result=None,
            turn_result=AgentTurnResult(
                trace_id=turn_context.trace_id,
                runtime_mode=turn_context.runtime_mode,
                status="completed",
                finish_reason="engine_direct_completed",
                response=model_response(selected, "engine reply"),
                response_source="direct",
            ),
        )

    async def persist_reply(
        *_args: Any,
        plan: RuntimeTurnPlan,
        gen: Any,
        **_kwargs: Any,
    ) -> None:
        order.append("commit")
        assert plan is expected_plan
        assert gen.stage == "execution"

    monkeypatch.setattr(
        engine_module,
        "execute_runtime_turn",
        execute_runtime_turn,
    )
    engine = _engine_from_stages(
        gather_reply_inputs=gather_reply_inputs,
        decide_whether_to_speak=decide_whether_to_speak,
        prepare_generation=prepare_generation,
    )
    engine = engine.__class__(
        policy_stage=engine.policy_stage,
        observation_stage=engine.observation_stage,
        context_stage=engine.context_stage,
        planning_stage=engine.planning_stage,
        execution_stage=engine.execution_stage,
        commit_stage=DefaultRuntimeCommitStage(
            reply_persistence=_ReplyPersistenceStage(persist_reply),
            reply_strategy_service=SimpleNamespace(
                notify_replied=lambda _session_id: None
            ),
        ),
        trace_stage=engine.trace_stage,
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


def test_turn_engine_applies_observation_effects_before_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    selected = selected_model("engine")
    inputs = _inputs()
    social_decision = _social_decision()
    skill_runtime = ToolGatewayResult(
        policy_text="No tools.",
        result_lines=(),
        turns=(),
    )
    plan = RuntimeTurnPlan(
        stage="planning",
        selected=selected,
        fallback_models=(),
        skill_runtime=skill_runtime,
        skill_activation=None,
        pre_tool_task_class="reply_default",
        prompt_messages=(AIModelMessage(role="user", content="hello"),),
        prompt_diagnostics={},
        tool_exposure_plan=ToolExposurePlan(),
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

    async def prepare_generation(*_args: Any, **_kwargs: Any) -> RuntimeTurnPlan:
        order.append("planning")
        return plan

    async def execute_runtime_turn(
        *,
        turn_context: TurnContext,
        plan: RuntimeTurnPlan,
    ) -> Any:
        del plan
        order.append("execution")
        return RuntimeExecutionOutcome(
            stage="execution",
            response=model_response(selected, "engine reply"),
            skill_runtime=skill_runtime,
            post_tool_task_class=None,
            delivery_result=None,
            turn_result=AgentTurnResult(
                trace_id=turn_context.trace_id,
                runtime_mode=turn_context.runtime_mode,
                status="completed",
                finish_reason="engine_direct_completed",
                response=model_response(selected, "engine reply"),
                response_source="direct",
            ),
        )

    async def persist_reply(*_args: Any, **_kwargs: Any) -> None:
        order.append("commit")

    monkeypatch.setattr(
        engine_module,
        "execute_runtime_turn",
        execute_runtime_turn,
    )
    engine = AISessionTurnEngine(
        policy_stage=DefaultRuntimePolicyStage(decide_whether_to_speak),
        observation_stage=DefaultRuntimeObservationStage(apply_observation_effects),
        context_stage=DefaultRuntimeContextStage(gather_reply_inputs),
        planning_stage=DefaultRuntimePlanningStage(prepare_generation),
        execution_stage=DefaultRuntimeExecutionStage(),
        commit_stage=DefaultRuntimeCommitStage(
            reply_persistence=_ReplyPersistenceStage(persist_reply),
            reply_strategy_service=SimpleNamespace(
                notify_replied=lambda _session_id: None
            ),
        ),
        trace_stage=DefaultRuntimeTraceStage(),
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
    plan = RuntimeTurnPlan(
        stage="planning",
        selected=selected,
        fallback_models=(),
        skill_runtime=skill_runtime,
        skill_activation="Skill active.",
        pre_tool_task_class="tool_orchestration" if has_tools else "reply_default",
        prompt_messages=(AIModelMessage(role="user", content="hello"),),
        prompt_diagnostics={"prompt_purpose": "reply_final"},
        tool_exposure_plan=ToolExposurePlan(
            selected_tools=(tool,) if has_tools else (),  # type: ignore[arg-type]
        ),
    )
    calls: list[str] = []

    async def prepare_generation(*_args: Any, **_kwargs: Any) -> RuntimeTurnPlan:
        calls.append("planning")
        return plan

    engine = AISessionTurnEngine(
        planning_stage=DefaultRuntimePlanningStage(prepare_generation),
    )

    inputs = _inputs()
    social_decision = _social_decision()
    result = asyncio.run(
        engine.plan_turn(
            trace_id="trace-plan",
            request=_request(),
            inputs=inputs,
            social_decision=social_decision,
            current_time=datetime(2026, 4, 28, tzinfo=timezone.utc),
        )
    )

    assert calls == ["planning"]
    assert result is not None
    assert result.prompt_messages == plan.prompt_messages
    assert result.prompt_diagnostics == plan.prompt_diagnostics
