from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException, Query

from apeiria.i18n import t
from apeiria.plugins.adapter_selection import adapter_selection_service
from apeiria.plugins.install_resolution import plugin_install_resolution_service
from apeiria.plugins.management import plugin_management_service
from apeiria.plugins.store.tasks import plugin_store_task_service
from apeiria.plugins.store.workflows import (
    PackageStoreListRequest,
    PackageStoreRevertRequest,
    StoreInstallRequest,
    package_store_workflow,
)
from apeiria.runtime.context import get_current_runtime
from apeiria.webui.routes.deps import require_auth
from apeiria.webui.schemas.adapter_selection import (
    AdapterSelectionEnableRequest,
    AdapterSelectionQueryParams,
    AdapterSelectionResponse,
    to_adapter_selection_response,
)
from apeiria.webui.schemas.adapter_store import (
    AdapterStoreItemsResponse,
    AdapterStoreMutationRequest,
    AdapterStoreRevertInstallRequest,
    AdapterStoreTaskItem,
    to_adapter_store_item,
    to_adapter_store_source_item,
    to_adapter_store_task_item,
)
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
from apeiria.webui.schemas.plugin_config import (
    PluginConfigRequest,
    PluginConfigResponse,
    PluginRawSettingsResponse,
    PluginSettingsResponse,
    PluginSettingsUpdateRequest,
    run_settings_action,
    to_plugin_config_response,
    to_plugin_raw_settings_response,
    to_plugin_settings_response,
    to_plugin_workspace_settings_summary,
)
from apeiria.webui.schemas.plugin_management import (
    PluginInstallConfirmRequest,
    PluginInstallResolveRequest,
    PluginInstallResolveResponse,
    PluginManualInstallRequest,
    PluginToggleResponse,
    PluginUninstallRequest,
    to_plugin_toggle_preview_response,
    to_plugin_toggle_response,
)
from apeiria.webui.schemas.plugin_store import (
    PluginStoreInstallRequest,
    PluginStoreItemsResponse,
    PluginStoreRevertInstallRequest,
    PluginStoreTaskItem,
    to_plugin_store_item,
    to_plugin_store_source_item,
    to_plugin_store_task_item,
)
from apeiria.webui.schemas.plugin_workbench import (
    PluginWorkbenchResponse,
    to_plugin_workbench_response,
)

router = APIRouter()


def _require_control_plane() -> Any:
    runtime = get_current_runtime()
    if runtime is None or runtime.control_plane is None:
        raise HTTPException(status_code=503, detail="control_plane_unavailable")
    return runtime.control_plane


# ── Plugin Catalog ──────────────────────────────────────────────


@router.get("", response_model=list[PluginItem])
async def list_plugins(
    _: Annotated[Any, Depends(require_auth)],
) -> list[PluginItem]:
    entries = await _require_control_plane().list_plugin_catalog_entries()
    cp = _require_control_plane()
    return [
        to_plugin_item_response(
            plugin,
            can_package_update=cp.can_plugin_package_update(plugin),
        )
        for plugin in entries
    ]


@router.get("/workbench", response_model=PluginWorkbenchResponse)
async def get_workbench(
    _: Annotated[Any, Depends(require_auth)],
) -> PluginWorkbenchResponse:
    state = await _require_control_plane().get_plugin_workbench()
    return to_plugin_workbench_response(state)


