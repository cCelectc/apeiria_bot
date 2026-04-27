from __future__ import annotations

import asyncio

from apeiria.ai.model import AIModelMessage
from apeiria.ai.tools import AIToolObservationResult, ToolGateway
from tests.ai.agent_turn_helpers import (
    ModelGatewayStub,
    ToolServiceStub,
    model_response,
    selected_model,
    tool_call,
    tool_request,
)


def test_tool_loop_records_final_response_finish_reason() -> None:
    selected = selected_model("main")
    gateway = ModelGatewayStub(
        [
            model_response(selected, "", tool_calls=(tool_call("call-1"),)),
            model_response(selected, "done"),
        ]
    )
    service = ToolServiceStub(
        [
            [
                AIToolObservationResult(
                    tool_name="memory.query",
                    summary="- [memory.query] result",
                    input_payload={"query_text": "hello"},
                    output_payload={"memory_ids": ["m1"]},
                )
            ]
        ]
    )
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            tool_request(),
            messages=[],
            tools=(),
            selected=selected,
        )
    )

    assert result.loop_finish_reason == "final_response"
    assert result.final_response is not None
    assert result.final_response.content == "done"
    assert [attempt.response_source for attempt in result.model_attempts] == [
        "tool_loop",
        "tool_loop",
    ]
    assert result.tool_attempts[0].tool_name == "memory.query"
    assert result.tool_attempts[0].status == "success"


def test_tool_loop_records_failed_tool_observation() -> None:
    selected = selected_model("main")
    gateway = ModelGatewayStub(
        [
            model_response(selected, "", tool_calls=(tool_call("call-1"),)),
            model_response(selected, "done"),
        ]
    )
    service = ToolServiceStub(
        [
            [
                AIToolObservationResult(
                    tool_name="memory.query",
                    summary="- [memory.query] failed: tool not found",
                    input_payload={"query_text": "hello"},
                    output_payload={"error": "tool not found"},
                    status="error",
                )
            ]
        ]
    )
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            tool_request(),
            messages=[],
            tools=(),
            selected=selected,
        )
    )

    assert result.tool_attempts[0].status == "error"
    assert result.tool_attempts[0].observation.content.startswith(
        "- [memory.query] failed"
    )


def test_tool_loop_records_denied_tool_observation() -> None:
    selected = selected_model("main")
    gateway = ModelGatewayStub(
        [
            model_response(selected, "", tool_calls=(tool_call("call-1"),)),
            model_response(selected, "done"),
        ]
    )
    service = ToolServiceStub(observations=[], allowed_tool_names=())
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            tool_request(),
            messages=[],
            tools=(),
            selected=selected,
        )
    )

    assert service.calls == []
    assert result.tool_attempts[0].status == "error"
    assert "denied by policy" in result.tool_attempts[0].observation.content


def test_tool_loop_recovers_once_from_context_pressure() -> None:
    selected = selected_model("main")
    long_observation = "- [memory.query] " + ("x" * 1200)
    gateway = ModelGatewayStub(
        [
            RuntimeError("context_length_exceeded api_key=secret-token"),
            model_response(selected, "done"),
        ]
    )
    service = ToolServiceStub(observations=[])
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            tool_request(),
            messages=[
                AIModelMessage(
                    role="assistant",
                    content="",
                    tool_calls=(tool_call("call-1"),),
                ),
                AIModelMessage(
                    role="tool",
                    content=long_observation,
                    tool_call_id="call-1",
                ),
            ],
            tools=(),
            selected=selected,
        )
    )

    assert result.final_response is not None
    assert result.final_response.content == "done"
    assert [attempt.status for attempt in result.model_attempts] == [
        "failed",
        "success",
    ]
    assert result.model_attempts[0].reason == "context_pressure"
    diagnostic = result.model_attempts[0].diagnostic or ""
    assert "secret-token" not in diagnostic
    assert "api_key=<redacted>" in diagnostic
    assert result.metadata["tool_loop_context_recovery_attempted"] is True
    assert result.metadata["tool_loop_context_recovery_succeeded"] is True
    assert result.metadata["tool_loop_context_recovery_failed"] is False
    assert result.metadata["tool_loop_context_recovery_compacted_messages"] == 1
    assert result.metadata["tool_loop_model_retry_count"] == 1
    assert result.metadata["tool_loop_model_attempt_count"] == len(gateway.calls)
    first_tool_message = next(
        message for message in gateway.message_calls[0] if message.role == "tool"
    )
    retry_tool_message = next(
        message for message in gateway.message_calls[1] if message.role == "tool"
    )
    assert first_tool_message.content == long_observation
    assert len(retry_tool_message.content) < len(long_observation)
    assert "[truncated]" in retry_tool_message.content


def test_tool_loop_records_failed_context_pressure_recovery() -> None:
    selected = selected_model("main")
    long_observation = "- [memory.query] " + ("x" * 1200)
    gateway = ModelGatewayStub(
        [
            RuntimeError("context_length_exceeded token=secret-token"),
            RuntimeError("context_length_exceeded token=secret-token"),
        ]
    )
    service = ToolServiceStub(observations=[])
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            tool_request(),
            messages=[
                AIModelMessage(
                    role="assistant",
                    content="",
                    tool_calls=(tool_call("call-1"),),
                ),
                AIModelMessage(
                    role="tool",
                    content=long_observation,
                    tool_call_id="call-1",
                ),
            ],
            tools=(),
            selected=selected,
        )
    )

    assert result.final_response is None
    assert result.loop_finish_reason == "context_pressure"
    assert [attempt.reason for attempt in result.model_attempts] == [
        "context_pressure",
        "context_pressure",
    ]
    assert result.metadata["tool_loop_context_recovery_attempted"] is True
    assert result.metadata["tool_loop_context_recovery_succeeded"] is False
    assert result.metadata["tool_loop_context_recovery_failed"] is True
    assert result.metadata["tool_loop_model_retry_count"] == 1
    assert all(
        "secret-token" not in (attempt.diagnostic or "")
        for attempt in result.model_attempts
    )


