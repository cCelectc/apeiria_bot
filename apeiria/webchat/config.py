from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.config.loader import load_config

if TYPE_CHECKING:
    from apeiria.config.models import AppConfig, WebChatConfig

_CONFIG_PATH = "data/config.yaml"
_FALLBACK_USER_ID = "webchat-admin"


def _load_app() -> AppConfig:
    return load_config(_CONFIG_PATH)


def get_webchat_config() -> WebChatConfig:
    return _load_app().apeiria.webchat


def resolve_default_user_id(app: AppConfig | None = None) -> str:
    app = app or _load_app()
    configured = app.apeiria.webchat.default_user_id
    if configured:
        return configured
    if app.nonebot.superusers:
        return app.nonebot.superusers[0]
    return _FALLBACK_USER_ID
