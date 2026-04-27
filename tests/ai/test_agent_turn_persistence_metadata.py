from __future__ import annotations

from apeiria.ai.tools import AIToolObservationResult, ToolGatewayResult
from apeiria.app.ai.agent_turn import PromptSafeObservation, ToolAttempt
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