def test_tool_loop_repairs_missing_tool_result_before_model_call() -> None:
    selected = selected_model("main")
    gateway = ModelGatewayStub([model_response(selected, "done")])
    service = ToolServiceStub(observations=[])
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            tool_request(),
            messages=[
                AIModelMessage(
                    role="assistant",
                    content="",
                    tool_calls=(tool_call("call-1"),),
                )
            ],
            tools=(),
            selected=selected,
        )
    )

    placeholder = next(
        message for message in gateway.message_calls[0] if message.role == "tool"
    )
    assert placeholder.tool_call_id == "call-1"
    assert "missing tool observation" in placeholder.content
    assert result.metadata["tool_loop_chain_repair_placeholders"] == 1


def test_tool_loop_omits_orphan_tool_result_before_model_call() -> None:
    selected = selected_model("main")
    gateway = ModelGatewayStub([model_response(selected, "done")])
    service = ToolServiceStub(observations=[])
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            tool_request(),
            messages=[
                AIModelMessage(
                    role="tool",
                    content="- [memory.query] orphan",
                    tool_call_id="call-1",
                )
            ],
            tools=(),
            selected=selected,
        )
    )

    assert all(message.role != "tool" for message in gateway.message_calls[0])
    assert result.metadata["tool_loop_chain_repair_orphans"] == 1


def test_tool_loop_records_max_rounds_and_repeated_tool_calls() -> None:
    selected = selected_model("main")
    gateway = ModelGatewayStub(
        [
            model_response(selected, "", tool_calls=(tool_call("call-1"),)),
            model_response(selected, "", tool_calls=(tool_call("call-2"),)),
            model_response(selected, "final after max rounds"),
        ]
    )
    service = ToolServiceStub(
        [
            [
                AIToolObservationResult(
                    tool_name="memory.query",
                    summary="- [memory.query] first",
                    input_payload={},
                    output_payload={},
                )
            ],
            [
                AIToolObservationResult(
                    tool_name="memory.query",
                    summary="- [memory.query] second",
                    input_payload={},
                    output_payload={},
                )
            ],
        ]
    )
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            tool_request(),
            messages=[],
            tools=(),
            selected=selected,
            max_rounds=2,
            repeated_tool_threshold=2,
        )
    )

    assert result.loop_finish_reason == "max_rounds_reached"
    assert result.final_response is not None
    assert result.final_response.content == "final after max rounds"
    assert [attempt.repetition_count for attempt in result.tool_attempts] == [1, 2]
    assert result.tool_attempts[1].repeated is True
    assert "repeated tool call" in (result.tool_attempts[1].diagnostic or "")
    expected_tool_rounds = 2
    assert len(service.calls) == expected_tool_rounds
    assert len(gateway.calls) == expected_tool_rounds + 1
    assert gateway.tool_calls[-1] == ()
    assert result.metadata["tool_loop_finalization_attempted"] is True
    assert result.metadata["tool_loop_finalization_succeeded"] is True


def test_tool_loop_keeps_max_rounds_result_when_finalization_is_empty() -> None:
    selected = selected_model("main")
    gateway = ModelGatewayStub(
        [
            model_response(selected, "", tool_calls=(tool_call("call-1"),)),
            model_response(selected, ""),
        ]
    )
    service = ToolServiceStub(
        [
            [
                AIToolObservationResult(
                    tool_name="memory.query",
                    summary="- [memory.query] first",
                    input_payload={},
                    output_payload={},
                )
            ]
        ]
    )
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            tool_request(),
            messages=[],
            tools=(),
            selected=selected,
            max_rounds=1,
        )
    )

    assert result.loop_finish_reason == "max_rounds_reached"
    assert result.final_response is not None
    assert result.final_response.tool_calls == (tool_call("call-1"),)
    assert len(service.calls) == 1
    assert gateway.tool_calls[-1] == ()
    assert result.metadata["tool_loop_finalization_attempted"] is True
    assert result.metadata["tool_loop_finalization_succeeded"] is False
    assert result.metadata["tool_loop_finalization_error"] == "empty_response"


def test_tool_loop_truncates_prompt_visible_observation() -> None:
    selected = selected_model("main")
    long_summary = "- [memory.query] " + ("x" * 200)
    gateway = ModelGatewayStub(
        [
            model_response(selected, "", tool_calls=(tool_call("call-1"),)),
            model_response(selected, "done"),
        ]
    )
    service = ToolServiceStub(
        [
            [
                AIToolObservationResult(
                    tool_name="memory.query",
                    summary=long_summary,
                    input_payload={},
                    output_payload={"full": long_summary},
                )
            ]
        ]
    )
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            tool_request(),
            messages=[],
            tools=(),
            selected=selected,
            observation_char_limit=48,
        )
    )

    assert result.tool_attempts[0].observation.truncated is True
    assert result.tool_attempts[0].observation.original_length == len(long_summary)
    assert result.tool_attempts[0].native_observation is not None
    assert result.tool_attempts[0].native_observation.output_payload["full"] == (
        long_summary
    )
    assert "[truncated]" in result.tool_attempts[0].observation.content
    tool_messages = [msg for msg in result.tool_messages if msg.role == "tool"]
    assert tool_messages
    assert tool_messages[0].content == result.tool_attempts[0].observation.content
