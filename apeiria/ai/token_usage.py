"""Token usage normalization and persistence for AI model calls."""

from __future__ import annotations

import json
from contextvars import ContextVar
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal, Protocol
from uuid import uuid4

from sqlalchemy import text

from apeiria.db.engine import get_session

if TYPE_CHECKING:
    from apeiria.ai.model.routing.selection import AISelectedModel
    from apeiria.ai.model.sources.models import AISourceDefinition

AIModelUsageMeasurementSource = Literal["provider", "missing"]
AIModelUsageGroupBy = Literal[
    "trace",
    "session",
    "source",
    "model",
    "response_source",
    "operation",
]


@dataclass(frozen=True, slots=True)
class AIModelUsageRecordContext:
    """Runtime context for one completed provider response."""

    trace_id: str | None
    session_id: str
    runtime_mode: str
    response_source: str
    selected: "AISelectedModel"
    operation: str
    attempt_index: int
    status: str


class AIModelUsageRecorder(Protocol):
    """Protocol for runtime usage recording collaborators."""

    def record_model_usage(
        self,
        create_input: "AIModelUsageCreateInput",
    ) -> "AIModelUsageRecord | None":
        """Persist one normalized model usage event."""


_default_usage_recorder: ContextVar[AIModelUsageRecorder | None] = ContextVar(
    "apeiria_default_usage_recorder",
    default=None,
)


def get_default_usage_recorder() -> AIModelUsageRecorder | None:
    """Return the ambient default usage recorder, or None."""
    return _default_usage_recorder.get()


def set_default_usage_recorder(recorder: AIModelUsageRecorder) -> None:
    """Set the ambient default usage recorder."""
    _default_usage_recorder.set(recorder)


@dataclass(frozen=True, slots=True)
class NormalizedAIModelUsage:
    """Provider usage normalized into common token fields."""

    usage_available: bool
    measurement_source: AIModelUsageMeasurementSource
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    audio_input_tokens: int | None = None
    audio_output_tokens: int | None = None
    provider_usage: dict[str, object] | None = None


@dataclass(frozen=True, slots=True)
class AIModelUsageCreateInput:
    """Input for one durable AI model usage event."""

    trace_id: str
    session_id: str
    runtime_mode: str
    response_source: str
    source_id: str
    model_name: str
    operation: str
    attempt_index: int
    status: str
    usage: NormalizedAIModelUsage
    provider_response_id: str | None = None
    finish_reason: str | None = None
    created_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class AIModelUsageRecord:
    """One persisted model usage event."""

    usage_event_id: str
    trace_id: str
    session_id: str
    runtime_mode: str
    response_source: str
    source_id: str
    model_name: str
    operation: str
    attempt_index: int
    status: str
    usage_available: bool
    measurement_source: AIModelUsageMeasurementSource
    input_tokens: int | None
    output_tokens: int | None
    total_tokens: int | None
    cached_input_tokens: int | None
    reasoning_tokens: int | None
    audio_input_tokens: int | None
    audio_output_tokens: int | None
    provider_usage: dict[str, object] | None
    provider_response_id: str | None
    finish_reason: str | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class AIModelUsageSummary:
    """Aggregated usage for one grouping key."""

    group_key: str
    call_count: int
    measured_call_count: int
    missing_usage_count: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    cached_input_tokens: int
    reasoning_tokens: int
    audio_input_tokens: int
    audio_output_tokens: int


