"""Schema models for AI model usage diagnostics routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

if TYPE_CHECKING:
    from apeiria.ai.token_usage import AIModelUsageRecord, AIModelUsageSummary
    from apeiria.app.ai.diagnostics.usage import AIModelUsageTotals


class AIModelUsageTotalsItem(BaseModel):
    usage_available: bool = False
    call_count: int = 0
    measured_call_count: int = 0
    missing_usage_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cached_input_tokens: int = 0
    reasoning_tokens: int = 0
    audio_input_tokens: int = 0
    audio_output_tokens: int = 0


class AIModelUsageEventItem(BaseModel):
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
    measurement_source: str
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None
    cached_input_tokens: int | None = None
    reasoning_tokens: int | None = None
    audio_input_tokens: int | None = None
    audio_output_tokens: int | None = None
    provider_usage: dict[str, Any] | None = None
    provider_response_id: str | None = None
    finish_reason: str | None = None
    created_at: str


class AIModelUsageSummaryItem(BaseModel):
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


def to_ai_model_usage_totals_item(
    item: "AIModelUsageTotals",
) -> AIModelUsageTotalsItem:
    return AIModelUsageTotalsItem(
        usage_available=item.usage_available,
        call_count=item.call_count,
        measured_call_count=item.measured_call_count,
        missing_usage_count=item.missing_usage_count,
        input_tokens=item.input_tokens,
        output_tokens=item.output_tokens,
        total_tokens=item.total_tokens,
        cached_input_tokens=item.cached_input_tokens,
        reasoning_tokens=item.reasoning_tokens,
        audio_input_tokens=item.audio_input_tokens,
        audio_output_tokens=item.audio_output_tokens,
    )


def to_ai_model_usage_event_item(
    item: "AIModelUsageRecord",
) -> AIModelUsageEventItem:
    return AIModelUsageEventItem(
        usage_event_id=item.usage_event_id,
        trace_id=item.trace_id,
        session_id=item.session_id,
        runtime_mode=item.runtime_mode,
        response_source=item.response_source,
        source_id=item.source_id,
        model_name=item.model_name,
        operation=item.operation,
        attempt_index=item.attempt_index,
        status=item.status,
        usage_available=item.usage_available,
        measurement_source=item.measurement_source,
        input_tokens=item.input_tokens,
        output_tokens=item.output_tokens,
        total_tokens=item.total_tokens,
        cached_input_tokens=item.cached_input_tokens,
        reasoning_tokens=item.reasoning_tokens,
        audio_input_tokens=item.audio_input_tokens,
        audio_output_tokens=item.audio_output_tokens,
        provider_usage=item.provider_usage,
        provider_response_id=item.provider_response_id,
        finish_reason=item.finish_reason,
        created_at=item.created_at.isoformat(),
    )


def to_ai_model_usage_summary_item(
    item: "AIModelUsageSummary",
) -> AIModelUsageSummaryItem:
    return AIModelUsageSummaryItem(
        group_key=item.group_key,
        call_count=item.call_count,
        measured_call_count=item.measured_call_count,
        missing_usage_count=item.missing_usage_count,
        input_tokens=item.input_tokens,
        output_tokens=item.output_tokens,
        total_tokens=item.total_tokens,
        cached_input_tokens=item.cached_input_tokens,
        reasoning_tokens=item.reasoning_tokens,
        audio_input_tokens=item.audio_input_tokens,
        audio_output_tokens=item.audio_output_tokens,
    )


__all__ = [
    "AIModelUsageEventItem",
    "AIModelUsageSummaryItem",
    "AIModelUsageTotalsItem",
    "to_ai_model_usage_event_item",
    "to_ai_model_usage_summary_item",
    "to_ai_model_usage_totals_item",
]
