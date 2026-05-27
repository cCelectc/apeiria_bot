"""AI runtime trace inspection routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from apeiria.app.ai import ai_application
from apeiria.webui.auth import require_auth

from .traces_schemas import AITurnTraceItem, to_ai_turn_trace_item

router = APIRouter()


@router.get("/traces", response_model=list[AITurnTraceItem])
async def list_ai_turn_traces(  # noqa: PLR0913
    _: Annotated[Any, Depends(require_auth)],
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    trace_id: Annotated[str | None, Query(min_length=1)] = None,
    session_id: Annotated[str | None, Query(min_length=1)] = None,
    runtime_mode: Annotated[str | None, Query(min_length=1)] = None,
    terminal_status: Annotated[str | None, Query(min_length=1)] = None,
    commit_status: Annotated[str | None, Query(min_length=1)] = None,
) -> list[AITurnTraceItem]:
    records = await ai_application.diagnostics.list_turn_traces(
        limit=limit,
        trace_id=trace_id,
        session_id=session_id,
        runtime_mode=runtime_mode,
        terminal_status=terminal_status,
        commit_status=commit_status,
    )
    return [
        to_ai_turn_trace_item(
            record,
            usage=await ai_application.diagnostics.usage_totals_for_trace(
                trace_id=record.trace_id
            ),
        )
        for record in records
    ]


@router.get("/traces/{trace_id}", response_model=AITurnTraceItem)
async def get_ai_turn_trace(
    trace_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> AITurnTraceItem:
    record = await ai_application.diagnostics.get_turn_trace(trace_id=trace_id)
    if record is None:
        raise HTTPException(status_code=404, detail="trace_not_found")
    usage = await ai_application.diagnostics.usage_totals_for_trace(trace_id=trace_id)
    usage_events = await ai_application.diagnostics.list_usage_events(
        limit=100,
        trace_id=trace_id,
    )
    return to_ai_turn_trace_item(
        record,
        usage=usage,
        usage_events=usage_events,
    )


__all__ = ["router"]
