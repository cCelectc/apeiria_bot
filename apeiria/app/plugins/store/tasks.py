"""Background tasks for plugin store operations."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from datetime import datetime, timezone
from uuid import uuid4

from apeiria.app.plugins.store.models import (
    StoreInstallRequest,
    StoreItem,
    StoreTask,
)
from apeiria.environment import (
    PackageOperationRequest,
    package_service,
    store_service,
)
from apeiria.plugins.package_ids import normalize_package_id


def _format_task_error(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__


def _store_plugin_not_found_error() -> ValueError:
    return ValueError("store plugin not found")


def _install_task_running_for_plugin_error() -> ValueError:
    return ValueError("install task already running for this plugin")


def _update_task_running_for_plugin_error() -> ValueError:
    return ValueError("update task already running for this plugin")


def _package_name_required_error() -> ValueError:
    return ValueError("package name is required")


def _plugin_module_name_required_error() -> ValueError:
    return ValueError("plugin module name is required")


def _install_task_running_for_target_error() -> ValueError:
    return ValueError("install task already running for this target")


def _update_task_running_for_target_error() -> ValueError:
    return ValueError("update task already running for this target")


def _package_name_mismatch_error() -> ValueError:
    return ValueError("package name mismatch")


def _module_name_mismatch_error() -> ValueError:
    return ValueError("module name mismatch")


def _plugin_cannot_be_updated_from_store_error() -> ValueError:
    return ValueError("plugin cannot be updated from store")


def _installed_package_mismatch_error() -> ValueError:
    return ValueError("installed package does not match store package")


class PluginStoreTaskService:
    """Own in-memory plugin store tasks."""

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
        item = await store_service.get_item(
            source_id=request.source_id,
            plugin_id=request.plugin_id,
            item_type=request.type,
        )
        if item is None:
            raise _store_plugin_not_found_error()
        self._validate_install_request(item, request)
        install_key = self._install_key(request)
        if install_key in self._active_install_keys:
            raise _install_task_running_for_plugin_error()

        task_id = uuid4().hex
        task = StoreTask(
            task_id=task_id,
            title=f"Install {item.name}",
            status="pending",
            logs="",
            created_at=_now(),
        )
        self._tasks[task_id] = task
        self._active_install_keys.add(install_key)
        background_task = asyncio.create_task(
            self._run_plugin_install_task(task_id, item, request, install_key)
        )
        self._background_tasks.add(background_task)
        background_task.add_done_callback(self._background_tasks.discard)
        return task

    async def create_plugin_update_task(
        self,
        request: StoreInstallRequest,
    ) -> StoreTask:
        item = await store_service.get_item(
            source_id=request.source_id,
            plugin_id=request.plugin_id,
            item_type=request.type,
        )
        if item is None:
            raise _store_plugin_not_found_error()
        self._validate_update_request(item, request)
        install_key = ("update", *self._install_key(request))
        if install_key in self._active_install_keys:
            raise _update_task_running_for_plugin_error()

        task_id = uuid4().hex
        task = StoreTask(
            task_id=task_id,
            title=f"Update {item.name}",
            status="pending",
            logs="",
            created_at=_now(),
        )
        self._tasks[task_id] = task
        self._active_install_keys.add(install_key)
        background_task = asyncio.create_task(
            self._run_plugin_update_task(task_id, item, request, install_key)
        )
        self._background_tasks.add(background_task)
        background_task.add_done_callback(self._background_tasks.discard)
        return task

    async def create_manual_plugin_install_task(
        self,
        requirement: str,
        module_name: str | None = None,
    ) -> StoreTask:
        target = requirement.strip()
        resolved_module = (module_name or "").strip()
        if not target:
            raise _package_name_required_error()

        install_key = ("manual", target, resolved_module or "auto")
        if install_key in self._active_install_keys:
            raise _install_task_running_for_target_error()

        task_id = uuid4().hex
        task = StoreTask(
            task_id=task_id,
            title=f"Install {target}",
            status="pending",
            logs="",
            created_at=_now(),
        )
        self._tasks[task_id] = task
        self._active_install_keys.add(install_key)
        background_task = asyncio.create_task(
            self._run_manual_plugin_install_task(
                task_id,
                target,
                resolved_module,
                install_key,
            )
        )
        self._background_tasks.add(background_task)
        background_task.add_done_callback(self._background_tasks.discard)
        return task

    async def create_manual_plugin_update_task(
        self,
        requirement: str,
        module_name: str,
    ) -> StoreTask:
        target = requirement.strip()
        resolved_module = module_name.strip()
        if not target:
            raise _package_name_required_error()
        if not resolved_module:
            raise _plugin_module_name_required_error()

        install_key = ("manual-update", target, resolved_module)
        if install_key in self._active_install_keys:
            raise _update_task_running_for_target_error()

        task_id = uuid4().hex
        task = StoreTask(
            task_id=task_id,
            title=f"Update {resolved_module}",
            status="pending",
            logs="",
            created_at=_now(),
        )
        self._tasks[task_id] = task
        self._active_install_keys.add(install_key)
        background_task = asyncio.create_task(
            self._run_manual_plugin_update_task(
                task_id,
                target,
                resolved_module,
                install_key,
            )
        )
        self._background_tasks.add(background_task)
        background_task.add_done_callback(self._background_tasks.discard)
        return task

    async def _run_plugin_install_task(
        self,
        task_id: str,
        item: StoreItem,
        request: StoreInstallRequest,
        install_key: tuple[str, str, str, str],
    ) -> None:
        self._update_task(
            task_id,
            status="running",
            started_at=_now(),
            logs=(
                f"source: {item.source_name}\n"
                f"plugin: {item.name}\n"
                f"package: {request.package_name}\n"
                f"module: {request.module_name}\n"
            ),
        )
        try:
            result = await asyncio.to_thread(
                package_service.install,
                PackageOperationRequest(
                    resource_kind="plugin",
                    operation="install",
                    requirement=request.package_name,
                    binding_value=request.module_name,
                ),
            )
            self._update_task(
                task_id,
                status="succeeded",
                finished_at=_now(),
                result={
                    "requirement": result.requirement,
                    "module_name": result.binding_value or "",
                    "restart_required": True,
                },
                logs=f"{self._tasks[task_id].logs}install succeeded\n",
            )
        except Exception as exc:  # noqa: BLE001
            error = _format_task_error(exc)
            self._update_task(
                task_id,
                status="failed",
                finished_at=_now(),
                error=error,
                logs=f"{self._tasks[task_id].logs}install failed\n{error}\n",
            )
        finally:
            self._active_install_keys.discard(install_key)

    async def _run_manual_plugin_install_task(
        self,
        task_id: str,
        requirement: str,
        module_name: str,
        install_key: tuple[str, ...],
    ) -> None:
        self._update_task(
            task_id,
            status="running",
            started_at=_now(),
            logs=(
                "source: manual\n"
                f"requirement: {requirement}\n"
                f"module: {module_name or 'auto'}\n"
            ),
        )
        try:
            if module_name:
                result = await asyncio.to_thread(
                    package_service.install,
                    PackageOperationRequest(
                        resource_kind="plugin",
                        operation="install",
                        requirement=requirement,
                        binding_value=module_name,
                    ),
                )
            else:
                result = await asyncio.to_thread(
                    package_service.install,
                    PackageOperationRequest(
                        resource_kind="plugin",
                        operation="install",
                        requirement=requirement,
                    ),
                )
            self._update_task(
                task_id,
                status="succeeded",
                finished_at=_now(),
                result={
                    "requirement": result.requirement,
                    "module_name": result.binding_value or "",
                    "restart_required": True,
                },
                logs=f"{self._tasks[task_id].logs}install succeeded\n",
            )
        except Exception as exc:  # noqa: BLE001
            error = _format_task_error(exc)
            self._update_task(
                task_id,
                status="failed",
                finished_at=_now(),
                error=error,
                logs=f"{self._tasks[task_id].logs}install failed\n{error}\n",
            )
        finally:
            self._active_install_keys.discard(install_key)

    async def _run_manual_plugin_update_task(
        self,
        task_id: str,
        requirement: str,
        module_name: str,
        install_key: tuple[str, ...],
    ) -> None:
        self._update_task(
            task_id,
            status="running",
            started_at=_now(),
            logs=(
                "source: installed\n"
                f"requirement: {requirement}\n"
                f"module: {module_name}\n"
            ),
        )
        try:
            result = await asyncio.to_thread(
                package_service.update,
                PackageOperationRequest(
                    resource_kind="plugin",
                    operation="update",
                    requirement=requirement,
                    binding_value=module_name,
                ),
            )
            self._update_task(
                task_id,
                status="succeeded",
                finished_at=_now(),
                result={
                    "requirement": result.requirement,
                    "module_name": result.binding_value or "",
                    "restart_required": True,
                },
                logs=f"{self._tasks[task_id].logs}update succeeded\n",
            )
        except Exception as exc:  # noqa: BLE001
            error = _format_task_error(exc)
            self._update_task(
                task_id,
                status="failed",
                finished_at=_now(),
                error=error,
                logs=f"{self._tasks[task_id].logs}update failed\n{error}\n",
            )
        finally:
            self._active_install_keys.discard(install_key)

    async def _run_plugin_update_task(
        self,
        task_id: str,
        item: StoreItem,
        request: StoreInstallRequest,
        install_key: tuple[str, ...],
    ) -> None:
        self._update_task(
            task_id,
            status="running",
            started_at=_now(),
            logs=(
                f"source: {item.source_name}\n"
                f"plugin: {item.name}\n"
                f"package: {request.package_name}\n"
                f"module: {request.module_name}\n"
            ),
        )
        try:
            result = await asyncio.to_thread(
                package_service.update,
                PackageOperationRequest(
                    resource_kind="plugin",
                    operation="update",
                    requirement=request.package_name,
                    binding_value=request.module_name,
                ),
            )
            self._update_task(
                task_id,
                status="succeeded",
                finished_at=_now(),
                result={
                    "requirement": result.requirement,
                    "module_name": result.binding_value or "",
                    "restart_required": True,
                },
                logs=f"{self._tasks[task_id].logs}update succeeded\n",
            )
        except Exception as exc:  # noqa: BLE001
            error = _format_task_error(exc)
            self._update_task(
                task_id,
                status="failed",
                finished_at=_now(),
                error=error,
                logs=f"{self._tasks[task_id].logs}update failed\n{error}\n",
            )
        finally:
            self._active_install_keys.discard(install_key)

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
            raise _plugin_cannot_be_updated_from_store_error()
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
    ) -> tuple[str, str, str, str]:
        return (
            request.source_id,
            request.plugin_id,
            request.package_name,
            request.module_name,
        )


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


plugin_store_task_service = PluginStoreTaskService()
