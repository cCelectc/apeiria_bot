"""Error hook — post-run exception handling with friendly user feedback."""

from nonebot.adapters import Bot, Event
from nonebot.log import logger
from nonebot.matcher import Matcher

from apeiria.app.message_delivery import delivery_gateway
from apeiria.app.runtime.diagnostics import runtime_diagnostic_recorder
from apeiria.app.runtime.observer import current_request_id
from apeiria.infra.config.bot_config import get_error_message


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
    plugin_module = matcher.plugin.module_name if matcher.plugin else None
    try:
        user_id = event.get_user_id()
    except Exception:  # noqa: BLE001
        user_id = "unknown"

    logger.opt(exception=exception).error(
        "Unhandled exception in plugin '{}' (user: {})",
        plugin_name,
        user_id,
    )
    runtime_diagnostic_recorder.record(
        "handler.error",
        source="bot.hooks.error",
        message=str(exception),
        request_id=current_request_id(),
        plugin_module=plugin_module,
        data={
            "exception_type": type(exception).__name__,
            "user_id": str(user_id),
        },
    )

    # Send friendly error message
    try:
        await delivery_gateway.reply(
            bot=bot,
            event=event,
            text=get_error_message(),
            origin="bot.hooks.error",
        )
    except Exception:  # noqa: BLE001
        logger.debug("Failed to send error message to user")
