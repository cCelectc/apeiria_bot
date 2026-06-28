from __future__ import annotations

import asyncio
import shutil
import uuid
from typing import Any

from nonebot.log import logger

_TASK_CLEANUP_DELAY = 60.0


class TaskRunner:
    def __init__(self) -> None:
        self._queues: dict[str, asyncio.Queue[dict[str, Any]]] = {}
        self._tasks: set[asyncio.Task[Any]] = set()

    async def start(
        self,
        kind: str,
        name: str,
        pkg_requirement: str,
        *,
        module_name: str | None = None,
    ) -> str:
        task_id = uuid.uuid4().hex
        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue()
        self._queues[task_id] = queue
        task = asyncio.create_task(
            self._run(task_id, queue, kind, name, pkg_requirement, module_name)
        )
        self._tasks.add(task)
        task.add_done_callback(self._tasks.discard)
        return task_id

    async def subscribe(self, task_id: str) -> asyncio.Queue[dict[str, Any]] | None:
        return self._queues.get(task_id)

    async def _run(  # noqa: PLR0913
        self,
        task_id: str,
        queue: asyncio.Queue[dict[str, Any]],
        kind: str,
        name: str,
        pkg_requirement: str,
        module_name: str | None,
    ) -> None:
        try:
            await self._do_install(queue, kind, name, pkg_requirement, module_name)
        except Exception as exc:  # noqa: BLE001
            logger.opt(exception=True).error("安装任务异常: {}", task_id)
            await queue.put(
                {
                    "type": "error",
                    "ok": False,
                    "message": f"安装失败: {exc}",
                }
            )
        finally:
            asyncio.get_event_loop().call_later(
                _TASK_CLEANUP_DELAY, self._queues.pop, task_id, None
            )

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
            await queue.put(
                {
                    "type": "error",
                    "ok": False,
                    "message": "uv not found",
                }
            )
            return

        await self._emit(queue, "output", f"> uv add {pkg_requirement}")

        proc = await asyncio.create_subprocess_exec(
            uv,
            "add",
            "--directory",
            ".apeiria",
            pkg_requirement,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )

        async for line in proc.stdout:  # type: ignore[union-attr]
            text = line.decode("utf-8", errors="replace").rstrip()
            await self._emit(queue, "output", text)

        await proc.wait()

        if proc.returncode != 0:
            await queue.put(
                {
                    "type": "error",
                    "ok": False,
                    "message": f"uv add 返回码: {proc.returncode}",
                }
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
