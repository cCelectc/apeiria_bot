"""Project update routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from apeiria.system.project_update import ProjectUpdateError
from apeiria.webui.auth import require_auth
from apeiria.webui.routes._deps import require_runtime_control_plane
from apeiria.webui.schemas.project_update import (
    ProjectUpdatePlanRequest,
    ProjectUpdatePlanResponse,
    ProjectUpdateStatusResponse,
    ProjectUpdateTaskItem,
    to_project_update_plan_request,
    to_project_update_plan_response,
    to_project_update_status_response,
    to_project_update_task_item,
)

router = APIRouter()


@router.get("/status", response_model=ProjectUpdateStatusResponse)
async def get_project_update_status(
    _: Annotated[Any, Depends(require_auth)],
) -> ProjectUpdateStatusResponse:
    state = require_runtime_control_plane().get_project_update_status()
    return to_project_update_status_response(state)


@router.post("/refresh", response_model=ProjectUpdateStatusResponse)
async def refresh_project_update_status(
    _: Annotated[Any, Depends(require_auth)],
) -> ProjectUpdateStatusResponse:
    try:
        state = require_runtime_control_plane().refresh_project_update_status(
            force=True
        )
    except ProjectUpdateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_project_update_status_response(state)


@router.post("/plan", response_model=ProjectUpdatePlanResponse)
async def preview_project_update_plan(
    payload: ProjectUpdatePlanRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> ProjectUpdatePlanResponse:
    plan = require_runtime_control_plane().create_project_update_plan(
        to_project_update_plan_request(payload)
    )
    return to_project_update_plan_response(plan)


@router.post("/tasks", response_model=ProjectUpdateTaskItem)
async def create_project_update_task(
    payload: ProjectUpdatePlanRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> ProjectUpdateTaskItem:
    try:
        task = await require_runtime_control_plane().create_project_update_task(
            to_project_update_plan_request(payload)
        )
    except ProjectUpdateError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_project_update_task_item(task)


@router.get("/tasks/{task_id}", response_model=ProjectUpdateTaskItem)
async def get_project_update_task(
    task_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> ProjectUpdateTaskItem:
    task = require_runtime_control_plane().get_project_update_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail="project_update_task_not_found")
    return to_project_update_task_item(task)
