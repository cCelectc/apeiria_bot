"""Bounded live NoneBot context for current-turn platform actions."""

from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Iterator

    from nonebot.adapters import Bot, Event


@dataclass(frozen=True, slots=True)
class LivePlatformContext:
    """Current live platform objects available only during one message turn."""

    bot: "Bot"
    event: "Event"


_live_platform_context: ContextVar[LivePlatformContext | None] = ContextVar(
    "apeiria_live_platform_context",
    default=None,
)


def get_live_platform_context() -> LivePlatformContext | None:
    """Return the active live platform context, if this turn has one."""

    return _live_platform_context.get()


@contextmanager
def live_platform_context(
    *,
    bot: "Bot",
    event: "Event",
) -> "Iterator[LivePlatformContext]":
    """Expose the current live bot/event pair and reset it after the turn."""

    context = LivePlatformContext(bot=bot, event=event)
    token = _live_platform_context.set(context)
    try:
        yield context
    finally:
        _live_platform_context.reset(token)


__all__ = [
    "LivePlatformContext",
    "get_live_platform_context",
    "live_platform_context",
]
