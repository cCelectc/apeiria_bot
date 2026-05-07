from __future__ import annotations

import asyncio
from dataclasses import replace
from typing import Any

from apeiria.ai.model import (
    AIModelContentPart,
    AIModelGenerateResponse,
    AIModelMessage,
)
from apeiria.ai.model.runtime.capabilities import (
    AIModelCallRequirements,
    AIModelCapabilities,
    AIModelCapabilityPlanningError,
)
from apeiria.ai.model.runtime.planning import plan_model_call
from apeiria.ai.tools import AIToolObservationResult
from apeiria.ai.tools.loop.prompt_budget import recover_prompt_budget_messages
from apeiria.app.ai.runtime.execution.tool_loop import RuntimeToolLoopRunner
from tests.ai.agent_turn_helpers import (
    ModelInvokerStub,
    ToolServiceStub,
    model_response,
    selected_model,
    tool_call,
    tool_loop_input,
)


class PlanningInvokerStub:
    def __init__(self, content: str = "done") -> None:
        self.content = content
        self.calls: list[Any] = []
        self.tool_calls: list[tuple[Any, ...]] = []

    async def generate_text(
        self,
        *,
        selected: Any,
        prompt: str = "",
        messages: tuple[AIModelMessage, ...] = (),
        tools: tuple[Any, ...] = (),
        requirements: AIModelCallRequirements | None = None,
        **_: Any,
    ) -> AIModelGenerateResponse:
        del prompt
        plan = plan_model_call(
            selected=selected,
            messages=messages,
            tools=tools,
            requirements=requirements,
        )
        self.calls.append(selected)
        if plan.action == "reject":
            raise AIModelCapabilityPlanningError(plan)
        self.tool_calls.append(plan.tools)
        return AIModelGenerateResponse(
            source_id=selected.source.source_id,
            model_name=selected.resolved_model_name or "",
            content=self.content,
            provider_data={
                "apeiria_degradations": [
                    {
                        "kind": item.kind,
                        "reason": item.reason,
                        "detail": item.detail,
                        "metadata": item.metadata,
                    }
                    for item in plan.degradations
                ]
            },
        )


class UpstreamError(RuntimeError):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


def _tool_definition() -> Any:
    from apeiria.ai.model import AIModelToolDefinition

    return AIModelToolDefinition(
        name="memory_query",
        description="Query memory",
        parameters={"type": "object"},
    )


def test_tool_loop_records_final_response_finish_reason() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub(
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
    runner = RuntimeToolLoopRunner(model_invoker=invoker, tool_service=service)

    result = asyncio.run(runner.run(tool_loop_input(selected)))

    assert result.finish_reason == "final_response"
    assert result.final_response is not None
    assert result.final_response.content == "done"
    assert [attempt.response_source for attempt in result.model_attempts] == [
        "tool_loop",
        "tool_loop",
    ]
    assert result.tool_attempts[0].tool_name == "memory.query"
    assert result.tool_attempts[0].status == "success"


def test_tool_loop_model_failure_uses_shared_taxonomy() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub([UpstreamError("upstream overloaded", status_code=503)])
    runner = RuntimeToolLoopRunner(
        model_invoker=invoker,
        tool_service=ToolServiceStub([]),
    )

    result = asyncio.run(runner.run(tool_loop_input(selected)))

    assert result.final_response is None
    assert result.finish_reason == "upstream_temporary_error"
    assert result.model_attempts[0].reason == "upstream_temporary_error"


def test_tool_loop_uses_capable_fallback_for_required_tools() -> None:
    primary = replace(
        selected_model("primary"),
        resolved_capabilities=AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            input_modalities=frozenset({"text"}),
            output_modalities=frozenset({"text"}),
            supports_tool_calling=False,
        ),
    )
    fallback = replace(
        selected_model("fallback"),
        resolved_capabilities=AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            input_modalities=frozenset({"text"}),
            output_modalities=frozenset({"text"}),
            supports_tool_calling=True,
        ),
    )
    invoker = PlanningInvokerStub()
    runner = RuntimeToolLoopRunner(
        model_invoker=invoker,
        tool_service=ToolServiceStub(observations=[]),
    )

    result = asyncio.run(
        runner.run(
            tool_loop_input(
                primary,
                messages=(AIModelMessage(role="user", content="use tools"),),
                tools=(_tool_definition(),),
                fallback_models=(fallback,),
            )
        )
    )

    assert [attempt.reason for attempt in result.model_attempts] == [
        "capability_unavailable",
        None,
    ]
    assert [item.source.source_id for item in invoker.calls] == [
        "source-primary",
        "source-fallback",
    ]
    assert result.final_response is not None
    assert result.final_response.content == "done"