class AIModelUsageRepository:
    """Own SQL operations for AI model usage observability."""

    async def record_usage(
        self,
        create_input: AIModelUsageCreateInput,
    ) -> AIModelUsageRecord:
        event_id = f"model_usage_{uuid4().hex}"
        created_at = create_input.created_at or _utcnow()
        usage = create_input.usage
        async with get_session() as session:
            await session.execute(
                text("""
                INSERT INTO ai_model_usage_event (
                    usage_event_id,
                    trace_id,
                    session_id,
                    runtime_mode,
                    response_source,
                    source_id,
                    model_name,
                    operation,
                    attempt_index,
                    status,
                    usage_available,
                    measurement_source,
                    input_tokens,
                    output_tokens,
                    total_tokens,
                    cached_input_tokens,
                    reasoning_tokens,
                    audio_input_tokens,
                    audio_output_tokens,
                    provider_usage_json,
                    provider_response_id,
                    finish_reason,
                    created_at
                ) VALUES (
                    :usage_event_id, :trace_id, :session_id,
                    :runtime_mode, :response_source, :source_id,
                    :model_name, :operation, :attempt_index,
                    :status, :usage_available, :measurement_source,
                    :input_tokens, :output_tokens, :total_tokens,
                    :cached_input_tokens, :reasoning_tokens,
                    :audio_input_tokens, :audio_output_tokens,
                    :provider_usage_json, :provider_response_id,
                    :finish_reason, :created_at
                )
                """),
                {
                    "usage_event_id": event_id,
                    "trace_id": create_input.trace_id,
                    "session_id": create_input.session_id,
                    "runtime_mode": create_input.runtime_mode,
                    "response_source": create_input.response_source,
                    "source_id": create_input.source_id,
                    "model_name": create_input.model_name,
                    "operation": create_input.operation,
                    "attempt_index": create_input.attempt_index,
                    "status": create_input.status,
                    "usage_available": 1 if usage.usage_available else 0,
                    "measurement_source": usage.measurement_source,
                    "input_tokens": usage.input_tokens,
                    "output_tokens": usage.output_tokens,
                    "total_tokens": usage.total_tokens,
                    "cached_input_tokens": usage.cached_input_tokens,
                    "reasoning_tokens": usage.reasoning_tokens,
                    "audio_input_tokens": usage.audio_input_tokens,
                    "audio_output_tokens": usage.audio_output_tokens,
                    "provider_usage_json": _json_dumps(usage.provider_usage),
                    "provider_response_id": create_input.provider_response_id,
                    "finish_reason": create_input.finish_reason,
                    "created_at": _datetime_to_text(created_at),
                },
            )
            await session.commit()
        return AIModelUsageRecord(
            usage_event_id=event_id,
            trace_id=create_input.trace_id,
            session_id=create_input.session_id,
            runtime_mode=create_input.runtime_mode,
            response_source=create_input.response_source,
            source_id=create_input.source_id,
            model_name=create_input.model_name,
            operation=create_input.operation,
            attempt_index=create_input.attempt_index,
            status=create_input.status,
            usage_available=usage.usage_available,
            measurement_source=usage.measurement_source,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            total_tokens=usage.total_tokens,
            cached_input_tokens=usage.cached_input_tokens,
            reasoning_tokens=usage.reasoning_tokens,
            audio_input_tokens=usage.audio_input_tokens,
            audio_output_tokens=usage.audio_output_tokens,
            provider_usage=usage.provider_usage,
            provider_response_id=create_input.provider_response_id,
            finish_reason=create_input.finish_reason,
            created_at=created_at,
        )

    async def list_usage_events(  # noqa: PLR0913
        self,
        *,
        limit: int,
        trace_id: str | None = None,
        session_id: str | None = None,
        source_id: str | None = None,
        model_name: str | None = None,
        response_source: str | None = None,
        operation: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[AIModelUsageRecord]:
        where, params = _usage_filters(
            trace_id=trace_id,
            session_id=session_id,
            source_id=source_id,
            model_name=model_name,
            response_source=response_source,
            operation=operation,
            created_from=created_from,
            created_to=created_to,
        )
        params["_limit"] = min(max(limit, 1), 100)
        async with get_session() as session:
            result = await session.execute(
                text(
                    _SELECT_USAGE_FIELDS
                    + where
                    + " ORDER BY created_at DESC LIMIT :_limit"
                ),
                params,
            )
            rows = result.fetchall()
        return [row_to_usage_record(tuple(row)) for row in rows]

    async def summarize_usage(  # noqa: PLR0913
        self,
        *,
        group_by: AIModelUsageGroupBy,
        trace_id: str | None = None,
        session_id: str | None = None,
        source_id: str | None = None,
        model_name: str | None = None,
        response_source: str | None = None,
        operation: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
    ) -> list[AIModelUsageSummary]:
        group_column = _GROUP_BY_COLUMNS[group_by]
        where, params = _usage_filters(
            trace_id=trace_id,
            session_id=session_id,
            source_id=source_id,
            model_name=model_name,
            response_source=response_source,
            operation=operation,
            created_from=created_from,
            created_to=created_to,
        )
        async with get_session() as session:
            result = await session.execute(
                text(f"""
                SELECT
                    {group_column} AS group_key,
                    COUNT(*) AS call_count,
                    SUM(CASE WHEN usage_available = 1 THEN 1 ELSE 0 END)
                        AS measured_call_count,
                    SUM(CASE WHEN usage_available = 0 THEN 1 ELSE 0 END)
                        AS missing_usage_count,
                    COALESCE(SUM(input_tokens), 0) AS input_tokens,
                    COALESCE(SUM(output_tokens), 0) AS output_tokens,
                    COALESCE(SUM(total_tokens), 0) AS total_tokens,
                    COALESCE(SUM(cached_input_tokens), 0) AS cached_input_tokens,
                    COALESCE(SUM(reasoning_tokens), 0) AS reasoning_tokens,
                    COALESCE(SUM(audio_input_tokens), 0) AS audio_input_tokens,
                    COALESCE(SUM(audio_output_tokens), 0) AS audio_output_tokens
                FROM ai_model_usage_event
                {where}
                GROUP BY {group_column}
                ORDER BY total_tokens DESC, call_count DESC
                """),
                params,
            )
            rows = result.fetchall()
        return [
            AIModelUsageSummary(
                group_key=str(row[0]),
                call_count=int(row[1]),
                measured_call_count=int(row[2] or 0),
                missing_usage_count=int(row[3] or 0),
                input_tokens=int(row[4] or 0),
                output_tokens=int(row[5] or 0),
                total_tokens=int(row[6] or 0),
                cached_input_tokens=int(row[7] or 0),
                reasoning_tokens=int(row[8] or 0),
                audio_input_tokens=int(row[9] or 0),
                audio_output_tokens=int(row[10] or 0),
            )
            for row in rows
        ]


def build_source_usage_create_input(  # noqa: PLR0913
    *,
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
) -> AIModelUsageCreateInput:
    """Build usage input for source-level operations without turn context."""

    from apeiria.ai.model.sources.models import (
        resolve_adapter_kind_for_client_type,
    )

    adapter_kind = source.adapter_kind or resolve_adapter_kind_for_client_type(
        source.client_type
    )
    return AIModelUsageCreateInput(
        trace_id=trace_id or "",
        session_id=session_id or "",
        runtime_mode=runtime_mode,
        response_source=response_source or operation,
        source_id=source.source_id,
        model_name=model_name,
        operation=operation,
        attempt_index=attempt_index,
        status=status,
        usage=normalize_provider_usage(
            adapter_kind=adapter_kind,
            usage=_extract_response_usage(response),
        ),
        provider_response_id=None,
        finish_reason=None,
    )


def _extract_response_usage(response: object) -> dict[str, object] | None:
    usage = getattr(response, "usage", None)
    return usage if isinstance(usage, dict) else None


def normalize_provider_usage(
    *,
    adapter_kind: str,
    usage: dict[str, object] | None,
) -> NormalizedAIModelUsage:
    """Normalize a provider usage payload without estimating missing tokens."""

    if not usage:
        return NormalizedAIModelUsage(
            usage_available=False,
            measurement_source="missing",
        )
    if adapter_kind == "gemini_native":
        return _normalize_gemini_usage(usage)
    if adapter_kind == "ollama_native":
        return _normalize_ollama_usage(usage)
    if adapter_kind == "anthropic_compatible":
        return _normalize_anthropic_usage(usage)
    return _normalize_openai_usage(usage)


def _normalize_openai_usage(usage: dict[str, object]) -> NormalizedAIModelUsage:
    prompt_details = _dict_field(usage, "prompt_tokens_details")
    completion_details = _dict_field(usage, "completion_tokens_details")
    return NormalizedAIModelUsage(
        usage_available=True,
        measurement_source="provider",
        input_tokens=_non_negative_int(usage.get("prompt_tokens")),
        output_tokens=_non_negative_int(usage.get("completion_tokens")),
        total_tokens=_non_negative_int(usage.get("total_tokens")),
        cached_input_tokens=_non_negative_int(prompt_details.get("cached_tokens")),
        reasoning_tokens=_non_negative_int(completion_details.get("reasoning_tokens")),
        audio_input_tokens=_non_negative_int(prompt_details.get("audio_tokens")),
        audio_output_tokens=_non_negative_int(completion_details.get("audio_tokens")),
        provider_usage=dict(usage),
    )


def _normalize_anthropic_usage(usage: dict[str, object]) -> NormalizedAIModelUsage:
    input_tokens = _non_negative_int(usage.get("input_tokens"))
    output_tokens = _non_negative_int(usage.get("output_tokens"))
    cache_read = _non_negative_int(usage.get("cache_read_input_tokens")) or 0
    cache_create = _non_negative_int(usage.get("cache_creation_input_tokens")) or 0
    return NormalizedAIModelUsage(
        usage_available=True,
        measurement_source="provider",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=_sum_optional(input_tokens, output_tokens),
        cached_input_tokens=cache_read + cache_create,
        provider_usage=dict(usage),
    )


def _normalize_gemini_usage(usage: dict[str, object]) -> NormalizedAIModelUsage:
    return NormalizedAIModelUsage(
        usage_available=True,
        measurement_source="provider",
        input_tokens=_non_negative_int(usage.get("promptTokenCount")),
        output_tokens=_non_negative_int(usage.get("candidatesTokenCount")),
        total_tokens=_non_negative_int(usage.get("totalTokenCount")),
        cached_input_tokens=_non_negative_int(usage.get("cachedContentTokenCount")),
        reasoning_tokens=_non_negative_int(usage.get("thoughtsTokenCount")),
        provider_usage=dict(usage),
    )


def _normalize_ollama_usage(usage: dict[str, object]) -> NormalizedAIModelUsage:
    input_tokens = _non_negative_int(usage.get("prompt_eval_count"))
    output_tokens = _non_negative_int(usage.get("eval_count"))
    return NormalizedAIModelUsage(
        usage_available=True,
        measurement_source="provider",
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=_sum_optional(input_tokens, output_tokens),
        provider_usage=dict(usage),
    )


def _usage_filters(  # noqa: PLR0913
    *,
    trace_id: str | None,
    session_id: str | None,
    source_id: str | None,
    model_name: str | None,
    response_source: str | None,
    operation: str | None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
) -> tuple[str, dict[str, object]]:
    clauses: list[str] = []
    params: dict[str, object] = {}
    for column, value in (
        ("trace_id", trace_id),
        ("session_id", session_id),
        ("source_id", source_id),
        ("model_name", model_name),
        ("response_source", response_source),
        ("operation", operation),
    ):
        if value is not None:
            clauses.append(f"{column} = :{column}")
            params[column] = value
    if created_from is not None:
        clauses.append("created_at >= :created_from")
        params["created_from"] = _datetime_to_text(created_from)
    if created_to is not None:
        clauses.append("created_at <= :created_to")
        params["created_to"] = _datetime_to_text(created_to)
    return (" WHERE " + " AND ".join(clauses) if clauses else "", params)


def row_to_usage_record(row: tuple[object, ...]) -> AIModelUsageRecord:
    return AIModelUsageRecord(
        usage_event_id=str(row[0]),
        trace_id=str(row[1]),
        session_id=str(row[2]),
        runtime_mode=str(row[3]),
        response_source=str(row[4]),
        source_id=str(row[5]),
        model_name=str(row[6]),
        operation=str(row[7]),
        attempt_index=_row_int(row[8]),
        status=str(row[9]),
        usage_available=bool(row[10]),
        measurement_source=_measurement_source(row[11]),
        input_tokens=_optional_row_int(row[12]),
        output_tokens=_optional_row_int(row[13]),
        total_tokens=_optional_row_int(row[14]),
        cached_input_tokens=_optional_row_int(row[15]),
        reasoning_tokens=_optional_row_int(row[16]),
        audio_input_tokens=_optional_row_int(row[17]),
        audio_output_tokens=_optional_row_int(row[18]),
        provider_usage=_json_loads(row[19]),
        provider_response_id=None if row[20] is None else str(row[20]),
        finish_reason=None if row[21] is None else str(row[21]),
        created_at=_datetime_from_text(row[22]),
    )


def _measurement_source(value: object) -> AIModelUsageMeasurementSource:
    return "provider" if str(value) == "provider" else "missing"


def _dict_field(payload: dict[str, object], key: str) -> dict[str, object]:
    value = payload.get(key)
    return value if isinstance(value, dict) else {}


def _non_negative_int(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int) and value >= 0:
        return value
    return None


def _optional_row_int(value: object) -> int | None:
    return None if value is None else _row_int(value)


def _row_int(value: object) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value)
    if isinstance(value, float):
        return int(value)
    return int(str(value))


