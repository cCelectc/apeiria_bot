from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from nonebot.log import logger

_TASK_TIMEOUT = 600
_HEARTBEAT_INTERVAL = 120


class ACPClient:
    def __init__(
        self,
        name: str,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        self.name = name
        self._command = command
        self._args = args or []
        self._env = env
        self._process: asyncio.subprocess.Process | None = None

    async def connect(self) -> None:
        import os

        merged_env = {**os.environ, **(self._env or {})}
        self._process = await asyncio.create_subprocess_exec(
            self._command,
            *self._args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
        )

    async def run_task(
        self,
        task_description: str,
        *,
        workspace: str | None = None,
        on_heartbeat: Any | None = None,
    ) -> str:
        if not self._process or not self._process.stdin or not self._process.stdout:
            msg = "ACP agent not connected"
            raise RuntimeError(msg)

        task_id = str(uuid.uuid4())
        await self._send_request(task_id, task_description, workspace)

        result_text = ""
        start_time = asyncio.get_event_loop().time()
        last_heartbeat = start_time

        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > _TASK_TIMEOUT:
                self._process.terminate()
                msg = f"ACP task timed out after {_TASK_TIMEOUT}s"
                raise TimeoutError(msg)

            now = asyncio.get_event_loop().time()
            if now - last_heartbeat > _HEARTBEAT_INTERVAL and on_heartbeat:
                await on_heartbeat(task_id, elapsed)
                last_heartbeat = now

            try:
                raw = await asyncio.wait_for(
                    self._process.stdout.readline(),
                    timeout=min(30, _TASK_TIMEOUT - elapsed),
                )
            except asyncio.TimeoutError:
                continue

            if not raw:
                break

            done, text = _parse_response(raw, task_id)
            if text is not None:
                result_text = text
            if done:
                break

        return result_text

    async def _send_request(
        self,
        task_id: str,
        task_description: str,
        workspace: str | None,
    ) -> None:
        assert self._process and self._process.stdin
        request = {
            "jsonrpc": "2.0",
            "id": task_id,
            "method": "session/start",
            "params": {
                "task": task_description,
                "workspace": workspace,
            },
        }
        line = json.dumps(request) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

    async def cancel(self) -> None:
        if not self._process or not self._process.stdin:
            return
        cancel_msg = {
            "jsonrpc": "2.0",
            "method": "session/cancel",
        }
        line = json.dumps(cancel_msg) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

    async def close(self) -> None:
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()


def _parse_response(raw: bytes, task_id: str) -> tuple[bool, str | None]:
    try:
        data = json.loads(raw.decode().strip())
    except (json.JSONDecodeError, UnicodeDecodeError):
        return False, None

    if data.get("id") == task_id:
        if "error" in data:
            msg = f"ACP error: {data['error']}"
            raise RuntimeError(msg)
        result = data.get("result", {})
        text = result.get(
            "summary",
            result.get("text", json.dumps(result)),
        )
        return True, text

    if "method" in data and not data.get("id"):
        logger.debug("ACP notification: %s", data.get("method"))

    return False, None
