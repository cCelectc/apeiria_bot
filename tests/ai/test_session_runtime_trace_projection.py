from __future__ import annotations

from apeiria.ai.turn_records import ModelAttempt, PromptSafeObservation, ToolAttempt
from apeiria.app.ai.agent_turn import AgentTurnResult
from apeiria.app.ai.pipeline.delivery_steps import DeliveryOutcome
from apeiria.app.ai.session_runtime import (
    RuntimeHardRuleDecision,
    project_turn_trace,
)


def test_project_turn_trace_from_agent_turn_result_and_delivery() -> None:
    turn = AgentTurnResult(
        trace_id="trace-1",
        runtime_mode="future_task",
        status="completed",
        finish_reason="completed",
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
                arguments_summary="{}",
                observation=PromptSafeObservation(content="ok"),
            ),
        ),
        response_source="direct",
    )
    strategy = RuntimeHardRuleDecision(
        action="continue",
        reason_codes=("future_task",),
        reason_text="future task",
        evidence={},
        should_observe=True,
        should_reply=True,
    )

    trace = project_turn_trace(
        session_id="session-1",
        strategy_decision=strategy,
        turn_result=turn,
        delivery_result=DeliveryOutcome(delivered=True),
    )

    assert trace.trace_id == "trace-1"
    assert trace.runtime_mode == "future_task"
    assert trace.strategy_action == "continue"
    assert trace.strategy_reason_codes == ("future_task",)
    assert trace.model_attempts == turn.model_attempts
    assert trace.tool_attempts == turn.tool_attempts
    assert trace.final_response_source == "direct"
    assert trace.delivery_status == "delivered"


def test_project_turn_trace_records_skips_and_delivery_failures() -> None:
    strategy = RuntimeHardRuleDecision(
        action="observe",
        reason_codes=("ambient_weak_relevance",),
        reason_text="weak ambient context",
        evidence={},
        should_observe=True,
        should_reply=False,
    )

    trace = project_turn_trace(
        session_id="session-1",
        strategy_decision=strategy,
        turn_result=None,
        trace_id="trace-skip",
        runtime_mode="message",
        delivery_result=DeliveryOutcome(delivered=False, error="bot_not_connected"),
    )

    assert trace.trace_id == "trace-skip"
    assert trace.strategy_action == "observe"
    assert trace.skip_reason == "ambient_weak_relevance"
    assert trace.delivery_status == "failed"


def test_project_turn_trace_records_social_policy_suppression() -> None:
    strategy = RuntimeHardRuleDecision(
        action="continue",
        reason_codes=("ambient_candidate",),
        reason_text="candidate",
        evidence={},
        should_observe=True,
        should_reply=True,
    )
    turn = AgentTurnResult.skipped(
        trace_id="trace-social",
        runtime_mode="message",
        finish_reason="strategy_skipped",
    )

    trace = project_turn_trace(
        session_id="session-1",
        strategy_decision=strategy,
        turn_result=turn,
    )

    assert trace.strategy_action == "continue"
    assert trace.skip_reason == "strategy_skipped"
    assert trace.to_metadata()["model_attempt_count"] == 0


def test_project_turn_trace_records_tool_loop_failure() -> None:
    strategy = RuntimeHardRuleDecision(
        action="continue",
        reason_codes=("direct_signal",),
        reason_text="direct",
        evidence={},
        should_observe=True,
        should_reply=True,
    )
    turn = AgentTurnResult(
        trace_id="trace-tool-failed",
        runtime_mode="message",
        status="failed",
        finish_reason="tool_loop_failed",
        response_source="tool_loop",
        tool_attempts=(
            ToolAttempt(
                tool_call_id="call-1",
                tool_name="memory.query",
                status="error",
                arguments_summary="{}",
                observation=PromptSafeObservation(content="failed"),
            ),
        ),
    )

    trace = project_turn_trace(
        session_id="session-1",
        strategy_decision=strategy,
        turn_result=turn,
    )

    assert trace.final_response_source == "tool_loop"
    assert trace.to_metadata()["tool_attempt_count"] == 1
    assert trace.to_metadata()["delivery_status"] == "not_required"


def test_turn_trace_metadata_omits_provider_diagnostics() -> None:
    strategy = RuntimeHardRuleDecision(
        action="continue",
        reason_codes=("direct_signal",),
        reason_text="direct",
        evidence={},
        should_observe=True,
        should_reply=True,
    )
    turn = AgentTurnResult(
        trace_id="trace-1",
        runtime_mode="message",
        status="failed",
        finish_reason="model_failed",
        model_attempts=(
            ModelAttempt(
                attempt_index=1,
                model_ref="source:gpt",
                status="failed",
                response_source="direct",
                diagnostic="token=secret-token",
            ),
        ),
        diagnostic="token=secret-token",
    )

    trace = project_turn_trace(
        session_id="session-1",
        strategy_decision=strategy,
        turn_result=turn,
        delivery_result=None,
    )

    metadata = trace.to_metadata()

    assert metadata["model_attempt_count"] == 1
    assert "secret-token" not in str(metadata)


def test_project_turn_trace_includes_bounded_prompt_diagnostics() -> None:
    strategy = RuntimeHardRuleDecision(
        action="continue",
        reason_codes=("direct_signal",),
        reason_text="direct",
        evidence={},
        should_observe=True,
        should_reply=True,
    )
    prompt_diagnostics = {
        "prompt_purpose": "reply_final",
        "stable_section_names": ("SystemInstructions",),
        "dynamic_section_names": ("Instruction",),
        "stable_section_count": 1,
        "dynamic_section_count": 1,
        "total_section_count": 2,
    }
    turn = AgentTurnResult(
        trace_id="trace-1",
        runtime_mode="message",
        status="completed",
        finish_reason="direct_model_completed",
        response_source="direct",
        metadata={"prompt_diagnostics": prompt_diagnostics},
    )

    trace = project_turn_trace(
        session_id="session-1",
        strategy_decision=strategy,
        turn_result=turn,
    )

    assert trace.prompt_diagnostics == prompt_diagnostics
    assert trace.to_metadata()["prompt_diagnostics"] == prompt_diagnostics
