"""Adapter configuration routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from apeiria.plugins.management import plugin_management_service
from apeiria.webui.auth import require_auth
from apeiria.webui.schemas.plugin_config import (
    AdapterConfigRequest,
    AdapterConfigResponse,
    to_adapter_config_response,
)

router = APIRouter()


@router.get("/config", response_model=AdapterConfigResponse)
async def get_adapter_config(
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterConfigResponse:
    return to_adapter_config_response(plugin_management_service.get_adapter_config())


@router.patch("/config", response_model=AdapterConfigResponse)
async def update_adapter_config(
    payload: AdapterConfigRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterConfigResponse:
    return to_adapter_config_response(
        plugin_management_service.update_adapter_config(payload.modules)
    )
