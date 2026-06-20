from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from nonebot.log import logger


@dataclass
class AgentEvent:
    type: str
    data: dict[str, Any] = field(default_factory=dict)


class EventBus:
    def __init__(self) -> None:
        self._subscribers: dict[str, list[Any]] = {}

    def subscribe(self, event_type: str, handler: Any) -> None:
        self._subscribers.setdefault(event_type, []).append(handler)

    async def emit(self, event: AgentEvent) -> None:
        handlers = self._subscribers.get(event.type, [])
        for handler in handlers:
            try:
                result = handler(event)
                if asyncio.iscoroutine(result):
                    await result
            except Exception:  # noqa: BLE001, PERF203
                logger.warning(
                    "Event handler error for %s",
                    event.type,
                    exc_info=True,
                )
