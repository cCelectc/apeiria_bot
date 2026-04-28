from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.runtime.bootstrapper import ApeiriaBootstrapper

if TYPE_CHECKING:
    from pytest import MonkeyPatch


def test_bootstrapper_exposes_explicit_phase_names() -> None:
    assert ApeiriaBootstrapper().phase_names() == (
        "environment",
        "config",
        "database",
        "user_extensions",
        "framework",
        "runtime",
        "user_plugins",
    )


def test_initialize_nonebot_delegates_to_bootstrapper(
    monkeypatch: MonkeyPatch,
) -> None:
    from apeiria import bootstrap

    calls: list[str] = []

    class StubBootstrapper:
        def initialize_nonebot(self) -> None:
            calls.append("initialize_nonebot")

    monkeypatch.setattr(bootstrap, "ApeiriaBootstrapper", StubBootstrapper)

    bootstrap.initialize_nonebot()

    assert calls == ["initialize_nonebot"]


def test_bootstrap_no_longer_exposes_legacy_initialize_wrapper() -> None:
    from apeiria import bootstrap

    assert not hasattr(bootstrap, "_initialize_nonebot_legacy")
    assert not hasattr(bootstrap, "resolve_driver_kwargs")


def test_bootstrapper_initialize_nonebot_runs_explicit_phases_in_order(
    monkeypatch: MonkeyPatch,
) -> None:
    calls: list[str] = []
    bootstrapper = ApeiriaBootstrapper()

    monkeypatch.setattr(
        bootstrapper,
        "_run_environment_phase",
        lambda: calls.append("environment"),
    )
    monkeypatch.setattr(
        bootstrapper,
        "_run_config_phase",
        lambda: calls.append("config"),
    )
    monkeypatch.setattr(
        bootstrapper,
        "_run_database_phase",
        lambda: calls.append("database"),
    )
    monkeypatch.setattr(
        bootstrapper,
        "_run_framework_phase",
        lambda: calls.append("framework"),
    )
    monkeypatch.setattr(
        bootstrapper,
        "_run_runtime_phase",
        lambda: calls.append("runtime"),
    )
    monkeypatch.setattr(
        bootstrapper,
        "_run_user_extensions_phase",
        lambda: calls.append("user_extensions"),
    )
    monkeypatch.setattr(
        bootstrapper,
        "_run_user_plugins_phase",
        lambda: calls.append("user_plugins"),
    )

    bootstrapper.initialize_nonebot()

    assert calls == [
        "environment",
        "config",
        "database",
        "user_extensions",
        "framework",
        "runtime",
        "user_plugins",
    ]


def test_bootstrapper_database_phase_stores_bootstrapped_database(
    monkeypatch: MonkeyPatch,
) -> None:
    bootstrapper = ApeiriaBootstrapper()
    database = object()

    monkeypatch.setattr(
        "apeiria.runtime.phases.database.run_database_phase",
        lambda: database,
    )

    bootstrapper._run_database_phase()

    assert bootstrapper.database is database


def test_bootstrap_run_delegates_to_bootstrapper(monkeypatch: MonkeyPatch) -> None:
    from apeiria import bootstrap

    calls: list[str] = []

    class StubBootstrapper:
        def run(self) -> None:
            calls.append("run")

    monkeypatch.setattr(bootstrap, "ApeiriaBootstrapper", StubBootstrapper)

    bootstrap.run()

    assert calls == ["run"]


def test_bot_entry_run_delegates_to_bootstrapper(monkeypatch: MonkeyPatch) -> None:
    from apeiria.bot import entry

    calls: list[str] = []

    class StubBootstrapper:
        def run(self) -> None:
            calls.append("run")

    def fake_guard(*, project_root: object | None = None) -> None:
        assert project_root is None
        calls.append("guard")

    monkeypatch.setattr(entry, "ensure_entry_environment_ready", fake_guard)
    monkeypatch.setattr(entry, "ApeiriaBootstrapper", StubBootstrapper)

    entry.run()

    assert calls == ["guard", "run"]
