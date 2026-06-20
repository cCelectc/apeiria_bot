from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from apeiria.plugins.management import plugin_management_service
from apeiria.webui.routes.deps import require_auth
from apeiria.webui.schemas.plugin_config import (
    AdapterConfigRequest,
    AdapterConfigResponse,
    DriverConfigRequest,
    DriverConfigResponse,
    PluginRawSettingsResponse,
    PluginSettingsRawUpdateRequest,
    PluginSettingsRawValidationResponse,
    PluginSettingsResponse,
    PluginSettingsUpdateRequest,
    run_settings_action,
    to_adapter_config_response,
    to_driver_config_response,
    to_plugin_raw_settings_response,
    to_plugin_settings_response,
    to_raw_validation_response,
)

router = APIRouter()


# ── Core config ─────────────────────────────────────────────────


@router.get("/core", response_model=PluginSettingsResponse)
async def get_core_view(
    _: Annotated[Any, Depends(require_auth)],
) -> PluginSettingsResponse:
    return to_plugin_settings_response(plugin_management_service.get_core_view())


@router.get("/core/raw", response_model=PluginRawSettingsResponse)
async def get_core_raw(
    _: Annotated[Any, Depends(require_auth)],
) -> PluginRawSettingsResponse:
    return to_plugin_raw_settings_response(plugin_management_service.get_core_text())


@router.patch("/core", response_model=PluginSettingsResponse)
async def update_core_view(
    body: PluginSettingsUpdateRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginSettingsResponse:
    result = run_settings_action(
        plugin_management_service.update_core_view,
        values=body.values or {},
        clear=body.clear or [],
    )
    return to_plugin_settings_response(result)


@router.patch("/core/raw", response_model=PluginRawSettingsResponse)
async def update_core_raw(
    body: PluginSettingsRawUpdateRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginRawSettingsResponse:
    result = run_settings_action(
        plugin_management_service.update_core_text,
        text=body.text,
    )
    return to_plugin_raw_settings_response(result)


@router.post("/core/validate", response_model=PluginSettingsRawValidationResponse)
async def validate_core_raw(
    body: PluginSettingsRawUpdateRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginSettingsRawValidationResponse:
    return to_raw_validation_response(
        run_settings_action(
            plugin_management_service.validate_core_text,
            text=body.text,
        )
    )


# ── Adapter config ──────────────────────────────────────────────


@router.get("/adapters", response_model=AdapterConfigResponse)
async def get_adapter_config(
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterConfigResponse:
    return to_adapter_config_response(plugin_management_service.get_adapter_config())


@router.patch("/adapters", response_model=AdapterConfigResponse)
async def update_adapter_config(
    body: AdapterConfigRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterConfigResponse:
    return to_adapter_config_response(
        run_settings_action(
            plugin_management_service.update_adapter_config,
            modules=body.modules,
        )
    )


# ── Driver config ───────────────────────────────────────────────


@router.get("/drivers", response_model=DriverConfigResponse)
async def get_driver_config(
    _: Annotated[Any, Depends(require_auth)],
) -> DriverConfigResponse:
    return to_driver_config_response(plugin_management_service.get_driver_config())


@router.patch("/drivers", response_model=DriverConfigResponse)
async def update_driver_config(
    body: DriverConfigRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> DriverConfigResponse:
    return to_driver_config_response(
        run_settings_action(
            plugin_management_service.update_driver_config,
            builtin=body.builtin,
        )
    )
