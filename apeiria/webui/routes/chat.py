"""Web UI chat routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, WebSocket
from fastapi.responses import FileResponse, RedirectResponse

from apeiria.access.principal_roles import CAP_CONTROL_PANEL
from apeiria.chat import (
    ChatAssetFileMissingError,
    ChatAssetNotFoundError,
    ChatAuthError,
    chat_gateway_service,
)
from apeiria.chat.transport import serve_chat_websocket
from apeiria.i18n import t
from apeiria.webui.auth import (
    require_control_panel,
    verify_auth_session_token,
)

router = APIRouter()


@router.get("/assets/{asset_id}", response_model=None)
async def get_chat_asset(
    asset_id: str,
    _: Annotated[Any, Depends(require_control_panel)],
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
    def _verify_admin_token(token: str):
        session = verify_auth_session_token(token)
        if not session.has_capability(CAP_CONTROL_PANEL):
            raise ChatAuthError(t("web_ui.auth.permission_denied"))
        return session

    await serve_chat_websocket(websocket, _verify_admin_token)
