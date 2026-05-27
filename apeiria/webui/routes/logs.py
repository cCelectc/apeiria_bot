"""Log routes — history + WebSocket real-time log streaming."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    HTTPException,
    Query,
    WebSocket,
    WebSocketDisconnect,
)

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


def _ensure_log_stream_session(session: Any) -> None:
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
    from apeiria.log import HistoryLogFilters, load_history_logs

    items, has_more, total = load_history_logs(
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
    from apeiria.log import load_history_log_sources

    return LogSourcesResponse(items=load_history_log_sources())


@router.websocket("/ws")
async def log_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time log streaming.

    Browser sessions authenticate through the HttpOnly session cookie.
    """
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
            await websocket.send_json((await subscription.queue.get()).to_payload())
    except WebSocketDisconnect:
        pass
    finally:
        log_buffer.unsubscribe(subscription)
