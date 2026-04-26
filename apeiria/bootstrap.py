from __future__ import annotations

"""Top-level NoneBot bootstrap used by bot.py and CLI entrypoints."""

from apeiria.runtime.bootstrapper import ApeiriaBootstrapper


def initialize_nonebot() -> None:
    """Initialize NoneBot through the runtime bootstrapper."""
    ApeiriaBootstrapper().initialize_nonebot()


def run() -> None:
    """Convenience entrypoint for CLI-style execution."""
    ApeiriaBootstrapper().run()
