"""Plugin configuration routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends

from apeiria.plugins import (
    config_mutation_service,
    config_query_service,
)
from apeiria.webui.auth import require_control_panel
from apeiria.webui.routes.plugin_support import (
    raise_settings_error,
    to_adapter_config_response,
    to_driver_config_response,
    to_plugin_config_response,
    to_plugin_raw_settings_response,
    to_plugin_settings_response,
    to_raw_validation_response,
)
from apeiria.webui.schemas.models import (
    AdapterConfigRequest,
    AdapterConfigResponse,
    DriverConfigRequest,
    DriverConfigResponse,
    PluginConfigRequest,
    PluginConfigResponse,
    PluginRawSettingsResponse,
    PluginSettingsRawUpdateRequest,
    PluginSettingsRawValidationResponse,
    PluginSettingsResponse,
    PluginSettingsUpdateRequest,
)

router = APIRouter()


@router.get("/adapters/config", response_model=AdapterConfigResponse)
async def get_adapter_config(
    _: Annotated[Any, Depends(require_control_panel)],
) -> AdapterConfigResponse:
    return to_adapter_config_response(config_query_service.get_adapter_config())


@router.patch("/adapters/config", response_model=AdapterConfigResponse)
async def update_adapter_config(
    payload: AdapterConfigRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> AdapterConfigResponse:
    return to_adapter_config_response(
        config_mutation_service.update_adapter_config(payload.modules)
    )


@router.get("/drivers/config", response_model=DriverConfigResponse)
async def get_driver_config(
    _: Annotated[Any, Depends(require_control_panel)],
) -> DriverConfigResponse:
    return to_driver_config_response(config_query_service.get_driver_config())


@router.patch("/drivers/config", response_model=DriverConfigResponse)
async def update_driver_config(
    payload: DriverConfigRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> DriverConfigResponse:
    return to_driver_config_response(
        config_mutation_service.update_driver_config(payload.builtin)
    )


@router.get("/config", response_model=PluginConfigResponse)
async def get_plugin_config(
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginConfigResponse:
    return to_plugin_config_response(config_query_service.get_plugin_config())


@router.patch("/config", response_model=PluginConfigResponse)
async def update_plugin_config(
    payload: PluginConfigRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginConfigResponse:
    return to_plugin_config_response(
        config_mutation_service.update_plugin_config(
            payload.modules,
            payload.dirs,
        )
    )


@router.get("/core/settings", response_model=PluginSettingsResponse)
async def get_core_settings(
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginSettingsResponse:
    return to_plugin_settings_response(config_query_service.get_core_view())


@router.get("/core/settings/raw", response_model=PluginRawSettingsResponse)
async def get_core_settings_raw(
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginRawSettingsResponse:
    return to_plugin_raw_settings_response(config_query_service.get_core_text())


@router.patch("/core/settings", response_model=PluginSettingsResponse)
async def update_core_settings(
    payload: PluginSettingsUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginSettingsResponse:
    try:
        state = config_mutation_service.update_core_view(
            payload.values,
            payload.clear,
        )
    except Exception as exc:
        raise_settings_error(exc)
        raise AssertionError("unreachable") from exc
    return to_plugin_settings_response(state)


@router.patch("/core/settings/raw", response_model=PluginRawSettingsResponse)
async def update_core_settings_raw(
    payload: PluginSettingsRawUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginRawSettingsResponse:
    try:
        state = config_mutation_service.update_core_text(payload.text)
    except Exception as exc:
        raise_settings_error(exc)
        raise AssertionError("unreachable") from exc
    return to_plugin_raw_settings_response(state)


@router.post(
    "/core/settings/raw/validate",
    response_model=PluginSettingsRawValidationResponse,
)
async def validate_core_settings_raw(
    payload: PluginSettingsRawUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginSettingsRawValidationResponse:
    return to_raw_validation_response(
        config_mutation_service.validate_core_text(payload.text)
    )


@router.get("/{module_name}/settings", response_model=PluginSettingsResponse)
async def get_plugin_settings(
    module_name: str,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginSettingsResponse:
    try:
        state = config_query_service.get_plugin_view(module_name)
    except Exception as exc:
        raise_settings_error(exc)
        raise AssertionError("unreachable") from exc
    return to_plugin_settings_response(state)


@router.get("/{module_name}/settings/raw", response_model=PluginRawSettingsResponse)
async def get_plugin_settings_raw(
    module_name: str,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginRawSettingsResponse:
    try:
        state = config_query_service.get_plugin_text(module_name)
    except Exception as exc:
        raise_settings_error(exc)
        raise AssertionError("unreachable") from exc
    return to_plugin_raw_settings_response(state)


@router.patch("/{module_name}/settings", response_model=PluginSettingsResponse)
async def update_plugin_settings(
    module_name: str,
    payload: PluginSettingsUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginSettingsResponse:
    try:
        state = config_mutation_service.update_plugin_view(
            module_name,
            payload.values,
            payload.clear,
        )
    except Exception as exc:
        raise_settings_error(exc)
        raise AssertionError("unreachable") from exc
    return to_plugin_settings_response(state)


@router.patch("/{module_name}/settings/raw", response_model=PluginRawSettingsResponse)
async def update_plugin_settings_raw(
    module_name: str,
    payload: PluginSettingsRawUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginRawSettingsResponse:
    try:
        state = config_mutation_service.update_plugin_text(
            module_name,
            payload.text,
        )
    except Exception as exc:
        raise_settings_error(exc)
        raise AssertionError("unreachable") from exc
    return to_plugin_raw_settings_response(state)


@router.post(
    "/{module_name}/settings/raw/validate",
    response_model=PluginSettingsRawValidationResponse,
)
async def validate_plugin_settings_raw(
    module_name: str,
    payload: PluginSettingsRawUpdateRequest,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginSettingsRawValidationResponse:
    try:
        state = config_mutation_service.validate_plugin_text(
            module_name,
            payload.text,
        )
    except Exception as exc:
        raise_settings_error(exc)
        raise AssertionError("unreachable") from exc
    return to_raw_validation_response(state)
