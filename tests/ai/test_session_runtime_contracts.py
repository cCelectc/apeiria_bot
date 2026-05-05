from __future__ import annotations

import inspect
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

import pytest

from apeiria.ai.model import AIModelBindingTarget, AIModelMessage, AIModelToolDefinition
from apeiria.ai.tools import AIToolPolicy
from apeiria.ai.turn_records import ModelAttempt, PromptSafeObservation, ToolAttempt
from apeiria.app.ai.agent_turn import AgentTurnResult
from apeiria.app.ai.session_runtime import (
    MAX_HARD_RULE_EVIDENCE_ITEMS,
    AgentRunner,
    AISessionRuntime,
    DeliveryTarget,
    MergeMetadata,
    RuntimeCommitResult,
    RuntimeContextBundle,
    RuntimeExecutionOutcome,
    RuntimeHardRuleAction,
    RuntimeHardRuleDecision,
    RuntimeHardRuleReasonCode,
    RuntimePolicyOutcome,
    RuntimeStageName,
    RuntimeTraceOutcome,
    RuntimeTurnPlan,
    RuntimeTurnSource,
    ToolExposurePlan,
    TurnContext,
    TurnTrace,
)
from apeiria.conversation.models import ChatSessionIdentity


def _identity() -> ChatSessionIdentity:
    return ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="group",
        scene_id="group-1",
        subject_id="user-1",
    )


