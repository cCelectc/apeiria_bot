from __future__ import annotations

import asyncio
from typing import Any

from apeiria.ai.model.catalog.models import AIChatModelDefinition
from apeiria.ai.model.routing.models import AIModelProfileDefinition
from apeiria.ai.model.routing.selection import AISelectedModel
from apeiria.ai.model.runtime.adapter import AIModelGenerateResponse
from apeiria.ai.model.sources.models import AISourceDefinition
from apeiria.app.ai.agent_turn.model_runtime import AgentTurnModelRuntime
from apeiria.app.ai.agent_turn.models import AgentModelGenerationRequest

_PRIMARY_UNAVAILABLE = "primary unavailable"


def test_model_runtime_attempt_records_cover_route_fallbacks() -> None:
    recorder = _UsageRecorder()
    runtime = AgentTurnModelRuntime(
        model_invoker=_FailThenSucceedInvoker(),
        usage_recorder=recorder,
    )

    async def scenario() -> None:
        result = await runtime.generate(
            AgentModelGenerationRequest(
                trace_id="trace-1",
                session_id="session-1",
                runtime_mode="normal",
                selected=_selected("profile-primary", "model-primary", "gpt-primary"),
                fallback_models=(
                    _selected("profile-fallback", "model-fallback", "gpt-fallback"),
                ),
            )
        )
        assert result.turn.status == "completed"
        assert result.turn.finish_reason == "fallback_model_completed"
        assert [
            (attempt.attempt_index, attempt.model_ref, attempt.status)
            for attempt in result.turn.model_attempts
        ] == [
            (1, "source-1:gpt-primary", "failed"),
            (2, "source-1:gpt-fallback", "success"),
        ]
        assert recorder.records == [
            ("source-1:gpt-fallback", 2, "success"),
        ]

    asyncio.run(scenario())


class _FailThenSucceedInvoker:
    async def generate_text(self, *, selected: AISelectedModel, **_: Any) -> object:
        if selected.profile.profile_id == "profile-primary":
            raise RuntimeError(_PRIMARY_UNAVAILABLE)
        return AIModelGenerateResponse(
            source_id=selected.source.source_id,
            model_name=selected.resolved_model_name or "",
            content="fallback response",
        )


class _UsageRecorder:
    def __init__(self) -> None:
        self.records: list[tuple[str, int, str]] = []

    def record_model_usage(self, create_input: Any) -> object:
        self.records.append(
            (
                f"{create_input.source_id}:{create_input.model_name}",
                int(create_input.attempt_index),
                str(create_input.status),
            )
        )
        return object()


def _selected(
    profile_id: str,
    model_id: str,
    model_identifier: str,
) -> AISelectedModel:
    return AISelectedModel(
        source=_source(),
        profile=AIModelProfileDefinition(
            profile_id=profile_id,
            name=profile_id,
            model_id=model_id,
            task_class="reply_default",
            priority=10,
            enabled=True,
        ),
        resolved_model_name=model_identifier,
        source_model=AIChatModelDefinition(
            model_id=model_id,
            source_id="source-1",
            model_identifier=model_identifier,
            display_name=model_identifier,
            enabled=True,
        ),
    )


def _source() -> AISourceDefinition:
    return AISourceDefinition(
        source_id="source-1",
        name="Primary",
        capability_type="chat_completion",
        client_type="openai",
        preset_type="openai_compatible",
        api_base=None,
        enabled=True,
        adapter_kind="openai_compatible",
    )
