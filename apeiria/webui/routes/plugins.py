"""Unified plugin routes."""

from __future__ import annotations

import mimetypes
from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse

from apeiria.exceptions import ResourceNotFoundError
from apeiria.i18n import t
from apeiria.plugins.management import plugin_management_service
from apeiria.webui.auth import require_auth
from apeiria.webui.routes.deps import require_runtime_control_plane
from apeiria.webui.schemas.plugin_catalog import (
    OrphanPluginConfigResponse,
    PluginItem,
    PluginReadmeResponse,
    PluginUpdateCheckItem,
    PluginUpdateCheckRequest,
    PluginWorkspaceResponse,
    to_orphan_plugin_config_response,
    to_plugin_item_response,
    to_plugin_readme_response,
    to_plugin_update_check_item,
)
from apeiria.webui.schemas.plugin_config import to_plugin_workspace_settings_summary
from apeiria.webui.schemas.plugin_management import to_plugin_toggle_preview_response
from apeiria.webui.schemas.plugin_workbench import (
    PluginWorkbenchResponse,
    to_plugin_workbench_response,
)

catalog_router = APIRouter()


@catalog_router.get("/{module_name}/readme", response_model=PluginReadmeResponse)
async def get_plugin_readme(
    module_name: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginReadmeResponse:
    try:
        state = await plugin_management_service.get_plugin_readme(module_name)
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.plugins.readme_not_found"),
        ) from None
    except RuntimeError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_plugin_readme_response(state)


@catalog_router.get("/{module_name}/readme/asset")
async def get_plugin_readme_asset(
    module_name: str,
    path: Annotated[str, Query(min_length=1)],
    _: Annotated[Any, Depends(require_auth)],
) -> FileResponse:
    try:
        asset_path = await plugin_management_service.get_plugin_readme_asset_path(
            module_name,
            path,
        )
    except ResourceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.plugins.readme_not_found"),
        ) from None
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail=t("web_ui.plugins.readme_asset_forbidden"),
        ) from None
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    media_type, _ = mimetypes.guess_type(asset_path.name)
    return FileResponse(
        asset_path,
        media_type=media_type or "application/octet-stream",
        filename=asset_path.name,
        headers={
            "Content-Security-Policy": "default-src 'none'; sandbox",
            "X-Content-Type-Options": "nosniff",
        },
    )


@catalog_router.get("/", response_model=list[PluginItem])
async def list_plugins(
    _: Annotated[Any, Depends(require_auth)],
) -> list[PluginItem]:
    control_plane = require_runtime_control_plane()
    plugins = await control_plane.list_plugin_catalog_entries()
    return [
        to_plugin_item_response(
            plugin,
            can_package_update=control_plane.can_plugin_package_update(plugin),
        )
        for plugin in plugins
    ]


@catalog_router.get("/workbench", response_model=PluginWorkbenchResponse)
async def get_plugin_workbench(
    _: Annotated[Any, Depends(require_auth)],
) -> PluginWorkbenchResponse:
    control_plane = require_runtime_control_plane()
    workspace = await control_plane.get_plugin_workbench()
    return to_plugin_workbench_response(workspace)


