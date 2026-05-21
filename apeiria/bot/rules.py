"""NoneBot2 Rule factories for bot-surface permission checks."""

from __future__ import annotations

from contextlib import suppress
from typing import TYPE_CHECKING

from nonebot import get_driver
from nonebot.log import logger
from nonebot.rule import Rule

from apeiria.access.level import extract_group_id
from apeiria.i18n import t

if TYPE_CHECKING:
    from nonebot.adapters import Bot, Event


def owner_check() -> Rule:
    """Rule that requires the current user to be a configured superuser."""

    async def _check(bot: "Bot", event: "Event") -> bool:
        try:
            user_id = event.get_user_id()
        except Exception:  # noqa: BLE001
            return False

        superusers = getattr(get_driver().config, "superusers", set())
        if str(user_id) in {str(item) for item in superusers}:
            return True

        with suppress(Exception):
            await bot.send(event, t("admin.owner_only"))
        logger.debug("Owner check failed for user {}", user_id)
        return False

    return Rule(_check)


def ensure_group() -> Rule:
    """Rule that only passes in group context."""

    async def _check(event: "Event") -> bool:
        try:
            user_id = event.get_user_id()
        except Exception:  # noqa: BLE001
            return False
        return extract_group_id(event.get_session_id(), user_id) is not None

    return Rule(_check)


def ensure_private() -> Rule:
    """Rule that only passes in private (DM) context."""

    async def _check(event: "Event") -> bool:
        try:
            user_id = event.get_user_id()
        except Exception:  # noqa: BLE001
            return False
        return event.get_session_id() == user_id

    return Rule(_check)


__all__ = ["ensure_group", "ensure_private", "owner_check"]