@router.post("/update-checks", response_model=list[PluginUpdateCheckItem])
async def check_updates(
    body: PluginUpdateCheckRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> list[PluginUpdateCheckItem]:
    results = await plugin_management_service.check_plugin_updates(
        force_refresh=body.force_refresh,
    )
    return [to_plugin_update_check_item(result) for result in results]


@router.get("/orphan-configs", response_model=OrphanPluginConfigResponse)
async def list_orphan_configs(
    _: Annotated[Any, Depends(require_auth)],
) -> OrphanPluginConfigResponse:
    items = await plugin_management_service.list_orphan_plugin_configs()
    return to_orphan_plugin_config_response(items)


@router.post("/orphan-configs/cleanup", response_model=OrphanPluginConfigResponse)
async def cleanup_orphan_configs(
    _: Annotated[Any, Depends(require_auth)],
) -> OrphanPluginConfigResponse:
    items = await plugin_management_service.cleanup_orphan_plugin_configs()
    return to_orphan_plugin_config_response(items)


# ── Per-plugin ──────────────────────────────────────────────────


@router.get("/{module_name}/readme", response_model=PluginReadmeResponse)
async def get_plugin_readme(
    module_name: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginReadmeResponse:
    readme = await plugin_management_service.get_plugin_readme(module_name)
    return to_plugin_readme_response(readme)


@router.get("/{module_name}/workspace", response_model=PluginWorkspaceResponse)
async def get_plugin_workspace(
    module_name: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginWorkspaceResponse:
    state = await plugin_management_service.build_plugin_workspace(module_name)
    if state is None:
        raise HTTPException(status_code=404, detail=t("web_ui.plugins.not_found"))
    return PluginWorkspaceResponse(
        plugin=to_plugin_item_response(
            state.plugin,
            can_package_update=state.can_package_update,
        ),
        enable_preview=(
            to_plugin_toggle_preview_response(state.enable_preview)
            if state.enable_preview is not None
            else None
        ),
        disable_preview=(
            to_plugin_toggle_preview_response(state.disable_preview)
            if state.disable_preview is not None
            else None
        ),
        settings=(
            to_plugin_workspace_settings_summary(state.settings)
            if state.settings is not None
            else None
        ),
    )


@router.get("/{module_name}/settings", response_model=PluginSettingsResponse)
async def get_plugin_settings(
    module_name: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginSettingsResponse:
    return to_plugin_settings_response(
        plugin_management_service.get_plugin_view(module_name)
    )


@router.get("/{module_name}/settings/raw", response_model=PluginRawSettingsResponse)
async def get_plugin_settings_raw(
    module_name: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginRawSettingsResponse:
    return to_plugin_raw_settings_response(
        plugin_management_service.get_plugin_text(module_name)
    )


@router.patch("/{module_name}/settings", response_model=PluginSettingsResponse)
async def update_plugin_settings(
    module_name: str,
    body: PluginSettingsUpdateRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginSettingsResponse:
    result = run_settings_action(
        plugin_management_service.update_plugin_view,
        module_name,
        values=body.values or {},
        clear=body.clear or [],
    )
    return to_plugin_settings_response(result)


@router.patch("/{module_name}/toggle", response_model=PluginToggleResponse)
async def toggle_plugin(
    module_name: str,
    _: Annotated[Any, Depends(require_auth)],
    enabled: Annotated[bool, Query(...)],
    cascade: Annotated[bool, Query(False)],  # noqa: FBT003
) -> PluginToggleResponse:
    result = await plugin_management_service.apply_plugin_toggle(
        module_name, enabled=enabled, cascade=cascade
    )
    return to_plugin_toggle_response(result)


@router.post("/{module_name}/uninstall", response_model=PluginToggleResponse)
async def uninstall_plugin(
    module_name: str,
    body: PluginUninstallRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginToggleResponse:
    result = await plugin_management_service.uninstall_plugin(
        module_name, remove_config=body.remove_config
    )
    return to_plugin_toggle_response(result)


# ── Local sources ───────────────────────────────────────────────


@router.get("/local-sources", response_model=PluginConfigResponse)
async def get_plugin_config(
    _: Annotated[Any, Depends(require_auth)],
) -> PluginConfigResponse:
    return to_plugin_config_response(plugin_management_service.get_plugin_config())


@router.patch("/local-sources", response_model=PluginConfigResponse)
async def update_plugin_config(
    body: PluginConfigRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginConfigResponse:
    return to_plugin_config_response(
        run_settings_action(
            plugin_management_service.update_plugin_config,
            modules=body.modules,
            dirs=body.dirs,
        )
    )


# ── Plugin Store ────────────────────────────────────────────────


@router.get("/store/sources")
async def list_store_sources(
    _: Annotated[Any, Depends(require_auth)],
) -> list[dict[str, Any]]:
    sources = package_store_workflow.list_sources()
    return [to_plugin_store_source_item(s) for s in sources]


@router.get("/store/items", response_model=PluginStoreItemsResponse)
async def list_store_items(  # noqa: PLR0913
    _: Annotated[Any, Depends(require_auth)],
    source_id: str = "",
    keyword: str = "",
    category: str = "",
    sort: str = "",
    installed_only: bool = False,  # noqa: FBT001, FBT002
    uninstalled_only: bool = False,  # noqa: FBT001, FBT002
    page: int = 1,
    page_size: int = 20,
) -> PluginStoreItemsResponse:
    request = PackageStoreListRequest(
        item_type="plugin",
        source_id=source_id,
        keyword=keyword,
        category=category,
        sort=sort,
        installed_only=installed_only,
        uninstalled_only=uninstalled_only,
        page=page,
        page_size=page_size,
    )
    result = await package_store_workflow.list_items(request)
    return PluginStoreItemsResponse(
        items=[to_plugin_store_item(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        has_next=result.has_next,
        categories=[{"value": c.value, "count": c.count} for c in result.categories],
    )


@router.post("/store/refresh")
async def refresh_store(
    _: Annotated[Any, Depends(require_auth)],
    source_id: str = "",
) -> list[dict[str, Any]]:
    sources = await package_store_workflow.refresh_sources(
        "plugin", source_id=source_id
    )
    return [to_plugin_store_source_item(s) for s in sources]


@router.post("/store/install", response_model=PluginStoreTaskItem)
async def install_store_plugin(
    body: PluginStoreInstallRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreTaskItem:
    request = StoreInstallRequest(
        source_id=body.source_id,
        item_id=body.item_id,
        type="plugin",
        package_requirement=body.item_id,
        binding_value=body.module_name or "",
    )
    task = await plugin_store_task_service.create_plugin_install_task(request)
    return to_plugin_store_task_item(task)


@router.post("/store/update", response_model=PluginStoreTaskItem)
async def update_store_plugin(
    body: PluginStoreInstallRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreTaskItem:
    request = StoreInstallRequest(
        source_id=body.source_id,
        item_id=body.item_id,
        type="plugin",
        package_requirement=body.item_id,
        binding_value=body.module_name or "",
    )
    task = await plugin_store_task_service.create_plugin_update_task(request)
    return to_plugin_store_task_item(task)


@router.get("/store/tasks/{task_id}", response_model=PluginStoreTaskItem)
async def get_store_task(
    task_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreTaskItem:
    task = package_store_workflow.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=t("web_ui.tasks.not_found"))
    return to_plugin_store_task_item(task)


@router.post("/store/revert")
async def revert_store_install(
    body: PluginStoreRevertInstallRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> dict[str, str]:
    request = PackageStoreRevertRequest(
        item_type="plugin",
        package_requirement=body.package_requirement,
        binding_value=body.module_name or "",
    )
    package_store_workflow.revert_install(request)
    return {"status": "ok"}


# ── Manual Install ─────────────────────────────────────────────


@router.post("/install/manual", response_model=PluginStoreTaskItem)
async def manual_install(
    body: PluginManualInstallRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreTaskItem:
    task = await plugin_store_task_service.create_manual_plugin_install_task(
        body.requirement, module_name=body.module_name
    )
    return to_plugin_store_task_item(task)


@router.post("/install/resolve", response_model=PluginInstallResolveResponse)
async def resolve_install(
    body: PluginInstallResolveRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginInstallResolveResponse:
    from apeiria.plugins.install_resolution import PluginInstallSource as DomainSource

    source = DomainSource(
        kind=body.source.kind,
        value=body.source.value,
        source_id=body.source.source_id,
        item_id=body.source.item_id,
    )
    result = await plugin_install_resolution_service.resolve(source)
    return PluginInstallResolveResponse.from_domain(result)


@router.post("/install/confirm", response_model=dict)
async def confirm_install(
    body: PluginInstallConfirmRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> dict[str, str]:
    from apeiria.config.plugins import plugin_config_service

    if body.action == "module":
        plugin_config_service.add_project_plugin_module(body.module_name)
    elif body.action == "dir":
        plugin_config_service.add_project_plugin_dir(body.module_name)
    else:
        raise HTTPException(status_code=400, detail="unsupported install action")
    return {"status": "ok"}


# ── Adapter Selection ──────────────────────────────────────────


adapter_router = APIRouter()


@adapter_router.get("/selection", response_model=AdapterSelectionResponse)
async def get_adapter_selection(
    _: Annotated[Any, Depends(require_auth)],
    query: Annotated[AdapterSelectionQueryParams, Depends()],
) -> AdapterSelectionResponse:
    from apeiria.plugins.adapter_selection import AdapterSelectionRequest

    result = await adapter_selection_service.get_selection(
        AdapterSelectionRequest(
            platform=query.platform,
            keyword=query.keyword,
        )
    )
    return to_adapter_selection_response(result)


@adapter_router.post("/enable")
async def enable_adapter(
    body: AdapterSelectionEnableRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> dict[str, str]:
    adapter_selection_service.enable_adapter(body.module_name)
    return {"status": "ok"}


@adapter_router.post("/disable")
async def disable_adapter(
    body: AdapterSelectionEnableRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> dict[str, str]:
    adapter_selection_service.disable_adapter(body.module_name)
    return {"status": "ok"}


# ── Adapter Store ──────────────────────────────────────────────


adapter_store_router = APIRouter()


@adapter_store_router.get("/store/sources")
async def list_adapter_store_sources(
    _: Annotated[Any, Depends(require_auth)],
) -> list[dict[str, Any]]:
    sources = package_store_workflow.list_sources()
    return [to_adapter_store_source_item(s) for s in sources]


@adapter_store_router.get("/store/items", response_model=AdapterStoreItemsResponse)
async def list_adapter_store_items(  # noqa: PLR0913
    _: Annotated[Any, Depends(require_auth)],
    source_id: str = "",
    keyword: str = "",
    category: str = "",
    sort: str = "",
    installed_only: bool = False,  # noqa: FBT001, FBT002
    uninstalled_only: bool = False,  # noqa: FBT001, FBT002
    page: int = 1,
    page_size: int = 20,
) -> AdapterStoreItemsResponse:
    request = PackageStoreListRequest(
        item_type="adapter",
        source_id=source_id,
        keyword=keyword,
        category=category,
        sort=sort,
        installed_only=installed_only,
        uninstalled_only=uninstalled_only,
        page=page,
        page_size=page_size,
    )
    result = await package_store_workflow.list_items(request)
    return AdapterStoreItemsResponse(
        items=[to_adapter_store_item(item) for item in result.items],
        total=result.total,
        page=result.page,
        page_size=result.page_size,
        has_next=result.has_next,
        categories=[{"value": c.value, "count": c.count} for c in result.categories],
    )


@adapter_store_router.post("/store/refresh")
async def refresh_adapter_store(
    _: Annotated[Any, Depends(require_auth)],
    source_id: str = "",
) -> list[dict[str, Any]]:
    sources = await package_store_workflow.refresh_sources(
        "adapter", source_id=source_id
    )
    return [to_adapter_store_source_item(s) for s in sources]


@adapter_store_router.post("/store/install", response_model=AdapterStoreTaskItem)
async def install_adapter(
    body: AdapterStoreMutationRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterStoreTaskItem:
    request = StoreInstallRequest(
        source_id=body.source_id,
        item_id=body.item_id,
        type="adapter",
        package_requirement=body.item_id,
        binding_value=body.module_name or "",
    )
    task = await plugin_store_task_service.create_adapter_install_task(request)
    return to_adapter_store_task_item(task)


@adapter_store_router.post("/store/update", response_model=AdapterStoreTaskItem)
async def update_adapter(
    body: AdapterStoreMutationRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterStoreTaskItem:
    request = StoreInstallRequest(
        source_id=body.source_id,
        item_id=body.item_id,
        type="adapter",
        package_requirement=body.item_id,
        binding_value=body.module_name or "",
    )
    task = await plugin_store_task_service.create_adapter_update_task(request)
    return to_adapter_store_task_item(task)


@adapter_store_router.get("/store/tasks/{task_id}", response_model=AdapterStoreTaskItem)
async def get_adapter_store_task(
    task_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterStoreTaskItem:
    task = package_store_workflow.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=t("web_ui.tasks.not_found"))
    return to_adapter_store_task_item(task)


@adapter_store_router.post("/store/revert")
async def revert_adapter_install(
    body: AdapterStoreRevertInstallRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> dict[str, str]:
    request = PackageStoreRevertRequest(
        item_type="adapter",
        package_requirement=body.package_requirement,
        binding_value=body.module_name or "",
    )
    package_store_workflow.revert_install(request)
    return {"status": "ok"}
