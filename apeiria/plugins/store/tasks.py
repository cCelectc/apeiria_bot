"""Background tasks for Web UI package store operations."""

from __future__ import annotations

import asyncio
import threading
from collections import deque
from dataclasses import replace
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Literal
from uuid import uuid4

from apeiria.environment import (
    PackageOperationRequest,
    package_service,
    store_service,
)
from apeiria.environment.package_progress import (
    PackageProgressReporter,
    use_package_progress_reporter,
)
from apeiria.plugins.package_ids import normalize_package_id
from apeiria.plugins.store.models import (
    StoreInstallRequest,
    StoreItem,
    StoreItemType,
    StoreTask,
    StoreTaskStep,
)

if TYPE_CHECKING:
    from collections.abc import Callable, Coroutine

    from apeiria.environment import PackageOperationResult

PackageMutationOperation = Literal["install", "update", "uninstall"]
MAX_DIAGNOSTICS = 8


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
        self._queue: deque[
            tuple[str, Callable[[], Coroutine[object, object, None]]]
        ] = deque()
        self._worker_task: asyncio.Task[None] | None = None
        self._running_task_id: str | None = None

    def get_task(self, task_id: str) -> StoreTask | None:
        return self._tasks.get(task_id)

    def get_active_task(self) -> StoreTask | None:
        if self._running_task_id is not None:
            task = self._tasks.get(self._running_task_id)
            if task is not None and task.status in {"queued", "pending", "running"}:
                return task
        for task_id, _ in self._queue:
            task = self._tasks.get(task_id)
            if task is not None and task.status in {"queued", "pending", "running"}:
                return task
        return None

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
            operation="install",
            resource_kind=request.type,
            requirement=request.package_name,
            binding_value=request.module_name,
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
            operation="update",
            resource_kind=request.type,
            requirement=request.package_name,
            binding_value=request.module_name,
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
            operation="install",
            resource_kind=resource_kind,
            requirement=target,
            binding_value=resolved_module or None,
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
            operation="update",
            resource_kind=resource_kind,
            requirement=target,
            binding_value=resolved_module,
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
            operation="uninstall",
            resource_kind=resource_kind,
            requirement=target,
            binding_value=resolved_module,
            runner_factory=lambda task_id: self._run_manual_mutation_task(
                task_id=task_id,
                resource_kind=resource_kind,
                operation="uninstall",
                requirement=target,
                module_name=resolved_module,
                task_key=install_key,
            ),
        )

    def _create_store_task(  # noqa: PLR0913
        self,
        *,
        task_key: tuple[str, ...],
        title: str,
        operation: PackageMutationOperation,
        resource_kind: StoreItemType,
        requirement: str,
        binding_value: str | None,
        runner_factory: "Callable[[str], Coroutine[object, object, None]]",
    ) -> StoreTask:
        task_id = uuid4().hex
        created_at = _now()

        def runner() -> Coroutine[object, object, None]:
            return runner_factory(task_id)

        task = StoreTask(
            task_id=task_id,
            title=title,
            status="queued",
            logs="queued\n",
            created_at=created_at,
            operation=operation,
            resource_kind=resource_kind,
            requirement=requirement,
            binding_value=binding_value,
            current_phase="queued",
            current_phase_label="Queued",
            steps=(
                StoreTaskStep(
                    phase="queued",
                    label="Queued",
                    status="running",
                    detail="Waiting for earlier package tasks.",
                    started_at=created_at,
                ),
            ),
        )
        self._tasks[task_id] = task
        self._active_install_keys.add(task_key)
        self._queue.append((task_id, runner))
        self._refresh_queue_positions()
        self._ensure_worker()
        return task

    def _ensure_worker(self) -> None:
        if self._worker_task is not None and not self._worker_task.done():
            return
        self._worker_task = asyncio.create_task(self._run_task_queue())
        self._background_tasks.add(self._worker_task)
        self._worker_task.add_done_callback(self._background_tasks.discard)

    async def _run_task_queue(self) -> None:
        while self._queue:
            task_id, runner = self._queue.popleft()
            self._running_task_id = task_id
            self._refresh_queue_positions()
            try:
                await runner()
            finally:
                self._running_task_id = None
                self._refresh_queue_positions()

    def _refresh_queue_positions(self) -> None:
        for position, (task_id, _) in enumerate(self._queue, start=1):
            task = self._tasks.get(task_id)
            if task is None or task.status != "queued":
                continue
            self._tasks[task_id] = replace(task, queue_position=position)

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
            self._begin_task_execution(
                task_id,
                detail=(
                    f"source: {item.source_name}\n"
                    f"{resource_label}: {item.name}\n"
                    f"package: {request.package_name}\n"
                    f"{_binding_label(request.type)}: {request.module_name}"
                ),
            )
            result = await asyncio.to_thread(
                self._perform_operation_with_progress,
                task_id,
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
            self._begin_task_execution(
                task_id,
                detail=(
                    f"source: {_manual_source_label(operation)}\n"
                    f"requirement: {requirement}\n"
                    f"{_binding_label(resource_kind)}: {module_name or 'auto'}"
                ),
            )
            operation_request = PackageOperationRequest(
                resource_kind=resource_kind,
                operation=operation,
                requirement=requirement,
                binding_value=module_name or None,
            )
            result = await asyncio.to_thread(
                self._perform_operation_with_progress,
                task_id,
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
        self._finish_current_step(task_id, status="succeeded")
        finished_at = _now()
        self._update_task(
            task_id,
            status="succeeded",
            finished_at=finished_at,
            current_phase="succeeded",
            current_phase_label="Succeeded",
            progress_percent=100,
            queue_position=None,
            restart_required=result.restart_required,
            steps=(
                *self._tasks[task_id].steps,
                StoreTaskStep(
                    phase="succeeded",
                    label="Succeeded",
                    status="succeeded",
                    detail=f"{operation} succeeded.",
                    started_at=finished_at,
                    finished_at=finished_at,
                ),
            ),
            result={
                "requirement": result.requirement,
                "module_name": result.binding_value or "",
                "resource_kind": resource_kind,
                "restart_required": result.restart_required,
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
        self._finish_current_step(task_id, status="failed", detail=error)
        task = self._tasks[task_id]
        self._update_task(
            task_id,
            status="failed",
            finished_at=_now(),
            current_phase="failed",
            current_phase_label="Failed",
            queue_position=None,
            error=error,
            diagnostics=(
                [
                    *task.diagnostics,
                    {
                        "phase": task.current_phase or "failed",
                        "message": error,
                    },
                ]
            )[-MAX_DIAGNOSTICS:],
            logs=f"{self._tasks[task_id].logs}{operation} failed\n{error}\n",
        )

    def _begin_task_execution(self, task_id: str, *, detail: str) -> None:
        started_at = _now()
        self._finish_step(task_id, "queued", status="succeeded", finished_at=started_at)
        self._update_task(
            task_id,
            status="running",
            started_at=started_at,
            queue_position=None,
            logs=f"{self._tasks[task_id].logs}{detail}\n",
        )
        self._start_step(
            task_id,
            "waiting_for_lock",
            "Waiting for package mutation lock",
            detail="Waiting for project package mutation lock.",
            started_at=started_at,
        )

    def _perform_operation_with_progress(
        self,
        task_id: str,
        request: PackageOperationRequest,
    ) -> "PackageOperationResult":
        reporter = _TaskProgressReporter(self, task_id)
        with use_package_progress_reporter(reporter):
            return package_service.perform_operation(request)

    def _start_step(  # noqa: PLR0913
        self,
        task_id: str,
        phase: str,
        label: str,
        *,
        detail: str | None = None,
        command: str | None = None,
        started_at: str | None = None,
    ) -> None:
        now = started_at or _now()
        self._finish_current_step(task_id, status="succeeded", finished_at=now)
        task = self._tasks[task_id]
        self._update_task(
            task_id,
            current_phase=phase,
            current_phase_label=label,
            steps=(
                *task.steps,
                StoreTaskStep(
                    phase=phase,
                    label=label,
                    status="running",
                    detail=detail,
                    command=command,
                    started_at=now,
                ),
            ),
            logs=f"{task.logs}{label}\n",
        )

    def _finish_current_step(
        self,
        task_id: str,
        *,
        status: str,
        detail: str | None = None,
        output_excerpt: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        task = self._tasks[task_id]
        if task.current_phase is None:
            return
        self._finish_step(
            task_id,
            task.current_phase,
            status=status,
            detail=detail,
            output_excerpt=output_excerpt,
            finished_at=finished_at,
        )

    def _finish_step(  # noqa: PLR0913
        self,
        task_id: str,
        phase: str,
        *,
        status: str,
        detail: str | None = None,
        output_excerpt: str | None = None,
        finished_at: str | None = None,
    ) -> None:
        task = self._tasks[task_id]
        if not task.steps:
            return
        steps = list(task.steps)
        for index in range(len(steps) - 1, -1, -1):
            step = steps[index]
            if step.phase != phase or step.status != "running":
                continue
            steps[index] = replace(
                step,
                status=status,
                detail=detail if detail is not None else step.detail,
                output_excerpt=(
                    output_excerpt
                    if output_excerpt is not None
                    else step.output_excerpt
                ),
                finished_at=finished_at or _now(),
            )
            self._update_task(task_id, steps=tuple(steps))
            return

    def _add_diagnostic(self, task_id: str, phase: str, message: str) -> None:
        task = self._tasks[task_id]
        self._update_task(
            task_id,
            diagnostics=(
                [
                    *task.diagnostics,
                    {
                        "phase": phase,
                        "message": message,
                    },
                ]
            )[-MAX_DIAGNOSTICS:],
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


class _TaskProgressReporter(PackageProgressReporter):
    """Bridge package operation progress into one Web UI store task."""

    def __init__(self, service: PluginStoreTaskService, task_id: str) -> None:
        self._service = service
        self._task_id = task_id
        self._lock = threading.Lock()

    def waiting_for_lock(self, lock_path: str) -> None:
        with self._lock:
            started_at = _now()
            task = self._service.get_task(self._task_id)
            if task is None:
                return
            if task.current_phase != "waiting_for_lock":
                self._service._start_step(
                    self._task_id,
                    "waiting_for_lock",
                    "Waiting for package mutation lock",
                    detail=lock_path,
                    started_at=started_at,
                )
            self._service._update_task(
                self._task_id,
                current_phase="waiting_for_lock",
                current_phase_label="Waiting for package mutation lock",
                lock_wait_started_at=task.lock_wait_started_at or started_at,
            )

    def lock_acquired(self, lock_path: str) -> None:
        with self._lock:
            acquired_at = _now()
            self._service._finish_step(
                self._task_id,
                "waiting_for_lock",
                status="succeeded",
                detail=lock_path,
                finished_at=acquired_at,
            )
            self._service._update_task(
                self._task_id,
                lock_acquired_at=acquired_at,
                current_phase="mutating",
                current_phase_label="Mutating package environment",
            )

    def step_started(
        self,
        phase: str,
        label: str,
        *,
        detail: str | None = None,
        command: str | None = None,
    ) -> None:
        with self._lock:
            self._service._start_step(
                self._task_id,
                phase,
                label,
                detail=detail,
                command=command,
            )

    def step_finished(
        self,
        phase: str,
        *,
        status: str = "succeeded",
        detail: str | None = None,
        output_excerpt: str | None = None,
    ) -> None:
        with self._lock:
            self._service._finish_step(
                self._task_id,
                phase,
                status=status,
                detail=detail,
                output_excerpt=output_excerpt,
            )

    def diagnostic(self, phase: str, message: str) -> None:
        with self._lock:
            self._service._add_diagnostic(self._task_id, phase, message)


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
