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
    ModelGatewayStub,
    model_response,
    selected_model,
)


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
    gateway = ModelGatewayStub([model_response(selected, "hello")])
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
    selected = selected_model("main")
    gateway = ModelGatewayStub([model_response(selected, "")])
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
    selected = selected_model("main")
    gateway = ModelGatewayStub([RuntimeError("bad api_key=secret-token failed")])
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
    primary = selected_model("primary", fallback_profile_id="profile-fallback")
    fallback = selected_model("fallback")
    gateway = ModelGatewayStub(
        [
            RuntimeError("primary failed"),
            model_response(fallback, "fallback answer"),
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

