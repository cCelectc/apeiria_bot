"""Private helpers for ProjectConfigService TOML manipulation."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import tomlkit
import tomlkit.items
from nonebot.log import logger

from apeiria.utils.files import load_toml_dict


def _plugin_name_candidates(plugin_name: str) -> tuple[str, ...]:
    stripped = plugin_name.strip()
    if not stripped:
        return ()

    candidates = [stripped]
    normalized = stripped.replace("-", "_")
    if normalized not in candidates:
        candidates.append(normalized)
    dashed = stripped.replace("_", "-")
    if dashed not in candidates:
        candidates.append(dashed)
    return tuple(candidates)


def _read_plugin_table(
    data: dict[str, Any],
    plugin_name: str,
) -> dict[str, Any]:
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        return {}

    for candidate in _plugin_name_candidates(plugin_name):
        plugin_config = plugins.get(candidate)
        if isinstance(plugin_config, dict):
            return dict(plugin_config)
    return {}


def _normalize_config(data: dict[str, Any]) -> dict[str, Any]:
    nonebot_config = data.get("nonebot")
    if isinstance(nonebot_config, dict):
        return dict(nonebot_config)
    return data


def _read_nonebot_overrides(
    config_path: Path,
    project_defaults: dict[str, Any],
) -> dict[str, Any]:
    data = _load_config(config_path)
    config = dict(project_defaults)
    config.update(_normalize_config(data))
    return config


def _read_effective_nonebot_config(
    config_path: Path,
    project_defaults: dict[str, Any],
) -> dict[str, Any]:
    from nonebot.compat import model_dump
    from nonebot.config import Config, Env

    env = Env()
    env_file = f".env.{env.environment}"
    config = Config(
        **_read_nonebot_overrides(config_path, project_defaults),
        _env_file=(".env", env_file),
    )
    return dict(model_dump(config))


def _read_env_nonebot_config() -> dict[str, Any]:
    from nonebot.compat import model_dump
    from nonebot.config import Config, Env

    env = Env()
    env_file = f".env.{env.environment}"
    config = Config(_env_file=(".env", env_file))
    return dict(model_dump(config))


def _parse_int(value: object, default: int) -> int:
    if isinstance(value, bool):
        return default
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return default
        try:
            return int(normalized)
        except ValueError:
            return default
    return default


def _load_config(config_path: Path) -> dict[str, Any]:
    return load_toml_dict(
        config_path,
        logger=logger,
        missing_dependency_message=(
            f"Skip loading {config_path.name}: tomllib/tomli is unavailable"
        ),
    )


def _load_toml_document(config_path: Path) -> tomlkit.TOMLDocument:
    if not config_path.is_file():
        return tomlkit.document()
    try:
        return tomlkit.parse(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        msg = f"cannot read {config_path.name}: {exc}"
        raise InvalidProjectConfigError(msg) from exc
    except Exception as exc:
        msg = f"{config_path.name} contains invalid TOML: {exc}"
        raise InvalidProjectConfigError(msg) from exc


def _dump_toml_value(value: object) -> tomlkit.items.Item:  # type: ignore[attr-defined]
    return tomlkit.item(_normalize_toml_value(value))  # type: ignore[call-overload]


def _normalize_toml_value(value: object) -> object:
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, set):
        return [_normalize_toml_value(item) for item in sorted(value)]
    if isinstance(value, list | tuple):
        return [_normalize_toml_value(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _normalize_toml_value(item) for key, item in value.items()}
    return value


def _build_table_from_mapping(
    values: dict[str, Any],
) -> tomlkit.items.Table:  # type: ignore[attr-defined]
    table = tomlkit.table()
    for key, value in values.items():
        table[str(key)] = _dump_toml_value(value)
    return table


def _parse_toml_text(text: str) -> tomlkit.TOMLDocument:
    normalized = text.strip()
    if not normalized:
        return tomlkit.document()
    if not normalized.endswith("\n"):
        normalized = f"{normalized}\n"
    return tomlkit.parse(normalized)


def _validate_plugin_section_toml(
    parsed: dict[str, object],
    section_name: str,
) -> tomlkit.items.Table | None:  # type: ignore[attr-defined]
    if any(key != "plugins" for key in parsed):
        msg = "raw editor only accepts the [plugins.<section>] section"
        raise ValueError(msg)

    plugins_section = parsed.get("plugins")
    if plugins_section is None:
        return None
    if not isinstance(plugins_section, tomlkit.items.Table):  # type: ignore[attr-defined]
        msg = "raw editor expects a [plugins.<section>] table"
        raise TypeError(msg)

    if any(key != section_name for key in plugins_section):
        msg = f"raw editor only accepts the [plugins.{section_name}] section"
        raise ValueError(msg)
    section = plugins_section.get(section_name)
    if section is not None and not isinstance(section, tomlkit.items.Table):  # type: ignore[attr-defined]
        msg = f"raw editor expects [plugins.{section_name}] to be a table"
        raise ValueError(msg)
    return section


def _set_plugin_module_mapping(
    document: tomlkit.TOMLDocument,
    updates: dict[str, str | None],
) -> None:
    plugin_modules = document.get("plugin_modules")
    if not isinstance(plugin_modules, tomlkit.items.Table):  # type: ignore[attr-defined]
        plugin_modules = tomlkit.table()
        document["plugin_modules"] = plugin_modules

    for section, module_name in updates.items():
        normalized_section = next(
            iter(_plugin_name_candidates(section)),
            section,
        )
        if not normalized_section:
            continue
        normalized_module = module_name.strip() if isinstance(module_name, str) else ""
        if normalized_module:
            plugin_modules[normalized_section] = normalized_module
        elif normalized_section in plugin_modules:
            del plugin_modules[normalized_section]

    if len(plugin_modules) == 0 and "plugin_modules" in document:
        del document["plugin_modules"]


class InvalidProjectConfigError(ValueError):
    """Raised when a project TOML file cannot be parsed safely for mutation."""