def test_tool_loop_records_optional_tool_degradation() -> None:
    selected = replace(
        selected_model("main"),
        resolved_capabilities=AIModelCapabilities(
            lanes=frozenset({"chat_completion"}),
            input_modalities=frozenset({"text"}),
            output_modalities=frozenset({"text"}),
            supports_tool_calling=False,
        ),
    )
    invoker = PlanningInvokerStub()
    runner = RuntimeToolLoopRunner(
        model_invoker=invoker,
        tool_service=ToolServiceStub(observations=[]),
    )

    result = asyncio.run(
        runner.run(
            tool_loop_input(
                selected,
                messages=(AIModelMessage(role="user", content="answer without tools"),),
                tools=(_tool_definition(),),
            ),
            tool_calling_requirement="optional",
        )
    )

    assert invoker.tool_calls == [()]
    assert result.final_response is not None
    assert result.diagnostics["tool_loop_capability_degradations"][0]["kind"] == (
        "tools_omitted"
    )


def test_prompt_budget_recovery_preserves_content_parts() -> None:
    message = AIModelMessage(
        role="tool",
        content="x" * 1000,
        tool_call_id="call-1",
        parts=(AIModelContentPart(kind="text", text="part text"),),
    )

    recovered, compacted = recover_prompt_budget_messages((message,))

    assert compacted == 1
    assert recovered[0].parts == message.parts
    assert "[truncated]" in recovered[0].content


def test_tool_loop_records_failed_tool_observation() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub(
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
    runner = RuntimeToolLoopRunner(model_invoker=invoker, tool_service=service)

    result = asyncio.run(runner.run(tool_loop_input(selected)))

    assert result.tool_attempts[0].status == "error"
    assert result.tool_attempts[0].observation.content.startswith(
        "- [memory.query] failed"
    )


def test_tool_loop_records_timeout_tool_observation() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub(
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
                    summary="- [memory.query] timed out after 0.1s",
                    input_payload={"query_text": "hello"},
                    output_payload={"error": "timeout"},
                    status="timeout",
                )
            ]
        ]
    )
    runner = RuntimeToolLoopRunner(model_invoker=invoker, tool_service=service)

    result = asyncio.run(
        runner.run(tool_loop_input(selected, execution_timeout_seconds=0.1))
    )

    assert result.tool_attempts[0].status == "timeout"
    assert result.tool_attempts[0].native_observation is not None
    assert result.tool_attempts[0].native_observation.output_payload == {
        "error": "timeout"
    }
    assert "timed out" in result.tool_attempts[0].observation.content


def test_tool_loop_records_denied_tool_observation() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub(
        [
            model_response(selected, "", tool_calls=(tool_call("call-1"),)),
            model_response(selected, "done"),
        ]
    )
    service = ToolServiceStub(observations=[], allowed_tool_names=())
    runner = RuntimeToolLoopRunner(model_invoker=invoker, tool_service=service)

    result = asyncio.run(runner.run(tool_loop_input(selected)))

    assert service.calls == []
    assert result.tool_attempts[0].status == "error"
    assert "denied by policy" in result.tool_attempts[0].observation.content


def test_tool_loop_denies_tool_not_exposed_for_current_turn() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub(
        [
            model_response(selected, "", tool_calls=(tool_call("call-1"),)),
            model_response(selected, "done"),
        ]
    )
    service = ToolServiceStub(observations=[], allowed_tool_names=("memory.query",))
    runner = RuntimeToolLoopRunner(model_invoker=invoker, tool_service=service)

    result = asyncio.run(
        runner.run(
            tool_loop_input(
                selected,
                tools=(_tool_definition(),),
                executable_tool_names=frozenset(),
            )
        )
    )

    assert service.calls == []
    assert result.tool_attempts[0].status == "error"
    assert "not exposed for this turn" in result.tool_attempts[0].observation.content
    assert result.tool_attempts[0].native_observation is not None
    assert result.tool_attempts[0].native_observation.output_payload["error"] == (
        "not_exposed_for_turn"
    )


