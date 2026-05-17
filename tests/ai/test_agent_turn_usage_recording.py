from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.app.ai.agent_turn import AgentModelGenerationRequest
from apeiria.app.ai.agent_turn.model_runtime import AgentTurnModelRuntime
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopRunner
from tests.ai.agent_turn_helpers import (
    ModelInvokerStub,
    ToolServiceStub,
    model_response,
    selected_model,
    stream_final,
    stream_start,
    tool_call,
    tool_loop_input,
)

if TYPE_CHECKING:
    from apeiria.ai.model.routing.selection import AISelectedModel
    from apeiria.ai.token_usage import AIModelUsageCreateInput
    from apeiria.app.ai.agent_turn.models import AIModelStreamSink

USAGE_STORE_UNAVAILABLE = "usage store unavailable"
PROVIDER_INPUT_TOKENS = 10
PROVIDER_OUTPUT_TOKENS = 5
PROVIDER_TOTAL_TOKENS = 15
EMPTY_RESPONSE_TOTAL_TOKENS = 8
FALLBACK_ATTEMPT_INDEX = 2
STREAM_TOTAL_TOKENS = 13


@dataclass
class UsageRecorderSpy:
    fail: bool = False

    def __post_init__(self) -> None:
        self.records: list[AIModelUsageCreateInput] = []

    def record_model_usage(self, create_input: AIModelUsageCreateInput) -> None:
        self.records.append(create_input)
        if self.fail:
            raise RuntimeError(USAGE_STORE_UNAVAILABLE)


def test_direct_generation_records_provider_usage() -> None:
    selected = selected_model("primary")
    recorder = UsageRecorderSpy()
    runtime = AgentTurnModelRuntime(
        model_invoker=ModelInvokerStub(
            [
                model_response(
                    selected,
                    "hello",
                    usage={
                        "prompt_tokens": PROVIDER_INPUT_TOKENS,
                        "completion_tokens": PROVIDER_OUTPUT_TOKENS,
                        "total_tokens": PROVIDER_TOTAL_TOKENS,
                    },
                    finish_reason="stop",
                    response_id="resp-1",
                )
            ]
        ),
        usage_recorder=recorder,
    )

    result = asyncio.run(runtime.generate(_request(selected)))

    assert result.response is not None
    assert len(recorder.records) == 1
    event = recorder.records[0]
    assert event.trace_id == "trace-1"
    assert event.session_id == "session-1"
    assert event.response_source == "direct"
    assert event.source_id == selected.source.source_id
    assert event.model_name == selected.resolved_model_name
    assert event.operation == "chat_generation"
    assert event.attempt_index == 1
    assert event.status == "success"
    assert event.provider_response_id == "resp-1"
    assert event.finish_reason == "stop"
    assert event.usage.usage_available is True
    assert event.usage.input_tokens == PROVIDER_INPUT_TOKENS
    assert event.usage.output_tokens == PROVIDER_OUTPUT_TOKENS
    assert event.usage.total_tokens == PROVIDER_TOTAL_TOKENS


def test_direct_generation_records_empty_response_with_usage() -> None:
    selected = selected_model("empty")
    recorder = UsageRecorderSpy()
    runtime = AgentTurnModelRuntime(
        model_invoker=ModelInvokerStub(
            [
                model_response(
                    selected,
                    "",
                    usage={
                        "prompt_tokens": EMPTY_RESPONSE_TOTAL_TOKENS,
                        "completion_tokens": 0,
                        "total_tokens": EMPTY_RESPONSE_TOTAL_TOKENS,
                    },
                )
            ]
        ),
        usage_recorder=recorder,
    )

    result = asyncio.run(runtime.generate(_request(selected)))

    assert result.response is None
    assert result.turn.finish_reason == "empty_response"
    assert len(recorder.records) == 1
    assert recorder.records[0].status == "empty_response"
    assert recorder.records[0].usage.total_tokens == EMPTY_RESPONSE_TOTAL_TOKENS


