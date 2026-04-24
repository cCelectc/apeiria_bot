from __future__ import annotations

from typing import TYPE_CHECKING

import nonebot

if TYPE_CHECKING:
    from apeiria.runtime.context import ApeiriaRuntime


class ApeiriaBootstrapper:
    """Minimal bootstrap façade for the explicit startup phases."""

    _PHASE_NAMES: tuple[str, ...] = (
        "environment",
        "config",
        "user_extensions",
        "framework",
        "runtime",
        "user_plugins",
    )

    def __init__(self) -> None:
        self.runtime: ApeiriaRuntime | None = None

    def phase_names(self) -> tuple[str, ...]:
        return self._PHASE_NAMES

    def initialize_nonebot(self) -> None:
        from apeiria.runtime.context import get_current_runtime, set_current_runtime

        previous_runtime = get_current_runtime()
        previous_bootstrapper_runtime = self.runtime

        try:
            self._run_environment_phase()
            self._run_config_phase()
            self._run_user_extensions_phase()
            self._run_framework_phase()
            self._run_runtime_phase()
            self._run_user_plugins_phase()
        except Exception:
            set_current_runtime(previous_runtime)
            self.runtime = previous_bootstrapper_runtime
            raise

    def _run_environment_phase(self) -> None:
        from apeiria.runtime.phases.environment import run_environment_phase

        run_environment_phase()

    def _run_config_phase(self) -> None:
        from apeiria.runtime.phases.config import run_config_phase

        run_config_phase()

    def _run_framework_phase(self) -> None:
        from apeiria.runtime.phases.framework import run_framework_phase

        run_framework_phase()

    def _run_runtime_phase(self) -> None:
        from apeiria.runtime.context import set_current_runtime
        from apeiria.runtime.control_plane import ApeiriaControlPlane
        from apeiria.runtime.phases.runtime import build_runtime

        self.runtime = build_runtime()
        self.runtime.control_plane = ApeiriaControlPlane(self.runtime)
        set_current_runtime(self.runtime)

    def _run_user_extensions_phase(self) -> None:
        from apeiria._user_loader import load_user_setup

        load_user_setup()

    def _run_user_plugins_phase(self) -> None:
        from apeiria._user_loader import load_user_plugins

        load_user_plugins()

    def run(self) -> None:
        self.initialize_nonebot()
        nonebot.run()
