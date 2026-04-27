from __future__ import annotations

import asyncio
from dataclasses import dataclass
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any

from apeiria.ai.model import (
    AIChatModelDefinition,
    AIModelBindingTarget,
    AIModelGenerateResponse,
    AIModelMessage,
    AIModelProfileDefinition,
    AIModelToolCall,
    AISelectedModel,
    AISourceDefinition,
)
from apeiria.ai.tools import (
    AIToolObservationResult,
    ToolGateway,
    ToolGatewayRequest,
    ToolGatewayResult,
)
from apeiria.ai.tools.models import AIToolPolicy
from apeiria.app.ai.agent_turn import (
    AgentModelGenerationRequest,
    AgentModelGenerationResult,
    AgentTurnModelRuntime,
    AgentTurnResult,
    PromptSafeObservation,
    ToolAttempt,
)
from apeiria.app.ai.pipeline.delivery_steps import DeliveryOutcome
from apeiria.app.ai.pipeline.generation_steps import ReplyPreparation
from apeiria.app.ai.pipeline.input_steps import ReplyInputs
from apeiria.app.ai.pipeline.service import AIRuntimeReplyRequest
from apeiria.app.ai.reply_strategy import ReplyStrategyDecision
from apeiria.conversation.models import ChatSessionIdentity

if TYPE_CHECKING:
    from apeiria.ai.model.runtime.adapter import AIModelToolDefinition


def _selected_model(
    suffix: str,
    *,
    fallback_profile_id: str | None = None,
) -> AISelectedModel:
    return AISelectedModel(
        source=AISourceDefinition(
            source_id=f"source-{suffix}",
            name=f"Source {suffix}",
            capability_type="chat_completion",
            client_type="openai",
            preset_type="openai_compatible",
            api_base="https://example.invalid/v1",
        ),
        profile=AIModelProfileDefinition(
            profile_id=f"profile-{suffix}",
            name=f"Profile {suffix}",
            model_id=f"model-{suffix}",
            task_class="reply_default",
            priority=10,
            fallback_profile_id=fallback_profile_id,
        ),
        resolved_model_name=f"model-{suffix}",
    )


def _response(
    selected: AISelectedModel,
    content: str,
    *,
    tool_calls: tuple[AIModelToolCall, ...] = (),
) -> AIModelGenerateResponse:
    return AIModelGenerateResponse(
        source_id=selected.source.source_id,
        model_name=selected.resolved_model_name or "",
        content=content,
        tool_calls=tool_calls,
        raw={"usage": {"prompt_tokens": 12}},
    )


class _Gateway:
    def __init__(self, outcomes: list[Any]) -> None:
        self.outcomes = list(outcomes)
        self.calls: list[AISelectedModel] = []
        self.message_calls: list[tuple[AIModelMessage, ...]] = []
        self.tool_calls: list[tuple[AIModelToolDefinition, ...]] = []

    async def generate_native(
        self,
        *,
        selected: AISelectedModel,
        prompt: str = "",
        messages: tuple[AIModelMessage, ...] = (),
        tools: tuple[AIModelToolDefinition, ...] = (),
    ) -> AIModelGenerateResponse | None:
        del prompt
        self.calls.append(selected)
        self.message_calls.append(messages)
        self.tool_calls.append(tools)
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return outcome


def test_agent_turn_result_can_record_strategy_skip() -> None:
    result = AgentTurnResult.skipped(
        trace_id="trace-skip",
        runtime_mode="message",
        finish_reason="strategy_skipped",
        diagnostic="initiative budget",
    )

    assert result.status == "skipped"
    assert result.finish_reason == "strategy_skipped"
    assert result.model_attempts == ()
    assert result.diagnostic == "initiative budget"


def test_model_runtime_records_direct_success() -> None:
    selected = _selected_model("main")
    gateway = _Gateway([_response(selected, "hello")])
    runtime = AgentTurnModelRuntime(model_gateway=gateway)

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-direct",
                session_id="session-1",
                runtime_mode="message",
                selected=selected,
                prompt="Say hello",
                response_source="direct",
            )
        )
    )

    assert result.turn.status == "completed"
    assert result.turn.finish_reason == "direct_model_completed"
    assert result.turn.response == result.response
    assert result.response.content == "hello"
    assert [attempt.model_ref for attempt in result.turn.model_attempts] == [
        "source-main:model-main"
    ]
    assert result.turn.model_attempts[0].status == "success"
    assert result.turn.model_attempts[0].response_source == "direct"


