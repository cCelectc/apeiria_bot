from __future__ import annotations

from apeiria.ai.tools import AIToolObservationResult, ToolGatewayResult
from apeiria.app.ai.agent_turn import (
    AgentTurnResult,
    PromptSafeObservation,
    ToolAttempt,
)
from apeiria.app.ai.reply_strategy import ReplyStrategyDecision
from tests.ai.agent_turn_helpers import model_response, selected_model


def test_tool_loop_metadata_is_available_to_persistence() -> None:
    from apeiria.app.ai.pipeline import generation_steps
    from apeiria.app.ai.pipeline.persistence_steps import _agent_turn_meta

    selected = selected_model("main")
    raw_payload = "raw-large-tool-output"
    original_observation_length = 4096
    turn = generation_steps._build_tool_loop_turn_result(
        trace_id="trace-tools",
        runtime_mode="message",
        skill_runtime=ToolGatewayResult(
            policy_text="",
            result_lines=(),
            turns=(),
            final_response=model_response(selected, "done"),
            loop_finish_reason="max_rounds_reached",
            model_attempts=(),
            tool_attempts=(
                ToolAttempt(
                    tool_call_id="call-1",
                    tool_name="memory.query",
                    status="success",
                    arguments_summary="{}",
                    observation=PromptSafeObservation(
                        content="- [memory.query] preview\n[truncated]",
                        truncated=True,
                        original_length=original_observation_length,
                    ),
                    native_observation=AIToolObservationResult(
                        tool_name="memory.query",
                        summary=raw_payload,
                        input_payload={},
                        output_payload={"raw": raw_payload},
                    ),
                ),
            ),
            metadata={
                "tool_loop_context_recovery_attempted": True,
                "tool_loop_model_retry_count": 1,
            },
        ),
    )

    persisted = _agent_turn_meta(turn)

    assert turn.response_source == "tool_loop"
    assert persisted["agent_turn_finish_reason"] == "max_rounds_reached"
    assert persisted["agent_turn_metadata"]["tool_observation_count"] == 0
    assert persisted["agent_turn_metadata"]["tool_message_count"] == 0
    assert (
        persisted["agent_turn_metadata"]["tool_loop_context_recovery_attempted"] is True
    )
    assert persisted["agent_turn_metadata"]["tool_loop_model_retry_count"] == 1
    attempt = persisted["agent_turn_tool_attempts"][0]
    assert attempt["observation_truncated"] is True
    assert attempt["observation_original_length"] == original_observation_length
    assert raw_payload not in str(persisted)
    assert "native_observation" not in attempt


def test_compact_turn_trace_metadata_is_available_to_persistence() -> None:
    from apeiria.app.ai.pipeline.persistence_steps import _turn_trace_meta

    decision = ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="allow",
        reason_codes=("direct_signal",),
        reason_text="direct",
        evidence={},
        decision_source="fallback",
    )
    turn = AgentTurnResult.skipped(
        trace_id="trace-1",
        runtime_mode="message",
        finish_reason="contract_test",
    )

    persisted = _turn_trace_meta(
        trace_id="trace-1",
        session_id="session-1",
        runtime_mode="message",
        social_decision=decision,
        turn=turn,
        delivery_delivered=None,
    )

    assert persisted["turn_trace"] == {
        "trace_id": "trace-1",
        "session_id": "session-1",
        "runtime_mode": "message",
        "strategy_action": "continue",
        "strategy_reason_codes": ["direct_signal"],
        "merged_message_count": 0,
        "merge_reason": None,
        "wait_reason": None,
        "defer_reason": None,
        "model_attempt_count": 0,
        "tool_attempt_count": 0,
        "tool_observation_count": 0,
        "final_response_source": None,
        "skip_reason": "contract_test",
        "delivery_status": "not_required",
    }
