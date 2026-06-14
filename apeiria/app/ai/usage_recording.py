"""Runtime-facing AI model usage recording helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

from nonebot.log import logger

from apeiria.ai.model.sources.models import resolve_adapter_kind_for_client_type
from apeiria.ai.token_usage import (
    AIModelUsageCreateInput,
    AIModelUsageRecordContext,
    AIModelUsageRecorder,
    AIModelUsageRepository,
    build_source_usage_create_input,
    normalize_provider_usage,
    set_default_usage_recorder,
)

if TYPE_CHECKING:
    from apeiria.ai.model.runtime.adapter import AIModelGenerateResponse
    from apeiria.ai.model.sources.models import AISourceDefinition
    from apeiria.ai.token_usage import AIModelUsageRecord


class RepositoryAIModelUsageRecorder:
    """Normalize provider usage and persist it through the usage repository."""

    def __init__(self, repository: AIModelUsageRepository | None = None) -> None:
        self._repository = repository or AIModelUsageRepository()

    def record_model_usage(
        self,
        create_input: AIModelUsageCreateInput,
    ) -> "AIModelUsageRecord":
        return self._repository.record_usage(create_input)


class NoopAIModelUsageRecorder:
    """Test-friendly recorder that intentionally drops usage events."""

    def record_model_usage(
        self,
        create_input: AIModelUsageCreateInput,
    ) -> None:
        del create_input


def build_model_usage_create_input(
    *,
    context: AIModelUsageRecordContext,
    response: "AIModelGenerateResponse",
) -> AIModelUsageCreateInput:
    """Build one normalized usage event input from runtime context."""

    selected = context.selected
    adapter_kind = selected.source.adapter_kind or resolve_adapter_kind_for_client_type(
        selected.source.client_type
    )
    return AIModelUsageCreateInput(
        trace_id=context.trace_id or "",
        session_id=context.session_id,
        runtime_mode=context.runtime_mode,
        response_source=context.response_source,
        source_id=selected.source.source_id,
        model_name=selected.resolved_model_name or response.model_name,
        operation=context.operation,
        attempt_index=context.attempt_index,
        status=context.status,
        usage=normalize_provider_usage(
            adapter_kind=adapter_kind,
            usage=response.usage,
        ),
        provider_response_id=response.response_id,
        finish_reason=response.finish_reason,
    )


def record_model_usage_safely(
    *,
    recorder: AIModelUsageRecorder | None,
    context: AIModelUsageRecordContext,
    response: "AIModelGenerateResponse",
) -> None:
    """Record usage without allowing observability failures to break replies."""

    if recorder is None:
        return
    create_input = build_model_usage_create_input(
        context=context,
        response=response,
    )
    try:
        recorder.record_model_usage(create_input)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "AI model usage recording failed trace_id={} session_id={} "
            "response_source={} attempt_index={} error={}",
            create_input.trace_id,
            create_input.session_id,
            create_input.response_source,
            create_input.attempt_index,
            str(exc)[:200],
        )


def record_source_usage_safely(  # noqa: PLR0913
    *,
    recorder: AIModelUsageRecorder | None,
    source: "AISourceDefinition",
    model_name: str,
    operation: str,
    response: object,
    trace_id: str | None = None,
    session_id: str | None = None,
    runtime_mode: str = "model_operation",
    response_source: str | None = None,
    attempt_index: int = 1,
    status: str = "success",
) -> None:
    """Record source operation usage without breaking model calls."""

    if recorder is None:
        return
    create_input = build_source_usage_create_input(
        source=source,
        model_name=model_name,
        operation=operation,
        response=response,
        trace_id=trace_id,
        session_id=session_id,
        runtime_mode=runtime_mode,
        response_source=response_source,
        attempt_index=attempt_index,
        status=status,
    )
    try:
        recorder.record_model_usage(create_input)
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "AI source usage recording failed source_id={} model_name={} "
            "operation={} error={}",
            create_input.source_id,
            create_input.model_name,
            create_input.operation,
            str(exc)[:200],
        )


ai_model_usage_recorder = RepositoryAIModelUsageRecorder()

set_default_usage_recorder(ai_model_usage_recorder)

__all__ = [
    "AIModelUsageRecordContext",
    "AIModelUsageRecorder",
    "NoopAIModelUsageRecorder",
    "RepositoryAIModelUsageRecorder",
    "ai_model_usage_recorder",
    "build_model_usage_create_input",
    "build_source_usage_create_input",
    "record_model_usage_safely",
    "record_source_usage_safely",
]
