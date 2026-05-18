"""Core configuration routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from apeiria.app.plugins.management import plugin_management_service
from apeiria.webui.auth import require_control_panel
from apeiria.webui.schemas.plugin_config import (
    PluginRawSettingsResponse,
    PluginSettingsRawUpdateRequest,
    PluginSettingsRawValidationResponse,
    PluginSettingsResponse,
    PluginSettingsUpdateRequest,
    run_settings_action,
    to_plugin_raw_settings_response,
    to_plugin_settings_response,
    to_raw_validation_response,
)

router = APIRouter()


@router.get("/settings", response_model=PluginSettingsResponse)
async def get_core_settings(
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginSettingsResponse:
    return to_plugin_settings_response(plugin_management_service.get_core_view())


@router.get("/settings/raw", response_model=PluginRawSettingsResponse)
async def get_core_settings_raw(
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginRawSettingsResponse:
    return to_plugin_raw_settings_response(plugin_management_service.get_core_text())


@router.patch("/settings", response_model=PluginSettingsResponse)
async def update_core_settings(
    payload: PluginSettingsUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginSettingsResponse:
    state = run_settings_action(
        plugin_management_service.update_core_view,
        payload.values,
        payload.clear,
    )
    return to_plugin_settings_response(state)


@router.patch("/settings/raw", response_model=PluginRawSettingsResponse)
async def update_core_settings_raw(
    payload: PluginSettingsRawUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginRawSettingsResponse:
    state = run_settings_action(
        plugin_management_service.update_core_text,
        payload.text,
    )
    return to_plugin_raw_settings_response(state)


@router.post(
    "/settings/raw/validate",
    response_model=PluginSettingsRawValidationResponse,
)
async def validate_core_settings_raw(
    payload: PluginSettingsRawUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginSettingsRawValidationResponse:
    return to_raw_validation_response(
        plugin_management_service.validate_core_text(payload.text)
    )