def test_tool_loop_recovers_once_from_context_pressure() -> None:
    selected = selected_model("main")
    long_observation = "- [memory.query] " + ("x" * 1200)
    invoker = ModelInvokerStub(
        [
            RuntimeError("context_length_exceeded api_key=secret-token"),
            model_response(selected, "done"),
        ]
    )
    runner = RuntimeToolLoopRunner(
        model_invoker=invoker,
        tool_service=ToolServiceStub(observations=[]),
    )

    result = asyncio.run(
        runner.run(
            tool_loop_input(
                selected,
                messages=(
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
                ),
            )
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
    assert result.diagnostics["tool_loop_context_recovery_attempted"] is True
    assert result.diagnostics["tool_loop_context_recovery_succeeded"] is True
    assert result.diagnostics["tool_loop_context_recovery_failed"] is False
    assert result.diagnostics["tool_loop_context_recovery_compacted_messages"] == 1
    assert result.diagnostics["tool_loop_model_retry_count"] == 1
    assert result.diagnostics["tool_loop_model_attempt_count"] == len(invoker.calls)
    first_tool_message = next(
        message for message in invoker.message_calls[0] if message.role == "tool"
    )
    retry_tool_message = next(
        message for message in invoker.message_calls[1] if message.role == "tool"
    )
    assert first_tool_message.content == long_observation
    assert len(retry_tool_message.content) < len(long_observation)
    assert "[truncated]" in retry_tool_message.content


def test_tool_loop_records_failed_context_pressure_recovery() -> None:
    selected = selected_model("main")
    long_observation = "- [memory.query] " + ("x" * 1200)
    invoker = ModelInvokerStub(
        [
            RuntimeError("context_length_exceeded token=secret-token"),
            RuntimeError("context_length_exceeded token=secret-token"),
        ]
    )
    runner = RuntimeToolLoopRunner(
        model_invoker=invoker,
        tool_service=ToolServiceStub(observations=[]),
    )

    result = asyncio.run(
        runner.run(
            tool_loop_input(
                selected,
                messages=(
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
                ),
            )
        )
    )

    assert result.final_response is None
    assert result.finish_reason == "context_pressure"
    assert [attempt.reason for attempt in result.model_attempts] == [
        "context_pressure",
        "context_pressure",
    ]
    assert result.diagnostics["tool_loop_context_recovery_attempted"] is True
    assert result.diagnostics["tool_loop_context_recovery_succeeded"] is False
    assert result.diagnostics["tool_loop_context_recovery_failed"] is True
    assert result.diagnostics["tool_loop_model_retry_count"] == 1
    assert all(
        "secret-token" not in (attempt.diagnostic or "")
        for attempt in result.model_attempts
    )


def test_tool_loop_repairs_missing_tool_result_before_model_call() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub([model_response(selected, "done")])
    runner = RuntimeToolLoopRunner(
        model_invoker=invoker,
        tool_service=ToolServiceStub(observations=[]),
    )

    result = asyncio.run(
        runner.run(
            tool_loop_input(
                selected,
                messages=(
                    AIModelMessage(
                        role="assistant",
                        content="",
                        tool_calls=(tool_call("call-1"),),
                    ),
                ),
            )
        )
    )

    placeholder = next(
        message for message in invoker.message_calls[0] if message.role == "tool"
    )
    assert placeholder.tool_call_id == "call-1"
    assert "missing tool observation" in placeholder.content
    assert result.diagnostics["tool_loop_chain_repair_placeholders"] == 1


def test_tool_loop_omits_orphan_tool_result_before_model_call() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub([model_response(selected, "done")])
    runner = RuntimeToolLoopRunner(
        model_invoker=invoker,
        tool_service=ToolServiceStub(observations=[]),
    )

    result = asyncio.run(
        runner.run(
            tool_loop_input(
                selected,
                messages=(
                    AIModelMessage(
                        role="tool",
                        content="- [memory.query] orphan",
                        tool_call_id="call-1",
                    ),
                ),
            )
        )
    )

    assert all(message.role != "tool" for message in invoker.message_calls[0])
    assert result.diagnostics["tool_loop_chain_repair_orphans"] == 1


def test_tool_loop_records_max_rounds_and_repeated_tool_calls() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub(
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
    runner = RuntimeToolLoopRunner(model_invoker=invoker, tool_service=service)

    result = asyncio.run(
        runner.run(
            tool_loop_input(selected),
            max_rounds=2,
            repeated_tool_threshold=2,
        )
    )

    assert result.finish_reason == "max_rounds_reached"
    assert result.final_response is not None
    assert result.final_response.content == "final after max rounds"
    assert [attempt.repetition_count for attempt in result.tool_attempts] == [1, 2]
    assert result.tool_attempts[1].repeated is True
    assert "repeated tool call" in (result.tool_attempts[1].diagnostic or "")
    expected_tool_rounds = 2
    assert len(service.calls) == expected_tool_rounds
    assert len(invoker.calls) == expected_tool_rounds + 1
    assert invoker.tool_calls[-1] == ()
    assert result.diagnostics["tool_loop_finalization_attempted"] is True
    assert result.diagnostics["tool_loop_finalization_succeeded"] is True


def test_tool_loop_keeps_max_rounds_result_when_finalization_is_empty() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub(
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
    runner = RuntimeToolLoopRunner(model_invoker=invoker, tool_service=service)

    result = asyncio.run(runner.run(tool_loop_input(selected), max_rounds=1))

    assert result.finish_reason == "max_rounds_reached"
    assert result.final_response is not None
    assert result.final_response.tool_calls == (tool_call("call-1"),)
    assert len(service.calls) == 1
    assert invoker.tool_calls[-1] == ()
    assert result.diagnostics["tool_loop_finalization_attempted"] is True
    assert result.diagnostics["tool_loop_finalization_succeeded"] is False
    assert result.diagnostics["tool_loop_finalization_error"] == "empty_response"


def test_tool_loop_truncates_prompt_visible_observation() -> None:
    selected = selected_model("main")
    long_summary = "- [memory.query] " + ("x" * 200)
    invoker = ModelInvokerStub(
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
    runner = RuntimeToolLoopRunner(model_invoker=invoker, tool_service=service)

    result = asyncio.run(
        runner.run(tool_loop_input(selected), observation_char_limit=48)
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
