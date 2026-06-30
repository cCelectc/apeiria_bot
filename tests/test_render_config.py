from __future__ import annotations

import json
import os


def test_render_config_injection() -> None:
    from apeiria.config.loader import expand_config
    from apeiria.config.models import AppConfig

    app = AppConfig()
    app.plugins = {
        "htmlrender": {
            "render_backend": "playwright",
            "render_startup_mode": "off",
            "render_playwright": {
                "skip_browser_install": True,
                "launch_args": "--no-sandbox --disable-gpu",
            },
        }
    }
    expand_config(app)
    try:
        assert os.environ["RENDER_BACKEND"] == "playwright"
        assert os.environ["RENDER_STARTUP_MODE"] == "off"
        pw = json.loads(os.environ["RENDER_PLAYWRIGHT"])
        assert pw["skip_browser_install"] is True
        assert "--disable-gpu" in pw["launch_args"]
    finally:
        for key in ("RENDER_BACKEND", "RENDER_STARTUP_MODE", "RENDER_PLAYWRIGHT"):
            os.environ.pop(key, None)


def test_init_template_contains_htmlrender(tmp_path, monkeypatch) -> None:
    from click.testing import CliRunner

    from apeiria.cli.init_cmd import init_cmd

    monkeypatch.chdir(tmp_path)
    result = CliRunner().invoke(init_cmd, input="\n\n")
    assert result.exit_code == 0, result.output

    config_text = (tmp_path / "data" / "config.yaml").read_text(encoding="utf-8")
    assert "htmlrender:" in config_text
    assert "render_backend: playwright" in config_text
    assert 'render_startup_mode: "off"' in config_text
    assert "skip_browser_install: true" in config_text
