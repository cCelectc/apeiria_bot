"""Driver configuration routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from apeiria.app.plugins.management import plugin_management_service
from apeiria.webui.auth import require_control_panel
from apeiria.webui.schemas.plugin_config import (
    DriverConfigRequest,
    DriverConfigResponse,
    to_driver_config_response,
)

router = APIRouter()


@router.get("/config", response_model=DriverConfigResponse)
async def get_driver_config(
    _: Annotated[Any, Depends(require_control_panel)],
) -> DriverConfigResponse:
    return to_driver_config_response(plugin_management_service.get_driver_config())


@router.patch("/config", response_model=DriverConfigResponse)
async def update_driver_config(
    payload: DriverConfigRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> DriverConfigResponse:
    return to_driver_config_response(
        plugin_management_service.update_driver_config(payload.builtin)
    )
