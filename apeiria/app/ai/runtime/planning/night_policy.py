"""Deterministic helpers for quiet-hour AI runtime behavior."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from datetime import datetime

    from apeiria.app.ai.runtime.session.runtime import SessionRuntimePolicy


def minute_of_day(current_time: datetime) -> int:
    """Return the local minute-of-day for one runtime timestamp."""

    local_time = current_time.astimezone()
    return local_time.hour * 60 + local_time.minute


def is_within_quiet_hours(
    *,
    current_time: datetime,
    policy: SessionRuntimePolicy,
) -> bool:
    """Return whether the current local time falls inside quiet hours."""

    if not policy.quiet_hours_enabled:
        return False
    current_minute = minute_of_day(current_time)
    start_minute = policy.quiet_hours_start_minute
    end_minute = policy.quiet_hours_end_minute
    if start_minute == end_minute:
        return True
    if start_minute < end_minute:
        return start_minute <= current_minute < end_minute
    return current_minute >= start_minute or current_minute < end_minute


__all__ = [
    "is_within_quiet_hours",
    "minute_of_day",
]
