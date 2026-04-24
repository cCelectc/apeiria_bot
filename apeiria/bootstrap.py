from __future__ import annotations

"""Top-level NoneBot bootstrap used by bot.py and CLI entrypoints."""

from apeiria._user_loader import load_user_plugins, load_user_setup
from apeiria.runtime.bootstrapper import ApeiriaBootstrapper
from apeiria.runtime.phases.config import (
    resolve_driver_kwargs as _resolve_driver_kwargs,
)
from apeiria.runtime.phases.config import run_config_phase as _run_config_phase
from apeiria.runtime.phases.environment import (
    run_environment_phase as _run_environment_phase,
)
from apeiria.runtime.phases.framework import run_framework_phase as _run_framework_phase


def resolve_driver_kwargs(config_kwargs: dict[str, object]) -> dict[str, object]:
    """Compatibility export for config-phase driver resolution."""
    return _resolve_driver_kwargs(config_kwargs)


def _initialize_nonebot_legacy() -> None:
    """Compatibility wrapper while startup logic moves into explicit phases."""
    _run_environment_phase()
    _run_config_phase()
    load_user_setup()
    _run_framework_phase()
    load_user_plugins()


def initialize_nonebot() -> None:
    """Initialize NoneBot through the runtime bootstrapper."""
    ApeiriaBootstrapper().initialize_nonebot()


def run() -> None:
    """Convenience entrypoint for CLI-style execution."""
    ApeiriaBootstrapper().run()
