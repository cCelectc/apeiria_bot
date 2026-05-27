"""AI model usage diagnostics routes."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, Literal

from fastapi import APIRouter, Depends, Query

from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_auth

from .usage_schemas import (
    AIModelUsageEventItem,
    AIModelUsageSummaryItem,
    to_ai_model_usage_event_item,
    to_ai_model_usage_summary_item,
)

if TYPE_CHECKING:
    from datetime import datetime

router = APIRouter()

UsageGroupBy = Literal[
    "trace",
    "session",
    "source",
    "model",
    "response_source",
    "operation",
]


@router.get("/usage-events", response_model=list[AIModelUsageEventItem])
async def list_ai_usage_events(  # noqa: PLR0913
    _: Annotated[Any, Depends(require_auth)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    trace_id: Annotated[str | None, Query(min_length=1)] = None,
    session_id: Annotated[str | None, Query(min_length=1)] = None,
    source_id: Annotated[str | None, Query(min_length=1)] = None,
    model_name: Annotated[str | None, Query(min_length=1)] = None,
    response_source: Annotated[str | None, Query(min_length=1)] = None,
    operation: Annotated[str | None, Query(min_length=1)] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
) -> list[AIModelUsageEventItem]:
    records = await ai_application.diagnostics.list_usage_events(
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
    return [to_ai_model_usage_event_item(record) for record in records]


@router.get("/usage-summary", response_model=list[AIModelUsageSummaryItem])
async def summarize_ai_usage(  # noqa: PLR0913
    _: Annotated[Any, Depends(require_auth)],
    group_by: UsageGroupBy = "session",
    trace_id: Annotated[str | None, Query(min_length=1)] = None,
    session_id: Annotated[str | None, Query(min_length=1)] = None,
    source_id: Annotated[str | None, Query(min_length=1)] = None,
    model_name: Annotated[str | None, Query(min_length=1)] = None,
    response_source: Annotated[str | None, Query(min_length=1)] = None,
    operation: Annotated[str | None, Query(min_length=1)] = None,
    created_from: Annotated[datetime | None, Query()] = None,
    created_to: Annotated[datetime | None, Query()] = None,
) -> list[AIModelUsageSummaryItem]:
    summaries = await ai_application.diagnostics.summarize_usage(
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
    return [to_ai_model_usage_summary_item(summary) for summary in summaries]


__all__ = ["router"]
