"""Shared package-store workflows for Web UI route adapters."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from apeiria.environment import (
    PackageOperationRequest,
    package_service,
    store_service,
)
from apeiria.plugins.store.models import (
    StoreItem,
    StoreItemType,
    StorePage,
    StoreQuery,
    StoreSource,
    StoreTask,
)
from apeiria.plugins.store.tasks import (
    plugin_store_task_service,
)


@dataclass(frozen=True)
class PackageStoreListRequest:
    """Route-neutral store item list request."""

    item_type: StoreItemType
    source_id: str = ""
    keyword: str = ""
    category: str = ""
    sort: str = "default"
    installed_only: bool = False
    uninstalled_only: bool = False
    page: int = 1
    page_size: int = 16


@dataclass(frozen=True)
class PackageStoreItemRequest:
    """Route-neutral store item detail request."""

    item_type: StoreItemType
    source_id: str
    item_id: str


@dataclass(frozen=True)
class PackageStoreRevertRequest:
    """Route-neutral revert request for a pending install."""

    item_type: StoreItemType
    package_requirement: str
    binding_value: str


class PackageStoreReader(Protocol):
    """Read-side store service contract used by package workflows."""

    def list_sources(self) -> list[StoreSource]: ...

    async def list_items(self, query: StoreQuery) -> StorePage: ...

    async def get_item(
        self,
        *,
        source_id: str,
        plugin_id: str,
        item_type: StoreItemType,
    ) -> StoreItem | None: ...

    async def refresh_sources(
        self,
        *,
        item_type: StoreItemType,
        source_id: str,
    ) -> list[StoreSource]: ...


class PackageStoreTaskReader(Protocol):
    """Task lookup contract used by package workflows."""

    def get_task(self, task_id: str) -> StoreTask | None: ...


class PackageMutationRunner(Protocol):
    """Package mutation contract used by package workflows."""

    def uninstall(self, request: PackageOperationRequest) -> object: ...


class PackageStoreWorkflow:
    """Own common Web UI package-store reads and task/revert operations."""

    def __init__(
        self,
        *,
        store_service: PackageStoreReader,
        task_service: PackageStoreTaskReader,
        package_service: PackageMutationRunner,
    ) -> None:
        self._store_service = store_service
        self._task_service = task_service
        self._package_service = package_service

    def list_sources(self) -> list[StoreSource]:
        return self._store_service.list_sources()

    async def list_items(self, request: PackageStoreListRequest) -> StorePage:
        return await self._store_service.list_items(
            StoreQuery(
                type=request.item_type,
                source_id=request.source_id,
                keyword=request.keyword,
                category=request.category,
                sort=request.sort,
                installed_only=request.installed_only,
                uninstalled_only=request.uninstalled_only,
                page=request.page,
                page_size=request.page_size,
            )
        )

    async def get_item(self, request: PackageStoreItemRequest) -> StoreItem | None:
        return await self._store_service.get_item(
            source_id=request.source_id,
            plugin_id=request.item_id,
            item_type=request.item_type,
        )

    async def refresh_sources(
        self,
        item_type: StoreItemType,
        *,
        source_id: str = "",
    ) -> list[StoreSource]:
        return await self._store_service.refresh_sources(
            item_type=item_type,
            source_id=source_id,
        )

    def get_task(self, task_id: str) -> StoreTask | None:
        return self._task_service.get_task(task_id)

    def revert_install(self, request: PackageStoreRevertRequest) -> None:
        self._package_service.uninstall(
            PackageOperationRequest(
                resource_kind=request.item_type,
                operation="uninstall",
                requirement=request.package_requirement,
                binding_value=request.binding_value,
            )
        )


package_store_workflow = PackageStoreWorkflow(
    store_service=store_service,
    task_service=plugin_store_task_service,
    package_service=package_service,
)
