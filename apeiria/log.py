"""Logging service — file rotation + WebSocket log buffer."""

from __future__ import annotations

import asyncio
import contextlib
import heapq
import re
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from nonebot.log import logger

from apeiria.i18n import t

if TYPE_CHECKING:
    from collections.abc import Mapping

    from loguru import Record


@dataclass(frozen=True)
class LogSubscription:
    """Per-connection queue used for real-time log delivery."""

    queue: asyncio.Queue["StructuredLogEntry"]
    loop: asyncio.AbstractEventLoop


@dataclass(frozen=True)
class StructuredLogEntry:
    """Structured log item used by the Web UI log stream."""

    timestamp: str
    level: str
    source: str
    message: str
    raw: str
    extra: dict[str, object]

    def to_payload(self) -> dict[str, object]:
        return {
            "timestamp": self.timestamp,
            "level": self.level,
            "source": self.source,
            "message": self.message,
            "raw": self.raw,
            "extra": self.extra,
        }


@dataclass(frozen=True)
class HistoryLogFilters:
    """History log query filters."""

    level: str = ""
    source: str = ""
    search: str = ""
    start: str = ""
    end: str = ""
    include_access: bool = True


class LogBuffer:
    """Circular buffer holding recent log entries for WebSocket push."""

    def __init__(self, maxlen: int = 500) -> None:
        self._buffer: deque[StructuredLogEntry] = deque(maxlen=maxlen)
        self._subscribers: list[LogSubscription] = []

    def append(self, entry: StructuredLogEntry) -> None:
        self._buffer.append(entry)
        for subscriber in tuple(self._subscribers):
            subscriber.loop.call_soon_threadsafe(
                self._push_to_queue,
                subscriber.queue,
                entry,
            )

    def get_recent(self, n: int = 100) -> list[StructuredLogEntry]:
        items = list(self._buffer)
        return items[-n:]

    def subscribe(self, max_queue_size: int = 200) -> LogSubscription:
        subscription = LogSubscription(
            queue=asyncio.Queue(maxsize=max_queue_size),
            loop=asyncio.get_running_loop(),
        )
        self._subscribers.append(subscription)
        return subscription

    def unsubscribe(self, subscription: LogSubscription) -> None:
        with contextlib.suppress(ValueError):
            self._subscribers.remove(subscription)

    @staticmethod
    def _push_to_queue(
        queue: asyncio.Queue[StructuredLogEntry],
        entry: StructuredLogEntry,
    ) -> None:
        if queue.full():
            with contextlib.suppress(asyncio.QueueEmpty):
                queue.get_nowait()
        with contextlib.suppress(asyncio.QueueFull):
            queue.put_nowait(entry)


log_buffer = LogBuffer()
LOG_LINE_PATTERN = re.compile(
    r"^(?P<timestamp>\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s"
    r"\[(?P<level>[^\]]+)\]\s"
    r"\[(?P<source>[^\]]+)\]\s\|\s"
    r"(?P<message>.*)$"
)
ACCESS_LOG_PATTERN = re.compile(
    r"^(?P<timestamp>\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})\s(?P<message>.*)$"
)
_DATETIME_SECONDS_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
_DATETIME_MINUTES_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}$")
_DATE_ONLY_PATTERN = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _log_format(_record: Record) -> str:
    return "{time:MM-DD HH:mm:ss} [{level}] [{name}] | {message}\n{exception}"


def _log_dir() -> Path:
    return Path("data/logs")


def _serialize_extra(extra: "Mapping[str, Any]") -> dict[str, object]:
    serialized: dict[str, object] = {}
    for key, value in extra.items():
        if key.startswith("_"):
            continue
        if isinstance(value, str | int | float | bool) or value is None:
            serialized[key] = value
            continue
        serialized[key] = str(value)
    return serialized


def _build_log_entry(message: Any) -> StructuredLogEntry:
    record = message.record
    return StructuredLogEntry(
        timestamp=record["time"].strftime("%Y-%m-%d %H:%M:%S"),
        level=record["level"].name,
        source=str(record["name"]),
        message=str(record["message"]),
        raw=str(message).rstrip(),
        extra=_serialize_extra(record["extra"]),
    )


def setup_logging(
    log_dir: Path | None = None,
    rotation: str = "00:00",
    retention: str = "30 days",
) -> None:
    if log_dir is None:
        log_dir = _log_dir()
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_dir / "{time:YYYY-MM-DD}.log",
        rotation=rotation,
        retention=retention,
        encoding="utf-8",
        format=_log_format,
        level="DEBUG",
        enqueue=True,
    )

    def _buffer_sink(message: Any) -> None:
        log_buffer.append(_build_log_entry(message))

    logger.add(
        _buffer_sink,
        format=_log_format,
        level="INFO",
    )

    logger.info("{}", t("logging.initialized", log_dir=log_dir))


