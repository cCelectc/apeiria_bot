"""In-memory ring buffer trace broker with loguru file sink and SSE streaming."""

from __future__ import annotations

import asyncio
import contextlib
import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone

from nonebot.log import logger


def _epoch_ms() -> float:
    return datetime.now(timezone.utc).timestamp() * 1000


@dataclass(frozen=True)
class TraceRecord:
    trace_id: str
    record_type: str
    session_id: str
    data: dict
    created_at: float = field(default_factory=_epoch_ms)


class TraceBroker:
    def __init__(self, *, capacity: int = 1000) -> None:
        self._buffer: deque[TraceRecord] = deque(maxlen=capacity)
        self._subscribers: list[asyncio.Queue[TraceRecord]] = []
        self._enabled: bool = True
        self._file_sink_id: int | None = None

    def enable_file_sink(
        self,
        path: str = "logs/apeiria.trace.jsonl",
        rotation: str = "10 MB",
        retention: int = 3,
    ) -> None:
        self._file_sink_id = logger.add(
            path,
            filter=lambda record: record["extra"].get("is_trace"),  # type: ignore[return-value]
            format="{message}",
            rotation=rotation,
            retention=retention,
            encoding="utf-8",
        )

    def clear(self) -> None:
        self._buffer.clear()

    def set_enabled(self, *, enabled: bool) -> None:
        self._enabled = enabled

    def record(self, trace: TraceRecord) -> None:
        if not self._enabled:
            return
        self._buffer.append(trace)
        for queue in self._subscribers:
            with contextlib.suppress(asyncio.QueueFull):
                queue.put_nowait(trace)
        logger.bind(is_trace=True).opt(colors=False).info(
            json.dumps(_to_dict(trace), ensure_ascii=False)
        )

    def snapshot(
        self, *, record_type: str | None = None, limit: int = 100
    ) -> list[TraceRecord]:
        items = list(self._buffer)
        if record_type is not None:
            items = [i for i in items if i.record_type == record_type]
        return items[-limit:]

    def subscribe(self) -> asyncio.Queue[TraceRecord]:
        queue: asyncio.Queue[TraceRecord] = asyncio.Queue(maxsize=256)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue[TraceRecord]) -> None:
        if queue in self._subscribers:
            self._subscribers.remove(queue)


def _to_dict(record: TraceRecord) -> dict:
    return {
        "trace_id": record.trace_id,
        "type": record.record_type,
        "session_id": record.session_id,
        "ts": record.created_at,
        "data": record.data,
    }


trace_broker = TraceBroker()

__all__ = ["TraceBroker", "TraceRecord", "_to_dict", "trace_broker"]
