"""Dashboard routes — bot status overview."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from apeiria.i18n import t
from apeiria.runtime.context import get_current_runtime
from apeiria.webui.auth import require_control_panel
from apeiria.webui.schemas.models import (
    DashboardEventItem,
    DashboardEventsResponse,
    StatusResponse,
    WebUIBuildRunResponse,
    WebUIBuildStatusResponse,
)
from apeiria.webui.schemas.operations import OperationStatusResponse

router = APIRouter()
_RUNTIME_UNAVAILABLE_DETAIL = "Apeiria runtime control plane is unavailable."


def _require_runtime_control_plane() -> Any:
    runtime = get_current_runtime()
    if runtime is None or runtime.control_plane is None:
        raise HTTPException(
            status_code=503,
            detail=_RUNTIME_UNAVAILABLE_DETAIL,
        )
    return runtime.control_plane


@router.get("/status", response_model=StatusResponse)
async def get_status(
    _: Annotated[Any, Depends(require_control_panel)],
) -> StatusResponse:
    """Return the current dashboard status snapshot."""
    snapshot = await _require_runtime_control_plane().get_dashboard_status()
    return StatusResponse(
        status=snapshot.status,
        uptime=snapshot.uptime,
        plugins_count=snapshot.plugins_count,
        disabled_plugins_count=snapshot.disabled_plugins_count,
        groups_count=snapshot.groups_count,
        disabled_groups_count=snapshot.disabled_groups_count,
        access_rules_count=snapshot.access_rules_count,
        adapters=snapshot.adapters,
    )


@router.get("/events", response_model=DashboardEventsResponse)
async def get_events(
    _: Annotated[Any, Depends(require_control_panel)],
) -> DashboardEventsResponse:
    """Return recent warning and error events for the dashboard."""
    events = _require_runtime_control_plane().get_dashboard_events()
    return DashboardEventsResponse(
        items=[
            DashboardEventItem(
                timestamp=item.timestamp,
                level=item.level,
                source=item.source,
                message=item.message,
            )
            for item in events
        ]
    )


@router.get("/webui-build", response_model=WebUIBuildStatusResponse)
async def get_webui_build_status(
    _: Annotated[Any, Depends(require_control_panel)],
) -> WebUIBuildStatusResponse:
    status = _require_runtime_control_plane().get_web_ui_build_status()
    return WebUIBuildStatusResponse(
        is_built=status.is_built,
        is_stale=status.is_stale,
        can_build=status.can_build,
        build_tool=status.build_tool,
        detail=status.detail,
    )


@router.post("/webui-build", response_model=WebUIBuildRunResponse)
async def rebuild_webui(
    _: Annotated[Any, Depends(require_control_panel)],
) -> WebUIBuildRunResponse:
    try:
        status = await _require_runtime_control_plane().rebuild_web_ui()
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return WebUIBuildRunResponse(
        is_built=status.is_built,
        is_stale=status.is_stale,
        can_build=status.can_build,
        build_tool=status.build_tool,
        detail=status.detail,
        logs=status.logs,
    )


@router.post("/webui-build/stream")
async def rebuild_webui_stream(
    _: Annotated[Any, Depends(require_control_panel)],
) -> StreamingResponse:
    control_plane = _require_runtime_control_plane()
    status = control_plane.get_web_ui_build_status()
    if not status.can_build:
        raise HTTPException(
            status_code=400,
            detail=t("web_ui.dashboard.build_tool_unavailable"),
        )
    return StreamingResponse(
        control_plane.stream_web_ui_rebuild(),
        media_type="application/x-ndjson",
    )


@router.post("/restart", response_model=OperationStatusResponse)
async def restart_bot(
    _: Annotated[Any, Depends(require_control_panel)],
) -> OperationStatusResponse:
    _require_runtime_control_plane().schedule_restart()
    return OperationStatusResponse(detail=t("web_ui.dashboard.restart_scheduled"))
