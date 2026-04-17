"""Log routes — history + WebSocket real-time log streaming."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import (
    APIRouter,
    Depends,
    Query,
    WebSocket,
    WebSocketDisconnect,
)

from apeiria.interfaces.http.auth import (
    require_control_panel,
    verify_auth_session_token,
)
from apeiria.interfaces.http.schemas.models import (
    LogHistoryQuery,
    LogHistoryResponse,
    LogItem,
    LogSourcesResponse,
)
from apeiria.shared.principal_roles import CAP_CONTROL_PANEL

router = APIRouter()


def _require_log_stream_claims(token: str) -> None:
    session = verify_auth_session_token(token)
    if not session.has_capability(CAP_CONTROL_PANEL):
        msg = "forbidden"
        raise ValueError(msg)


@router.get("/history", response_model=LogHistoryResponse)
async def get_log_history(
    _: Annotated[Any, Depends(require_control_panel)],
    before: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
    filters: Annotated[LogHistoryQuery, Depends()] = LogHistoryQuery(),
) -> LogHistoryResponse:
    from apeiria.infra.logging.service import HistoryLogFilters, load_history_logs

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
    _: Annotated[Any, Depends(require_control_panel)],
) -> LogSourcesResponse:
    from apeiria.infra.logging.service import load_history_log_sources

    return LogSourcesResponse(items=load_history_log_sources())


@router.websocket("/ws")
async def log_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for real-time log streaming.

    Client sends JWT token as first message for auth.
    """
    await websocket.accept()

    # Auth: first message must be JWT token
    try:
        token = await websocket.receive_text()
    except WebSocketDisconnect:
        return

    try:
        _require_log_stream_claims(token)
    except ValueError:
        await websocket.close(code=4001, reason="Unauthorized")
        return

    from apeiria.infra.logging.service import log_buffer

    subscription = log_buffer.subscribe()
    try:
        while True:
            await websocket.send_json((await subscription.queue.get()).to_payload())
    except WebSocketDisconnect:
        pass
    finally:
        log_buffer.unsubscribe(subscription)
