from __future__ import annotations

import asyncio
import threading
import time
from dataclasses import replace
from typing import TYPE_CHECKING

from apeiria.app.plugins.store.tasks import PluginStoreTaskService
from apeiria.environment import package_service
from apeiria.environment.models import PackageOperationRequest, PackageOperationResult
from apeiria.environment.package_progress import use_package_progress_reporter
from apeiria.plugins.install import PackageService, StoreInstallError

if TYPE_CHECKING:
    from pathlib import Path

    from pytest import MonkeyPatch


class _UnexpectedTestPassError(AssertionError):
    """Raised when a negative-path test did not raise."""


class _ConfigBoomError(RuntimeError):
    """Test config failure sentinel."""

    def __init__(self) -> None:
        super().__init__("config boom")


class _RollbackBoomError(RuntimeError):
    """Test rollback failure sentinel."""

    def __init__(self) -> None:
        super().__init__("rollback boom")


def test_webui_package_tasks_run_in_queue_order_without_overlap(
    monkeypatch: "MonkeyPatch",
) -> None:
    service = PluginStoreTaskService()
    active = 0
    max_active = 0
    calls: list[str] = []
    lock = threading.Lock()
    first_started = threading.Event()
    release_first = threading.Event()

    def fake_perform_operation(
        request: PackageOperationRequest,
    ) -> PackageOperationResult:
        nonlocal active, max_active
        with lock:
            active += 1
            max_active = max(max_active, active)
            calls.append(request.requirement)
        if request.requirement == "package-a":
            first_started.set()
            assert release_first.wait(timeout=2)
        else:
            time.sleep(0.05)
        with lock:
            active -= 1
        return PackageOperationResult(
            resource_kind=request.resource_kind,
            operation=request.operation,
            requirement=request.requirement,
            binding_values=[request.binding_value or ""],
        )

    monkeypatch.setattr(
        "apeiria.app.plugins.store.tasks.package_service.perform_operation",
        fake_perform_operation,
    )

    async def run() -> tuple[str, str]:
        first = await service.create_manual_plugin_install_task(
            "package-a",
            "plugins.package_a",
        )
        second = await service.create_manual_plugin_install_task(
            "package-b",
            "plugins.package_b",
        )
        for _ in range(100):
            if first_started.is_set():
                break
            await asyncio.sleep(0.01)
        queued = service.get_task(second.task_id)
        assert queued is not None
        assert queued.status == "queued"
        assert queued.queue_position == 1
        release_first.set()
        await asyncio.gather(*tuple(service._background_tasks))
        return first.task_id, second.task_id

    first_task_id, second_task_id = asyncio.run(run())

    first_task = service.get_task(first_task_id)
    second_task = service.get_task(second_task_id)
    assert first_task is not None
    assert second_task is not None
    assert calls == ["package-a", "package-b"]
    assert max_active == 1
    assert first_task.status == "succeeded"
    assert second_task.status == "succeeded"


def test_package_service_direct_calls_share_mutation_lock(
    monkeypatch: "MonkeyPatch",
    tmp_path: Path,
) -> None:
    try:
        from apeiria.environment import package_mutation
    except ImportError:
        package_mutation = None
    if package_mutation is not None:
        monkeypatch.setattr(package_mutation, "current_project_root", lambda: tmp_path)

    service = PackageService()
    active = 0
    max_active = 0
    lock = threading.Lock()

    def fake_add_requirement(*args, **kwargs) -> None:  # noqa: ANN002, ANN003
        nonlocal active, max_active
        del args, kwargs
        with lock:
            active += 1
            max_active = max(max_active, active)
        time.sleep(0.05)
        with lock:
            active -= 1

    monkeypatch.setattr(service, "_add_requirement", fake_add_requirement)

    def run_install(name: str) -> None:
        service.install(
            PackageOperationRequest(
                resource_kind="package",
                operation="install",
                requirement=name,
            )
        )

    first = threading.Thread(target=run_install, args=("package-a",))
    second = threading.Thread(target=run_install, args=("package-b",))
    first.start()
    second.start()
    first.join(timeout=2)
    second.join(timeout=2)

    assert not first.is_alive()
    assert not second.is_alive()
    assert max_active == 1


