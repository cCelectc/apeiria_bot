"""Global bot configuration, extending nonebot2 config."""

from __future__ import annotations

import nonebot
from pydantic import BaseModel

from apeiria.i18n import t


class BotConfig(BaseModel):
    """Extended bot configuration."""

    # Error handling
    error_message: str = "common.error"

    # Rate limiting (default: per-user per-command)
    rate_limit_default: int = 5
    rate_limit_window: int = 60

    # Logging
    log_rotation: str = "00:00"
    log_retention: str = "30 days"


_bot_config: BotConfig | None = None


def _get_bot_config() -> BotConfig:
    global _bot_config  # noqa: PLW0603
    if _bot_config is None:
        _bot_config = nonebot.get_plugin_config(BotConfig)
    return _bot_config


def get_error_message() -> str:
    """Resolve configured error message, supporting either i18n key or raw text."""
    message = _get_bot_config().error_message
    return t(message) if "." in message else message
