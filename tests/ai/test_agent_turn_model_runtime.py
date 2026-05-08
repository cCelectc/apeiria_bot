from __future__ import annotations

import asyncio
from typing import Any

from apeiria.ai.model import (
    AIChatModelDefinition,
    AIModelProfileDefinition,
    AISourceDefinition,
)
from apeiria.app.ai.agent_turn import (
    AgentModelGenerationRequest,
    AgentTurnModelRuntime,
    AgentTurnResult,
)
from tests.ai.agent_turn_helpers import (
    ModelInvokerStub,
    model_response,
    selected_model,
    stream_delta,
    stream_final,
    stream_start,
)


class ProviderConfigError(RuntimeError):
    pass


class UpstreamError(RuntimeError):
    def __init__(self, message: str, *, status_code: int) -> None:
        super().__init__(message)
        self.status_code = status_code


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
    selected = selected_model("main")
    invoker = ModelInvokerStub([model_response(selected, "hello")])
    runtime = AgentTurnModelRuntime(model_invoker=invoker)

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
    selected = selected_model("main")
    invoker = ModelInvokerStub([model_response(selected, "")])
    runtime = AgentTurnModelRuntime(model_invoker=invoker)

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
    selected = selected_model("main")
    invoker = ModelInvokerStub([RuntimeError("bad api_key=secret-token failed")])
    runtime = AgentTurnModelRuntime(model_invoker=invoker)

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


def test_model_runtime_classifies_configuration_error() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub([ProviderConfigError("missing api_key=secret-token")])
    runtime = AgentTurnModelRuntime(model_invoker=invoker)

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-config",
                session_id="session-1",
                runtime_mode="message",
                selected=selected,
                prompt="Say hello",
            )
        )
    )

    assert result.response is None
    assert result.turn.finish_reason == "configuration_error"
    assert result.turn.model_attempts[0].reason == "configuration_error"
    assert "secret-token" not in (result.turn.model_attempts[0].diagnostic or "")


def test_model_runtime_classifies_timeout() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub([TimeoutError("request timed out")])
    runtime = AgentTurnModelRuntime(model_invoker=invoker)

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-timeout",
                session_id="session-1",
                runtime_mode="message",
                selected=selected,
                prompt="Say hello",
            )
        )
    )

    assert result.response is None
    assert result.turn.finish_reason == "model_timeout"
    assert result.turn.model_attempts[0].reason == "model_timeout"


def test_model_runtime_classifies_temporary_upstream_error() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub([UpstreamError("upstream unavailable", status_code=503)])
    runtime = AgentTurnModelRuntime(model_invoker=invoker)

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-temp",
                session_id="session-1",
                runtime_mode="message",
                selected=selected,
                prompt="Say hello",
            )
        )
    )

    assert result.response is None
    assert result.turn.finish_reason == "upstream_temporary_error"
    assert result.turn.model_attempts[0].reason == "upstream_temporary_error"


def test_model_runtime_classifies_permanent_upstream_error() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub([UpstreamError("unauthorized", status_code=401)])
    runtime = AgentTurnModelRuntime(model_invoker=invoker)

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-perm",
                session_id="session-1",
                runtime_mode="message",
                selected=selected,
                prompt="Say hello",
            )
        )
    )

    assert result.response is None
    assert result.turn.finish_reason == "upstream_permanent_error"
    assert result.turn.model_attempts[0].reason == "upstream_permanent_error"


def test_model_runtime_unknown_provider_error_uses_generic_reason() -> None:
    selected = selected_model("main")
    invoker = ModelInvokerStub([RuntimeError("provider exploded")])
    runtime = AgentTurnModelRuntime(model_invoker=invoker)

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-unknown",
                session_id="session-1",
                runtime_mode="message",
                selected=selected,
                prompt="Say hello",
            )
        )
    )

    assert result.response is None
    assert result.turn.finish_reason == "model_error"
    assert result.turn.model_attempts[0].reason == "model_error"


def test_model_runtime_uses_configured_fallback_candidate() -> None:
    primary = selected_model("primary", fallback_profile_id="profile-fallback")
    fallback = selected_model("fallback")
    invoker = ModelInvokerStub(
        [
            RuntimeError("primary failed"),
            model_response(fallback, "fallback answer"),
        ]
    )
    runtime = AgentTurnModelRuntime(model_invoker=invoker)

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
    assert result.turn.model_attempts[0].reason == "model_error"
    assert [attempt.model_ref for attempt in result.turn.model_attempts] == [
        "source-primary:model-primary",
        "source-fallback:model-fallback",
    ]


