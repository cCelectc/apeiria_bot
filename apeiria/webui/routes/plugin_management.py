"""Plugin toggle, uninstall, and task routes."""

from __future__ import annotations

from inspect import isawaitable
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from apeiria.app.plugins.install_resolution import (
    PluginInstallSource,
    plugin_install_resolution_service,
)
from apeiria.app.plugins.management import plugin_management_service
from apeiria.app.plugins.store.tasks import plugin_store_task_service
from apeiria.app.plugins.store.update_check import (
    plugin_update_check_service,
    supports_plugin_update_check,
)
from apeiria.config.plugins import plugin_config_service
from apeiria.exceptions import ProtectedPluginError, ResourceNotFoundError
from apeiria.i18n import t
from apeiria.webui.auth import require_auth
from apeiria.webui.schemas.operations import OperationStatusResponse
from apeiria.webui.schemas.plugin_management import (
    PluginInstallConfirmRequest,
    PluginInstallResolveRequest,
    PluginInstallResolveResponse,
    PluginManualInstallRequest,
    PluginPackageUpdateRequest,
    PluginPolicyUpdateRequest,
    PluginPolicyUpdateResponse,
    PluginTogglePreviewResponse,
    PluginUninstallRequest,
    to_plugin_policy_update_response,
    to_plugin_toggle_preview_response,
)
from apeiria.webui.schemas.plugin_store import (
    PluginStoreTaskItem,
    to_plugin_store_task_item,
)

router = APIRouter()


class PluginTogglePreviewQuery(BaseModel):
    enabled: bool


def resolve_plugin_install_source(
    payload: PluginInstallResolveRequest,
) -> object:
    source = payload.source
    return plugin_install_resolution_service.resolve(
        PluginInstallSource(
            kind=source.kind,
            value=source.value,
            source_id=source.source_id,
            item_id=source.item_id,
        )
    )


@router.patch("/{module_name}/policy", response_model=PluginPolicyUpdateResponse)
async def update_plugin_policy(
    module_name: str,
    payload: PluginPolicyUpdateRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginPolicyUpdateResponse:
    plugin = await plugin_management_service.get_plugin(module_name)
    try:
        result = await plugin_management_service.apply_plugin_toggle(
            module_name,
            enabled=payload.enabled,
            cascade=payload.cascade,
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
    return to_plugin_policy_update_response(
        result,
        was_loaded=(plugin.runtime_state.is_loaded if plugin is not None else None),
    )


@router.get("/{module_name}/toggle-preview", response_model=PluginTogglePreviewResponse)
async def preview_toggle_plugin(
    module_name: str,
    query: Annotated[PluginTogglePreviewQuery, Depends()],
    _: Annotated[Any, Depends(require_auth)],
) -> PluginTogglePreviewResponse:
    try:
        preview = await plugin_management_service.preview_toggle_plugin(
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
    _: Annotated[Any, Depends(require_auth)],
) -> OperationStatusResponse:
    try:
        await plugin_management_service.uninstall_plugin(
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
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreTaskItem:
    try:
        task = await plugin_store_task_service.create_manual_plugin_install_task(
            payload.requirement,
            payload.module_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_plugin_store_task_item(task)


@router.post("/install/resolve", response_model=PluginInstallResolveResponse)
async def resolve_plugin_install(
    payload: PluginInstallResolveRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginInstallResolveResponse:
    result = resolve_plugin_install_source(payload)
    if isawaitable(result):
        result = await result
    if isinstance(result, PluginInstallResolveResponse):
        return result
    if isinstance(result, dict):
        return PluginInstallResolveResponse.model_validate(result)
    return PluginInstallResolveResponse.from_domain(result)


@router.post("/install/confirm", response_model=PluginStoreTaskItem)
async def confirm_plugin_install(
    payload: PluginInstallConfirmRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreTaskItem:
    action = payload.action
    if action.kind != "install_package":
        if action.kind == "register_local_module":
            if not action.module_name:
                raise HTTPException(
                    status_code=400,
                    detail="plugin module is required",
                )
            plugin_config_service.add_project_plugin_module(action.module_name)
            return to_plugin_store_task_item(
                _completed_registration_task(
                    title=f"Register {action.module_name}",
                    binding_value=action.module_name,
                )
            )
        if action.kind == "register_local_directory":
            if not action.path:
                raise HTTPException(
                    status_code=400,
                    detail="plugin directory is required",
                )
            plugin_config_service.add_project_plugin_dir(action.path)
            return to_plugin_store_task_item(
                _completed_registration_task(
                    title=f"Register {action.path}",
                    binding_value=action.path,
                )
            )
        raise HTTPException(status_code=400, detail="unsupported install action")
    if not action.requirement:
        raise HTTPException(status_code=400, detail="package requirement is required")
    try:
        task = await plugin_store_task_service.create_manual_plugin_install_task(
            action.requirement,
            action.module_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_plugin_store_task_item(task)


class _RegistrationTask(BaseModel):
    task_id: str = "local-registration"
    title: str
    status: str = "succeeded"
    logs: str = "registered\n"
    error: str | None = None
    result: dict[str, object] = {}
    operation: str = "install"
    resource_kind: str = "plugin"
    requirement: str | None = None
    binding_value: str | None = None
    current_phase: str = "succeeded"
    current_phase_label: str = "Succeeded"
    progress_percent: int = 100
    queue_position: int | None = None
    lock_wait_started_at: str | None = None
    lock_acquired_at: str | None = None
    restart_required: bool = True
    steps: tuple[object, ...] = ()
    diagnostics: list[dict[str, object]] = []
    created_at: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


def _completed_registration_task(
    *,
    title: str,
    binding_value: str,
) -> _RegistrationTask:
    return _RegistrationTask(
        title=title,
        binding_value=binding_value,
        result={
            "resource_kind": "plugin",
            "module_name": binding_value,
            "restart_required": True,
        },
    )


@router.post("/{module_name}/update", response_model=PluginStoreTaskItem)
async def update_plugin_package_task(
    module_name: str,
    payload: PluginPackageUpdateRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreTaskItem:
    plugin = await plugin_management_service.get_plugin(module_name)
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

    update_check = await plugin_update_check_service.check_plugin(
        module_name,
        payload.package_name,
        force_refresh=True,
    )
    if not update_check.has_update:
        raise HTTPException(
            status_code=400,
            detail=t("web_ui.plugins.update_not_available"),
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
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreTaskItem:
    task = plugin_store_task_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=t("web_ui.tasks.not_found"))
    return to_plugin_store_task_item(task)
