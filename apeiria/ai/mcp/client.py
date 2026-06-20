from __future__ import annotations

import asyncio
import json
from typing import Any

from nonebot.log import logger

_REQUEST_TIMEOUT = 30


class MCPClient:
    def __init__(self, name: str, transport: str) -> None:
        self.name = name
        self.transport = transport
        self._connected = False
        self._request_id = 0
        self._process: asyncio.subprocess.Process | None = None
        self._pending: dict[int, asyncio.Future[Any]] = {}
        self._reader_task: asyncio.Task[None] | None = None

    @property
    def connected(self) -> bool:
        return self._connected

    async def connect_stdio(
        self,
        command: str,
        args: list[str] | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        import os

        merged_env = {**os.environ, **(env or {})}
        self._process = await asyncio.create_subprocess_exec(
            command,
            *(args or []),
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env=merged_env,
        )
        self._connected = True
        self._reader_task = asyncio.create_task(self._read_stdout())

    async def connect_sse(
        self,
        url: str,
        headers: dict[str, str] | None = None,
    ) -> None:
        self._sse_url = url
        self._sse_headers = headers or {}
        self._connected = True

    async def request(
        self,
        method: str,
        params: dict[str, Any] | None = None,
    ) -> Any:
        self._request_id += 1
        req_id = self._request_id
        message = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
            "params": params or {},
        }

        if self.transport == "stdio":
            return await self._send_stdio(req_id, message)
        if self.transport == "sse":
            return await self._send_sse(message)
        msg = f"Unsupported transport: {self.transport}"
        raise ValueError(msg)

    async def _send_stdio(
        self,
        req_id: int,
        message: dict[str, Any],
    ) -> Any:
        if not self._process or not self._process.stdin:
            msg = "MCP stdio not connected"
            raise RuntimeError(msg)
        line = json.dumps(message) + "\n"
        self._process.stdin.write(line.encode())
        await self._process.stdin.drain()

        future: asyncio.Future[Any] = asyncio.get_event_loop().create_future()
        self._pending[req_id] = future
        try:
            return await asyncio.wait_for(future, timeout=_REQUEST_TIMEOUT)
        finally:
            self._pending.pop(req_id, None)

    async def _send_sse(self, message: dict[str, Any]) -> Any:
        import httpx

        async with httpx.AsyncClient(
            timeout=_REQUEST_TIMEOUT,
        ) as client:
            resp = await client.post(
                self._sse_url,
                json=message,
                headers=self._sse_headers,
            )
            resp.raise_for_status()
            result = resp.json()
            if "error" in result:
                msg = f"MCP error: {result['error']}"
                raise RuntimeError(msg)
            return result.get("result")

    async def _read_stdout(self) -> None:
        if not self._process or not self._process.stdout:
            return
        while True:
            try:
                line = await self._process.stdout.readline()
                if not line:
                    break
                data = json.loads(line.decode().strip())
                req_id = data.get("id")
                if req_id and req_id in self._pending:
                    future = self._pending.pop(req_id)
                    if "error" in data:
                        future.set_exception(
                            RuntimeError(f"MCP error: {data['error']}")
                        )
                    else:
                        future.set_result(data.get("result"))
            except Exception:  # noqa: BLE001
                logger.warning(
                    "MCP reader error for %s",
                    self.name,
                    exc_info=True,
                )
                break
        self._connected = False

    async def close(self) -> None:
        self._connected = False
        if self._reader_task:
            self._reader_task.cancel()
        if self._process:
            self._process.terminate()
            try:
                await asyncio.wait_for(self._process.wait(), timeout=5)
            except asyncio.TimeoutError:
                self._process.kill()