def _sum_optional(left: int | None, right: int | None) -> int | None:
    if left is None and right is None:
        return None
    return (left or 0) + (right or 0)


def _json_dumps(value: dict[str, object] | None) -> str | None:
    if value is None:
        return None
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _json_loads(value: object) -> dict[str, object] | None:
    if value is None:
        return None
    try:
        payload = json.loads(str(value))
    except json.JSONDecodeError:
        return None
    return payload if isinstance(payload, dict) else None


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def _datetime_to_text(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def _datetime_from_text(value: object) -> datetime:
    parsed = datetime.fromisoformat(str(value))
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


_SELECT_USAGE_FIELDS = """
SELECT
    usage_event_id,
    trace_id,
    session_id,
    runtime_mode,
    response_source,
    source_id,
    model_name,
    operation,
    attempt_index,
    status,
    usage_available,
    measurement_source,
    input_tokens,
    output_tokens,
    total_tokens,
    cached_input_tokens,
    reasoning_tokens,
    audio_input_tokens,
    audio_output_tokens,
    provider_usage_json,
    provider_response_id,
    finish_reason,
    created_at
FROM ai_model_usage_event
"""

_GROUP_BY_COLUMNS: dict[AIModelUsageGroupBy, str] = {
    "trace": "trace_id",
    "session": "session_id",
    "source": "source_id",
    "model": "model_name",
    "response_source": "response_source",
    "operation": "operation",
}

ai_model_usage_repository = AIModelUsageRepository()

__all__ = [
    "AIModelUsageCreateInput",
    "AIModelUsageGroupBy",
    "AIModelUsageMeasurementSource",
    "AIModelUsageRecord",
    "AIModelUsageRecordContext",
    "AIModelUsageRecorder",
    "AIModelUsageRepository",
    "AIModelUsageSummary",
    "NormalizedAIModelUsage",
    "ai_model_usage_repository",
    "build_source_usage_create_input",
    "get_default_usage_recorder",
    "normalize_provider_usage",
    "row_to_usage_record",
    "set_default_usage_recorder",
]
