"""Error hook — post-run exception handling with friendly user feedback."""

from nonebot.adapters import Bot, Event
from nonebot.log import logger
from nonebot.matcher import Matcher

from apeiria.config.bot_config import get_error_message


async def error_hook(
    matcher: Matcher,
    exception: Exception | None,
    bot: Bot,
    event: Event,
) -> None:
    """Catch unhandled exceptions from matcher execution."""
    if exception is None:
        return

    plugin_name = matcher.plugin.name if matcher.plugin else "unknown"
    try:
        user_id = event.get_user_id()
    except Exception:  # noqa: BLE001
        user_id = "unknown"

    logger.opt(exception=exception).error(
        "Unhandled exception in plugin '{}' (user: {})",
        plugin_name,
        user_id,
    )

    try:
        await bot.send(event, get_error_message())
    except Exception:  # noqa: BLE001
        logger.debug("Failed to send error message to user")
