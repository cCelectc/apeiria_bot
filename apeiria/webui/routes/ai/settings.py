"""AI runtime settings management routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import ValidationError

from apeiria.ai.runtime_settings import ai_runtime_settings_service
from apeiria.webui.auth import require_control_panel

from .settings_schemas import (
    AIRuntimeSettingsResponse,
    AIRuntimeSettingsUpdateRequest,
    to_ai_runtime_settings_response,
)

router = APIRouter()


@router.get("/runtime-settings", response_model=AIRuntimeSettingsResponse)
async def get_ai_runtime_settings(
    _: Annotated[Any, Depends(require_control_panel)],
) -> AIRuntimeSettingsResponse:
    return to_ai_runtime_settings_response(ai_runtime_settings_service.get_view())


@router.patch("/runtime-settings", response_model=AIRuntimeSettingsResponse)
async def update_ai_runtime_settings(
    payload: AIRuntimeSettingsUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AIRuntimeSettingsResponse:
    try:
        view = ai_runtime_settings_service.update_settings(
            payload.values,
            clear=payload.clear,
        )
    except (ValidationError, ValueError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_ai_runtime_settings_response(view)
