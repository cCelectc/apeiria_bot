"""NoneBot2 Rule factories for permission checks."""

from contextlib import suppress

from nonebot import get_driver
from nonebot.adapters import Bot, Event
from nonebot.log import logger
from nonebot.rule import Rule

from apeiria.access.level import extract_group_id
from apeiria.access.service import access_service
from apeiria.i18n import t


def owner_check() -> Rule:
    """Rule that requires the current user to be a configured superuser."""

    async def _check(bot: Bot, event: Event) -> bool:
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


def admin_check(level: int = 5) -> Rule:
    """Rule that requires minimum permission level."""

    async def _check(bot: Bot, event: Event) -> bool:
        context = await access_service.build_context(bot, event)
        if context is None:
            return False

        if context.is_superuser:
            return True

        if context.group_id is None:
            return False

        if context.adapter_role_level >= level:
            return True

        user_level = await access_service.get_user_level(
            context.user_id,
            context.group_id,
        )
        return user_level >= level

    return Rule(_check)


def ensure_group() -> Rule:
    """Rule that only passes in group context."""

    async def _check(event: Event) -> bool:
        try:
            user_id = event.get_user_id()
        except Exception:  # noqa: BLE001
            return False
        return extract_group_id(event.get_session_id(), user_id) is not None

    return Rule(_check)


def ensure_private() -> Rule:
    """Rule that only passes in private (DM) context."""

    async def _check(event: Event) -> bool:
        try:
            user_id = event.get_user_id()
        except Exception:  # noqa: BLE001
            return False
        return event.get_session_id() == user_id

    return Rule(_check)
