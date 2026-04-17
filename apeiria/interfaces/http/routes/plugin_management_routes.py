"""Plugin toggle, uninstall, and task routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from apeiria.app.plugin_store import plugin_store_task_service
from apeiria.app.plugins import plugin_governance_service
from apeiria.infra.package_store.update_check import supports_plugin_update_check
from apeiria.interfaces.http.auth import require_control_panel, require_owner
from apeiria.interfaces.http.routes.plugin_route_support import (
    to_plugin_store_task_item,
    to_plugin_toggle_preview_response,
    to_plugin_toggle_response,
)
from apeiria.interfaces.http.schemas.models import (
    OperationStatusResponse,
    PluginManualInstallRequest,
    PluginPackageUpdateRequest,
    PluginStoreTaskItem,
    PluginTogglePreviewResponse,
    PluginToggleResponse,
    PluginUninstallRequest,
)
from apeiria.shared.exceptions import ProtectedPluginError, ResourceNotFoundError
from apeiria.shared.i18n import t

router = APIRouter()


class PluginTogglePreviewQuery(BaseModel):
    enabled: bool


@router.patch("/{module_name}", response_model=PluginToggleResponse)
async def update_plugin(
    module_name: str,
    _: Annotated[Any, Depends(require_control_panel)],
    *,
    enabled: bool = True,
    cascade: bool = False,
) -> PluginToggleResponse:
    try:
        result = await plugin_governance_service.apply_plugin_toggle(
            module_name,
            enabled=enabled,
            cascade=cascade,
        )
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.plugins.not_found"),
        ) from None
    except ProtectedPluginError as exc:
        raise HTTPException(
            status_code=400,
            detail=t("web_ui.plugins.protected", reason=str(exc)),
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_plugin_toggle_response(result)


@router.get("/{module_name}/toggle-preview", response_model=PluginTogglePreviewResponse)
async def preview_toggle_plugin(
    module_name: str,
    query: Annotated[PluginTogglePreviewQuery, Depends()],
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginTogglePreviewResponse:
    try:
        preview = await plugin_governance_service.preview_toggle_plugin(
            module_name,
            enabled=query.enabled,
        )
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.plugins.not_found"),
        ) from None
    return to_plugin_toggle_preview_response(preview)


@router.post("/{module_name}/uninstall", response_model=OperationStatusResponse)
async def uninstall_plugin(
    module_name: str,
    payload: PluginUninstallRequest,
    _: Annotated[Any, Depends(require_owner)],
) -> OperationStatusResponse:
    try:
        await plugin_governance_service.uninstall_plugin(
            module_name,
            remove_config=payload.remove_config,
        )
    except ResourceNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.plugins.not_found"),
        ) from None
    except ProtectedPluginError as exc:
        raise HTTPException(
            status_code=400,
            detail=t("web_ui.plugins.protected", reason=str(exc)),
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OperationStatusResponse(status="ok")


@router.post("/install/manual", response_model=PluginStoreTaskItem)
async def install_plugin_manual(
    payload: PluginManualInstallRequest,
    _: Annotated[Any, Depends(require_owner)],
) -> PluginStoreTaskItem:
    try:
        task = await plugin_store_task_service.create_manual_plugin_install_task(
            payload.requirement,
            payload.module_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_plugin_store_task_item(task)


@router.post("/{module_name}/update", response_model=PluginStoreTaskItem)
async def update_plugin_package_task(
    module_name: str,
    payload: PluginPackageUpdateRequest,
    _: Annotated[Any, Depends(require_owner)],
) -> PluginStoreTaskItem:
    plugin = await plugin_governance_service.get_plugin(module_name)
    if plugin is None:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.plugins.not_found"),
        ) from None
    if (
        not plugin.governance_state.can_uninstall
        or plugin.package_binding.installed_package != payload.package_name
        or not supports_plugin_update_check(payload.package_name)
    ):
        raise HTTPException(
            status_code=400,
            detail=t("web_ui.plugins.update_not_allowed"),
        ) from None

    try:
        task = await plugin_store_task_service.create_manual_plugin_update_task(
            payload.package_name,
            module_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_plugin_store_task_item(task)


@router.get("/install/tasks/{task_id}", response_model=PluginStoreTaskItem)
async def get_plugin_install_task(
    task_id: str,
    _: Annotated[Any, Depends(require_control_panel)],
) -> PluginStoreTaskItem:
    task = plugin_store_task_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=t("web_ui.tasks.not_found"))
    return to_plugin_store_task_item(task)
