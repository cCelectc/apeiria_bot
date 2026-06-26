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


def _collect_adapter_entries(*paths: str) -> list[dict]:
    import tomllib

    seen_modules: set[str] = set()
    entries: list[dict] = []

    for path in paths:
        toml_path = Path(path)
        if not toml_path.exists():
            continue
        raw = tomllib.loads(toml_path.read_text(encoding="utf-8"))
        cfg = raw.get("tool", {}).get("nonebot", {}).get("adapters", {})
        if not isinstance(cfg, dict):
            continue
        for adapter_entries in cfg.values():
            if not isinstance(adapter_entries, list):
                continue
            for entry in adapter_entries:
                if not isinstance(entry, dict):
                    continue
                module_name = entry.get("module_name", "")
                if not module_name or module_name in seen_modules:
                    continue
                seen_modules.add(module_name)
                entries.append(entry)

    return entries


def load_adapters_from_toml(
    *paths: str,
    states: dict[str, dict] | None = None,
) -> int:
    import importlib

    from nonebot import get_adapters, get_driver

    entries = _collect_adapter_entries(*paths)
    if not entries:
        return 0

    existing = get_adapters()
    driver = get_driver()
    registered = 0

    for entry in entries:
        module_name = entry.get("module_name", "")
        name = entry.get("name", module_name)
        if name in existing:
            continue
        if states is not None:
            state_entry = states.get(name, {})
            if not state_entry.get("enabled", True):
                logger.debug("Skipped disabled adapter: {}", name)
                continue
        try:
            mod = importlib.import_module(module_name)
            adapter_cls = getattr(mod, "Adapter", None)
            if adapter_cls is not None:
                driver.register_adapter(adapter_cls)
                logger.info("Registered adapter: {}", name)
                registered += 1
        except Exception:  # noqa: BLE001
            logger.opt(exception=True).warning(
                "Failed to load adapter: {}", module_name
            )

    return registered


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