def test_direct_generation_records_fallback_attempt_with_provider_usage() -> None:
    primary = selected_model("primary")
    fallback = selected_model("fallback")
    recorder = UsageRecorderSpy()
    runtime = AgentTurnModelRuntime(
        model_invoker=ModelInvokerStub(
            [
                RuntimeError("temporary provider failure"),
                model_response(
                    fallback,
                    "fallback reply",
                    usage={
                        "prompt_tokens": 7,
                        "completion_tokens": 3,
                        "total_tokens": 10,
                    },
                ),
            ]
        ),
        usage_recorder=recorder,
    )

    result = asyncio.run(
        runtime.generate(
            _request(
                primary,
                fallback_models=(fallback,),
            )
        )
    )

    assert result.response is not None
    assert [attempt.status for attempt in result.turn.model_attempts] == [
        "failed",
        "success",
    ]
    assert len(recorder.records) == 1
    assert recorder.records[0].attempt_index == FALLBACK_ATTEMPT_INDEX
    assert recorder.records[0].model_name == fallback.resolved_model_name


def test_streamed_direct_generation_records_final_response_usage() -> None:
    selected = selected_model("stream", supports_streaming=True)
    response = model_response(
        selected,
        "streamed",
        usage={
            "prompt_tokens": 9,
            "completion_tokens": 4,
            "total_tokens": STREAM_TOTAL_TOKENS,
        },
    )
    recorder = UsageRecorderSpy()
    runtime = AgentTurnModelRuntime(
        model_invoker=ModelInvokerStub(
            [[stream_start(selected), stream_final(selected, response)]]
        ),
        usage_recorder=recorder,
    )

    result = asyncio.run(runtime.generate(_request(selected, stream_policy="optional")))

    assert result.response is response
    assert len(recorder.records) == 1
    assert recorder.records[0].status == "success"
    assert recorder.records[0].usage.total_tokens == STREAM_TOTAL_TOKENS


def test_usage_recording_failure_does_not_break_direct_reply() -> None:
    selected = selected_model("primary")
    recorder = UsageRecorderSpy(fail=True)
    runtime = AgentTurnModelRuntime(
        model_invoker=ModelInvokerStub([model_response(selected, "hello")]),
        usage_recorder=recorder,
    )

    result = asyncio.run(runtime.generate(_request(selected)))

    assert result.response is not None
    assert result.turn.status == "completed"
    assert len(recorder.records) == 1


def test_tool_loop_records_each_model_response_context() -> None:
    selected = selected_model("tools")
    first = model_response(
        selected,
        "",
        tool_calls=(tool_call("call-1"),),
        usage={
            "prompt_tokens": 10,
            "completion_tokens": 2,
            "total_tokens": 12,
        },
    )
    second = model_response(
        selected,
        "final answer",
        usage={
            "prompt_tokens": 15,
            "completion_tokens": 5,
            "total_tokens": 20,
        },
    )
    recorder = UsageRecorderSpy()
    runner = RuntimeToolLoopRunner(
        model_invoker=ModelInvokerStub([first, second]),
        tool_service=ToolServiceStub(observations=[[]]),
        usage_recorder=recorder,
    )

    result = asyncio.run(runner.run(tool_loop_input(selected), max_rounds=2))

    assert result.final_response is second
    assert [event.trace_id for event in recorder.records] == [
        "trace-tools",
        "trace-tools",
    ]
    assert [event.session_id for event in recorder.records] == [
        "session-1",
        "session-1",
    ]
    assert [event.response_source for event in recorder.records] == [
        "tool_loop",
        "tool_loop",
    ]
    assert [event.attempt_index for event in recorder.records] == [1, 2]
    assert [event.usage.total_tokens for event in recorder.records] == [12, 20]


def _request(
    selected: "AISelectedModel",
    *,
    fallback_models: tuple["AISelectedModel", ...] = (),
    stream_policy: "AIModelStreamSink" = "none",
) -> AgentModelGenerationRequest:
    return AgentModelGenerationRequest(
        trace_id="trace-1",
        session_id="session-1",
        runtime_mode="message",
        selected=selected,
        messages=(),
        fallback_models=fallback_models,
        response_source="direct",
        stream_policy=stream_policy,
    )
