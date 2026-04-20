"""Time formatting helpers."""

from __future__ import annotations

from apeiria.i18n import t


def format_duration(seconds: int) -> str:
    """Format seconds into human-readable duration string."""
    if seconds <= 0:
        return t("duration.permanent")
    parts: list[str] = []
    days, seconds = divmod(seconds, 86400)
    hours, seconds = divmod(seconds, 3600)
    minutes, seconds = divmod(seconds, 60)
    if days:
        parts.append(f"{days}{t('duration.day')}")
    if hours:
        parts.append(f"{hours}{t('duration.hour')}")
    if minutes:
        parts.append(f"{minutes}{t('duration.minute')}")
    if seconds:
        parts.append(f"{seconds}{t('duration.second')}")
    return "".join(parts) or t("duration.zero")