def test_model_runtime_preserves_fallback_after_temporary_error() -> None:
    primary = selected_model("primary", fallback_profile_id="profile-fallback")
    fallback = selected_model("fallback")
    invoker = ModelInvokerStub(
        [
            UpstreamError("try again later", status_code=503),
            model_response(fallback, "fallback answer"),
        ]
    )
    runtime = AgentTurnModelRuntime(model_invoker=invoker)

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-temp-fallback",
                session_id="session-1",
                runtime_mode="message",
                selected=primary,
                prompt="Say hello",
                fallback_models=(fallback,),
            )
        )
    )

    assert result.response is not None
    assert result.turn.finish_reason == "fallback_model_completed"
    assert result.turn.model_attempts[0].reason == "upstream_temporary_error"
    assert result.turn.model_attempts[1].status == "success"


def test_model_runtime_exposes_direct_capability_degradations() -> None:
    selected = selected_model("main")
    response = model_response(selected, "hello")
    response = type(response)(
        source_id=response.source_id,
        model_name=response.model_name,
        content=response.content,
        provider_data={
            "apeiria_degradations": [
                {
                    "kind": "tools_omitted",
                    "reason": "optional_tools_unsupported",
                    "detail": "model lacks tool calling",
                    "metadata": {"tool_count": 1},
                }
            ]
        },
    )
    invoker = ModelInvokerStub([response])
    runtime = AgentTurnModelRuntime(model_invoker=invoker)

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-degraded",
                session_id="session-1",
                runtime_mode="message",
                selected=selected,
                prompt="Say hello",
                response_source="direct",
            )
        )
    )

    assert result.turn.metadata["capability_degradations"] == [
        {
            "kind": "tools_omitted",
            "reason": "optional_tools_unsupported",
            "detail": "model lacks tool calling",
            "metadata": {"tool_count": 1},
        }
    ]


def test_model_runtime_streams_direct_reply_and_records_final_response() -> None:
    selected = selected_model("main", supports_streaming=True)
    response = model_response(selected, "hello world")
    stream_events = [
        stream_start(selected, stream_id="stream-1"),
        stream_delta(selected, "hello ", stream_id="stream-1"),
        stream_delta(selected, "world", stream_id="stream-1"),
        stream_final(selected, response, stream_id="stream-1"),
    ]
    invoker = ModelInvokerStub([stream_events])
    runtime = AgentTurnModelRuntime(model_invoker=invoker)
    captured_events: list[object] = []

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-stream",
                session_id="session-1",
                runtime_mode="message",
                selected=selected,
                prompt="Say hello",
                response_source="direct",
                stream_sink=captured_events.append,
            )
        )
    )

    assert result.response is response
    assert result.turn.status == "completed"
    assert result.turn.finish_reason == "direct_model_stream_completed"
    assert invoker.stream_calls == [selected]
    assert invoker.calls == []
    assert captured_events == stream_events
    assert result.turn.metadata["streaming"] == {
        "status": "completed",
        "stream_id": "stream-1",
        "event_count": 4,
    }


def test_model_runtime_does_not_commit_partial_text_after_stream_failure() -> None:
    selected = selected_model("main", supports_streaming=True)
    invoker = ModelInvokerStub([RuntimeError("stream failed after partial text")])
    runtime = AgentTurnModelRuntime(model_invoker=invoker)
    captured_events: list[object] = []

    result = asyncio.run(
        runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-stream-fail",
                session_id="session-1",
                runtime_mode="message",
                selected=selected,
                prompt="Say hello",
                response_source="direct",
                stream_sink=captured_events.append,
            )
        )
    )

    assert result.response is None
    assert result.turn.status == "failed"
    assert result.turn.finish_reason == "model_error"
    assert result.turn.model_attempts[0].status == "failed"
    assert result.turn.model_attempts[0].reason == "model_error"


def test_runtime_planning_resolves_profile_fallback_candidates(
    monkeypatch: Any,
) -> None:
    from apeiria.ai.model.catalog import chat as chat_module
    from apeiria.ai.model.routing import profile as profile_module
    from apeiria.ai.model.sources import service as source_module
    from apeiria.app.ai.runtime.planning import model_selection as model_steps

    primary = selected_model("primary", fallback_profile_id="profile-fallback")
    fallback = selected_model("fallback")

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
                default_options={"max_tokens": 200},
                capability_metadata={"tool_calling": True},
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

    candidates = asyncio.run(model_steps.select_fallback_models(primary, limit=1))

    assert [candidate.profile.profile_id for candidate in candidates] == [
        "profile-fallback"
    ]
    assert candidates[0].resolved_model_name == "model-fallback"
    assert candidates[0].source_model is not None
    assert candidates[0].source_model.model_id == fallback.profile.model_id
    assert candidates[0].model_default_options == {"max_tokens": 200}
    assert candidates[0].resolved_capabilities.supports_tool_calling is True
