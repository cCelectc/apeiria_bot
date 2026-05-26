from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Callable

    import pytest


@dataclass(frozen=True)
class _BootstrapperPhases:
    environment: Callable[[], list[str]]
    config: Callable[[], None]
    database: Callable[..., str]
    user_extensions: Callable[[], None]
    framework: Callable[[], None]
    runtime: Callable[[], None]
    user_plugins: Callable[[], None]


def test_bootstrapper_passes_startup_pending_uninstalls_to_database_cleanup(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from apeiria.runtime.bootstrapper import ApeiriaBootstrapper

    calls: list[tuple[str, object]] = []

    def stub_environment_phase() -> list[str]:
        calls.append(("environment", None))
        return ["plugins.pending"]

    def stub_config_phase() -> None:
        calls.append(("config", None))

    def stub_database_phase(*, pending_plugin_module_uninstalls: set[str]) -> str:
        calls.append(("database", pending_plugin_module_uninstalls))
        return "db-runtime"

    def stub_user_extensions_phase() -> None:
        calls.append(("user_extensions", None))

    def stub_framework_phase() -> None:
        calls.append(("framework", None))

    def stub_runtime_phase() -> None:
        calls.append(("runtime", None))

    def stub_user_plugins_phase() -> None:
        calls.append(("user_plugins", None))

    phases = _BootstrapperPhases(
        environment=stub_environment_phase,
        config=stub_config_phase,
        database=stub_database_phase,
        user_extensions=stub_user_extensions_phase,
        framework=stub_framework_phase,
        runtime=stub_runtime_phase,
        user_plugins=stub_user_plugins_phase,
    )

    _patch_bootstrapper_phases(
        monkeypatch,
        phases=phases,
    )

    bootstrapper = ApeiriaBootstrapper()
    bootstrapper.initialize_nonebot()

    assert bootstrapper.database == "db-runtime"
    assert calls == [
        ("environment", None),
        ("config", None),
        ("database", {"plugins.pending"}),
        ("user_extensions", None),
        ("framework", None),
        ("runtime", None),
        ("user_plugins", None),
    ]


def _patch_bootstrapper_phases(
    monkeypatch: pytest.MonkeyPatch,
    *,
    phases: _BootstrapperPhases,
) -> None:
    from apeiria.runtime.bootstrapper import ApeiriaBootstrapper

    def patched_run_environment_phase(self: ApeiriaBootstrapper) -> None:
        self._startup_pending_plugin_module_uninstalls = set(phases.environment())

    def patched_run_database_phase(self: ApeiriaBootstrapper) -> None:
        self.database = phases.database(
            pending_plugin_module_uninstalls=(
                self._startup_pending_plugin_module_uninstalls
            )
        )

    monkeypatch.setattr(
        ApeiriaBootstrapper,
        "_run_environment_phase",
        patched_run_environment_phase,
    )
    monkeypatch.setattr(
        ApeiriaBootstrapper,
        "_run_config_phase",
        _wrap_phase(phases.config),
    )
    monkeypatch.setattr(
        ApeiriaBootstrapper,
        "_run_database_phase",
        patched_run_database_phase,
    )
    monkeypatch.setattr(
        ApeiriaBootstrapper,
        "_run_user_extensions_phase",
        _wrap_phase(phases.user_extensions),
    )
    monkeypatch.setattr(
        ApeiriaBootstrapper,
        "_run_framework_phase",
        _wrap_phase(phases.framework),
    )
    monkeypatch.setattr(
        ApeiriaBootstrapper,
        "_run_runtime_phase",
        _wrap_phase(phases.runtime),
    )
    monkeypatch.setattr(
        ApeiriaBootstrapper,
        "_run_user_plugins_phase",
        _wrap_phase(phases.user_plugins),
    )


def _wrap_phase(callback: Callable[[], None]) -> Callable[[object], None]:
    def runner(self: object) -> None:
        _ = self
        callback()

    return runner
