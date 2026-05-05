from __future__ import annotations

import asyncio
from typing import Any

from apeiria.app.plugins.store.models import (
    StoreCategoryCount,
    StoreItem,
    StoreItemType,
    StorePage,
    StoreQuery,
    StoreSource,
    StoreTask,
)
from apeiria.app.plugins.store.workflows import (
    PackageStoreItemRequest,
    PackageStoreListRequest,
    PackageStoreRevertRequest,
    PackageStoreWorkflow,
)
from apeiria.environment.models import PackageOperationRequest
from apeiria.webui.routes import adapter_store, plugin_store


class _FakeStoreService:
    def __init__(self) -> None:
        self.queries: list[StoreQuery] = []
        self.detail_requests: list[dict[str, str]] = []
        self.refresh_requests: list[dict[str, str]] = []
        self.sources = [
            StoreSource(source_id="official", label="Official", kind="builtin")
        ]
        self.page = StorePage(
            items=[
                StoreItem(
                    source_id="official",
                    item_id="console",
                    type="adapter",
                    name="Console",
                    module_name="nonebot.adapters.console",
                    package_requirement="nonebot-adapter-console",
                )
            ],
            total=1,
            page=2,
            page_size=12,
        )

    def list_sources(self) -> list[StoreSource]:
        return self.sources

    async def list_items(self, query: StoreQuery) -> StorePage:
        self.queries.append(query)
        return self.page

    async def get_item(
        self,
        *,
        source_id: str,
        plugin_id: str,
        item_type: str,
    ) -> StoreItem | None:
        self.detail_requests.append(
            {
                "source_id": source_id,
                "plugin_id": plugin_id,
                "item_type": item_type,
            }
        )
        return self.page.items[0]

    async def refresh_sources(
        self,
        *,
        item_type: str,
        source_id: str,
    ) -> list[StoreSource]:
        self.refresh_requests.append(
            {
                "item_type": item_type,
                "source_id": source_id,
            }
        )
        return self.sources


class _FakeTaskService:
    def __init__(self) -> None:
        self.task = StoreTask(
            task_id="task-1",
            title="Install Console",
            status="pending",
            logs="",
        )

    def get_task(self, task_id: str) -> StoreTask | None:
        return self.task if task_id == self.task.task_id else None


class _FakePackageService:
    def __init__(self) -> None:
        self.requests: list[PackageOperationRequest] = []

    def uninstall(self, request: PackageOperationRequest) -> Any:
        self.requests.append(request)
        return None


def test_package_store_workflow_builds_resource_neutral_store_queries() -> None:
    store = _FakeStoreService()
    workflow = PackageStoreWorkflow(
        store_service=store,
        task_service=_FakeTaskService(),
        package_service=_FakePackageService(),
    )

    page = asyncio.run(
        workflow.list_items(
            PackageStoreListRequest(
                item_type="adapter",
                source_id="official",
                keyword="console",
                category="protocol",
                sort="name",
                installed_only=True,
                uninstalled_only=False,
                page=2,
                page_size=12,
            )
        )
    )

    assert page is store.page
    assert store.queries == [
        StoreQuery(
            type="adapter",
            source_id="official",
            keyword="console",
            category="protocol",
            sort="name",
            installed_only=True,
            uninstalled_only=False,
            page=2,
            page_size=12,
        )
    ]


def test_package_store_workflow_owns_common_reads_refresh_and_task_lookup() -> None:
    store = _FakeStoreService()
    task_service = _FakeTaskService()
    workflow = PackageStoreWorkflow(
        store_service=store,
        task_service=task_service,
        package_service=_FakePackageService(),
    )

    assert workflow.list_sources() == store.sources
    assert workflow.get_task("task-1") is task_service.task
    assert workflow.get_task("missing") is None

    detail = asyncio.run(
        workflow.get_item(
            PackageStoreItemRequest(
                item_type="plugin",
                source_id="official",
                item_id="nonebot-plugin-apscheduler",
            )
        )
    )
    refreshed = asyncio.run(workflow.refresh_sources("plugin", source_id="official"))

    assert detail is store.page.items[0]
    assert refreshed == store.sources
    assert store.detail_requests == [
        {
            "source_id": "official",
            "plugin_id": "nonebot-plugin-apscheduler",
            "item_type": "plugin",
        }
    ]
    assert store.refresh_requests == [
        {
            "item_type": "plugin",
            "source_id": "official",
        }
    ]


