from __future__ import annotations

import tempfile
from pathlib import Path


def test_load_from_toml(tmp_path: Path) -> None:
    import apeiria.config.loader as loader_mod

    old_root = loader_mod._PROJECT_ROOT
    loader_mod._PROJECT_ROOT = tmp_path
    try:
        config_file = tmp_path / "apeiria.config.toml"
        config_file.write_text(
            'host = "127.0.0.1"\nport = 9090\nsuperusers = ["admin"]\n',
            encoding="utf-8",
        )
        result = loader_mod.load_startup_kwargs()
        assert result["host"] == "127.0.0.1"
        assert result["port"] == 9090  # noqa: PLR2004
        assert "admin" in result["superusers"]
    finally:
        loader_mod._PROJECT_ROOT = old_root


def test_load_missing_config() -> None:
    import apeiria.config.loader as loader_mod

    with tempfile.TemporaryDirectory() as d:
        old_root = loader_mod._PROJECT_ROOT
        loader_mod._PROJECT_ROOT = Path(d)
        try:
            result = loader_mod.load_startup_kwargs()
            assert isinstance(result, dict)
        finally:
            loader_mod._PROJECT_ROOT = old_root


def test_load_plugins_toml(tmp_path: Path) -> None:
    import apeiria.config.loader as loader_mod

    old_root = loader_mod._PROJECT_ROOT
    loader_mod._PROJECT_ROOT = tmp_path
    try:
        plugins_file = tmp_path / "apeiria.plugins.toml"
        plugins_file.write_text(
            'plugins = ["plugin_a", "plugin_b"]\n',
            encoding="utf-8",
        )
        result = loader_mod.load_startup_kwargs()
        assert result["_plugins"] == ["plugin_a", "plugin_b"]
    finally:
        loader_mod._PROJECT_ROOT = old_root
