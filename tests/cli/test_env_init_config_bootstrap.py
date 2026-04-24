from __future__ import annotations

from types import SimpleNamespace
from typing import TYPE_CHECKING

from click.testing import CliRunner

from apeiria.cli.commands.env import env_init
from apeiria.environment.manager import EnvironmentService

if TYPE_CHECKING:
    import pathlib

    import pytest


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
