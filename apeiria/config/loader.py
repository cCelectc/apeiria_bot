from __future__ import annotations

import json
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

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


def _flatten_nested(
    prefix: str,
    obj: dict,
    parent: str = "",
    skipped: list[str] | None = None,
    skip_existing: bool = False,  # noqa: FBT001, FBT002
) -> None:
    for key, val in obj.items():
        full_key = f"{parent}__{key}" if parent else key
        env_key = f"{prefix}__{full_key}".upper()
        if isinstance(val, dict):
            _flatten_nested(prefix, val, full_key, skipped, skip_existing)
        elif skip_existing and env_key in os.environ:
            if skipped is not None:
                skipped.append(env_key)
        else:
            os.environ[env_key] = to_env_value(val)


def _try_resolve_plugin_contract(name: str):
    try:
        from apeiria.plugin.metadata.resolver import resolve_config_namespace_contract

        return resolve_config_namespace_contract(name)
    except (ImportError, ValueError, TypeError):
        return None


def _try_resolve_adapter_contract(name: str):
    try:
        from apeiria.plugin.adapter_resolver import resolve_adapter_config

        return resolve_adapter_config(name)
    except (ImportError, ValueError, TypeError):
        return None


def _inject_section_config(
    entries: dict[str, dict],
    resolve_fn: Callable[[str], Any],
    set_driver_attr: object | None = None,
    skipped: list[str] | None = None,
    skip_existing: bool = False,  # noqa: FBT001, FBT002
) -> None:
    for name, cfg in entries.items():
        if not cfg:
            continue
        contract = resolve_fn(name)
        if contract and contract.is_scoped and contract.namespace:
            inner_cfg = cfg.get(contract.namespace, cfg)
            if isinstance(inner_cfg, dict):
                _flatten_nested(
                    contract.namespace.upper(),
                    inner_cfg,
                    skipped=skipped,
                    skip_existing=skip_existing,
                )
                if set_driver_attr is not None:
                    setattr(set_driver_attr, contract.namespace, inner_cfg)
        else:
            for key, val in cfg.items():
                env_key = key.upper()
                if skip_existing and env_key in os.environ:
                    if skipped is not None:
                        skipped.append(env_key)
                else:
                    os.environ[env_key] = to_env_value(val)
                if set_driver_attr is not None:
                    setattr(set_driver_attr, key, val)


def expand_config(app: AppConfig) -> None:
    skipped_keys: list[str] = []

    nonebot_fields = {
        name: getattr(app.nonebot, name) for name in app._nonebot_field_names
    }
    for key, value in nonebot_fields.items():
        env_key = key.upper()
        if env_key in os.environ:
            skipped_keys.append(env_key)
        else:
            os.environ[env_key] = to_env_value(value)

    _inject_section_config(
        app.plugins,
        _try_resolve_plugin_contract,
        skipped=skipped_keys,
        skip_existing=True,
    )
    _inject_section_config(
        app.adapters,
        _try_resolve_adapter_contract,
        skipped=skipped_keys,
        skip_existing=True,
    )

    if skipped_keys:
        logger.warning(
            "Skipped {} YAML config key(s) — already set by .env / process env: {}",
            len(skipped_keys),
            ", ".join(sorted(skipped_keys)),
        )

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

    _inject_section_config(
        app.plugins, _try_resolve_plugin_contract, set_driver_attr=config
    )
    _inject_section_config(
        app.adapters, _try_resolve_adapter_contract, set_driver_attr=config
    )

    logger.success("Plugin config hot-reloaded")
