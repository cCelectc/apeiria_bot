from __future__ import annotations

import sqlite3
from typing import TYPE_CHECKING

import pytest

from apeiria.bot import entry
from apeiria.environment.manager import EnvironmentService
from apeiria.utils.project_context import (
    reset_active_project_root,
    set_active_project_root,
)

if TYPE_CHECKING:
    from collections.abc import Iterator
    from pathlib import Path


class UnexpectedBootstrapError(AssertionError):
    """Raised when startup reaches the bootstrapper too early."""


class UnexpectedEnvironmentMutationError(AssertionError):
    """Raised when the guard tries to run setup or repair operations."""


@pytest.fixture
def active_project(tmp_path: Path) -> "Iterator[Path]":
    token = set_active_project_root(tmp_path)
    try:
        yield tmp_path
    finally:
        reset_active_project_root(token)


def test_fresh_project_reports_env_init_before_bootstrapper(
    monkeypatch: pytest.MonkeyPatch,
    active_project: Path,
) -> None:
    _write_example_templates(active_project)
    _fail_if_bootstrapper_runs(monkeypatch)

    with pytest.raises(RuntimeError) as exc_info:
        entry.run()

    message = str(exc_info.value)
    assert "local environment has not been initialized" in message
    assert "apeiria env init" in message
    assert "apeiria env repair" not in message


def test_ready_project_delegates_to_bootstrapper(
    monkeypatch: pytest.MonkeyPatch,
    active_project: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _prepare_ready_environment(active_project)
    calls: list[str] = []

    class StubBootstrapper:
        def run(self) -> None:
            calls.append("run")

    monkeypatch.setattr(entry, "ApeiriaBootstrapper", StubBootstrapper)

    entry.run()

    assert calls == ["run"]
    assert capsys.readouterr().err == ""


def test_missing_extension_project_reports_env_repair(
    monkeypatch: pytest.MonkeyPatch,
    active_project: Path,
) -> None:
    _write_project_configs(active_project)
    (active_project / ".venv").mkdir()
    _fail_if_bootstrapper_runs(monkeypatch)

    with pytest.raises(RuntimeError) as exc_info:
        entry.run()

    message = str(exc_info.value)
    assert "Managed extension project is missing" in message
    assert "apeiria env repair" in message


def test_incompatible_database_reports_db_repair_without_bootstrapper(
    monkeypatch: pytest.MonkeyPatch,
    active_project: Path,
) -> None:
    _prepare_ready_environment(active_project)
    database_path = active_project / "data" / "db" / "apeiria.sqlite3"
    database_path.parent.mkdir(parents=True)
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE unrelated (id INTEGER PRIMARY KEY)")
    _fail_if_bootstrapper_runs(monkeypatch)

    with pytest.raises(RuntimeError) as exc_info:
        entry.run()

    message = str(exc_info.value)
    assert "database" in message.lower()
    assert "apeiria db repair" in message


def test_entry_guard_does_not_run_setup_or_repair_commands(
    monkeypatch: pytest.MonkeyPatch,
    active_project: Path,
) -> None:
    _write_example_templates(active_project)
    _fail_if_bootstrapper_runs(monkeypatch)

    def unexpected_command(*_args: object, **_kwargs: object) -> None:
        raise UnexpectedEnvironmentMutationError

    monkeypatch.setattr(
        EnvironmentService,
        "initialize_user_environment",
        unexpected_command,
    )
    monkeypatch.setattr(EnvironmentService, "sync_main_project", unexpected_command)
    monkeypatch.setattr(EnvironmentService, "sync_plugin_project", unexpected_command)
    monkeypatch.setattr(
        EnvironmentService,
        "repair_database_schema",
        unexpected_command,
    )

    with pytest.raises(RuntimeError) as exc_info:
        entry.run()

    assert "apeiria env init" in str(exc_info.value)


def test_entry_guard_does_not_mutate_project_state(
    monkeypatch: pytest.MonkeyPatch,
    active_project: Path,
) -> None:
    _prepare_ready_environment(active_project)
    database_path = active_project / "data" / "db" / "apeiria.sqlite3"
    auth_path = active_project / "data" / "web_ui" / "secret.json"
    database_path.parent.mkdir(parents=True)
    auth_path.parent.mkdir(parents=True)
    database_path.write_bytes(b"not sqlite")
    auth_path.write_text('{"token_secret":"keep"}\n', encoding="utf-8")
    _fail_if_bootstrapper_runs(monkeypatch)

    before = {
        path: path.read_bytes()
        for path in (
            active_project / "apeiria.config.toml",
            active_project / "apeiria.plugins.toml",
            active_project / "apeiria.adapters.toml",
            active_project / "apeiria.drivers.toml",
            active_project / ".env",
            active_project / ".env.dev",
            active_project / ".env.prod",
            active_project / ".apeiria" / "extensions" / "pyproject.toml",
            auth_path,
            database_path,
        )
    }

    with pytest.raises(RuntimeError) as exc_info:
        entry.run()

    assert "apeiria db repair" in str(exc_info.value)
    assert {path: path.read_bytes() for path in before} == before


def _fail_if_bootstrapper_runs(monkeypatch: pytest.MonkeyPatch) -> None:
    class StubBootstrapper:
        def run(self) -> None:
            raise UnexpectedBootstrapError

    monkeypatch.setattr(entry, "ApeiriaBootstrapper", StubBootstrapper)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_example_templates(project_root: Path) -> None:
    _write_text(project_root / "apeiria.config.example.toml", "config = true\n")
    _write_text(project_root / "apeiria.plugins.example.toml", "plugins = true\n")
    _write_text(project_root / "apeiria.adapters.example.toml", "adapters = true\n")
    _write_text(project_root / "apeiria.drivers.example.toml", "drivers = true\n")


def _write_project_configs(project_root: Path) -> None:
    _write_text(project_root / "apeiria.config.toml", "config = true\n")
    _write_text(project_root / "apeiria.plugins.toml", "plugins = true\n")
    _write_text(project_root / "apeiria.adapters.toml", "adapters = true\n")
    _write_text(project_root / "apeiria.drivers.toml", "drivers = true\n")
    _write_text(project_root / ".env", "ENV=keep\n")
    _write_text(project_root / ".env.dev", "ENV=dev\n")
    _write_text(project_root / ".env.prod", "ENV=prod\n")


def _prepare_ready_environment(project_root: Path) -> None:
    _write_project_configs(project_root)
    (project_root / ".venv").mkdir()
    _write_text(
        project_root / ".apeiria" / "extensions" / "pyproject.toml",
        '[project]\nname = "apeiria-user-plugins"\n',
    )
