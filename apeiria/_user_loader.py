from __future__ import annotations

import inspect
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from typing import TYPE_CHECKING

import nonebot

from apeiria.config import adapter_config_service, plugin_config_service
from apeiria.environment.extension_project import inject_plugin_site_packages

if TYPE_CHECKING:
    from types import ModuleType


_CONFIGURE_WITH_NB_ARGS = 2


def _project_root() -> Path:
    return Path(__file__).resolve().parent.parent


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
    """Invoke `configure()` from `user_bot.py` with backward-compatible arity."""
    configure = getattr(module, "configure", None)
    if configure is None:
        nonebot.logger.warning("Skip loading user_bot.py: missing configure()")
        return

    if not callable(configure):
        nonebot.logger.warning("Skip loading user_bot.py: configure is not callable")
        return

    signature = inspect.signature(configure)
    parameters = list(signature.parameters.values())
    accepts_varargs = any(
        parameter.kind is inspect.Parameter.VAR_POSITIONAL for parameter in parameters
    )
    positional_params = [
        parameter
        for parameter in parameters
        if parameter.kind
        in (
            inspect.Parameter.POSITIONAL_ONLY,
            inspect.Parameter.POSITIONAL_OR_KEYWORD,
        )
    ]
    if accepts_varargs or len(positional_params) >= _CONFIGURE_WITH_NB_ARGS:
        configure(driver, nonebot)
    else:
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
