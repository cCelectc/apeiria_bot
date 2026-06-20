from __future__ import annotations

from collections.abc import AsyncIterator  # noqa: TC003
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse

from apeiria.log import HistoryLogFilters, load_history_log_sources, load_history_logs
from apeiria.log import log_buffer as _log_buffer
from apeiria.runtime.context import get_current_runtime
from apeiria.webui.routes.deps import require_auth
from apeiria.webui.schemas.models import (
    DashboardEventsResponse,
    LogItem,
    StatusResponse,
    WebUIBuildRunResponse,
    WebUIBuildStatusResponse,
)
from apeiria.webui.schemas.operations import OperationStatusResponse
from apeiria.webui.schemas.project_update import (
    ProjectUpdatePlanRequest,
    ProjectUpdatePlanResponse,
    ProjectUpdateStatusResponse,
    ProjectUpdateTaskItem,
)

router = APIRouter()


def _require_control_plane() -> Any:
    runtime = get_current_runtime()
    if runtime is None or runtime.control_plane is None:
        raise HTTPException(
            status_code=503,
            detail="Apeiria runtime control plane is unavailable.",
        )
    return runtime.control_plane


# ── Dashboard ───────────────────────────────────────────────────


@router.get("/status", response_model=StatusResponse)
async def get_status(
    _: Annotated[Any, Depends(require_auth)],
) -> StatusResponse:
    return await _require_control_plane().get_dashboard_status()


@router.get("/events", response_model=DashboardEventsResponse)
async def get_events(
    _: Annotated[Any, Depends(require_auth)],
) -> DashboardEventsResponse:
    return _require_control_plane().get_dashboard_events()


# ── WebUI Build ─────────────────────────────────────────────────


@router.get("/webui-build", response_model=WebUIBuildStatusResponse)
async def get_webui_build(
    _: Annotated[Any, Depends(require_auth)],
) -> WebUIBuildStatusResponse:
    return _require_control_plane().get_web_ui_build_status()


@router.post("/webui-build", response_model=WebUIBuildRunResponse)
async def rebuild_webui(
    _: Annotated[Any, Depends(require_auth)],
) -> WebUIBuildRunResponse:
    return await _require_control_plane().rebuild_web_ui()


@router.post("/webui-build/stream")
async def stream_webui_build(
    _: Annotated[Any, Depends(require_auth)],
) -> StreamingResponse:
    async def _stream() -> AsyncIterator[bytes]:
        async for chunk in _require_control_plane().stream_web_ui_rebuild():
            yield chunk

    return StreamingResponse(_stream(), media_type="text/event-stream")


@router.post("/restart")
async def restart(
    _: Annotated[Any, Depends(require_auth)],
) -> OperationStatusResponse:
    _require_control_plane().schedule_restart()
    return OperationStatusResponse(status="scheduled")


# ── Logs ────────────────────────────────────────────────────────


@router.get("/logs/history")
async def logs_history(
    _: Annotated[Any, Depends(require_auth)],
    before: str | None = None,
    limit: int = 100,
    level: str | None = None,
    source: str | None = None,
) -> dict[str, Any]:
    import asyncio

    items: list[LogItem] = await asyncio.to_thread(
        load_history_logs,
        before=before,
        limit=limit,
        filters=HistoryLogFilters(level=level, source=source),
    )
    return {"items": [item.model_dump(mode="json") for item in items]}


@router.get("/logs/sources")
async def logs_sources(
    _: Annotated[Any, Depends(require_auth)],
) -> dict[str, Any]:
    import asyncio

    sources = await asyncio.to_thread(load_history_log_sources)
    return {"sources": sources}


@router.get("/logs/stream")
async def logs_stream(
    _: Annotated[Any, Depends(require_auth)],
) -> StreamingResponse:
    import json

    subscription = _log_buffer.subscribe()

    async def _stream() -> AsyncIterator[str]:
        try:
            while True:
                entry = await subscription.queue.get()
                yield f"data: {json.dumps(entry.to_payload(), default=str)}\n\n"
        finally:
            _log_buffer.unsubscribe(subscription)

    return StreamingResponse(_stream(), media_type="text/event-stream")


# ── Project Update ──────────────────────────────────────────────


@router.get("/update/status", response_model=ProjectUpdateStatusResponse)
async def update_status(
    _: Annotated[Any, Depends(require_auth)],
) -> ProjectUpdateStatusResponse:
    from apeiria.webui.schemas.project_update import (
        to_project_update_status_response,
    )

    state = _require_control_plane().get_project_update_status()
    return to_project_update_status_response(state)


@router.post("/update/refresh", response_model=ProjectUpdateStatusResponse)
async def update_refresh(
    _: Annotated[Any, Depends(require_auth)],
) -> ProjectUpdateStatusResponse:
    from apeiria.webui.schemas.project_update import (
        to_project_update_status_response,
    )

    state = _require_control_plane().refresh_project_update_status(force=True)
    return to_project_update_status_response(state)


@router.post("/update/plan", response_model=ProjectUpdatePlanResponse)
async def update_plan(
    body: ProjectUpdatePlanRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> ProjectUpdatePlanResponse:
    from apeiria.webui.schemas.project_update import (
        to_project_update_plan_request,
        to_project_update_plan_response,
    )

    request = to_project_update_plan_request(body)
    plan = _require_control_plane().create_project_update_plan(request)
    return to_project_update_plan_response(plan)


@router.post("/update/tasks", response_model=ProjectUpdateTaskItem)
async def update_create_task(
    body: ProjectUpdatePlanRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> ProjectUpdateTaskItem:
    from apeiria.webui.schemas.project_update import (
        to_project_update_plan_request,
        to_project_update_task_item,
    )

    request = to_project_update_plan_request(body)
    task = await _require_control_plane().create_project_update_task(request)
    return to_project_update_task_item(task)


@router.get("/update/tasks/{task_id}", response_model=ProjectUpdateTaskItem)
async def update_get_task(
    task_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> ProjectUpdateTaskItem:
    from apeiria.webui.schemas.project_update import to_project_update_task_item

    task = _require_control_plane().get_project_update_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="project_update_task_not_found")
    return to_project_update_task_item(task)