def test_model_runtime_records_empty_response_without_raising() -> None:
    selected = _selected_model("main")
    gateway = _Gateway([_response(selected, "")])
    runtime = AgentTurnModelRuntime(model_gateway=gateway)

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-empty",
                session_id="session-1",
                runtime_mode="message",
                selected=selected,
                prompt="Say hello",
            )
        )
    )

    assert result.response is None
    assert result.turn.status == "failed"
    assert result.turn.finish_reason == "empty_response"
    assert result.turn.model_attempts[0].status == "failed"
    assert result.turn.model_attempts[0].reason == "empty_response"


def test_model_runtime_sanitizes_provider_exception() -> None:
    selected = _selected_model("main")
    gateway = _Gateway([RuntimeError("bad api_key=secret-token failed")])
    runtime = AgentTurnModelRuntime(model_gateway=gateway)

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-error",
                session_id="session-1",
                runtime_mode="message",
                selected=selected,
                prompt="Say hello",
            )
        )
    )

    assert result.response is None
    assert result.turn.status == "failed"
    assert result.turn.finish_reason == "model_error"
    diagnostic = result.turn.model_attempts[0].diagnostic or ""
    assert "secret-token" not in diagnostic
    assert "api_key=<redacted>" in diagnostic


def test_model_runtime_uses_configured_fallback_candidate() -> None:
    primary = _selected_model("primary", fallback_profile_id="profile-fallback")
    fallback = _selected_model("fallback")
    gateway = _Gateway(
        [
            RuntimeError("primary failed"),
            _response(fallback, "fallback answer"),
        ]
    )
    runtime = AgentTurnModelRuntime(model_gateway=gateway)

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-fallback",
                session_id="session-1",
                runtime_mode="message",
                selected=primary,
                prompt="Say hello",
                fallback_models=(fallback,),
            )
        )
    )

    assert result.response is not None
    assert result.response.content == "fallback answer"
    assert result.turn.status == "completed"
    assert result.turn.finish_reason == "fallback_model_completed"
    assert [attempt.status for attempt in result.turn.model_attempts] == [
        "failed",
        "success",
    ]
    assert [attempt.model_ref for attempt in result.turn.model_attempts] == [
        "source-primary:model-primary",
        "source-fallback:model-fallback",
    ]


def test_pipeline_resolves_profile_fallback_candidates(monkeypatch: Any) -> None:
    from apeiria.ai.model.catalog import chat as chat_module
    from apeiria.ai.model.routing import profile as profile_module
    from apeiria.ai.model.sources import service as source_module
    from apeiria.app.ai.pipeline import model_steps

    primary = _selected_model("primary", fallback_profile_id="profile-fallback")
    fallback = _selected_model("fallback")

    async def list_profiles() -> list[AIModelProfileDefinition]:
        return [primary.profile, fallback.profile]

    async def list_sources() -> list[AISourceDefinition]:
        return [primary.source, fallback.source]

    async def list_models() -> list[AIChatModelDefinition]:
        return [
            AIChatModelDefinition(
                model_id=primary.profile.model_id,
                source_id=primary.source.source_id,
                model_identifier=primary.resolved_model_name or "",
                display_name="Primary",
            ),
            AIChatModelDefinition(
                model_id=fallback.profile.model_id,
                source_id=fallback.source.source_id,
                model_identifier=fallback.resolved_model_name or "",
                display_name="Fallback",
            ),
        ]

    monkeypatch.setattr(
        profile_module.ai_model_profile_service,
        "list_profiles",
        list_profiles,
    )
    monkeypatch.setattr(source_module.ai_source_service, "list_sources", list_sources)
    monkeypatch.setattr(
        chat_module.ai_chat_model_service,
        "list_all_models",
        list_models,
    )

    candidates = asyncio.run(
        model_steps.select_pipeline_fallback_models(primary, limit=1)
    )

    assert [candidate.profile.profile_id for candidate in candidates] == [
        "profile-fallback"
    ]
    assert candidates[0].resolved_model_name == "model-fallback"


@dataclass
class _ToolService:
    observations: list[list[AIToolObservationResult]]
    allowed_tool_names: tuple[str, ...] = ("memory.query",)

    def __post_init__(self) -> None:
        self.calls: list[object] = []

    async def execute_tool_intents(
        self,
        *,
        request: object,
        intents: list[object],
    ) -> list[AIToolObservationResult]:
        del request
        self.calls.append(tuple(intents))
        return self.observations.pop(0)

    def build_tool_turns(
        self,
        observations: list[AIToolObservationResult],
    ) -> list[Any]:
        del observations
        return []

    def list_allowed_tools(self, _policy: AIToolPolicy) -> list[Any]:
        return [SimpleNamespace(name=name) for name in self.allowed_tool_names]

    @property
    def registry(self) -> Any:
        return _Registry()


