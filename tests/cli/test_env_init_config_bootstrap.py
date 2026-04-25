from __future__ import annotations

import sys
from types import ModuleType, SimpleNamespace
from typing import TYPE_CHECKING

from click.testing import CliRunner

from apeiria.cli.commands.env import env_init
from apeiria.environment.manager import EnvironmentService

if TYPE_CHECKING:
    import pathlib

    import pytest


class UnexpectedNoneBotInitError(AssertionError):
    """Raised if database validation leaks into NoneBot startup."""


def _write_text(path: pathlib.Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def test_ensure_project_config_files_creates_missing_targets(
    tmp_path: pathlib.Path,
) -> None:
    _write_text(tmp_path / "apeiria.config.example.toml", "config = true\n")
    _write_text(tmp_path / "apeiria.plugins.example.toml", "plugins = true\n")
    _write_text(tmp_path / "apeiria.adapters.example.toml", "adapters = true\n")
    _write_text(tmp_path / "apeiria.drivers.example.toml", "drivers = true\n")
    service = EnvironmentService(project_root=tmp_path)

    result = service.ensure_project_config_files()

    assert result.created == [
        "apeiria.config.toml",
        "apeiria.plugins.toml",
        "apeiria.adapters.toml",
        "apeiria.drivers.toml",
    ]
    assert result.skipped == []
    assert (tmp_path / "apeiria.config.toml").read_text(encoding="utf-8") == (
        "config = true\n"
    )
    assert (tmp_path / "apeiria.plugins.toml").read_text(encoding="utf-8") == (
        "plugins = true\n"
    )


def test_ensure_project_config_files_skips_existing_targets(
    tmp_path: pathlib.Path,
) -> None:
    _write_text(tmp_path / "apeiria.config.example.toml", "from_example = true\n")
    _write_text(tmp_path / "apeiria.plugins.example.toml", "plugins = true\n")
    _write_text(tmp_path / "apeiria.adapters.example.toml", "adapters = true\n")
    _write_text(tmp_path / "apeiria.drivers.example.toml", "drivers = true\n")
    _write_text(tmp_path / "apeiria.config.toml", "keep = true\n")
    service = EnvironmentService(project_root=tmp_path)

    result = service.ensure_project_config_files()

    assert result.created == [
        "apeiria.plugins.toml",
        "apeiria.adapters.toml",
        "apeiria.drivers.toml",
    ]
    assert result.skipped == ["apeiria.config.toml"]
    assert (tmp_path / "apeiria.config.toml").read_text(encoding="utf-8") == (
        "keep = true\n"
    )


def test_env_init_reports_created_and_skipped_configs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = CliRunner()

    def fake_initialize_user_environment(
        *,
        no_dev: bool = False,
    ) -> SimpleNamespace:
        assert no_dev is False
        return SimpleNamespace(
            created=["apeiria.config.toml", "apeiria.plugins.toml"],
            skipped=["apeiria.adapters.toml", "apeiria.drivers.toml"],
        )

    monkeypatch.setattr(
        "apeiria.cli.commands.env.check_system_dependencies",
        lambda: None,
    )
    monkeypatch.setattr("apeiria.cli.commands.env._", lambda text: text)
    monkeypatch.setattr(
        "apeiria.cli.commands.env.initialize_user_environment",
        fake_initialize_user_environment,
    )

    result = runner.invoke(env_init, [])

    assert result.exit_code == 0
    assert "created config: apeiria.config.toml" in result.output
    assert "created config: apeiria.plugins.toml" in result.output
    assert "skipped config: apeiria.adapters.toml" in result.output
    assert "skipped config: apeiria.drivers.toml" in result.output
    assert "initialized environment" in result.output
    assert "user_bot.example.py" in result.output


def test_validate_database_schema_uses_project_database_without_nonebot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    bootstrap = ModuleType("apeiria.bootstrap")

    def unexpected_initialize_nonebot() -> None:
        raise UnexpectedNoneBotInitError

    bootstrap.initialize_nonebot = unexpected_initialize_nonebot  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "apeiria.bootstrap", bootstrap)
    service = EnvironmentService(project_root=tmp_path)

    service.validate_database_schema()

    assert (tmp_path / "data" / "db" / "apeiria.sqlite3").is_file()


def test_runtime_export_includes_sqlite_database(tmp_path: pathlib.Path) -> None:
    service = EnvironmentService(project_root=tmp_path)
    service.validate_database_schema()

    target_root, copied = service.export_runtime_state(tmp_path / "bundle")

    assert copied == 1
    assert target_root == (tmp_path / "bundle").resolve()
    assert (target_root / "data" / "db" / "apeiria.sqlite3").is_file()


def test_runtime_import_keeps_existing_database_when_bundle_has_no_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    source_root = tmp_path / "bundle"
    source_root.mkdir()
    service = EnvironmentService(project_root=tmp_path / "project")
    service.validate_database_schema()
    database_path = tmp_path / "project" / "data" / "db" / "apeiria.sqlite3"
    monkeypatch.setattr(service, "initialize_user_environment", lambda: None)

    _source_root, copied = service.import_runtime_state(source_root)

    assert copied == 0
    assert database_path.is_file()


def test_runtime_import_restores_sqlite_database(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: pathlib.Path,
) -> None:
    source_root = tmp_path / "bundle"
    source_database = source_root / "data" / "db" / "apeiria.sqlite3"
    source_database.parent.mkdir(parents=True)
    source_database.write_bytes(b"sqlite bundle")
    service = EnvironmentService(project_root=tmp_path / "project")
    monkeypatch.setattr(service, "initialize_user_environment", lambda: None)

    _source_root, copied = service.import_runtime_state(source_root)

    assert copied == 1
    assert (
        tmp_path / "project" / "data" / "db" / "apeiria.sqlite3"
    ).read_bytes() == b"sqlite bundle"
