"""Plugin store routes."""

from __future__ import annotations

from typing import Annotated, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from apeiria.app.plugins.store.models import StoreInstallRequest
from apeiria.app.plugins.store.tasks import plugin_store_task_service
from apeiria.app.plugins.store.workflows import (
    PackageStoreItemRequest,
    PackageStoreListRequest,
    PackageStoreRevertRequest,
    package_store_workflow,
)
from apeiria.i18n import t
from apeiria.webui.auth import require_auth
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
    to_plugin_store_task_item,
)

router = APIRouter()


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


@router.get("/sources", response_model=list[PluginStoreSourceItem])
async def list_plugin_store_sources(
    _: Annotated[Any, Depends(require_auth)],
) -> list[PluginStoreSourceItem]:
    return [
        to_plugin_store_source_item(item)
        for item in package_store_workflow.list_sources()
    ]


@router.get("/items", response_model=PluginStoreItemsResponse)
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


@router.get("/items/{source_id}/{plugin_id}", response_model=PluginStoreItem)
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


@router.post("/refresh", response_model=list[PluginStoreSourceItem])
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


@router.post("/install", response_model=PluginStoreTaskItem)
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


@router.post("/update", response_model=PluginStoreTaskItem)
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


@router.get("/tasks/{task_id}", response_model=PluginStoreTaskItem)
async def get_plugin_store_task(
    task_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> PluginStoreTaskItem:
    task = package_store_workflow.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=t("web_ui.tasks.not_found"))
    return to_plugin_store_task_item(task)


@router.post("/revert-install")
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