def test_package_store_workflow_prepares_revert_install_requests() -> None:
    package_service = _FakePackageService()
    workflow = PackageStoreWorkflow(
        store_service=_FakeStoreService(),
        task_service=_FakeTaskService(),
        package_service=package_service,
    )

    workflow.revert_install(
        PackageStoreRevertRequest(
            item_type="adapter",
            package_requirement="nonebot-adapter-console",
            binding_value="nonebot.adapters.console",
        )
    )

    assert package_service.requests == [
        PackageOperationRequest(
            resource_kind="adapter",
            operation="uninstall",
            requirement="nonebot-adapter-console",
            binding_value="nonebot.adapters.console",
        )
    ]


class _FakeRouteWorkflow:
    def __init__(self) -> None:
        self.list_requests: list[PackageStoreListRequest] = []
        self.item_requests: list[PackageStoreItemRequest] = []
        self.refresh_requests: list[tuple[str, str]] = []
        self.task_requests: list[str] = []
        self.revert_requests: list[PackageStoreRevertRequest] = []
        self.sources = [
            StoreSource(source_id="official", label="Official", kind="builtin")
        ]

    def list_sources(self) -> list[StoreSource]:
        return self.sources

    async def list_items(self, request: PackageStoreListRequest) -> StorePage:
        self.list_requests.append(request)
        return StorePage(
            items=[_store_item(request.item_type, "shared")],
            categories=[StoreCategoryCount(value="tools", count=1)],
            total=1,
            page=request.page,
            page_size=request.page_size,
        )

    async def get_item(self, request: PackageStoreItemRequest) -> StoreItem | None:
        self.item_requests.append(request)
        return _store_item(request.item_type, request.item_id)

    async def refresh_sources(
        self,
        item_type: str,
        *,
        source_id: str = "",
    ) -> list[StoreSource]:
        self.refresh_requests.append((item_type, source_id))
        return self.sources

    def get_task(self, task_id: str) -> StoreTask | None:
        self.task_requests.append(task_id)
        return StoreTask(
            task_id=task_id,
            title="Install shared",
            status="pending",
            logs="",
            result={"restart_required": True},
        )

    def revert_install(self, request: PackageStoreRevertRequest) -> None:
        self.revert_requests.append(request)


def _store_item(item_type: StoreItemType, item_id: str) -> StoreItem:
    return StoreItem(
        source_id="official",
        item_id=item_id,
        type=item_type,
        name=f"{item_type.title()} Shared",
        module_name=f"nonebot.{item_type}.shared",
        package_requirement=f"nonebot-{item_type}-shared",
        source_label="Official",
    )


