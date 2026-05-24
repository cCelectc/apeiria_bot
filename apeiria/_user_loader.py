from __future__ import annotations

"""User setup and plugin loading helpers for runtime bootstrap."""

from importlib.util import module_from_spec, spec_from_file_location
from typing import TYPE_CHECKING

import nonebot

from apeiria.config import adapter_config_service, plugin_config_service
from apeiria.environment.extension_project import inject_plugin_site_packages
from apeiria.utils.project_context import current_project_root

if TYPE_CHECKING:
    from pathlib import Path
    from types import ModuleType


def _project_root() -> Path:
    return current_project_root()


def _load_user_module(user_bot: Path) -> ModuleType | None:
    """Load the optional local `user_bot.py` module if it exists."""
    if not user_bot.is_file():
        return None

    spec = spec_from_file_location("user_bot", user_bot)
    if spec is None or spec.loader is None:
        nonebot.logger.warning("Skip loading user_bot.py: invalid module spec")
        return None

    module = module_from_spec(spec)
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # noqa: BLE001
        nonebot.logger.warning("Skip loading {}: {}", user_bot.name, exc)
        return None
    return module


def _apply_user_module(module: ModuleType, driver: object) -> None:
    """Invoke `configure()` from `user_bot.py` with the current setup contract."""
    configure = getattr(module, "configure", None)
    if configure is None:
        nonebot.logger.warning("Skip loading user_bot.py: missing configure()")
        return

    if not callable(configure):
        nonebot.logger.warning("Skip loading user_bot.py: configure is not callable")
        return

    configure(driver)


def load_user_setup(user_bot: Path | None = None) -> None:
    """Load local user setup hooks and configured adapters."""
    target = user_bot or _project_root() / "user_bot.py"
    module = _load_user_module(target)
    if module is not None:
        _apply_user_module(module, nonebot.get_driver())
    adapter_config_service.load_project_adapters(nonebot.get_driver())


def load_user_plugins() -> None:
    """Load project plugins from the managed plugin config after bootstrap."""
    # Re-inject extension site-packages defensively: framework plugin load in
    # between may have altered sys.path, and user plugins are the first code
    # to rely on extension venv packages.
    inject_plugin_site_packages()
    plugin_config_service.load_project_plugins()