def test_webui_task_waits_for_direct_package_service_lock(
    monkeypatch: "MonkeyPatch",
    tmp_path: Path,
) -> None:
    from apeiria.environment import package_mutation

    service = PluginStoreTaskService()
    monkeypatch.setattr(package_mutation, "current_project_root", lambda: tmp_path)

    adapter = package_service._resource_adapters["plugin"]

    def bind_requirement(requirement: str, binding: str) -> None:
        del requirement, binding

    def after_install(requirement: str, binding: str | None) -> None:
        del requirement, binding

    monkeypatch.setitem(
        package_service._resource_adapters,
        "plugin",
        replace(
            adapter,
            bind_requirement=bind_requirement,
            after_install=after_install,
        ),
    )

    active = 0
    max_active = 0
    active_lock = threading.Lock()
    direct_started = threading.Event()
    release_direct = threading.Event()

    def fake_add_requirement(requirement: str, extra_args: tuple[str, ...]) -> None:
        nonlocal active, max_active
        del extra_args
        with active_lock:
            active += 1
            max_active = max(max_active, active)
        if requirement == "package-a":
            direct_started.set()
            assert release_direct.wait(timeout=2)
        else:
            time.sleep(0.05)
        with active_lock:
            active -= 1

    monkeypatch.setattr(package_service, "_add_requirement", fake_add_requirement)

    def direct_install() -> None:
        package_service.install(
            PackageOperationRequest(
                resource_kind="plugin",
                operation="install",
                requirement="package-a",
                binding_value="plugins.package_a",
            )
        )

    thread = threading.Thread(target=direct_install)
    thread.start()
    assert direct_started.wait(timeout=2)

    async def run_webui_task() -> str:
        task = await service.create_manual_plugin_install_task(
            "package-b",
            "plugins.package_b",
        )
        for _ in range(100):
            current = service.get_task(task.task_id)
            if current and current.status == "running":
                break
            await asyncio.sleep(0.01)
        running = service.get_task(task.task_id)
        assert running is not None
        assert running.current_phase == "waiting_for_lock"
        release_direct.set()
        await asyncio.gather(*tuple(service._background_tasks))
        return task.task_id

    task_id = asyncio.run(run_webui_task())
    thread.join(timeout=2)

    task = service.get_task(task_id)
    assert task is not None
    assert task.status == "succeeded"
    assert max_active == 1


def test_uv_failure_reports_command_progress(
    monkeypatch: "MonkeyPatch",
    tmp_path: Path,
) -> None:
    from apeiria.environment import extension_project

    events: list[tuple[str, str, str | None, str | None]] = []

    class Reporter:
        def waiting_for_lock(self, lock_path: str) -> None:
            del lock_path

        def lock_acquired(self, lock_path: str) -> None:
            del lock_path

        def step_started(
            self,
            phase: str,
            label: str,
            *,
            detail: str | None = None,
            command: str | None = None,
        ) -> None:
            events.append((phase, "started", label, command or detail))

        def step_finished(
            self,
            phase: str,
            *,
            status: str = "succeeded",
            detail: str | None = None,
            output_excerpt: str | None = None,
        ) -> None:
            events.append((phase, status, detail, output_excerpt))

        def diagnostic(self, phase: str, message: str) -> None:
            events.append((phase, "diagnostic", message, None))

    class Result:
        returncode = 2
        stdout = "\x1b[31mstdout failed\x1b[0m"
        stderr = "stderr failed"

    monkeypatch.setattr(extension_project, "find_uv_executable", lambda: "/bin/uv")

    def run_uv_command(*args: object, **kwargs: object) -> Result:
        del args, kwargs
        return Result()

    monkeypatch.setattr(
        extension_project.subprocess,
        "run",
        run_uv_command,
    )

    with use_package_progress_reporter(Reporter()):
        try:
            extension_project._run_uv(["add", "package-a"], cwd=tmp_path)
        except RuntimeError:
            pass
        else:
            raise _UnexpectedTestPassError

    assert (
        "uv_command",
        "started",
        "Running uv command",
        "uv add package-a",
    ) in events
    assert any(
        event[0] == "uv_command"
        and event[1] == "failed"
        and event[3]
        and "stdout failed" in event[3]
        and "stderr failed" in event[3]
        for event in events
    )
    assert any(
        event[0] == "uv_command" and event[1] == "diagnostic" for event in events
    )