def test_turn_context_is_frozen_and_provider_neutral() -> None:
    context = TurnContext(
        trace_id="trace-1",
        identity=_identity(),
        source=RuntimeTurnSource(
            runtime_mode="message",
            message_text="hello",
            source_message_id="msg-1",
            user_id="user-1",
            direct_signal=True,
            is_private=False,
        ),
        delivery_target=DeliveryTarget(
            session_id="session-1",
            reply_to_message_id="msg-1",
        ),
        current_time=datetime(2026, 4, 28, tzinfo=timezone.utc),
        model_target=AIModelBindingTarget(
            conversation_id="session-1",
            group_id="group-1",
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(execution_enabled=True),
        prompt_messages=(AIModelMessage(role="user", content="hello"),),
        merge=MergeMetadata(
            merged_message_ids=("msg-1", "msg-2"),
            merged_message_count=2,
            reason="ambient_merge_window",
        ),
    )

    assert context.session_id == "session-1"
    assert context.runtime_mode == "message"
    assert context.source.direct_signal is True
    assert context.prompt_messages[0].role == "user"

    with pytest.raises(FrozenInstanceError):
        context.trace_id = "mutated"  # type: ignore[misc]


def test_runtime_stage_contracts_are_explicit_and_provider_neutral() -> None:
    assert RuntimeStageName.__args__ == (
        "ingress",
        "policy",
        "context",
        "planning",
        "execution",
        "commit",
        "trace",
    )

    source = RuntimeTurnSource(
        runtime_mode="message",
        message_text="hello",
        source_message_id="msg-1",
        user_id="user-1",
        direct_signal=True,
    )
    decision = RuntimeHardRuleDecision(
        action="continue",
        reason_codes=("direct_signal",),
        reason_text="direct",
        evidence={"direct_signal": True},
        should_observe=True,
        should_reply=True,
    )
    policy = RuntimePolicyOutcome(
        stage="policy",
        source=source,
        decision=decision,
    )

    assert policy.should_continue is True
    assert policy.source.runtime_mode == "message"
    assert "nonebot" not in repr(policy).lower()


def test_runtime_plan_and_outcome_contracts_do_not_need_platform_events() -> None:
    selected = object()
    skill_runtime = object()
    plan = RuntimeTurnPlan(
        stage="planning",
        selected=selected,  # type: ignore[arg-type]
        fallback_models=(),
        skill_runtime=skill_runtime,  # type: ignore[arg-type]
        skill_activation=None,
        pre_tool_task_class="reply_default",
        prompt_messages=(AIModelMessage(role="user", content="hello"),),
        prompt_diagnostics={"prompt_purpose": "reply_final"},
        tool_exposure_plan=ToolExposurePlan(),
    )
    context_bundle = RuntimeContextBundle(
        stage="context",
        inputs=object(),  # type: ignore[arg-type]
        diagnostics={"source": "test"},
    )
    execution = RuntimeExecutionOutcome(
        stage="execution",
        response=None,
        skill_runtime=skill_runtime,  # type: ignore[arg-type]
        post_tool_task_class=None,
        delivery_result=None,
    )
    commit = RuntimeCommitResult(
        stage="commit",
        reply_text="hello",
        delivery_result=None,
    )
    trace = RuntimeTraceOutcome(
        stage="trace",
        trace=TurnTrace(
            trace_id="trace-1",
            session_id="session-1",
            runtime_mode="message",
            strategy_action="continue",
            strategy_reason_codes=("direct_signal",),
        ),
    )

    assert plan.selected is selected
    assert plan.has_executable_tools is False
    assert context_bundle.diagnostics["source"] == "test"
    assert execution.response is None
    assert commit.reply_text == "hello"
    assert trace.trace.to_metadata()["trace_id"] == "trace-1"


def test_hard_rule_decision_vocabulary_and_observe_reply_split() -> None:
    assert RuntimeHardRuleAction.__args__ == (
        "drop",
        "observe",
        "merge",
        "wait",
        "defer",
        "continue",
    )

    decision = RuntimeHardRuleDecision(
        action="observe",
        reason_codes=("ambient_weak_relevance",),
        reason_text="Ambient context is retained but does not need a reply.",
        evidence={"session_id": "session-1", "direct_signal": False},
        should_observe=True,
        should_reply=False,
    )

    assert decision.action == "observe"
    assert decision.should_observe is True
    assert decision.should_reply is False
    assert decision.reason_codes == ("ambient_weak_relevance",)


def test_hard_rule_reason_codes_are_stable_and_evidence_is_bounded() -> None:
    assert RuntimeHardRuleReasonCode.__args__ == (
        "duplicate_event",
        "bot_self_message",
        "empty_input",
        "initiative_disabled",
        "direct_signal",
        "private_message",
        "future_task",
        "ambient_candidate",
        "ambient_merge_window",
        "session_busy",
        "ambient_cooldown",
        "ambient_weak_relevance",
        "policy_denied",
    )

    decision = RuntimeHardRuleDecision(
        action="drop",
        reason_codes=("duplicate_event",),
        reason_text="Duplicate event was ignored.",
        evidence={f"key_{index}": index for index in range(20)},
        should_observe=False,
        should_reply=False,
    )

    assert len(decision.evidence) == MAX_HARD_RULE_EVIDENCE_ITEMS
    assert list(decision.evidence) == [
        f"key_{index}" for index in range(MAX_HARD_RULE_EVIDENCE_ITEMS)
    ]


def test_tool_exposure_plan_splits_awareness_from_executable_tools() -> None:
    executable = AIModelToolDefinition(
        name="memory.query",
        description="Recall relevant memories",
        parameters={"type": "object", "properties": {}},
    )

    plan = ToolExposurePlan(
        awareness_text="External capabilities may be available when selected.",
        category_ids=("memory", "future_task", "relationship", "plugin_capability"),
        selected_tools=(executable,),
        hidden_reasons={"admin.project": "excluded_from_ambient_group"},
        unavailable_reasons={"future_task.create": "provider_disabled"},
        denied_reasons={"memory.update": "policy_denied"},
        diagnostics={"policy": "ambient_group_default"},
    )

    assert "memory.query" not in plan.awareness_text
    assert plan.selected_tool_names == ("memory.query",)
    assert plan.has_executable_tools is True
    assert plan.hidden_reasons["admin.project"] == "excluded_from_ambient_group"
    assert plan.unavailable_reasons["future_task.create"] == "provider_disabled"
    assert plan.denied_reasons["memory.update"] == "policy_denied"


def test_agent_runner_protocol_owns_turn_execution() -> None:
    class _Runner:
        async def run_turn(
            self,
            context: TurnContext,
            plan: RuntimeTurnPlan,
        ) -> RuntimeExecutionOutcome:
            return RuntimeExecutionOutcome(
                stage="execution",
                response=None,
                skill_runtime=plan.skill_runtime,
                post_tool_task_class=None,
                delivery_result=None,
                turn_result=AgentTurnResult.skipped(
                    trace_id=context.trace_id,
                    runtime_mode=context.runtime_mode,
                    finish_reason="contract_test",
                ),
            )

    runner = _Runner()

    assert isinstance(runner, AgentRunner)


def test_session_runtime_protocol_coordinates_context_and_runner() -> None:
    class _Runtime:
        session_id = "session-1"

        async def run_turn(
            self,
            context: TurnContext,
            plan: RuntimeTurnPlan,
        ) -> RuntimeExecutionOutcome:
            return RuntimeExecutionOutcome(
                stage="execution",
                response=None,
                skill_runtime=plan.skill_runtime,
                post_tool_task_class=None,
                delivery_result=None,
                turn_result=AgentTurnResult.skipped(
                    trace_id=context.trace_id,
                    runtime_mode=context.runtime_mode,
                    finish_reason="contract_test",
                ),
            )

    runtime = _Runtime()

    assert isinstance(runtime, AISessionRuntime)


def test_turn_trace_projects_provider_neutral_attempts() -> None:
    trace = TurnTrace(
        trace_id="trace-1",
        session_id="session-1",
        runtime_mode="message",
        strategy_action="continue",
        strategy_reason_codes=("direct_signal",),
        merge_reason="ambient_merge_window",
        wait_reason="collect_more_context",
        defer_reason="session_busy",
        model_attempts=(
            ModelAttempt(
                attempt_index=1,
                model_ref="source:gpt",
                status="success",
                response_source="direct",
            ),
        ),
        tool_attempts=(
            ToolAttempt(
                tool_call_id="call-1",
                tool_name="memory.query",
                status="success",
                arguments_summary="query_text=hello",
                observation=PromptSafeObservation(content="found memory"),
            ),
        ),
        final_response_source="direct",
        delivery_status="not_required",
    )

    projection = trace.to_metadata()

    assert projection == {
        "trace_id": "trace-1",
        "session_id": "session-1",
        "runtime_mode": "message",
        "strategy_action": "continue",
        "strategy_reason_codes": ["direct_signal"],
        "merged_message_count": 0,
        "merge_reason": "ambient_merge_window",
        "wait_reason": "collect_more_context",
        "defer_reason": "session_busy",
        "model_attempt_count": 1,
        "tool_attempt_count": 1,
        "tool_observation_count": 1,
        "final_response_source": "direct",
        "skip_reason": None,
        "delivery_status": "not_required",
    }


def test_protocol_methods_are_awaitable() -> None:
    class _Runner:
        async def run_turn(
            self,
            context: TurnContext,
            plan: RuntimeTurnPlan,
        ) -> RuntimeExecutionOutcome:
            return RuntimeExecutionOutcome(
                stage="execution",
                response=None,
                skill_runtime=plan.skill_runtime,
                post_tool_task_class=None,
                delivery_result=None,
                turn_result=AgentTurnResult.skipped(
                    trace_id=context.trace_id,
                    runtime_mode=context.runtime_mode,
                    finish_reason="contract_test",
                ),
            )

    assert inspect.iscoroutinefunction(_Runner().run_turn)