def test_plugin_and_adapter_routes_share_workflow_for_common_reads(
    monkeypatch: Any,
) -> None:
    workflow = _FakeRouteWorkflow()
    monkeypatch.setattr(plugin_store, "package_store_workflow", workflow)
    monkeypatch.setattr(adapter_store, "package_store_workflow", workflow)

    plugin_sources = asyncio.run(plugin_store.list_plugin_store_sources(None))
    adapter_sources = asyncio.run(adapter_store.list_adapter_store_sources(None))
    plugin_items = asyncio.run(
        plugin_store.list_plugin_store_items(
            None,
            plugin_store.PluginStoreItemsQueryParams(
                source="official",
                search="shared",
                category="tools",
                sort="name",
                installed_only=True,
                page=2,
                per_page=8,
            ),
        )
    )
    adapter_items = asyncio.run(
        adapter_store.list_adapter_store_items(
            None,
            adapter_store.AdapterStoreItemsQueryParams(
                source="official",
                search="shared",
                category="tools",
                sort="name",
                installed_only=True,
                page=2,
                per_page=8,
            ),
        )
    )
    plugin_detail = asyncio.run(
        plugin_store.get_plugin_store_item("official", "shared-plugin", None)
    )
    adapter_detail = asyncio.run(
        adapter_store.get_adapter_store_item("official", "shared-adapter", None)
    )

    assert plugin_sources[0].source_id == adapter_sources[0].source_id == "official"
    assert plugin_items.items[0].plugin_id == "shared"
    assert adapter_items.items[0].adapter_id == "shared"
    assert plugin_items.categories[0].value == adapter_items.categories[0].value
    assert plugin_detail.plugin_id == "shared-plugin"
    assert adapter_detail.adapter_id == "shared-adapter"
    assert workflow.list_requests == [
        PackageStoreListRequest(
            item_type="plugin",
            source_id="official",
            keyword="shared",
            category="tools",
            sort="name",
            installed_only=True,
            page=2,
            page_size=8,
        ),
        PackageStoreListRequest(
            item_type="adapter",
            source_id="official",
            keyword="shared",
            category="tools",
            sort="name",
            installed_only=True,
            page=2,
            page_size=8,
        ),
    ]
    assert workflow.item_requests == [
        PackageStoreItemRequest(
            item_type="plugin",
            source_id="official",
            item_id="shared-plugin",
        ),
        PackageStoreItemRequest(
            item_type="adapter",
            source_id="official",
            item_id="shared-adapter",
        ),
    ]


def test_plugin_and_adapter_routes_share_workflow_for_refresh_tasks_and_revert(
    monkeypatch: Any,
) -> None:
    workflow = _FakeRouteWorkflow()
    monkeypatch.setattr(plugin_store, "package_store_workflow", workflow)
    monkeypatch.setattr(adapter_store, "package_store_workflow", workflow)

    plugin_refresh = asyncio.run(
        plugin_store.refresh_plugin_store_sources(
            plugin_store.PluginStoreRefreshRequest(source_id="official"),
            None,
        )
    )
    adapter_refresh = asyncio.run(
        adapter_store.refresh_adapter_store_sources(
            adapter_store.AdapterStoreRefreshRequest(source_id="official"),
            None,
        )
    )
    plugin_task = asyncio.run(plugin_store.get_plugin_store_task("task-1", None))
    adapter_task = asyncio.run(adapter_store.get_adapter_store_task("task-2", None))
    plugin_revert = asyncio.run(
        plugin_store.revert_plugin_store_install(
            plugin_store.PluginStoreRevertInstallRequest(
                package_name="nonebot-plugin-shared",
                module_name="nonebot.plugin.shared",
            ),
            None,
        )
    )
    adapter_revert = asyncio.run(
        adapter_store.revert_adapter_store_install(
            adapter_store.AdapterStoreRevertInstallRequest(
                package_name="nonebot-adapter-shared",
                module_name="nonebot.adapter.shared",
            ),
            None,
        )
    )

    assert plugin_refresh[0].source_id == adapter_refresh[0].source_id == "official"
    assert plugin_task.task_id == "task-1"
    assert adapter_task.task_id == "task-2"
    assert plugin_revert.status == adapter_revert.status == "ok"
    assert workflow.refresh_requests == [
        ("plugin", "official"),
        ("adapter", "official"),
    ]
    assert workflow.task_requests == ["task-1", "task-2"]
    assert workflow.revert_requests == [
        PackageStoreRevertRequest(
            item_type="plugin",
            package_requirement="nonebot-plugin-shared",
            binding_value="nonebot.plugin.shared",
        ),
        PackageStoreRevertRequest(
            item_type="adapter",
            package_requirement="nonebot-adapter-shared",
            binding_value="nonebot.adapter.shared",
        ),
    ]
