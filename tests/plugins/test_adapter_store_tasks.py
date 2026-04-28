from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from apeiria.app.plugins.store.models import StoreInstallRequest, StoreItem
from apeiria.app.plugins.store.tasks import PluginStoreTaskService
from apeiria.environment.models import PackageOperationRequest, PackageOperationResult

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_create_adapter_install_task_uses_adapter_resource_kind(
    monkeypatch: MonkeyPatch,
) -> None:
    service = PluginStoreTaskService()
    item = StoreItem(
        source_id="official",
        item_id="console",
        type="adapter",
        name="Console Adapter",
        module_name="nonebot.adapters.console",
        package_requirement="nonebot-adapter-console",
    )
    calls = []

    async def fake_get_item(
        *,
        source_id: str,
        plugin_id: str,
        item_type: str,
    ) -> StoreItem | None:
        assert source_id == "official"
        assert plugin_id == "console"
        assert item_type == "adapter"
        return item

    def fake_install(request: PackageOperationRequest):
        calls.append(request)
        return PackageOperationResult(
            resource_kind="adapter",
            operation="install",
            requirement=request.requirement,
            binding_values=[request.binding_value or ""],
        )

    monkeypatch.setattr(
        "apeiria.app.plugins.store.tasks.store_service.get_item",
        fake_get_item,
    )
    monkeypatch.setattr(
        "apeiria.app.plugins.store.tasks.package_service.install",
        fake_install,
    )

    async def run() -> str:
        task = await service.create_adapter_install_task(
            StoreInstallRequest(
                source_id="official",
                item_id="console",
                type="adapter",
                package_requirement="nonebot-adapter-console",
                binding_value="nonebot.adapters.console",
            )
        )
        await asyncio.gather(*tuple(service._background_tasks))
        return task.task_id

    task_id = asyncio.run(run())

    result = service.get_task(task_id)
    assert result is not None
    assert calls and calls[0].resource_kind == "adapter"
    assert result.status == "succeeded"
    assert result.result["module_name"] == "nonebot.adapters.console"


def test_create_manual_adapter_uninstall_task_uses_adapter_resource_kind(
    monkeypatch: MonkeyPatch,
) -> None:
    service = PluginStoreTaskService()
    calls = []

    def fake_uninstall(request: PackageOperationRequest):
        calls.append(request)
        return PackageOperationResult(
            resource_kind="adapter",
            operation="uninstall",
            requirement=request.requirement,
            binding_values=[request.binding_value or ""],
        )

    monkeypatch.setattr(
        "apeiria.app.plugins.store.tasks.package_service.uninstall",
        fake_uninstall,
    )

    async def run() -> str:
        task = await service.create_manual_adapter_uninstall_task(
            "nonebot-adapter-console",
            "nonebot.adapters.console",
        )
        await asyncio.gather(*tuple(service._background_tasks))
        return task.task_id

    task_id = asyncio.run(run())

    result = service.get_task(task_id)
    assert result is not None
    assert calls and calls[0].resource_kind == "adapter"
    assert calls[0].operation == "uninstall"
    assert result.status == "succeeded"
    assert result.result["module_name"] == "nonebot.adapters.console"
