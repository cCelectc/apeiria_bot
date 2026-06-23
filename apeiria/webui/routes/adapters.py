"""Unified adapter routes."""

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

config_router = APIRouter()


@config_router.get("/config", response_model=AdapterConfigResponse)
async def get_adapter_config(
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterConfigResponse:
    return to_adapter_config_response(plugin_management_service.get_adapter_config())


@config_router.patch("/config", response_model=AdapterConfigResponse)
async def update_adapter_config(
    payload: AdapterConfigRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterConfigResponse:
    return to_adapter_config_response(
        plugin_management_service.update_adapter_config(payload.modules)
    )


from fastapi import APIRouter, HTTPException

from apeiria.plugins.adapter_selection import (
    AdapterSelectionRequest,
    adapter_selection_service,
)
from apeiria.webui.schemas.adapter_selection import (
    AdapterSelectionEnableRequest,
    AdapterSelectionItem,
    AdapterSelectionQueryParams,
    AdapterSelectionResponse,
    to_adapter_selection_item,
    to_adapter_selection_response,
)

selection_router = APIRouter()


@selection_router.get("", response_model=AdapterSelectionResponse)
async def get_adapter_selection(
    params: Annotated[AdapterSelectionQueryParams, Depends()],
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterSelectionResponse:
    state = await adapter_selection_service.get_selection(
        AdapterSelectionRequest(
            search=params.search,
            source=params.source,
            category=params.category,
            sort=params.sort,
            unenabled_only=params.unenabled_only,
            page=params.page,
            per_page=params.per_page,
        )
    )
    return to_adapter_selection_response(state)


@selection_router.post("/enable", response_model=AdapterSelectionItem)
async def enable_adapter(
    payload: AdapterSelectionEnableRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterSelectionItem:
    try:
        item = adapter_selection_service.enable_adapter(payload.module_name)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return to_adapter_selection_item(item)


@selection_router.post("/disable", response_model=AdapterSelectionItem)
async def disable_adapter(
    payload: AdapterSelectionEnableRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterSelectionItem:
    item = adapter_selection_service.disable_adapter(payload.module_name)
    if item is None:
        raise HTTPException(status_code=404, detail="adapter is not enabled")
    return to_adapter_selection_item(item)


from fastapi import APIRouter
from pydantic import BaseModel, Field

from apeiria.i18n import t
from apeiria.plugins.store.models import StoreInstallRequest
from apeiria.plugins.store.tasks import plugin_store_task_service
from apeiria.plugins.store.workflows import (
    PackageStoreItemRequest,
    PackageStoreListRequest,
    PackageStoreRevertRequest,
    package_store_workflow,
)
from apeiria.webui.schemas.adapter_store import (
    AdapterStoreCategoryItem,
    AdapterStoreItem,
    AdapterStoreItemsResponse,
    AdapterStoreManualInstallRequest,
    AdapterStoreMutationRequest,
    AdapterStoreRevertInstallRequest,
    AdapterStoreSourceItem,
    AdapterStoreTaskItem,
    AdapterStoreUninstallRequest,
    to_adapter_store_item,
    to_adapter_store_source_item,
    to_adapter_store_task_item,
)
from apeiria.webui.schemas.operations import OperationStatusResponse

store_router = APIRouter()


class AdapterStoreItemsQueryParams(BaseModel):
    """Adapter store list query params."""

    source: str = ""
    search: str = ""
    category: str = ""
    sort: str = "default"
    installed_only: bool = False
    uninstalled_only: bool = False
    page: int = Field(default=1, ge=1)
    per_page: int = Field(default=16, ge=1, le=100)


class AdapterStoreRefreshRequest(BaseModel):
    """Adapter store refresh payload."""

    source_id: str = ""


@store_router.get("/sources", response_model=list[AdapterStoreSourceItem])
async def list_adapter_store_sources(
    _: Annotated[Any, Depends(require_auth)],
) -> list[AdapterStoreSourceItem]:
    return [
        to_adapter_store_source_item(item)
        for item in package_store_workflow.list_sources()
    ]


@store_router.get("/items", response_model=AdapterStoreItemsResponse)
async def list_adapter_store_items(
    _: Annotated[Any, Depends(require_auth)],
    params: Annotated[AdapterStoreItemsQueryParams, Depends()],
) -> AdapterStoreItemsResponse:
    result = await package_store_workflow.list_items(
        PackageStoreListRequest(
            item_type="adapter",
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
    return AdapterStoreItemsResponse(
        items=[to_adapter_store_item(item) for item in result.items],
        categories=[
            AdapterStoreCategoryItem(value=item.value, count=item.count)
            for item in result.categories
        ],
        total=result.total,
        page=result.page,
        per_page=result.per_page,
    )


@store_router.get("/items/{source_id}/{adapter_id}", response_model=AdapterStoreItem)
async def get_adapter_store_item(
    source_id: str,
    adapter_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterStoreItem:
    item = await package_store_workflow.get_item(
        PackageStoreItemRequest(
            item_type="adapter",
            source_id=source_id,
            item_id=adapter_id,
        )
    )
    if item is None:
        raise HTTPException(
            status_code=404,
            detail=t("web_ui.plugins.store_not_found"),
        )
    return to_adapter_store_item(item)


@store_router.post("/refresh", response_model=list[AdapterStoreSourceItem])
async def refresh_adapter_store_sources(
    payload: AdapterStoreRefreshRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> list[AdapterStoreSourceItem]:
    return [
        to_adapter_store_source_item(item)
        for item in await package_store_workflow.refresh_sources(
            "adapter",
            source_id=payload.source_id,
        )
    ]


@store_router.post("/install", response_model=AdapterStoreTaskItem)
async def install_adapter_store_item(
    payload: AdapterStoreMutationRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterStoreTaskItem:
    try:
        task = await plugin_store_task_service.create_adapter_install_task(
            StoreInstallRequest(
                source_id=payload.source_id,
                item_id=payload.adapter_id,
                type="adapter",
                package_requirement=payload.package_name,
                binding_value=payload.module_name,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return to_adapter_store_task_item(task)


@store_router.post("/install/manual", response_model=AdapterStoreTaskItem)
async def install_adapter_manual(
    payload: AdapterStoreManualInstallRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterStoreTaskItem:
    try:
        task = await plugin_store_task_service.create_manual_adapter_install_task(
            payload.requirement,
            payload.module_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return to_adapter_store_task_item(task)


@store_router.post("/update", response_model=AdapterStoreTaskItem)
async def update_adapter_store_item(
    payload: AdapterStoreMutationRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterStoreTaskItem:
    try:
        task = await plugin_store_task_service.create_adapter_update_task(
            StoreInstallRequest(
                source_id=payload.source_id,
                item_id=payload.adapter_id,
                type="adapter",
                package_requirement=payload.package_name,
                binding_value=payload.module_name,
            )
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return to_adapter_store_task_item(task)


@store_router.post("/uninstall", response_model=AdapterStoreTaskItem)
async def uninstall_adapter_store_item(
    payload: AdapterStoreUninstallRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterStoreTaskItem:
    try:
        task = await plugin_store_task_service.create_manual_adapter_uninstall_task(
            payload.package_name,
            payload.module_name,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    return to_adapter_store_task_item(task)


@store_router.get("/tasks/{task_id}", response_model=AdapterStoreTaskItem)
async def get_adapter_store_task(
    task_id: str,
    _: Annotated[Any, Depends(require_auth)],
) -> AdapterStoreTaskItem:
    task = package_store_workflow.get_task(task_id)
    if task is None:
        raise HTTPException(status_code=404, detail=t("web_ui.tasks.not_found"))
    return to_adapter_store_task_item(task)


@store_router.post("/revert-install", response_model=OperationStatusResponse)
async def revert_adapter_store_install(
    payload: AdapterStoreRevertInstallRequest,
    _: Annotated[Any, Depends(require_auth)],
) -> OperationStatusResponse:
    try:
        package_store_workflow.revert_install(
            PackageStoreRevertRequest(
                item_type="adapter",
                package_requirement=payload.package_name,
                binding_value=payload.module_name,
            )
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return OperationStatusResponse(status="ok")


router = APIRouter()
router.include_router(config_router)
router.include_router(selection_router, prefix="/selection")
router.include_router(store_router, prefix="/store")
