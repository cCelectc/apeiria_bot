"""Log routes — history + SSE real-time log streaming."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    Request,
    WebSocket,
    WebSocketDisconnect,
)
from fastapi.responses import StreamingResponse

from apeiria.webui.auth import (
    require_auth,
    require_connection_auth,
)
from apeiria.webui.schemas.models import (
    LogHistoryQuery,
    LogHistoryResponse,
    LogItem,
    LogSourcesResponse,
)

router = APIRouter()


def _ensure_log_stream_session(session: object | None) -> None:
    if session is not None:
        return
    msg = "forbidden"
    raise ValueError(msg)


@router.get("/history", response_model=LogHistoryResponse)
async def get_log_history(
    _: Annotated[Any, Depends(require_auth)],
    before: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    filters: Annotated[LogHistoryQuery, Depends()] = LogHistoryQuery(),
) -> LogHistoryResponse:
    import asyncio as _asyncio

    from apeiria.log import HistoryLogFilters, load_history_logs

    items, has_more, total = await _asyncio.to_thread(
        load_history_logs,
        before=before,
        limit=limit,
        filters=HistoryLogFilters(**filters.model_dump()),
    )
    return LogHistoryResponse(
        items=[
            LogItem(
                timestamp=item.timestamp,
                level=item.level,
                source=item.source,
                message=item.message,
                raw=item.raw,
                extra=item.extra,
            )
            for item in items
        ],
        total=total,
        before=before,
        next_before=before + len(items) if has_more else None,
        has_more=has_more,
    )


@router.get("/sources", response_model=LogSourcesResponse)
async def get_log_sources(
    _: Annotated[Any, Depends(require_auth)],
) -> LogSourcesResponse:
    import asyncio as _asyncio

    from apeiria.log import load_history_log_sources

    return LogSourcesResponse(
        items=await _asyncio.to_thread(load_history_log_sources),
    )


@router.websocket("/ws")
async def log_websocket(websocket: WebSocket) -> None:
    await websocket.accept()

    try:
        session = await require_connection_auth(websocket)
        _ensure_log_stream_session(session)
    except (HTTPException, ValueError):
        await websocket.close(code=4001, reason="Unauthorized")
        return

    from apeiria.log import log_buffer

    subscription = log_buffer.subscribe()
    try:
        while True:
            await websocket.send_json(
                (await subscription.queue.get()).to_payload(),
            )
    except WebSocketDisconnect:
        pass
    finally:
        log_buffer.unsubscribe(subscription)


@router.get("/stream")
async def log_sse_stream(
    req: Request,
    _: Annotated[Any, Depends(require_auth)],
) -> StreamingResponse:
    """SSE endpoint for real-time log streaming."""
    from apeiria.log import log_buffer

    async def event_stream() -> Any:
        subscription = log_buffer.subscribe()
        try:
            while True:
                if await req.is_disconnected():
                    break
                try:
                    entry = await asyncio.wait_for(
                        subscription.queue.get(),
                        timeout=30,
                    )
                    yield f"data: {json.dumps(entry.to_payload())}\n\n"
                except asyncio.TimeoutError:
                    yield ": keepalive\n\n"
        finally:
            log_buffer.unsubscribe(subscription)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
