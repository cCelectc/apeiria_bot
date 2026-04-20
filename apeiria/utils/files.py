from __future__ import annotations

from importlib import import_module
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    import logging
    from pathlib import Path


def _load_toml_module():
    try:
        return import_module("tomllib")
    except ModuleNotFoundError:
        pass
    try:
        return import_module("tomli")
    except ModuleNotFoundError:
        pass
    return None


def atomic_write_text(target: Path, text: str) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    temp_file = target.with_suffix(f"{target.suffix}.tmp")
    temp_file.write_text(text, encoding="utf-8")
    temp_file.replace(target)


def load_toml_dict(
    config_path: Path,
    *,
    logger: logging.Logger,
    missing_dependency_message: str,
) -> dict[str, Any]:
    toml_module = _load_toml_module()
    if toml_module is None:
        logger.warning(missing_dependency_message)
        return {}
    if not config_path.is_file():
        return {}

    try:
        with config_path.open("rb") as file:
            data = toml_module.load(file)
    except OSError as exc:
        logger.warning("Skip loading %s: %s", config_path.name, exc)
        return {}
    except ValueError as exc:
        logger.warning("Skip loading %s: invalid TOML (%s)", config_path.name, exc)
        return {}

    return data if isinstance(data, dict) else {}
