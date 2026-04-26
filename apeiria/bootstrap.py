from __future__ import annotations

"""Top-level NoneBot bootstrap used by bot.py and CLI entrypoints."""

from apeiria.runtime.bootstrapper import ApeiriaBootstrapper
from apeiria.runtime.phases.config import (
    resolve_driver_kwargs as _resolve_driver_kwargs,
)


def resolve_driver_kwargs(config_kwargs: dict[str, object]) -> dict[str, object]:
    """Compatibility export for config-phase driver resolution."""
    return _resolve_driver_kwargs(config_kwargs)


def initialize_nonebot() -> None:
    """Initialize NoneBot through the runtime bootstrapper."""
    ApeiriaBootstrapper().initialize_nonebot()


def run() -> None:
    """Convenience entrypoint for CLI-style execution."""
    ApeiriaBootstrapper().run()
