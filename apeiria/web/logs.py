from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import TYPE_CHECKING, Any

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from nonebot.log import logger

from apeiria.web.auth import verify_token

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

    from loguru import Message

    from apeiria.config.models import LogConfig

_DEFAULT_BUFFER = 500
_MAX_SCAN_LINES = 5000
_HEARTBEAT = 15.0

_MUTED_ACCESS_PREFIXES = ("/assets/",)
_MUTED_ACCESS_PATHS = frozenset({"/favicon.svg", "/icons.svg", "/api/status"})
_ACCESS_ARG_COUNT = 5
_ACCESS_PATH_INDEX = 2
_ACCESS_STATUS_INDEX = 4
_HTTP_ERROR = 400
_ACCESS_LOG_MAX_BYTES = 10 * 1024 * 1024
_ACCESS_LOG_BACKUPS = 5


class _StaticAccessFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if not isinstance(args, tuple) or len(args) < _ACCESS_ARG_COUNT:
            return True
        path = args[_ACCESS_PATH_INDEX]
        status = args[_ACCESS_STATUS_INDEX]
        is_muted = isinstance(path, str) and (
            path.startswith(_MUTED_ACCESS_PREFIXES) or path in _MUTED_ACCESS_PATHS
        )
        is_success = isinstance(status, int) and status < _HTTP_ERROR
        return not (is_muted and is_success)


def route_access_logs(cfg: LogConfig) -> None:
    """Route uvicorn access logs to a dedicated file, off the console and SSE."""
    from nonebot import get_driver

    path = Path(cfg.file).parent / "access.log"

    def _apply() -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        access = logging.getLogger("uvicorn.access")
        for handler in list(access.handlers):
            access.removeHandler(handler)
        access.propagate = False
        file_handler = RotatingFileHandler(
            str(path),
            maxBytes=_ACCESS_LOG_MAX_BYTES,
            backupCount=_ACCESS_LOG_BACKUPS,
            encoding="utf-8",
        )
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(message)s"),
        )
        file_handler.addFilter(_StaticAccessFilter())
        access.addHandler(file_handler)

    get_driver().on_startup(_apply)


class LogHub:
    def __init__(self) -> None:
        self._installed = False
        self._cfg: LogConfig | None = None
        self._subscribers: set[asyncio.Queue[str]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def install_sinks(self, cfg: LogConfig) -> None:
        if self._installed:
            return
        self._cfg = cfg
        Path(cfg.file).parent.mkdir(parents=True, exist_ok=True)
        logger.add(
            cfg.file,
            level=cfg.level,
            rotation=cfg.rotation,
            retention=cfg.retention,
            encoding="utf-8",
            enqueue=True,
            serialize=True,
        )
        logger.add(self._broadcast_sink, level=cfg.level, enqueue=True)
        self._installed = True

    def _broadcast_sink(self, message: Message) -> None:
        if self._loop is None or not self._subscribers:
            return
        record = message.record
        payload = json.dumps(
            {
                "time": record["time"].isoformat(),
                "level": record["level"].name,
                "name": record["name"],
                "message": record["message"],
            },
            ensure_ascii=False,
        )
        with contextlib.suppress(RuntimeError):
            self._loop.call_soon_threadsafe(self._fanout, payload)

    def _fanout(self, payload: str) -> None:
        for queue in list(self._subscribers):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                try:
                    queue.get_nowait()
                    queue.put_nowait(payload)
                except (asyncio.QueueEmpty, asyncio.QueueFull):
                    continue

    def subscribe(self) -> asyncio.Queue[str]:
        buffer = self._cfg.stream_buffer if self._cfg else _DEFAULT_BUFFER
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=buffer)
        self._loop = asyncio.get_running_loop()
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self._subscribers.discard(queue)

    async def event_stream(self, request: Request) -> AsyncIterator[str]:
        queue = self.subscribe()
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    payload = await asyncio.wait_for(queue.get(), timeout=_HEARTBEAT)
                except TimeoutError:
                    yield ": ping\n\n"
                    continue
                yield f"data: {payload}\n\n"
        finally:
            self.unsubscribe(queue)

    def read_history(
        self,
        level: str = "",
        query: str = "",
        page: int = 1,
        size: int = 100,
    ) -> dict[str, Any]:
        path = Path(self._cfg.file) if self._cfg else None
        if path is None or not path.exists():
            return {"items": [], "total": 0, "page": page, "size": size}

        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        records: list[dict[str, str]] = []
        for line in lines[-_MAX_SCAN_LINES:]:
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            record = obj.get("record", {})
            records.append(
                {
                    "time": record.get("time", {}).get("repr", ""),
                    "level": record.get("level", {}).get("name", ""),
                    "name": record.get("name", ""),
                    "message": record.get("message", ""),
                }
            )

        if level:
            records = [r for r in records if r["level"] == level]
        if query:
            needle = query.lower()
            records = [r for r in records if needle in r["message"].lower()]

        records.reverse()
        total = len(records)
        start = (page - 1) * size
        return {
            "items": records[start : start + size],
            "total": total,
            "page": page,
            "size": size,
        }


_hub = LogHub()


def get_log_hub() -> LogHub:
    return _hub


logs_router = APIRouter(prefix="/api/logs", tags=["logs"])


@logs_router.get("/stream", dependencies=[Depends(verify_token)])
async def stream(request: Request) -> StreamingResponse:
    return StreamingResponse(
        get_log_hub().event_stream(request),
        media_type="text/event-stream",
    )


@logs_router.get("/history", dependencies=[Depends(verify_token)])
async def history(
    level: str = "",
    q: str = "",
    page: int = 1,
    size: int = 100,
) -> JSONResponse:
    result = await asyncio.to_thread(get_log_hub().read_history, level, q, page, size)
    return JSONResponse(content=result)
