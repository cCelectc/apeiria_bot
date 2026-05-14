"""Factory for the default AI runtime application entry."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event

    from apeiria.app.ai.runtime.contracts import (
        FutureTaskRuntimeResult,
        RuntimeTraceContext,
    )


class LiveRuntimeEntry(Protocol):
    """Runtime entry shape lazily resolved by the factory."""

    async def handle_message(
        self,
        bot: "Bot",
        event: "Event",
        *,
        trace: "RuntimeTraceContext | None" = None,
    ) -> str | None: ...

    async def handle_future_task(
        self,
        task_id: str,
        *,
        trace: "RuntimeTraceContext | None" = None,
    ) -> "FutureTaskRuntimeResult | None": ...


@dataclass(slots=True)
class LazyAIRuntimeEntry:
    """Defer heavy runtime assembly until a live turn enters the application."""

    _entry: LiveRuntimeEntry | None = field(default=None, init=False, repr=False)

    async def handle_message(
        self,
        bot: "Bot",
        event: "Event",
        *,
        trace: "RuntimeTraceContext | None" = None,
    ) -> str | None:
        """Handle one platform message through the default runtime entry."""

        return await self._resolve().handle_message(bot, event, trace=trace)

    async def handle_future_task(
        self,
        task_id: str,
        *,
        trace: "RuntimeTraceContext | None" = None,
    ) -> "FutureTaskRuntimeResult | None":
        """Handle one due future task through the default runtime entry."""

        return await self._resolve().handle_future_task(task_id, trace=trace)

    def _resolve(self) -> LiveRuntimeEntry:
        if self._entry is None:
            from apeiria.app.ai.runtime.live import DefaultAILiveRuntimeEntry

            self._entry = DefaultAILiveRuntimeEntry()
        return self._entry


def create_default_ai_runtime_entry() -> LazyAIRuntimeEntry:
    """Return the lazily assembled default runtime entry."""

    return LazyAIRuntimeEntry()


__all__ = ["LazyAIRuntimeEntry", "LiveRuntimeEntry", "create_default_ai_runtime_entry"]
