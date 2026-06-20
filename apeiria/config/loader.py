from __future__ import annotations

from pathlib import Path
from typing import Any

import tomlkit
from nonebot.log import logger

_PROJECT_ROOT = Path()


def load_startup_kwargs() -> dict[str, Any]:
    kwargs: dict[str, Any] = {}

    config = _load_toml("apeiria.config.toml")
    if config:
        _apply_core_config(kwargs, config)

    _apply_plugins_config(kwargs)
    _apply_adapters_config(kwargs)
    _apply_drivers_config(kwargs)

    return kwargs


def _apply_core_config(kwargs: dict[str, Any], config: dict[str, Any]) -> None:
    kwargs["host"] = config.get("host", "0.0.0.0")
    kwargs["port"] = config.get("port", 8080)
    superusers = config.get("superusers", [])
    if isinstance(superusers, list):
        kwargs["superusers"] = set(superusers)
    for key in ("command_start", "command_sep", "log_level"):
        if key in config:
            kwargs[key] = config[key]


def _apply_plugins_config(kwargs: dict[str, Any]) -> None:
    plugins_config = _load_toml("apeiria.plugins.toml")
    if not plugins_config:
        return
    plugins_section = plugins_config.get("plugins", {})
    if isinstance(plugins_section, dict):
        kwargs["_plugins"] = list(plugins_section.get("modules", []))
        kwargs["_plugin_dirs"] = list(plugins_section.get("dirs", []))
    elif isinstance(plugins_section, list):
        kwargs["_plugins"] = list(plugins_section)


def _apply_adapters_config(kwargs: dict[str, Any]) -> None:
    adapters_config = _load_toml("apeiria.adapters.toml")
    if not adapters_config:
        return
    adapters_section = adapters_config.get("adapters", {})
    if isinstance(adapters_section, dict):
        kwargs["_adapter_modules"] = list(adapters_section.get("modules", []))
    elif isinstance(adapters_section, list):
        kwargs["_adapter_modules"] = list(adapters_section)


def _apply_drivers_config(kwargs: dict[str, Any]) -> None:
    drivers_config = _load_toml("apeiria.drivers.toml")
    if not drivers_config:
        return None
    drivers_section = drivers_config.get("drivers", {})
    if isinstance(drivers_section, dict):
        builtins = drivers_section.get("builtin", [])
        if isinstance(builtins, list) and builtins:
            kwargs["driver"] = "+".join(builtins)

    return kwargs


def _load_toml(filename: str) -> dict[str, Any] | None:
    path = _PROJECT_ROOT / filename
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8") as f:
            return dict(tomlkit.load(f))
    except Exception:  # noqa: BLE001
        logger.warning("Failed to load {}", filename, exc_info=True)
        return None
