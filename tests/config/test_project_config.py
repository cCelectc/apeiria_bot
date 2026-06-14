"""Tests for project configuration loading."""

from __future__ import annotations

from typing import TYPE_CHECKING

from apeiria.config.project import ProjectConfigService

if TYPE_CHECKING:
    from pathlib import Path

    import pytest


def test_load_missing_config_returns_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "nonexistent.toml"
    svc = ProjectConfigService()
    result = svc.read_project_config(config_path)
    assert result is not None


def test_project_config_service_uses_target_path(tmp_path: Path) -> None:
    config_path = tmp_path / "apeiria.config.toml"
    config_path.write_text('name = "testbot"\n', encoding="utf-8")
    svc = ProjectConfigService()
    result = svc.read_project_config(config_path)
    assert result.get("name") == "testbot"


def test_read_config_from_existing_file(tmp_path: Path) -> None:
    config_path = tmp_path / "apeiria.config.toml"
    config_path.write_text('name = "testbot"\n', encoding="utf-8")
    svc = ProjectConfigService()
    result = svc.read_project_config(config_path)
    assert result.get("name") == "testbot"


def test_default_config_path_uses_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    config_path = tmp_path / "apeiria.config.toml"
    config_path.write_text('name = "localbot"\n', encoding="utf-8")
    svc = ProjectConfigService()
    result = svc.read_project_config()
    assert result.get("name") == "localbot"