class _Registry:
    def list_tools(self) -> list[Any]:
        return []


def _tool_request() -> ToolGatewayRequest:
    return ToolGatewayRequest(
        session_id="session-1",
        source_message_id="message-1",
        trace_id="trace-tools",
        message_text="use tools",
        policy=AIToolPolicy(execution_enabled=True),
        recalled_memories=(),
        relationship_context=None,
        current_time=__import__("datetime").datetime.now(
            __import__("datetime").timezone.utc
        ),
    )


def _tool_call(call_id: str, name: str = "memory_query") -> AIModelToolCall:
    return AIModelToolCall(
        tool_call_id=call_id,
        name=name,
        arguments={"query_text": "hello"},
    )


def test_tool_loop_records_final_response_finish_reason() -> None:
    selected = _selected_model("main")
    gateway = _Gateway(
        [
            _response(selected, "", tool_calls=(_tool_call("call-1"),)),
            _response(selected, "done"),
        ]
    )
    service = _ToolService(
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
            _tool_request(),
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
    selected = _selected_model("main")
    gateway = _Gateway(
        [
            _response(selected, "", tool_calls=(_tool_call("call-1"),)),
            _response(selected, "done"),
        ]
    )
    service = _ToolService(
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
            _tool_request(),
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
    selected = _selected_model("main")
    gateway = _Gateway(
        [
            _response(selected, "", tool_calls=(_tool_call("call-1"),)),
            _response(selected, "done"),
        ]
    )
    service = _ToolService(observations=[], allowed_tool_names=())
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            _tool_request(),
            messages=[],
            tools=(),
            selected=selected,
        )
    )

    assert service.calls == []
    assert result.tool_attempts[0].status == "error"
    assert "denied by policy" in result.tool_attempts[0].observation.content


