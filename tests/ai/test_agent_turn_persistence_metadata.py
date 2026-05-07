from __future__ import annotations

from apeiria.ai.tools import AIToolObservationResult
from apeiria.ai.turn_records import ModelAttempt
from apeiria.app.ai.agent_turn import (
    AgentTurnResult,
    PromptSafeObservation,
    ToolAttempt,
)
from apeiria.app.ai.reply_strategy import ReplyStrategyDecision
from tests.ai.agent_turn_helpers import model_response, selected_model

_MAX_DIAGNOSTIC_LENGTH = 200


def test_tool_loop_metadata_is_available_to_persistence() -> None:
    from apeiria.app.ai.runtime.commit.persistence import _agent_turn_meta

    selected = selected_model("main")
    raw_payload = "raw-large-tool-output"
    original_observation_length = 4096
    turn = AgentTurnResult(
        trace_id="trace-tools",
        runtime_mode="message",
        status="completed",
        finish_reason="max_rounds_reached",
        response=model_response(selected, "done"),
        response_source="tool_loop",
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
            "tool_observation_count": 0,
            "tool_message_count": 0,
            "tool_loop_context_recovery_attempted": True,
            "tool_loop_model_retry_count": 1,
        },
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
    from apeiria.app.ai.runtime.commit.persistence import _turn_trace_meta

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


def test_agent_turn_metadata_is_sanitized_for_assistant_persistence() -> None:
    from apeiria.app.ai.runtime.commit.persistence import _agent_turn_meta

    turn = AgentTurnResult(
        trace_id="trace-secret",
        runtime_mode="message",
        status="failed",
        finish_reason="model_failed",
        model_attempts=(
            ModelAttempt(
                attempt_index=1,
                model_ref="source:gpt",
                status="failed",
                response_source="direct",
                reason="model_error",
                diagnostic="api_key=sk-secret " + "x" * 400,
            ),
        ),
        tool_attempts=(
            ToolAttempt(
                tool_call_id="call-1",
                tool_name="memory.query",
                status="error",
                arguments_summary="{}",
                observation=PromptSafeObservation(content="safe observation"),
                diagnostic="Authorization: Bearer sk-secret",
            ),
        ),
        metadata={
            "password": "hidden",
            "nested": {"token": "secret-value"},
            "long": "x" * 400,
        },
    )

    persisted = _agent_turn_meta(turn)

    model_diagnostic = persisted["agent_turn_model_attempts"][0]["diagnostic"]
    assert str(model_diagnostic).startswith("api_key=[redacted] ")
    assert len(str(model_diagnostic)) == _MAX_DIAGNOSTIC_LENGTH
    assert (
        persisted["agent_turn_tool_attempts"][0]["diagnostic"]
        == "Authorization: Bearer [redacted]"
    )
    assert persisted["agent_turn_metadata"]["password"] == "[redacted]"
    assert persisted["agent_turn_metadata"]["nested"] == {"token": "[redacted]"}
    assert persisted["agent_turn_metadata"]["long"] == "x" * 200
