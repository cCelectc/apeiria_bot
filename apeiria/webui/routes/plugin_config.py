"""Plugin configuration routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException

from apeiria.plugins.management import plugin_management_service
from apeiria.webui.auth import require_auth
from apeiria.webui.schemas.plugin_config import (
    PluginConfigRequest,
    PluginConfigResponse,
    PluginRawSettingsResponse,
    PluginSettingsRawUpdateRequest,
    PluginSettingsRawValidationResponse,
    PluginSettingsResponse,
    PluginSettingsUpdateRequest,
    run_settings_action,
    to_plugin_config_response,
    to_plugin_raw_settings_response,
    to_plugin_settings_response,
    to_raw_validation_response,
)

router = APIRouter()
_RESERVED_PLUGIN_MODULE_PATH_SEGMENTS = frozenset(
    {"core", "adapters", "drivers", "config"}
)


def _ensure_plugin_settings_module_name(module_name: str) -> None:
    if module_name in _RESERVED_PLUGIN_MODULE_PATH_SEGMENTS:
        raise HTTPException(status_code=404, detail="plugin settings not found")


@router.get("/local-sources", response_model=PluginConfigResponse)
async def get_plugin_local_sources(
    _: Annotated[Any, Depends(require_auth)],
) -> PluginConfigResponse:
    return to_plugin_config_response(plugin_management_service.get_plugin_config())


@router.patch("/local-sources", response_model=PluginConfigResponse)
async def update_plugin_local_sources(
    payload: PluginConfigRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginConfigResponse:
    return to_plugin_config_response(
        plugin_management_service.update_plugin_config(
            payload.modules,
            payload.dirs,
        )
    )


@router.get("/{module_name}/settings", response_model=PluginSettingsResponse)
async def get_plugin_settings(
    module_name: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginSettingsResponse:
    _ensure_plugin_settings_module_name(module_name)
    state = run_settings_action(plugin_management_service.get_plugin_view, module_name)
    return to_plugin_settings_response(state)


@router.get("/{module_name}/settings/raw", response_model=PluginRawSettingsResponse)
async def get_plugin_settings_raw(
    module_name: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginRawSettingsResponse:
    _ensure_plugin_settings_module_name(module_name)
    state = run_settings_action(plugin_management_service.get_plugin_text, module_name)
    return to_plugin_raw_settings_response(state)


@router.patch("/{module_name}/settings", response_model=PluginSettingsResponse)
async def update_plugin_settings(
    module_name: str,
    payload: PluginSettingsUpdateRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginSettingsResponse:
    _ensure_plugin_settings_module_name(module_name)
    state = run_settings_action(
        plugin_management_service.update_plugin_view,
        module_name,
        payload.values,
        payload.clear,
    )
    return to_plugin_settings_response(state)


@router.patch("/{module_name}/settings/raw", response_model=PluginRawSettingsResponse)
async def update_plugin_settings_raw(
    module_name: str,
    payload: PluginSettingsRawUpdateRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginRawSettingsResponse:
    _ensure_plugin_settings_module_name(module_name)
    state = run_settings_action(
        plugin_management_service.update_plugin_text,
        module_name,
        payload.text,
    )
    return to_plugin_raw_settings_response(state)


@router.post(
    "/{module_name}/settings/raw/validate",
    response_model=PluginSettingsRawValidationResponse,
)
async def validate_plugin_settings_raw(
    module_name: str,
    payload: PluginSettingsRawUpdateRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginSettingsRawValidationResponse:
    _ensure_plugin_settings_module_name(module_name)
    state = run_settings_action(
        plugin_management_service.validate_plugin_text,
        module_name,
        payload.text,
    )
    return to_raw_validation_response(state)
