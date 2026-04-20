"""Dashboard routes — bot status overview."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from apeiria.environment import environment_service
from apeiria.environment.dashboard import dashboard_service
from apeiria.i18n import t
from apeiria.webui.auth import require_control_panel
from apeiria.webui.schemas.models import (
    DashboardEventItem,
    DashboardEventsResponse,
    OperationStatusResponse,
    StatusResponse,
    WebUIBuildRunResponse,
    WebUIBuildStatusResponse,
)

router = APIRouter()


@router.get("/status", response_model=StatusResponse)
async def get_status(
    _: Annotated[Any, Depends(require_control_panel)],
) -> StatusResponse:
    """Return the current dashboard status snapshot."""
    snapshot = await dashboard_service.get_status_snapshot()
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
    return DashboardEventsResponse(
        items=[
            DashboardEventItem(
                timestamp=item.timestamp,
                level=item.level,
                source=item.source,
                message=item.message,
            )
            for item in dashboard_service.get_recent_events()
        ]
    )


@router.get("/webui-build", response_model=WebUIBuildStatusResponse)
async def get_webui_build_status(
    _: Annotated[Any, Depends(require_control_panel)],
) -> WebUIBuildStatusResponse:
    status = environment_service.get_frontend_build_status()
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
        status = await environment_service.rebuild_frontend()
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
    status = environment_service.get_frontend_build_status()
    if not status.can_build:
        raise HTTPException(
            status_code=400,
            detail=t("web_ui.dashboard.build_tool_unavailable"),
        )
    return StreamingResponse(
        environment_service.stream_frontend_rebuild(),
        media_type="application/x-ndjson",
    )


@router.post("/restart", response_model=OperationStatusResponse)
async def restart_bot(
    _: Annotated[Any, Depends(require_control_panel)],
) -> OperationStatusResponse:
    dashboard_service.schedule_restart()
    return OperationStatusResponse(detail=t("web_ui.dashboard.restart_scheduled"))
