from __future__ import annotations

import asyncio
import shutil
import uuid
from typing import Any

_TASK_CLEANUP_DELAY = 60.0


class TaskRunner:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._tasks: set[asyncio.Task[Any]] = set()

    async def start(  # noqa: PLR0913
        self,
        kind: str,
        name: str,
        pkg_requirement: str = "",
        *,
        module_name: str | None = None,
        uninstall: bool = False,
        keep_config: bool = False,
        update: bool = False,
    ) -> str:
        task_id = uuid.uuid4().hex
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._queues[task_id] = queue
        if update:
            coro = self._do_update(queue, kind, name, pkg_requirement)
        elif uninstall:
            coro = self._do_uninstall(queue, kind, name, keep_config=keep_config)
        else:
            coro = self._do_install(queue, kind, name, pkg_requirement, module_name)
        task = asyncio.create_task(coro)
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task_id

    async def subscribe(self, task_id: str) -> asyncio.Queue[dict[str, Any]] | None:
        return self._queues.get(task_id)

    async def _run_subprocess(
        self,
        queue: asyncio.Queue[dict[str, Any]],
        uv: str,
        *args: str,
    ) -> int | None:
        proc = await asyncio.create_subprocess_exec(
            uv,
            *args,
            "--directory",
            ".apeiria",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        async for line in proc.stdout:  # type: ignore[union-attr]
            text = line.decode("utf-8", errors="replace").rstrip()
            await self._emit(queue, "output", text)
        await proc.wait()
        return proc.returncode

    async def _do_install(
        self,
        queue: asyncio.Queue[dict[str, Any]],
        kind: str,
        name: str,
        pkg_requirement: str,
        module_name: str | None,
    ) -> None:
        uv = shutil.which("uv")
        if uv is None:
            await queue.put({"type": "error", "ok": False, "message": "uv not found"})
            return

        await self._emit(queue, "output", f"> uv add {pkg_requirement}")
        rc = await self._run_subprocess(queue, uv, "add", pkg_requirement)
        if rc != 0:
            await queue.put(
                {"type": "error", "ok": False, "message": f"uv add 返回码: {rc}"}
            )
            return

        if kind == "plugin":
            from apeiria.env.sync import sync_apeiria_env
            from apeiria.plugin.manager import _read_plugins_yaml, _write_plugins_yaml

            data = _read_plugins_yaml()
            packages = data.setdefault("packages", {})
            packages[name] = pkg_requirement
            states = data.setdefault("states", {})
            states[name] = {"enabled": True}
            _write_plugins_yaml(data)
            await self._emit(queue, "output", "> uv sync")
            sync_apeiria_env()
        elif kind == "adapter":
            from apeiria.env.sync import sync_apeiria_env
            from apeiria.plugin.adapter_manager import (
                _read_adapters_yaml,
                _toml_add_adapter,
                _write_adapters_yaml,
            )

            _toml_add_adapter(name, module_name or name)
            data = _read_adapters_yaml()
            packages = data.setdefault("packages", {})
            packages[name] = pkg_requirement
            states = data.setdefault("states", {})
            states[name] = {"enabled": True}
            _write_adapters_yaml(data)
            await self._emit(queue, "output", "> uv sync")
            sync_apeiria_env()

        await queue.put(
            {
                "type": "done",
                "ok": True,
                "name": name,
                "message": f"{name} 安装完成",
            }
        )

    async def _do_uninstall(  # noqa: PLR0915
        self,
        queue: asyncio.Queue[dict[str, Any]],
        kind: str,
        name: str,
        *,
        keep_config: bool,
    ) -> None:
        uv = shutil.which("uv")
        if uv is None:
            await queue.put({"type": "error", "ok": False, "message": "uv not found"})
            return

        if kind == "plugin":
            from apeiria.plugin.manager import _read_plugins_yaml

            data = _read_plugins_yaml()
            packages = data.get("packages") or {}
            pkg_req = packages.get(name) or name
        elif kind == "adapter":
            from apeiria.plugin.adapter_manager import _read_adapters_yaml

            data = _read_adapters_yaml()
            packages = data.get("packages") or {}
            pkg_req = packages.get(name) or name
        else:
            pkg_req = name

        await self._emit(queue, "output", f"> uv remove {pkg_req}")
        rc = await self._run_subprocess(queue, uv, "remove", pkg_req)
        if rc != 0:
            await queue.put(
                {"type": "error", "ok": False, "message": f"uv remove 返回码: {rc}"}
            )
            return

        if kind == "plugin":
            from pathlib import Path

            from apeiria.env.sync import sync_apeiria_env
            from apeiria.plugin.manager import (
                _read_plugins_yaml,
                _remove_plugin_config,
                _write_plugins_yaml,
            )

            data = _read_plugins_yaml()
            packages = data.get("packages") or {}
            packages.pop(name, None)
            states = data.get("states") or {}
            states.pop(name, None)
            _write_plugins_yaml(data)

            local_path = Path(f".apeiria/plugins/{name}")
            if local_path.is_dir():
                import shutil as _shutil

                _shutil.rmtree(local_path, ignore_errors=True)

            if not keep_config:
                _remove_plugin_config(name)

            await self._emit(queue, "output", "> uv sync")
            sync_apeiria_env()
        elif kind == "adapter":
            from apeiria.env.sync import sync_apeiria_env
            from apeiria.plugin.adapter_manager import (
                _read_adapters_yaml,
                _remove_adapter_config,
                _toml_remove_adapter,
                _write_adapters_yaml,
            )

            _toml_remove_adapter(name)
            data = _read_adapters_yaml()
            packages = data.get("packages") or {}
            packages.pop(name, None)
            states = data.get("states") or {}
            states.pop(name, None)
            _write_adapters_yaml(data)

            if not keep_config:
                _remove_adapter_config(name)

            await self._emit(queue, "output", "> uv sync")
            sync_apeiria_env()

        await queue.put(
            {
                "type": "done",
                "ok": True,
                "name": name,
                "message": f"{name} 卸载完成",
            }
        )

    async def _do_update(
        self,
        queue: asyncio.Queue[dict[str, Any]],
        kind: str,
        name: str,
        pkg_requirement: str,
    ) -> None:
        uv = shutil.which("uv")
        if uv is None:
            await queue.put({"type": "error", "ok": False, "message": "uv not found"})
            return

        await self._emit(queue, "output", f"> uv add {pkg_requirement}")
        rc = await self._run_subprocess(queue, uv, "add", pkg_requirement)
        if rc != 0:
            await queue.put(
                {"type": "error", "ok": False, "message": f"uv add 返回码: {rc}"}
            )
            return

        if kind == "plugin":
            from apeiria.env.sync import sync_apeiria_env
            from apeiria.plugin.manager import _read_plugins_yaml, _write_plugins_yaml

            data = _read_plugins_yaml()
            data.setdefault("packages", {})[name] = pkg_requirement
            _write_plugins_yaml(data)
            await self._emit(queue, "output", "> uv sync")
            sync_apeiria_env()
        elif kind == "adapter":
            from apeiria.env.sync import sync_apeiria_env
            from apeiria.plugin.adapter_manager import (
                _read_adapters_yaml,
                _write_adapters_yaml,
            )

            data = _read_adapters_yaml()
            data.setdefault("packages", {})[name] = pkg_requirement
            _write_adapters_yaml(data)
            await self._emit(queue, "output", "> uv sync")
            sync_apeiria_env()

        await queue.put(
            {
                "type": "done",
                "ok": True,
                "name": name,
                "message": f"{name} 更新完成",
            }
        )

    async def _emit(
        self, queue: asyncio.Queue[dict[str, Any]], event_type: str, text: str
    ) -> None:
        await queue.put(
            {
                "type": event_type,
                "text": text,
            }
        )


_runner = TaskRunner()


def get_task_runner() -> TaskRunner:
    return _runner