def load_history_logs(
    *,
    before: int = 0,
    limit: int = 50,
    filters: HistoryLogFilters | None = None,
) -> tuple[list[StructuredLogEntry], bool, int]:
    if limit <= 0:
        return [], False, 0

    log_dir = _log_dir()
    if not log_dir.exists():
        return [], False, 0

    active_filters = filters or HistoryLogFilters()
    items = _collect_history_entries(
        sorted(log_dir.glob("*.log"), reverse=True),
        filters=active_filters,
    )
    page = items[before : before + limit]
    return page, before + len(page) < len(items), len(items)


def load_history_log_sources() -> list[str]:
    log_dir = _log_dir()
    if not log_dir.exists():
        return []

    sources = {
        entry.source
        for entry in _collect_history_entries(
            sorted(log_dir.glob("*.log"), reverse=True),
            filters=HistoryLogFilters(),
        )
        if entry.source
    }
    return sorted(sources)


def _collect_history_entries(
    log_files: list[Path],
    *,
    filters: HistoryLogFilters,
) -> list[StructuredLogEntry]:
    if not log_files:
        return []

    entries: list[StructuredLogEntry] = []
    for log_file in log_files:
        entries.extend(_read_log_file_entries(log_file, filters=filters))

    entries.sort(key=lambda entry: entry.timestamp, reverse=True)
    return entries


def _read_log_file_entries(
    log_file: Path,
    *,
    filters: HistoryLogFilters,
) -> list[StructuredLogEntry]:
    heap: list[tuple[float, int, StructuredLogEntry]] = []
    sequence = 0
    with log_file.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            entry = _parse_log_line(line.rstrip("\n"))
            if entry is None or not _match_history_filters(entry, filters):
                continue
            timestamp = _entry_sort_key(entry)
            heapq.heappush(heap, (-timestamp, sequence, entry))
            sequence += 1
    return [item[2] for item in heap]


def _parse_log_line(line: str) -> StructuredLogEntry | None:
    if not line.strip():
        return None

    match = LOG_LINE_PATTERN.match(line)
    if match:
        groups = match.groupdict()
        return StructuredLogEntry(
            timestamp=groups["timestamp"],
            level=groups["level"].strip(),
            source=groups["source"].strip(),
            message=groups["message"].strip(),
            raw=line,
            extra={},
        )

    access_match = ACCESS_LOG_PATTERN.match(line)
    if access_match:
        groups = access_match.groupdict()
        return StructuredLogEntry(
            timestamp=groups["timestamp"],
            level="ACCESS",
            source="uvicorn.access",
            message=groups["message"].strip(),
            raw=line,
            extra={},
        )
    return None


def _entry_sort_key(entry: StructuredLogEntry) -> float:
    try:
        return (
            datetime.strptime(entry.timestamp, "%Y-%m-%d %H:%M:%S")
            .replace(tzinfo=timezone.utc)
            .timestamp()
        )
    except ValueError:
        return 0.0


def _match_history_filters(
    entry: StructuredLogEntry,
    filters: HistoryLogFilters,
) -> bool:
    entry_ts = _entry_sort_key(entry)
    if filters.level and entry.level.lower() != filters.level.lower():
        return False
    if filters.source and filters.source.lower() not in entry.source.lower():
        return False

    haystack = f"{entry.source}\n{entry.message}\n{entry.raw}".lower()
    if filters.search and filters.search.lower() not in haystack:
        return False

    if not filters.include_access and entry.level.upper() == "ACCESS":
        return False

    start_ts = _parse_filter_datetime(filters.start)
    if start_ts is not None and entry_ts < start_ts:
        return False

    end_ts = _parse_filter_datetime(filters.end)
    return end_ts is None or entry_ts <= end_ts


def _parse_filter_datetime(value: str) -> float | None:
    normalized = value.strip()
    if not normalized:
        return None

    if _DATETIME_SECONDS_PATTERN.fullmatch(normalized):
        fmt = "%Y-%m-%d %H:%M:%S"
    elif _DATETIME_MINUTES_PATTERN.fullmatch(normalized):
        fmt = "%Y-%m-%d %H:%M"
    elif _DATE_ONLY_PATTERN.fullmatch(normalized):
        fmt = "%Y-%m-%d"
    else:
        return None
    return datetime.strptime(normalized, fmt).replace(tzinfo=timezone.utc).timestamp()
    return None
