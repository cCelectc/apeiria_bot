"""Lightweight i18n localization system."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from nonebot.log import logger

_translations: dict[str, dict[str, Any]] = {}
_current_locale: str = "zh_CN"
_default_locale: str = "zh_CN"
_locale_initialized: bool = False

_CORE_LOCALES_DIR = Path(__file__).parent / "locales"


def t(key: str, **kwargs: Any) -> str:
    """Get localized string by dot-path key."""
    _ensure_initialized()
    value = _resolve(key, _current_locale)
    if value is None and _current_locale != _default_locale:
        value = _resolve(key, _default_locale)
    if value is None:
        return key
    if "{prefix}" in value and "prefix" not in kwargs:
        kwargs["prefix"] = _get_default_prefix()
    return value.format(**kwargs) if kwargs else value


def set_locale(locale: str) -> None:
    """Switch the active locale."""
    global _current_locale  # noqa: PLW0603
    _current_locale = locale
    logger.debug("Locale set to: {}", locale)


def get_locale() -> str:
    """Get the current active locale."""
    return _current_locale


def load_locales(path: Path) -> None:
    """Load and merge YAML locale files from a directory."""
    import yaml

    if not path.is_dir():
        logger.warning("{}", t("i18n.locales_not_found", path=path))
        return

    for file in path.glob("*.yaml"):
        locale_name = file.stem
        with file.open(encoding="utf-8") as handle:
            data = yaml.safe_load(handle)
        if isinstance(data, dict):
            if locale_name in _translations:
                _deep_merge(_translations[locale_name], data)
            else:
                _translations[locale_name] = data
            logger.debug("Merged locale: {} from {}", locale_name, path.name)


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> None:
    for key, value in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def _ensure_initialized() -> None:
    global _locale_initialized, _current_locale  # noqa: PLW0603
    if _locale_initialized:
        return
    _locale_initialized = True

    load_locales(_CORE_LOCALES_DIR)

    try:
        import nonebot

        config = nonebot.get_driver().config
        locale = getattr(config, "locale", None)
        if locale and isinstance(locale, str) and locale in _translations:
            _current_locale = locale
    except Exception:  # noqa: BLE001
        pass

    logger.info("{}", t("i18n.ready", locale=_current_locale))


def _resolve(key: str, locale: str) -> str | None:
    data: Any = _translations.get(locale)
    if data is None:
        return None
    for part in key.split("."):
        if isinstance(data, dict):
            data = data.get(part)
        else:
            return None
    return str(data) if data is not None else None


def _get_default_prefix() -> str:
    try:
        from apeiria.utils.command_prefix import get_command_prefix

        return get_command_prefix()
    except Exception:  # noqa: BLE001
        return "/"
