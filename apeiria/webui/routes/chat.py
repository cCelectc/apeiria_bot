"""Web UI chat routes."""

from __future__ import annotations

import asyncio
import json
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Request, WebSocket
from fastapi.responses import FileResponse, RedirectResponse, StreamingResponse
from pydantic import BaseModel

from apeiria.i18n import t
from apeiria.webchat import (
    ChatAssetFileMissingError,
    ChatAssetNotFoundError,
    ChatAuthError,
    chat_gateway_service,
)
from apeiria.webchat.transport import serve_chat_websocket
from apeiria.webui.auth import require_auth, require_connection_auth

router = APIRouter()


def _ensure_chat_session(session: object | None) -> None:
    if session is not None:
        return
    raise ChatAuthError(t("web_ui.auth.permission_denied"))


@router.get("/assets/{asset_id}", response_model=None)
async def get_chat_asset(
    asset_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> FileResponse | RedirectResponse:
    try:
        asset = chat_gateway_service.get_asset(asset_id)
    except ChatAssetNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.chat.asset_not_found"),
        ) from None
    except ChatAssetFileMissingError:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.chat.asset_file_missing"),
        ) from None

    if asset.remote_url:
        return RedirectResponse(asset.remote_url)
    if asset.local_path is None:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.chat.asset_file_missing"),
        )
    return FileResponse(
        asset.local_path,
        media_type=asset.content_type,
        filename=asset.file_name,
    )


@router.websocket("/ws")
async def chat_websocket(websocket: WebSocket) -> None:
    try:
        session = await require_connection_auth(websocket)
        _ensure_chat_session(session)
    except (ChatAuthError, HTTPException):
        await websocket.close(code=4001, reason="Unauthorized")
        return
    await serve_chat_websocket(websocket, session)


# --- SSE Chat endpoints ---


class SendMessageBody(BaseModel):
    session_id: str
    message_id: str
    segments: list[dict]


@router.post("/messages")
async def send_message(
    body: SendMessageBody,
    _req: Request,
    _auth: Annotated[Any, Depends(require_auth)],
) -> dict[str, str | bool]:
    return {"message_id": body.message_id, "accepted": True}


def _sse_event(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"


async def _sse_stream() -> Any:
    """SSE event stream for chat replies (test implementation)."""
    test_reply = "你好！这是一条测试回复。SSE 聊天端点已就绪。"
    sid = "test-session"
    stream_id = "test-stream-1"

    yield _sse_event(
        {
            "type": "reply.partial.start",
            "session_id": sid,
            "trace_id": "test-trace",
            "stream_id": stream_id,
        }
    )
    await asyncio.sleep(0.2)

    for char in test_reply:
        yield _sse_event(
            {
                "type": "reply.partial.delta",
                "session_id": sid,
                "trace_id": "test-trace",
                "stream_id": stream_id,
                "content_delta": char,
            }
        )
        await asyncio.sleep(0.03)

    await asyncio.sleep(0.1)
    yield _sse_event(
        {
            "type": "reply.partial.complete",
            "session_id": sid,
            "trace_id": "test-trace",
            "stream_id": stream_id,
            "message_id": "test-msg-1",
        }
    )


@router.get("/stream")
async def chat_stream(
    _req: Request,
    _auth: Annotated[Any, Depends(require_auth)],
) -> StreamingResponse:
    return StreamingResponse(
        _sse_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# --- Session management (REST) ---


class SessionInfo(BaseModel):
    session_id: str
    target_user_id: str


@router.get("/sessions", response_model=list[SessionInfo])
async def list_sessions(
    _: Annotated[Any, Depends(require_auth)],
) -> list[SessionInfo]:
    return []


@router.post("/sessions", response_model=SessionInfo, status_code=201)
async def create_session(
    _: Annotated[Any, Depends(require_auth)],
) -> SessionInfo:
    import uuid

    sid = uuid.uuid4().hex[:12]
    return SessionInfo(session_id=sid, target_user_id="")


@router.delete("/sessions/{session_id}", status_code=204)
async def delete_session(
    session_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> None:
    pass