def test_config_failure_and_rollback_failure_report_progress(  # noqa: C901
    monkeypatch: "MonkeyPatch",
    tmp_path: Path,
) -> None:
    from apeiria.environment import package_mutation

    monkeypatch.setattr(package_mutation, "current_project_root", lambda: tmp_path)
    service = PackageService()
    adapter = service._resource_adapters["plugin"]

    def fail_bind_requirement(requirement: str, binding: str) -> object:
        del requirement, binding
        raise _ConfigBoomError

    def add_requirement(*args: object, **kwargs: object) -> None:
        del args, kwargs

    def fail_remove_requirement(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise _RollbackBoomError

    service._resource_adapters["plugin"] = replace(
        adapter,
        bind_requirement=fail_bind_requirement,
    )
    monkeypatch.setattr(service, "_add_requirement", add_requirement)
    monkeypatch.setattr(
        "apeiria.plugins.install.remove_plugin_requirement",
        fail_remove_requirement,
    )

    events: list[tuple[str, str, str | None]] = []

    class Reporter:
        def waiting_for_lock(self, lock_path: str) -> None:
            del lock_path

        def lock_acquired(self, lock_path: str) -> None:
            del lock_path

        def step_started(
            self,
            phase: str,
            label: str,
            *,
            detail: str | None = None,
            command: str | None = None,
        ) -> None:
            del command
            events.append((phase, "started", detail or label))

        def step_finished(
            self,
            phase: str,
            *,
            status: str = "succeeded",
            detail: str | None = None,
            output_excerpt: str | None = None,
        ) -> None:
            del output_excerpt
            events.append((phase, status, detail))

        def diagnostic(self, phase: str, message: str) -> None:
            events.append((phase, "diagnostic", message))

    with use_package_progress_reporter(Reporter()):
        try:
            service.install(
                PackageOperationRequest(
                    resource_kind="plugin",
                    operation="install",
                    requirement="package-a",
                    binding_value="plugins.package_a",
                )
            )
        except StoreInstallError as exc:
            error = str(exc)
        else:
            raise _UnexpectedTestPassError

    assert "config boom" in error
    assert "rollback failed" in error
    assert "rollback boom" in error
    assert ("config", "failed", "config boom") in events
    assert ("rollback", "failed", "rollback boom") in events

    service.install(
        PackageOperationRequest(
            resource_kind="package",
            operation="install",
            requirement="package-b",
        )
    )


def test_plugin_store_task_schema_exposes_structured_progress() -> None:
    from apeiria.app.plugins.store.models import StoreTask, StoreTaskStep
    from apeiria.webui.schemas.plugin_store import to_plugin_store_task_item

    task = StoreTask(
        task_id="task-1",
        title="Install package-a",
        status="running",
        logs="running uv add package-a\n",
        operation="install",
        resource_kind="plugin",
        requirement="package-a",
        binding_value="plugins.package_a",
        current_phase="uv_command",
        current_phase_label="Running uv command",
        queue_position=None,
        lock_wait_started_at="2026-05-17T00:00:00+00:00",
        lock_acquired_at="2026-05-17T00:00:01+00:00",
        restart_required=False,
        steps=(
            StoreTaskStep(
                phase="uv_command",
                label="Running uv command",
                status="running",
                command="uv add package-a",
                started_at="2026-05-17T00:00:01+00:00",
            ),
        ),
    )

    payload = to_plugin_store_task_item(task).model_dump()

    assert payload["task_id"] == "task-1"
    assert payload["logs"] == "running uv add package-a\n"
    assert payload["operation"] == "install"
    assert payload["resource_kind"] == "plugin"
    assert payload["requirement"] == "package-a"
    assert payload["binding_value"] == "plugins.package_a"
    assert payload["current_phase"] == "uv_command"
    assert payload["steps"][0]["phase"] == "uv_command"
    assert payload["steps"][0]["command"] == "uv add package-a"
