"""Background tasks for Web UI package store operations."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from apeiria.app.plugins.store.models import (
    StoreInstallRequest,
    StoreItem,
    StoreItemType,
    StoreTask,
)
from apeiria.environment import (
    PackageOperationRequest,
    package_service,
    store_service,
)
from apeiria.plugins.package_ids import normalize_package_id

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from apeiria.environment import PackageOperationResult

PackageMutationOperation = Literal["install", "update", "uninstall"]


def _format_task_error(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__


def _store_package_not_found_error() -> ValueError:
    return ValueError("store package not found")


def _install_task_running_for_item_error() -> ValueError:
    return ValueError("install task already running for this store item")


def _update_task_running_for_item_error() -> ValueError:
    return ValueError("update task already running for this store item")


def _package_name_required_error() -> ValueError:
    return ValueError("package name is required")


def _module_name_required_error() -> ValueError:
    return ValueError("module name is required")


def _install_task_running_for_target_error() -> ValueError:
    return ValueError("install task already running for this target")


def _update_task_running_for_target_error() -> ValueError:
    return ValueError("update task already running for this target")


def _uninstall_task_running_for_target_error() -> ValueError:
    return ValueError("uninstall task already running for this target")


def _package_name_mismatch_error() -> ValueError:
    return ValueError("package name mismatch")


def _module_name_mismatch_error() -> ValueError:
    return ValueError("module name mismatch")


def _resource_cannot_be_updated_from_store_error() -> ValueError:
    return ValueError("resource cannot be updated from store")


def _installed_package_mismatch_error() -> ValueError:
    return ValueError("installed package does not match store package")


class PluginStoreTaskService:
    """Own in-memory Web UI package store tasks."""

    def __init__(self) -> None:
        self._tasks: dict[str, StoreTask] = {}
        self._background_tasks: set[asyncio.Task[None]] = set()
        self._active_install_keys: set[tuple[str, ...]] = set()

    def get_task(self, task_id: str) -> StoreTask | None:
        return self._tasks.get(task_id)

    async def create_plugin_install_task(
        self,
        request: StoreInstallRequest,
    ) -> StoreTask:
        return await self.create_store_install_task(request)

    async def create_adapter_install_task(
        self,
        request: StoreInstallRequest,
    ) -> StoreTask:
        return await self.create_store_install_task(request)

    async def create_store_install_task(
        self,
        request: StoreInstallRequest,
    ) -> StoreTask:
        item = await store_service.get_item(
            source_id=request.source_id,
            plugin_id=request.plugin_id,
            item_type=request.type,
        )
        if item is None:
            raise _store_package_not_found_error()
        self._validate_install_request(item, request)
        install_key = self._install_key(request)
        if install_key in self._active_install_keys:
            raise _install_task_running_for_item_error()
        return self._create_store_task(
            task_key=install_key,
            title=f"Install {item.name}",
            runner_factory=lambda task_id: self._run_store_mutation_task(
                task_id=task_id,
                item=item,
                operation="install",
                request=request,
                task_key=install_key,
            ),
        )

    async def create_plugin_update_task(
        self,
        request: StoreInstallRequest,
    ) -> StoreTask:
        return await self.create_store_update_task(request)

    async def create_adapter_update_task(
        self,
        request: StoreInstallRequest,
    ) -> StoreTask:
        return await self.create_store_update_task(request)

    async def create_store_update_task(
        self,
        request: StoreInstallRequest,
    ) -> StoreTask:
        item = await store_service.get_item(
            source_id=request.source_id,
            plugin_id=request.plugin_id,
            item_type=request.type,
        )
        if item is None:
            raise _store_package_not_found_error()
        self._validate_update_request(item, request)
        install_key = ("update", *self._install_key(request))
        if install_key in self._active_install_keys:
            raise _update_task_running_for_item_error()
        return self._create_store_task(
            task_key=install_key,
            title=f"Update {item.name}",
            runner_factory=lambda task_id: self._run_store_mutation_task(
                task_id=task_id,
                item=item,
                operation="update",
                request=request,
                task_key=install_key,
            ),
        )

    async def create_manual_plugin_install_task(
        self,
        requirement: str,
        module_name: str | None = None,
    ) -> StoreTask:
        return await self.create_manual_install_task(
            resource_kind="plugin",
            requirement=requirement,
            module_name=module_name,
        )

    async def create_manual_adapter_install_task(
        self,
        requirement: str,
        module_name: str | None = None,
    ) -> StoreTask:
        return await self.create_manual_install_task(
            resource_kind="adapter",
            requirement=requirement,
            module_name=module_name,
        )

    async def create_manual_install_task(
        self,
        *,
        resource_kind: StoreItemType,
        requirement: str,
        module_name: str | None = None,
    ) -> StoreTask:
        target = requirement.strip()
        resolved_module = (module_name or "").strip()
        if not target:
            raise _package_name_required_error()

        install_key = (
            "manual-install",
            resource_kind,
            target,
            resolved_module or "auto",
        )
        if install_key in self._active_install_keys:
            raise _install_task_running_for_target_error()

        return self._create_store_task(
            task_key=install_key,
            title=f"Install {target}",
            runner_factory=lambda task_id: self._run_manual_mutation_task(
                task_id=task_id,
                resource_kind=resource_kind,
                operation="install",
                requirement=target,
                module_name=resolved_module,
                task_key=install_key,
            ),
        )

    async def create_manual_plugin_update_task(
        self,
        requirement: str,
        module_name: str,
    ) -> StoreTask:
        return await self.create_manual_update_task(
            resource_kind="plugin",
            requirement=requirement,
            module_name=module_name,
        )

    async def create_manual_adapter_update_task(
        self,
        requirement: str,
        module_name: str,
    ) -> StoreTask:
        return await self.create_manual_update_task(
            resource_kind="adapter",
            requirement=requirement,
            module_name=module_name,
        )

    async def create_manual_update_task(
        self,
        *,
        resource_kind: StoreItemType,
        requirement: str,
        module_name: str,
    ) -> StoreTask:
        target = requirement.strip()
        resolved_module = module_name.strip()
        if not target:
            raise _package_name_required_error()
        if not resolved_module:
            raise _module_name_required_error()

        install_key = ("manual-update", resource_kind, target, resolved_module)
        if install_key in self._active_install_keys:
            raise _update_task_running_for_target_error()

        return self._create_store_task(
            task_key=install_key,
            title=f"Update {resolved_module}",
            runner_factory=lambda task_id: self._run_manual_mutation_task(
                task_id=task_id,
                resource_kind=resource_kind,
                operation="update",
                requirement=target,
                module_name=resolved_module,
                task_key=install_key,
            ),
        )

    async def create_manual_adapter_uninstall_task(
        self,
        requirement: str,
        module_name: str,
    ) -> StoreTask:
        return await self.create_manual_uninstall_task(
            resource_kind="adapter",
            requirement=requirement,
            module_name=module_name,
        )

    async def create_manual_uninstall_task(
        self,
        *,
        resource_kind: StoreItemType,
        requirement: str,
        module_name: str,
    ) -> StoreTask:
        target = requirement.strip()
        resolved_module = module_name.strip()
        if not target:
            raise _package_name_required_error()
        if not resolved_module:
            raise _module_name_required_error()

        install_key = ("manual-uninstall", resource_kind, target, resolved_module)
        if install_key in self._active_install_keys:
            raise _uninstall_task_running_for_target_error()

        return self._create_store_task(
            task_key=install_key,
            title=f"Uninstall {resolved_module}",
            runner_factory=lambda task_id: self._run_manual_mutation_task(
                task_id=task_id,
                resource_kind=resource_kind,
                operation="uninstall",
                requirement=target,
                module_name=resolved_module,
                task_key=install_key,
            ),
        )

    def _create_store_task(
        self,
        *,
        task_key: tuple[str, ...],
        title: str,
        runner_factory: "Callable[[str], Coroutine[object, object, None]]",
    ) -> StoreTask:
        task_id = uuid4().hex
        task = StoreTask(
            task_id=task_id,
            title=title,
            status="pending",
            logs="",
            created_at=_now(),
        )
        self._tasks[task_id] = task
        self._active_install_keys.add(task_key)
        background_task = asyncio.create_task(runner_factory(task_id))
        self._background_tasks.add(background_task)
        background_task.add_done_callback(self._background_tasks.discard)
        return task

    async def _run_store_mutation_task(
        self,
        *,
        task_id: str,
        item: StoreItem,
        operation: PackageMutationOperation,
        request: StoreInstallRequest,
        task_key: tuple[str, ...],
    ) -> None:
        resource_label = _resource_label(request.type)
        try:
            self._update_task(
                task_id,
                status="running",
                started_at=_now(),
                logs=(
                    f"source: {item.source_name}\n"
                    f"{resource_label}: {item.name}\n"
                    f"package: {request.package_name}\n"
                    f"{_binding_label(request.type)}: {request.module_name}\n"
                ),
            )
            result = await asyncio.to_thread(
                package_service.perform_operation,
                PackageOperationRequest(
                    resource_kind=request.type,
                    operation=operation,
                    requirement=request.package_name,
                    binding_value=request.module_name,
                ),
            )
            self._mark_task_succeeded(
                task_id,
                operation=operation,
                resource_kind=request.type,
                result=result,
            )
        except Exception as exc:  # noqa: BLE001
            self._mark_task_failed(task_id, operation=operation, exc=exc)
        finally:
            self._active_install_keys.discard(task_key)

    async def _run_manual_mutation_task(  # noqa: PLR0913
        self,
        *,
        task_id: str,
        resource_kind: StoreItemType,
        operation: PackageMutationOperation,
        requirement: str,
        module_name: str,
        task_key: tuple[str, ...],
    ) -> None:
        try:
            self._update_task(
                task_id,
                status="running",
                started_at=_now(),
                logs=(
                    f"source: {_manual_source_label(operation)}\n"
                    f"requirement: {requirement}\n"
                    f"{_binding_label(resource_kind)}: {module_name or 'auto'}\n"
                ),
            )
            operation_request = PackageOperationRequest(
                resource_kind=resource_kind,
                operation=operation,
                requirement=requirement,
                binding_value=module_name or None,
            )
            result = await asyncio.to_thread(
                package_service.perform_operation,
                operation_request,
            )
            self._mark_task_succeeded(
                task_id,
                operation=operation,
                resource_kind=resource_kind,
                result=result,
            )
        except Exception as exc:  # noqa: BLE001
            self._mark_task_failed(task_id, operation=operation, exc=exc)
        finally:
            self._active_install_keys.discard(task_key)

    def _mark_task_succeeded(
        self,
        task_id: str,
        *,
        operation: PackageMutationOperation,
        resource_kind: StoreItemType,
        result: "PackageOperationResult",
    ) -> None:
        self._update_task(
            task_id,
            status="succeeded",
            finished_at=_now(),
            result={
                "requirement": result.requirement,
                "module_name": result.binding_value or "",
                "resource_kind": resource_kind,
                "restart_required": True,
            },
            logs=f"{self._tasks[task_id].logs}{operation} succeeded\n",
        )

    def _mark_task_failed(
        self,
        task_id: str,
        *,
        operation: PackageMutationOperation,
        exc: Exception,
    ) -> None:
        error = _format_task_error(exc)
        self._update_task(
            task_id,
            status="failed",
            finished_at=_now(),
            error=error,
            logs=f"{self._tasks[task_id].logs}{operation} failed\n{error}\n",
        )

    def _validate_install_request(
        self,
        item: StoreItem,
        request: StoreInstallRequest,
    ) -> None:
        if item.package_name != request.package_name:
            raise _package_name_mismatch_error()
        if item.module_name != request.module_name:
            raise _module_name_mismatch_error()

    def _validate_update_request(
        self,
        item: StoreItem,
        request: StoreInstallRequest,
    ) -> None:
        self._validate_install_request(item, request)
        if not item.can_update:
            raise _resource_cannot_be_updated_from_store_error()
        installed_package = normalize_package_id(item.installed_package or "")
        store_package = normalize_package_id(request.package_name)
        if not installed_package or installed_package != store_package:
            raise _installed_package_mismatch_error()

    def _update_task(self, task_id: str, **updates: object) -> None:
        current = self._tasks[task_id]
        self._tasks[task_id] = replace(current, **updates)

    def _install_key(
        self,
        request: StoreInstallRequest,
    ) -> tuple[str, ...]:
        return (
            request.type,
            request.source_id,
            request.plugin_id,
            request.package_name,
            request.module_name,
        )


def _manual_source_label(operation: PackageMutationOperation) -> str:
    if operation == "update":
        return "installed"
    if operation == "uninstall":
        return "project"
    return "manual"


def _binding_label(resource_kind: StoreItemType) -> str:
    if resource_kind in {"plugin", "adapter"}:
        return "module"
    return "binding"


def _resource_label(resource_kind: StoreItemType) -> str:
    return resource_kind


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


plugin_store_task_service = PluginStoreTaskService()
