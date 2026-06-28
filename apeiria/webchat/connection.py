from __future__ import annotations

import asyncio
import json
from typing import Any, Protocol
from uuid import uuid4

from nonebot.log import logger


class SupportsSendText(Protocol):
    async def send_text(self, data: str) -> None: ...


class ConnectionManager:
    """管理活跃 WebSocket 连接：登记/注销、按 id 路由、广播。

    连接计数的上下线用锁保护，供适配器判定首/末连接以触发 bot 上下线。
    """

    def __init__(self) -> None:
        self._conns: dict[str, SupportsSendText] = {}
        self._lock = asyncio.Lock()

    async def add(self, ws: SupportsSendText) -> tuple[str, bool]:
        """登记连接，返回 (connection_id, 是否为首个连接)。"""
        async with self._lock:
            is_first = len(self._conns) == 0
            conn_id = uuid4().hex
            self._conns[conn_id] = ws
            return conn_id, is_first

    async def remove(self, conn_id: str) -> bool:
        """注销连接，返回注销后是否已无活跃连接（末连接）。"""
        async with self._lock:
            self._conns.pop(conn_id, None)
            return len(self._conns) == 0

    def count(self) -> int:
        return len(self._conns)

    async def send_to(self, conn_id: str, frame: dict[str, Any]) -> None:
        ws = self._conns.get(conn_id)
        if ws is not None:
            await self._safe_send(conn_id, ws, frame)

    async def broadcast(self, frame: dict[str, Any]) -> None:
        for conn_id, ws in list(self._conns.items()):
            await self._safe_send(conn_id, ws, frame)

    async def _safe_send(
        self, conn_id: str, ws: SupportsSendText, frame: dict[str, Any]
    ) -> None:
        try:
            await ws.send_text(json.dumps(frame, ensure_ascii=False))
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).debug(
                "webchat: failed to send to connection {}", conn_id
            )