@catalog_router.get("/{module_name}/workspace", response_model=PluginWorkspaceResponse)
async def get_plugin_workspace(
    module_name: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginWorkspaceResponse:
    workspace = await plugin_management_service.build_plugin_workspace(module_name)
    if workspace is None:
        raise HTTPException(status_code=404, detail=t("web_ui.plugins.not_found"))

    plugin_item = to_plugin_item_response(
        workspace.plugin,
        can_package_update=workspace.can_package_update,
    )
    enable_preview = (
        to_plugin_toggle_preview_response(workspace.enable_preview)
        if workspace.enable_preview is not None
        else None
    )
    disable_preview = (
        to_plugin_toggle_preview_response(workspace.disable_preview)
        if workspace.disable_preview is not None
        else None
    )
    settings = (
        to_plugin_workspace_settings_summary(workspace.settings)
        if workspace.settings is not None
        else None
    )

    return PluginWorkspaceResponse(
        plugin=plugin_item,
        enable_preview=enable_preview,
        disable_preview=disable_preview,
        settings=settings,
        readme_available=plugin_item.can_view_readme,
    )


@catalog_router.post("/update-checks", response_model=list[PluginUpdateCheckItem])
async def check_plugin_updates(
    payload: PluginUpdateCheckRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> list[PluginUpdateCheckItem]:
    results = await plugin_management_service.check_plugin_updates(
        force_refresh=payload.force_refresh,
    )
    return [to_plugin_update_check_item(item) for item in results]


@catalog_router.get("/orphan-configs", response_model=OrphanPluginConfigResponse)
async def list_orphan_plugin_configs(
    _: Annotated[Any, Depends(require_auth)],
) -> OrphanPluginConfigResponse:
    items = await plugin_management_service.list_orphan_plugin_configs()
    return to_orphan_plugin_config_response(items)


@catalog_router.post(
    "/orphan-configs/cleanup", response_model=OrphanPluginConfigResponse
)
async def cleanup_orphan_plugin_configs(
    _: Annotated[Any, Depends(require_auth)],
) -> OrphanPluginConfigResponse:
    items = await plugin_management_service.cleanup_orphan_plugin_configs()
    return to_orphan_plugin_config_response(items)


from fastapi import APIRouter

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

config_router = APIRouter()
_RESERVED_PLUGIN_MODULE_PATH_SEGMENTS = frozenset(
    {"core", "adapters", "drivers", "config"}
)


def _ensure_plugin_settings_module_name(module_name: str) -> None:
    if module_name in _RESERVED_PLUGIN_MODULE_PATH_SEGMENTS:
        raise HTTPException(status_code=404, detail="plugin settings not found")


@config_router.get("/local-sources", response_model=PluginConfigResponse)
async def get_plugin_local_sources(
    _: Annotated[Any, Depends(require_auth)],
) -> PluginConfigResponse:
    return to_plugin_config_response(plugin_management_service.get_plugin_config())


@config_router.patch("/local-sources", response_model=PluginConfigResponse)
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


@config_router.get("/{module_name}/settings", response_model=PluginSettingsResponse)
async def get_plugin_settings(
    module_name: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginSettingsResponse:
    _ensure_plugin_settings_module_name(module_name)
    state = run_settings_action(plugin_management_service.get_plugin_view, module_name)
    return to_plugin_settings_response(state)


@config_router.get(
    "/{module_name}/settings/raw", response_model=PluginRawSettingsResponse
)
async def get_plugin_settings_raw(
    module_name: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginRawSettingsResponse:
    _ensure_plugin_settings_module_name(module_name)
    state = run_settings_action(plugin_management_service.get_plugin_text, module_name)
    return to_plugin_raw_settings_response(state)


@config_router.patch("/{module_name}/settings", response_model=PluginSettingsResponse)
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


@config_router.patch(
    "/{module_name}/settings/raw", response_model=PluginRawSettingsResponse
)
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


@config_router.post(
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


from inspect import isawaitable

from fastapi import APIRouter
from pydantic import BaseModel

from apeiria.config.plugins import plugin_config_service
from apeiria.exceptions import ProtectedPluginError
from apeiria.plugins.install_resolution import (
    PluginInstallSource,
    plugin_install_resolution_service,
)
from apeiria.plugins.store.tasks import plugin_store_task_service
from apeiria.plugins.store.update_check import (
    plugin_update_check_service,
    supports_plugin_update_check,
)
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
)
from apeiria.webui.schemas.plugin_store import (
    PluginStoreTaskItem,
    to_plugin_store_task_item,
)

management_router = APIRouter()


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


@management_router.patch(
    "/{module_name}/policy", response_model=PluginPolicyUpdateResponse
)
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


@management_router.get(
    "/{module_name}/toggle-preview", response_model=PluginTogglePreviewResponse
)
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


@management_router.post(
    "/{module_name}/uninstall", response_model=OperationStatusResponse
)
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


@management_router.post("/install/manual", response_model=PluginStoreTaskItem)
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


@management_router.post("/install/resolve", response_model=PluginInstallResolveResponse)
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


@management_router.post("/install/confirm", response_model=PluginStoreTaskItem)
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


@management_router.post("/{module_name}/update", response_model=PluginStoreTaskItem)
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


@management_router.get("/install/tasks/{task_id}", response_model=PluginStoreTaskItem)
async def get_plugin_install_task(
    task_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreTaskItem:
    task = plugin_store_task_service.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=t("web_ui.tasks.not_found"))
    return to_plugin_store_task_item(task)


from fastapi import APIRouter
from pydantic import BaseModel, Field

from apeiria.plugins.store.models import StoreInstallRequest
from apeiria.plugins.store.workflows import (
    PackageStoreItemRequest,
    PackageStoreListRequest,
    PackageStoreRevertRequest,
    package_store_workflow,
)
from apeiria.webui.schemas.operations import OperationStatusResponse
from apeiria.webui.schemas.plugin_store import (
    PluginStoreCategoryItem,
    PluginStoreInstallRequest,
    PluginStoreItem,
    PluginStoreItemsResponse,
    PluginStoreRevertInstallRequest,
    PluginStoreSourceItem,
    PluginStoreTaskItem,
    to_plugin_store_item,
    to_plugin_store_source_item,
)

store_router = APIRouter()


class PluginStoreItemsQueryParams(BaseModel):
    """Plugin store list query params."""

    source: str = ""
    search: str = ""
    category: str = ""
    sort: str = "default"
    installed_only: bool = False
    uninstalled_only: bool = False
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=16, ge=1, le=100)


class PluginStoreRefreshRequest(BaseModel):
    """Plugin store refresh payload."""

    source_id: str = ""


@store_router.get("/sources", response_model=list[PluginStoreSourceItem])
async def list_plugin_store_sources(
    _: Annotated[Any, Depends(require_auth)],
) -> list[PluginStoreSourceItem]:
    return [
        to_plugin_store_source_item(item)
        for item in package_store_workflow.list_sources()
    ]


@store_router.get("/items", response_model=PluginStoreItemsResponse)
async def list_plugin_store_items(
    _: Annotated[Any, Depends(require_auth)],
    params: Annotated[PluginStoreItemsQueryParams, Depends()],
) -> PluginStoreItemsResponse:
    result = await package_store_workflow.list_items(
        PackageStoreListRequest(
            item_type="plugin",
            source_id=params.source,
            keyword=params.search,
            category=params.category,
            sort=params.sort,
            installed_only=params.installed_only,
            uninstalled_only=params.uninstalled_only,
            page=params.page,
            page_size=params.per_page,
        )
    )
    return PluginStoreItemsResponse(
        items=[to_plugin_store_item(item) for item in result.items],
        categories=[
            PluginStoreCategoryItem(value=item.value, count=item.count)
            for item in result.categories
        ],
        total=result.total,
        page=result.page,
        per_page=result.per_page,
    )


@store_router.get("/items/{source_id}/{plugin_id}", response_model=PluginStoreItem)
async def get_plugin_store_item(
    source_id: str,
    plugin_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreItem:
    item = await package_store_workflow.get_item(
        PackageStoreItemRequest(
            item_type="plugin",
            source_id=source_id,
            item_id=plugin_id,
        )
    )
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.plugins.store_not_found"),
        )
    return to_plugin_store_item(item)


@store_router.post("/refresh", response_model=list[PluginStoreSourceItem])
async def refresh_plugin_store_sources(
    payload: PluginStoreRefreshRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> list[PluginStoreSourceItem]:
    return [
        to_plugin_store_source_item(item)
        for item in await package_store_workflow.refresh_sources(
            "plugin",
            source_id=payload.source_id,
        )
    ]


@store_router.post("/install", response_model=PluginStoreTaskItem)
async def install_plugin_store_item(
    payload: PluginStoreInstallRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreTaskItem:
    try:
        task = await plugin_store_task_service.create_plugin_install_task(
            StoreInstallRequest(
                source_id=payload.source_id,
                item_id=payload.plugin_id,
                type="plugin",
                package_requirement=payload.package_name,
                binding_value=payload.module_name,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return to_plugin_store_task_item(task)


@store_router.post("/update", response_model=PluginStoreTaskItem)
async def update_plugin_store_item(
    payload: PluginStoreInstallRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreTaskItem:
    try:
        task = await plugin_store_task_service.create_plugin_update_task(
            StoreInstallRequest(
                source_id=payload.source_id,
                item_id=payload.plugin_id,
                type="plugin",
                package_requirement=payload.package_name,
                binding_value=payload.module_name,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return to_plugin_store_task_item(task)


@store_router.get("/tasks/{task_id}", response_model=PluginStoreTaskItem)
async def get_plugin_store_task(
    task_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreTaskItem:
    task = package_store_workflow.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=t("web_ui.tasks.not_found"))
    return to_plugin_store_task_item(task)


@store_router.post("/revert-install")
async def revert_plugin_store_install(
    payload: PluginStoreRevertInstallRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> OperationStatusResponse:
    try:
        package_store_workflow.revert_install(
            PackageStoreRevertRequest(
                item_type="plugin",
                package_requirement=payload.package_name,
                binding_value=payload.module_name,
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OperationStatusResponse(status="ok")


router = APIRouter()
router.include_router(catalog_router, prefix="")
router.include_router(config_router, prefix="")
router.include_router(management_router, prefix="")
router.include_router(store_router, prefix="/store")
