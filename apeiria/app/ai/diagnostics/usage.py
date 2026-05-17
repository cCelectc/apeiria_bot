"""Read helpers for AI model usage diagnostics."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from apeiria.ai.token_usage import AIModelUsageRepository

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.ai.token_usage import (
        AIModelUsageGroupBy,
        AIModelUsageRecord,
        AIModelUsageSummary,
    )


@dataclass(frozen=True, slots=True)
class AIModelUsageTotals:
    """Aggregate model usage totals for one trace, session, or query."""

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

    @property
    def usage_available(self) -> bool:
        return self.measured_call_count > 0


class UsageDiagnosticsAdminMixin:
    """Expose AI model usage details and summaries for admin surfaces."""

    def __init__(
        self,
        *,
        usage_repository: AIModelUsageRepository | None = None,
    ) -> None:
        self._usage_repository = usage_repository or AIModelUsageRepository()

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
        created_from: "datetime | None" = None,
        created_to: "datetime | None" = None,
    ) -> list["AIModelUsageRecord"]:
        return self._usage_repository.list_usage_events(
            limit=limit,
            trace_id=trace_id,
            session_id=session_id,
            source_id=source_id,
            model_name=model_name,
            response_source=response_source,
            operation=operation,
            created_from=created_from,
            created_to=created_to,
        )

    async def summarize_usage(  # noqa: PLR0913
        self,
        *,
        group_by: "AIModelUsageGroupBy",
        trace_id: str | None = None,
        session_id: str | None = None,
        source_id: str | None = None,
        model_name: str | None = None,
        response_source: str | None = None,
        operation: str | None = None,
        created_from: "datetime | None" = None,
        created_to: "datetime | None" = None,
    ) -> list["AIModelUsageSummary"]:
        return self._usage_repository.summarize_usage(
            group_by=group_by,
            trace_id=trace_id,
            session_id=session_id,
            source_id=source_id,
            model_name=model_name,
            response_source=response_source,
            operation=operation,
            created_from=created_from,
            created_to=created_to,
        )

    async def usage_totals_for_trace(self, *, trace_id: str) -> AIModelUsageTotals:
        return _totals_from_summaries(
            self._usage_repository.summarize_usage(
                group_by="trace",
                trace_id=trace_id,
            )
        )

    async def usage_totals_for_session(self, *, session_id: str) -> AIModelUsageTotals:
        return _totals_from_summaries(
            self._usage_repository.summarize_usage(
                group_by="session",
                session_id=session_id,
            )
        )


def _totals_from_summaries(
    summaries: list["AIModelUsageSummary"],
) -> AIModelUsageTotals:
    if not summaries:
        return AIModelUsageTotals()
    return AIModelUsageTotals(
        call_count=sum(item.call_count for item in summaries),
        measured_call_count=sum(item.measured_call_count for item in summaries),
        missing_usage_count=sum(item.missing_usage_count for item in summaries),
        input_tokens=sum(item.input_tokens for item in summaries),
        output_tokens=sum(item.output_tokens for item in summaries),
        total_tokens=sum(item.total_tokens for item in summaries),
        cached_input_tokens=sum(item.cached_input_tokens for item in summaries),
        reasoning_tokens=sum(item.reasoning_tokens for item in summaries),
        audio_input_tokens=sum(item.audio_input_tokens for item in summaries),
        audio_output_tokens=sum(item.audio_output_tokens for item in summaries),
    )


__all__ = [
    "AIModelUsageTotals",
    "UsageDiagnosticsAdminMixin",
]
