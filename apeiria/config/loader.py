from __future__ import annotations

import json
import os
from pathlib import Path

import yaml
from nonebot.log import logger

from apeiria.config.models import AppConfig


def load_config(path: str) -> AppConfig:
    config_path = Path(path)
    if not config_path.exists():
        logger.warning("Config file not found at {}, using defaults", path)
        return AppConfig()

    raw = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return AppConfig(**raw)


def to_env_value(value: object) -> str:
    if isinstance(value, str):
        return value
    if isinstance(value, bool):
        return "1" if value else "0"
    return json.dumps(value)


def expand_config(app: AppConfig) -> None:
    nonebot_fields = {
        name: getattr(app.nonebot, name) for name in app._nonebot_field_names
    }
    for key, value in nonebot_fields.items():
        os.environ[key.upper()] = to_env_value(value)

    for fields in app.plugins.values():
        for key, value in fields.items():
            os.environ[key.upper()] = to_env_value(value)

    for fields in app.adapters.values():
        for key, value in fields.items():
            os.environ[key.upper()] = to_env_value(value)

    logger.success("Config expanded from YAML to environment")


def update_runtime_config(app: AppConfig) -> None:
    from nonebot import get_driver

    driver = get_driver()
    config = driver.config

    for plugin_name, fields in app.plugins.items():
        for key, value in fields.items():
            os.environ[key.upper()] = to_env_value(value)
            setattr(config, key, value)
            logger.debug("Hot-reloaded config: {}.{} = {}", plugin_name, key, value)

    logger.success("Plugin config hot-reloaded")