def test_tool_loop_recovers_once_from_context_pressure() -> None:
    selected = _selected_model("main")
    long_observation = "- [memory.query] " + ("x" * 1200)
    gateway = _Gateway(
        [
            RuntimeError("context_length_exceeded api_key=secret-token"),
            _response(selected, "done"),
        ]
    )
    service = _ToolService(observations=[])
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            _tool_request(),
            messages=[
                AIModelMessage(
                    role="assistant",
                    content="",
                    tool_calls=(_tool_call("call-1"),),
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
    selected = _selected_model("main")
    long_observation = "- [memory.query] " + ("x" * 1200)
    gateway = _Gateway(
        [
            RuntimeError("context_length_exceeded token=secret-token"),
            RuntimeError("context_length_exceeded token=secret-token"),
        ]
    )
    service = _ToolService(observations=[])
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            _tool_request(),
            messages=[
                AIModelMessage(
                    role="assistant",
                    content="",
                    tool_calls=(_tool_call("call-1"),),
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
    selected = _selected_model("main")
    gateway = _Gateway([_response(selected, "done")])
    service = _ToolService(observations=[])
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            _tool_request(),
            messages=[
                AIModelMessage(
                    role="assistant",
                    content="",
                    tool_calls=(_tool_call("call-1"),),
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
    selected = _selected_model("main")
    gateway = _Gateway([_response(selected, "done")])
    service = _ToolService(observations=[])
    tool_gateway = ToolGateway(model_gateway=gateway, tool_service=service)

    result = asyncio.run(
        tool_gateway.run_tool_loop(
            _tool_request(),
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
    selected = _selected_model("main")
    gateway = _Gateway(
        [
            _response(selected, "", tool_calls=(_tool_call("call-1"),)),
            _response(selected, "", tool_calls=(_tool_call("call-2"),)),
            _response(selected, "final after max rounds"),
        ]
    )
    service = _ToolService(
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
            _tool_request(),
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
    selected = _selected_model("main")
    gateway = _Gateway(
        [
            _response(selected, "", tool_calls=(_tool_call("call-1"),)),
            _response(selected, ""),
        ]
    )
    service = _ToolService(
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
            _tool_request(),
            messages=[],
            tools=(),
            selected=selected,
            max_rounds=1,
        )
    )

    assert result.loop_finish_reason == "max_rounds_reached"
    assert result.final_response is not None
    assert result.final_response.tool_calls == (_tool_call("call-1"),)
    assert len(service.calls) == 1
    assert gateway.tool_calls[-1] == ()
    assert result.metadata["tool_loop_finalization_attempted"] is True
    assert result.metadata["tool_loop_finalization_succeeded"] is False
    assert result.metadata["tool_loop_finalization_error"] == "empty_response"


def test_tool_loop_truncates_prompt_visible_observation() -> None:
    selected = _selected_model("main")
    long_summary = "- [memory.query] " + ("x" * 200)
    gateway = _Gateway(
        [
            _response(selected, "", tool_calls=(_tool_call("call-1"),)),
            _response(selected, "done"),
        ]
    )
    service = _ToolService(
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
            _tool_request(),
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


def test_tool_loop_metadata_is_available_to_persistence() -> None:
    from apeiria.app.ai.pipeline import generation_steps
    from apeiria.app.ai.pipeline.persistence_steps import _agent_turn_meta

    selected = _selected_model("main")
    raw_payload = "raw-large-tool-output"
    original_observation_length = 4096
    turn = generation_steps._build_tool_loop_turn_result(
        trace_id="trace-tools",
        runtime_mode="message",
        skill_runtime=ToolGatewayResult(
            policy_text="",
            result_lines=(),
            turns=(),
            final_response=_response(selected, "done"),
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
        persisted["agent_turn_metadata"]["tool_loop_context_recovery_attempted"]
        is True
    )
    assert persisted["agent_turn_metadata"]["tool_loop_model_retry_count"] == 1
    attempt = persisted["agent_turn_tool_attempts"][0]
    assert attempt["observation_truncated"] is True
    assert attempt["observation_original_length"] == original_observation_length
    assert raw_payload not in str(persisted)
    assert "native_observation" not in attempt


def test_direct_generation_records_future_task_runtime_mode(monkeypatch: Any) -> None:
    from apeiria.app.ai.pipeline import generation_steps

    selected = _selected_model("main")
    captured_requests: list[Any] = []

    async def generate_model_turn(request: Any) -> AgentModelGenerationResult:
        captured_requests.append(request)
        response = _response(selected, "future answer")
        return AgentModelGenerationResult(
            response=response,
            selected=selected,
            turn=AgentTurnResult(
                trace_id=request.trace_id,
                runtime_mode=request.runtime_mode,
                status="completed",
                finish_reason="direct_model_completed",
                response=response,
                response_source=request.response_source,
            ),
        )

    async def select_fallbacks(
        _selected: AISelectedModel,
    ) -> tuple[AISelectedModel, ...]:
        return ()

    async def deliver_reply(
        _request: AIRuntimeReplyRequest,
        _reply_text: str,
    ) -> DeliveryOutcome:
        return DeliveryOutcome(delivered=True)

    monkeypatch.setattr(generation_steps, "generate_model_turn", generate_model_turn)
    monkeypatch.setattr(
        generation_steps,
        "select_pipeline_fallback_models",
        select_fallbacks,
    )
    monkeypatch.setattr(generation_steps, "record_context_usage", lambda *_, **__: None)
    monkeypatch.setattr(generation_steps, "deliver_generated_reply", deliver_reply)

    identity = ChatSessionIdentity(
        session_id="session-1",
        platform="test",
        bot_id="bot-1",
        scene_type="private",
        scene_id="user-1",
        subject_id=None,
    )
    request = AIRuntimeReplyRequest(
        identity=identity,
        message_text="future task",
        source_message_id=None,
        user_id="user-1",
        sender_id="bot-1",
        runtime_mode="future_task",
    )
    inputs = ReplyInputs(
        turns=[],
        conversation_summary=None,
        relationship_target=object(),
        model_target=AIModelBindingTarget(
            conversation_id="session-1",
            group_id=None,
            user_id="user-1",
        ),
        tool_policy=AIToolPolicy(),
        persona=None,
        recalled_memories=[],
        relationship_context=None,
        person_profile=(),
        allowed_tools=(),
        initiative_bias=0.0,
    )
    prep = ReplyPreparation(
        skill_runtime=ToolGatewayResult(policy_text="", result_lines=(), turns=()),
        selected=selected,
        skill_activation=None,
        pre_tool_task_class="reply_default",
    )
    social_decision = ReplyStrategyDecision(
        action="reply",
        should_speak=True,
        tool_mode="allow",
        reason_codes=(),
        reason_text="test",
        evidence={},
        decision_source="fallback",
    )

    result = asyncio.run(
        generation_steps._generate_direct(
            request=request,
            inputs=inputs,
            social_decision=social_decision,
            prep=prep,
            trace_id="trace-future",
        )
    )

    assert captured_requests[0].runtime_mode == "future_task"
    assert result.turn_result is not None
    assert result.turn_result.runtime_mode == "future_task"
    assert result.delivery_result == DeliveryOutcome(delivered=True)
